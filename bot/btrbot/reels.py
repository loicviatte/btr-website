"""Reels cut from the latest episode (workflow: claude/btr-reels-workflow.md in the Claude project).

1. Claude proposes 10 moments from the transcript, Loïc ticks the ones he wants (6 a week).
2. For each: the bot downloads only that section in 4K, transcribes it word by word (Parakeet, on the server),
   finds the exact first/last words, cuts the long silences (found on the sound itself, at the quietest 10 ms),
   follows the source edit shot by shot (guest close-up, Marius close-up, or the wide shot of both → split screen:
   guest on top, Marius below), renders 1080×1920 on an exact frame grid (any frame rate), brings the sound to
   −14 LUFS (two passes, peak limited, no music) and burns the v3 subtitles.
3. Subtitles show only words the speaker really says (they come from the transcription of the same audio).
"""
import json
import math
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

import numpy as np

YT = "https://www.youtube.com/watch?v={}"
OUT_W, OUT_H = 1080, 1920
PAD = 6.0                 # seconds downloaded before/after the moment, to find the exact words
MIN_LEN, MAX_LEN = 15.0, 90.0
GAP_CUT, GAP_KEEP = 0.40, 0.14   # silences longer than GAP_CUT are cut down to GAP_KEEP
END_TAIL = 0.40           # a breath after the last word (~10 frames) instead of a dry cut, if the pause allows it
LOCATE_MIN = 70           # below this fuzzy score the moment is not in the clip: fail instead of cutting elsewhere
TARGET_LUFS = -14.0
TG_LIMIT = 49 * 2 ** 20   # Telegram bots cannot send files over 50 MB
ASR_DIR = "sherpa-onnx-nemo-parakeet-tdt-0.6b-v2-int8"


@dataclass
class Word:
    text: str
    start: float
    end: float


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9']", "", (s or "").lower().replace("’", "'"))


def run(cmd: list, **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], check=True, capture_output=True, text=True, **kw)


# ---------------------------------------------------------------- download
def section_bounds(start: float, end: float) -> tuple[int, int]:
    """Whole seconds around the moment: a section that starts on a whole second keeps picture and sound aligned."""
    return max(0, int(math.floor(start - PAD))), int(math.ceil(end + PAD))


def download_section(video_id: str, a: int, b: int, dest: Path, cookies: Path | None) -> Path:
    """Only [a, b] seconds of the episode, best quality up to 4K. VP9/H.264 preferred over AV1 (faster to decode)."""
    import yt_dlp
    from yt_dlp.utils import download_range_func
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bv*[height<=2160][vcodec^=vp09]+ba/bv*[height<=2160][vcodec^=avc1]+ba/bv*[height<=2160]+ba/b",
        "merge_output_format": "mp4", "outtmpl": str(dest.with_suffix(".%(ext)s")),
        "download_ranges": download_range_func(None, [(a, b)]),
        "quiet": True, "no_warnings": True, "noprogress": True,
    }
    if cookies and cookies.exists():
        opts["cookiefile"] = str(cookies)
    with yt_dlp.YoutubeDL(opts) as y:
        y.download([YT.format(video_id)])
    if not dest.exists():
        found = sorted(dest.parent.glob(dest.stem + ".*"))
        if not found:
            raise RuntimeError("téléchargement de l'extrait vide")
        found[0].replace(dest)
    return dest


def probe(path: Path) -> dict:
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height,r_frame_rate:format=duration", "-of", "json", path])
    j = json.loads(r.stdout)
    s = j["streams"][0]
    rate = Fraction(s["r_frame_rate"]) if s.get("r_frame_rate", "0/0") != "0/0" else Fraction(25)
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": float(rate), "rate": f"{rate.numerator}/{rate.denominator}",
            "duration": float(j["format"]["duration"])}


# ---------------------------------------------------------------- speech → words
def audio_offset(section_start: float, fps: float) -> float:
    """A section cut from a whole second starts its picture on the next frame boundary: at 29.97 or 23.976 fps the
    sound starts a few ms earlier than the picture. Skipping that much sound keeps them aligned (0 at 25/50 fps)."""
    return max(0.0, math.ceil(section_start * fps - 1e-6) / fps - section_start)


def extract_wav(src: Path, dest: Path, offset: float = 0.0) -> Path:
    af = ["-af", f"atrim=start={offset:.6f},asetpts=PTS-STARTPTS"] if offset > 1e-4 else []
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", *af, "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dest])
    return dest


def read_wav(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return sr, data.astype(np.float32) / 32768.0


class Transcriber:
    """NVIDIA Parakeet TDT 0.6B (int8) through sherpa-onnx, on CPU: words with their start/end times."""

    def __init__(self, models_dir: Path, threads: int = 2):
        import sherpa_onnx
        d = Path(models_dir) / ASR_DIR
        if not (d / "encoder.int8.onnx").exists():
            raise RuntimeError(f"modèle de transcription absent ({d}) : relancer install.sh")
        self.rec = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"), decoder=str(d / "decoder.int8.onnx"),
            joiner=str(d / "joiner.int8.onnx"), tokens=str(d / "tokens.txt"),
            num_threads=threads, model_type="nemo_transducer", decoding_method="greedy_search")

    def words(self, wav: Path, chunk: float = 50.0) -> list[Word]:
        sr, x = read_wav(wav)
        out: list[Word] = []
        step = int(chunk * sr)
        pos = 0
        while pos < len(x):
            # cut chunks in the quietest spot of the last 6 s, never in the middle of a word
            stop = min(len(x), pos + step)
            if stop < len(x):
                win = x[stop - 6 * sr:stop]
                e = np.convolve(win ** 2, np.ones(sr // 20), "same")
                stop = stop - 6 * sr + int(np.argmin(e))
            out += self._decode(x[pos:stop], sr, pos / sr)
            pos = stop
        return out

    def _decode(self, samples: np.ndarray, sr: int, offset: float) -> list[Word]:
        s = self.rec.create_stream()
        s.accept_waveform(sr, samples)
        self.rec.decode_stream(s)
        r = s.result
        toks, ts = list(r.tokens), list(r.timestamps)
        durs = list(getattr(r, "durations", []) or [])
        total = len(samples) / sr
        words: list[Word] = []
        for i, (tok, t) in enumerate(zip(toks, ts)):
            t = float(t)
            end = t + float(durs[i]) if i < len(durs) and durs[i] else (float(ts[i + 1]) if i + 1 < len(ts) else total)
            new_word = tok.startswith((" ", "▁")) or not words
            piece = tok.replace("▁", " ").strip()
            if not piece:
                continue
            if words and re.fullmatch(r"[^\w']+", piece):
                words[-1].text += piece        # punctuation sticks to the word, without stretching its end time
            elif words and not new_word:
                words[-1].text += piece
                words[-1].end = offset + end
            else:
                words.append(Word(piece, offset + t, offset + end))
        for a, b in zip(words, words[1:]):     # never let a word end after the next one starts
            a.end = min(max(a.end, a.start + 0.05), b.start)
        return words


# ---------------------------------------------------------------- the sound itself (silences)
class Energy:
    """Loudness of the clip every 10 ms: where speech really stops, and the quietest spot to cut."""
    HOP = 0.01

    def __init__(self, wav: Path):
        sr, x = read_wav(wav)
        n = int(sr * self.HOP)
        frames = len(x) // n
        rms = np.sqrt(np.mean(x[:frames * n].reshape(frames, n) ** 2, axis=1) + 1e-12) if frames else np.zeros(1)
        self.db = 20 * np.log10(rms + 1e-9)
        live = self.db[self.db > -90] if frames else self.db    # digital silence (inserted gaps) would skew the floor
        p10, p90 = (np.percentile(live, 10), np.percentile(live, 90)) if len(live) else (-60.0, -20.0)
        self.thr = float(min(max(p10 + 8, -50.0), p90 - 15))

    def _i(self, t: float) -> int:
        return int(np.clip(round(t / self.HOP), 0, len(self.db) - 1))

    def quiet(self, t0: float, t1: float) -> float:
        a, b = self._i(min(t0, t1)), self._i(max(t0, t1))
        if b <= a:
            return (t0 + t1) / 2
        return (a + int(np.argmin(self.db[a:b + 1]))) * self.HOP

    def silence(self, t0: float, t1: float, min_len: float = 0.05) -> tuple[float, float] | None:
        """Longest silent stretch in [t0, t1] (start, end) of at least `min_len` s, or None. (The closure inside a word,
        a few ms, is never taken for a pause.)"""
        a, b = self._i(t0), self._i(t1)
        best, cur, best_run = 0, None, None
        for k in range(a, b + 1):
            if self.db[k] < self.thr:
                cur = k if cur is None else cur
                if k - cur + 1 > best:
                    best, best_run = k - cur + 1, (cur, k)
            else:
                cur = None
        if not best_run or best * self.HOP < min_len:
            return None
        return best_run[0] * self.HOP, (best_run[1] + 1) * self.HOP


# ---------------------------------------------------------------- the moment inside the clip
def _find(words: list[Word], phrase: str, lo: int = 0, hi: int | None = None) -> tuple[int, float]:
    """Index of the word where `phrase` best starts (fuzzy), and the score 0-100."""
    from rapidfuzz import fuzz
    target = [norm(w) for w in phrase.split() if norm(w)]
    if not target or not words:
        return -1, 0.0
    hi = len(words) if hi is None else min(hi, len(words))
    toks = [norm(w.text) for w in words]
    best, best_i = 0.0, -1
    n = len(target)
    for i in range(lo, max(lo, hi - 1) + 1):
        if i >= len(toks):
            break
        sc = fuzz.ratio(" ".join(target), " ".join(toks[i:i + n]))
        if sc > best:
            best, best_i = sc, i
    return best_i, best


def locate(words: list[Word], first_words: str, last_words: str) -> tuple[int, int, float]:
    """(first word index, last word index, confidence) of the moment in the transcribed clip.
    Fails when the words are not really there, rather than cutting another passage."""
    i0, s0 = _find(words, first_words)
    if i0 < 0 or s0 < LOCATE_MIN:
        raise RuntimeError(f"je ne retrouve pas le début de l'extrait dans le son (score {s0:.0f}/100)")
    n_last = len([w for w in last_words.split() if norm(w)])
    i1s, s1 = _find(words, last_words, i0 + 1)
    if i1s < 0 or s1 < LOCATE_MIN:
        raise RuntimeError(f"je ne retrouve pas la fin de l'extrait dans le son (score {s1:.0f}/100)")
    i1 = min(len(words) - 1, i1s + max(n_last, 1) - 1)
    if i1 <= i0:
        raise RuntimeError("début et fin de l'extrait dans le mauvais ordre")
    return i0, i1, min(s0, s1)


def finish_sentence(words: list[Word], i1: int, max_words: int = 8, max_gap: float = 0.30) -> int:
    """The model's last words can stop one word short of the end of the sentence ("give" instead of "give me"):
    carry on to the end of the sentence while the speech flows (no pause), at most a few words."""
    k = i1
    for _ in range(max_words):
        if re.search(r"[.?!…]$", words[k].text) or k + 1 >= len(words) or words[k + 1].start - words[k].end > max_gap:
            break
        k += 1
    if k != i1 and not re.search(r"[.?!…]$", words[k].text):
        return i1                       # no sentence end close by: keep the model's end
    return k


def correct_with_srt(words: list[Word], cues: list, t0: float) -> list[Word]:
    """Loïc's own DaVinci SRT is the reference for the words (names like Motsi, mishearings): the speech model gives
    the timing, the SRT the text. `t0` = episode time of the clip's 0. Outside the stretch both agree on, nothing
    changes; a word the SRT has and the audio-model missed is added only where there is time for it."""
    from difflib import SequenceMatcher
    if not words or not cues:
        return words
    a, b = t0 + words[0].start - 3, t0 + words[-1].end + 3
    ref: list[tuple[str, float, float]] = []
    for c in cues:
        if c.end < a or c.start > b:
            continue
        toks = c.text.split()
        step = (c.end - c.start) / max(len(toks), 1)
        ref += [(t, c.start + i * step - t0, c.start + (i + 1) * step - t0) for i, t in enumerate(toks)]
    if not ref:
        return words
    ka, kb = [norm(w.text) for w in words], [norm(t) for t, _, _ in ref]
    ops = SequenceMatcher(None, ka, kb, autojunk=False).get_opcodes()
    eq = [o for o in ops if o[0] == "equal"]
    if not eq or sum(o[2] - o[1] for o in eq) < 0.5 * len(words):
        return words                    # the SRT does not cover this clip well: keep the audio model's words
    lo, hi = eq[0][1], eq[-1][2]        # only inside the stretch both agree on
    out: list[Word] = list(words[:lo])
    for tag, i1, i2, j1, j2 in ops:
        if i2 <= lo and i1 < lo or i1 >= hi:
            continue
        if tag == "equal":
            out += [Word(ref[j][0], words[i].start, words[i].end) for i, j in zip(range(i1, i2), range(j1, j2))]
        elif tag == "delete":
            out += words[i1:i2]          # said but not in the SRT (stutters): kept, the subtitles skip fillers
        elif tag == "replace":
            span_a, span_b = words[i1].start, words[i2 - 1].end
            n = j2 - j1
            out += [Word(ref[j][0], span_a + (span_b - span_a) * k / n, span_a + (span_b - span_a) * (k + 1) / n)
                    for k, j in enumerate(range(j1, j2))]
        elif tag == "insert":
            prev_end = out[-1].end if out else 0.0
            nxt = words[i1].start if i1 < len(words) else prev_end
            n = j2 - j1
            if nxt - prev_end >= 0.12 * n:
                out += [Word(ref[j][0], prev_end + (nxt - prev_end) * k / n, prev_end + (nxt - prev_end) * (k + 1) / n)
                        for k, j in enumerate(range(j1, j2))]
    out += words[hi:]
    return out


def keep_ranges(words: list[Word], i0: int, i1: int, energy: Energy, start_shift: float = 0.0, end_shift: float = 0.0,
                cut_phrases: list[str] = ()) -> tuple[list[tuple[float, float]], list[str]]:
    """Time ranges of the clip to keep, and the asked phrases that were not found. Long silences (measured on the
    sound) are shortened to GAP_KEEP; asked phrases are removed; every cut falls at a quiet spot between words, never
    inside the last word. Start/end shifts move the edges and every range is clipped to them."""
    removed: set[int] = set()
    missing: list[str] = []
    for ph in cut_phrases or ():
        j, sc = _find(words, ph, i0, i1 + 1)
        if j >= 0 and sc >= 85:
            removed.update(range(j, min(i1 + 1, j + len(ph.split()))))
        else:
            missing.append(ph)
    idx = [k for k in range(i0, i1 + 1) if k not in removed]
    if not idx:
        raise RuntimeError("rien à garder")

    def after(k: int) -> tuple[float, float]:
        """The pause after word k: from the end of its sound to the next word."""
        nxt = words[k + 1].start if k + 1 < len(words) else words[k].end + 0.8
        # a real pause (≥ 120 ms) anywhere after the word starts: the speech model often stretches the last word of a
        # sentence over the pause. Else a short one, but only near its end (never the closure inside a word).
        sil = energy.silence(words[k].start + 0.05, nxt + 0.05, 0.12) or \
            energy.silence(max(words[k].start + 0.05, words[k].end - 0.08), nxt + 0.05, 0.05)
        if sil:
            return sil
        e = max(energy.quiet(words[k].end, min(nxt, words[k].end + 0.12)), words[k].end - 0.03)
        return e, max(e, nxt)

    first, last = words[idx[0]], words[idx[-1]]
    # edges (start: just before the first word; end: where the last word's sound stops), then Loïc's shifts
    a = energy.quiet(first.start - 0.25, first.start - 0.02)
    if start_shift:
        a = energy.quiet(first.start + start_shift - 0.3, first.start + start_shift + 0.3)
    s_end, nxt_start = after(idx[-1])
    # the end: a breath after the last word's sound, unless the next word comes sooner (then just before it)
    room = nxt_start - 0.06 if idx[-1] + 1 < len(words) else s_end + END_TAIL
    b = max(min(s_end + END_TAIL, room), s_end + 0.04, last.end - 0.03)
    if end_shift:
        b = energy.quiet(b + end_shift - 0.3, b + end_shift + 0.3)
    # inner cuts: long pauses, removed phrases
    ranges: list[list[float]] = [[min(a, first.start), None]]
    for p, q in zip(idx, idx[1:]):
        if q != p + 1:                                   # a removed phrase: from after p to before q
            l0, l1 = after(p)
            r0, r1 = after(q - 1)
            ranges[-1][1] = l0 + min(GAP_KEEP / 2, (l1 - l0) / 2)
            ranges.append([r1 - min(GAP_KEEP / 2, (r1 - r0) / 2), None])
            continue
        g0, g1 = after(p)
        if g1 - g0 > GAP_CUT and g1 <= words[q].start + 0.1:
            ranges[-1][1] = g0 + GAP_KEEP / 2
            ranges.append([g1 - GAP_KEEP / 2, None])
    ranges[-1][1] = max(b, last.end)
    clipped = [(max(x, a), min(y, b)) for x, y in ranges]
    out = [(float(x), float(y)) for x, y in clipped if y > x + 0.05]
    if not out:
        raise RuntimeError("rien à garder après la retouche : le début et la fin se croisent")
    return out, missing


def snap_to_cuts(ranges: list[tuple[float, float]], cuts: list[float], words: list[Word]) -> list[tuple[float, float]]:
    """A range that starts (ends) a few frames before (after) a camera switch, in the pause around the words, starts
    (ends) on the switch instead: no 1-2 frame flash of the previous shot."""
    starts = [w.start for w in words]
    ends = [w.end for w in words]
    out = []
    for a, b in ranges:
        ws = min((s for s in starts if s >= a - 0.02), default=a)
        we = max((e for e in ends if e <= b + 0.02), default=b)
        for c in cuts:
            if a < c <= a + 0.3 and c <= ws + 0.03:
                a = c
            if b - 0.3 <= c < b and c >= we - 0.03:
                b = c
        if b > a + 0.05:
            out.append((a, b))
    return out


# ---------------------------------------------------------------- shots of the source edit
def scene_cuts(src: Path, a: float, b: float) -> list[float]:
    """Camera switches in the source between a and b (clip times)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-an",
                        "-vf", "scale=320:-2,scdet=threshold=12", "-f", "null", "-"], capture_output=True, text=True)
    return sorted(a + float(m) for m in re.findall(r"lavfi\.scd\.time:\s*([\d.]+)", r.stderr))


def sample_frames(src: Path, a: float, b: float, out_dir: Path, fps: float = 3.0) -> list[tuple[float, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob("s_*.jpg"):
        p.unlink()
    run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src, "-an",
         "-vf", f"fps={fps},scale=1280:-2", "-q:v", "4", out_dir / "s_%05d.jpg"])
    files = sorted(out_dir.glob("s_*.jpg"))
    return [(a + (int(p.stem[2:]) - 1) / fps + 0.5 / fps, p) for p in files]


def classify(img, faces) -> dict:
    """What the frame shows: one person (guest / marius), both (wide shot), or nobody we can use."""
    from .faces import MATCH, NOT_MATCH
    if img is None:
        return {"kind": "none"}
    H, W = img.shape[:2]
    fs = [f for f in faces.analyse(img) if f.score > 0.8 and f.box[3] / H > 0.05]
    fs.sort(key=lambda f: -f.box[3])
    if not fs:
        return {"kind": "none"}

    def info(f):
        x, y, w, h = f.box
        return {"cx": (x + w / 2) / W, "cy": (y + h / 2) / H, "fh": h / H, "sim": f.sim_marius}
    if len(fs) >= 2 and fs[0].box[3] / H <= 0.30:
        # a wide shot: Marius (best match) and the biggest other face, at comparable sizes
        mf = max(fs, key=lambda f: f.sim_marius)
        gf = [f for f in fs if f is not mf][0]
        if mf.sim_marius >= NOT_MATCH and min(mf.box[3], gf.box[3]) >= 0.4 * max(mf.box[3], gf.box[3]):
            return {"kind": "both", "marius": info(mf), "guest": info(gf)}
    f = info(fs[0])
    who = "marius" if f["sim"] >= MATCH else ("guest" if f["sim"] < NOT_MATCH else "unsure")
    return {"kind": who, "face": f}


def _median(items: list[dict], key: str) -> float:
    return float(np.median([i[key] for i in items]))


def shot_layouts(samples: list[tuple[float, dict]], cuts: list[float], a: float, b: float) -> list[dict]:
    """One layout per source shot: [{a, b, kind, ...face positions}]."""
    bounds = [a] + [c for c in cuts if a + 0.05 < c < b - 0.05] + [b]
    shots = []
    for s, e in zip(bounds, bounds[1:]):
        inside = [c for t, c in samples if s <= t < e] or [c for t, c in samples if abs(t - (s + e) / 2) < 0.7]
        kinds = [c["kind"] for c in inside if c["kind"] != "none"]
        if not kinds:
            shots.append({"a": s, "b": e, "kind": "center"})
            continue
        kind = max(set(kinds), key=kinds.count)
        if kind == "unsure":
            kind = "guest"
        if kind == "both":
            both = [c for c in inside if c["kind"] == "both"]
            shots.append({"a": s, "b": e, "kind": "split",
                          "guest": {k: _median([c["guest"] for c in both], k) for k in ("cx", "cy", "fh")},
                          "marius": {k: _median([c["marius"] for c in both], k) for k in ("cx", "cy", "fh")}})
        else:
            faces_ = [c["face"] for c in inside if c["kind"] in (kind, "unsure") and "face" in c] or \
                     [c["face"] for c in inside if "face" in c]
            shots.append({"a": s, "b": e, "kind": kind, **{k: _median(faces_, k) for k in ("cx", "cy", "fh")}})
    merged: list[dict] = []
    for sh in shots:   # a mis-detected flash (< 0.35 s) joins the previous shot: no flickering framing
        if merged and sh["b"] - sh["a"] < 0.35:
            merged[-1]["b"] = sh["b"]
        else:
            merged.append(sh)
    return merged


def pieces(ranges: list[tuple[float, float]], shots: list[dict], fps: float, limit: float) -> list[dict]:
    """The edit on the source's exact frame grid: each piece = whole frames of one range inside one shot.
    Inside one camera shot the framing alternates wide / tight at every cut, so the jump cuts read as intentional."""
    def F(t: float) -> int:
        return int(round(t * fps))
    last_frame = F(limit) - 2
    shot_starts = [F(s["a"]) for s in shots]

    def shot_at(frame: int) -> int:
        k = 0
        for i, s0 in enumerate(shot_starts):
            if frame >= s0:
                k = i
        return k
    out: list[dict] = []
    for ri, (ra, rb) in enumerate(ranges):
        fa, fb = F(ra), min(F(rb), last_frame)
        if fb - fa < 1:
            continue
        bounds = [fa] + [c for c in shot_starts[1:] if fa < c < fb] + [fb]
        for s, e in zip(bounds, bounds[1:]):
            k = shot_at(s)
            sh = shots[k]
            out.append({**{x: v for x, v in sh.items() if x not in ("a", "b")}, "f0": s, "frames": e - s,
                        "src": s / fps, "range": ri, "shot": k})
    zoom, last = "wide", None
    for p in out:
        if p["kind"] in ("guest", "marius", "unsure"):
            if last and last["shot"] == p["shot"] and last["range"] != p["range"]:
                zoom = "tight" if zoom == "wide" else "wide"
            elif not last or last["shot"] != p["shot"]:
                zoom = "wide"
            p["zoom"] = zoom
        last = p
    t_out = 0
    for p in out:
        p["out"] = t_out / fps
        t_out += p["frames"]
    return out


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def crop_box(W: int, H: int, cx: float, cy: float, w: float, h: float, head: float) -> tuple[int, int, int, int]:
    """A w×h box in the W×H frame, the face centre at (cx, `head` of the height)."""
    w, h = _even(min(w, W)), _even(min(h, H))
    x = int(np.clip(cx * W - w / 2, 0, W - w))
    y = int(np.clip(cy * H - head * h, 0, H - h))
    return w, h, x, y


def vfilter(p: dict, W: int, H: int) -> str:
    tail = "setsar=1,tpad=stop_mode=clone:stop_duration=2"
    if p["kind"] == "split":
        parts = []
        for who in ("guest", "marius"):
            f = p[who]
            h = float(np.clip(f["fh"] * H * 3.2, 0.30 * H, H))
            w = h * OUT_W / (OUT_H / 2)
            if w > W:
                w, h = W, W * (OUT_H / 2) / OUT_W
            parts.append(crop_box(W, H, f["cx"], f["cy"], w, h, 0.42))
        (w1, h1, x1, y1), (w2, h2, x2, y2) = parts
        return (f"split=2[g][m];[g]crop={w1}:{h1}:{x1}:{y1},scale={OUT_W}:{OUT_H // 2}:flags=lanczos[t];"
                f"[m]crop={w2}:{h2}:{x2}:{y2},scale={OUT_W}:{OUT_H // 2}:flags=lanczos[u];[t][u]vstack,{tail}")
    if p["kind"] == "center":
        w, h, x, y = crop_box(W, H, 0.5, 0.5, H * OUT_W / OUT_H, H, 0.5)
    else:
        tight = p.get("zoom") == "tight"
        h = H * (0.74 if tight else 1.0)
        w, h, x, y = crop_box(W, H, p["cx"], p["cy"], h * OUT_W / OUT_H, h, 0.36 if tight else 0.5)
    return f"crop={w}:{h}:{x}:{y},scale={OUT_W}:{OUT_H}:flags=lanczos,{tail}"


def render_video(src: Path, pcs: list[dict], info: dict, work: Path) -> Path:
    """Each piece seeks a quarter frame before its first frame, so the decoder starts exactly on it, and takes
    exactly `frames` frames at the source rate: no skipped, doubled or stray frame at any cut, at any frame rate."""
    work.mkdir(parents=True, exist_ok=True)
    listing = []
    for i, p in enumerate(pcs):
        out = work / f"p_{i:03d}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, p['src'] - 0.25 / info['fps']):.6f}", "-i", src,
             "-an", "-filter_complex", vfilter(p, info["w"], info["h"]),
             "-frames:v", str(p["frames"]), "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
             "-pix_fmt", "yuv420p", "-r", info["rate"], out])
        listing.append(f"file '{out.name}'")
    (work / "list.txt").write_text("\n".join(listing) + "\n")
    video = work / "video.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", video])
    return video


def _loudness(wav: Path) -> float:
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "loudnorm=print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = re.findall(r'"input_i"\s*:\s*"(-?[\d.]+|-inf)"', r.stderr)
    return float(m[-1]) if m and m[-1] != "-inf" else -70.0


def render_audio(src: Path, pcs: list[dict], fps: float, work: Path, offset: float = 0.0) -> Path:
    """The sound of each kept range in one piece (continuous across camera switches, short fades only at the edit
    cuts), then brought to −14 LUFS: gain + peak limiter, measured, corrected once."""
    ranges: list[list] = []                     # [start_s, frames] per range, in order
    for p in pcs:
        if ranges and ranges[-1][2] == p["range"]:
            ranges[-1][1] += p["frames"]
        else:
            ranges.append([p["src"], p["frames"], p["range"]])
    parts, labels = [], []
    for i, (s, n, _) in enumerate(ranges):
        dur = n / fps
        parts.append(f"[0:a]atrim=start={s + offset:.6f}:duration={dur:.6f},asetpts=PTS-STARTPTS,aresample=48000,"
                     f"afade=t=in:d=0.008,afade=t=out:st={max(0.0, dur - 0.008):.6f}:d=0.008[a{i}]")
        labels.append(f"[a{i}]")
    raw = work / "audio_raw.wav"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex",
         ";".join(parts) + f";{''.join(labels)}concat=n={len(ranges)}:v=0:a=1[out]", "-map", "[out]", "-ac", "2",
         "-c:a", "pcm_s16le", raw])
    level = work / "audio_level.wav"
    gain = min(20.0, TARGET_LUFS - _loudness(raw))
    for _ in range(2):
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", raw, "-af",
             f"volume={gain:.2f}dB,alimiter=limit=0.84:level=false:attack=3:release=60", "-c:a", "pcm_s16le", level])
        miss = TARGET_LUFS - _loudness(level)
        if abs(miss) <= 0.3:
            break
        gain = min(20.0, gain + miss)
    audio = work / "audio.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", level, "-c:a", "aac", "-b:a", "192k", audio])
    for f in (raw, level):
        f.unlink(missing_ok=True)
    return audio


def final_mux(video: Path, audio: Path, ass: Path, fonts_dir: Path, out: Path, duration: float,
              frames: int | None = None) -> Path:
    """Subtitles burned, H.264 1080×1920, every planned frame kept, under Telegram's 50 MB limit for bots."""
    vf = f"ass={ass.name}:fontsdir={fonts_dir}"
    cap = int(min(6000, max(1500, 44 * 8 * 1000 / max(duration, 1) - 250)))
    for _ in range(3):
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio, "-vf", vf,
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", f"{cap}k", "-bufsize", f"{2 * cap}k",
             "-pix_fmt", "yuv420p", "-c:a", "copy", *(["-frames:v", str(frames)] if frames else ["-shortest"]),
             "-t", f"{duration:.4f}", "-movflags", "+faststart", out], cwd=str(ass.parent))
        if out.stat().st_size <= TG_LIMIT:
            break
        cap = int(cap * 0.75)
    return out


def out_words(words: list[Word], pcs: list[dict], fps: float) -> list[Word]:
    """The clip's words on the timeline of the edited reel (words in removed parts disappear)."""
    res = []
    for w in words:
        for p in pcs:
            a, dur = p["src"], p["frames"] / fps
            mid = (w.start + w.end) / 2
            if a <= mid < a + dur:
                res.append(Word(w.text, p["out"] + max(0.0, w.start - a), p["out"] + min(dur, w.end - a)))
                break
    return res


def layout_at(pcs: list[dict], t: float) -> str:
    """The framing on screen at time t of the reel ('split' moves the subtitles to the seam)."""
    kind = pcs[0]["kind"] if pcs else "center"
    for p in pcs:
        if p["out"] <= t + 1e-6:
            kind = p["kind"]
    return kind


# ---------------------------------------------------------------- disk
def slim(work: Path, keep_final: bool = True) -> None:
    """After a reel is validated (keep the final file) or dropped (keep nothing): the 4K source goes."""
    for p in list(work.glob("clip*")) + [work / "audio.m4a"]:
        if p.exists():
            p.unlink()
    for d in ("pieces", "frames"):
        shutil.rmtree(work / d, ignore_errors=True)
    if not keep_final:
        shutil.rmtree(work, ignore_errors=True)


def cleanup(data_dir: Path, keep_days: int = 21) -> None:
    """Reels older than 3 weeks are deleted from the server (Loïc has the files on Telegram)."""
    limit = time.time() - keep_days * 86400
    for d in Path(data_dir).glob("episodes/*/reels/r*"):
        if d.is_dir() and d.stat().st_mtime < limit:
            shutil.rmtree(d, ignore_errors=True)

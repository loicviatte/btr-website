"""Reels cut from the latest episode (workflow: claude/btr-reels-workflow.md in the Claude project).

1. Claude proposes 10 moments from the transcript, Loïc ticks the ones he wants (6 a week).
2. For each: the bot downloads only that section in 4K, transcribes it word by word (Parakeet, on the server),
   finds the exact first/last words, trims long silences, follows the source edit shot by shot (guest close-up,
   Marius close-up, or the wide shot of both → split screen: guest on top, Marius below), renders 1080×1920 with
   frame-exact cuts, normalises the sound to −14 LUFS (no music) and burns the v3 subtitles.
3. Subtitles show only words the speaker really says (they come from the transcription of the same audio).
"""
import json
import re
import shutil
import subprocess
import time
import wave
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

YT = "https://www.youtube.com/watch?v={}"
OUT_W, OUT_H = 1080, 1920
PAD = 4.0                 # seconds downloaded before/after the moment, to find the exact words
MIN_LEN, MAX_LEN = 15.0, 75.0
GAP_CUT, GAP_KEEP = 0.40, 0.14   # silences longer than GAP_CUT are cut down to GAP_KEEP
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
def download_section(video_id: str, start: float, end: float, dest: Path, cookies: Path | None) -> Path:
    """Only the moment (plus a margin), best quality up to 4K. VP9/H.264 preferred over AV1 (much faster to decode)."""
    import yt_dlp
    from yt_dlp.utils import download_range_func
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bv*[height<=2160][vcodec^=vp09]+ba/bv*[height<=2160][vcodec^=avc1]+ba/bv*[height<=2160]+ba/b",
        "merge_output_format": "mp4", "outtmpl": str(dest.with_suffix(".%(ext)s")),
        "download_ranges": download_range_func(None, [(max(0.0, start - PAD), end + PAD)]),
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
    num, den = (int(x) for x in s["r_frame_rate"].split("/"))
    fps = num / den if den else 25.0
    if abs(fps - round(fps)) < 0.02:
        fps = float(round(fps))
    return {"w": int(s["width"]), "h": int(s["height"]), "fps": fps, "duration": float(j["format"]["duration"])}


# ---------------------------------------------------------------- speech → words
def extract_wav(src: Path, dest: Path) -> Path:
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", dest])
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
            # punctuation sticks to the previous word
            if words and (not new_word or re.fullmatch(r"[^\w']+", piece)):
                words[-1].text += piece
                words[-1].end = offset + end
            else:
                words.append(Word(piece, offset + t, offset + end))
        # TDT durations can be 0 at the end of a word: never let a word end after the next one starts
        for a, b in zip(words, words[1:]):
            a.end = min(max(a.end, a.start + 0.05), b.start)
        return words


# ---------------------------------------------------------------- the moment inside the clip
def _find(words: list[Word], phrase: str, lo: int = 0, hi: int | None = None) -> tuple[int, float]:
    """Index of the word where `phrase` best starts (fuzzy), and the score 0-100."""
    from rapidfuzz import fuzz
    target = [norm(w) for w in phrase.split() if norm(w)]
    if not target:
        return -1, 0.0
    hi = len(words) if hi is None else hi
    toks = [norm(w.text) for w in words]
    best, best_i = 0.0, -1
    n = len(target)
    for i in range(lo, max(lo, hi - 1) + 1):
        window = " ".join(toks[i:i + n])
        sc = fuzz.ratio(" ".join(target), window)
        if sc > best:
            best, best_i = sc, i
    return best_i, best


def locate(words: list[Word], first_words: str, last_words: str) -> tuple[int, int, float]:
    """(first word index, last word index, confidence) of the moment in the transcribed clip."""
    i0, s0 = _find(words, first_words)
    if i0 < 0:
        raise RuntimeError("début de l'extrait introuvable dans l'audio")
    n_last = len([w for w in last_words.split() if norm(w)])
    i1s, s1 = _find(words, last_words, i0)
    if i1s < 0:
        raise RuntimeError("fin de l'extrait introuvable dans l'audio")
    i1 = min(len(words) - 1, i1s + max(n_last, 1) - 1)
    return i0, i1, min(s0, s1)


def keep_ranges(words: list[Word], i0: int, i1: int, start_shift: float = 0.0, end_shift: float = 0.0,
                cut_phrases: list[str] = ()) -> list[tuple[float, float]]:
    """Time ranges of the clip to keep: from just before the first word to just after the last one, with long
    silences shortened and the asked phrases removed (cuts always fall between words)."""
    removed: set[int] = set()
    for ph in cut_phrases or ():
        j, sc = _find(words, ph, i0, i1 + 1)
        if j >= 0 and sc >= 85:
            removed.update(range(j, min(i1 + 1, j + len(ph.split()))))
    idx = [k for k in range(i0, i1 + 1) if k not in removed]
    if not idx:
        raise RuntimeError("rien à garder")
    prev_end = words[i0 - 1].end if i0 > 0 else 0.0
    nxt = words[i1 + 1].start if i1 + 1 < len(words) else words[i1].end + 0.6
    a = max(words[idx[0]].start - 0.10, (prev_end + words[idx[0]].start) / 2) + start_shift
    b = min(words[idx[-1]].end + 0.12, (words[idx[-1]].end + nxt) / 2) + end_shift
    ranges: list[list[float]] = [[max(0.0, a), None]]
    for p, q in zip(idx, idx[1:]):
        gap = words[q].start - words[p].end
        if q != p + 1 or gap > GAP_CUT:      # a removed phrase, or a long silence
            ranges[-1][1] = words[p].end + GAP_KEEP / 2
            ranges.append([words[q].start - GAP_KEEP / 2, None])
    ranges[-1][1] = b
    return [(float(x), float(y)) for x, y in ranges if y - x > 0.05]


# ---------------------------------------------------------------- shots of the source edit
def scene_cuts(src: Path, a: float, b: float) -> list[float]:
    """Camera switches in the source between a and b (absolute clip times)."""
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
        others = [f for f in fs if f is not mf]
        gf = others[0]
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
    # merge flashes (< 0.35 s) into the previous shot: a mis-detected cut must not flicker the framing
    merged: list[dict] = []
    for sh in shots:
        if merged and sh["b"] - sh["a"] < 0.35:
            merged[-1]["b"] = sh["b"]
        else:
            merged.append(sh)
    return merged


def pieces(ranges: list[tuple[float, float]], shots: list[dict], fps: float, limit: float | None = None) -> list[dict]:
    """The edit as a list of frame-exact pieces, each with its framing. Inside one camera shot the framing
    alternates wide / tight at every cut, so the jump cuts read as intentional. `limit` = clip length."""
    out: list[dict] = []
    if limit:
        ranges = [(a, min(b, limit - 2 / fps)) for a, b in ranges if a < limit - 2 / fps]
    for ri, (ra, rb) in enumerate(ranges):
        for sh in shots:
            a, b = max(ra, sh["a"]), min(rb, sh["b"])
            if b - a < 1 / fps:
                continue
            out.append({**{k: v for k, v in sh.items() if k not in ("a", "b")}, "a": a, "b": b, "range": ri,
                        "shot": shots.index(sh)})
    zoom, last = "wide", None
    for p in out:
        if p["kind"] in ("guest", "marius", "unsure"):
            if last and last["shot"] == p["shot"] and last["range"] != p["range"]:
                zoom = "tight" if zoom == "wide" else "wide"
            elif not last or last["shot"] != p["shot"]:
                zoom = "wide"
            p["zoom"] = zoom
        last = p
    # frame-exact durations (the video and the audio are cut with the same numbers)
    t_out = 0
    for p in out:
        p["src"] = round(p["a"] * fps) / fps
        p["frames"] = max(1, int((p["b"] - p["src"]) * fps + 1e-6))
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


def vfilter(p: dict, W: int, H: int, fps: float) -> str:
    tail = f"setsar=1,fps={fps:g},tpad=stop_mode=clone:stop_duration=2"
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
    work.mkdir(parents=True, exist_ok=True)
    listing = []
    for i, p in enumerate(pcs):
        out = work / f"p_{i:03d}.mp4"
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{p['src']:.4f}", "-i", src, "-an",
             "-filter_complex", vfilter(p, info["w"], info["h"], info["fps"]),
             "-frames:v", str(p["frames"]), "-c:v", "libx264", "-preset", "veryfast", "-crf", "15",
             "-pix_fmt", "yuv420p", "-r", f"{info['fps']:g}", out])
        listing.append(f"file '{out.name}'")
    (work / "list.txt").write_text("\n".join(listing) + "\n")
    video = work / "video.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", work / "list.txt", "-c", "copy", video])
    return video


def render_audio(src: Path, pcs: list[dict], fps: float, work: Path) -> Path:
    parts, labels = [], []
    for i, p in enumerate(pcs):
        dur = p["frames"] / fps
        parts.append(f"[0:a]atrim=start={p['src']:.4f}:duration={dur:.4f},asetpts=PTS-STARTPTS,"
                     f"afade=t=in:d=0.006,afade=t=out:st={max(0.0, dur - 0.006):.4f}:d=0.006[a{i}]")
        labels.append(f"[a{i}]")
    graph = ";".join(parts) + f";{''.join(labels)}concat=n={len(pcs)}:v=0:a=1,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[out]"
    audio = work / "audio.m4a"
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-filter_complex", graph, "-map", "[out]",
         "-c:a", "aac", "-b:a", "192k", audio])
    return audio


def final_mux(video: Path, audio: Path, ass: Path, fonts_dir: Path, out: Path, duration: float) -> Path:
    """Subtitles burned, H.264 1080×1920. The bitrate cap keeps the file under Telegram's 50 MB for bots."""
    vf = f"ass={ass.name}:fontsdir={fonts_dir}"
    cap = int(min(6000, max(2500, 44 * 8 * 1000 / max(duration, 1) - 250)))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", video, "-i", audio, "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-maxrate", f"{cap}k", "-bufsize", f"{2 * cap}k",
         "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", "-movflags", "+faststart", out], cwd=str(ass.parent))
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
    for p in list(work.glob("clip*")) + [work / "audio.m4a", work / "a.wav"]:
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

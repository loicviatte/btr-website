"""The heavy, blocking steps. The Telegram bot calls these in a worker thread."""
import json
import logging
import re
from pathlib import Path

from . import design, frames, render, srt
from .config import Settings
from .faces import Faces
from .llm import LLM
from .state import Episode, Reels
from .youtube import YouTube

log = logging.getLogger(__name__)


def _clean(s: str) -> str:
    return re.sub(r"^[\s“”\"']+|[\s“”\"']+$", "", s or "")


def clean_quote(a: dict) -> dict:
    return {"top": _clean(a.get("top")), "key": _clean(a.get("key")).upper(), "bottom": _clean(a.get("bottom"))}


def apply_all(words: list, fixes: list[dict]) -> tuple[list, list[str]]:
    """Each fix applied wherever it occurs (a name can come back several times in a reel)."""
    from . import reels as R
    missing = []
    for fx in fixes or ():
        a = "".join(R.norm(t) for t in str(fx.get("from", "")).split())
        b = "".join(R.norm(t) for t in str(fx.get("to", "")).split())
        for k in range(8 if a not in b else 1):              # « Mac » → « Danny Mac » must not loop
            words, miss = R.apply_fixes(words, [fx])
            if miss:
                if k == 0:
                    missing += miss
                break
    return words, missing


def cover_hook(c, said: str, fallback: bool = False) -> dict | None:
    """The cover words, only if they are words really said, consecutively (« They just / DON'T / CARE. »)."""
    def key(w):
        return re.sub(r"[^a-z0-9']", "", w.lower().replace("’", "'")).replace("'", "")
    spoken = [key(w) for w in (said or "").split()]
    spoken = [w for w in spoken if w]
    if c and isinstance(c, dict):
        parts = {k: re.sub(r"\s+", " ", str(c.get(k) or "")).strip() for k in ("small", "big", "gold")}
        words = [key(w) for k in ("small", "big", "gold") for w in parts[k].split()]
        words = [w for w in words if w]
        n = len(words)
        if 1 <= n <= 7 and any(spoken[i:i + n] == words for i in range(len(spoken) - n + 1)):
            parts["big"], parts["gold"] = parts["big"].upper(), parts["gold"].upper()
            return parts
    if fallback and spoken:
        raw = [w for w in (said or "").split() if key(w)][:4]
        return {"small": " ".join(raw[:-2]), "big": raw[-2].upper() if len(raw) > 1 else "", "gold": raw[-1].upper()}
    return None


def mmss(t) -> float:
    if isinstance(t, (int, float)):
        return float(t)
    parts = [int(p) for p in re.findall(r"\d+", str(t or "0"))] or [0]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return float(sec)


def part_number(ep) -> str | None:
    """'PART 2' badge for multi-part episodes: set by Loïc (ep["part"], "" = none) or read from the titles."""
    import re
    if ep.get("part") is not None:
        return str(ep["part"]) or None
    for t in ((ep.get("final") or {}).get("title", ""), ep.get("title", "")):
        m = re.search(r"\bpart(?:ie)?\s*_?(\d)\b", t or "", re.I)
        if m:
            return m.group(1)
    return None


def render_thumbs(ep: Episode, models_dir: Path, only: str | None = None, skip=()) -> dict[str, Path]:
    """Render the 3 thumbnails from the picked frames, or just one ("youtube" | "instagram" | "square").
    Designs in `skip` (validated by Loïc) are left untouched."""
    g, m = ep["pick_guest"], ep["pick_marius"]
    q = clean_quote(ep["final"])
    name = ep.get("guest_name", "")
    work = ep.dir / "render"
    root = ep.dir.parent.parent                    # data dir: layout settings are read now, at every render
    part = part_number(ep)

    def lay(fmt):
        d = design.load(root, fmt)
        d["part"] = part
        return d
    want = [d for d in ("youtube", "square", "instagram") if only in (None, d) and d not in skip]
    out: dict[str, Path] = {}
    # the square reuses the frames/cut-outs made by the YouTube render
    if "youtube" in want or ("square" in want and not (work / "yt_marius_cut.png").exists()):
        yt = render.youtube(work, Path(g["hires"]), g["cx"], Path(m["hires"]), m["cx"], q, name, lay("youtube"))
        if "youtube" in want:
            out["youtube"] = yt
    if "square" in want:
        out["square"] = render.square(work, g["cx"], m["cx"], q, name, lay("square"))
    if "instagram" in want:
        out["instagram"] = render.instagram(work, models_dir, Path(g["hires"]), g, q, name, lay("instagram"))
    return out


class DryRun(Exception):
    """Raised instead of writing to a video that is already public."""


class Pipeline:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.yt = YouTube(cfg.youtube_token, cfg.channel_id, cfg.youtube_client)
        self.llm = LLM(cfg.anthropic_key, cfg.model, cfg.data_dir)
        self._faces = None

    @property
    def faces(self) -> Faces:
        if self._faces is None:
            self._faces = Faces(self.cfg.models_dir)
        return self._faces

    # ---- 1. transcript + axes ------------------------------------------
    def fetch_transcript(self, ep: Episode) -> bool:
        text, kind = self.yt.caption_srt(ep.video_id)
        if not text:
            return False
        ep.file("captions_youtube.srt").write_text(text)
        ep["transcript_kind"] = kind
        return True

    def cues(self, ep: Episode) -> list[srt.Cue]:
        for name in ("captions_davinci.srt", "captions_youtube.srt"):
            p = ep.file(name)
            if p.exists():
                cues, _ = srt.normalise_offset(srt.parse(p.read_text()))
                if cues:
                    return cues
        return []

    def propose_axes(self, ep: Episode) -> dict:
        refs = self.yt.public_references(12)
        ep["refs"] = refs[:4]
        timed = srt.timed_text(self.cues(ep), 30)
        res = self.llm.propose_axes(ep["title"], ep.get("guest_name") or ep["title"], [r["title"] for r in refs], timed)
        ep["guest_name"] = res.get("guest_name") or ep.get("guest_name")
        ep["axes"] = self._verify(ep, res.get("axes", []))
        return res

    def _verify(self, ep: Episode, axes: list[dict]) -> list[dict]:
        """Keep only quotes really said, and pin their timestamp from the captions."""
        cues = self.cues(ep)
        out = []
        for a in axes:
            t = srt.find_quote(cues, a.get("quote", ""))
            a["verified"] = t is not None
            if t is not None:
                a["timestamp"] = srt.fmt(t)
            out.append(a)
        return out

    def refine(self, ep: Episode, message: str) -> dict:
        timed = srt.timed_text(self.cues(ep), 30)
        history = ep.get("chat") or []
        res = self.llm.refine(ep["title"], ep.get("guest_name", ""), ep.get("axes", []), timed, message, history)
        ep["chat"] = (history + [{"who": "Loïc", "text": message},
                                 {"who": "Bot", "text": str(res.get("reply") or "")[:1500]}])[-40:]
        if res.get("axes"):
            ep["axes"] = self._verify(ep, res["axes"])
        if res.get("final"):
            ep["final"] = self._verify(ep, [res["final"]])[0]
            if res["final"].get("guest_name"):
                ep["guest_name"] = res["final"]["guest_name"]
        return res

    # ---- 2. frames --------------------------------------------------------
    def scan(self, ep: Episode) -> list[dict]:
        video = frames.download_scan_copy(ep.video_id, ep.file("scan.mp4"), self.cfg.ytdlp_cookies)
        fr = frames.sample(video, ep.dir / "frames", 2.0)
        cache, marker = ep.file("scan.json"), ep.file("scan.v2")
        had_cache = cache.exists()
        cands = frames.scan(fr, self.faces, cache)
        if had_cache and not marker.exists():
            # scans made before the timestamp fix are 1 s early: shift them (and what was already shown)
            for c in cands:
                c["t"] += 1.0
            cache.write_text(json.dumps(cands))
            for who in ("guest", "marius"):
                if ep.get(f"shown_{who}"):
                    ep[f"shown_{who}"] = [t + 1.0 for t in ep[f"shown_{who}"]]
            ep.save()
        marker.touch()
        return cands

    def propose_frames(self, ep: Episode, who: str, exclude=()) -> list[dict]:
        cands = self.scan(ep)
        near = mmss(ep["final"].get("timestamp")) if who == "guest" and ep.get("final") else None
        sl = frames.shortlist(cands, who, 24, near, exclude)
        if not sl:
            return []
        try:  # keep only clearly open eyes (checked on face close-ups, 12 at a time: the contact sheet is too small)
            kept = []
            for j in range(0, len(sl), 12):
                chunk = sl[j:j + 12]
                ok = set(self.llm.open_eyes(frames.face_sheet(chunk, ep.file(f"eyes_{who}.jpg"))))
                kept += [c for i, c in enumerate(chunk, 1) if i in ok]
            sl = kept
        except Exception:
            pass
        if not sl:
            return []
        sheet = frames.contact_sheet(sl, ep.file(f"sheet_{who}.jpg"))
        label = ep.get("guest_name", "the guest") if who == "guest" else f"{self.cfg.host_name} (the host)"
        try:
            pick = self.llm.pick_frames(sheet, label, ep["final"]["quote"], 4)
            order = [i - 1 for i in pick.get("best", []) if 1 <= i <= len(sl)]
        except Exception:
            order = []
        order += [i for i in range(len(sl)) if i not in order]
        chosen = [sl[i] for i in order[:4]]
        # 4K versions of the proposals
        url = None
        for i, c in enumerate(chosen):
            out = ep.file(f"{who}_{int(c['t'])}.jpg")
            if not out.exists():
                try:
                    url = url or frames.full_res_url(ep.video_id, self.cfg.ytdlp_cookies)
                    frames.grab(url, c["t"], out)
                except Exception:
                    frames.grab(str(ep.file("scan.mp4")), c["t"], out)  # fallback: 720p copy
            c["hires"] = str(out)
        return chosen

    # ---- 3. thumbnails ------------------------------------------------------
    def thumbnails(self, ep: Episode, only: str | None = None) -> dict[str, Path]:
        # a design asked for by name is re-opened; "all" never touches the validated ones
        return render_thumbs(ep, self.cfg.models_dir, only, () if only else tuple(ep.get("validated") or ()))

    def description(self, ep: Episode) -> str:
        refs = ep.get("refs") or self.yt.public_references(4)
        text = srt.plain_text(self.cues(ep))
        return self.llm.description(ep["final"]["title"], ep.get("guest_name", ""), refs, text)

    def badge_thumbnail(self, vid: str, part: str) -> Path:
        """Current YouTube thumbnail of a video (the bot's own 1920 render if it made it) + the PART badge."""
        import urllib.request
        ep = Episode(self.cfg.data_dir, vid)
        work = ep.dir / "badge"
        work.mkdir(parents=True, exist_ok=True)
        local = ep.dir / "render" / "thumb_youtube.png"
        if local.exists():
            bg = local
        else:
            th = self.yt.video(vid)["snippet"]["thumbnails"]
            url = (th.get("maxres") or th.get("standard") or th.get("high"))["url"]
            bg = work / "current.jpg"
            urllib.request.urlretrieve(url, bg)
        return render.badge(work, bg, str(part))

    def _guard(self, ep: Episode) -> None:
        """Never touch a video that is already public: /episode on a live episode is a dry run."""
        status = self.yt.video(ep.video_id)["status"].get("privacyStatus")
        if status == "public":
            raise DryRun("Cette vidéo est déjà publique, donc c'était un test : je n'ai rien modifié sur YouTube. "
                               "Les miniatures sont dans le chat, et sur une vidéo non répertoriée je publie pour de vrai.")

    def publish(self, ep: Episode) -> None:
        self._guard(ep)
        desc = ep["description"].replace("{CHAPTERS}", "").replace("{{CHAPTERS}}", "")
        desc = re.sub(r"\n{3,}", "\n\n", desc).strip()
        self.yt.update_metadata(ep.video_id, ep["final"]["title"], desc)
        self.yt.set_thumbnail(ep.video_id, ep.dir / "render" / "thumb_youtube.jpg")

    # ---- 4. chapters --------------------------------------------------------
    def chapters(self, ep: Episode) -> list[list[str]]:
        if ep.get("chapters_in_description") and ep.get("chapters"):   # already written into the description
            return ep["chapters"]
        ch = self.llm.chapters(srt.timed_text(self.cues(ep), 20))
        if not ch or ch[0][0] not in ("00:00", "0:00"):
            ch = [["00:00", "Intro"]] + (ch or [])
        return ch

    def retime_chapters(self, ep: Episode) -> list[list[str]]:
        """Same chapters and titles, start times re-read from the SRT (snapped to real subtitle starts)."""
        cues = self.cues(ep)
        old = ep.get("chapters") or []
        if not old:
            raise RuntimeError("Pas encore de chapitres à recaler.")
        new = self.llm.retime_chapters(srt.timed_text(cues, 6), old)
        starts = sorted(c.start for c in cues)
        out, last = [], -1.0
        for t, title in new:
            sec = mmss(t)
            snapped = min(starts, key=lambda x: abs(x - sec)) if starts and abs(min(starts, key=lambda x: abs(x - sec)) - sec) <= 4 else sec
            if snapped <= last:
                snapped = last + 10
            out.append([srt.fmt(0 if not out else snapped), title])
            last = 0 if not out else snapped
        # keep the description in sync with the chapters
        block_old = "\n".join(f"{t} {title}" for t, title in old)
        block_new = "\n".join(f"{t} {title}" for t, title in out)
        if ep.get("description") and block_old in ep["description"]:
            ep["description"] = ep["description"].replace(block_old, block_new)
        ep["chapters"] = out
        ep.save()
        return out

    def description_with_chapters(self, ep: Episode) -> str:
        """Put the chapters (timecodes) into the description now, before publishing."""
        ep["chapters_in_description"] = False
        ch = self.chapters(ep)
        block = "\n".join(f"{t} {title}" for t, title in ch)
        base = ep["description"]
        if "{CHAPTERS}" in base or "{{CHAPTERS}}" in base:
            base = base.replace("{{CHAPTERS}}", block).replace("{CHAPTERS}", block)
        elif block not in base:
            base = base.rstrip() + "\n\n" + block
        ep["chapters"], ep["description"], ep["chapters_in_description"] = ch, base, True
        ep.save()
        return base

    def publish_chapters(self, ep: Episode, chapters: list[list[str]]) -> str:
        self._guard(ep)
        block = "\n".join(f"{t} {title}" for t, title in chapters)
        cur = self.yt.video(ep.video_id)["snippet"].get("description", "")
        base = ep.get("description") or cur
        if block in base:   # timecodes were already added before publishing
            desc = base
        elif "{CHAPTERS}" in base or "{{CHAPTERS}}" in base:
            desc = base.replace("{{CHAPTERS}}", block).replace("{CHAPTERS}", block)
        else:
            desc = cur.rstrip() + "\n\n" + block
        self.yt.update_metadata(ep.video_id, None, desc)
        return desc

    # ---- 5. reels (claude/btr-reels-workflow.md) ---------------------------------
    _asr = None

    def asr(self):
        from .reels import Transcriber
        if self._asr is None:
            self._asr = Transcriber(self.cfg.models_dir)
        return self._asr

    def asr_release(self) -> None:
        """The speech model takes ~1 GB of RAM: freed as soon as a clip is transcribed (the words are cached)."""
        self._asr = None

    def reel_episode(self, vid: str | None, active: Episode | None) -> Episode:
        """The episode to cut reels from: the one asked for, else the episode in progress if it has a transcript,
        else the latest public episode of the channel."""
        if not vid and active is not None and self.cues(active):
            return active
        if not vid:
            refs = self.yt.public_references(1)
            if not refs:
                raise RuntimeError("aucun épisode public trouvé sur la chaîne")
            vid = refs[0]["id"]
        ep = Episode(self.cfg.data_dir, vid)
        ep["public_title"] = self.yt.video(vid)["snippet"]["title"]   # the published title, not the upload name
        if not ep.get("title"):
            ep["title"] = ep["public_title"]
        self._attach_srt(ep)
        if not self.cues(ep) and not self.fetch_transcript(ep):
            raise RuntimeError("pas encore de transcript pour cette vidéo (ni SRT DaVinci, ni sous-titres YouTube)")
        ep.save()
        return ep

    def _attach_srt(self, ep: Episode) -> None:
        """Loïc's DaVinci SRT for this video, if it is still waiting in data/pending_srt (copied, not moved)."""
        import shutil

        from . import drive
        if ep.file("captions_davinci.srt").exists():
            return
        pending = sorted((self.cfg.data_dir / "pending_srt").glob("*.srt"), key=lambda p: -p.stat().st_mtime)
        for title in (ep.get("public_title"), ep.get("title")):
            hit = next((p for p in pending if title and drive.matches(p.name, title)), None)
            if hit:
                shutil.copy(hit, ep.file("captions_davinci.srt"))
                return

    @staticmethod
    def reel_title(ep: Episode) -> str:
        return ep.get("public_title") or (ep.get("final") or {}).get("title") or ep.get("title", "")

    def reel_candidates(self, ep: Episode, n: int = 10) -> dict:
        """10 moments proposed by Claude, checked against the transcript. Returns the new reels list (not saved)."""
        import shutil
        import time

        from . import reels as R
        cues = self.cues(ep)
        final = ep.get("final") or {}
        avoid = f"\"{final.get('quote')}\" at {final.get('timestamp')}" if final.get("quote") else ""
        raw = self.llm.reel_candidates(self.reel_title(ep), ep.get("guest_name", ""), avoid, srt.timed_text(cues, 15), n)
        out = []
        for c in raw:
            a, b = mmss(c.get("start")), mmss(c.get("end"))
            if b <= a or not c.get("first_words") or not c.get("last_words"):
                continue
            t = srt.find_quote(cues, c["first_words"])
            if t is not None and abs(t - a) <= 8:     # the transcript knows better than the model where it starts
                b, a = b + (t - a), t
            e = srt.find_quote_end(cues, c["last_words"], a)
            if e is not None and a + 8 < e <= a + R.MAX_LEN:   # …and where it ends
                b = e
            c.update(start_s=a, end_s=min(max(b, a + R.MIN_LEN), a + R.MAX_LEN), verified=t is not None)
            out.append(c)
        out.sort(key=lambda c: c["start_s"])
        for i, c in enumerate(out, 1):
            c["n"] = i
        R.cleanup(self.cfg.data_dir)
        shutil.rmtree(ep.dir / "reels", ignore_errors=True)       # a new list replaces the previous one
        return {"id": int(time.time()) % 1_000_000, "cands": out, "sel": [], "items": {}}

    def render_reel(self, ep: Episode, cand: dict, shift: list, cuts: list, fixes: list | None = None,
                    note: str = "") -> dict:
        """Cut, frame, subtitle and render one moment. Pure: returns the reel's new fields, the caller stores them."""
        from . import reels as R
        try:
            return self._render_reel(ep, cand, shift, cuts, fixes, note, widen=0.0)
        except R.NotInClip:            # the moment runs past the section downloaded: once more, with a wider one
            return self._render_reel(ep, cand, shift, cuts, fixes, note, widen=20.0)

    def _render_reel(self, ep: Episode, cand: dict, shift: list, cuts: list, fixes, note: str, widen: float) -> dict:
        import cv2

        from . import reels as R
        n = cand["n"]
        work = ep.dir / "reels" / f"r{n:02d}"
        work.mkdir(parents=True, exist_ok=True)
        s0, s1 = float(shift[0]), float(shift[1])
        cues_all = self.cues(ep)
        start_s, end_s = cand["start_s"], cand["end_s"]
        e = srt.find_quote_end(cues_all, cand.get("last_words", ""), start_s) if cues_all else None
        if e is not None and start_s + 8 < e <= start_s + R.MAX_LEN:
            end_s = max(end_s, e)       # lists made before the end was looked up in the transcript
        # the 6 s margin covers most adjustments; beyond it, the section downloaded grows
        a0 = start_s - widen + min(0.0, s0 + R.PAD - 1)
        b0 = end_s + widen + max(0.0, s1 - R.PAD + 1)
        dl_a, dl_b = R.section_bounds(a0, b0)
        tag = f"{dl_a}_{dl_b}"
        for old in list(work.glob("clip_*.mp4")) + list(work.glob("words_*.json")):
            if tag not in old.name:
                old.unlink()
        clip = R.download_section(ep.video_id, dl_a, dl_b, work / f"clip_{tag}.mp4", self.cfg.ytdlp_cookies)
        info = R.probe(clip)
        off = R.audio_offset(dl_a, info["fps"])
        wav = work / f"clip_{tag}.wav"
        if not wav.exists():
            R.extract_wav(clip, wav, off)
        wj = work / f"words_{tag}.json"
        if wj.exists():
            words = [R.Word(**w) for w in json.loads(wj.read_text())]
        else:
            try:
                words = self.asr().words(wav)
            finally:
                self.asr_release()
            wj.write_text(json.dumps([w.__dict__ for w in words]))
        # Loïc's DaVinci SRT and the speech model are compared; where they differ, Claude picks one of the two
        diffs, picks = [], {}
        if ep.file("captions_davinci.srt").exists():
            words, diffs = R.compare_with_srt(words, cues_all, dl_a + off)
            if diffs:
                try:
                    picks = self.llm.reel_arbitrate(ep.get("guest_name", ""), self.reel_title(ep), diffs)
                except Exception:  # noqa: BLE001
                    picks = {}
                words = R.apply_choices(words, diffs, picks)
        i0, i1, conf = R.locate(words, cand.get("first_words", ""), cand.get("last_words", ""))
        i1 = R.finish_sentence(words, i1)
        energy = R.Energy(wav)
        ranges, missing = R.keep_ranges(words, i0, i1, energy, s0, s1, cuts)
        a, b = ranges[0][0], ranges[-1][1]
        scene = R.scene_cuts(clip, max(0.0, a - 0.5), b + 0.5)
        ranges = R.snap_to_cuts(ranges, scene, words)
        if not ranges:
            raise RuntimeError("rien à garder après la retouche")
        a, b = ranges[0][0], ranges[-1][1]
        fr = R.sample_frames(clip, a, b, work / "frames")
        samples = [(t, R.classify(cv2.imread(str(p)), self.faces)) for t, p in fr]
        shots = R.shot_layouts(samples, scene, a, b)
        try:
            R.cover_search(clip, samples, dict(fr), work / "cover")         # sharp 4K stills for the reel cover
        except Exception:  # noqa: BLE001
            log.exception("reel cover stills")
        pcs = R.pieces(ranges, shots, info["fps"], info["duration"])
        if not pcs:
            raise RuntimeError("extrait vide après le montage")
        video = R.render_video(clip, pcs, info, work / "pieces")
        video.replace(work / "base.mp4")                         # the picture without subtitles, kept for subtitle fixes
        R.render_audio(clip, pcs, info["fps"], work, off)
        import shutil
        shutil.rmtree(work / "pieces", ignore_errors=True)
        doubts = [f"« {d['audio'] or '—'} » (audio) / « {d['srt']} » (SRT) → {d['srt'] if picks.get(k) == 'srt' else d['audio'] or '—'}"
                  for k, d in enumerate(diffs) if a - 0.2 <= d["t"] <= b + 0.2]
        alts = [{"audio": d["audio"], "srt": d["srt"]} for d in diffs if a - 0.2 <= d["t"] <= b + 0.2]
        edit = {"framing": R.FRAMING, "fps": info["fps"], "frames": sum(p["frames"] for p in pcs), "doubts": doubts, "alts": alts,
                "confidence": round(conf),
                "missing_cuts": missing, "words": [w.__dict__ for w in R.out_words(words, pcs, info["fps"])],
                "layout": [{"out": p["out"], "frames": p["frames"], "kind": p["kind"]} for p in pcs]}
        (work / "edit.json").write_text(json.dumps(edit))
        kinds = [p["kind"] for p in pcs]
        return {**self.reel_subtitles(ep, cand, fixes or [], note), "status": "preview", "confidence": round(conf),
                "shots": {k: kinds.count(k) for k in set(kinds)}, "missing_cuts": missing, "doubts": doubts}

    def reel_subtitles(self, ep: Episode, cand: dict, fixes: list, note: str = "") -> dict:
        """Subtitles + final file from the kept edit (base picture + sound): a few seconds, no new cut.
        Loïc's word fixes are applied here; `note` = his remark on the layout, passed to the layout model."""
        from . import reels as R
        from . import subs
        from .config import ASSETS
        n = cand["n"]
        work = ep.dir / "reels" / f"r{n:02d}"
        if not self.reel_edit_kept(ep, n):
            raise RuntimeError("le montage de ce reel n'est plus sur le serveur : il faut le refaire en entier")
        edit = json.loads((work / "edit.json").read_text())
        words = [R.Word(**w) for w in edit["words"]]
        if "names" not in edit:                                   # proper nouns checked once per edit (context + web)
            names = self.reel_names(ep, words)
            if names is not None:                                 # a failed check is tried again next time
                edit["names"] = names
                (work / "edit.json").write_text(json.dumps(edit))
        words, _ = apply_all(words, edit.get("names") or [])
        ow, not_found = R.apply_fixes(words, fixes)               # Loïc's own fixes come last: his version wins
        total = edit["frames"] / edit["fps"]
        stats: dict = {}
        try:
            blocks = subs.parse_blocks(self.llm.reel_blocks([w.text for w in ow], note), ow, stats=stats)
        except Exception:  # noqa: BLE001
            blocks = []
        if not blocks or stats.get("reinserted", 0) > 0.15 * len(ow):   # the model's layout misses too much
            blocks = subs.auto_blocks(ow)
        # ≤ 4 lines a page, no expression cut in two, no sentence tail on the next sentence's page
        blocks = subs.cap_lines(subs.merge_flashes(subs.sentence_seams(subs.keep_phrases(blocks))))
        blocks = subs.keep_together(blocks, cand.get("together") or [])   # Loïc's « laisse X ensemble », always last
        subs.vary(blocks)                                         # not always centred, not always at the same height
        subs.timeline(blocks, total, lambda t: R.layout_at(edit["layout"], t))
        vis = subs.visibility(blocks)                             # every word readable ≥ 0.5 s: checked on each reel
        if vis["short"]:
            log.warning("reel %s: words shown too briefly %s", n, vis["short"])
        fonts = subs.prepare_fonts(ASSETS, self.cfg.data_dir / "fonts")
        ass = subs.write_ass(blocks, fonts, work / "subs.ass")
        slug = re.sub(r"[^a-z0-9]+", "-", (ep.get("guest_name") or "btr").lower()).strip("-")
        out = R.final_mux(work / "base.mp4", work / "audio.m4a", ass, fonts, work / f"BTR_reel_{n:02d}_{slug}.mp4",
                          total, edit["frames"])
        return {"file": str(out), "duration": round(total, 1), "said": " ".join(w.text for w in ow)[:1500],
                "shown": len(subs.shown_words(blocks)), "spoken": len(ow), "fixes_not_found": not_found,
                "on_screen": [" / ".join(" ".join(t.text for t in line) for line in b.lines) for b in blocks][:40],
                "names": [f"{x['from']} → {x['to']}" for x in edit.get("names") or []], "visibility": vis,
                "size_mb": round(out.stat().st_size / 2 ** 20, 1)}

    def reel_names(self, ep: Episode, words: list) -> list[dict] | None:
        """Spelling of the names said in the reel, checked by Claude against the episode's own texts (title, YouTube
        description, chapters) and the web. A fix is kept only for a name that sounds like what was heard."""
        from rapidfuzz import fuzz

        from . import reels as R
        text = " ".join(w.text for w in words)
        if not ep.get("names_context"):
            parts = [self.reel_title(ep), ep.get("title", "")]
            try:
                parts.append(self.yt.video(ep.video_id)["snippet"].get("description", ""))
            except Exception:  # noqa: BLE001
                pass
            for c in ep.get("chapters") or (ep.get("final") or {}).get("chapters") or []:
                parts.append(" ".join(map(str, c)) if isinstance(c, (list, tuple)) else str(c))
            ep["names_context"] = "\n".join(p for p in parts if p)[:8000]
            ep.save()
        try:
            res = self.llm.reel_names(ep.get("guest_name", ""), self.reel_title(ep), text, ep["names_context"])
        except Exception:  # noqa: BLE001
            log.exception("reel names")
            return None
        heard = {R.norm(w.text) for w in words}
        keep = []
        for f in res.get("fixes") or []:
            src, dst = str(f.get("from", "")).strip(), str(f.get("to", "")).strip()
            a, b = "".join(R.norm(t) for t in src.split()), "".join(R.norm(t) for t in dst.split())
            if not a or not b or a == b or not any(R.norm(t) in heard for t in src.split()):
                continue
            if len(b) > 1.5 * len(a) + 2 or len(a) > 1.5 * len(b) + 2 or fuzz.ratio(a, b) < 50:
                continue                                           # not the same spoken name (or words added): refused
            keep.append({"from": src, "to": dst, "source": str(f.get("source", ""))[:200]})
        return keep

    def reel_edit_kept(self, ep: Episode, n: int) -> bool:
        """The edit of reel n (picture, sound, word timings) is still here: subtitles alone can be redone."""
        from . import reels as R
        work = ep.dir / "reels" / f"r{n:02d}"
        if not all((work / f).exists() for f in ("edit.json", "base.mp4", "audio.m4a")):
            return False
        try:
            return json.loads((work / "edit.json").read_text()).get("framing", 1) == R.FRAMING
        except Exception:  # noqa: BLE001
            return False

    def reel_feedback(self, ep: Episode, n: int, item: dict, feedback: str) -> dict:
        """What Loïc's remark about the subtitles means: word fixes and/or a layout note (Claude reads the reel).
        A fix is kept only if its new words come from Loïc's own message or from one of the two versions heard
        there (his SRT or the speech model): the model may never put words in the guest's mouth."""
        from . import reels as R
        res = self.llm.reel_sub_feedback(str(item.get("said", "")).split(), item.get("on_screen") or [], feedback)
        edit_p = ep.dir / "reels" / f"r{n:02d}" / "edit.json"
        alts = json.loads(edit_p.read_text()).get("alts", []) if edit_p.exists() else []
        heard = {R.norm(t) for a in alts for t in (a["audio"] + " " + a["srt"]).split()}
        said_by_him = {R.norm(t) for t in feedback.split()}
        kept, refused = [], []
        for f in res.get("fixes") or []:
            new_words = {R.norm(t) for t in str(f.get("to", "")).split()} - {""}
            if new_words and new_words <= (said_by_him | heard):
                kept.append(f)
            else:
                refused.append(f)
        res["fixes"] = kept
        if refused:
            asks = " ; ".join(f"« {f.get('from')} »" for f in refused)
            res["reply"] = (str(res.get("reply", "")) + f" Pour {asks}, je n'ai pas de version sûre de ce qui est dit : "
                            "écris-moi les mots exacts et je corrige.").strip()
        return res

    def reel_captions(self, ep: Episode, said: str) -> dict:
        """Instagram without hashtags (enforced), TikTok / Shorts with some."""
        try:
            c = self.llm.reel_captions(ep.get("guest_name", ""), self.reel_title(ep), said)
        except Exception:  # noqa: BLE001
            return {}
        ig = re.sub(r"[ \t]*#[\w-]+", "", c.get("instagram") or "").strip()
        tt = (c.get("tiktok") or ig).strip()
        if "#" not in tt:
            tt += "\n\n#dancesport #ballroom #latindance #breaktheroutine"
        out = {"instagram": ig, "tiktok": tt}
        cover = cover_hook(c.get("cover"), said)
        if cover:
            out["cover"] = cover
        return out

    def reel_cover(self, ep: Episode, n: int, item: dict, text: dict | None = None, pick: int | None = None) -> dict:
        """The cover of reel n: the best 4K still of the guest (eyes open, lively; the model looks at the faces),
        the hook in the validated template. `text` / `pick` = Loïc's choice (other words, other photo number)."""
        work = ep.dir / "reels" / f"r{n:02d}"
        cdir = work / "cover"
        cands = json.loads((cdir / "cands.json").read_text()) if (cdir / "cands.json").exists() else []
        cands = [c for c in cands if (cdir / c["file"]).exists()]
        if not cands and (work / "base.mp4").exists():          # reels made before the stills were kept
            cands = self._cover_from_edit(work, cdir)
        if not cands:
            raise RuntimeError("pas d'image du guest pour la cover")
        order = list(range(len(cands)))
        if pick is not None and 1 <= pick <= len(cands):
            order = [pick - 1]
        elif len(cands) > 1:
            try:
                from .config import ASSETS
                sheet = render.cover_sheet([cdir / c["file"] for c in cands], cands, cdir / "sheet.jpg")
                best = [i - 1 for i in self.llm.reel_cover_pick(sheet, ASSETS / "cover_ref.jpg") if 1 <= i <= len(cands)]
                order = best + [i for i in order if i not in best]
            except Exception:  # noqa: BLE001
                log.exception("cover pick")
        c = cands[order[0]]
        hook = cover_hook(text, item.get("said", "")) if text else None
        hook = hook or (item.get("captions") or {}).get("cover")
        if not hook:                                   # captions written before the cover existed: ask for the hook
            hook = self.reel_captions(ep, item.get("said", "")).get("cover")
        hook = hook or cover_hook(None, item.get("said", ""), fallback=True)
        slug = re.sub(r"[^a-z0-9]+", "-", (ep.get("guest_name") or "btr").lower()).strip("-")
        out = render.reel_cover(cdir, cdir / c["file"], c, hook, ep.get("guest_name") or "",
                                work / f"BTR_reel_{n:02d}_{slug}_cover.jpg")
        return {"cover": str(out), "cover_text": hook, "cover_pick": order[0] + 1, "cover_count": len(cands)}

    def reel_cover_search(self, ep: Episode, n: int) -> int:
        """More and better cover stills for reel n (the 4K section of the moment downloaded again, sampled every
        0.33 s, sharp guest faces kept), then the cover is chosen again from them. Returns the number of stills."""
        import shutil

        import cv2

        from . import reels as R
        work = ep.dir / "reels" / f"r{n:02d}"
        tags = sorted(work.glob("words_*.json"))
        if not tags:
            raise RuntimeError("le moment de ce reel n'est plus sur le serveur")
        a, b = (int(float(x)) for x in tags[-1].stem.split("_")[1:3])
        clip = R.download_section(ep.video_id, a, b, work / f"clipcover_{a}_{b}.mp4", self.cfg.ytdlp_cookies)
        try:
            info = R.probe(clip)
            frames = dict(R.sample_frames(clip, 0.0, info["duration"], work / "frames_cover", fps=3.0))
            samples = [(t, R.classify(cv2.imread(str(p)), self.faces)) for t, p in frames.items()]
            cands = R.cover_search(clip, samples, frames, work / "cover")
        finally:
            clip.unlink(missing_ok=True)
            shutil.rmtree(work / "frames_cover", ignore_errors=True)
        if not cands:
            raise RuntimeError("aucune image nette du guest seul dans ce moment")
        return len(cands)

    def reel_ig_slots(self, ep: Episode, taken: set[str]) -> list[str] | None:
        """The days (« ven. 31.10 ») of this episode's Instagram reel slots still free in ClickUp (None: not connected)."""
        from . import share
        token = share.Secrets(self.cfg.data_dir).get("clickup_token")
        if not token:
            return None
        try:
            video = self.yt.video(ep.video_id)
        except Exception:  # noqa: BLE001
            video = {}
        guest, part = ep.get("guest_name") or "", part_number(ep)
        label = share.episode_label(guest, part) or self.reel_title(ep)
        free = share.free_slots(share.ClickUp(token).tasks(), label, guest, part, share.episode_date(video), taken)
        days = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
        out = []
        for t in free:
            d = share.post_date(t)
            out.append(f"{days[d.weekday()]} {d.strftime('%d.%m')}" if t.get("due_date") else "sans date")
        return out

    def reel_share(self, ep: Episode, n: int, item: dict, taken: set[str], instagram: bool = True) -> dict:
        """Validated reel n → its ClickUp place (Instagram: the episode's next free « Reel k/N » slot, else a new
        « Reel · … » task; TikTok + Shorts only: a « Short · … » task), then Drive (« BTR Reels / <guest> », video +
        cover named MMDD_EPn_GUEST_FEED|SHORTS_TITLE, MMDD = planned date of the ClickUp task, else today; viewable by
        link), then the task gets the links, captions and cover, status approved. Drive and ClickUp are independent:
        one failing does not block the other. Returns what was done and why not."""
        from . import share
        sec = share.Secrets(self.cfg.data_dir)
        client = self.cfg.youtube_client[:2]
        title = item.get("title") or f"Reel {n}"
        guest = ep.get("guest_name") or ""
        part = part_number(ep)
        label = share.episode_label(guest, part) or self.reel_title(ep)
        url = f"https://www.youtube.com/watch?v={ep.video_id}"
        out: dict = {"links": dict(item.get("links") or {}), "drive_ids": dict(item.get("drive_ids") or {})}
        cu = task = kind = None
        # 1. ClickUp: where the reel goes (its date names the files)
        try:
            cu = share.ClickUp(sec.get("clickup_token"))
            try:
                video = self.yt.video(ep.video_id)
            except Exception:  # noqa: BLE001
                video = {}
            ep_date = share.episode_date(video)
            tid, kind = item.get("clickup_task"), item.get("clickup_kind")
            if tid:
                try:
                    task = cu.task(tid)
                except RuntimeError:
                    task = None                                     # deleted in ClickUp meanwhile
            if task and not kind:                                   # validated before the Instagram choice existed
                kind = "slot" if re.match(r"Reel\s+\d+\s*/\s*\d+", task.get("name", "")) else "ig_new"
            if task and (kind == "short") == instagram:             # Loïc changed his mind: undo the old place
                if kind == "slot":
                    orig = item.get("clickup_orig") or {}
                    old = task.get("markdown_description") or task.get("description") or ""
                    head = (re.match(r"(Reel\s+\d+\s*/\s*\d+)", task.get("name", "")) or [None, "Reel"])[1]
                    cu.update(task["id"], name=orig.get("name") or f"{head} · {label}",
                              markdown_content=orig.get("desc") or old.split(share.MARK)[0].rstrip(),
                              status="to generate")
                else:
                    cu.delete(task["id"])                           # a task the bot made itself
                out["clickup_freed"] = task.get("name", "")
                task, kind = None, None
            if task is None and instagram:
                slot = share.pick_slot(cu.tasks(), label, guest, part, ep_date, taken)
                if slot:
                    task, kind = cu.task(slot["id"]), "slot"
                    out["clickup_orig"] = {"name": task.get("name", ""),
                                           "desc": task.get("markdown_description") or task.get("description") or ""}
            if task is None:
                kind = "ig_new" if instagram else "short"
                name = f"{'Reel' if instagram else 'Short'} · {label} · {title}"[:200]
                fields = [{"id": share.F_EPISODE, "value": label}, {"id": share.F_FORMAT, "value": share.CLIP},
                          {"id": share.F_IG, "value": share.IG_TODO if instagram else share.IG_NO},
                          {"id": share.F_TT, "value": share.TT_TODO}, {"id": share.F_YT, "value": share.YT_TODO}]
                if instagram:
                    fields.append({"id": share.F_PLACEMENT, "value": share.REELS_TAB})
                task = cu.create(name=name, markdown_content=share.WHERE_IG if instagram else share.WHERE_SHORT,
                                 status="approved", custom_fields=fields)
                task.setdefault("name", name)
                task.setdefault("markdown_description", share.WHERE_IG if instagram else share.WHERE_SHORT)
                out["clickup_new"] = True
        except share.NotConnected as e:
            out["clickup_error"] = str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("clickup")
            out["clickup_error"] = str(e)[-300:]
        # 2. Drive: one folder per guest, files named for the calendar
        base = share.file_base(share.post_date(task), self.ep_number(ep), guest or self.reel_title(ep), instagram, title)
        out["file_base"] = base
        try:
            d = share.Drive(sec, client)
            root = sec.get("drive_root") or d.folder(share.FOLDER)
            sec.set(drive_root=root)
            sub = d.folder(guest or self.reel_title(ep), root)
            out["links"]["folder"] = d.folder_link(sub)
            ids = out["drive_ids"]
            for key, link in out["links"].items():                 # files uploaded before their ids were kept
                if key in ("video", "cover") and key not in ids and share.file_id(link):
                    ids[key] = share.file_id(link)
            f = d.put(Path(item["file"]), sub, f"{base}.mp4", "video/mp4", ids.get("video"))
            ids["video"], out["links"]["video"] = f["id"], f["webViewLink"]
            if item.get("cover") and Path(item["cover"]).exists():
                f = d.put(Path(item["cover"]), sub, f"{base}_COVER.jpg", "image/jpeg", ids.get("cover"))
                ids["cover"], out["links"]["cover"] = f["id"], f["webViewLink"]
            d.drop_empty_folders(root, keep=sub)                    # the old per-episode folders
        except share.NotConnected as e:
            out["drive_error"] = str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("drive")
            out["drive_error"] = share.drive_error(e)
        # 3. ClickUp: name, status, links, captions, cover
        if task is not None:
            try:
                old = ((share.WHERE_IG if instagram else share.WHERE_SHORT) if out.get("clickup_new")
                       else task.get("markdown_description") or task.get("description") or "")
                name = share.slot_name(task.get("name", ""), label, title) if kind == "slot" else task.get("name", "")
                cu.update(task["id"], name=name, status="approved",
                          markdown_content=share.description(old, out["links"], item, title, url, share.today_str(),
                                                             instagram, base))
                task["name"] = name
                if kind == "slot" and (not share._field(task, share.F_EPISODE)
                                       or "of " in str(share._field(task, share.F_EPISODE))):
                    cu.set_field(task["id"], share.F_EPISODE, label)
                if item.get("cover") and Path(item["cover"]).exists() and (
                        item.get("cover_sent") != item.get("cover") or out.get("clickup_new")
                        or item.get("clickup_task") != task["id"]):
                    try:
                        cu.attach(task["id"], Path(item["cover"]))
                        out["cover_sent"] = item["cover"]
                    except Exception:  # noqa: BLE001
                        log.exception("clickup attach")
                out.update(clickup_task=task["id"], clickup_kind=kind, clickup_name=name,
                           clickup_url=task.get("url") or f"https://app.clickup.com/t/{task['id']}")
            except Exception as e:  # noqa: BLE001
                log.exception("clickup")
                out["clickup_error"] = str(e)[-300:]
        return out

    def ep_number(self, ep: Episode) -> int | None:
        """BTR episode number of the guest (Kiera Brunton = 1 … Oti Mabuse = 13; both parts share it). A new guest
        gets the next number the first time a reel of theirs is filed; Loïc can correct it (ep["ep_number"])."""
        from . import share
        if ep.get("ep_number"):
            return int(ep["ep_number"])
        guest = ep.get("guest_name") or ""
        if not guest:
            return None
        path = self.cfg.data_dir / "ep_numbers.json"
        try:
            nums = json.loads(path.read_text())
        except Exception:  # noqa: BLE001
            nums = dict(share.EP_NUMBERS)
        key = share.guest_key(guest)
        if key not in nums:
            nums[key] = max(nums.values() or [0]) + 1
            path.write_text(json.dumps(nums, ensure_ascii=False, indent=1))
        return int(nums[key])

    def _cover_from_edit(self, work: Path, cdir: Path) -> list[dict]:
        """Fallback stills from the edit itself (1080×1920, no subtitles): guest frames only."""
        import cv2

        from . import reels as R
        cdir.mkdir(parents=True, exist_ok=True)
        edit = json.loads((work / "edit.json").read_text())
        dur = edit["frames"] / edit["fps"]
        out = []
        for i, t in enumerate([dur * k / 9 for k in range(1, 9)]):
            jpg = cdir / f"e_{i:02d}.jpg"
            R.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", work / "base.mp4", "-frames:v", "1",
                   "-q:v", "2", jpg])
            img = cv2.imread(str(jpg))
            k = R.classify(img, self.faces) if img is not None else {"kind": "none"}
            if k["kind"] in ("guest", "unsure") and R.layout_at(edit["layout"], t) != "split":
                out.append({"file": jpg.name, "t": round(t, 2), **k["face"]})
        return out

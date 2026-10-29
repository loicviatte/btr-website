"""The heavy, blocking steps. The Telegram bot calls these in a worker thread."""
import json
import re
from pathlib import Path

from . import design, frames, render, srt
from .config import Settings
from .faces import Faces
from .llm import LLM
from .state import Episode, Reels
from .youtube import YouTube


def _clean(s: str) -> str:
    return re.sub(r"^[\s“”\"']+|[\s“”\"']+$", "", s or "")


def clean_quote(a: dict) -> dict:
    return {"top": _clean(a.get("top")), "key": _clean(a.get("key")).upper(), "bottom": _clean(a.get("bottom"))}


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
            c.update(start_s=a, end_s=min(max(b, a + R.MIN_LEN), a + R.MAX_LEN), verified=t is not None)
            out.append(c)
        out.sort(key=lambda c: c["start_s"])
        for i, c in enumerate(out, 1):
            c["n"] = i
        R.cleanup(self.cfg.data_dir)
        shutil.rmtree(ep.dir / "reels", ignore_errors=True)       # a new list replaces the previous one
        return {"id": int(time.time()) % 1_000_000, "cands": out, "sel": [], "items": {}}

    def render_reel(self, ep: Episode, cand: dict, shift: list, cuts: list) -> dict:
        """Cut, frame, subtitle and render one moment. Pure: returns the reel's new fields, the caller stores them."""
        import cv2

        from . import reels as R
        from . import subs
        from .config import ASSETS
        n = cand["n"]
        work = ep.dir / "reels" / f"r{n:02d}"
        work.mkdir(parents=True, exist_ok=True)
        s0, s1 = float(shift[0]), float(shift[1])
        # the 6 s margin covers most adjustments; beyond it, the section downloaded grows
        a0 = cand["start_s"] + min(0.0, s0 + R.PAD - 1)
        b0 = cand["end_s"] + max(0.0, s1 - R.PAD + 1)
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
        if ep.file("captions_davinci.srt").exists():           # Loïc's SRT corrects the words (names, mishearings)
            words = R.correct_with_srt(words, self.cues(ep), dl_a + off)
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
        samples = [(t, R.classify(cv2.imread(str(p)), self.faces)) for t, p in R.sample_frames(clip, a, b, work / "frames")]
        shots = R.shot_layouts(samples, scene, a, b)
        pcs = R.pieces(ranges, shots, info["fps"], info["duration"])
        if not pcs:
            raise RuntimeError("extrait vide après le montage")
        video = R.render_video(clip, pcs, info, work / "pieces")
        audio = R.render_audio(clip, pcs, info["fps"], work, off)
        total = sum(p["frames"] for p in pcs) / info["fps"]
        ow = R.out_words(words, pcs, info["fps"])
        stats: dict = {}
        try:
            blocks = subs.parse_blocks(self.llm.reel_blocks([w.text for w in ow]), ow, stats=stats)
        except Exception:  # noqa: BLE001
            blocks = []
        if not blocks or stats.get("reinserted", 0) > 0.15 * len(ow):   # the model's layout misses too much
            blocks = subs.auto_blocks(ow)
        subs.timeline(blocks, total, lambda t: R.layout_at(pcs, t))
        fonts = subs.prepare_fonts(ASSETS, self.cfg.data_dir / "fonts")
        ass = subs.write_ass(blocks, fonts, work / "subs.ass")
        slug = re.sub(r"[^a-z0-9]+", "-", (ep.get("guest_name") or "btr").lower()).strip("-")
        out = R.final_mux(video, audio, ass, fonts, work / f"BTR_reel_{n:02d}_{slug}.mp4", total,
                          sum(p["frames"] for p in pcs))
        import shutil
        shutil.rmtree(work / "pieces", ignore_errors=True)        # ~400 MB of intermediate 1080p pieces
        kinds = [p["kind"] for p in pcs]
        return {"file": str(out), "duration": round(total, 1), "status": "preview", "confidence": round(conf),
                "shots": {k: kinds.count(k) for k in set(kinds)}, "said": " ".join(w.text for w in ow)[:1500],
                "shown": len(subs.shown_words(blocks)), "spoken": len(ow), "missing_cuts": missing,
                "size_mb": round(out.stat().st_size / 2 ** 20, 1)}

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
        return {"instagram": ig, "tiktok": tt}

"""The heavy, blocking steps. The Telegram bot calls these in a worker thread."""
import json
import re
from pathlib import Path

from . import frames, render, srt
from .config import Settings
from .faces import Faces
from .llm import LLM
from .state import Episode
from .youtube import YouTube


def _clean(s: str) -> str:
    return re.sub(r"^[\s“”\"']+|[\s“”\"']+$", "", s or "")


def clean_quote(a: dict) -> dict:
    return {"top": _clean(a.get("top")), "key": _clean(a.get("key")).upper(), "bottom": _clean(a.get("bottom"))}


def mmss(t: str) -> float:
    parts = [int(p) for p in re.findall(r"\d+", t or "0")] or [0]
    sec = 0
    for p in parts:
        sec = sec * 60 + p
    return float(sec)


def render_thumbs(ep: Episode, models_dir: Path, only: str | None = None, skip=()) -> dict[str, Path]:
    """Render the 3 thumbnails from the picked frames, or just one ("youtube" | "instagram" | "square").
    Designs in `skip` (validated by Loïc) are left untouched."""
    g, m = ep["pick_guest"], ep["pick_marius"]
    q = clean_quote(ep["final"])
    name = ep.get("guest_name", "")
    work = ep.dir / "render"
    want = [d for d in ("youtube", "square", "instagram") if only in (None, d) and d not in skip]
    out: dict[str, Path] = {}
    # the square reuses the frames/cut-outs made by the YouTube render
    if "youtube" in want or ("square" in want and not (work / "yt_marius_cut.png").exists()):
        yt = render.youtube(work, Path(g["hires"]), g["cx"], Path(m["hires"]), m["cx"], q, name)
        if "youtube" in want:
            out["youtube"] = yt
    if "square" in want:
        out["square"] = render.square(work, g["cx"], m["cx"], q, name)
    if "instagram" in want:
        out["instagram"] = render.instagram(work, models_dir, Path(g["hires"]), g, q, name)
    return out


class DryRun(Exception):
    """Raised instead of writing to a video that is already public."""


class Pipeline:
    def __init__(self, cfg: Settings):
        self.cfg = cfg
        self.yt = YouTube(cfg.youtube_token, cfg.channel_id, cfg.youtube_client)
        self.llm = LLM(cfg.anthropic_key, cfg.model)
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

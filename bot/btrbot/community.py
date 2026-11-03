"""YouTube Community posts of an episode (Loïc 02.11.2026): « YouTube Community · New episode tomorrow / Poll / World
Atlas · Ep … » tasks of the ClickUp calendar. YouTube has no API to publish them: the bot writes them (Opus, from the
transcript; the World Atlas one from the week's carousel in btr-media), Loïc validates them in « Stories & carrousels »,
and at the task's time the bot sends him the text + images ready to copy with « ✅ Posté sur YouTube ».
Rules (ClickUp tasks + world-atlas workflow): no link in the text; only the week's World Atlas, never a catch-up.
Pure: names, state, texts. bot.community_* drives it."""
import json
import re
from pathlib import Path

KINDS = {"tomorrow": "Nouvel épisode demain", "poll": "Sondage", "atlas": "World Atlas"}
MAX_Q, MAX_OPT = 100, 65          # YouTube poll limits (question, each option)


def task_kind(name: str) -> str | None:
    """« YouTube Community · Poll · Ep Nov 3 » → poll; « … · New episode tomorrow · … » → tomorrow; « … · World Atlas… »
    → atlas."""
    parts = [p.strip().lower() for p in re.split(r"\s+·\s+", name or "")]
    if len(parts) < 2 or "community" not in parts[0]:
        return None
    w = parts[1]
    if "tomorrow" in w or "demain" in w:
        return "tomorrow"
    if "poll" in w or "sondage" in w or "quiz" in w:
        return "poll"
    if "atlas" in w:
        return "atlas"
    return None


class State:
    def __init__(self, ep):
        self.ep = ep
        self.path = Path(ep.file("community.json"))
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {}
        self.items = self.data.setdefault("items", {})

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))


class ImgState:
    """The poll image's photos, kept in the poll item (item["img"]), shaped like posts.PostState so the posts Maker
    picks / offers / swaps them (Maker.choices, use_choice): item key « ycpoll », photo sid « ycpoll:face » (never
    « poll:face »: the Story Poll's files in posts/choices would be cleaned with it)."""

    def __init__(self, st: State, kind: str = "poll"):
        self.st, self.ep = st, st.ep
        self.data = st.items.setdefault(kind, {}).setdefault("img", {})
        self.data.setdefault("items", {})["ycpoll"] = {"kind": "ycpoll"}
        self.data.setdefault("content", {})["ycpoll"] = {}

    @property
    def items(self) -> dict:
        return self.data["items"]

    def save(self) -> None:
        self.st.save()


SID = "ycpoll:face"
SMILE_WANT = "souriant(e), regard vers la caméra si possible, visage bien net"


def image_caption(it: dict) -> str:
    """The poll image as its own YouTube « Image » post (a poll post can't carry an image): question + answers in the
    text, votes in the comments. No link."""
    opts = "\n".join(f"{i}. {o}" for i, o in enumerate(it.get("options") or [], 1))
    return "\n\n".join(x for x in (it.get("question") or "", opts, "Vote in our poll and tell us why in the comments.") if x)


def no_link(text: str) -> str:
    """No link on YouTube (Loïc's rule): URLs out, « link in bio » becomes « on the channel »."""
    t = re.sub(r"https?://\S+", "", text or "")
    t = re.sub(r"(?i)on YouTube and Spotify, link in bio\.", "on the channel.", t)
    t = re.sub(r"(?i),?\s*link in bio\.?", ".", t)
    t = re.sub(r"\.\.+", ".", t)
    return re.sub(r"[ \t]+\n", "\n", t).strip()


def atlas_entry(countries: dict, guest: str) -> tuple[str, dict] | None:
    """The country the guest landed on (btr-media pipeline/countries.json), the latest if several."""
    g = re.sub(r"[^a-z ]", "", (guest or "").lower()).split()
    best = None
    for slug, c in (countries or {}).items():
        cg = re.sub(r"[^a-z ]", "", str(c.get("guest", "")).lower()).split()
        if g and cg and g[0] == cg[0] and (len(g) < 2 or len(cg) < 2 or g[-1] == cg[-1]):
            if best is None or int(c.get("no", 0)) > int(best[1].get("no", 0)):
                best = (slug, c)
    return best


def atlas_images(media: str, slug: str, no: int, n: int = 8) -> list[str]:
    return [f"{media}world-atlas/{int(no):02d}-{slug}/{i:02d}.jpg" for i in range(1, n + 1)]


def block(it: dict) -> str:
    """The text Loïc copies into YouTube (poll: question + options)."""
    out = [it.get("text") or ""]
    if it.get("question"):
        out += ["", "Sondage : " + it["question"]] + [f"{i}. {o}" + (" ✓" if it.get("correct") == i - 1 else "")
                                                      for i, o in enumerate(it.get("options") or [], 1)]
    return "\n".join(x for x in out).strip()


def check(it: dict) -> list[str]:
    """What breaks YouTube's limits or Loïc's rules."""
    errs = []
    if re.search(r"https?://|www\.", it.get("text") or ""):
        errs.append("lien dans le texte")
    if it.get("question") is not None:
        if not 3 <= len(it["question"]) <= MAX_Q:
            errs.append("question trop longue")
        opts = it.get("options") or []
        if not 2 <= len(opts) <= 5 or any(len(o) > MAX_OPT for o in opts):
            errs.append("2 à 5 réponses de 65 caractères max")
    return errs

"""Carousels and stories of an episode (Loïc 31.10.2026; rules: claude/btr-carousels-workflow.md and
claude/btr-stories-workflow.md in the Claude project, templates = the validated Oti Part 2 pages of the canvas
« BTR Designs », ported to templates/posts.html).

Per episode, what to make comes from the ClickUp « Content calendar » tasks of that episode:
« Carousel · Key moment · Ep Nov 3 », « Carousel · Topics · … », « Story · Poll · … » (Teaser share, Poll, Rapid fire,
The Chain, Link, Ask the next guest, Question / answer, Quote, Atlas quiz). Steps (state in posts.json of the episode):
content (Opus: key moment, 6 topics, story texts; every quote checked as words really said) → shots (the 720p scan
copy sampled every 2 s, faces told apart: guest / Marius / both / wide / no face, eyes open checked, then the 4K frame)
→ render (Playwright, templates/posts.html) → previews in the « Stories & carrousels » topic → Loïc validates →
Drive (public links) + ClickUp task « ready » → published at the task's time: carousels and sticker-free stories by the
Instagram API, the others (sticker, link, teaser share, TikTok) as a notification with everything ready to copy.
"""
import html
import json
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image, ImageDraw

from .config import ASSETS, TEMPLATES

log = logging.getLogger("btrbot.posts")
TZ = ZoneInfo("Europe/London")
V = 1                                  # bump when the templates change: drafts are rendered again

# ClickUp task name → kind
STORY_NAMES = {"teaser share": "teaser", "teaser": "teaser", "poll": "poll", "rapid fire": "rapid", "the chain": "chain",
               "chain": "chain", "link": "link", "ask the next guest": "ask", "question / answer": "qa",
               "question/answer": "qa", "q&a": "qa", "quote": "quote", "citation": "quote", "atlas quiz": "atlas",
               "quiz atlas": "atlas", "world atlas quiz": "atlas"}
LABEL = {"moment": "Carrousel Key moment", "topics": "Carrousel Topics", "teaser": "Story Teaser share",
         "poll": "Story Poll", "rapid": "Story Rapid fire", "chain": "Story The Chain", "link": "Story Link",
         "ask": "Story Ask the next guest", "qa": "Story Question / réponse", "quote": "Story Citation",
         "atlas": "Story Quiz World Atlas"}
CAROUSELS = ("moment", "topics")
AUTO_STORIES = ("qa", "quote")        # no sticker: the API posts them; the others need Loïc's sticker in the app
STICKER = {"teaser": "partage du reel teaser + sticker lien", "poll": "sondage", "rapid": "quiz", "chain": "quiz",
           "link": "lien", "ask": "question", "atlas": "quiz"}
ZONES = {"poll": (1190, 1370), "rapid": (1220, 1530), "chain": (1240, 1550), "ask": (1270, 1550), "atlas": (800, 1110),
         "link": (1500, 1620), "teaser": (1500, 1620)}
B_OK = ("poll", "rapid", "chain", "atlas")   # kinds with a « b » version (link at the bottom, no poll / quiz)
# 3-episode story cycle (stories workflow) when the calendar has no task for an episode
CYCLE = [["teaser", "poll", "chain", "quote"], ["teaser", "rapid", "qa", "ask"], ["teaser", "poll", "link", "ask"]]


# ---------------------------------------------------------------- ClickUp tasks of an episode
def task_kind(name: str) -> str | None:
    parts = [p.strip().lower() for p in re.split(r"\s+·\s+", name or "")]
    if len(parts) < 2:
        return None
    if parts[0] in ("carousel", "carrousel"):
        if "key moment" in parts[1] or "moment" in parts[1]:
            return "moment"
        if "topic" in parts[1] or "sujet" in parts[1]:
            return "topics"
        return None                                 # World Atlas carousels have their own pipeline
    if parts[0] == "story":
        return STORY_NAMES.get(parts[1])
    return None


def due(task: dict | None) -> datetime | None:
    d = (task or {}).get("due_date")
    try:
        return datetime.fromtimestamp(int(d) / 1000, TZ) if d else None
    except (TypeError, ValueError):
        return None


def tiktok_time(task: dict, ig_at: datetime | None) -> datetime | None:
    """« Time: 10:00 Instagram · 12:00 TikTok » → that day at 12:00; else 2 h after Instagram (carousels only)."""
    if not ig_at:
        return None
    m = re.search(r"(\d{1,2})[:h](\d{2})\s*TikTok", task.get("text_content") or task.get("markdown_description")
                  or task.get("description") or "", re.I)
    if m:
        return ig_at.replace(hour=int(m.group(1)), minute=int(m.group(2)))
    return ig_at + timedelta(hours=2)


def episode_items(tasks: list[dict], matches) -> dict:
    """{key: {kind, task}} for this episode's tasks (matches(task) → bool). Key = kind (one of each per episode)."""
    out = {}
    for t in sorted(tasks, key=lambda t: int(t.get("due_date") or 9e15)):
        k = task_kind(t.get("name", ""))
        if k and matches(t) and k not in out:
            out[k] = {"kind": k, "task": t["id"], "name": t.get("name", "")}
    return out


def default_items(ep_no: int | None) -> dict:
    kinds = ["moment", "topics"] + CYCLE[((ep_no or 1) - 1) % 3]
    return {k: {"kind": k, "task": None, "name": LABEL[k]} for k in kinds}


# ---------------------------------------------------------------- text helpers
def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def gold_html(text: str, gold: list[str]) -> str:
    """The sentence with its key words in gold (each phrase once, case-insensitive, whole words)."""
    out = esc(text)
    for g in gold or []:
        g = esc(str(g).strip())
        if not g:
            continue
        m = re.search(r"(?<![\w’'])" + re.escape(g) + r"(?![\w’'])", out, re.I)
        if m:
            out = out[:m.start()] + f'<span class="gold">{m.group(0)}</span>' + out[m.end():]
    return out


def lines_html(text: str) -> str:
    return "<br>".join(esc(x.strip()) for x in str(text or "").split("\n") if x.strip())


def first_name(guest: str) -> str:
    return (guest or "Our guest").split()[0]


def poss(first: str) -> str:
    return first + "’s"


def tc(t: float) -> str:
    t = int(round(t))
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def secs(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    parts = [int(p) for p in re.findall(r"\d+", str(v))]
    if not parts:
        return None
    s = 0
    for p in parts[-3:]:
        s = s * 60 + p
    return float(s)


def clean(x) -> str:
    return re.sub(r"\s+", " ", re.sub(r"^[\s“”\"']+|[\s“”\"']+$", "", str(x or ""))).strip()


def find_time(cues, text: str) -> float | None:
    """When these words start being said: the LAST cue window that still holds the whole quote (srt.find_quote gives
    the start of the first window, up to 4 cues early)."""
    from rapidfuzz import fuzz
    q = re.sub(r"[^\w\s']", "", (text or "").lower().replace("’", "'")).strip()
    if not q:
        return None
    scores = []
    for i in range(len(cues)):
        w = re.sub(r"[^\w\s']", "", " ".join(c.text for c in cues[i:i + 4]).lower().replace("’", "'"))
        scores.append(fuzz.partial_ratio(q, w))
    if not scores or max(scores) < 80:
        return None
    top = max(scores)
    best = scores.index(top)
    while best + 1 < len(scores) and scores[best + 1] >= top - 2:   # later windows still hold it: it starts later
        best += 1
    return cues[best].start


# ---------------------------------------------------------------- captions (code assembles the validated format)
def captions(kind: str, c: dict, guest: str, handle: str | None, part: str | None) -> dict:
    who_ig = "@" + handle if handle else guest
    out_line = (f"Full episode, part {part}, on YouTube and Spotify" if part else "Full episode on YouTube and Spotify")
    gtag = "#" + re.sub(r"[^A-Za-z0-9]", "", guest or "")
    extra = [t if str(t).startswith("#") else "#" + str(t) for t in (c.get("tags") or [])[:3] if re.fullmatch(r"#?\w+", str(t))]
    tags = " ".join(dict.fromkeys(["#BreakTheRoutine", "#DanceSport", "#Ballroom", "#LatinDance", gtag, *extra,
                                   "#DancePodcast"]))
    if kind == "moment":
        hook, quote, ctx = clean(c.get("hook")), clean(c.get("quote")), re.sub(r"[.:]+$", "", clean(c.get("context")))
        q = clean(c.get("question")) or "Have you ever felt this?"
        q += "" if q.endswith("?") else "?"

        def body(who):
            line = f"{who} on {ctx}: “{quote}”" if quote and quote != hook else f"{who} on {ctx}."
            return "\n\n".join(x for x in (f"“{hook}”" if hook else "", line, f"{q} Tell us in the comments.") if x)
        return {"instagram": f"{body(who_ig)}\n\n{out_line}, link in bio.",
                "tiktok": f"{body(guest)}\n\n{out_line}.\n\n{tags}"}
    if kind == "topics":
        hook = clean(c.get("hook")) or ""
        hook = re.sub(r"\s*Swipe through\.?$", "", hook).strip()
        summ = clean(c.get("summary")) or "{guest} told us everything."
        if "{guest}" not in summ:
            summ = summ.rstrip(".") + ", with {guest}."

        def body(who):
            return "\n\n".join(x for x in (hook, summ.replace("{guest}", who),
                                           "Which moment would you watch first? Tell us in the comments.") if x)
        return {"instagram": f"{body(who_ig)}\n\n{out_line}, link in bio.", "tiktok": f"{body(guest)}\n\n{out_line}.\n\n{tags}"}
    return {}


# ---------------------------------------------------------------- photo placement
def place(src: str, size: tuple[int, int], box: tuple[int, int, int, int], face: dict | None = None,
          cx: float = 0.5, cy: float | None = None, zoom: float = 1.0, css: str = "", shot: dict | None = None,
          sid: str | None = None) -> dict:
    """The photo covers the box; the face (fractions of the frame) lands at (cx, cy) of the box. zoom > 1 = closer;
    zoom < 1 = wider than the frame allows: the missing set around it is generated (Maker.fill_gaps → shot["ext"])."""
    W, H = size
    bw, bh = box[2], box[3]
    s = max(bw / W, bh / H) * zoom
    w, h = W * s, H * s
    if face:
        fx, fy = bw * cx - face["cx"] * w, (bh * cy - face["cy"] * h) if cy is not None else (bh - h) / 2
        left = min(0.0, max(bw - w, fx)) if w >= bw else fx
        top = min(0.0, max(bh - h, fy)) if h >= bh else fy
    else:
        left, top = (bw - w) / 2, (bh - h) / 2
    p = {"src": src, "box": box, "left": round(left, 1), "top": round(top, 1), "w": round(w, 1), "h": round(h, 1),
         "css": css, "sid": sid}
    gap = left > 0.5 or top > 0.5 or left + w < bw - 0.5 or top + h < bh - 0.5
    if gap:
        p["gap_key"] = f"{bw}x{bh}|{p['left']:.0f}|{p['top']:.0f}|{p['w']:.0f}"
        ext = ((shot or {}).get("ext") or {}).get(p["gap_key"])
        if ext and Path(ext).exists():                  # the set around the photo already generated: it fills the box
            p.update(src=Path(ext).as_uri(), left=0, top=0, w=bw, h=bh, gap_key=None)
    return p


def gap_region(p: dict, size: tuple[int, int]) -> tuple[float, float, float, float]:
    """The part of the source photo (pixels, may go outside it) that the box shows."""
    k = p["w"] / size[0]
    bw, bh = p["box"][2], p["box"][3]
    return (-p["left"] / k, -p["top"] / k, (bw - p["left"]) / k, (bh - p["top"]) / k)


def pair_zoom(faces: list[dict], sizes: list[tuple[int, int]], box: tuple[int, int, int, int]) -> list[float]:
    """Zooms so two faces side by side (or stacked) have the same height on screen: the SMALLER face sets the size
    (the closer photo is pulled back, the set around it generated), so nobody looks blown up."""
    hs = []
    for f, (W, H) in zip(faces, sizes):
        s = max(box[2] / W, box[3] / H)
        hs.append((f or {}).get("fh", 0.2) * H * s)
    low = min(hs)
    return [max(0.45, low / h) if h else 1.0 for h in hs]


def pair_place(src: list[str], faces: list[dict], sizes: list[tuple[int, int]], boxes: list[tuple], eye_y: float,
               css: str = "", shots: list | None = None, sids: list | None = None) -> list[dict]:
    """Two photos with the faces at the same size and the eyes on the same line (eye_y, fraction of the box)."""
    zs = pair_zoom(faces, sizes, boxes[0])
    shots = shots or [None] * len(src)
    sids = sids or [None] * len(src)
    out = []
    for s_, f, size, box, z, sh, sid in zip(src, faces, sizes, boxes, zs, shots, sids):
        f = dict(f or {})
        if "eyes" in f:                                  # place the eyes (not the face centre) on the line
            f["cy"] = f["eyes"]
        z *= float((sh or {}).get("zoom_adj") or 1.0)
        out.append(place(s_, size, box, f or None, 0.5, eye_y, z, css, sh, sid))
    return out


# ---------------------------------------------------------------- previews
def zones_preview(clean_jpg: Path, kind: str, b: bool, out: Path) -> Path:
    """Clean story on the left, the Instagram zones in dotted lines on the right (stories workflow)."""
    im = Image.open(clean_jpg).convert("RGB")
    W, H = im.size
    z = im.copy()
    d = ImageDraw.Draw(z, "RGBA")

    def dash(y0, y1, color, label):
        d.rectangle([0, y0, W, y1], fill=color[:3] + (40,))
        for x in range(0, W, 40):
            d.line([x, y0, x + 20, y0], fill=color, width=4)
            d.line([x, y1, x + 20, y1], fill=color, width=4)
        d.text((24, y0 + 8), label, fill=color)
    dash(0, 250, (255, 255, 255, 255), "barre + profil")
    dash(1700, H, (255, 255, 255, 255), "champ message")
    zone = ZONES.get("link" if b else kind)
    if zone:
        dash(zone[0], zone[1], (254, 203, 122, 255), "sticker " + ("lien" if b else STICKER.get(kind, "")))
    sheet = Image.new("RGB", (W * 2 + 40, H), (8, 4, 3))
    sheet.paste(im, (0, 0))
    sheet.paste(z, (W + 40, 0))
    sheet = sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)
    sheet.save(out, quality=88)
    return out


# ---------------------------------------------------------------- rendering
env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))


def render_pages(pages: list[dict], work: Path) -> list[dict]:
    """pages: [{name, H, kind, …template vars}] → [{name, file, overflow}] (one browser for all)."""
    from playwright.sync_api import sync_playwright
    work.mkdir(parents=True, exist_ok=True)
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(timeout=60000)
        for pg_vars in pages:
            name = pg_vars["name"]
            H = pg_vars.get("H", 1350)
            page_html = env.get_template("posts.html").render(assets=ASSETS.as_uri(), **pg_vars)
            f = work / f"{name}.html"
            f.write_text(page_html)
            pg = b.new_page(viewport={"width": 1080, "height": H})
            pg.set_default_timeout(60000)
            pg.goto(f.as_uri())
            pg.evaluate("document.fonts.ready")
            pg.wait_for_load_state("networkidle")
            info = pg.evaluate("window.fit()") or {}
            png = work / f"{name}.png"
            pg.screenshot(path=str(png))
            pg.close()
            jpg = work / f"{name}.jpg"
            Image.open(png).convert("RGB").save(jpg, quality=92, optimize=True, progressive=True)
            png.unlink(missing_ok=True)
            out.append({"name": name, "file": str(jpg), "overflow": info.get("overflow") or []})
        b.close()
    return out


# ---------------------------------------------------------------- what each item needs (shots) and its pages
def needs(kind: str, c: dict, n_topics: int = 6) -> list[dict]:
    """Shots an item needs: {id, who (guest|marius|both|wide|noface|prev), t (seconds or None), win (search ±s)}."""
    if kind == "moment":
        ss = c.get("sentences") or []
        out = []
        for i, s in enumerate(ss):
            t = secs(s.get("t"))
            nxt = secs(ss[i + 1].get("t")) if i + 1 < len(ss) else None
            span = max(4.0, min(12.0, (nxt - t) if (t is not None and nxt is not None and nxt > t) else 8.0))
            out.append({"id": f"m{i}", "who": "guest", "t": t, "win": span, "after": True})
        return out
    if kind == "topics":
        out = [{"id": "cover", "who": "guest", "t": None, "win": None}]
        for i, it in enumerate((c.get("items") or [])[:n_topics]):
            lay = "ABCDAB"[i % 6]
            who = "both" if lay in "AC" else "guest"
            out.append({"id": f"t{i}", "who": who, "t": secs(it.get("qt")) or secs(it.get("start")), "win": 90})
        out.append({"id": "end", "who": "both", "t": None, "win": None})
        return out
    t = secs(c.get("t"))
    return {
        "teaser": [{"id": "bg", "who": "wide", "t": None, "win": None}],
        "poll": [{"id": "face", "who": "guest", "t": t, "win": 60}],
        "rapid": [{"id": "face", "who": "guest", "t": t, "win": 90}],
        "chain": [{"id": "prev", "who": "prev", "t": None, "win": None},
                  {"id": "face", "who": "guest", "t": t, "win": 60}],
        "link": [{"id": "bg", "who": "wide", "t": None, "win": None}, {"id": "band", "who": "both", "t": t, "win": 120}],
        "ask": [{"id": "face", "who": "marius", "t": t, "win": 60}],
        "qa": [{"id": "q", "who": "marius", "t": secs(c.get("t_q")) or t, "win": 30},
               {"id": "a", "who": "guest", "t": secs(c.get("t_a")) or t, "win": 30}],
        "quote": [{"id": "face", "who": "guest", "t": t, "win": 30}],
        "atlas": [{"id": "hands", "who": "noface", "t": t, "win": 90}],
    }.get(kind, [])


def pages(kind: str, c: dict, shots: dict, ctx: dict, b: bool = False) -> list[dict]:
    """Template variables of every page of an item. shots: id → {file (4K jpg), size, face}. ctx: guest, part, …"""
    guest, part = ctx["guest"], ctx.get("part")
    first = first_name(guest)
    uri = lambda sid: Path(shots[sid]["file"]).as_uri() if sid in shots else ""  # noqa: E731

    def ph(sid, box, cx=0.5, cy=None, zoom=1.0, css=""):
        s = shots.get(sid) or {}
        z = zoom * float(s.get("zoom_adj") or 1.0)
        return place(uri(sid), tuple(s.get("size") or (3840, 2160)), box, s.get("face"), cx, cy, z, css, s, sid)

    def logo_x(sid):
        f = (shots.get(sid) or {}).get("face") or {}
        return 64 if f.get("cx", 0.5) > 0.62 else 876

    if kind == "moment":
        ss = c.get("sentences") or []
        out = []
        for i in range(max(1, min(4, len(ss) // 2))):
            a, bb = (ss[2 * i] if 2 * i < len(ss) else {}), (ss[2 * i + 1] if 2 * i + 1 < len(ss) else {})
            out.append({"name": f"moment-{i + 1:02d}", "H": 1350, "kind": "moment", "first": i == 0,
                        "p1": ph(f"m{2 * i}", (0, 0, 1080, 675)), "p2": ph(f"m{2 * i + 1}", (0, 675, 1080, 675)),
                        "s1": gold_html(a.get("text", ""), a.get("gold")), "s2": gold_html(bb.get("text", ""), bb.get("gold")),
                        "name_upper": guest.upper(), "guest_title": ctx.get("guest_title") or ""})
        return out
    if kind == "topics":
        items = (c.get("items") or [])[:6]
        n = len(items) + 2
        out = [{"name": "topics-01", "H": 1350, "kind": "topics_cover", "p1": ph("cover", (0, 0, 1080, 1350), 0.5, 0.3),
                "part": part, "count": len(items), "name_lines": guest.upper().split(),
                "hook": clean(c.get("hook")) or "Swipe through."}]
        for i, it in enumerate(items):
            lay = "ABCDAB"[i % 6]
            box = {"A": (0, 640, 1080, 540), "B": (0, 500, 1080, 850), "C": (0, 0, 1080, 720), "D": (0, 0, 1080, 1350)}[lay]
            cy = {"A": 0.5, "B": 0.3, "C": 0.45, "D": 0.3}[lay]
            out.append({"name": f"topics-{i + 2:02d}", "H": 1350, "kind": "topics_item", "layout": lay,
                        "p1": ph(f"t{i}", box, 0.5, cy), "num": f"{i + 1:02d}", "watch": it.get("watch", ""),
                        "title": it.get("title", ""), "context": it.get("context", ""), "quote": it.get("quote", ""),
                        "counter": f"{i + 2:02d} / {n:02d}"})
        out.append({"name": f"topics-{n:02d}", "H": 1350, "kind": "topics_end", "p1": ph("end", (0, 0, 1080, 608), 0.5, 0.42),
                    "counter": f"{n:02d} / {n:02d}", "toc": [{"watch": it.get("watch", ""), "title": it.get("title", "")} for it in items]})
        return out
    base = {"name": f"story-{kind}{'-b' if b else ''}", "H": 1920, "kind": kind, "b": b, "first": first,
            "first_upper": first.upper(), "footer": c.get("footer") or f"{'Part ' + part + ', link' if part else 'Link'} in bio."}
    full = (0, 0, 1080, 1920)
    if kind == "teaser":
        base.update(p1=ph("bg", full, css="filter:blur(14px) brightness(.8);transform:scale(1.06)"),
                    line=f"NEW EPISODE · {guest.upper()}" + (f" PART {part}" if part else ""))
    elif kind == "poll":
        base.update(p1=ph("face", full), logo_x=logo_x("face"), line=lines_html(c.get("line")),
                    question=c.get("question", ""), tap=c.get("tap") or "to hear why.")
    elif kind == "rapid":
        base.update(p1=ph("face", full), logo_x=logo_x("face"), question=c.get("question", ""),
                    rapid_count=c.get("count") or 0)
    elif kind == "chain":
        p1, p2 = pair_place([uri("prev"), uri("face")], [(shots.get(k) or {}).get("face") for k in ("prev", "face")],
                            [tuple((shots.get(k) or {}).get("size") or (3840, 2160)) for k in ("prev", "face")],
                            [(0, 0, 538, 1920), (542, 0, 538, 1920)], 0.33,
                            shots=[shots.get("prev"), shots.get("face")], sids=["prev", "face"])
        base.update(p1=p1, p2=p2,
                    prev_upper=str(c.get("prev_guest") or "THE LAST GUEST").upper(), question=c.get("question", ""))
    elif kind == "link":
        base.update(p1=ph("bg", full, css="filter:blur(16px) brightness(.55);transform:scale(1.06)"),
                    p2=ph("band", (0, 0, 1080, 604), 0.5, 0.45),
                    line=f"{guest.upper()}" + (f" · PART {part}" if part else ""),
                    headline=c.get("headline", ""), tap=c.get("tap") or "to hear what they told us.")
    elif kind == "ask":
        base.update(p1=ph("face", full, 0.5, None), logo_x=logo_x("face"))
    elif kind == "qa":
        p1, p2 = pair_place([uri("q"), uri("a")], [(shots.get(k) or {}).get("face") for k in ("q", "a")],
                            [tuple((shots.get(k) or {}).get("size") or (3840, 2160)) for k in ("q", "a")],
                            [(0, 0, 1080, 958), (0, 962, 1080, 958)], 0.34,
                            shots=[shots.get("q"), shots.get("a")], sids=["q", "a"])
        base.update(p1=p1, p2=p2,
                    question=c.get("question", ""), answer=c.get("answer", ""))
    elif kind == "quote":
        base.update(p1=ph("face", full), logo_x=logo_x("face"), quote=c.get("quote", ""),
                    label=str(c.get("label") or f"{guest} ON THE PODCAST").upper(),
                    sub=f"Part {part} · link in bio" if part else "Link in bio")
    elif kind == "atlas":
        base.update(p1=ph("hands", full), pronoun=c.get("pronoun") or ctx.get("pronoun") or "they")
    return [base]


def slide_sids(kind: str, slide: int, part: str | None = None, n_topics: int = 6) -> list[str]:
    """Photos (shot ids) on one slide: Key moment slide n = 2 photos (top / bottom), Topics 1 = cover, last = end."""
    if kind == "moment":
        ids = [f"m{2 * (slide - 1)}", f"m{2 * (slide - 1) + 1}"]
        p = (part or "").lower()
        if p in ("haut", "top", "h", "1", "up"):
            return ids[:1]
        if p in ("bas", "bottom", "b", "2", "down"):
            return ids[1:]
        return ids
    if kind == "topics":
        last = n_topics + 2
        if slide <= 1:
            return ["cover"]
        if slide >= last:
            return ["end"]
        return [f"t{slide - 2}"]
    return []


def sid_slide(kind: str, sid: str, n_topics: int = 6) -> int:
    if kind == "moment" and sid.startswith("m"):
        return int(sid[1:]) // 2 + 1
    if kind == "topics":
        return 1 if sid == "cover" else n_topics + 2 if sid == "end" else int(sid[1:]) + 2
    return 1


# ---------------------------------------------------------------- shot choice
def score(c: dict) -> float:
    return c.get("sharp", 0) * (0.6 + c.get("fh", 0)) - 40 * max(0.0, c.get("cy", 0.4) - 0.45)


def pick(cands: list[dict], need: dict, used: list[float]) -> list[dict]:
    """Candidates for one shot, best first: in the window when the moment is known (the guest's own sentence for the
    key moment), never a frame already used (3 s apart)."""
    pool = [c for c in cands if c["kind"] == need["who"] and all(abs(c["t"] - u) >= 3 for u in used)]
    fh = need.get("fh")
    if fh:                                    # a given face size (« plus petite », or matched to the other face)
        near_t = need.get("t")
        pool = sorted(pool, key=lambda c: abs(c.get("fh", 0) - fh) / fh * 3 - score(c) / 400
                      + (abs(c["t"] - near_t) / 600 if near_t is not None else 0))
        return pool
    t, win = need.get("t"), need.get("win")
    if t is not None and win:
        lo, hi = (t - 1, t + win) if need.get("after") else (t - win, t + win)
        near = [c for c in pool if lo <= c["t"] <= hi]
        if near:
            return sorted(near, key=lambda c: -score(c) + 0.5 * abs(c["t"] - t))
        wide = [c for c in pool if abs(c["t"] - t) <= 3 * win]
        if wide:
            return sorted(wide, key=lambda c: abs(c["t"] - t))
    return sorted(pool, key=lambda c: -score(c))


def classify(faces_found: list, W: int, H: int, match: float, not_match: float) -> dict:
    """One sampled frame → kind guest | marius | both | wide | noface | None (unclear), with the main face."""
    fs = [f for f in faces_found if f.score > 0.8]
    if not fs:
        return {"kind": "noface"}
    info = []
    for f in fs:
        x, y, w, h = f.box
        who = "marius" if f.sim_marius >= match else ("guest" if f.sim_marius < not_match else None)
        info.append({"who": who, "cx": (x + w / 2) / W, "cy": (y + h / 2) / H, "fw": w / W, "fh": h / H, "top": y / H})
    big = [i for i in info if i["fh"] >= 0.16]
    if len(fs) >= 2 and {i["who"] for i in info} >= {"marius", "guest"}:
        ms = [i for i in info if i["who"] == "marius"][0]
        gs = [i for i in info if i["who"] == "guest"][0]
        mid = {"cx": (ms["cx"] + gs["cx"]) / 2, "cy": (ms["cy"] + gs["cy"]) / 2, "fh": max(ms["fh"], gs["fh"]),
               "fw": max(ms["fw"], gs["fw"]), "top": min(ms["top"], gs["top"])}
        return {"kind": "both", **mid}
    if len(big) == 1 and len(fs) == 1 and big[0]["who"]:
        return {"kind": big[0]["who"], **{k: v for k, v in big[0].items() if k != "who"}}
    if not big:
        f0 = max(info, key=lambda i: i["fh"])
        return {"kind": "wide", **{k: v for k, v in f0.items() if k != "who"}}
    return {"kind": None}


# ---------------------------------------------------------------- state
class PostState:
    """data/episodes/<id>/posts.json"""

    def __init__(self, ep):
        self.ep = ep
        self.path = ep.dir / "posts.json"
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {"items": {}, "content": {}, "shots": {}}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
        tmp.replace(self.path)

    @property
    def items(self) -> dict:
        return self.data.setdefault("items", {})


def all_states(data_dir: Path) -> list:
    """Every episode with posts (for the publishing tick)."""
    from .state import Episode
    out = []
    for p in sorted((data_dir / "episodes").glob("*/posts.json")):
        out.append(PostState(Episode(data_dir, p.parent.name)))
    return out


def now() -> datetime:
    return datetime.now(timezone.utc)


def label_time(dt: datetime | None) -> str:
    if not dt:
        return "pas de date"
    d = dt.astimezone(TZ)
    days = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
    return f"{days[d.weekday()]} {d.strftime('%d.%m %H:%M')}"


def drive_direct(fid: str) -> str:
    return f"https://drive.usercontent.google.com/download?id={fid}&export=download"


def stamp() -> float:
    return time.time()

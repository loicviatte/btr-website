"""« BTR Data » for Simone, the team's ClickUp analytics agent (Loïc 02.11.2026): every Tuesday evening, after the
episode of the day is out, the bot writes into the ClickUp doc « BTR Data » (space Break The Routine Podcast):
  - « Stats hebdo »: one block per posting week (Tuesday → Monday), newest on top: followers per platform and their
    weekly change, every post of the week with its figures (Instagram reels / carousels / images, TikTok videos, YouTube
    Shorts), the full episodes on YouTube (views and weekly change; with YouTube Analytics: average % watched, average
    view duration, and where viewers drop in the latest episodes, with what was being said there);
  - « Épisodes »: one sub-page per episode (digest written by Opus from the transcript + the whole transcript below),
    made once.
Simone reads it (Knowledge) and publishes her review in ClickUp (« Revues de Simone »).
Sources: Instagram Graph API + TikTok (sandbox) as in stats.py, the repo's data/stats/youtube.json and
tools/episode-generator/trans.json (GitHub API), the bot's own SRTs, YouTube Analytics (a separate Google grant,
scope yt-analytics.readonly, /connect). Snapshots in data/insights/state.json give the week-on-week changes.
"""
import json
import logging
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

from .share import REDIRECT, NotConnected, Secrets

log = logging.getLogger("btrbot.insights")
TZ = ZoneInfo("Europe/London")
WS = "90151241571"
DOC = "2kypxhv3-5115"
PAGES = {"stats": "2kypxhv3-7635", "episodes": "2kypxhv3-7655", "reviews": "2kypxhv3-7675"}
REPO = "loicviatte/btr-website"
ANALYTICS_SCOPE = "https://www.googleapis.com/auth/yt-analytics.readonly"
CHUNK = 30000                       # characters per transcript page


# ---------------------------------------------------------------- ClickUp docs (API v3)
class Docs:
    def __init__(self, token: str):
        if not token:
            raise NotConnected("ClickUp")
        self.h = {"Authorization": token, "Content-Type": "application/json"}
        self.base = f"https://api.clickup.com/api/v3/workspaces/{WS}/docs/{DOC}"

    def _req(self, method: str, path: str, **kw) -> dict:
        for i in range(3):
            r = requests.request(method, self.base + path, headers=self.h, timeout=60, **kw)
            if r.status_code == 429:
                time.sleep(5 * (i + 1))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"ClickUp docs {r.status_code}: {r.text[:200]}")
            return r.json() if r.text else {}
        raise RuntimeError("ClickUp docs: trop de requêtes")

    def create(self, name: str, content: str, parent: str | None = None) -> str:
        body = {"name": name[:200], "content": content, "content_format": "text/md"}
        if parent:
            body["parent_page_id"] = parent
        return str(self._req("POST", "/pages", json=body).get("id"))

    def update(self, page: str, content: str, mode: str = "replace") -> None:
        self._req("PUT", f"/pages/{page}", json={"content": content, "content_edit_mode": mode,
                                                  "content_format": "text/md"})


# ---------------------------------------------------------------- repo files
def gh_file(token: str, path: str):
    h = {"Accept": "application/vnd.github.raw+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    r = requests.get(f"https://api.github.com/repos/{REPO}/contents/{path}", headers=h, params={"ref": "main"},
                     timeout=60)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- YouTube Analytics (own Google grant)
def analytics_auth_url(client_id: str) -> str:
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code", "access_type": "offline",
        "prompt": "consent", "scope": ANALYTICS_SCOPE})


def analytics_connect(sec: Secrets, client: tuple[str, str], code: str) -> None:
    r = requests.post("https://oauth2.googleapis.com/token", timeout=30, data={
        "code": code, "client_id": client[0], "client_secret": client[1], "redirect_uri": REDIRECT,
        "grant_type": "authorization_code"})
    tok = r.json()
    if "refresh_token" not in tok:
        raise RuntimeError(tok.get("error_description") or tok.get("error") or "Google n'a pas renvoyé d'accès")
    if ANALYTICS_SCOPE not in tok.get("scope", ""):
        raise RuntimeError("l'accès YouTube Analytics n'a pas été coché sur la page Google : recommence et coche-le")
    sec.set(analytics_refresh=tok["refresh_token"])


def analytics(sec: Secrets, client: tuple[str, str]):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    refresh = sec.get("analytics_refresh")
    if not refresh:
        raise NotConnected("YouTube Analytics")
    creds = Credentials(None, refresh_token=refresh, client_id=client[0], client_secret=client[1],
                        token_uri="https://oauth2.googleapis.com/token", scopes=[ANALYTICS_SCOPE])
    creds.refresh(Request())
    return build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)


def yt_query(svc, **kw) -> list[dict]:
    r = svc.reports().query(ids="channel==MINE", **kw).execute()
    cols = [c["name"] for c in r.get("columnHeaders", [])]
    return [dict(zip(cols, row)) for row in r.get("rows", []) or []]


def yt_videos(svc, start: str, end: str, n: int = 50) -> dict:
    """video id → views, minutes watched, average view duration (s) and % between start and end."""
    rows = yt_query(svc, startDate=start, endDate=end, dimensions="video", sort="-views", maxResults=n,
                    metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained")
    return {r["video"]: r for r in rows}


def yt_retention(svc, vid: str, published: str, end: str) -> list[tuple[float, float]]:
    """(fraction of the video, share of viewers still watching) every 1 %."""
    rows = yt_query(svc, startDate=published[:10], endDate=end, dimensions="elapsedVideoTimeRatio",
                    metrics="audienceWatchRatio", filters=f"video=={vid}")
    return [(float(r["elapsedVideoTimeRatio"]), float(r["audienceWatchRatio"])) for r in rows]


def drops(curve: list[tuple[float, float]], k: int = 3) -> list[tuple[float, float]]:
    """The k steepest drops after the first 5 % (the intro always loses people): (fraction, lost share)."""
    out = []
    for (x0, y0), (x1, y1) in zip(curve, curve[1:]):
        if x0 >= 0.05:
            out.append((x1, y0 - y1))
    return sorted([d for d in out if d[1] > 0], key=lambda d: -d[1])[:k]


def at_share(curve: list[tuple[float, float]], x: float) -> float | None:
    near = [c for c in curve if abs(c[0] - x) <= 0.011]
    return near[0][1] if near else None


# ---------------------------------------------------------------- helpers
def mmss(s: float) -> str:
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60:02d}:{s % 60:02d}"


def said_at(lines: list, t: float) -> str:
    """The transcript line around second t (trans.json lines = [seconds, text])."""
    best = None
    for s, txt in lines or []:
        if s <= t + 2:
            best = txt
        else:
            break
    return (best or "")[:160]


def week(now: datetime) -> tuple[datetime, datetime]:
    """The posting week that just ended (Tuesday 00:00 → Tuesday 00:00, London) when run on a Tuesday evening; on any
    other day, the week in progress until now."""
    now = now.astimezone(TZ)
    start = (now - timedelta(days=(now.weekday() - 1) % 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    if now.weekday() == 1:                    # Tuesday: the week that closed this morning
        start -= timedelta(days=7)
    return start, start + timedelta(days=7)


def day_label(d: datetime) -> str:
    days = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
    d = d.astimezone(TZ)
    return f"{days[d.weekday()]} {d.strftime('%d.%m')}"


def delta(now, before) -> str:
    if now is None:
        return "—"
    if before is None:
        return "(1er relevé)"
    d = now - before
    return f"+{d}" if d > 0 else str(d)


def table(head: list[str], rows: list[list]) -> str:
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "/").replace("\n", " ") for x in r) + " |")
    return "\n".join(out)


def instagram_media(sec: Secrets, since: datetime) -> tuple[int, list[dict]]:
    """Followers + every post since `since`, with its figures (missing metrics are skipped)."""
    from .instagram import Instagram
    I = Instagram(sec)
    me = I._get(I.uid, fields="followers_count")
    out, after = [], None
    for _ in range(5):
        kw = {"fields": "id,media_type,media_product_type,permalink,timestamp,caption,like_count,comments_count",
              "limit": 50}
        if after:
            kw["after"] = after
        page = I._get(f"{I.uid}/media", **kw)
        stop = False
        for m in page.get("data", []):
            ts = datetime.fromisoformat(m["timestamp"].replace("+0000", "+00:00"))
            if ts < since:
                stop = True
                continue
            row = {"ts": ts.isoformat(), "type": m.get("media_product_type") or m.get("media_type"),
                   "kind": m.get("media_type"), "link": m.get("permalink", ""),
                   "caption": re.sub(r"\s+", " ", m.get("caption") or "")[:90],
                   "likes": m.get("like_count"), "comments": m.get("comments_count")}
            for metric in ("views", "reach", "saved", "shares"):
                try:
                    d = I._get(f"{m['id']}/insights", metric=metric).get("data") or []
                    row[metric] = int(((d[0].get("values") or [{}])[0]).get("value") or 0) if d else None
                except Exception:  # noqa: BLE001
                    row[metric] = None
            out.append(row)
        after = ((page.get("paging") or {}).get("cursors") or {}).get("after")
        if stop or not (page.get("paging") or {}).get("next"):
            break
    return int(me.get("followers_count") or 0), out


# ---------------------------------------------------------------- state
class State:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "insights" / "state.json"
        try:
            self.data = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {}
        self.data.setdefault("episodes", {})
        self.data.setdefault("snapshots", [])

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))

    def last(self) -> dict:
        return self.data["snapshots"][-1] if self.data["snapshots"] else {}


# ---------------------------------------------------------------- episode pages
def timed(lines: list) -> str:
    return "\n".join(f"[{mmss(s)}] {t}" for s, t in lines or [])


def clean_md(text: str) -> str:
    """The model's markdown as ClickUp keeps it: no code fence, no HTML / XML tag, no front-matter rule on top."""
    t = re.sub(r"^```\w*\s*|```\s*$", "", (text or "").strip())
    t = re.sub(r"</?[A-Za-z][\w-]*(\s[^>]*)?>", "", t)
    t = re.sub(r"^(---+\s*\n)+", "", t.strip())
    return t.strip()


def pieces(text: str, size: int = 8000) -> list[str]:
    """Text cut at line ends into pieces of at most `size` characters (a line longer than that is cut)."""
    out, cur = [], ""
    for line in text.split("\n"):
        while len(line) > size:
            if cur:
                out.append(cur)
                cur = ""
            out.append(line[:size])
            line = line[size:]
        if cur and len(cur) + 1 + len(line) > size:
            out.append(cur)
            cur = line
        else:
            cur = f"{cur}\n{line}" if cur else line
    if cur:
        out.append(cur)
    return out


def episode_pages(st: State, docs: Docs, digest, episodes: list[dict], trans: dict, local=None,
                  limit: int = 20, save_dir: Path | None = None) -> list[str]:
    """One page per episode (oldest first): header + digest, the transcript in sub-pages. A page whose digest is
    missing (st.data["digested"]) gets it written again. digest(title, date, transcript_text) → markdown;
    local(vid) → [[s, text]] from the bot's own SRT, or None."""
    made = []
    done = st.data.setdefault("digested", [])
    for e in sorted(episodes, key=lambda e: e.get("publishedAt") or ""):
        vid = e["id"]
        if (vid in st.data["episodes"] and vid in done) or len(made) >= limit:
            continue
        lines = trans.get(vid) or (local(vid) if local else None)
        if not lines:
            continue
        date = (e.get("publishedAt") or "")[:10]
        text = timed(lines)
        body = clean_md(digest(e.get("title", ""), date, text))
        if save_dir:
            save_dir.mkdir(parents=True, exist_ok=True)
            (save_dir / f"{vid}.md").write_text(body)
        log.info("insights digest %s: %d chars, starts %r", vid, len(body), body[:120])
        head = (f"**{e.get('title', '')}**\n\nSorti le {date} · https://youtu.be/{vid} · {e.get('views', '—')} vues au "
                f"{datetime.now(TZ).strftime('%d.%m.%Y')}\n")
        page = st.data["episodes"].get(vid)
        if not page:
            page = docs.create(f"{date} · {short_title(e.get('title', ''))}", head, PAGES["episodes"])
            chunks = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)] or [""]
            for i, c in enumerate(chunks, 1):
                docs.create("Transcript" + (f" ({i}/{len(chunks)})" if len(chunks) > 1 else ""), c, page)
            st.data["episodes"][vid] = page
            st.save()
        else:
            docs.update(page, head)
        for piece in pieces(body):                             # the digest in pieces, after the header
            docs.update(page, "\n" + piece, mode="append")
        if vid not in done:
            done.append(vid)
        st.save()
        made.append(e.get("title", vid))
    return made


def short_title(t: str) -> str:
    """« Why She Walked Away… | Break the Routine with Oti Mabuse (PART 2) » → « Oti Mabuse (PART 2) »."""
    m = re.search(r"Break the Routine with ([^|]+)", t or "", re.I)
    return (m.group(1) if m else (t or "")).strip()[:80]


# ---------------------------------------------------------------- weekly stats
def snapshot(yt_json: dict, base: dict, ig: tuple | None, tt: dict | None, now: datetime) -> dict:
    snap = {"at": now.isoformat(),
            "yt": {"subscribers": yt_json.get("subscribers"), "channelViews": yt_json.get("channelViews"),
                   "episodes": {e["id"]: e.get("views") for e in yt_json.get("episodes") or []}},
            "spotify": (base or {}).get("spotify") or {}}
    if ig:
        snap["ig"] = {"followers": ig[0]}
    if tt:
        snap["tt"] = {"followers": tt.get("followers"), "likes": tt.get("likes")}
    return snap


def week_block(start: datetime, end: datetime, now: datetime, snap: dict, prev: dict, yt_json: dict,
               ig_posts: list[dict] | None, tt: dict | None, an: dict | None, trans: dict) -> str:
    """The markdown block of one week. an = YouTube Analytics results ({"week": {vid: row}, "life": {vid: row},
    "meta": {vid: {title, seconds}}, "retention": {vid: curve}}) or None."""
    last_day = end - timedelta(days=1)
    out = [f"## Semaine du {day_label(start)} au {day_label(last_day)} {start.year}",
           f"*Relevé le {day_label(now)} à {now.astimezone(TZ).strftime('%H:%M')} (Londres).*"]
    eps = sorted(yt_json.get("episodes") or [], key=lambda e: e.get("publishedAt") or "")
    new = [e for e in eps if start.isoformat()[:10] <= (e.get("publishedAt") or "")[:10] <= now.isoformat()[:10]]
    if new:
        out.append("Épisode(s) sorti(s) : " + ", ".join(f"{short_title(e['title'])} le {e['publishedAt'][:10]}" for e in new))
    p = prev or {}
    since = (f"Depuis le {day_label(datetime.fromisoformat(p['at']))}" if p.get("at") else "Évolution")
    rows = [["Instagram", (snap.get("ig") or {}).get("followers", "—"),
             delta((snap.get("ig") or {}).get("followers"), (p.get("ig") or {}).get("followers"))],
            ["TikTok", (snap.get("tt") or {}).get("followers", "—"),
             delta((snap.get("tt") or {}).get("followers"), (p.get("tt") or {}).get("followers"))],
            ["YouTube", snap["yt"].get("subscribers", "—"),
             delta(snap["yt"].get("subscribers"), (p.get("yt") or {}).get("subscribers"))],
            ["Spotify (à la main)", (snap.get("spotify") or {}).get("followers", "—"),
             f"relevé du {(snap.get('spotify') or {}).get('asOf', '—')}"]]
    out += ["", "### Abonnés", table(["Plateforme", "Total", since], rows)]
    if ig_posts is not None:
        rows = []
        for m in sorted(ig_posts, key=lambda m: m["ts"]):
            ts = datetime.fromisoformat(m["ts"])
            if ts < start:
                continue
            typ = {"REELS": "Reel", "FEED": "Carrousel" if m.get("kind") == "CAROUSEL_ALBUM" else "Image",
                   "STORY": "Story"}.get(m.get("type"), m.get("type") or "")
            rows.append([day_label(ts) + (" (nouvelle sem.)" if ts >= end else ""), typ, m["caption"][:60] or m["link"],
                         m.get("views", "—"), m.get("reach", "—"), m.get("likes", "—"), m.get("comments", "—"),
                         m.get("saved", "—"), m.get("shares", "—")])
        out += ["", "### Instagram : posts de la semaine",
                table(["Jour", "Type", "Post", "Vues", "Portée", "Likes", "Comm.", "Enreg.", "Partages"], rows)
                if rows else "Aucun post."]
    if tt:
        rows = [[f"{v[0][6:8]}.{v[0][4:6]}", v[1], v[2]] for v in tt.get("videos") or []
                if start.strftime("%Y%m%d") <= v[0] <= now.astimezone(TZ).strftime("%Y%m%d")]
        out += ["", f"### TikTok : posts de la semaine (likes au total : {tt.get('likes', '—')})",
                table(["Jour", "Vidéo", "Vues"], rows) if rows else "Aucun post."]
    pe = (p.get("yt") or {}).get("episodes") or {}
    life = (an or {}).get("life") or {}
    rows = []
    for e in reversed(eps):
        a = life.get(e["id"]) or {}
        rows.append([short_title(e["title"]), e["publishedAt"][:10], e.get("views", "—"),
                     delta(e.get("views"), pe.get(e["id"])),
                     f"{a['averageViewPercentage']:.0f} %" if a.get("averageViewPercentage") is not None else "—",
                     mmss(a["averageViewDuration"]) if a.get("averageViewDuration") is not None else "—"])
    out += ["", f"### YouTube : épisodes complets (chaîne : {snap['yt'].get('channelViews', '—')} vues au total)",
            table(["Épisode", "Sortie", "Vues", since, "% regardé moyen", "Durée moyenne"], rows)]
    if an:
        meta = an.get("meta") or {}
        ep_ids = {e["id"] for e in eps}
        rows = [[meta.get(v, {}).get("title", v)[:60], r.get("views"), f"{r.get('averageViewPercentage', 0):.0f} %",
                 r.get("subscribersGained", 0)]
                for v, r in (an.get("week") or {}).items() if v not in ep_ids][:15]
        out += ["", "### YouTube : Shorts et autres vidéos (vues de la semaine)",
                table(["Vidéo", "Vues", "% regardé", "Abonnés gagnés"], rows) if rows else "Rien cette semaine."]
        for vid, curve in (an.get("retention") or {}).items():
            if not curve:
                continue
            secs = (meta.get(vid) or {}).get("seconds") or 0
            name = short_title((meta.get(vid) or {}).get("title", vid))
            keep = ", ".join(f"{int(x * 100)} % de la vidéo : {s * 100:.0f} % des spectateurs"
                             for x in (0.25, 0.5, 0.75) for s in [at_share(curve, x)] if s is not None)
            out += ["", f"#### Rétention · {name}", keep or "—"]
            for x, lost in drops(curve):
                t = x * secs
                out.append(f"- chute à {mmss(t)} ({lost * 100:.1f} pts) : « {said_at(trans.get(vid), t)} »")
    else:
        out += ["", "*YouTube Analytics pas encore connecté : pas de rétention ni de Shorts (lien dans /connect).*"]
    return "\n".join(out) + "\n\n---\n"

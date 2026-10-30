"""YouTube Shorts of the filed reels: when each one goes out (pure planning, no network).

Every filed reel becomes a Short, uploaded private with a publishAt: YouTube makes it public by itself at that time.
The time comes from (first match): Loïc's own choice (item["short_at"]), the ClickUp task's due date (at HOUR when
it has no time), the time already scheduled, else the next day without a Short (one per day, from tomorrow).
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/London")       # BTR's audience is mostly in the UK
HOUR = (18, 0)                       # time of day when the date has no time
LEAD = timedelta(minutes=30)         # sooner than this is too soon (upload + processing)
DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(v) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except ValueError:
        return None


def label(dt: datetime) -> str:
    d = dt.astimezone(TZ)
    return f"{DAYS[d.weekday()]} {d.strftime('%d.%m %H:%M')}"


def due_at(task: dict | None, now: datetime) -> datetime | None:
    """The ClickUp task's due date as a publishing time (London), None if there is none or it is already past."""
    due = (task or {}).get("due_date")
    if not due:
        return None
    try:
        d = datetime.fromtimestamp(int(due) / 1000, TZ)
    except (TypeError, ValueError):
        return None
    if not task.get("due_date_time"):
        d = d.replace(hour=HOUR[0], minute=HOUR[1], second=0, microsecond=0)
    return d if d >= now + LEAD else None


def parse_choice(text: str, now: datetime) -> datetime:
    """« 2026-11-04 19:00 », « 2026-11-04 », « 4.11 19h », « 04/11 » → London time. ValueError if unreadable or too soon."""
    import re
    t = (text or "").strip().lower()
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", t)
    year_given = bool(m)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    else:
        m = re.match(r"(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?", t)
        if not m:
            raise ValueError(f"date illisible : {text}")
        d, mo = int(m.group(1)), int(m.group(2))
        year_given = bool(m.group(3))
        y = int(m.group(3)) if m.group(3) else now.astimezone(TZ).year
        y += 2000 if y < 100 else 0
    rest = t[m.end():]
    h = re.search(r"(\d{1,2})\s*(?:h|:)\s*(\d{2})?", rest)
    hh, mm = (int(h.group(1)), int(h.group(2) or 0)) if h else HOUR
    dt = datetime(y, mo, d, hh, mm, tzinfo=TZ)
    if not year_given and dt < now - timedelta(days=60):     # « 4.01 » in December = next year
        dt = dt.replace(year=y + 1)
    if dt < now + LEAD:
        raise ValueError(f"{label(dt)} est déjà passé (ou dans moins de 30 min)")
    return dt


def plan(entries: list[dict], now: datetime) -> list[dict]:
    """entries: {key, vid (YouTube id if already sent), cur_at, task_at, chosen}, in publishing order.
    Returns them with at, why and action ("upload" | "move" | None)."""
    out, busy = [], set()
    for e in entries:
        cur = e.get("cur_at")
        if e.get("chosen"):
            at, why = e["chosen"], "ton choix"
        elif e.get("task_at"):
            at, why = e["task_at"], "date ClickUp"
        elif cur and cur >= now + LEAD:
            at, why = cur, "déjà programmé"
        else:
            at, why = None, ""
        out.append(dict(e, at=at, why=why))
        if at:
            busy.add(at.astimezone(TZ).date())
    day = (now.astimezone(TZ) + timedelta(days=1)).date()
    for p in out:
        if p["at"] is None:
            while day in busy:
                day += timedelta(days=1)
            p["at"], p["why"] = datetime(day.year, day.month, day.day, *HOUR, tzinfo=TZ), "jour libre"
            busy.add(day)
    for p in out:
        cur = p.get("cur_at")
        if not p.get("vid"):
            p["action"] = "upload"
        elif cur is None or abs((p["at"] - cur).total_seconds()) > 60:
            p["action"] = "move"
        else:
            p["action"] = None
    return out

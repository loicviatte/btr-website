"""« ✅ À valider » topic (Loïc 01.11.2026): ONE message per episode, edited in place, listing everything of the episode
(miniatures, reels + covers, carousels + stories) with its state; a quick tap shows the item in its own topic (link to
the preview message, or the bot sends it again). What is published is locked (🟢, no button, edits refused).
Pure: builds the text and the buttons from the episode state; bot.dash_tick sends / edits the messages."""
import html
import re
from datetime import datetime, timedelta

from . import posts

WAIT, OK, PLAN, LIVE, WORK, TODO = "⏳", "✅", "📅", "🟢", "🔄", "⬜"


def esc(s) -> str:
    return html.escape(str(s or ""), quote=False)


def msg_link(ref) -> str | None:
    """[chat_id, message_id] of a message in the BTR Studio group → its t.me link (opens it in its topic)."""
    try:
        chat, mid = ref
    except (TypeError, ValueError):
        return None
    s = str(chat)
    return f"https://t.me/c/{s[4:]}/{mid}" if s.startswith("-100") and mid else None


def when(at: str | None) -> str:
    try:
        return posts.label_time(datetime.fromisoformat(at)) if at else ""
    except ValueError:
        return ""


def reel_locked(it: dict) -> bool:
    """A reel already out somewhere (YouTube Short public or Instagram posted) is never changed again."""
    return bool((it.get("yt_short") or {}).get("posted") or (it.get("ig_post") or {}).get("posted"))


def post_locked(it: dict) -> bool:
    return it.get("status") == "posted" or bool((it.get("ig") or {}).get("done"))


def thumbs_line(ep, code: str) -> tuple[str, str, str | None]:
    """The episode's YouTube title / thumbnails / chapters."""
    stage = ep.stage
    cmd = f"/{code}_miniatures" if ep.get("thumb_msgs") else None
    if stage in ("new", "waiting_transcript"):
        return WORK, "Miniatures : en attente de la transcription", None
    if stage in ("axes_proposed", "frames_proposed"):
        return WAIT, "Miniatures : titre / photo à choisir", None
    if stage == "thumbs_proposed":
        return WAIT, "Miniatures à valider", cmd
    if stage in ("published", "chapters_proposed"):
        return WAIT, "Miniatures publiées · chapitres à valider", None
    if stage == "done":
        return LIVE, "Miniatures + chapitres publiés", None
    return WORK, f"Miniatures : {stage}", None


def reel_line(code: str, n: int, it: dict, title: str, task: dict | None = None) -> tuple[str, str, str | None]:
    name = f"Reel {n} · {title}" if title else f"Reel {n}"
    st = it.get("status")
    ys, ig = it.get("yt_short") or {}, it.get("ig_post") or {}
    cmd = f"/{code}_reel{n}"
    if reel_locked(it) or ((task or {}).get("status") or "").lower() == "posted":
        where = ", ".join(x for x, ok in (("Short", ys.get("posted")), ("Instagram", ig.get("posted")),
                                          ("TikTok", (it.get("tt_post") or {}).get("posted"))) if ok)
        return LIVE, f"{name} — publié" + (f" ({where})" if where else ""), None
    if st in ("queued", "rendering"):
        return WORK, f"{name} — en montage", None
    if st == "preview":
        return WAIT, f"{name} — à valider", cmd
    if st == "ok" and not it.get("filed"):
        return WAIT, f"{name} — validé, à ranger (feed ?)", cmd
    if it.get("filed") and not it.get("cover_ok"):
        return WAIT, f"{name} — cover à valider", cmd
    if ys.get("id") and not ys.get("posted"):
        return PLAN, f"{name} — {when(ys.get('at')) or 'programmé'}", cmd
    if it.get("cover_ok"):
        return OK, f"{name} — cover validée", cmd
    return WORK, f"{name} — {st or 'en attente'}", None


def post_line(code: str, k: str, it: dict, task: dict | None) -> tuple[str, str, str | None]:
    """A carousel / story of the episode: the bot's item and/or its ClickUp task (the task's status wins once posted,
    a post made by hand counts too)."""
    name = posts.LABEL.get(it.get("kind", k) if it else k, k).replace("Carrousel ", "")
    cmd = f"/{code}_{k}"
    tstat = ((task or {}).get("status") or "").lower()
    if post_locked(it or {}) or tstat == "posted":
        lk = ((it or {}).get("ig") or {}).get("link")
        return LIVE, f"{name} — publié" + (f" ({lk})" if lk else ""), None
    if it and it.get("skip"):
        return WORK, f"{name} — pas fait ({it['skip']})", None
    if it and it.get("status") == "ok":
        return PLAN, f"{name} — {when(it.get('at')) or 'validé, sans date'}", cmd
    if it and it.get("status") == "draft":
        return WAIT, f"{name} — à valider", cmd
    if tstat in ("scheduled", "ready"):
        return PLAN, f"{name} — {when((task or {}).get('due_iso')) or 'programmé'} (ClickUp)", None
    if tstat == "approved":
        return OK, f"{name} — validé (ClickUp)", None
    if tstat == "generated":
        return WAIT, f"{name} — fait à la main, à valider dans ClickUp", None
    if tstat == "to generate":
        return TODO, f"{name} — à générer", f"/{code}_faire_{k}"
    return WORK, f"{name} — en préparation", None


def render(ep, code: str, title: str, reels: dict | None, reel_titles: dict, post_items: dict,
           tasks: dict | None = None) -> tuple[str, int]:
    """→ (HTML text with tappable /commands like BotFather, number of things waiting for Loïc). tasks = the
    episode's ClickUp tasks by kind (moment, topics, poll…) and by reel number ("reel3")."""
    tasks = tasks or {}
    lines, waiting = [], 0

    def add(icon, text, cmd):
        nonlocal waiting
        lines.append(f"{icon} {esc(text)}" + (f"  {cmd}" if cmd else ""))
        waiting += icon == WAIT
    if ep.stage != "new" or ep.get("thumb_msgs"):
        lines.append("\n<b>🖼️ Miniatures</b>")
        add(*thumbs_line(ep, code))
    items = [(int(n), it) for n, it in ((reels or {}).get("items") or {}).items() if it.get("status") != "dropped"]
    if items:
        lines.append("\n<b>🎬 Reels</b>")
        for n, it in sorted(items):
            add(*reel_line(code, n, it, reel_titles.get(n, ""), tasks.get(f"reel{n}")))
    kinds = list(dict.fromkeys([k for k in posts.LABEL if k in tasks] + list(post_items)))
    if kinds:
        lines.append("\n<b>📚 Carrousels & stories</b>")
        order = list(posts.LABEL)
        for k in sorted(kinds, key=lambda x: order.index(x) if x in order else 99):
            add(*post_line(code, k, post_items.get(k) or {"kind": k}, tasks.get(k)))
    head = (f"<b>{esc(title)}</b>\n" + (f"{WAIT} <b>{waiting} à valider</b>" if waiting else f"{OK} Rien à valider"))
    foot = "\n\n<i>Tape une commande : l'élément arrive dans son fil, avec ses boutons pour valider ou modifier.</i>"
    return head + "\n" + "\n".join(lines) + foot, waiting


def episode_code(guest: str, part: str | None, taken: dict, vid: str) -> str:
    """oti2, kiera, peter1… : the short name in the /commands (unique per episode)."""
    import re
    import unicodedata
    first = unicodedata.normalize("NFKD", (guest or "ep").split()[0]).encode("ascii", "ignore").decode().lower()
    code = (re.sub(r"[^a-z]", "", first) or "ep")[:12] + (str(part) if part else "")
    while taken.get(code) not in (None, vid):
        code += vid[-1].lower() if vid[-1].isalnum() else "x"
    return code


# ── « 🗓️ Posts planning » : the overview on top (Loïc 01.11.2026) ─────────────────────────────────────────────────
DONE = ("posted", "complete", "completed", "closed", "done")
PLAN_ICON = {"to generate": TODO, "generated": WAIT, "approved": OK, "ready": PLAN, "scheduled": PLAN}


def ig_kind(name: str) -> str | None:
    """What a calendar task is: atlas / carousel / story / reel / short / community / other (every platform)."""
    n = (name or "").strip().lower()
    if not n:
        return None
    if re.match(r"car+ousel\s+·\s+world atlas", n):
        return "atlas"
    if n.startswith(("carousel", "carrousel")):
        return "carousel"
    if n.startswith("story"):
        return "story"
    if n.startswith("reel"):
        return "reel"
    if n.startswith("short"):
        return "short"
    if "community" in n.split("·")[0]:
        return "community"
    return "other"


PLATFORM = {"atlas": "📸", "carousel": "📸", "story": "📸", "reel": "📸", "short": "▶️", "community": "▶️", "other": "•"}


def short_name(name: str, kind: str) -> str:
    """« Reel 3/3 · Oti Mabuse P2 · Her One Question » → « Reel 3/3 · Her One Question »; « Carousel · World Atlas 04
    Namibia · catch-up » → « Atlas 04 Namibia »; « Story · The Chain · Oti P2 » → « Story The Chain »; « YouTube
    Community · Poll · Ep Nov 3 » → « Community · Poll »."""
    parts = [p.strip() for p in re.split(r"\s+·\s+", name or "") if p.strip()]
    if kind == "atlas":
        return re.sub(r"(?i)^world atlas", "Atlas", parts[1] if len(parts) > 1 else name)
    if kind in ("reel", "short"):
        return " · ".join([parts[0]] + parts[2:]) if len(parts) > 2 else parts[0]
    if kind == "community":
        return f"Community · {parts[1]}" if len(parts) > 1 else "Community"
    if kind in ("carousel", "story"):
        head = {"carousel": "Carrousel", "story": "Story"}[kind]
        return f"{head} {parts[1]}" if len(parts) > 1 else head
    return name


def planning_overview(title: str | None, mine: list[dict], atlas: list[dict], now: datetime,
                      week: tuple | None = None) -> str:
    """mine / atlas: [{"name", "status", "at" (datetime|None)}], not posted. → the HTML message, grouped by day.
    week = (Tuesday, next Tuesday): the header says which week."""
    days = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
    rows = [(r, ig_kind(r["name"]) or "carousel") for r in mine + atlas]
    rows.sort(key=lambda x: (x[0].get("at") is None, x[0].get("at") or now))
    n = len(rows)
    if week:
        a, b = week[0].astimezone(posts.TZ), (week[1] - timedelta(days=1)).astimezone(posts.TZ)
        head = f"<b>🗓️ Semaine du {days[a.weekday()]} {a.strftime('%d.%m')} au {days[b.weekday()]} {b.strftime('%d.%m')}</b>\n"
        if title:
            head += f"Épisode : {esc(title)}\n"
    else:
        head = f"<b>🗓️ {esc(title or 'Épisode en cours')}</b>\n"
    head += (f"{n} post{'s' if n > 1 else ''} restant{'s' if n > 1 else ''}" if n else f"{OK} Tout est publié")
    if atlas:
        head += f" (dont {len(atlas)} Atlas)"
    lines, day = [], None
    for r, kind in rows:
        at = r.get("at")
        d = at.astimezone(posts.TZ) if at else None
        key = d.date() if d else "?"
        if key != day:
            day = key
            lines.append("\n<b>" + (f"{days[d.weekday()]} {d.strftime('%d.%m')}" if d else "Sans date") + "</b>")
        miss = r.get("missing") or []
        late = (" ⚠️ en retard" + (f" ({', '.join(miss)})" if miss else "")) if at and at < now else ""
        icon = PLAN_ICON.get((r.get("status") or "").lower(), WORK)
        hour = d.strftime("%H:%M") + " " if d else ""
        done = f"  /fait_{r['id']}" if late and r.get("id") and re.fullmatch(r"[a-z0-9]+", r["id"]) else ""
        lines.append(f"{icon} {hour}{PLATFORM.get(kind, '•')} {'🌍 ' if kind == 'atlas' else ''}"
                     f"{esc(short_name(r['name'], kind))}{late}{done}")
    legend = (f"\n\n<i>{TODO} à générer · {WAIT} à valider · {OK} validé · {PLAN} programmé · 📸 Instagram (+ TikTok) · "
              "▶️ YouTube</i>")
    if any(r.get("at") and r["at"] < now for r, _ in rows):
        legend += "\n<i>Déjà publié à la main ? Tape /fait_… sur sa ligne : la tâche passe en « posted ».</i>"
    foot = ("\n<i>Écris ta demande ici (changer un type, une date, ajouter, retirer) : la conversation s'efface une fois "
            "faite, ce message se met à jour.</i>")
    body = "\n".join(lines)
    if len(head + body + legend + foot) > 4000:
        body = body[:4000 - len(head + legend + foot) - 30].rsplit("\n", 1)[0] + "\n…"
    return head + "\n" + body + legend + foot

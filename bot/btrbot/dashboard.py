"""« ✅ À valider » topic (Loïc 01.11.2026): ONE message per episode, edited in place, listing everything of the episode
(miniatures, reels + covers, carousels + stories) with its state; a quick tap shows the item in its own topic (link to
the preview message, or the bot sends it again). What is published is locked (🟢, no button, edits refused).
Pure: builds the text and the buttons from the episode state; bot.dash_tick sends / edits the messages."""
import html
from datetime import datetime

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

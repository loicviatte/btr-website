"""« ✅ À valider » topic (Loïc 01.11.2026): ONE message per episode, edited in place, listing everything of the episode
(miniatures, reels + covers, carousels + stories) with its state; a quick tap shows the item in its own topic (link to
the preview message, or the bot sends it again). What is published is locked (🟢, no button, edits refused).
Pure: builds the text and the buttons from the episode state; bot.dash_tick sends / edits the messages."""
import html
from datetime import datetime

from . import posts

WAIT, OK, PLAN, LIVE, WORK = "⏳", "✅", "📅", "🟢", "🔄"


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


def thumbs_line(ep) -> tuple[str, str, dict | None]:
    """(icon, text, button) for the episode's YouTube title / thumbnails / chapters."""
    stage = ep.stage
    link = None
    msgs = ep.get("thumb_msgs") or {}
    if msgs:
        link = msg_link([ep.get("thumb_chat"), list(msgs.values())[-1]]) if ep.get("thumb_chat") else None
    if stage in ("new", "waiting_transcript"):
        return WORK, "Miniatures : en attente de la transcription", None
    if stage in ("axes_proposed", "frames_proposed"):
        return WAIT, "Miniatures : titre / photo à choisir", {"text": "⏳ Miniatures", "url": link} if link else None
    if stage == "thumbs_proposed":
        return WAIT, "Miniatures à valider", {"text": "⏳ Miniatures", "url": link} if link else None
    if stage in ("published", "chapters_proposed"):
        return WAIT, "Miniatures publiées · chapitres à valider", None
    if stage == "done":
        return LIVE, "Miniatures + chapitres publiés", None
    return WORK, f"Miniatures : {stage}", None


def reel_line(vid: str, n: int, it: dict, title: str) -> tuple[str, str, dict | None]:
    name = f"Reel {n} · {title}" if title else f"Reel {n}"
    st = it.get("status")
    ys, ig = it.get("yt_short") or {}, it.get("ig_post") or {}
    tap = {"text": f"Reel {n}", "callback_data": f"dash:r:{vid}:{n}"}
    if reel_locked(it):
        where = ", ".join(x for x, ok in (("Short", ys.get("posted")), ("Instagram", ig.get("posted")),
                                          ("TikTok", (it.get("tt_post") or {}).get("posted"))) if ok)
        return LIVE, f"{name} — publié ({where})", None
    if st in ("queued", "rendering"):
        return WORK, f"{name} — en montage", None
    if st == "preview":
        return WAIT, f"{name} — à valider", dict(tap, text=f"⏳ Reel {n}")
    if st == "ok" and not it.get("filed"):
        return WAIT, f"{name} — validé, à ranger (feed ?)", dict(tap, text=f"⏳ Reel {n}")
    if it.get("filed") and not it.get("cover_ok"):
        return WAIT, f"{name} — cover à valider", dict(tap, text=f"⏳ Cover {n}")
    if ys.get("id") and not ys.get("posted"):
        return PLAN, f"{name} — {when(ys.get('at')) or 'programmé'}", dict(tap, text=f"📅 Reel {n}")
    if it.get("cover_ok"):
        return OK, f"{name} — cover validée", dict(tap, text=f"✅ Reel {n}")
    return WORK, f"{name} — {st or 'en attente'}", None


def post_line(vid: str, k: str, it: dict) -> tuple[str, str, dict | None]:
    name = posts.LABEL.get(it.get("kind", k), k).replace("Carrousel ", "").replace("Story ", "Story ")
    link = msg_link(it.get("msg"))
    tap = ({"url": link} if link else {"callback_data": f"dash:p:{vid}:{k}"})
    if post_locked(it):
        lk = (it.get("ig") or {}).get("link")
        return LIVE, f"{name} — publié" + (f" ({lk})" if lk else ""), None
    if it.get("skip"):
        return WORK, f"{name} — pas fait ({it['skip']})", None
    if it.get("status") == "draft":
        return WAIT, f"{name} — à valider", dict(tap, text=f"⏳ {name}")
    if it.get("status") == "ok":
        return PLAN, f"{name} — {when(it.get('at')) or 'validé, sans date'}", dict(tap, text=f"📅 {name}")
    return WORK, f"{name} — en préparation", None


def render(ep, title: str, reels: dict | None, reel_titles: dict, post_items: dict) -> tuple[str, list[list[dict]], int]:
    """→ (HTML text, keyboard rows of {text, url | callback_data}, number of things waiting for Loïc)."""
    vid = ep.video_id
    lines, buttons, waiting = [], [], 0

    def add(icon, text, btn):
        nonlocal waiting
        lines.append(f"{icon} {esc(text)}")
        waiting += icon == WAIT
        if btn:
            buttons.append(btn)
    if ep.stage != "new" or ep.get("thumb_msgs"):
        lines.append("<b>🖼️ Miniatures</b>")
        add(*thumbs_line(ep))
    items = [(int(n), it) for n, it in ((reels or {}).get("items") or {}).items() if it.get("status") != "dropped"]
    if items:
        lines.append("<b>🎬 Reels</b>")
        for n, it in sorted(items):
            add(*reel_line(vid, n, it, reel_titles.get(n, "")))
    if post_items:
        lines.append("<b>📚 Carrousels & stories</b>")
        order = list(posts.LABEL)
        for k, it in sorted(post_items.items(), key=lambda kv: order.index(kv[1].get("kind", kv[0]))
                            if kv[1].get("kind", kv[0]) in order else 99):
            add(*post_line(vid, k, it))
    head = (f"<b>{esc(title)}</b>\n" + (f"{WAIT} <b>{waiting} à valider</b>" if waiting else f"{OK} Rien à valider"))
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    return head + "\n\n" + "\n".join(lines), rows, waiting

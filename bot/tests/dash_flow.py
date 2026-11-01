"""Offline check of the « À valider » topic (dashboard.py + bot.dash_tick).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/dash_flow.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import dashboard, posts  # noqa: E402
from btrbot.state import Reels  # noqa: E402

bot.cfg.chat_id = 42
bot.TOPICS.group, bot.TOPICS.threads = -100555, {"dash": 9, "reels": 1, "stories": 3}
ep = bot.reg.episode("VIDDASH0001")
ep["guest_name"] = "Oti Mabuse"
ep["part"] = "2"
ep.stage = "done"
ep.save()
rs = Reels.of(ep)
rs.data = {"cands": [{"n": i, "title": f"T{i}"} for i in (1, 2, 3, 4)], "items": {
    "1": {"status": "ok", "filed": True, "cover_ok": True, "yt_short": {"id": "Y", "posted": True}, "ig_post": {"posted": True}},
    "2": {"status": "ok", "filed": True, "cover_ok": False, "cover": "c.jpg"},
    "3": {"status": "preview", "file": "r.mp4"},
    "4": {"status": "dropped"}}}
rs.save()
st = posts.PostState(ep)
st.data["items"] = {"topics": {"kind": "topics", "status": "draft", "msg": [-100555, 77]},
                    "poll": {"kind": "poll", "status": "ok", "at": "2026-11-04T19:00:00+00:00"},
                    "moment": {"kind": "moment", "status": "posted", "ig": {"done": True, "link": "https://instagram.com/p/x"}}}
st.save()
text, kb = bot.dash_content(ep)
assert "Oti Mabuse · Part 2" in text and "3 à valider" in text, text
assert "Reel 4" not in text and "🟢 Reel 1" in text and "⏳ Reel 2" in text and "cover à valider" in text
assert "🟢 Key moment" in text and "📅 Story Poll" in text and "mer. 04.11 19:00" in text
labels = [b.text for row in kb.inline_keyboard for b in row]
assert "⏳ Topics" in labels and not any("Reel 1" in x for x in labels) and not any("Key moment" in x for x in labels)
topics_btn = [b for row in kb.inline_keyboard for b in row if b.text == "⏳ Topics"][0]
assert topics_btn.url == "https://t.me/c/555/77"
assert dashboard.reel_locked(rs.data["items"]["1"]) and not dashboard.reel_locked(rs.data["items"]["2"])
print("OK render")

sent, edits = [], []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append(text)
        return NS(message_id=500 + len(sent), chat_id=chat)

    async def edit_message_text(self, text, chat_id=None, message_id=None, **kw):
        edits.append((chat_id, message_id))


ctx = NS(bot=FakeBot())


async def main():
    await bot.dash_tick(ctx)
    assert len(sent) == 1 and not edits
    await bot.dash_tick(ctx)                             # nothing changed: nothing sent or edited
    assert len(sent) == 1 and not edits
    s2 = posts.PostState(ep)
    s2.items["topics"]["status"] = "ok"
    s2.save()
    await bot.dash_tick(ctx)
    assert edits == [(-100555, 501)] and len(sent) == 1, (edits, sent)
    # a locked post refuses edits
    s3 = posts.PostState(ep)
    msgs = []

    async def say(c, t, **kw):
        msgs.append(t)
    bot.say = say
    await bot.on_post_button(ctx, NS(), f"pst:tx:{ep.video_id}:moment")
    assert "déjà publié" in msgs[-1]
    print("OK tick")

asyncio.run(main())

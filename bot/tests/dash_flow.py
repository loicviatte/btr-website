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
bot.CU_CACHE.update(at=9e18, tasks=[
    {"id": "K", "name": "Carousel · Key moment · Oti P2", "status": {"status": "posted"}, "custom_fields": []},
    {"id": "S", "name": "Story · Ask the next guest · Oti P2", "status": {"status": "to generate"}, "custom_fields": []},
    {"id": "T", "name": "Carousel · Topics · Oti P2", "status": {"status": "generated"}, "custom_fields": []},
    {"id": "P", "name": "Story · Poll · Oti P2", "status": {"status": "to generate"}, "custom_fields": []}])
s0 = posts.PostState(ep)
s0.items["quote"] = {"kind": "quote", "status": "ok"}          # made outside the calendar (trial): hidden
s0.save()
text, kb = bot.dash_content(ep)
assert kb is None and "Oti Mabuse · Part 2" in text and "3 à valider" in text, text
assert "Reel 4" not in text and "🟢 Reel 1" in text and "⏳ Reel 2" in text and "cover à valider" in text
assert "/oti2_reel2" in text and "/oti2_reel1" not in text and "/oti2_topics" in text
assert "🟢 Key moment" in text and "/oti2_moment" not in text                       # posted (bot or ClickUp) = locked
assert "📅 Story Poll" in text and "mer. 04.11 19:00" in text
assert "⬜ Story Ask the next guest — à générer" in text and "/oti2_faire_ask" in text, text
assert "Citation" not in text, text
assert dashboard.reel_locked(rs.data["items"]["1"]) and not dashboard.reel_locked(rs.data["items"]["2"])
assert dashboard.episode_code("Oti Mabuse", "2", {}, "x") == "oti2" and dashboard.episode_code("Zoë Ball", None, {"zoe": "a"}, "b1") == "zoe1"
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
    bot.pipe.yt.video = lambda vid: {"status": {}, "snippet": {"publishedAt": "2026-10-27T18:00:00Z"}}
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

# a tapped command shows the item in its topic (and is deleted from « À valider »)
shown = []


async def fake_btn(c, d):
    shown.append(d)


async def cmd():
    bot.on_dash_button = fake_btn
    deleted = []

    class B2(FakeBot):
        async def delete_message(self, chat, mid):
            deleted.append(mid)
    up = NS(message=NS(text="/oti2_reel2@BTRStudioBot", message_id=9), effective_chat=NS(id=-100555), effective_user=NS(id=42))
    await bot.on_dash_cmd(up, NS(bot=B2()))
    assert shown == [f"dash:r:{ep.video_id}:2"] and deleted == [9], (shown, deleted)
    print("OK command")

asyncio.run(cmd())

# « À valider » keeps only the overview: other bot messages and Loïc's own disappear after a while
bot.reg.data["del_queue"] = []
jobs = bot.reg.data["del_queue"]          # [chat, message id, when]: deleted by del_tick (kept across restarts)


async def fake_post(self, endpoint, data, *a, **k):
    return {"message_id": 70, "chat": {"id": data["chat_id"]}}
bot._do_post = fake_post


async def clean():
    from btrbot import topics
    tok = topics.TOPIC.set("dash")
    await bot._routed_post(None, "sendMessage", {"chat_id": 42, "text": "J'ai lancé…"})
    assert jobs and jobs[-1][1] == 70, jobs
    n = len(jobs)
    k = bot.DASH_KEEP.set(True)
    await bot._routed_post(None, "sendMessage", {"chat_id": 42, "text": "overview"})
    bot.DASH_KEEP.reset(k)
    assert len(jobs) == n                                    # the overview itself stays
    await bot._routed_post(None, "sendMessage", {"chat_id": -100555, "message_thread_id": 9, "text": "welcome"})
    assert len(jobs) == n                                    # not routed (welcome, pinned): stays
    topics.TOPIC.reset(tok)
    up = NS(effective_chat=NS(id=-100555, type="supergroup"), effective_user=NS(id=42), callback_query=None,
            effective_message=NS(message_thread_id=9, is_topic_message=True), message=NS(message_id=71))
    await bot.set_origin(up, None)
    assert jobs[-1][1] == 71
    print("OK clean")

asyncio.run(clean())

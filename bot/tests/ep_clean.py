"""Offline check of the per-episode cleaning of the work topics (Loïc 02.11: a fresh state for the next episode).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/ep_clean.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import topics  # noqa: E402

bot.cfg.chat_id = 42
bot.TOPICS.group, bot.TOPICS.threads = -100555, {"reels": 1, "thumbs": 2, "stories": 3, "dash": 9, "planning": 11}
ep = bot.reg.episode("VIDCLEAN001")
ep["guest_name"], ep["part"], ep.stage = "Oti Mabuse", "2", "done"
ep.save()
ep2 = bot.reg.episode("VIDCLEAN002")
ep2["guest_name"] = "Kiera Hughes"
ep2.save()
n = {"i": 100}


async def fake_post(self, endpoint, data, *a, **k):
    n["i"] += 1
    return {"message_id": n["i"]}
bot._do_post = fake_post


async def send_for(ep_):                         # a work function that takes the episode
    await bot._routed_post(None, "sendMessage", {"chat_id": 42, "text": "x"})
send_for = topics.within("reels", send_for)


async def main():
    bot.reg.data.update(ep_msgs={}, topic_ep={})
    await send_for(ep)                                         # 101 → Oti (explicit)
    await send_for(ep2)                                        # 102 → Kiera (explicit)
    tok = topics.TOPIC.set("reels")
    await bot._routed_post(None, "sendMessage", {"chat_id": 42, "text": "tick"})   # 103 → topic's last: Kiera
    topics.TOPIC.set("dash")
    await bot._routed_post(None, "sendMessage", {"chat_id": 42, "text": "dash"})   # 104 → not a work topic
    topics.TOPIC.reset(tok)
    up = NS(effective_chat=NS(id=-100555, type="supergroup"), effective_user=NS(id=42), callback_query=None,
            effective_message=NS(message_thread_id=1, is_topic_message=True), message=NS(message_id=200))
    await bot.set_origin(up, None)                             # Loïc writes in Reels → topic's last: Kiera
    m = bot.reg.data["ep_msgs"]
    assert [x[1] for x in m["VIDCLEAN001"]] == [101], m
    assert [x[1] for x in m["VIDCLEAN002"]] == [102, 103, 200], m

    # not everything out: no clean command, refused
    T = lambda i, name, st: {"id": i, "name": name, "status": {"status": st}, "custom_fields": [], "due_date": "1793600000000"}  # noqa: E731
    bot.CU_CACHE.update(at=9e18, tasks=[T("a", "Carousel · Topics · Oti P2", "posted"), T("b", "Reel 3/3 · Oti Mabuse P2 · x", "scheduled"),
                                        T("c", "Carousel · World Atlas 04 Namibia · catch-up", "scheduled")])
    text, _ = bot.dash_content(ep)
    assert "nettoyer" not in text
    said, deleted = [], []

    async def say(ctx, t, **kw):
        said.append(t)
    bot.say = say

    class B:
        async def delete_messages(self, chat, ids):
            deleted.extend(ids)

        async def delete_message(self, chat, mid):
            deleted.append(mid)
    ctx = NS(bot=B())
    upd = NS(message=NS(text="/oti2_nettoyer", message_id=300), effective_chat=NS(id=-100555))
    bot.allowed = lambda u: True
    await bot.on_dash_cmd(upd, ctx)
    assert "pas encore publié" in said[-1] and deleted == [300], (said, deleted)

    # all out (the Atlas catch-up is not this episode's) → command in « À valider », then cleaned
    bot.CU_CACHE["tasks"][1]["status"]["status"] = "posted"
    text, _ = bot.dash_content(ep)
    assert "/oti2_nettoyer" in text and "(1 message)" in text, text
    bot.reg.data["dash"] = {"VIDCLEAN001": {"mid": 77, "sig": "s"}}
    deleted.clear()
    await bot.on_dash_cmd(upd, ctx)
    assert sorted(deleted) == [77, 101, 300], deleted
    assert "VIDCLEAN001" not in bot.reg.data["ep_msgs"] and "VIDCLEAN001" not in bot.reg.data["dash"]
    assert "VIDCLEAN002" in bot.reg.data["ep_msgs"]
    ep.file("posts.json").write_text('{"items": {}}')
    import os
    os.utime(ep.file("posts.json"), (bot.reg.episode("VIDCLEAN001")["cleaned_at"] - 5,) * 2)
    assert all(e.video_id != "VIDCLEAN001" for e in bot.dash_episodes(cleaned=False))
    assert any(e.video_id == "VIDCLEAN001" for e in bot.dash_episodes())                  # still known elsewhere
    print("OK clean")

asyncio.run(main())

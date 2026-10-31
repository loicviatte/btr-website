"""Offline check of the BTR Studio group routing (topics.py + bot wiring).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/topics_flow.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import topics  # noqa: E402

OWNER, GROUP = 1001, -100777
bot.cfg.chat_id = OWNER
T = bot.TOPICS

# not set up yet: nothing moves
assert T.route(OWNER, "sendMessage", {"chat_id": OWNER}) == {"chat_id": OWNER}
T.group, T.threads = GROUP, {"reels": 11, "thumbs": 22, "stories": 33}
T.save()
assert topics.Topics(bot.cfg.data_dir).threads["thumbs"] == 22


def sent(endpoint="sendMessage", to=OWNER, **kw):
    return T.route(OWNER, endpoint, dict(chat_id=to, **kw))


assert sent() == {"chat_id": GROUP}                                   # no topic → General
assert sent("deleteMessage") == {"chat_id": OWNER}                     # only send* calls move
assert sent(to=GROUP, message_thread_id=22) == {"chat_id": GROUP, "message_thread_id": 22}


async def main():
    seen = {}

    async def probe(name):
        seen[name] = sent("sendVideo")
        await asyncio.sleep(0)

    await topics.within("reels", probe)("a")
    assert seen["a"] == {"chat_id": GROUP, "message_thread_id": 11}, seen
    assert topics.TOPIC.get() is None                                  # restored after
    topics.TOPIC.set("private")
    assert sent() == {"chat_id": OWNER}                                # started in the private chat: stays there
    await topics.within("thumbs", probe)("b")                          # …unless the work has its own topic
    assert seen["b"]["message_thread_id"] == 22
    # a job started inside a topic keeps it
    async def outer():
        t = asyncio.create_task(probe("c"))
        await t
    await topics.within("reels", outer)()
    assert seen["c"]["message_thread_id"] == 11
    topics.TOPIC.set(None)


asyncio.run(main())
print("OK route")

# every name given to assign() exists and is wrapped
import re  # noqa: E402
src = Path(bot.__file__).read_text()
for topic in ("reels", "thumbs"):
    names = re.search(r'topics\.assign\(globals\(\), "%s", """(.*?)"""' % topic, src, re.S).group(1).split()
    for n in names:
        assert getattr(getattr(bot, n), "_btr_topic", None) == topic, n
assert not hasattr(bot.ask_assistant, "_btr_topic") and not hasattr(bot.on_secret, "_btr_topic")
print("OK wrapped")

# one chat memory per topic
topics.TOPIC.set("reels")
bot.MEMORY.add("user", "cover du reel 2")
topics.TOPIC.set("thumbs")
assert not any("cover du reel 2" in m["content"] for m in bot.MEMORY._list())
bot.MEMORY.add("user", "pk_" + "x" * 30)
assert len(bot.MEMORY.everything()) == 2
topics.TOPIC.set(None)
print("OK memory")

# only Loïc drives the bot in the group
U = lambda chat, user: NS(effective_chat=NS(id=chat), effective_user=NS(id=user))  # noqa: E731
assert bot.allowed(U(OWNER, OWNER)) and bot.allowed(U(GROUP, OWNER))
assert not bot.allowed(U(GROUP, 555)) and not bot.allowed(U(-1009, OWNER))
print("OK allowed")

# set_origin: the topic of the incoming message
async def origin(chat, thread, user=OWNER, ctype="supergroup"):
    m = NS(message_thread_id=thread, is_topic_message=bool(thread))
    up = NS(effective_chat=NS(id=chat, type=ctype), effective_user=NS(id=user), effective_message=m, callback_query=None)
    await bot.set_origin(up, None)
    return topics.TOPIC.get()

assert asyncio.run(origin(GROUP, 11)) == "reels"
assert asyncio.run(origin(GROUP, None)) == "system"
assert asyncio.run(origin(GROUP, 999)) == "system"
assert asyncio.run(origin(OWNER, None, ctype="private")) == "private"
print("OK origin")

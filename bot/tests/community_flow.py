"""Offline check of the YouTube Community posts (Loïc 02.11): written from the calendar, validated, sent at their time.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/community_flow.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import community as cm, posts, share  # noqa: E402

# ---- pure helpers
assert cm.task_kind("YouTube Community · Poll · Ep Nov 3") == "poll"
assert cm.task_kind("YouTube Community · New episode tomorrow · Ep Nov 10") == "tomorrow"
assert cm.task_kind("YouTube Community · World Atlas 12 Scotland · Oti P2") == "atlas"
assert cm.task_kind("Story · Poll · Ep Nov 3") is None
assert cm.no_link("Full episode with Oti Mabuse on YouTube and Spotify, link in bio.") == "Full episode with Oti Mabuse on the channel."
assert "http" not in cm.no_link("See https://x.y now")
countries = {"scotland": {"no": 12, "name": "Scotland", "guest": "Oti Mabuse", "display": "Scotland"},
             "rwanda": {"no": 7, "name": "Rwanda", "guest": "Phemelo Mabuse"}}
assert cm.atlas_entry(countries, "Oti Mabuse")[0] == "scotland" and cm.atlas_entry(countries, "Kiera Brunton") is None
assert cm.atlas_images("M/", "scotland", 12)[0] == "M/world-atlas/12-scotland/01.jpg"
assert cm.check({"text": "ok", "question": "Who?", "options": ["a"]}) and not cm.check({"text": "ok", "question": "Who?", "options": ["a", "b"]})
print("OK helpers")

NOW = datetime(2026, 11, 2, 20, 0, tzinfo=timezone.utc)
posts.now = lambda: NOW
bot.cfg.chat_id = 42
bot.TOPICS.group, bot.TOPICS.threads = -100555, {"reels": 1, "thumbs": 2, "stories": 3, "dash": 9, "planning": 11}
ep = bot.reg.episode("VIDCOMM0001")
ep["guest_name"], ep["release_at"], ep.stage = "Flavia Cacace", "2026-11-03T18:00:00+00:00", "done"
ep.save()
ep.file("captions_davinci.srt").write_text("1\n00:00:01,000 --> 00:00:04,000\nI never wanted to be on television.\n")
Path(ep.file("render")).mkdir(exist_ok=True)
from PIL import Image  # noqa: E402
Image.new("RGB", (1920, 1080)).save(ep.file("render/thumb_youtube.jpg"))
ms = lambda d: str(int(d.timestamp() * 1000))  # noqa: E731
tasks = [{"id": "P", "name": "YouTube Community · Poll · Ep Nov 3", "status": {"status": "to generate"},
          "due_date": ms(NOW + timedelta(days=2)), "custom_fields": []},
         {"id": "T", "name": "YouTube Community · New episode tomorrow · Ep Nov 3", "status": {"status": "to generate"},
          "due_date": ms(NOW + timedelta(minutes=30)), "custom_fields": []},
         {"id": "A", "name": "YouTube Community · World Atlas · Ep Nov 3", "status": {"status": "to generate"},
          "due_date": ms(NOW + timedelta(days=2, hours=1)), "custom_fields": []},
         {"id": "L", "name": "YouTube Community · Poll · Ep Nov 24", "status": {"status": "to generate"},
          "due_date": ms(NOW + timedelta(days=22)), "custom_fields": []}]
assert bot.cm_episode(tasks[0]).video_id == "VIDCOMM0001"
bot.CU_CACHE.update(at=9e18, tasks=tasks)
calls, sent = [], []


class CU:
    def tasks(self):
        return tasks

    def task(self, tid):
        return next(t for t in tasks if t["id"] == tid)

    def update(self, tid, **f):
        calls.append(("update", tid, f.get("status")))

    def set_field(self, tid, fid, v):
        calls.append(("field", tid, v))

    def attach(self, tid, p):
        calls.append(("attach", tid))
bot.maker = lambda: NS(clickup=lambda: CU())
answers = [{"text": "Flavia says “I always wanted TV”.", "question": "Would you go on TV?", "options": ["Yes", "No"]},
           {"text": "Flavia on the spotlight: “I never wanted to be on television.”", "question": "Would you go on TV?",
            "options": ["Yes", "No way", "Only for dance"], "correct": None},
           {"text": "Tomorrow: Flavia Cacace on Break The Routine. Out tomorrow on the channel."}]
asked = []


def post(kind, *a):
    asked.append((kind, a[-1]))
    return answers.pop(0)
bot.pipe.llm = NS(community_post=post)


async def say(ctx, text, **kw):
    sent.append((text, kw.get("reply_markup")))
    return NS(chat_id=-100555, message_id=500 + len(sent))
bot.say = say


async def tg(fn, *a, **k):
    sent.append(("media", None))
bot.tg = tg


async def fake_fetch(*a):
    return None


def fetch(path):
    return {"pipeline/countries.json": {"italy": {"no": 13, "name": "Italy", "guest": "Flavia Cacace", "display": "Italy"}},
            "pipeline/captions.json": {"Italy": {"instagram": "World Atlas No. 13: Italy.\n\nFull episode with Flavia Cacace on YouTube and Spotify, link in bio."}}}[path]
bot.cm_fetch = fetch


async def main():
    ctx = NS(bot=NS(send_photo=None, send_media_group=None))
    bot.CM_SCAN["at"] = 0
    await bot.community_tick(ctx)
    st = cm.State(ep)
    poll, tom, atl = st.items["poll"], st.items["tomorrow"], st.items["atlas"]
    assert "Nov 24" not in str(st.items) and len(st.items) == 3
    assert poll["status"] == "draft" and poll["options"] == ["Yes", "No way", "Only for dance"] and not poll["warn"], poll
    assert "citation pas exacte" in asked[1][1] or "Fix these problems" in asked[1][1], asked
    assert tom["images"][0].endswith("thumb_youtube.jpg") and atl["country"] == "Italy"
    assert atl["text"].endswith("on the channel.") and atl["images"][7].endswith("13-italy/08.jpg")
    assert ("update", "P", "generated") in calls
    kb = [k for t, k in sent if k][0]
    assert kb.inline_keyboard[0][0].callback_data.startswith("yc:ok:VIDCOMM0001:")
    # dash: 3 drafts to validate
    text, _ = bot.dash_content(ep)
    assert "▶️ YouTube Community" in text and "/flavia_yt_poll" in text and "3 à valider" in text, text
    # validate « tomorrow »: ClickUp scheduled + YouTube Scheduled + thumbnail attached
    q = NS(edit_message_reply_markup=lambda *a, **k: asyncio.sleep(0))
    await bot.on_cm_button(ctx, q, "yc:ok:VIDCOMM0001:tomorrow")
    assert ("update", "T", "scheduled") in calls and ("field", "T", share.YT_SCHEDULED) in calls and ("attach", "T") in calls
    undo = [k for t, k in sent if k and "validé" in t]
    assert undo and undo[-1].inline_keyboard[0][0].callback_data == "yc:undo:VIDCOMM0001:tomorrow"
    # undone (Loïc 03.11): draft again, ClickUp « generated » + YouTube To do, preview back; then validated again
    await bot.on_cm_button(ctx, q, "yc:undo:VIDCOMM0001:tomorrow")
    assert cm.State(ep).items["tomorrow"]["status"] == "draft"
    assert ("update", "T", "generated") in calls and ("field", "T", share.YT_TODO) in calls
    assert sent[-1][1].inline_keyboard[0][0].callback_data == "yc:ok:VIDCOMM0001:tomorrow"
    await bot.on_cm_button(ctx, q, "yc:ok:VIDCOMM0001:tomorrow")
    assert cm.State(ep).items["tomorrow"]["status"] == "ok"
    # its time comes: sent ready to copy with « Posté sur YouTube »
    posts.now = lambda: NOW + timedelta(minutes=31)
    sent.clear()
    await bot.community_tick(ctx)
    final = [(t, k) for t, k in sent if k]
    assert final and "À poster maintenant" in final[-1][0] and final[-1][1].inline_keyboard[0][0].callback_data == "yc:done:VIDCOMM0001:tomorrow"
    sent.clear()
    await bot.community_tick(ctx)
    assert not sent                                                   # only once
    await bot.on_cm_button(ctx, q, "yc:done:VIDCOMM0001:tomorrow")
    assert ("field", "T", share.YT_POSTED) in calls and cm.State(ep).items["tomorrow"]["status"] == "posted"
    print("OK flow")

asyncio.run(main())

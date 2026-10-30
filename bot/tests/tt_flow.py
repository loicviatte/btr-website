"""Offline check of the TikTok semi-auto flow (bot.tt_tick / tt_posted; ClickUp faked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/tt_flow.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import share, shorts  # noqa: E402
from btrbot.state import Reels  # noqa: E402

sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append(("msg", text, kw.get("reply_markup")))

    async def send_video(self, chat, f, caption=None, **kw):
        sent.append(("video", caption, None))

    async def send_photo(self, chat, f, caption=None, **kw):
        sent.append(("photo", caption, None))


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
EP = bot.reg.episode("VIDTT000001")
rs = Reels.of(EP)
video = Path(bot.cfg.data_dir) / "r.mp4"
video.write_bytes(b"x")
now = datetime.now(timezone.utc)
rs.data = {"cands": [{"n": 1, "title": "M1", "start_s": 0, "end_s": 30}, {"n": 2, "title": "M2", "start_s": 0, "end_s": 30}],
           "sel": [1, 2], "items": {
    "1": {"status": "ok", "filed": True, "file": str(video), "cover": str(video), "captions": {"tiktok": "Hook <b>\n#BTR"},
          "yt_short": {"id": "S1", "at": shorts.iso(now - timedelta(seconds=10))}},
    "2": {"status": "ok", "filed": True, "file": str(video), "yt_short": {"id": "S2", "at": shorts.iso(now + timedelta(days=1))}}}}
rs.save()
calls = []
bot.pipe.tt_mark = lambda item, v: calls.append(v)


async def main():
    await bot.tt_tick(ctx)
    kinds = [s[0] for s in sent]
    assert kinds == ["video", "photo", "msg"], sent
    assert "&lt;b&gt;" in sent[-1][1] and sent[-1][2] is not None
    assert calls == [share.TT_SCHEDULED, share.TT_SCHEDULED], calls
    await bot.tt_tick(ctx)
    assert len(sent) == 3                                  # sent once
    await bot.tt_posted(ctx, "VIDTT000001", 1)
    assert rs.data["items"]["1"]["tt_post"]["posted"] and calls[-1] == share.TT_POSTED
    print("OK tiktok")


asyncio.run(main())


# ---- composer + Direct Post (TikTok API faked) ----
from btrbot import tiktok  # noqa: E402

posted = []


class FakeTT:
    def __init__(self, sec):
        pass

    def creator_info(self):
        return {"creator_nickname": "Break The Routine", "creator_username": "breaktheroutine",
                "privacy_level_options": ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "SELF_ONLY"],
                "comment_disabled": False, "duet_disabled": True, "stitch_disabled": False,
                "max_video_post_duration_sec": 600}

    def post(self, video, title, settings, cover_ms=0):
        posted.append((title, dict(settings)))
        return "P1"

    def status(self, pid):
        return {"status": "PUBLISH_COMPLETE"}


tiktok.TikTok = FakeTT
share.Secrets.get = lambda self, k, d=None: "x" if k == "tt_refresh" else d


class Q:
    def __init__(self):
        self.text = None

    async def edit_message_text(self, text, **kw):
        self.text = text


async def composer():
    real_sleep = asyncio.sleep
    bot.asyncio.sleep = lambda s: real_sleep(0)
    sent.clear()
    await bot.tt_compose(ctx, EP, 2)
    assert sent[0][0] == "video" and "à choisir" in sent[-1][1] and "Music Usage" in sent[-1][1], sent[-1][1]
    kb = sent[-1][2].inline_keyboard
    labels = [b.text for row in kb for b in row]
    assert "🚫 Duo" in labels and "Tout le monde" in labels and not any(l.startswith("● ") for l in labels), labels
    q = Q()
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:go")
    assert "Choisis d'abord" in sent[-1][1]
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:p:2")       # SELF_ONLY
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:m")
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:b")         # branded can't be private
    assert rs.data["items"]["2"]["tt_post"]["settings"]["privacy_level"] is None
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:p:0")
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:c")
    await bot.on_tt_button(ctx, q, "ttc:VIDTT000001:2:go")
    tt = rs.data["items"]["2"]["tt_post"]
    assert tt["confirmed"] and "Partenariat" in q.text and "Branded Content" in q.text, q.text
    rs.data["items"]["2"]["yt_short"]["at"] = shorts.iso(datetime.now(timezone.utc) - timedelta(seconds=5))
    n = len([s for s in sent if s[0] == "video"])
    await bot.tt_tick(ctx)
    for _ in range(20):
        await real_sleep(0.05)
        if posted:
            break
    await real_sleep(0.1)
    assert posted and posted[0][1]["privacy_level"] == "PUBLIC_TO_EVERYONE" and posted[0][1]["disable_comment"], posted
    assert len([s for s in sent if s[0] == "video"]) == n            # no manual notification
    assert tt["posted"] and "en ligne sur TikTok" in sent[-1][1], sent[-1]
    print("OK tiktok composer")


asyncio.run(composer())

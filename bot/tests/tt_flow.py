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

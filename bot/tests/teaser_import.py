"""Offline check: Loïc's own teaser from Drive becomes a filed reel on the « Reel teaser » task.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/teaser_import.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402

said, sent = [], []
bot.say = lambda ctx, t, **k: (said.append(t), asyncio.sleep(0))[1]
ep = bot.reg.episode("VIDTEASER01")
ep["guest_name"] = "Hannah Trever"
ep["release_at"] = "2026-11-03T00:00:00+00:00"
ep.save()
bot.RS(ep).data = {"cands": [], "items": {"1": {"status": "ok"}, "4": {"status": "ok"}}}
tmp = Path(tempfile.mkdtemp())
vid = tmp / "t.mp4"
vid.write_bytes(b"x" * 2000)
TASK = {"id": "TT", "name": "Reel teaser · Ep Nov 3", "status": {"status": "to generate"}, "due_date": "1793732400000",
        "custom_fields": []}
bot.ep_calendar = lambda e: [TASK]
cu = NS(tasks=lambda: [TASK])
bot.maker = lambda: NS(clickup=lambda: cu)
bot.pipe.teaser_import = lambda e, fid, n: (sent.append(("import", fid, n)) or
                                            {"file": str(vid), "said": "we are no longer part", "duration": 30.0,
                                             "status": "ok", "title": "Teaser", "teaser": True, "external": True,
                                             "instagram": True})
bot.pipe.reel_cover = lambda e, n, it, *a, **k: {"cover": str(vid), "cover_text": {"big": "NO"}}
bot.pipe.reel_captions = lambda e, s: {"instagram": "regular", "v": 99}
bot.pipe.teaser_captions = lambda e, it, fb="": {"instagram": "cap" + (" " + fb if fb else ""), "short_title": "T",
                                                 "v": 99, "teaser": True}
bot.pipe.teaser_apply = lambda e, n, it: (sent.append(("apply", n, it["captions"]["instagram"])) or ["Short YouTube", "ClickUp"])


async def share(ctx, e, n, quiet=False, cover=True):
    it = bot.reel_item(e, n)
    sent.append(("share", n, it.get("clickup_task"), it.get("title")))
    return f"Reel {n} rangé"
bot.share_reel = share


async def video(*a, **k):
    sent.append(("video",))
ctx = NS(bot=NS(send_video=video))


async def main():
    await bot.teaser_import(ctx, ep, "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/view?usp=sharing")
    assert ("import", "1AbCdEfGhIjKlMnOpQrStUvWxYz012345", 5) in sent, sent
    assert ("share", 5, "TT", "Teaser") in sent, sent
    it = bot.reel_item(ep, 5)
    assert it["filed"] and it["clickup_kind"] == "teaser" and it["captions"]["instagram"] == "cap"
    assert "Cover OK" in said[-1], said
    await bot.teaser_import(ctx, ep, "")
    assert "colle-moi le lien" in said[-1], said[-1]
    # the vertical thumbnail is the cover when it exists (Loïc 03.11)
    Path(ep.file("render")).mkdir(exist_ok=True)
    Path(ep.file("render/thumb_instagram.jpg")).write_bytes(b"jpg")
    await bot.teaser_import(ctx, ep, "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUvWxYz012345/view")
    it = bot.reel_item(ep, 5)
    assert it["cover_vertical"] and it["cover"].endswith("_teaser_cover.jpg") and Path(it["cover"]).read_bytes() == b"jpg"
    # teaser-style texts again on demand, carried to the Short + ClickUp (Loïc 03.11)
    it["filed"] = True
    bot.RS(ep).save()
    await bot.teaser_recaption(ctx, ep, None, "plus court")
    assert ("apply", 5, "cap plus court") in sent, sent
    assert "Short YouTube + ClickUp + Instagram" in said[-1] and "cap plus court" in said[-1], said[-1]
    print("teaser import: OK")

asyncio.run(main())

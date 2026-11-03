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
bot.pipe.reel_captions = lambda e, s: {"instagram": "cap", "v": 99}


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
    await bot.teaser_import(ctx, ep, "pas de lien")
    assert "identifiant" in said[-1]
    print("teaser import: OK")

asyncio.run(main())

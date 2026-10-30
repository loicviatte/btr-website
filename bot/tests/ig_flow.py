"""Offline check of the Instagram posting (bot.ig_tick: warn when not connected, upload ~45 min before, publish at the
time, retries). Meta and ClickUp faked.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/ig_flow.py
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
        sent.append(text)


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
EP = bot.reg.episode("VIDIG000001")
rs = Reels.of(EP)
video = Path(bot.cfg.data_dir) / "r.mp4"
video.write_bytes(b"x")
now = datetime.now(timezone.utc)
rs.data = {"cands": [{"n": i, "title": f"M{i}", "start_s": 0, "end_s": 30} for i in (1, 2, 3)], "sel": [1, 2, 3], "items": {
    "1": {"status": "ok", "filed": True, "file": str(video), "instagram": True, "captions": {"collab": ["otimabuse"]},
          "yt_short": {"id": "S1", "at": shorts.iso(now + timedelta(minutes=30))}},
    "2": {"status": "ok", "filed": True, "file": str(video), "instagram": True,
          "yt_short": {"id": "S2", "at": shorts.iso(now + timedelta(days=2))}},
    "3": {"status": "ok", "filed": True, "file": str(video), "instagram": False,
          "yt_short": {"id": "S3", "at": shorts.iso(now + timedelta(minutes=5))}}}}
rs.save()
SEC = {}
share.Secrets.get = lambda self, k, d=None: SEC.get(k, d)
calls = []
p = bot.pipe
p.ig_mark = lambda item, v: calls.append(("mark", v))
p.ig_prepare = lambda ep, n, item: calls.append(("prepare", n)) or {"container": f"C{n}", "made": now.isoformat(),
                                                                       "grid": False, "note": ""}
fail = [0]


def publish(item):
    if fail[0]:
        fail[0] -= 1
        raise RuntimeError("Instagram 500 : boom")
    calls.append(("publish", item["ig_post"]["container"]))
    return {"id": "M1", "permalink": "https://instagram.com/reel/x"}


p.ig_publish = publish


async def fake_share(ctx, ep, n, quiet=False, cover=True):
    return ""


bot.share_reel = fake_share


async def tick():
    await bot.ig_tick(ctx)
    for _ in range(50):
        if not bot.IG_BUSY:
            break
        await asyncio.sleep(0.02)


async def main():
    it1 = rs.data["items"]["1"]
    await tick()                                         # not connected: one warning for reel 1 only
    assert len(sent) == 1 and "pas connecté" in sent[0] and "M1" in sent[0], sent
    await tick()
    assert len(sent) == 1
    SEC["ig_token"] = "x"
    it1["ig_post"].pop("warned")
    await tick()                                         # connected: marks both feed reels, uploads reel 1
    assert calls.count(("mark", share.IG_SCHEDULED)) == 2 and ("prepare", 1) in calls, calls
    assert it1["ig_post"]["container"] == "C1" and not it1["ig_post"].get("posted")
    await tick()                                         # not time yet: nothing
    assert not any(c[0] == "publish" for c in calls)
    it1["yt_short"]["at"] = shorts.iso(datetime.now(timezone.utc) - timedelta(seconds=5))
    fail[0] = 1
    await tick()                                         # first publish fails, retried next minute
    assert it1["ig_post"]["tries"] == 1 and not it1["ig_post"].get("posted")
    await tick()
    assert it1["ig_post"]["posted"] and it1["links"]["instagram"].startswith("https://instagram.com"), it1
    assert "en ligne sur Instagram" in sent[-1] and "@otimabuse" in sent[-1], sent[-1]
    assert ("prepare", 3) not in calls and ("prepare", 2) not in calls
    n = len(calls)
    await tick()
    assert len(calls) == n
    print("OK instagram")


asyncio.run(main())


# ---- guest's Instagram @ ----
caps = {"instagram": "“Hook.”\n\nKiera Brunton on judging: “x”\n\nWhy? Tell us in the comments.", "collab": ["mariusiepure"]}
c = share.apply_handle(caps, "Kiera Brunton", "kierabrunton")
assert "\n\n@kierabrunton on judging" in c["instagram"] and c["collab"] == ["kierabrunton", "mariusiepure"], c
assert share.apply_handle(c, "Kiera Brunton", "kierabrunton")["instagram"] == c["instagram"]
assert share.apply_handle(caps, "Kiera Brunton", None)["collab"] == ["mariusiepure"]


async def handles():
    EP2 = bot.reg.episode("VIDIG000002")
    EP2["guest_name"] = "Kiera Brunton"
    EP2.save()
    r2 = Reels.of(EP2)
    r2.data = {"cands": [], "sel": [], "items": {"1": {"status": "ok", "captions": dict(caps)}}}
    r2.save()
    bot.pipe.guest_instagram = lambda ep: {"handle": "kierabrunton", "sure": True, "evidence": "compte vérifié"}
    await bot.ask_handle(ctx, EP2)
    assert "@kierabrunton" in sent[-1] and bot.reg.data["handle_ask"]["cand"] == "kierabrunton"
    n = len(sent)
    await bot.ask_handle(ctx, EP2)                       # asked once only
    assert len(sent) == n
    assert await bot.handle_reply(ctx, "@kiera.brunton_")
    assert share.guest_handle("Kiera Brunton") == "kiera.brunton_" and "handle_ask" not in bot.reg.data
    assert "@kiera.brunton_ on judging" in r2.data["items"]["1"]["captions"]["instagram"]
    assert not await bot.handle_reply(ctx, "@someone")    # nothing pending any more
    share.load_handles(bot.cfg.data_dir)
    assert share.guest_handle("kiera brunton") == "kiera.brunton_"
    print("OK handles")


asyncio.run(handles())

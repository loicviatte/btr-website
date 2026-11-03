"""Offline check: an unlisted upload YouTube is still processing is announced once, reminded once, then started.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/pending_upload.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402

said = []


async def fake_say(ctx, text, **kw):
    said.append(text)

bot.say = fake_say
bot.poll_drive = lambda ctx: asyncio.sleep(0)
bot.shorts_sync = bot.shorts_watch = lambda ctx: asyncio.sleep(0)
bot.poll_transcripts = lambda ctx: asyncio.sleep(0)
bot.pick_pending = lambda title: None
bot.reg.data["initialised"] = True

VID = "qAk-Mqe6xoQ"
pending = {"id": VID, "snippet": {"title": "EP14 HANNAH VIDEO", "publishedAt": "2026-11-03T00:17:38Z"},
           "status": {"privacyStatus": "unlisted", "uploadStatus": "uploaded"},
           "processingDetails": {"processingStatus": "processing"}, "fileDetails": {"fileSize": "29162810199"}}
state = {"ready": []}
bot.pipe.yt = NS(unlisted_pending=lambda: [] if state["ready"] else [pending], unlisted_ready=lambda: state["ready"])
ctx = NS(bot=None)


async def main():
    await bot.poll_youtube(ctx)
    assert len(said) == 1 and "traite encore" in said[0] and "29 Go" in said[0] and "déjà" in said[0], said
    await bot.poll_youtube(ctx)
    assert len(said) == 1, said                                               # > 6 h already said: told once
    said.insert(0, "")                                                        # keep the indexes below
    state["ready"] = [{"id": VID, "snippet": {"title": "EP14 HANNAH VIDEO"}}]
    await bot.poll_youtube(ctx)
    assert "fini de traiter" in said[2] and "Nouvelle vidéo" in said[3], said
    assert bot.reg.seen(VID) and VID not in bot.reg.data["pending"]
    assert bot.reg.episode(VID).stage == "waiting_transcript"
    pending["processingDetails"]["processingStatus"] = "failed"
    pending["id"] = "OTHER000001"
    state["ready"] = []
    await bot.poll_youtube(ctx)
    assert "pas réussi" in said[-1], said
    print("pending upload: OK")

asyncio.run(main())

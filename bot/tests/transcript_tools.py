"""Offline check of transcript_search / post_texts (the chat answers questions about texts from the SRT).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/transcript_tools.py
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import posts  # noqa: E402

ep = bot.reg.episode("VIDTEXT0001")
ep["guest_name"], ep["part"] = "Oti Mabuse", "2"
ep.save()
ep.file("captions_davinci.srt").write_text(
    "1\n01:00:00,000 --> 01:00:03,000\nHello.\n\n2\n01:34:10,000 --> 01:34:13,000\nIf I wasn't a dancer I'd open a school\n\n"
    "3\n01:34:13,000 --> 01:34:16,000\nwith some chickens in the garden.\n")
st = posts.PostState(ep)
st.data["items"] = {"chain": {"kind": "chain", "status": "ok", "made": 5, "sticker": {"type": "quiz"}}}
st.data["content"] = {"chain": {"question": "If you weren't a dancer…", "line": "Her plan B still has a dance school, and chickens."}}
st.save()


async def main():
    h = bot.tool_handlers(NS(bot=None), [])
    r = await h["transcript_search"](query="chicken", guest="Oti P2")
    assert "34:13" in r and "chickens in the garden" in r and "Oti Mabuse" in r, r
    r = await h["transcript_search"](at="34:11")
    assert "school" in r, r
    r = await h["post_texts"](keys=["chain"])
    assert "chickens" in r and "quiz" in r, r
    assert "transcript_search" in bot.topic_context_base("stories")
    print("OK transcript tools")

asyncio.run(main())

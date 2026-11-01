"""Offline check of the « Instagram planning » overview + the conversation sweep.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/planning_overview.py
"""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import dashboard, posts  # noqa: E402

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)
posts.now = lambda: NOW
bot.cfg.chat_id = 42
bot.TOPICS.group, bot.TOPICS.threads = -100555, {"dash": 9, "planning": 11, "stories": 3}
ep = bot.reg.episode("VIDPLAN0001")
ep["guest_name"], ep["part"], ep["release_at"] = "Oti Mabuse", "2", "2026-10-27T18:00:00+00:00"
ep.save()
(ep.file("posts.json")).write_text('{"items": {}}')


def T(i, name, status, ms):
    return {"id": i, "name": name, "status": {"status": status}, "due_date": str(ms), "custom_fields": []}


bot.CU_CACHE.update(at=9e18, tasks=[
    T("a", "Carousel · Key moment · Oti P2", "posted", 1793354400000),
    T("b", "Reel 3/3 · Oti Mabuse P2 · Her One Question", "scheduled", 1793563200000),
    T("c", "Carousel · Topics · Oti P2", "scheduled", 1793613600000),
    T("d", "Short · Oti Mabuse P2 · Studios Lack Gratitude", "scheduled", 1793620800000),
    T("e", "Story · The Chain · Oti P2", "to generate", 1793646000000),
    T("f", "Reel · Oti Mabuse P2 · Too Many World Champions", "scheduled", 1793649600000),
    T("g", "Carousel · World Atlas 04 Namibia · catch-up", "scheduled", 1793728800000),
    T("h", "Carousel · World Atlas 02 Papua New Guinea · catch-up", "posted", 1793296800000),
    T("i", "Story · Teaser share · Ep Nov 3", "to generate", 1793732400000),
    T("j", "Carousel · World Atlas 09 Japan · catch-up", "scheduled", 1794564000000),
    T("k", "YouTube Community · Poll · Ep Nov 3", "to generate", 1793811600000),
    T("l", "Carousel · World Atlas 05 Chad · catch-up", "scheduled", 1793872800000)])
text = bot.plan_overview_text()
print(text)
assert "Semaine du mar. 27.10 au lun. 02.11" in text and "Épisode : Oti Mabuse · Part 2" in text, text
assert "5 posts restants" in text, text
assert "Reel 3/3 · Her One Question" in text and "Carrousel Topics" in text and "⬜" in text and "Story The Chain" in text
assert "▶️ Short · Studios Lack Gratitude" in text and "📸 Carrousel Topics" in text
assert "Key moment" not in text and "Community" not in text and "Teaser share" not in text     # posted / next week
assert "Namibia" not in text and "Papua" not in text                                           # next week / posted
s, e = bot.plan_week(datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc))
assert s.strftime("%a %d.%m %H:%M") == "Tue 03.11 00:00" and e.strftime("%d.%m") == "10.11"
assert bot.plan_week(NOW)[0].strftime("%d.%m") == "27.10"
assert "en retard" not in text
assert dashboard.ig_kind("Carrousel · World Atlas 03 Mexico") == "atlas" and dashboard.ig_kind("Short · x") == "short"
assert dashboard.short_name("YouTube Community · Poll · Ep Nov 3", "community") == "Community · Poll"
print("OK overview")

sent, edits, deleted = [], [], []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append((chat, text, kw))
        return NS(message_id=700 + len(sent))

    async def edit_message_text(self, text, **kw):
        edits.append(text)

    async def delete_message(self, chat, mid):
        deleted.append(mid)


async def main():
    ctx = NS(bot=FakeBot())
    await bot.plan_overview_tick(ctx)
    assert len(sent) == 1 and bot.reg.data["planning_msg"]["mid"] == 701
    await bot.plan_overview_tick(ctx)
    assert len(sent) == 1 and not edits                       # nothing changed: untouched
    bot.CU_CACHE["tasks"][1]["status"]["status"] = "posted"
    await bot.plan_overview_tick(ctx)
    assert len(edits) == 1 and "4 posts restants" in edits[0]
    # the conversation: Loïc asks (kept while unanswered), the bot answers, then everything goes
    bot.reg.data["plan_msgs"] = []
    bot.plan_forget(-100555, 801, incoming=True)
    await bot.plan_sweep(ctx)
    assert not deleted and bot.reg.data["plan_msgs"]          # answer still coming
    bot.plan_forget(-100555, 802)
    await bot.plan_sweep(ctx)
    assert deleted == [801, 802] and bot.reg.data["plan_msgs"] == []
    print("OK tick + sweep")

asyncio.run(main())

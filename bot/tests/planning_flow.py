"""Offline check of « Instagram planning » (ClickUp calendar changed by chat).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/planning_flow.py
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import posts  # noqa: E402

base = datetime(2026, 11, 4, 19, 0, tzinfo=posts.TZ)
assert bot.plan_when("11h", base).strftime("%d.%m %H:%M") == "04.11 11:00"
assert bot.plan_when("5.11 18h30", base).strftime("%d.%m %H:%M") == "05.11 18:30"
assert bot.plan_when("6.11", base).strftime("%H:%M") == "19:00"
assert posts.task_name("rapid", "Ep Nov 3") == "Story · Rapid fire · Ep Nov 3"
assert posts.task_label("Story · Poll · Ep Nov 3") == "Ep Nov 3"
assert "Time: 19:00" in posts.task_desc("poll", base)
print("OK parse")

tasks = {"P": {"id": "P", "name": "Story · Poll · Ep Nov 3", "status": {"status": "scheduled"},
               "due_date": str(int(base.timestamp() * 1000)), "markdown_description": "Where: Instagram story\nTime: 19:00\nWhat: x"},
         "D": {"id": "D", "name": "Story · Link · Oti P2", "status": {"status": "posted"}, "due_date": "1"}}
updates, created, deleted = [], [], []


class CU:
    def task(self, tid):
        return tasks[tid]

    def update(self, tid, **f):
        updates.append((tid, f))
        tasks[tid].update({k: v for k, v in f.items() if k == "name"})

    def tasks(self):
        return list(tasks.values())

    def create(self, **f):
        created.append(f)
        return {"id": "N", "name": f["name"]}

    def delete(self, tid):
        deleted.append(tid)


bot.maker().clickup = lambda: CU()
bot.dash_episodes = lambda: []
bot.bg = lambda c, label, coro, limit=None: coro.close() or "lancé"


async def main():
    r = await bot.plan_change(None, "P", "rapid")
    assert "fait" in r and updates[-1][1]["name"] == "Story · Rapid fire · Ep Nov 3" and updates[-1][1]["status"] == "to generate", (r, updates)
    r = await bot.plan_change(None, "P", None, "11h")
    f = updates[-1][1]
    assert datetime.fromtimestamp(f["due_date"] / 1000, posts.TZ).hour == 11 and "Time: 11:00" in f["markdown_content"], f
    assert "verrouillé" in await bot.plan_change(None, "D", "poll")
    assert "carrousel" in await bot.plan_change(None, "P", "topics")
    r = await bot.plan_add(None, "quote", "6.11 19h", like="P")
    assert created and created[-1]["name"] == "Story · Quote · Ep Nov 3" and created[-1]["status"] == "to generate", created
    assert "déjà publié" in await bot.plan_remove("D") and not deleted
    await bot.plan_remove("P")
    assert deleted == ["P"]
    print("OK planning")

asyncio.run(main())

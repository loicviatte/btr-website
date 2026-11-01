"""Stress / edge cases of « Posts planning » + « À valider » (overview, sweeps, routing, /fait, transcript search).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/planning_stress.py
"""
import asyncio
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import dashboard, posts, srt, topics  # noqa: E402

NOW = datetime(2026, 11, 1, 18, 0, tzinfo=timezone.utc)
posts.now = lambda: NOW
bot.cfg.chat_id = 42
bot.TOPICS.group, bot.TOPICS.threads = -100555, {"dash": 9, "planning": 11, "stories": 3}
ms = lambda d: str(int(d.timestamp() * 1000))


def T(i, name, status, at):
    return {"id": i, "name": name, "status": {"status": status}, "due_date": ms(at) if at else None, "custom_fields": []}


# ── week boundaries (London, DST ended 25.10) ──
L = posts.TZ
for when, start in [(datetime(2026, 11, 3, 0, 0, tzinfo=L), "03.11"), (datetime(2026, 11, 2, 23, 59, tzinfo=L), "27.10"),
                    (datetime(2026, 10, 25, 12, 0, tzinfo=L), "20.10"), (datetime(2026, 11, 10, 0, 0, 1, tzinfo=L), "10.11")]:
    s, e = bot.plan_week(when)
    assert s.strftime("%d.%m %H:%M") == f"{start} 00:00" and e - s == timedelta(days=7) and e.hour == 0, (when, s, e)
print("OK week")

# ── overview edge cases ──
bot.CU_CACHE.update(at=9e18, tasks=[])
txt = bot.plan_overview_text()
assert "Tout est publié" in txt and "Semaine du mar. 27.10 au lun. 02.11" in txt, txt
many = [T(f"t{i}", f"Story · <Poll> & co {i} · Oti P2", "to generate", NOW + timedelta(hours=i % 30)) for i in range(120)]
many += [T("nodue", "Carousel · Topics · Oti P2", "to generate", None),
         dict(T("late1", "Short · Oti P2 · Alone", "scheduled", NOW - timedelta(hours=3)), custom_fields=[
             {"id": bot._share.F_TT, "value": {"name": "Scheduled"}}, {"id": bot._share.F_YT, "value": {"name": "Posted"}},
             {"id": bot._share.F_IG, "value": {"name": "Not planned"}}]),
         T("Bad ID", "Reel · Oti P2 · x", "scheduled", NOW - timedelta(hours=2)),
         T("done1", "Reel · Oti P2 · y", "posted", NOW - timedelta(hours=1)),
         T("weird", "", "to generate", NOW),
         T("nextw", "Reel · Oti P2 · z", "scheduled", datetime(2026, 11, 3, 0, 0, tzinfo=L))]
bot.CU_CACHE["tasks"] = many
txt = bot.plan_overview_text()
assert len(txt) <= 4096 and "…" in txt, len(txt)
assert "&lt;Poll&gt; &amp; co" in txt and "<Poll>" not in txt
assert "en retard (TikTok)  /fait_late1" in txt, txt[-900:]
assert "/fait_late1" in txt and "/fait_Bad" not in txt and "Déjà publié à la main" in txt
assert "Oti P2 · y" not in txt and "· y" not in txt and "Reel · z" not in txt          # posted / next week hidden
print("OK overview edge cases", len(txt))

# ── routing / sweeps ──
calls = []


async def fake_post(self, endpoint, data, *a, **k):
    calls.append((endpoint, dict(data)))
    if endpoint == "sendMediaGroup":
        return [{"message_id": 900}, {"message_id": 901}]
    return {"message_id": 800 + len(calls)}

bot._do_post = fake_post
deleted = []


class FakeBot:
    async def delete_message(self, chat, mid):
        deleted.append(mid)


async def main():
    ctx = NS(bot=FakeBot())
    eb = object()
    bot.reg.data["plan_msgs"], bot.reg.data["del_queue"] = [], []
    tok = topics.TOPIC.set("planning")
    await bot._routed_post(eb, "sendMessage", {"chat_id": 42, "text": "a"})
    await bot._routed_post(eb, "sendMediaGroup", {"chat_id": 42, "media": []})
    await bot._routed_post(eb, "sendChatAction", {"chat_id": 42, "action": "typing"})
    k = bot.DASH_KEEP.set(True)
    await bot._routed_post(eb, "sendMessage", {"chat_id": 42, "text": "overview"})
    bot.DASH_KEEP.reset(k)
    topics.TOPIC.set("stories")
    await bot._routed_post(eb, "sendMessage", {"chat_id": 42, "text": "elsewhere"})
    topics.TOPIC.set("dash")
    await bot._routed_post(eb, "sendMessage", {"chat_id": 42, "text": "dash answer"})
    topics.TOPIC.reset(tok)
    ids = [m[1] for m in bot.reg.data["plan_msgs"]]
    assert ids == [801, 900, 901], ids
    assert [x[1] for x in bot.reg.data["del_queue"]] == [806], bot.reg.data["del_queue"]
    assert calls[0][1]["message_thread_id"] == 11 and calls[0][1]["chat_id"] == -100555
    # model busy: nothing goes even long after; done → sweep
    bot.PLAN_BUSY.update(n=1, since=time.time())
    await bot.plan_sweep(ctx)
    assert not deleted
    bot.PLAN_BUSY.update(n=1, since=time.time() - 4000)            # stuck for more than 30 min: swept anyway
    await bot.plan_sweep(ctx)
    assert deleted == [801, 900, 901], deleted
    bot.PLAN_BUSY.update(n=0)
    # dash deletions survive a restart: they are in reg.data, done by del_tick when due
    deleted.clear()
    await bot.del_tick(ctx)
    assert not deleted
    bot.reg.data["del_queue"][0][2] = time.time() - 1
    await bot.del_tick(ctx)
    assert deleted == [806] and bot.reg.data["del_queue"] == []
    print("OK routing + sweeps")

    # ── overview edit: hiccup → no duplicate; gone → sent again ──
    sent, mode = [], {"err": None}

    class OB:
        async def edit_message_text(self, text, **kw):
            if mode["err"]:
                raise mode["err"]

        async def send_message(self, chat, text, **kw):
            sent.append(text)
            return NS(message_id=1000 + len(sent))

    async def tg(fn, *a, **k):
        return await fn(*a, **k)
    bot.tg = tg
    octx = NS(bot=OB())
    bot.reg.data["planning_msg"] = {"mid": 777, "sig": "old"}
    mode["err"] = TimeoutError("timed out")
    await bot.plan_overview_tick(octx)
    assert not sent and bot.reg.data["planning_msg"] == {"mid": 777, "sig": "old"}
    mode["err"] = Exception("Bad Request: message to edit not found")
    await bot.plan_overview_tick(octx)
    assert len(sent) == 1 and bot.reg.data["planning_msg"]["mid"] == 1001
    print("OK overview edits")

    # ── /fait ──
    said = []

    async def say(ctx, text, **kw):
        said.append(text)
    bot.say = say

    class CU:
        def task(self, tid):
            return {"t1": dict(T("t1", "Short · Oti P2 · x", "scheduled", NOW - timedelta(hours=1)),
                               custom_fields=[{"id": bot._share.F_TT, "value": {"name": "Scheduled"}}]),
                    "t2": T("t2", "Reel · x", "scheduled", NOW + timedelta(hours=1))}[tid]

        def set_field(self, tid, f, v):
            said.append(f"FIELD {f} {v}")

        def update(self, tid, **f):
            said.append(f"UPDATE {tid} {f}")

        def tasks(self):
            return []
    bot.maker = lambda: NS(clickup=lambda: CU())
    await bot.plan_mark_done(None, "t2")
    assert "pas encore passé" in said[-1]
    await bot.plan_mark_done(None, "t1")
    assert f"FIELD {bot._share.F_TT} {bot._share.TT_POSTED}" in said and not any(x.startswith(f"FIELD {bot._share.F_YT}") for x in said)
    assert "UPDATE t1 {'status': 'posted'}" in said and "marqué publié" in said[-1]
    print("OK /fait")

asyncio.run(main())

# ── transcript search: big, odd queries ──
cues = [srt.Cue(i * 3, i * 3 + 3, f"line {i} about dancing (and) café") for i in range(4000)]
cues[3210] = srt.Cue(9630, 9633, "we kept Chickens [really] in the garden")
t0 = time.time()
r = srt.search(cues, "chicken")
assert "2:40:30" in r and time.time() - t0 < 2, r
assert "n'est pas" in srt.search(cues, "(chicken") or "2:40:30" in srt.search(cues, "(chicken")
assert "café" in srt.search(cues, "CAFE")[:400] and "autres passages" in srt.search(cues, "cafe")
assert srt.search(cues, "") == "rien à chercher" and srt.search([], "x").startswith("pas de transcription")
assert "chickens" in srt.search(cues, at=9631).lower()
print("OK transcript search", round(time.time() - t0, 2), "s")

# ── a validated post linked to its task afterwards is filed (« Posts planning » switched Ask → The Chain, 01.11) ──
ep = bot.reg.episode("VIDLINK0001")
ep["guest_name"] = "Oti Mabuse"
ep.save()
st = posts.PostState(ep)
st.data["items"] = {"chain": {"kind": "chain", "status": "ok", "task": "agvq", "files": []},
                    "poll": {"kind": "poll", "status": "draft", "task": "p1"},
                    "topics": {"kind": "topics", "status": "ok", "task": "agvm"}}
st.save()
filed = []


class CU2:
    def task(self, tid):
        return {"agvq": {"status": {"status": "to generate"}}, "agvm": {"status": {"status": "scheduled"}}}[tid]


bot.maker = lambda: NS(clickup=lambda: CU2(), file=lambda ep, st, k: filed.append(k))
out = asyncio.run(bot.posts_file_linked(ep))
assert filed == ["chain"] and out == ["Story The Chain · Oti Mabuse"], (filed, out)
print("OK file linked")

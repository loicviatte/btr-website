"""Offline check of the YouTube Shorts scheduling (planner, upload, ClickUp, sync; YouTube and ClickUp faked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/shorts_flow.py
"""
import asyncio
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import share, shorts  # noqa: E402
from btrbot.state import Reels  # noqa: E402

NOW = datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc)

# ---- planner -------------------------------------------------------------------------------------------
sat = datetime(2026, 10, 31, 18, 0, tzinfo=shorts.TZ)
p = shorts.plan([{"key": "a", "task_at": sat}, {"key": "b"}, {"key": "c"},
                 {"key": "d", "vid": "Y1", "cur_at": datetime(2026, 11, 5, 18, 0, tzinfo=shorts.TZ)},
                 {"key": "e", "vid": "Y2", "cur_at": datetime(2026, 11, 6, 18, 0, tzinfo=shorts.TZ),
                  "chosen": datetime(2026, 11, 7, 19, 0, tzinfo=shorts.TZ)}], NOW)
got = {x["key"]: (shorts.label(x["at"]), x["why"], x["action"]) for x in p}
assert got["a"] == ("sam. 31.10 18:00", "date ClickUp", "upload"), got
assert got["b"] == ("dim. 01.11 18:00", "jour libre", "upload"), got        # Saturday taken by a
assert got["c"] == ("lun. 02.11 18:00", "jour libre", "upload"), got
assert got["d"][2] is None and got["e"] == ("sam. 07.11 19:00", "ton choix", "move"), got
assert shorts.iso(sat) == "2026-10-31T18:00:00Z"
assert shorts.label(shorts.parse_choice("4.11 19h", NOW)) == "mer. 04.11 19:00"
assert shorts.label(shorts.parse_choice("2026-11-04", NOW)) == "mer. 04.11 18:00"
assert shorts.parse_choice("3.01", NOW).year == 2027
for bad in ("30.10 10h", "demain"):
    try:
        shorts.parse_choice(bad, NOW)
        raise AssertionError(bad)
    except ValueError:
        pass
past = {"due_date": str(int((NOW - timedelta(days=1)).timestamp() * 1000))}
assert shorts.due_at(past, NOW) is None
print("OK planner")

# ---- bot flow with fakes ---------------------------------------------------------------------------------
sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append((text, kw.get("reply_markup")))


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
p = bot.pipe
EP = bot.reg.episode("VIDSHORTS01")
EP["guest_name"] = "Oti Mabuse"
EP.save()
rs = Reels.of(EP)
video = Path(tempfile.mkdtemp()) / "r.mp4"
video.write_bytes(b"x")
due = int(datetime(2026, 11, 20, 0, 0, tzinfo=shorts.TZ).timestamp() * 1000)
rs.data = {"cands": [{"n": i, "title": f"Moment {i}", "start_s": 0, "end_s": 30} for i in (1, 2, 3)], "sel": [1, 2, 3],
           "items": {"1": {"status": "ok", "filed": True, "file": str(video), "instagram": False, "clickup_task": "T1",
                           "clickup_kind": "short", "captions": {"short_title": "Oti: “x” | Break The Routine",
                                                                 "short_desc": "Oti on x.\n\n#BreakTheRoutine #Shorts"}},
                     "2": {"status": "ok", "filed": True, "file": str(video), "instagram": True, "clickup_task": "T2",
                           "clickup_kind": "slot"},
                     "3": {"status": "dropped"}}}
rs.save()
tasks = {"T1": {"id": "T1"}, "T2": {"id": "T2", "due_date": str(due)}}
calls = []


class FakeCU:
    def __init__(self, token):
        pass

    def task(self, tid):
        return tasks[tid]

    def set_field(self, tid, f, v):
        calls.append(("field", tid, v))

    def update(self, tid, **kw):
        calls.append(("update", tid, kw))
        tasks[tid].update(kw)


share.ClickUp = FakeCU
share.Secrets.get = lambda self, k, d=None: "pk_x" if k == "clickup_token" else d
yt = {}
made = [0]


class FakeYT:
    def upload_short(self, path, title, desc, at, cat, tags):
        made[0] += 1
        vid = f"S{made[0]}"
        yt[vid] = {"privacyStatus": "private", "publishAt": at, "title": title}
        return {"id": vid, "status": dict(yt[vid])}

    def reschedule(self, vid, at):
        assert yt[vid]["privacyStatus"] == "private"
        yt[vid]["publishAt"] = at

    def statuses(self, ids):
        return {i: yt[i] for i in ids if i in yt}

    def video(self, vid):
        return {"snippet": {"categoryId": "24"}}


p.yt = FakeYT()
shared = []


async def fake_share(ctx, ep, n, quiet=False, cover=True):
    assert cover is False
    shared.append(n)
    return ""


bot.share_reel = fake_share
real_now = datetime.now(timezone.utc)


async def main():
    await bot.shorts_show(ctx)
    text, kb = sent[-1]
    assert "Reel 2" in text and "date ClickUp" in text and "Reel 1" in text and "jour libre" in text, text
    assert "Reel 3" not in text and kb is not None, text
    await bot.shorts_go(ctx)
    assert len(yt) == 2 and shared == [2, 1], (yt, shared)
    it1, it2 = rs.data["items"]["1"], rs.data["items"]["2"]
    assert it2["yt_short"]["at"] == "2026-11-20T18:00:00Z", it2
    assert it1["links"]["short"].startswith("https://youtube.com/shorts/")
    assert ("field", "T1", share.YT_SCHEDULED) in calls and any(c[0] == "update" and c[1] == "T1" for c in calls)
    assert not any(c[0] == "update" and c[1] == "T2" for c in calls)          # a calendar slot keeps Loïc's date
    assert "Rien à programmer" not in sent[-1][0] and "lien" in sent[-1][0], sent[-1][0]
    # nothing left to do
    await bot.shorts_go(ctx)
    assert "Rien à programmer" in sent[-1][0], sent[-1][0]
    # Loïc moves the Short of reel 1
    item = rs.data["items"]["1"]
    item["short_at"] = shorts.iso(shorts.parse_choice("25.11 19h", real_now))
    rs.save()
    await bot.shorts_go(ctx)
    assert yt[item["yt_short"]["id"]]["publishAt"] == item["short_at"] and len(yt) == 2, yt
    assert "déplacé" in sent[-1][0], sent[-1][0]
    # deleted on YouTube → sent again
    del yt[item["yt_short"]["id"]]
    await bot.shorts_go(ctx)
    assert len(yt) == 2 and item["yt_short"]["id"] == "S3", (yt, item)
    # YouTube made it public → Posted in ClickUp, never touched again
    item["yt_short"]["at"] = "2026-01-01T00:00:00Z"
    yt["S3"]["privacyStatus"] = "public"
    await bot.shorts_sync(ctx)
    assert item["yt_short"].get("posted") and ("field", "T1", share.YT_POSTED) in calls
    assert "Short en ligne" in sent[-1][0]
    n = len(sent)
    await bot.shorts_sync(ctx)
    assert len(sent) == n
    # description line in ClickUp
    d = share.description("", {"short": "https://youtube.com/shorts/S3"}, {"yt_short": {"at": "2026-11-25T19:00:00Z"}},
                          "T", "u", "30.10", False)
    assert "YouTube Short : https://youtube.com/shorts/S3" in d and "mer. 25.11 19:00" in d, d
    print("OK flow")


asyncio.run(main())

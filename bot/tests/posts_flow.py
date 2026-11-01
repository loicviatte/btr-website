"""Offline check of the carousels & stories (posts.py, postmaker.py, bot wiring; ClickUp, Instagram, LLM faked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/posts_flow.py [--render]
"""
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import postmaker, posts, share, srt  # noqa: E402

# ---- ClickUp names → kinds, Atlas tasks -----------------------------------------------------------------
assert posts.task_kind("Carousel · Key moment · Ep Nov 3") == "moment"
assert posts.task_kind("Carousel · Topics · Oti P2") == "topics"
assert posts.task_kind("Carousel · World Atlas 09 Japan · catch-up") is None
assert posts.task_kind("Story · Question / answer · Ep Dec 1") == "qa"
assert posts.task_kind("Story · Atlas quiz · Ep Dec 8") == "atlas"
assert posts.task_kind("Reel 2/3 · Oti Mabuse P2 · How To Impress Each Judge") is None
day = datetime(2026, 11, 4, 10, 0, tzinfo=posts.TZ)
tk = {"text_content": "Where: Instagram (grid) + TikTok\nTime: 10:00 Instagram · 12:00 TikTok"}
assert posts.tiktok_time(tk, day).hour == 12
a = postmaker.atlas_task({"name": "Carousel · World Atlas 02 Papua New Guinea · catch-up",
                          "text_content": "Images: btr-media/world-atlas/02-papua-new-guinea · caption: x\nMusic: “Song”, Band"})
assert a["key"] == "PapuaNewGuinea" and a["images"][7].endswith("world-atlas/02-papua-new-guinea/08.jpg") and a["music"]
tasks = [{"id": "A", "name": "Story · Poll · Ep Nov 3", "due_date": "2"}, {"id": "B", "name": "Carousel · Key moment · Ep Nov 3", "due_date": "1"},
         {"id": "C", "name": "Story · Poll · Ep Nov 10", "due_date": "3"}]
its = posts.episode_items(tasks, lambda t: "Nov 3" in t["name"])
assert set(its) == {"poll", "moment"} and its["poll"]["task"] == "A"
assert list(posts.default_items(2)) == ["moment", "topics", "teaser", "rapid", "qa", "ask"]
assert posts.gold_html("Where is my family? Where's my husband?", ["family?", "husband?"]).count('class="gold"') == 2
print("OK tasks")

# ---- content check: exact quotes only, times pinned, WATCH AT from the chapters -------------------------
cues = srt.parse("""1
00:00:10,000 --> 00:00:14,000
When you give yourself so much to the job, you are left empty.

2
00:02:25,000 --> 00:02:29,000
I thought I was the clever, special one, working by myself.

3
00:06:53,000 --> 00:06:56,000
Why are you here? Hell no. I want to win.
""")
said = srt.plain_text(cues)
res = {"moment": {"sentences": [{"text": "When you give yourself so much to the job,", "gold": ["job"]},
                                {"text": "you are left completely empty."}], "hook": "you are left empty.", "quote": "invented line"},
       "topics": {"items": [{"chapter": 1, "title": "Nobody wins alone", "quote": "I thought I was the clever, special one"},
                            {"chapter": 2, "title": "X", "quote": "made up words here"}]},
       "quote": {"quote": "Hell no. I want to win.", "label": "OTI"}}
errs = postmaker.Maker._check(res, ["moment", "topics", "quote"], said, [])
assert len(errs) == 3, errs                                  # sentence 2, the moment quote, topic 2
warn = postmaker.Maker._clean(res, ["moment", "topics", "quote"], said, cues, [["00:00", "Intro"], ["02:25", "Alone"], ["06:53", "Why"]])
assert len(res["moment"]["sentences"]) == 0 or len(res["moment"]["sentences"]) % 2 == 0
assert res["moment"]["quote"] == "" and res["topics"]["items"][0]["watch"] == "02:25" and len(res["topics"]["items"]) == 1
assert res["quote"]["t"] == 413.0, res["quote"]
print("OK content check")

# ---- captions (format of the validated Oti P2 posts) ----------------------------------------------------
c = posts.captions("moment", {"hook": "When you give yourself so much to the job, you are left empty.", "context": "why she walked away from Strictly",
                              "quote": "I have nothing to prove.", "question": "Have you ever felt this"}, "Oti Mabuse", "otimabuse", "2")
assert c["instagram"].startswith("“When you give") and "@otimabuse on why she walked away from Strictly: “I have nothing to prove.”" in c["instagram"]
assert "Have you ever felt this? Tell us in the comments." in c["instagram"] and c["instagram"].endswith("Full episode, part 2, on YouTube and Spotify, link in bio.")
assert "link in bio" not in c["tiktok"].lower() and "Oti Mabuse on" in c["tiktok"] and "#OtiMabuse" in c["tiktok"]
c = posts.captions("topics", {"hook": "Strictly, two wins, and why she walked away. Swipe through.", "summary": "From Kelvin to Bill, {guest} told us everything."},
                   "Oti Mabuse", "otimabuse", "2")
assert c["instagram"].split("\n\n")[0] == "Strictly, two wins, and why she walked away." and "@otimabuse told us" in c["instagram"]
print("OK captions")

# ---- shot choice ----------------------------------------------------------------------------------------
cands = [{"t": 9.0, "kind": "guest", "sharp": 50, "fh": .3, "cy": .35}, {"t": 11.0, "kind": "guest", "sharp": 90, "fh": .3, "cy": .35},
         {"t": 200.0, "kind": "guest", "sharp": 500, "fh": .3, "cy": .35}, {"t": 13.0, "kind": "both", "sharp": 80, "fh": .1, "cy": .4}]
r = posts.pick(cands, {"who": "guest", "t": 10.0, "win": 6, "after": True}, [])
assert r[0]["t"] == 11.0, r                                   # the guest while saying it, not the sharpest of the episode
assert all(abs(c["t"] - 11.0) >= 3 for c in posts.pick(cands, {"who": "guest", "t": 10.0, "win": 6, "after": True}, [11.0]))
assert posts.pick(cands, {"who": "guest", "t": None, "win": None}, [])[0]["t"] == 200.0
p = posts.place("x", (3840, 2160), (0, 0, 1080, 1920), {"cx": 0.7, "cy": 0.3})
assert p["h"] == 1920 and abs(-p["left"] + 540 - 0.7 * p["w"]) < 1   # face centred
print("OK shots")

# ---- render (needs Playwright + fonts) -----------------------------------------------------------------
if "--render" in sys.argv:
    from PIL import Image
    tmp = Path(tempfile.mkdtemp())
    img = tmp / "f.jpg"
    Image.new("RGB", (3840, 2160), (90, 60, 40)).save(img)
    sh = {"face": {"file": str(img), "size": [3840, 2160], "face": {"cx": .5, "cy": .35, "fh": .3}}}
    pg = posts.pages("poll", {"line": "Two Strictly wins.\nThen she walked away.", "question": "Would you have stayed?" * 3,
                              "footer": "x"}, sh, {"guest": "Oti Mabuse", "part": "2"})
    out = posts.render_pages(pg, tmp)
    assert Path(out[0]["file"]).exists() and Image.open(out[0]["file"]).size == (1080, 1920)
    posts.zones_preview(Path(out[0]["file"]), "poll", False, tmp / "z.jpg")
    print("OK render", out[0]["overflow"])

# ---- publishing tick: carousel by the API at its time, sticker story and TikTok sent to Loïc --------------
sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append(("msg", text, kw.get("reply_markup")))

    async def send_media_group(self, chat, media, **kw):
        sent.append(("group", len(media), None))

    async def send_photo(self, chat, f, **kw):
        sent.append(("photo", kw.get("caption", ""), None))


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
ep = bot.reg.episode("VIDPOSTS001")
ep["guest_name"] = "Oti Mabuse"
ep.save()
st = posts.PostState(ep)
now = posts.now()
jpg = Path(tempfile.mkdtemp()) / "s.jpg"
jpg.write_bytes(b"x")
st.data["items"] = {
    "moment": {"kind": "moment", "status": "ok", "task": "T1", "files": [str(jpg)] * 4, "drive": [{"id": f"D{i}"} for i in range(4)],
               "captions": {"instagram": "IG text", "tiktok": "TT text"}, "collab": ["otimabuse", "mariusiepure"],
               "at": (now + timedelta(minutes=10)).isoformat(), "tt_at": (now + timedelta(hours=2)).isoformat()},
    "poll": {"kind": "poll", "status": "ok", "task": "T2", "files": [str(jpg)], "drive": [{"id": "D9"}],
             "sticker": {"type": "sondage", "question": "Would you have stayed?", "options": ["Yes", "No"]},
             "at": (now - timedelta(minutes=1)).isoformat()},
}
st.save()
calls = []


class FakeIG:
    def __init__(self, sec):
        pass

    def carousel(self, urls, caption, collab):
        calls.append(("carousel", len(urls), caption, tuple(collab)))
        assert urls[0] == posts.drive_direct("D0")
        return "C1"

    def story(self, url):
        calls.append(("story", url))
        return "S1"

    def publish(self, cid):
        calls.append(("publish", cid))
        return {"id": "M1", "permalink": "https://instagram.com/p/x"}


import btrbot.instagram as instagram  # noqa: E402
instagram.Instagram = FakeIG
share.Secrets.get = lambda self, k, d=None: {"ig_token": "t", "ig_user": "u", "clickup_token": "pk_x"}.get(k, d)
marks = []
bot.maker().mark = lambda it, ig=False, tt=False, link="": marks.append((it.get("task"), ig, tt, link))
bot.ATLAS["at"] = 9e18                                      # no ClickUp in this test
bot.ATLAS["tasks"] = []


async def main():
    await bot.posts_tick(ctx)
    assert ("carousel", 4, "IG text", ("otimabuse", "mariusiepure")) in calls, calls
    assert not any(c[0] == "publish" for c in calls)                       # prepared, not yet published
    assert any(m[0] == "group" for m in sent) and any("Would you have stayed?" in (m[1] or "") for m in sent if m[0] == "msg")
    n = len(sent)
    await bot.posts_tick(ctx)
    assert len(sent) == n                                                  # the story is sent once
    s2 = posts.PostState(ep)
    s2.items["moment"]["at"] = (now - timedelta(minutes=1)).isoformat()
    s2.save()
    await bot.posts_tick(ctx)
    assert ("publish", "C1") in calls and ("T1", True, False, "https://instagram.com/p/x") in marks
    assert posts.PostState(ep).items["moment"]["ig"]["done"]
    # TikTok at its time
    s3 = posts.PostState(ep)
    s3.items["moment"]["tt_at"] = (now - timedelta(minutes=1)).isoformat()
    s3.save()
    await bot.posts_tick(ctx)
    assert any("TikTok" in (m[1] or "") and "TT text" in (m[1] or "") for m in sent if m[0] == "msg")
    # Loïc taps « Posté sur TikTok » / « Posté sur Instagram » (story)
    q = NS(edit_message_reply_markup=lambda *a, **k: asyncio.sleep(0))
    await bot.on_post_button(ctx, q, f"pst:ttd:{ep.video_id}:moment")
    await bot.on_post_button(ctx, q, f"pst:igd:{ep.video_id}:poll")
    s4 = posts.PostState(ep)
    assert s4.items["moment"]["status"] == "posted" and s4.items["poll"]["status"] == "posted"
    assert ("T1", False, True, "") in marks and ("T2", True, False, "") in marks
    # too late: never posted, Loïc told once
    s4.items["late"] = {"kind": "quote", "status": "ok", "task": "T3", "files": [str(jpg)], "drive": [{"id": "D"}],
                        "at": (now - timedelta(hours=13)).isoformat()}
    s4.save()
    await bot.posts_tick(ctx)
    await bot.posts_tick(ctx)
    assert sum("12 h de retard" in (m[1] or "") for m in sent if m[0] == "msg") == 1
    assert not any(c == ("story", posts.drive_direct("D")) for c in calls)
    print("OK publishing")

asyncio.run(main())

# ---- one slide's photo changes, the others stay ---------------------------------------------------------
assert posts.slide_sids("moment", 2, "bas") == ["m3"] and posts.slide_sids("moment", 1) == ["m0", "m1"]
assert posts.slide_sids("topics", 1) == ["cover"] and posts.slide_sids("topics", 8) == ["end"] and posts.slide_sids("topics", 4) == ["t2"]
assert posts.sid_slide("moment", "m3") == 2 and posts.sid_slide("topics", "t2") == 4 and posts.sid_slide("topics", "end") == 8
M = postmaker.Maker(NS(cfg=NS(ytdlp_cookies=None), llm=NS(open_eyes=lambda sheet: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])),
                    bot.cfg.data_dir)
ep2 = bot.reg.episode("VIDPOSTS002")
st2 = posts.PostState(ep2)
st2.data = {"items": {"moment": {"kind": "moment"}}, "content": {"moment": {"sentences": [{"text": "x", "t": 10.0 * i} for i in range(8)]}},
            "shots": {}}
pool = [{"t": float(t), "kind": "guest", "sharp": 100, "fh": .3, "cy": .35, "cx": .5, "fw": .2, "top": .2, "file": str(jpg)}
        for t in range(1, 120, 2)]
M._scan = lambda ep: [(c["t"], Path(c["file"])) for c in pool]
M._classify = lambda ep, fr, times: pool
import btrbot.frames as frames  # noqa: E402
frames.full_res_url = lambda vid, cookies: "url"
frames.grab = lambda src, t, out: Image.new("RGB", (3840, 2160)).save(out) or out
frames.face_sheet = lambda cands, out: out
M.refine = lambda shot: shot
from PIL import Image  # noqa: E402
M.shots(ep2, st2, ["moment"])
before = {k: v["t"] for k, v in st2.data["shots"].items()}
assert len(before) == 8
M.shots(ep2, st2, ["moment"], None, {"moment:m3"}, {"moment:m3": {"t": 100.0, "who": None}})
after = {k: v["t"] for k, v in st2.data["shots"].items()}
assert after["moment:m3"] != before["moment:m3"] and abs(after["moment:m3"] - 100) <= 20, after
assert all(after[k] == before[k] for k in before if k != "moment:m3")
print("OK one slide")

# ---- pulled back: the smaller face sets the size, the set around the bigger one is generated ------------
from btrbot import imaging  # noqa: E402
tmp = Path(tempfile.mkdtemp())
big, small = tmp / "big.jpg", tmp / "small.jpg"
Image.new("RGB", (3840, 2160), (120, 80, 60)).save(big)
Image.new("RGB", (3840, 2160), (60, 80, 120)).save(small)
sh = {"prev": {"file": str(small), "size": [3840, 2160], "face": {"cx": .5, "cy": .35, "fh": .2, "eyes": .32}},
      "face": {"file": str(big), "size": [3840, 2160], "face": {"cx": .5, "cy": .4, "fh": .4, "eyes": .36}}}
pg = posts.pages("chain", {"question": "Q?", "prev_guest": "Leila Stewart"}, sh, {"guest": "Oti Mabuse", "part": "2"})
p2 = pg[0]["p2"]
assert p2.get("gap_key") and abs(p2["h"] * 0.4 - pg[0]["p1"]["h"] * 0.2) < 2, (p2, pg[0]["p1"])   # same face size
imaging.fill_out = lambda md, img, region, max_side=1600: Image.new("RGB", (int(region[2] - region[0]), int(region[3] - region[1])))
M2 = postmaker.Maker(NS(cfg=NS(models_dir=tmp)), bot.cfg.data_dir)
assert M2.fill_gaps(pg, sh) and sh["face"]["ext"]
pg = posts.pages("chain", {"question": "Q?", "prev_guest": "Leila Stewart"}, sh, {"guest": "Oti Mabuse", "part": "2"})
assert pg[0]["p2"]["w"] == 538 and pg[0]["p2"]["left"] == 0 and not pg[0]["p2"].get("gap_key")
sh["face"]["zoom_adj"] = 0.8                                  # « moins zoomé » on the same photo
pg = posts.pages("chain", {"question": "Q?"}, sh, {"guest": "Oti Mabuse", "part": "2"})
assert pg[0]["p2"].get("gap_key")                             # a new framing: generated again
print("OK pull back")

# ---- a task goes « posted » once every planned platform is posted --------------------------------------
opts = lambda *names: {"options": [{"id": f"o{i}", "name": n, "orderindex": i} for i, n in enumerate(names)]}  # noqa: E731
T = lambda ig, tt, yt: {"custom_fields": [  # noqa: E731
    {"id": share.F_IG, "value": ig, "type_config": opts("Not planned", "To schedule", "Scheduled", "Posted")},
    {"id": share.F_TT, "value": tt, "type_config": opts("Not planned", "To schedule", "Scheduled", "Posted")},
    {"id": share.F_YT, "value": yt, "type_config": opts("Not planned", "To schedule", "Scheduled", "Posted")}]}
assert share.all_posted(T(3, 3, 3)) and share.all_posted(T(0, 3, "o3"))           # orderindex or option id
assert not share.all_posted(T(3, 2, 3)) and not share.all_posted(T(0, 0, 0))
assert share.all_posted({"custom_fields": [{"id": share.F_IG, "value": {"name": "Posted"}}]})
print("OK posted status")

# ---- the calendar decides which posts exist ------------------------------------------------------------
M3 = postmaker.Maker(NS(cfg=NS(), ep_number=lambda ep: 13), bot.cfg.data_dir)
ep3 = bot.reg.episode("VIDPOSTS003")
ep3["guest_name"] = "Oti Mabuse"
ep3.save()
M3.episode_tasks = lambda ep, tasks=None: {
    "topics": {"id": "TT", "name": "Carousel · Topics · Oti P2", "status": {"status": "generated"}, "text_content": "by hand"},
    "link": {"id": "TL", "name": "Story · Link · Oti P2", "status": {"status": "posted"}},
    "poll": {"id": "TP", "name": "Story · Poll · Oti P2", "status": {"status": "to generate"}}}
st3 = posts.PostState(ep3)
assert list(M3.plan(ep3, st3)) == ["poll"]                      # not the default rotation, not the hand-made ones
assert st3.items["poll"]["task"] == "TP"
assert list(M3.plan(ep3, st3, ["topics"])) == ["topics"] and st3.items["topics"]["task"] == "TT"   # asked: linked
print("OK calendar")

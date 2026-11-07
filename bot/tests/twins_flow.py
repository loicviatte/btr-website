"""Offline check of the re-uploaded episode flow (btrbot/twins.py + bot.ask_twin / on_twin_button / carry_twin).
YouTube is faked: nothing leaves the machine.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/twins_flow.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import twins  # noqa: E402

# ---- pure rules ------------------------------------------------------------------------------------
assert twins.iso_seconds("PT1H52M3S") == 6723 and twins.iso_seconds("PT45S") == 45 and twins.iso_seconds("") == 0
assert twins.norm_title("EP15_Lene_FINAL v2 (1).mp4") == twins.norm_title("EP15 Lene final")
assert twins.is_twin("EP15 Lene v2", 0, ["EP15 Lene"], 0) == "titre"
assert twins.is_twin("Export 0711", 6723, ["EP15 Lene"], 6724) == "durée"
assert twins.is_twin("Export 0711", 6723, ["EP15 Lene"], 6800) is None
assert twins.is_twin("Oti part 2", 6000, ["Oti part 1"], 6000) is None          # two parts never match
assert twins.is_twin("Short", 40, ["Other"], 40) is None                       # short clips never match on length
print("OK rules")

sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append((text, kw.get("reply_markup")))


class FakeQ:
    async def edit_message_reply_markup(self, m):
        pass


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
root = Path(bot.cfg.data_dir)
OLD, NEW, OTHER = "LENEV1aaaaa", "LENEV2bbbbb", "OTHERcccccc"

# V1: published episode with thumbnails, chapters, stories, a badge
ep = bot.reg.episode(OLD)
ep.data.update({"title": "EP15 Lene", "final": {"title": "Lene: Dancing is a language | BTR #15"},
                "description": "Lene talks…\n\n00:00 Intro\n12:00 Childhood", "chapters": [["00:00", "Intro"], ["12:00", "Childhood"]],
                "guest_name": "LENE", "release_at": "2026-11-10T18:00:00+00:00"})
ep.stage = "done"
ep.save()
(ep.dir / "render").mkdir()
(ep.dir / "render" / "thumb_youtube.jpg").write_bytes(b"jpg-v1")
(ep.dir / "posts.json").write_text(json.dumps({"items": {"s1": {"file": str(ep.dir / "posts" / "s1.jpg"), "vid": OLD}}}))
bot.reg.data.update({"seen": [OLD], "active": OLD, "topic_ep": {"stories": OLD}, "ep_msgs": {OLD: [[1, 2]]},
                     "initialised": True})
bot.reg.save()
# an unrelated episode that must never be touched
oth = bot.reg.episode(OTHER)
oth.data.update({"title": "EP14 Hannah", "guest_name": "HANNAH"})
oth.stage = "done"
oth.save()

V2 = {"id": NEW, "snippet": {"title": "EP15 Lene v2"}, "contentDetails": {"duration": "PT1H52M3S"},
      "status": {"privacyStatus": "unlisted", "uploadStatus": "processed"}}
YT = {OLD: {"snippet": {"title": "Lene: Dancing is a language | BTR #15", "description": "Lene talks…\n\n00:00 Intro",
                        "categoryId": "22", "tags": ["dancesport", "ballroom"],
                        "thumbnails": {"maxres": {"url": "https://i.ytimg.com/x.jpg"}}},
            "status": {"privacyStatus": "unlisted"}, "contentDetails": {"duration": "PT1H52M3S"}},
      NEW: {"snippet": {"title": "EP15 Lene v2", "description": "", "categoryId": "22"},
            "status": {"privacyStatus": "unlisted"}, "contentDetails": {"duration": "PT1H52M3S"}},
      OTHER: {"snippet": {"title": "EP14 Hannah"}, "status": {"privacyStatus": "public"},
              "contentDetails": {"duration": "PT1H10M"}}}
writes = []
bot.pipe.yt.video = lambda vid: YT[vid]
bot.pipe.yt.unlisted_ready = lambda: [V2]
bot.pipe.yt.unlisted_pending = lambda: []
bot.pipe.yt.update_metadata = lambda vid, t=None, d=None, snippet_from=None: writes.append(("meta", vid, t, d, (snippet_from or {}).get("tags")))
bot.pipe.yt.set_thumbnail = lambda vid, p: writes.append(("thumb", vid, Path(p).read_bytes()))
started = []


async def fake_start(ctx, vid, v):
    started.append(vid)
bot.poll_drive = lambda c: asyncio.sleep(0)
bot.shorts_sync = lambda c: asyncio.sleep(0)
bot.shorts_watch = lambda c: asyncio.sleep(0)
bot.poll_transcripts = lambda c: asyncio.sleep(0)


def buttons(markup):
    return [b.callback_data for row in markup.inline_keyboard for b in row] if markup else []


async def settle():
    for _ in range(50):                    # background jobs (bg → guarded) finish
        await asyncio.sleep(0.02)
        if not bot.RUNNING and not [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]:
            return


async def main():
    real_start = bot.start_new_video
    bot.start_new_video = fake_start
    # 1. the scan finds the V2 → question, nothing started
    await bot.poll_youtube(ctx)
    assert not started, started
    text, kb = sent[-1]
    assert "même titre" in text and OLD in text, text
    assert buttons(kb) == [f"tw:new:{NEW}", f"tw:old:{NEW}", f"tw:diff:{NEW}"], buttons(kb)
    # 2. « la 2 » → second question (what was made on the V1)
    await bot.on_twin_button(ctx, FakeQ(), f"tw:new:{NEW}")
    text, kb = sent[-1]
    assert "les 3 miniatures" in text and "les chapitres" in text and "stories" in text, text
    assert buttons(kb) == [f"tw:keep:{NEW}", f"tw:regen:{NEW}"]
    # 3. « reprendre la V1 » (through the chat tool, like a typed answer)
    h = bot.tool_handlers(ctx, [])
    out = await h["reupload_choice"]("keep")
    assert out.startswith("fait"), out
    await settle()
    text, kb = sent[-1]
    assert "repris pour la V2" in text and "miniature" in text and buttons(kb) == ["reels:propose"], text
    # files moved, ids rewritten, stub left
    new_dir, old_dir = root / "episodes" / NEW, root / "episodes" / OLD
    st = json.loads((new_dir / "state.json").read_text())
    assert st["video_id"] == NEW and st["replaces"] == OLD and st["stage"] == "done" and st["chapters"], st
    assert st["duration_s"] == 6723
    assert (new_dir / "render" / "thumb_youtube.jpg").read_bytes() == b"jpg-v1"
    posts = (new_dir / "posts.json").read_text()
    assert OLD not in posts and f"/episodes/{NEW}/posts" in posts, posts
    stub = json.loads((old_dir / "state.json").read_text())
    assert stub["stage"] == "replaced" and stub["replaced_by"] == NEW and "guest_name" not in stub
    assert sorted(p.name for p in old_dir.iterdir()) == ["state.json"]
    # registry follows
    r = bot.reg.data
    assert r["active"] == NEW and r["topic_ep"]["stories"] == NEW and NEW in r["ep_msgs"] and OLD not in r["ep_msgs"]
    assert not r.get("twins")
    # YouTube: the V1's text, tags and the bot's thumbnail on the V2, nothing written on the V1 or another video
    assert writes[0] == ("meta", NEW, YT[OLD]["snippet"]["title"], YT[OLD]["snippet"]["description"], ["dancesport", "ballroom"]), writes
    assert writes[1] == ("thumb", NEW, b"jpg-v1"), writes
    assert all(w[1] == NEW for w in writes)
    # the other episode untouched
    assert json.loads((root / "episodes" / OTHER / "state.json").read_text())["guest_name"] == "HANNAH"
    # 4. the stub is never offered again as a twin, and a click twice is harmless
    assert twins.find(root, "ZZZZZZZZZZZ", "EP15 Lene", 6723) is not None   # the moved one (V2) matches…
    assert twins.find(root, "ZZZZZZZZZZZ", "EP15 Lene", 6723)["vid"] == NEW  # …never the stub
    n = len(sent)
    await bot.on_twin_button(ctx, FakeQ(), f"tw:keep:{NEW}")
    assert len(sent) == n + 1 and "déjà réglé" in sent[-1][0]
    print("OK keep V1 work")

    # 5. « regenerate » and « different » paths on a fresh pair
    A, B_ = "AAAAAAAAAAA", "BBBBBBBBBBB"
    e = bot.reg.episode(A)
    e.data.update({"title": "EP16 Max", "guest_name": "MAX", "final": {"title": "Max"}})
    e.stage = "thumbs_proposed"
    e.save()
    v = {"id": B_, "snippet": {"title": "EP16 Max"}, "contentDetails": {"duration": "PT2H"}}
    YT[A] = {"contentDetails": {"duration": "PT1H"}}
    await bot.ask_twin(ctx, B_, v, twins.find(root, B_, "EP16 Max", 7200, None))
    await bot.on_twin_button(ctx, FakeQ(), f"tw:new:{B_}")
    await bot.on_twin_button(ctx, FakeQ(), f"tw:regen:{B_}")
    assert started == [B_], started
    assert (root / "replaced" / A / "state.json").exists()
    assert json.loads((root / "episodes" / A / "state.json").read_text())["stage"] == "replaced"
    C, D = "CCCCCCCCCCC", "DDDDDDDDDDD"
    e = bot.reg.episode(C)
    e.data.update({"title": "EP17 Zoe part 1", "guest_name": "ZOE"})
    e.stage = "done"
    e.save()
    await bot.ask_twin(ctx, D, {"id": D, "snippet": {"title": "EP17 Zoe part 1"}, "contentDetails": {}},
                       {"vid": C, "why": "titre"})
    await bot.on_twin_button(ctx, FakeQ(), f"tw:diff:{D}")
    assert started == [B_, D] and json.loads((root / "episodes" / C / "state.json").read_text())["stage"] == "done"
    print("OK regen / different")

    # 6. a normal new video still starts as before (real start_new_video, SRT path off)
    bot.start_new_video = real_start
    bot.pick_pending = lambda title: None
    E = "EEEEEEEEEEE"
    await bot.start_new_video(ctx, E, {"snippet": {"title": "EP18 Nobody"}, "contentDetails": {"duration": "PT1H5M"}})
    s = json.loads((root / "episodes" / E / "state.json").read_text())
    assert s["stage"] == "waiting_transcript" and s["duration_s"] == 3900 and bot.reg.active == E
    print("OK new video")

    # 7. boot one-shot: a Lene V2 already started by the old bot (axes made) → set aside, question asked
    L1, L2 = "LENE1xxxxxx", "LENE2yyyyyy"
    e1 = bot.reg.episode(L1)
    e1.data.update({"title": "EP15 LENE VIDEO", "guest_name": "LENE", "created": time.time() - 5 * 86400})
    e1.stage = "done"
    e1.save()
    e2 = bot.reg.episode(L2)
    e2.data.update({"title": "EP15 LENE VIDEO v2", "axes": [1, 2, 3]})
    e2.stage = "axes_proposed"
    e2.save()
    (e2.dir / "captions_youtube.srt").write_text("x")
    bot.reg.active = L2
    YT[L1] = {"snippet": {"title": "Lene | BTR #15"}, "contentDetails": {"duration": "PT1H40M"}}
    YT[L2] = {"snippet": {"title": "EP15 LENE VIDEO v2"}, "contentDetails": {"duration": "PT1H40M1S"},
              "status": {"privacyStatus": "unlisted"}}
    await bot.twin_lene_1107(ctx)
    assert not (root / "episodes" / L2).exists() and (root / "replaced" / f"{L2}_fresh" / "captions_youtube.srt").exists()
    assert bot.reg.active == L1 and bot.reg.data["twins"][L2]["old"] == L1, bot.reg.data.get("twins")
    assert buttons(sent[-1][1])[0] == f"tw:new:{L2}"
    await bot.on_twin_button(ctx, FakeQ(), f"tw:new:{L2}")
    await bot.on_twin_button(ctx, FakeQ(), f"tw:keep:{L2}")
    await settle()
    assert json.loads((root / "episodes" / L2 / "state.json").read_text())["replaces"] == L1 and bot.reg.active == L2
    print("OK boot one-shot")


asyncio.run(main())

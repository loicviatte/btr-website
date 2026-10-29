"""Offline walk through the reels flow on Telegram (YouTube, Claude and the render mocked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=/tmp/btr-test python tests/reel_flow.py <some.mp4>
"""
import asyncio
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
import btrbot.reels as R  # noqa: E402
from btrbot.state import Reels  # noqa: E402

VIDEO = sys.argv[1]
sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append(("msg", text[:140].replace("\n", " | "), bool(kw.get("reply_markup"))))

    async def send_video(self, chat, f, caption=None, **kw):
        sent.append(("video", (caption or "")[:80].replace("\n", " | "), bool(kw.get("reply_markup"))))

    async def send_document(self, chat, f, filename=None, caption=None, **kw):
        sent.append(("doc", filename))

    async def send_chat_action(self, *a, **k):
        pass


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
p = bot.pipe
EP = bot.reg.episode("VIDREEL0001")
EP["title"] = "Oti Mabuse Part 2"
EP["guest_name"] = "Oti Mabuse"
EP.save()
p.reel_episode = lambda vid, active: EP
LIST_ID = [100]


def cands(ep, n=10):
    LIST_ID[0] += 1
    return {"id": LIST_ID[0], "sel": [], "items": {},
            "cands": [{"n": i, "start_s": 60.0 * i, "end_s": 60.0 * i + 40, "title": f"Moment {i}", "first_words": "a",
                       "last_words": "b", "hook": "I got a yacht for my husband", "why": "ça fait débat " * 30,
                       "verified": i != 3} for i in range(1, 11)]}


p.reel_candidates = cands
rendered = []


def render(ep, cand, shift, cuts, fixes=(), note=""):
    rendered.append((cand["n"], tuple(shift), tuple(cuts)))
    f = Path(bot.cfg.data_dir) / f"reel_{cand['n']}.mp4"
    shutil.copy(VIDEO, f)
    return {"file": str(f), "duration": 15.4, "status": "preview", "confidence": 95, "shots": {"guest": 2, "split": 1},
            "said": "I got a yacht", "shown": 40, "spoken": 51, "missing_cuts": list(cuts[1:])}


p.render_reel = render
subbed = []


def resub(ep, cand, fixes, note=""):
    subbed.append((cand["n"], tuple((f["from"], f["to"]) for f in fixes), note))
    f = Path(bot.cfg.data_dir) / f"reel_{cand['n']}.mp4"
    return {"file": str(f), "duration": 15.4, "said": "and Motsi", "shown": 2, "spoken": 2, "fixes_not_found": [],
            "on_screen": ["and / MOTSI"]}


p.reel_subtitles = resub
p.reel_feedback = lambda item, fb: ({"fixes": [{"from": "Muti", "to": "Motsi"}], "relayout": False, "reply": "Je remplace Muti par Motsi."}
                                    if "Motsi" in fb else {"fixes": [], "relayout": True, "layout_note": "keep the question on one line",
                                                           "reply": "Je remets la question sur une ligne."})
p.reel_captions = lambda ep, said: {"instagram": "Hook IG", "tiktok": "Hook TT #dancesport"}
slim_calls = []
R.slim = lambda work, keep_final=True: slim_calls.append(keep_final)


def store():
    return Reels.of(EP).data


async def press(data):
    async def ans():
        pass

    async def edit(markup):
        sent.append(("edit", sum(len(r) for r in markup.inline_keyboard)))
    q = NS(data=data, answer=ans, edit_message_reply_markup=edit)
    await bot.on_button(NS(effective_chat=NS(id=42), callback_query=q), ctx)


async def settle():
    for _ in range(200):
        await asyncio.sleep(0.02)
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if not pending and not bot.LOCK.locked():
            break
    await asyncio.sleep(0.05)


async def main():
    await bot.propose_reels(ctx)
    lid = store()["id"]
    for n in (1, 3, 4, 3):          # 3 ticked then unticked
        await press(f"rsel:{lid}:{n}")
    assert store()["sel"] == [1, 4], store()["sel"]
    await press(f"rgo:{lid}")
    await settle()
    assert [r[0] for r in rendered] == [1, 4], rendered
    await press(f"rok:{lid}:1")
    await press(f"rno:{lid}:4")
    await settle()
    assert store()["items"]["1"]["status"] == "ok" and store()["items"]["4"]["status"] == "dropped", store()["items"]
    h = bot.tool_handlers(ctx, [])
    out = await h["reel_adjust"](1, start_shift=-2, end_shift=1.5, cut="you know")
    await settle()
    out = await h["reel_adjust"](1, cut="nowhere")
    await settle()
    it = store()["items"]["1"]
    assert it["shift"] == [-2.0, 1.5] and it["cuts"] == ["you know", "nowhere"], it
    assert rendered[-1] == (1, (-2.0, 1.5), ("you know", "nowhere")), rendered
    assert it["missing_cuts"] == ["nowhere"]
    # a dropped reel queued again is rendered; an old button from a previous list is refused
    out2 = await h["reels_select"]([2, 4, 99])
    await settle()
    assert [r[0] for r in rendered[-2:]] == [2, 4], rendered
    await bot.propose_reels(ctx)               # a new list
    before = len(rendered)
    await press(f"rok:{lid}:2")
    await press(f"rgo:{lid}")
    await settle()
    assert len(rendered) == before and store()["id"] != lid
    assert "ancienne liste" in sent[-1][1], sent[-1]
    # dropping a reel that was never rendered, then selecting it, does not crash
    lid2 = store()["id"]
    await press(f"rno:{lid2}:5")
    await settle()
    out3 = await h["reels_select"]([5])
    await settle()
    assert rendered[-1][0] == 5, rendered
    # double tap on « Monter la sélection »: each reel is made once
    before = len(rendered)
    await press(f"rsel:{lid2}:6")
    await press(f"rgo:{lid2}")
    await press(f"rgo:{lid2}")
    await settle()
    assert [r[0] for r in rendered[before:]] == [6], rendered[before:]
    await press("rgo")                          # a button from before the list ids
    assert "ancienne liste" in sent[-1][1], sent[-1]
    # subtitles feedback: only the subtitles are redone, the word fix is kept for later full edits
    before_full = len(rendered)
    out4 = await h["reel_subtitles"](6, "c'est Motsi pas Muti")
    await settle()
    out5 = await h["reel_subtitles"](6, "problème de sous-titre à why are you here")
    await settle()
    assert len(rendered) == before_full, rendered
    assert subbed[0] == (6, (("Muti", "Motsi"),), ""), subbed
    assert subbed[1] == (6, (("Muti", "Motsi"),), "keep the question on one line"), subbed
    out6 = await h["reel_adjust"](6, end_shift=0.4)
    await settle()
    assert len(rendered) == before_full + 1 and rendered[-1][1] == (0.0, 0.4), rendered
    print("subtitles →", out4, "|", out5)
    print("context:\n" + bot.reels_context())
    print("select →", out2, "|", out3)
    assert slim_calls == [True, False], slim_calls        # reel 5 had no file to clean


try:
    asyncio.run(main())
except Exception:
    print("--- last messages ---")
    for x in sent[-8:]:
        print(x)
    raise
for s in sent:
    print(s)
print("OK")

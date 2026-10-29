"""Offline walk through the reels flow on Telegram (YouTube, Claude and the render mocked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=/tmp/btr-test python tests/reel_flow.py <some.mp4>
"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot.state import Reels as R2  # noqa: E402

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


def cands(ep, n=10):
    R2.of(ep).data = {"cands": [{"n": i, "start_s": 60.0 * i, "end_s": 60.0 * i + 40, "title": f"Moment {i}",
                              "hook": "I got a yacht for my husband", "why": "ça fait débat", "verified": i != 3}
                             for i in range(1, 11)], "sel": [], "items": {}}
    R2.of(ep).save()
    return R2.of(ep).data["cands"]


p.reel_candidates = cands
rendered = []


def render(ep, n):
    rendered.append(n)
    item = R2.of(ep).data["items"].setdefault(str(n), {"shift": [0.0, 0.0], "cuts": []})
    item.update(file=VIDEO, duration=15.4, status="preview", confidence=95, shots={"guest": 2, "split": 1},
                said="I got a yacht", shown=40, spoken=51, captions={"instagram": "Hook IG", "tiktok": "Hook TT #dancesport"})
    R2.of(ep).save()
    return item


p.render_reel = render
p.asr_release = lambda: None
slim_calls = []
import btrbot.reels as R  # noqa: E402
R.slim = lambda work, keep_final=True: slim_calls.append(keep_final)


async def press(data):
    async def ans():
        pass

    async def edit(markup):
        sent.append(("edit", sum(len(r) for r in markup.inline_keyboard)))
    q = NS(data=data, answer=ans, edit_message_reply_markup=edit)
    await bot.on_button(NS(effective_chat=NS(id=42), callback_query=q), ctx)


async def settle():
    for _ in range(50):
        await asyncio.sleep(0.02)
        if not bot.RUNNING and not bot.LOCK.locked():
            break
    await asyncio.sleep(0.05)


async def main():
    await bot.propose_reels(ctx)
    for n in (1, 3, 4, 3):          # 3 ticked then unticked
        await press(f"rsel:{n}")
    assert R2.of(EP).data["sel"] == [1, 4], R2.of(EP).data["sel"]
    await press("rgo")
    await settle()
    assert rendered == [1, 4], rendered
    await press("rok:1")
    await press("rno:4")
    assert R2.of(EP).data["items"]["1"]["status"] == "ok" and R2.of(EP).data["items"]["4"]["status"] == "dropped"
    h = bot.tool_handlers(ctx, [])
    out = await h["reel_adjust"](1, start_shift=-2, end_shift=1.5, cut="you know")
    await settle()
    it = R2.of(EP).data["items"]["1"]
    assert it["shift"] == [-2.0, 1.5] and it["cuts"] == ["you know"], it
    assert rendered == [1, 4, 1], rendered
    out2 = await h["reels_select"]([2, 99])
    await settle()
    assert rendered[-1] == 2, rendered
    print("context:\n" + bot.reels_context())
    print("adjust →", out, "| select →", out2)
    assert slim_calls == [True, False], slim_calls


asyncio.run(main())
for s in sent:
    print(s)
print("OK")

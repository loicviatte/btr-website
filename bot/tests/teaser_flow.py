"""Offline check of the teaser: moments found in the transcript, pieces put together + « Episode out now » end screen.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/teaser_flow.py [out_dir]
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import reels as R  # noqa: E402

pipe = bot.pipe
ep = bot.reg.episode("VIDTEASE001")
ep["guest_name"], ep["part"] = "Oti Mabuse", "2"
ep.save()
srt_text = []
lines = ["Hello and welcome.", "I was the unknown one on Strictly.", "Nobody knew who I was at all.", "Filler talk here.",
         "Judges never told me the truth.", "More filler.", "I cried in the car park that night.", "Filler again.",
         "And then everything changed for me.", "Thanks for having me."]
for i, l in enumerate(lines):
    a, b = 60 + i * 10, 60 + i * 10 + 4
    srt_text.append(f"{i + 1}\n00:{a // 60:02d}:{a % 60:02d},000 --> 00:{b // 60:02d}:{b % 60:02d},000\n{l}\n")
ep.file("captions_davinci.srt").write_text("\n".join(srt_text))


class LLM:
    def teaser_moments(self, *a, **k):
        return [{"start": "01:10", "end": "01:14", "first_words": "I was the unknown one", "last_words": "one on Strictly", "line": "x"},
                {"start": "01:20", "end": "01:24", "first_words": "Nobody knew who I was", "last_words": "who I was at all"},
                {"start": "05:00", "end": "05:04", "first_words": "words that do not exist anywhere", "last_words": "nope"},
                {"start": "01:40", "end": "01:44", "first_words": "Judges never told me", "last_words": "told me the truth"},
                {"start": "02:00", "end": "02:04", "first_words": "I cried in the car park", "last_words": "park that night"},
                {"start": "02:20", "end": "02:24", "first_words": "And then everything changed", "last_words": "changed for me"}]
pipe.llm = LLM()
ms = pipe.teaser_moments(ep)
assert len(ms) == 5 and all(m["start_s"] in (70, 80, 100, 120, 140) for m in ms), ms
assert ms[0]["end_s"] == 74.0, ms[0]
print("OK moments", [(m["start_s"], m["end_s"]) for m in ms])

made = []


def fake_render(ep_, cand, shift, cuts):
    wd = pipe.reel_work(ep_, cand["n"])
    wd.mkdir(parents=True, exist_ok=True)
    d = cand["end_s"] - cand["start_s"]
    f = wd / f"BTR_reel_{cand['n']}.mp4"
    color = ["red", "green", "blue", "orange", "purple"][len(made) % 5]
    for out, txt in ((wd / "base.mp4", False), (f, True)):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={color}:s=1080x1920:r=25:d={d}",
                        "-f", "lavfi", "-i", f"sine=f={300 + 100 * len(made)}:d={d}", "-shortest", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", out], check=True)
    made.append(cand["n"])
    return {"file": str(f), "duration": d}
pipe.render_reel = fake_render
res = pipe.render_teaser(ep, ms)
dur = R.probe(Path(res["file"]))["duration"]
assert abs(dur - (5 * 4 + 3.5)) < 0.4, (dur, res)
assert made == [1070, 1080, 1100, 1120, 1140], made
assert (ep.dir / "teaser" / "end.jpg").exists()
# a second run with one moment changed renders only that one
made.clear()
ms[2] = dict(ms[2], end_s=103.5)
pipe.render_teaser(ep, ms)
assert made == [1100], made
print("OK render", res)
if len(sys.argv) > 1:
    import shutil
    shutil.copy(res["file"], sys.argv[1])
    shutil.copy(ep.dir / "teaser" / "end.jpg", Path(sys.argv[1]).with_suffix(".jpg"))

# ── Telegram: moments listed, video sent with ✅ / 🔁, feedback keeps the previous moments in the request ──
import asyncio  # noqa: E402
from types import SimpleNamespace as NS  # noqa: E402

said, videos, asked = [], [], []


async def say(ctx, text, **kw):
    said.append(text)
bot.say = say


class TB:
    async def send_video(self, chat, f, **kw):
        videos.append(kw)
        return NS(chat_id=chat, message_id=99)


def tm(ep_, fb=""):
    asked.append(fb)
    return ms
pipe.teaser_moments = tm
pipe.render_teaser = lambda ep_, m: res
asyncio.run(bot.teaser_make(NS(bot=TB()), ep))
assert videos and videos[0]["reply_markup"].inline_keyboard[0][0].callback_data == "tz:ok:VIDTEASE001"
assert "5 moments" in said[-1] and "<code>01:10</code>" in said[-1], said[-1]
asyncio.run(bot.teaser_make(NS(bot=TB()), ep, "remplace le moment 3"))
assert "remplace le moment 3" in asked[-1] and "Previous moments" in asked[-1] and "I was the unknown one" in asked[-1]
assert bot.teaser_state(ep)["status"] == "preview" and bot.teaser_state(ep)["feedback"] == ["remplace le moment 3"]
print("OK telegram")

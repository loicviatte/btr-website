"""Offline check of the photo selection for a carousel / story slide (« 🎞️ Sélection », tools post_photo_choices /
post_photo_pick): numbered album, number buttons, the pick lands on its slide only, guard on a validated post.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/post_choices.py
"""
import asyncio
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import posts  # noqa: E402

sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append(("msg", text, kw.get("reply_markup")))
        return NS(chat_id=chat, message_id=len(sent))

    async def send_media_group(self, chat, media, **kw):
        sent.append(("group", [m.caption for m in media], None))

    async def send_photo(self, chat, f, **kw):
        sent.append(("photo", kw.get("caption", ""), None))


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
ep = bot.reg.episode("VIDCHOICE01")
ep["guest_name"] = "Oti Mabuse"
ep.save()
tmp = Path(tempfile.mkdtemp())
imgs = []
for i in range(11):
    p = tmp / f"s{i}.jpg"
    Image.new("RGB", (3840, 2160), (20 * i, 60, 40)).save(p)
    imgs.append(p)
st = posts.PostState(ep)
shot = lambda i, who="guest": {"file": str(imgs[i]), "t": 100.0 * i, "size": [3840, 2160], "who": who,  # noqa: E731
                               "face": {"cx": .5, "cy": .35, "fh": .3}}
st.data["items"] = {"topics": {"kind": "topics", "status": "draft", "files": [str(imgs[0])] * 8, "made": 1},
                    "moment": {"kind": "moment", "status": "draft", "files": [str(imgs[0])] * 4, "made": 1}}
st.data["content"] = {"topics": {"items": [{"title": f"T{i}", "quote": "q"} for i in range(6)]}}
st.data["shots"] = {"topics:cover": shot(0), "topics:t0": shot(0, "both"), "moment:m0": shot(0), "moment:m1": shot(0)}
st.save()
asked = []


def fake_choices(ep_, st_, sid, who=None, n=10, want=""):
    asked.append((sid, who, want))
    out = []
    for i in range(1, 11):
        s = dict(shot(i, who or st_.data["shots"][sid]["who"]), n=i, smile=i in (3, 7), label=str(imgs[i]))
        out.append(s)
    st_.data.setdefault("choices", {})[sid] = {"ts": posts.stamp() + len(asked), "who": out[0]["who"], "items": out}
    st_.save()
    return out


rendered = []
bot.maker().choices = fake_choices
bot.maker().render = lambda ep_, st_, keys: rendered.append(keys)


async def main():
    # « 🎞️ Sélection » on the Topics preview: slide picker (8 slides), then slide 1 → album of 10 numbered photos
    assert any(b.callback_data.startswith("pst:sel:") for b in bot.post_buttons(ep.video_id, "topics", "topics", False).inline_keyboard[0])
    await bot.choices_picker(ctx, ep, "topics")
    kb = sent[-1][2].inline_keyboard
    assert [b.callback_data for row in kb for b in row][0] == f"pst:ss:{ep.video_id}:topics:1", kb
    await bot.posts_choices(ctx, ep, "topics", [1])
    grp = [m for m in sent if m[0] == "group"][-1][1]
    assert len(grp) == 10 and grp[0] == "1 · 01:40" and grp[2].endswith("sourire"), grp
    msg = sent[-1]
    assert "slide 1" in msg[1] and "2 avec le sourire" in msg[1], msg[1]
    btns = [b.callback_data for row in msg[2].inline_keyboard for b in row]
    assert btns[3] == f"pst:pk:{ep.video_id}:topics:cover:4" and len(btns) == 10, btns
    assert asked[-1] == ("topics:cover", None, "")

    # « la 4 » → photo n° 4 on the cover, nothing else changed, history keeps the old one
    await bot.posts_pick(ctx, ep, "topics", "topics:cover", 4)
    st2 = posts.PostState(ep)
    assert st2.data["shots"]["topics:cover"]["t"] == 400.0 and st2.data["shots"]["topics:t0"]["t"] == 0.0
    assert st2.data["history"]["topics:cover"][-1]["t"] == 0.0 and rendered[-1] == ["topics"]
    assert "photo n° 4 posée sur la slide 1" in sent[-1][1], sent[-1][1]
    await bot.posts_pick(ctx, ep, "topics", "topics:cover", 42)
    assert "pas de photo n° 42" in sent[-1][1]

    # Key moment slide 1 without part: « haut ou bas ? »; then the bottom photo
    await bot.posts_choices(ctx, ep, "moment", [1])
    assert "haut ou du bas" in sent[-1][1]
    await bot.posts_choices(ctx, ep, "moment", [1], "bas")
    assert asked[-1][0] == "moment:m1" and "slide 1 (bas)" in sent[-1][1]

    # tool post_photo_pick finds the latest selection of the post; a validated post asks Oui / Non first
    h = bot.tool_handlers(ctx, [])
    started = []
    bot.bg = lambda ctx_, label, coro, limit=None: (started.append(label), coro.close(), "lancé")[2]
    r = await h["post_photo_pick"]("topics", 7)
    assert r == "lancé" and started[-1].startswith("Photo n° 7"), (r, started)
    st3 = posts.PostState(ep)
    st3.items["topics"]["status"] = "ok"
    st3.save()
    r = await h["post_photo_pick"]("topics", 7, slide=1)
    assert "confirmation" in r and "punl:y:" in sent[-1][2].inline_keyboard[0][0].callback_data, r
    tok = sent[-1][2].inline_keyboard[0][0].callback_data.split(":")[2]
    assert bot.reg.data["post_unlock"][tok]["args"] == {"sid": "topics:cover", "n": 7}
    r = await h["post_photo_choices"]("topics", slides=[3], want="elle rit")
    assert r == "lancé" and started[-1].startswith("Sélection de photos")
    print("OK post choices")


asyncio.run(main())

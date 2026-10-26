"""Offline walk through the Telegram flow with YouTube/Claude mocked."""
import asyncio, sys
from pathlib import Path
from types import SimpleNamespace as NS
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot

sent = []
class FakeBot:
    async def send_message(self, chat, text, **kw): sent.append(("msg", text[:160].replace("\n"," | "), bool(kw.get("reply_markup"))))
    async def send_media_group(self, chat, media): sent.append(("album", len(media)))
    async def send_photo(self, chat, f, caption=None): sent.append(("photo", caption))
    async def send_document(self, chat, f, filename=None, caption=None): sent.append(("doc", filename))
ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
p = bot.pipe
p.yt = NS(unlisted_ready=lambda: [{"id": "VID00000001", "snippet": {"title": "EP13 Peter Nash raw"}}],
          video=lambda v: {"snippet": {"title": "EP13", "description": "old"}})
p.fetch_transcript = lambda ep: True
def axes(ep):
    ep["guest_name"] = "Peter Nash"
    ep["axes"] = [{"angle": "a1", "quote": "People were breaking the rules", "top": "People were", "key": "breaking", "bottom": "the rules", "timestamp": "00:02", "title": "T1", "why": "w", "verified": True},
                  {"angle": "a2", "quote": "x", "top": "x", "key": "Y", "bottom": "z", "timestamp": "00:04", "title": "T2", "why": "w", "verified": False}]
p.propose_axes = axes
p.refine = lambda ep, m: {"reply": "ok", "axes": None, "final": None}
p.llm = NS(pick_frames=lambda *a, **k: {"best": [1]}, _ask=lambda s: "new desc {CHAPTERS}")
p.description = lambda ep: "Hook\n{CHAPTERS}\nLinks"
p.publish = lambda ep: None
p.chapters = lambda ep: [["00:00", "Intro"], ["00:10", "Breaking the rules"]]
p.publish_chapters = lambda ep, ch: "desc"
upd = NS(effective_chat=NS(id=42), callback_query=None, message=None)
async def press(data):
    async def ans(): pass
    upd.callback_query = NS(data=data, answer=ans)
    await bot.on_button(upd, ctx)
async def main():
    bot.reg.data["initialised"] = True
    await bot.poll_youtube(ctx)
    await press("axis:0")
    await press("pick:guest:0")
    await press("pick:marius:0")
    await press("publish")
    await press("chapters_ok")
    print("stage:", bot.reg.episode("VID00000001").stage)
asyncio.run(main())
for s in sent: print(s)

"""Offline check: a change asked on a scheduled / published carousel → « Tu veux vraiment le modifier ? » Oui / Non;
Oui = back to preview (ClickUp « generated », fields To do), the change runs with its parameters; revalidated after its
date = a new date is asked, nothing published meanwhile (ClickUp, Instagram, renders faked).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/post_unlock.py
"""
import asyncio
import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import btrbot.bot as bot  # noqa: E402
from btrbot import posts, share  # noqa: E402

sent = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        sent.append((text, kw.get("reply_markup")))

    async def send_media_group(self, chat, media, **kw):
        pass

    async def send_photo(self, chat, f, **kw):
        pass


class FakeCU:
    def __init__(self):
        self.t = {"id": "T1", "name": "Carousel · Topics · Oti P2", "status": {"status": "posted"},
                  "due_date": str(int((posts.now() - timedelta(hours=3)).timestamp() * 1000)),
                  "custom_fields": [{"id": share.F_IG, "value": share.IG_POSTED, "type_config": {"options": [
                      {"id": share.IG_POSTED, "name": "Posted"}, {"id": share.IG_TODO, "name": "To do"}]}}]}
        self.calls = []

    def task(self, tid):
        return self.t

    def tasks(self):
        return [self.t]

    def update(self, tid, **f):
        self.calls.append(("update", f))
        if "status" in f:
            self.t["status"] = {"status": f["status"]}
        if "due_date" in f:
            self.t["due_date"] = str(f["due_date"])

    def set_field(self, tid, fid, v):
        self.calls.append(("field", fid, v))


ctx = NS(bot=FakeBot(), args=[])
bot.cfg.chat_id = 42
cu = FakeCU()
M = bot.maker()
M.clickup = lambda: cu
bot.CU_CACHE.update(at=9e18, tasks=[cu.t])
ep = bot.reg.episode("VIDUNLOCK01")
ep["guest_name"] = "Oti Mabuse"
ep.save()
jpg = Path(tempfile.mkdtemp()) / "s.jpg"
jpg.write_bytes(b"x")
st = posts.PostState(ep)
st.data["items"] = {"topics": {"kind": "topics", "status": "ok", "task": "T1", "files": [str(jpg)] * 8,
                               "at": cu.t and (posts.now() - timedelta(hours=3)).isoformat(),
                               "ig": {"done": True, "link": "https://www.instagram.com/p/DfPAlooG2IU/"},
                               "tt": {"sent": True}}}
st.save()
ran = []


async def fake_photos(ctx, ep, k, slides, part=None, at=None, who=None, size=None):
    ran.append((k, slides, part))


bot.posts_photos = fake_photos
bot.ep_tasks = lambda ep: {"topics": {"status": (cu.t["status"] or {}).get("status")}}
handlers = bot.tool_handlers(ctx, [])


def last_buttons():
    for text, kb in reversed(sent):
        if kb:
            return text, [b.callback_data for row in kb.inline_keyboard for b in row]
    return None, []


async def main():
    out = await handlers["post_photos"](key="topics", slides=[1, 7])
    assert "confirmation" in out, out
    text, cbs = last_buttons()
    assert "déjà publié sur Instagram" in text and "DfPAlooG2IU" in text and "supprime-le toi-même" in text, text
    q = NS(edit_message_reply_markup=lambda *a, **k: asyncio.sleep(0))
    # Non: nothing changes
    await bot.on_unlock_button(ctx, q, [c for c in cbs if c.startswith("punl:n:")][0])
    assert posts.PostState(ep).items["topics"]["ig"]["done"] and not ran and not cu.calls
    # Oui: reopened, ClickUp back, the same change runs
    await handlers["post_photos"](key="topics", slides=[1, 7])
    _, cbs = last_buttons()
    await bot.on_unlock_button(ctx, q, [c for c in cbs if c.startswith("punl:y:")][0])
    for _ in range(20):
        await asyncio.sleep(0.05)
        if ran:
            break
    it = posts.PostState(ep).items["topics"]
    assert it["status"] == "draft" and "ig" not in it and "tt" not in it and it["ig_old"] and "reopened" in it, it
    assert ("update", {"status": "generated"}) in cu.calls and ("field", share.F_IG, share.IG_TODO) in cu.calls
    assert ran == [("topics", [1, 7], None)], ran
    assert bot.post_guard(ep, "topics") is None                        # a draft now: changes run straight away
    # revalidation with the old date gone: no date kept, a new one asked
    M.file = lambda ep, st, k: (st.items[k].update(status="ok", at=posts.now().isoformat()), st.save(), st.items[k])[2]
    bot.plan_refresh = lambda: asyncio.sleep(0)
    await bot.post_validate(ctx, ep, "topics")
    it = posts.PostState(ep).items["topics"]
    assert it["status"] == "ok" and it.get("need_date") and not it.get("at"), it
    text, cbs = last_buttons()
    assert "ancienne date est passée" in text and cbs[0].startswith("punl:d:"), text
    await bot.posts_tick(ctx)                                          # nothing goes out without a date
    assert "ig" not in posts.PostState(ep).items["topics"] or not posts.PostState(ep).items["topics"]["ig"].get("cid")
    # the date offered
    await bot.on_unlock_button(ctx, q, cbs[0])
    it = posts.PostState(ep).items["topics"]
    assert it.get("at") and not it.get("need_date") and posts.due(cu.t) > posts.now(), it
    print("OK post unlock")


asyncio.run(main())

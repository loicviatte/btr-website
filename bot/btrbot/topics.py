"""The BTR Studio Telegram group: one forum topic per kind of work, like separate bots (Loïc 31.10).

Loïc creates a group, turns on Topics, makes the bot admin and writes anything in it: the bot keeps the group
(data/topics.json) and creates its topics. From then on everything the bot used to send to his private chat goes to
the group, in the topic of the work (TOPIC, a context variable): the reel / cover / Shorts / Instagram / TikTok
functions send to « Reels », the episode thumbnail / chapters ones to « Miniatures », the rest (boot, errors, /check)
to the group's General topic. An answer to Loïc goes to the topic he wrote in, with that topic's own chat memory.
The private chat stays for secrets (/connect): what starts there is answered there.
"""
import contextvars
import functools
import inspect
import json
from pathlib import Path

TOPIC: contextvars.ContextVar = contextvars.ContextVar("btr_topic", default=None)
# key → topic name (General = "system", no thread id); order = creation order
NAMES = {"reels": "🎬 Reels & covers", "thumbs": "🖼️ Miniatures épisode", "stories": "📚 Stories & carrousels"}
COLORS = {"reels": 0xFF93B2, "thumbs": 0xFFD67E, "stories": 0x6FB9F0}
LABELS = {"reels": "Reels & covers (reels, covers, Shorts YouTube, Instagram, TikTok)",
          "thumbs": "Miniatures épisode (miniatures YouTube / podcast / reel teaser, titres, chapitres)",
          "stories": "Stories & carrousels", "system": "Général (système, alertes, /check, /couts)",
          "private": "chat privé (connexions, secrets)"}
WELCOME = {"reels": "Ici : les reels, leurs covers, les Shorts YouTube, Instagram et TikTok.",
           "thumbs": "Ici : les miniatures de la vidéo principale (YouTube, podcast, reel teaser), titres et chapitres.",
           "stories": "Ici : les stories et les carrousels."}


class Topics:
    def __init__(self, data_dir: Path):
        self.path = Path(data_dir) / "topics.json"
        try:
            d = json.loads(self.path.read_text())
        except (OSError, ValueError):
            d = {}
        self.group: int = int(d.get("group") or 0)
        self.threads: dict = {k: int(v) for k, v in (d.get("threads") or {}).items()}

    def save(self) -> None:
        self.path.write_text(json.dumps({"group": self.group, "threads": self.threads}, indent=1))

    def key_of(self, thread: int | None) -> str:
        return next((k for k, v in self.threads.items() if thread and v == thread), "system")

    def route(self, owner: int, endpoint: str, data: dict) -> dict:
        """A send* call to the owner's private chat → the group, in the current topic (unless it started in the
        private chat and no topic was forced)."""
        if not self.group or not owner or not endpoint.lower().startswith("send"):
            return data
        try:
            to = int(data.get("chat_id") or 0)
        except (TypeError, ValueError):
            return data
        topic = TOPIC.get()
        if to != owner or topic == "private":
            return data
        data["chat_id"] = self.group
        thread = self.threads.get(topic or "system")
        if thread:
            data["message_thread_id"] = thread
        else:
            data.pop("message_thread_id", None)
        return data


def within(topic: str, fn):
    """fn (async) runs with TOPIC = topic: everything it sends, and the jobs it starts, go to that topic."""
    if not inspect.iscoroutinefunction(fn) or getattr(fn, "_btr_topic", None):
        return fn

    @functools.wraps(fn)
    async def w(*a, **k):
        tok = TOPIC.set(topic)
        try:
            return await fn(*a, **k)
        finally:
            try:
                TOPIC.reset(tok)
            except ValueError:            # finished in another context (wait_for task): nothing to restore
                pass
    w._btr_topic = topic
    return w


def assign(ns: dict, topic: str, names: str) -> None:
    for n in names.split():
        if n in ns:
            ns[n] = within(topic, ns[n])

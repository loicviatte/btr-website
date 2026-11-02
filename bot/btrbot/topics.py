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
EP: contextvars.ContextVar = contextvars.ContextVar("btr_episode", default=None)   # video id the messages belong to
# key → topic name (General = "system", no thread id); order = creation order
NAMES = {"reels": "🎬 Reels & covers", "thumbs": "🖼️ Miniatures épisode", "stories": "📚 Stories & carrousels",
         "dash": "✅ À valider", "planning": "🗓️ Posts planning"}
COLORS = {"reels": 0xFF93B2, "thumbs": 0xFFD67E, "stories": 0x6FB9F0, "dash": 0x8EEE98, "planning": 0xCB86DB}
LABELS = {"reels": "Reels & covers (reels, covers, Shorts YouTube, Instagram, TikTok)",
          "thumbs": "Miniatures épisode (miniatures YouTube / podcast / reel teaser, titres, chapitres)",
          "stories": "Stories & carrousels", "dash": "À valider (un message par épisode, mis à jour tout seul)",
          "planning": "Posts planning (le calendrier ClickUp de tous les posts, toutes plateformes ; on y change les "
                      "carrousels et stories : type, date, ajouter, retirer ; outils planning_*)",
          "system": "Général (système, alertes, /check, /couts)",
          "private": "chat privé (connexions, secrets)"}
WELCOME = {"reels": "Ici : les reels, leurs covers, les Shorts YouTube, Instagram et TikTok.",
           "thumbs": "Ici : les miniatures de la vidéo principale (YouTube, podcast, reel teaser), titres et chapitres.",
           "stories": "Ici : les stories et les carrousels.",
           "dash": "Ici : un seul message par épisode, mis à jour tout seul : ce qui reste à valider (⏳), ce qui est "
                   "programmé (📅) et publié (🟢). Un tap ouvre l'élément dans son fil ; ce qui est publié est verrouillé.",
           "planning": "Ici : en haut, tous les posts qui restent pour l'épisode en cours (toutes plateformes) ; on change le calendrier dans ClickUp en parlant (« remplace la story Poll du 4.11 par "
                       "un Rapid fire », « décale Topics à 11h », « ajoute une Citation jeudi 19h »). Le nouveau contenu est "
                       "généré pour validation et « À valider » se met à jour."}


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


def episode_of(a, k) -> str | None:
    """The episode among a function's arguments (an object with a video_id), if any."""
    for x in list(a) + list(k.values()):
        vid = getattr(x, "video_id", None)
        if isinstance(vid, str) and vid:
            return vid
    return None


def within(topic: str, fn):
    """fn (async) runs with TOPIC = topic: everything it sends, and the jobs it starts, go to that topic."""
    if not inspect.iscoroutinefunction(fn) or getattr(fn, "_btr_topic", None):
        return fn

    @functools.wraps(fn)
    async def w(*a, **k):
        tok = TOPIC.set(topic)
        vid = episode_of(a, k)                     # what it sends belongs to that episode (cleaned with it)
        tok_ep = EP.set(vid) if vid else None
        try:
            return await fn(*a, **k)
        finally:
            try:
                TOPIC.reset(tok)
                if tok_ep is not None:
                    EP.reset(tok_ep)
            except ValueError:            # finished in another context (wait_for task): nothing to restore
                pass
    w._btr_topic = topic
    return w


def assign(ns: dict, topic: str, names: str) -> None:
    for n in names.split():
        if n in ns:
            ns[n] = within(topic, ns[n])

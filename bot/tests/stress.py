"""Stress test of the conversation: real chat model (Haiku) + real tool loop, fake side effects.

Run ON THE SERVER (it needs the real API key), on a throw-away data folder:
    DATA_DIR=$(mktemp -d) .venv/bin/python -m tests.stress
Nothing is sent to Telegram or YouTube: heavy jobs and messages are recorded instead.
Prints, for each message, the tools the model called, its answer, latency and cost, then a summary.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
assert os.environ.get("DATA_DIR"), "use a throw-away DATA_DIR"
import btrbot.bot as b  # noqa: E402

SENT: list = []
CALLS: list = []


class FakeBot:
    async def send_message(self, chat, text, **kw):
        SENT.append(text)
        return NS(message_id=len(SENT))

    async def send_photo(self, chat, f, **kw):
        SENT.append("[photo] " + str(kw.get("caption")))
        return NS(message_id=len(SENT))

    send_document = send_photo

    async def send_media_group(self, chat, media):
        SENT.append(f"[album {len(media)}]")

    async def send_chat_action(self, *a, **k):
        pass


def fake(name):
    async def f(*a, **k):
        CALLS.append(name)
    return f


# side effects replaced by recorders (the chat model and the tool loop are real)
for n in ("make_thumbs", "propose_frames", "send_recap", "badge_preview", "retime_chapters", "propose_chapters",
          "show_chapters", "title_discussion", "poll_youtube", "start_video", "talk_to_agent"):
    setattr(b, n, fake(n))
b.run_check = lambda: "✅ tout va bien"
b.pipe.description_with_chapters = lambda ep: "desc avec chapitres"
real_ask = b.pipe.llm._ask
b.pipe.llm._ask = lambda *a, **k: "Nouvelle description courte."
b.pipe.yt = NS(recent=lambda n=15: [
    {"id": "PjDZ8X_JWY0", "status": {"privacyStatus": "public"}, "snippet": {"title": "Oti Mabuse — Why She Walked Away From Strictly After Two Wins (PART 2)"}},
    {"id": "Xq3oti1PART", "status": {"privacyStatus": "public"}, "snippet": {"title": "She Left Everything Behind to Chase Her Dance Dream | Break the Routine with Oti Mabuse"}},
    {"id": "nashPART2xx", "status": {"privacyStatus": "public"}, "snippet": {"title": "Peter Nash | Fairness, Inclusion and a Life in Dance (PART 2)"}},
])
ctx = NS(bot=FakeBot())


def episode(stage: str, validated=("youtube", "square")):
    ep = b.reg.episode("PjDZ8X_JWY0")
    ep.data.clear()
    ep.data.update({
        "title": "Oti Mabuse part 2 raw", "guest_name": "Oti Mabuse", "stage": stage,
        "axes": [{"angle": "Strictly", "top": "I walked", "key": "AWAY", "bottom": "from Strictly", "title": "Why Oti Walked Away From Strictly", "verified": True},
                 {"angle": "Famille", "top": "My family", "key": "DIDN'T SPEAK", "bottom": "to me", "title": "Oti Mabuse: My Family Didn't Speak To Me", "verified": True},
                 {"angle": "Victoires", "top": "Two wins", "key": "WASN'T", "bottom": "enough", "title": "Two Strictly Wins Weren't Enough", "verified": True}],
        "final": {"top": "I walked", "key": "AWAY", "bottom": "from Strictly", "title": "Why Oti Walked Away From Strictly (PART 2)", "quote": "I walked away from Strictly"},
        "pick_guest": {"hires": "/x.jpg", "cx": .3}, "pick_marius": {"hires": "/y.jpg", "cx": .6},
        "validated": list(validated), "description": "Oti Mabuse... {CHAPTERS}",
        "chapters": [["00:00", "Intro"], ["03:10", "Leaving Strictly"], ["21:35", "Family"]],
    })
    ep.save()
    b.reg.active = "PjDZ8X_JWY0"
    return ep


# (stage or None = no episode, message, tools that must be called, tools that must NOT be called)
CASES = [
    ("thumbs", "vertical validé", {"validate"}, {"propose_claude_code", "redo_thumbnails"}),
    ("thumbs", "tout est validé sauf le carré", {"validate"}, {"propose_claude_code"}),
    ("thumbs", "rouvre le carré", {"reopen"}, {"propose_claude_code"}),
    ("thumbs", "le texte du vertical un peu plus haut stp", {"set_design"}, {"propose_claude_code"}),
    ("thumbs-cont", "encore un peu plus haut et refais le", {"set_design", "redo_thumbnails"}, {"propose_claude_code"}),
    ("thumbs", "sur le carré mets marius derrière oti et refais le", {"set_design", "redo_thumbnails"}, {"propose_claude_code"}),
    ("thumbs", "les yeux de marius sont fermés", {"other_frames"}, {"propose_claude_code"}),
    ("thumbs", "renvoie moi les miniatures", {"send_recap"}, set()),
    ("thumbs", "change le titre en : Oti Mabuse: Why I Walked Away From Strictly", {"set_title"}, set()),
    ("thumbs", "la citation : I had to | LEAVE | Strictly", {"set_quote"}, set()),
    ("thumbs", "ok publie", {"publish"}, set()),
    ("thumbs", "mets les chapitres dans la description", {"chapters"}, set()),
    ("thumbs", "les timecodes des chapitres sont décalés", {"chapters"}, set()),
    ("thumbs", "j'ai pas reçu les miniatures", {"get_status"}, {"propose_claude_code"}),
    ("thumbs", "c'est fait ?", {"get_status"}, {"propose_claude_code"}),
    ("thumbs", "combien j'ai dépensé aujourd'hui en IA ?", {"costs"}, set()),
    ("thumbs", "mets part 1 et part 2 sur les miniatures des deux dernières vidéos d'oti", {"badge"}, {"propose_claude_code"}),
    ("thumbs", "ajoute une version 4:5 pour le feed insta à chaque épisode", {"propose_claude_code"}, set()),
    ("thumbs", "le logo est trop gros sur le carré, il mange la tête d'oti", {"thumbnail_feedback|propose_claude_code"}, set()),
    ("thumbs", "description plus courte et sans hashtags", {"edit_description"}, set()),
    ("thumbs", "mets un badge part 2 sur cet épisode", {"set_part"}, {"badge"}),
    ("thumbs", "merci 👍", set(), {"propose_claude_code", "publish", "redo_thumbnails"}),
    ("thumbs", "fais un check complet du bot", {"health_check"}, set()),
    ("axes", "le 2", {"choose_axis"}, {"title_chat"}),
    ("axes", "plus provoc, un truc sur strictly", {"title_chat"}, {"choose_axis"}),
    ("axes", "j'aime le 3 mais trouve un titre plus court", {"title_chat"}, set()),
    (None, "salut ça va ?", set(), {"propose_claude_code"}),
    (None, "traite cette vidéo https://youtu.be/AbCdEfGhIjK", {"start_episode"}, set()),
    (None, "regarde s'il y a une nouvelle vidéo", {"scan_youtube"}, set()),
    (None, "pourquoi tu m'as envoyé du json bizarre hier ?", set(), {"publish", "badge"}),
]


async def main():
    rows, ok_n, t_total = [], 0, 0.0
    ledger = b.pipe.llm.ledger.path
    for stage, msg, must, never in CASES:
        if stage == "thumbs":
            episode("thumbs_proposed")
        elif stage == "axes":
            episode("axes_proposed", ())
        elif stage is None:
            b.reg.active = None
        if stage != "thumbs-cont":
            b.reg.data["convo"] = []
        before = len(ledger.read_text().splitlines()) if ledger.exists() else 0
        SENT.clear()
        CALLS.clear()
        actions: list = []
        orig = b.assistant.converse

        async def spy(*a, **k):
            r = await orig(*a, **k)
            actions.extend(x.split("(")[0] for x in r[1])
            spy.detail = r[1]
            return r
        b.assistant.converse = spy
        t0 = time.time()
        await b.ask_assistant(ctx, msg)
        await asyncio.sleep(0.2)   # background jobs
        dt = time.time() - t0
        b.assistant.converse = orig
        t_total += dt
        lines = ledger.read_text().splitlines()[before:] if ledger.exists() else []
        usd = sum(json.loads(x)["usd"] for x in lines)
        tools = set(actions)
        need_ok = all(any(alt in tools for alt in m.split("|")) for m in must)
        ok = need_ok and not (tools & never) and (bool(tools) or not must)
        ok_n += ok
        rows.append(f"{'✅' if ok else '❌'} « {msg} »\n   outils : {', '.join(getattr(spy, 'detail', [])) or '—'}\n"
                    f"   réponse : {(SENT[-1] if SENT else '—')[:300]}\n   {dt:.1f} s · {usd * 100:.2f} ¢")
    print("\n".join(rows))
    tot = sum(json.loads(x)["usd"] for x in ledger.read_text().splitlines()) if ledger.exists() else 0
    print(f"\nRÉSUMÉ : {ok_n}/{len(CASES)} OK · {t_total / len(CASES):.1f} s en moyenne · {tot:.3f} $ au total "
          f"({tot / len(CASES) * 100:.2f} ¢ par message) · modèle {b.CHAT_MODEL}")


if __name__ == "__main__":
    asyncio.run(main())

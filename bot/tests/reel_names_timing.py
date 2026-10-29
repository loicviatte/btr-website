"""Subtitle timing (every word readable ≥ 0.5 s, even a sentence's last word right before the next one), sentence
seams across pages, and the proper-noun guard. Offline.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x python tests/reel_names_timing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import subs  # noqa: E402
from btrbot.reels import Word  # noqa: E402
from btrbot.subs import Block, Tok  # noqa: E402


def page(*lines):
    return Block([[Tok(w, *t) for w, t in ln] for ln in lines], "c")


# fast speech: « …they don't care. » then « When » 30 ms later; « care. » lasts 120 ms
w = [("they", (0.0, 0.2)), ("just", (0.2, 0.35)), ("don't", (0.35, 0.5)), ("care.", (0.5, 0.62)),
     ("When", (0.65, 0.8)), ("you", (0.8, 0.9)), ("are", (0.9, 1.0)), ("on", (1.0, 1.1)), ("these", (1.1, 1.3)),
     ("shows.", (1.3, 1.5)), ("Yes.", (1.52, 1.6)), ("So", (1.62, 1.7))]
blocks = [page(w[:4]), page(w[4:10]), page(w[10:11]), page(w[11:])]
blocks = subs.merge_flashes(blocks)
subs.timeline(blocks, 3.0, lambda t: "full")
v = subs.visibility(blocks)
print(v)
assert not v["short"] and v["min_seen"] >= 0.48 and v["max_late"] <= 0.6, v
# a sentence tail at the start of a page goes back; a sentence start at the end of a page goes forward
b1 = page([("I", (0, 0.1)), ("was", (0.1, 0.2)), ("like,", (0.2, 0.3))], [("they", (0.3, 0.4)), ("just", (0.4, 0.5))])
b2 = page([("don't", (0.5, 0.6)), ("care.", (0.6, 0.7))], [("When", (0.75, 0.8)), ("you", (0.8, 0.9))])
b3 = page([("are", (0.9, 1)), ("on", (1, 1.1)), ("these", (1.1, 1.2)), ("shows.", (1.2, 1.3))], [("So", (1.35, 1.4))])
b4 = page([("what?", (1.4, 1.5))])
out = subs.sentence_seams([b1, b2, b3, b4])
pages = [" ".join(t.text for line in b.lines for t in line) for b in out]
print(pages)
assert pages[0].endswith("they just don't care.") and pages[1] == "When you are on these shows.", pages
assert pages[-1].startswith("So what?"), pages
# proper nouns: a fix must be the same spoken name, never extra words
from btrbot.pipeline import apply_all  # noqa: E402
words = [Word(t, i, i + 0.5) for i, t in enumerate("me and Muti we danced with danny mack at black pool".split())]
fixed, miss = apply_all(words, [{"from": "Muti", "to": "Motsi"}, {"from": "danny mack", "to": "Danny Mac"},
                                {"from": "black pool", "to": "Blackpool"}])
print(" ".join(x.text for x in fixed))
assert " ".join(x.text for x in fixed) == "me and Motsi we danced with Danny Mac at Blackpool", fixed
print("OK")

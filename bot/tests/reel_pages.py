"""Subtitle pages: never more than 4 lines, never an expression cut between two pages, not always centred.

    python tests/reel_pages.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import subs  # noqa: E402
from btrbot.subs import Block, Tok  # noqa: E402


def page(*lines, align="c"):
    return Block([[Tok(w, 0, 0) for w in ln.split()] for ln in lines], align)


def text(bs):
    return [" / ".join(" ".join(t.text for t in ln) for ln in b.lines) for b in bs]


# 6 lines: cut at the sentence end, never between « why » and « not »
bs = subs.cap_lines(subs.keep_phrases([page("so I said", "why", "not.", "and then", "she came", "back")]))
assert all(len(b.lines) <= 4 for b in bs), text(bs)
assert text(bs)[0].endswith("not."), text(bs)
# « give | me » across lines: the cut goes elsewhere
bs = subs.cap_lines([page("you have to", "give", "me", "the", "chance", "today")])
for a, b in zip(bs, bs[1:]):
    assert not subs._open_end(a.lines[-1][-1], b.lines[0][0]), text(bs)
assert all(len(b.lines) <= 4 for b in bs), text(bs)
# no safe boundary at all: lines are joined, still ≤ 4
bs = subs.cap_lines([page("the", "very", "really", "to", "of", "my")])
assert len(bs) == 1 and len(bs[0].lines) <= 4, text(bs)
# keep_phrases may merge a one-word page: the cap still holds
bs = subs.cap_lines(subs.keep_phrases([page("why"), page("not", "a", "b", "c.")]))
assert all(len(b.lines) <= 4 for b in bs) and text(bs)[0].startswith("why not"), text(bs)
# variety: never 3 centred pages in a row, some pages lower
bs = [page("a", align="c") for _ in range(10)]
subs.vary(bs)
al = [b.align for b in bs]
assert "c" in al and any(a != "c" for a in al) and "ccc" not in "".join(a[0] for a in al), al
assert any(b.meta["low"] for b in bs) and not all(b.meta["low"] for b in bs)
print(text(subs.cap_lines(subs.keep_phrases([page("so I said", "why", "not.", "and then", "she came", "back")]))))
print("aligns", al)
print("OK")

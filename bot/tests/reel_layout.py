"""Placement of the reel subtitles on real reels, offline (no model, no render): the pages of each existing subs.ass
are read back (same words, lines, emphasis, timings), placed again with the current rules, and the new ASS is checked:
  - every page starts at or above the last word of the page before (top of its first line <= that word's baseline),
  - no page starts in the bottom third, most pages start in the centre,
  - about 40 % fewer position changes than the old file at least, text unchanged, 4 lines max.
Usage: python tests/reel_layout.py [episode_dir] [n ...]   (default: PjDZ8X_JWY0, reels 1 2 3 5 6 8)"""
import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import subs  # noqa: E402
from btrbot import reels as R  # noqa: E402

EP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/opt/btr-bot/data/episodes/PjDZ8X_JWY0")
NS = [int(x) for x in sys.argv[2:]] or [1, 2, 3, 5, 6, 8]
FONTS = Path("/opt/btr-bot/data/fonts")
DIA = re.compile(r"^Dialogue: 1,([\d:.]+),([\d:.]+),Base,,0,0,0,,\{\\an(\d)\\pos\((-?\d+),(-?\d+)\)[^}]*\}(.*)$")
SEG = re.compile(r"\{([^}]*)\}([^{]*)")


def secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def read_ass(path: Path) -> list[dict]:
    """Pages of an ASS file: [{start, end, lines: [{an, x, y, toks: [(text, big, gold, italic, tight, t0, size)]}]}]."""
    pages: list[dict] = []
    for row in path.read_text(encoding="utf-8").splitlines():
        m = DIA.match(row)
        if not m:
            continue
        start, end, an, x, y, body = secs(m[1]), secs(m[2]), int(m[3]), int(m[4]), int(m[5]), m[6]
        toks = []
        for tags, word in SEG.findall(body):
            t0 = re.search(r"\\t\((\d+),", tags)
            toks.append((word.strip(), "BTR Heavy" in tags, subs.GOLD in tags, "\\i1" in tags, "\\fsp" in tags,
                         int(t0[1]) if t0 else 0, float(re.search(r"\\fs([\d.]+)", tags)[1])))
        if not pages or (pages[-1]["start"], pages[-1]["end"]) != (start, end):
            pages.append({"start": start, "end": end, "lines": []})
        pages[-1]["lines"].append({"an": an, "x": x, "y": y, "toks": toks})
    return pages


def geometry(p: dict) -> tuple[float, float, str]:
    """Top of the first line, baseline of the last word, and the place (c / l / r / stair / low) of a page."""
    first, last = p["lines"][0], p["lines"][-1]
    h1, hl = max(t[6] for t in first["toks"]), max(t[6] for t in last["toks"])
    top = first["y"] - h1 * subs.DESC - h1 * subs.CAP
    base = last["y"] - hl * subs.DESC
    an = first["an"]
    place = "c" if an == 2 else "r" if an == 3 else ("stair" if len(p["lines"]) > 1 and last["x"] > first["x"] else "l")
    if place == "c" and (top + base) / 2 > subs.Y_FULL + 80:
        place = "low"
    return top, base, place


def to_blocks(pages: list[dict]) -> list[subs.Block]:
    blocks = []
    for p in pages:
        lines = []
        for ln in p["lines"]:
            lines.append([subs.Tok(t[0], p["start"] + t[5] / 1000, 0.0, big=t[1], gold=t[2], italic=t[3], tight=t[4])
                          for t in ln["toks"]])
        flat = [t for ln in lines for t in ln]
        for a, b in zip(flat, flat[1:]):
            a.end = b.start
        flat[-1].end = max(flat[-1].start, p["end"] - 0.35)
        blocks.append(subs.Block(lines))
    return blocks


def moves(places: list[str]) -> int:
    return sum(a != b for a, b in zip(places, places[1:]))


fails = []
for n in NS:
    work = EP / "reels" / f"r{n:02d}"
    old = read_ass(work / "subs.ass")
    edit = json.loads((work / "edit.json").read_text())
    blocks = to_blocks(old)
    subs.vary(blocks)
    subs.timeline(blocks, edit["frames"] / edit["fps"], lambda t: R.layout_at(edit["layout"], t))
    with tempfile.TemporaryDirectory() as tmp:
        new = read_ass(subs.write_ass(blocks, FONTS, Path(tmp) / "subs.ass"))
    og, ng = [geometry(p) for p in old], [geometry(p) for p in new]
    old_bad = sum(b[0] > a[1] + 1 for a, b in zip(og, og[1:]))
    bad = [i for i, (a, b) in enumerate(zip(ng, ng[1:]), 1) if b[0] > a[1] + 1]    # 1 px: ASS positions are rounded
    low_start = [i for i, g in enumerate(ng) if g[0] > subs.START_MAX + 1]
    centre = sum(g[2] == "c" for g in ng) / len(ng)
    om, nm = moves([g[2] for g in og]), moves([g[2] for g in ng])
    same_text = [t[0] for p in old for ln in p["lines"] for t in ln["toks"]] == \
                [t[0] for p in new for ln in p["lines"] for t in ln["toks"]]
    max_lines = max(len(p["lines"]) for p in new)
    print(f"r{n:02d}: {len(new)} pages | départ sous le dernier mot précédent: avant {old_bad}, après {len(bad)} | "
          f"centre {centre:.0%} | changements de position {om} → {nm} | max {max_lines} lignes | texte identique {same_text}")
    for i in bad:
        print(f"   page {i}: top {ng[i][0]:.0f} > dernier mot {ng[i - 1][1]:.0f}")
    if bad or low_start or centre <= 0.5 or not same_text or (om and nm > 0.6 * om) or max_lines > subs.MAX_LINES:
        fails.append(n)
print("ÉCHEC sur les reels", fails if fails else "") if fails else print("OK")
sys.exit(1 if fails else 0)

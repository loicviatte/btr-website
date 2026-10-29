"""BTR v3 animated subtitles (style of claude/btr-subtitles-workflow.md), as an ASS file burned by libass.

Pages of 1-4 stacked lines (varied, mostly centred; a phrase is never cut between two pages); small linking words in Monument Extended Regular, punch words in Heavy, gold
#FCDF9A on key words, synthetic italic on punchlines. Each word comes out of a blur when it is spoken (190 ms),
the block leaves with a 120 ms blur + fade. Soft black shadow offset 5 px. No landing effect, no text behind the
head, no camera shake (all rejected by Loïc).

Notation of a block line (from the model, checked against the transcript):
  lower-case = small word, UPPER-CASE = punch word, prefixes on ONE word: * gold, / italic, ~ letters tighten.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from PIL import ImageFont

W, H = 1080, 1920
SMALL, BIG = 82, 150          # ASS sizes (= 165 / 300 px on the 4K master)
LINE_GAP = 30                 # 60 px on the 4K master
MARGIN = 170                  # side margin: Instagram's reel view crops ~100 px a side on tall phones (Loïc 29.10.2026)
MARGIN_R = 200                # right edge of a right-aligned page: clear of Instagram's like / comment / share column
EM = 1000 / (1040 + 320)      # libass scales the font so ascent+descent = size: 1 em = 0.735 × size
CAP = 0.72 * EM               # cap height in units of the size
DESC = 0.32 * EM              # descender, below the baseline
GOLD = "&H9ADFFC&"            # #FCDF9A in ASS (BGR)
WHITE = "&HFFFFFF&"
Y_FULL, Y_SPLIT = 1160, 960   # block centre: under the face on a full frame, on the seam of a split screen
LOW_BOTTOM = 1540             # bottom of a lower page, always above the Instagram caption UI
START_MAX = 1280              # a page never starts in the bottom third of the screen (Loïc, 29.10.2026)
MAX_LINES = 4                 # hard limit per page (Loïc, 29.10.2026)
CYCLE, AWAY_RUN = 8, 2        # in every 8 pages: 6 in the centre, then 2 pages off it at the same place
AWAY = ("l", "r", "low", "stair")   # where the off-centre pages go, in turn
ALIGNS = ("c", "l", "r", "stair")
STAIR = 60                    # each line of a "stair" block is shifted right by 60 px (120 px on the 4K master)
FONT_FILES = {"small": "BTRRegular.ttf", "big": "BTRHeavy.ttf"}
FONT_NAMES = {"small": "BTR Regular", "big": "BTR Heavy"}


@dataclass
class Tok:
    text: str                 # what is shown (may carry punctuation or quotes)
    start: float
    end: float
    big: bool = False
    gold: bool = False
    italic: bool = False
    tight: bool = False


@dataclass
class Block:
    lines: list[list[Tok]]
    align: str = "c"          # c | l | r | stair
    start: float = 0.0
    end: float = 0.0
    y_center: float = Y_FULL
    meta: dict = field(default_factory=dict)


# ---------------------------------------------------------------- fonts
def prepare_fonts(assets: Path, out_dir: Path) -> Path:
    """The brand woff2 files, converted once into fonts libass can load, renamed so each weight is unambiguous."""
    from fontTools.ttLib import TTFont
    out_dir.mkdir(parents=True, exist_ok=True)
    for kind, src in (("big", "PPMonumentExtended-Heavy.woff2"), ("small", "PPMonumentExtended-Regular.woff2")):
        dest = out_dir / FONT_FILES[kind]
        if dest.exists():
            continue
        f = TTFont(str(assets / src))
        f.flavor = None
        fam = FONT_NAMES[kind]
        for r in f["name"].names:
            if r.nameID in (1, 4, 16):
                r.string = fam
            elif r.nameID in (2, 17):
                r.string = "Regular"
            elif r.nameID == 6:
                r.string = fam.replace(" ", "-")
        f["OS/2"].usWeightClass = 400
        f["head"].macStyle = 0
        f.save(str(dest))
    return out_dir


class Measure:
    def __init__(self, fonts_dir: Path):
        self.dir = fonts_dir
        self._cache: dict = {}

    def width(self, text: str, kind: str, size: float) -> float:
        px = max(1, int(round(size * EM)))
        key = (kind, px)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(str(self.dir / FONT_FILES[kind]), px)
        return self._cache[key].getlength(text)


# ---------------------------------------------------------------- notation → blocks
WORD_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']")
TOKEN_RE = re.compile(r"^([“”\"'(]*)([*/~#^!%]*)([“”\"'(]*)(.*?)([”“\"')?.!,:;…]*)$")
FILLERS = {"um", "uh", "uhm", "erm", "er", "ah", "eh", "hmm", "mm", "mhm", "oh"}


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9']", "", s.lower().replace("’", "'"))


def _same(a: str, b: str) -> bool:
    """Same spoken word: identical letters, apostrophes aside (dont = don't). NEVER ≠ ever, LOVED ≠ love."""
    ka, kb = _key(a), _key(b)
    return bool(ka) and (ka == kb or ka.replace("'", "") == kb.replace("'", ""))


def _shown(core: str, spoken: str) -> str:
    """The spoken word's own letters, in the model's case (UPPER for a punch word)."""
    letters = re.sub(r"^[^\w']+|[^\w']+$", "", spoken.replace("’", "'"))
    if core.isupper() and len(re.sub(r"[^A-Za-zÀ-ÿ]", "", core)) > 1:
        return letters.upper()
    return letters                      # small word: the spoken casing (names keep their capital)


def parse_blocks(spec: list[dict], words: list, max_shift: int = 6, stats: dict | None = None) -> list[Block]:
    """Blocks from the model's notation. Each token must be the SAME word as the next words really said (in order);
    its letters always come from the transcription, the model only brings case, emphasis and punctuation. A token
    that does not match is dropped; a spoken word the model skipped is put back as small words on their own lines
    (3 at most), unless it is a filler (um, uh…) or the extra copy of a repeated word. So the subtitles can neither
    add, change nor silently drop a meaningful word. `stats["reinserted"]` = how many words had to be put back."""
    toks: list[tuple[int, int, str]] = []            # (block, line, raw token), in reading order
    meta: list[str] = []
    for bi, b in enumerate(spec):
        meta.append(b.get("align", "c") if b.get("align") in ALIGNS else "c")
        for li, line in enumerate(b.get("lines") or []):
            toks += [(bi, li, re.sub(r"^\d+:", "", raw)) for raw in str(line).split()]
    parsed = []
    for bi, li, raw in toks:
        m = TOKEN_RE.match(raw)
        if m and WORD_RE.search(m.group(4)):
            parsed.append((bi, li, m.groups()))
    placed: list[tuple[int, int, int, Tok]] = []
    k = 0
    for t, (bi, li, (lead, flags, lead2, core, trail)) in enumerate(parsed):
        hit = next((j for j in range(k, min(len(words), k + max_shift)) if _same(core, words[j].text)), None)
        if hit is None:
            # the model skipped a longer aside: resync further on, only if the next token agrees right after
            nxt = parsed[t + 1][2][3] if t + 1 < len(parsed) else None
            for j in range(k + max_shift, len(words)):
                if _same(core, words[j].text) and (nxt is None or (j + 1 < len(words) and _same(nxt, words[j + 1].text))):
                    hit = j
                    break
        if hit is None:
            continue
        w = words[hit]
        k = hit + 1
        letters = re.sub(r"[^A-Za-zÀ-ÿ]", "", core)
        big = bool(letters) and letters.isupper() and (len(letters) > 1 or letters not in ("I", "A"))
        text = (lead + lead2) + _shown(core, w.text) + trail
        placed.append((bi, li, hit, Tok(text, w.start, w.end, big, "*" in flags, "/" in flags, "~" in flags)))
    used = {p[2] for p in placed}
    entries: list[tuple[int, object]] = [(p[2], p) for p in placed]
    back = 0
    for j, w in enumerate(words):
        if j in used:
            continue
        kw = _key(w.text)
        twins = [i for i in (j - 1, j + 1) if 0 <= i < len(words) and _key(words[i].text) == kw]
        if not kw or kw in FILLERS or any(i in used for i in twins) or (j - 1) in twins:
            continue                                   # filler, or a repeated word already shown once
        word = re.sub(r"^[^\w']+|[^\w']+$", "", w.text.replace("’", "'"))
        entries.append((j, Tok(word, w.start, w.end)))
        back += 1
    if stats is not None:
        stats["reinserted"] = back
    entries.sort(key=lambda e: e[0])
    blocks: list[Block] = []
    cur_key, cur_line, cur_block = None, None, None
    first_block = min((p[0] for p in placed), default=0)
    bi_now = first_block
    for _, e in entries:
        if isinstance(e, tuple):                       # a token placed by the model
            bi, li, _, tok = e
            key = (bi, li)
        else:                                          # a word put back: its own short line in the current block
            bi, tok = bi_now, e
            key = ("back", bi) if cur_key == ("back", bi) and len(cur_line) < 3 else ("back", bi, id(e))
        if bi != cur_block:
            blocks.append(Block([], meta[bi] if bi < len(meta) else "c"))
            cur_block, cur_key = bi, None
        if key != cur_key:
            cur_line = []
            blocks[-1].lines.append(cur_line)
            cur_key = ("back", bi) if key[0] == "back" else key
        cur_line.append(tok)
        bi_now = bi
    return blocks


# words that cannot end a page (they lead into the next word) / cannot start one (they close the previous word)
LEADS = {"a", "an", "the", "to", "of", "in", "on", "at", "for", "with", "from", "by", "into", "about", "my", "your",
         "his", "her", "our", "their", "its", "this", "that", "these", "those", "and", "but", "or", "so", "because",
         "if", "when", "than", "very", "really", "give", "why", "how", "what", "come", "let", "i", "you", "we", "they",
         "he", "she", "it's", "i'm", "you're", "we're", "they're", "don't", "can't", "didn't", "doesn't", "won't",
         "is", "are", "was", "were", "be", "been", "have", "has", "had", "do", "does", "did", "can", "could", "will",
         "would", "should", "must", "no", "more", "most", "such", "kind", "sort", "lot", "bit", "going"}
TAILS = {"not", "me", "it", "him", "her", "them", "us", "up", "out", "on", "off", "down", "back", "too", "there",
         "away", "yet", "anyway", "though"}


def _open_end(tok: Tok, nxt: Tok) -> bool:
    """The page ends on `tok` and the next one starts with `nxt`: are they one expression cut in two?"""
    if re.search(r"[.?!,:;…]['”\"]?$", tok.text):
        return False                                     # the speaker closed the phrase there
    return _key(tok.text) in LEADS or _key(nxt.text) in TAILS


def keep_phrases(blocks: list[Block]) -> list[Block]:
    """Never cut a phrase between two pages (« why | not », « give | me », « a lot | of »): the dangling words move to
    the next page, or, when the next page starts with a closing word, that word joins the previous page."""
    blocks = [b for b in blocks if any(b.lines)]
    for i in range(len(blocks) - 1):
        a, b = blocks[i], blocks[i + 1]
        for _ in range(3):                               # at most 3 words moved per seam
            if not a.lines or not b.lines or not _open_end(a.lines[-1][-1], b.lines[0][0]):
                break
            if _key(b.lines[0][0].text) in TAILS and sum(map(len, b.lines)) > 1:
                a.lines[-1].append(b.lines[0].pop(0))    # « give | me » → « give me | »
            elif sum(map(len, a.lines)) > 1:
                b.lines[0].insert(0, a.lines[-1].pop())  # « a lot of | sugar » → « | of sugar »… then « a lot »
            else:
                b.lines[:0], a.lines = a.lines, []       # a one-word page leading into the next: one page
                break
            a.lines = [ln for ln in a.lines if ln]
            b.lines = [ln for ln in b.lines if ln]
    return [b for b in blocks if b.lines]


def _cut_ok(a: list[Tok], b: list[Tok]) -> int:
    """How good it is to start a new page between line `a` and line `b`: 2 = end of a sentence, 1 = a clause closes
    (comma, or nothing ties the two words), 0 = it would split an expression."""
    last, nxt = a[-1], b[0]
    if re.search(r"[.?!…]['”\"]?$", last.text):
        return 2
    return 0 if _open_end(last, nxt) or (_key(nxt.text) == "of") else 1


def cap_lines(blocks: list[Block], max_lines: int = MAX_LINES) -> list[Block]:
    """At most `max_lines` lines per page, never by cutting an expression: a long page is cut at the best line boundary
    (sentence end first, then a clause end, as balanced as possible); if no boundary is safe, its two shortest
    neighbouring lines are joined instead (the line is scaled down to fit the width)."""
    out: list[Block] = []
    todo = list(blocks)
    while todo:
        b = todo.pop(0)
        if len(b.lines) <= max_lines:
            out.append(b)
            continue
        n = len(b.lines)
        safe = []
        for k in range(1, min(n, max_lines + 1)):            # the first page never goes over the limit
            q = _cut_ok(b.lines[k - 1], b.lines[k])
            if q:
                both_fit = n - k <= max_lines
                safe.append((both_fit, q, -abs(n - 2 * k), k))   # both pages fit > sentence end > balanced
        if safe:
            k = max(safe)[-1]
            first, rest = Block(b.lines[:k], b.align, meta=dict(b.meta)), Block(b.lines[k:], b.align, meta=dict(b.meta))
            todo[:0] = [first, rest]
            continue
        i = min(range(n - 1), key=lambda j: len(b.lines[j]) + len(b.lines[j + 1]))
        b.lines[i:i + 2] = [b.lines[i] + b.lines[i + 1]]
        todo.insert(0, b)
    return out


def vary(blocks: list[Block]) -> None:
    """Mostly in the centre, few moves (Loïc: the eye must not chase the text): pages start centred; after 6 centred
    pages, 2 pages sit together off the centre (left, right, lower, stair in turn), then back to the centre.
    The model's alignment is not used: the rhythm is the program's, so it holds on every reel."""
    for i, b in enumerate(blocks):
        k, slot = divmod(i, CYCLE)
        away = AWAY[k % len(AWAY)] if slot >= CYCLE - AWAY_RUN else "c"
        b.align = "c" if away == "low" else away
        b.meta["low"] = away == "low"


def auto_blocks(words: list) -> list[Block]:
    """Fallback without the model: pages of varied length (a short accent after a long one), 1-3 words per line,
    the longest word of each page big, never cut inside an expression."""
    blocks: list[Block] = []
    cur: list = []
    for i, w in enumerate(words):
        cur.append(w)
        end_sentence = bool(re.search(r"[.?!]$", w.text))
        gap = i + 1 < len(words) and words[i + 1].start - w.end > 0.35
        short = len(blocks) % 3 == 2                     # every third page is a short accent
        nxt = words[i + 1].text if i + 1 < len(words) else ""
        open_end = bool(nxt) and (_open_end(Tok(w.text, 0, 0), Tok(nxt, 0, 0)) or _key(nxt) == "of"
                                  or (w.text[:1].isupper() and nxt[:1].isupper() and not end_sentence
                                      and _key(w.text) != "i" and _key(nxt) != "i"))   # a name: Danny Mac
        if i == len(words) - 1 or (not open_end and (len(cur) >= (3 if short else 7)
                                                     or ((end_sentence or gap) and len(cur) >= (1 if short else 3)))) \
                or len(cur) >= 10:
            longest = max(cur, key=lambda x: len(_key(x.text)))
            toks = [Tok(x.text.upper() if x is longest else x.text, x.start, x.end, big=x is longest) for x in cur]
            lines, line = [], []
            for t in toks:
                if t.big and line:
                    lines.append(line)
                    line = []
                line.append(t)
                if t.big or len(line) == 3:
                    lines.append(line)
                    line = []
            if line:
                lines.append(line)
            blocks.append(Block(lines, ("c", "l", "c", "r", "c", "stair")[len(blocks) % 6]))
            cur = []
    return blocks


MIN_SEEN = 0.5      # every word stays on screen at least this long after it appears (190 ms blur-in + ~0.3 s to read)
MIN_PAGE = 0.8      # shortest page


def timeline(blocks: list[Block], total: float, layout_at) -> None:
    """Page start/end on the reel, and where it sits (full frame or split screen). A page never leaves before its last
    word has been readable for MIN_SEEN: when the next words come right after a sentence's last word, the next page
    starts a little later (its words appear as soon as it starts) instead of wiping that word after a flash."""
    prev_end = 0.0
    for i, b in enumerate(blocks):
        toks = [t for line in b.lines for t in line]
        b.start = max(toks[0].start, prev_end)
        latest = max(max(t.start for t in toks), b.start)          # when the last word of the page appears
        last = max(t.end for t in toks)
        nxt = blocks[i + 1].lines[0][0].start if i + 1 < len(blocks) else total
        b.end = min(max(latest + MIN_SEEN, min(nxt, max(last + 0.35, b.start + MIN_PAGE))), total)
        prev_end = b.end
        split = any(layout_at(t) == "split" for t in (b.start + 0.05, (b.start + b.end) / 2, b.end - 0.05))
        b.y_center = Y_SPLIT if split else Y_FULL
        b.meta["split"] = split


def appear(t: Tok, b: Block) -> float:
    """When word t shows up: as it is spoken, but never before its page, and early enough to be readable MIN_SEEN
    before the page goes (at the very end of a reel the last words come up a little ahead of the voice)."""
    return max(b.start, min(t.start, b.end - MIN_SEEN))


def visibility(blocks: list[Block]) -> dict:
    """Check of the timing: how long each word is readable (page end − the moment it appears) and how late it appears
    after it is spoken. {"short": [(word, seconds)], "min_seen": s, "max_late": s}"""
    short, seen_all, late_all = [], [], []
    for b in blocks:
        for line in b.lines:
            for t in line:
                shown = appear(t, b)
                seen = b.end - shown
                seen_all.append(seen)
                late_all.append(shown - t.start)
                if seen < MIN_SEEN - 0.02:
                    short.append((t.text, round(seen, 2)))
    return {"short": short, "min_seen": round(min(seen_all, default=0), 2), "max_late": round(max(late_all, default=0), 2)}


def merge_flashes(blocks: list[Block], span: float = 0.3) -> list[Block]:
    """A page of 1-2 words spoken in a flash (< 0.3 s) cannot stay readable without pushing every next page late: it
    joins the next page (or the one before, when the next is full)."""
    out: list[Block] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        toks = [t for line in b.lines for t in line]
        quick = len(toks) <= 2 and toks and toks[-1].start - toks[0].start < span
        if quick and i + 1 < len(blocks) and len(blocks[i + 1].lines) + len(b.lines) <= MAX_LINES:
            blocks[i + 1].lines[:0] = b.lines
        elif quick and out and len(out[-1].lines) + len(b.lines) <= MAX_LINES:
            out[-1].lines.extend(b.lines)
        else:
            out.append(b)
        i += 1
    return out


SENT_END = re.compile(r"[.?!…]['”\"]?$")


def sentence_seams(blocks: list[Block], tail: int = 2) -> list[Block]:
    """A page never holds the last 1-2 words of a sentence followed by the start of the next one (« …care. When
    you »): those last words go back to the end of the page before; and a page never ends on the first 1-2 words of
    a new sentence: they go to the next page."""
    blocks = [b for b in blocks if any(b.lines)]

    def flat(b):
        return [t for line in b.lines for t in line]

    def take_first(b, k):
        out = []
        while k and b.lines:
            out.append(b.lines[0].pop(0))
            k -= 1
            if not b.lines[0]:
                b.lines.pop(0)
        return out

    def take_last(b, k):
        out = []
        while k and b.lines:
            out.insert(0, b.lines[-1].pop())
            k -= 1
            if not b.lines[-1]:
                b.lines.pop()
        return out
    for i, b in enumerate(blocks):
        toks = flat(b)
        ends = [k for k, t in enumerate(toks) if SENT_END.search(t.text)]
        if i > 0 and ends and ends[0] < tail and ends[0] < len(toks) - 1 and blocks[i - 1].lines:
            prev = blocks[i - 1]
            if not SENT_END.search(prev.lines[-1][-1].text):            # it continues the sentence of the page before
                moved = take_first(b, ends[0] + 1)
                last = prev.lines[-1]
                if len(last) + len(moved) <= 3 and not any(t.big for t in moved + last):
                    last.extend(moved)
                else:
                    prev.lines.append(moved)
                toks = flat(b)
                ends = [k for k, t in enumerate(toks) if SENT_END.search(t.text)]
        if i + 1 < len(blocks) and not ends and len(toks) <= tail and b.lines \
                and len(blocks[i + 1].lines) + len(b.lines) <= MAX_LINES:
            blocks[i + 1].lines[:0] = b.lines                    # what is left (« When you ») joins its sentence
            b.lines = []
            continue
        if i + 1 < len(blocks) and ends and len(toks) - 1 - ends[-1] in range(1, tail + 1):
            moved = take_last(b, len(toks) - 1 - ends[-1])
            nxt = blocks[i + 1]
            if nxt.lines and len(nxt.lines[0]) + len(moved) <= 3 and not any(t.big for t in moved + nxt.lines[0]):
                nxt.lines[0][:0] = moved
            else:
                nxt.lines.insert(0, moved)
    return [b for b in blocks if b.lines]


# ---------------------------------------------------------------- ASS
def _ts(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _esc(s: str) -> str:
    return s.replace("\\", "").replace("{", "(").replace("}", ")")


def _line_sizes(line: list[Tok], m: Measure) -> tuple[float, float]:
    """Scale (≤1) so the line fits the width, and the line width at that scale."""
    def width(scale):
        total = 0.0
        for i, t in enumerate(line):
            kind = "big" if t.big else "small"
            size = (BIG if t.big else SMALL) * scale
            total += m.width(t.text, kind, size) + (m.width(" ", "small", SMALL * scale) if i else 0)
        return total
    w = width(1.0)
    s = min(1.0, (W - 2 * MARGIN) / w) if w else 1.0
    return s, width(s)


def _sizes(b: Block, m: Measure) -> tuple[list[float], list[float], float]:
    """Line scales, line heights (font size) and the block height from the top of its first line to the baseline of
    its last line."""
    scales = [_line_sizes(line, m)[0] for line in b.lines]
    heights = [max((BIG if t.big else SMALL) * s for t in line) for line, s in zip(b.lines, scales)]
    return scales, heights, sum(h * CAP for h in heights) + LINE_GAP * (len(heights) - 1)


def place(blocks: list[Block], m: Measure) -> None:
    """Vertical place of each page. A page never starts lower than the last word of the page before (its top is at or
    above that word's baseline) and never in the bottom third; a "low" page starts right at that level and runs down,
    its bottom above the Instagram caption. meta["top"] / meta["last"] = top of the page / baseline of its last word."""
    prev = None
    for b in blocks:
        _, heights, total = _sizes(b, m)
        limit = min(START_MAX, prev if prev is not None else START_MAX)
        top = b.y_center - total / 2
        if b.meta.get("low") and not b.meta.get("split"):
            top = max(top, min(limit, LOW_BOTTOM - total - heights[-1] * DESC))
        top = min(top, limit)
        b.y_center = top + total / 2
        b.meta["top"], b.meta["last"] = round(top, 1), round(top + total, 1)
        prev = top + total


def block_events(b: Block, m: Measure) -> list[str]:
    ev = []
    scales, heights, total = _sizes(b, m)
    baseline = b.y_center - total / 2
    dur_ms = int(round((b.end - b.start) * 1000))
    for li, (line, s, hmax) in enumerate(zip(b.lines, scales, heights)):
        baseline += hmax * CAP + (LINE_GAP if li else 0)
        y = baseline + hmax * DESC                       # \an1/2: the anchor is the bottom of the line box
        if b.align == "c":
            an, x = 2, W / 2
        elif b.align == "r":
            an, x = 3, W - MARGIN_R
        else:
            an, x = 1, MARGIN + (STAIR * li if b.align == "stair" else 0)
            x = min(x, W - MARGIN - _line_sizes(line, m)[1])
        parts_txt, parts_sh = [], []
        for i, t in enumerate(line):
            kind = "big" if t.big else "small"
            size = round((BIG if t.big else SMALL) * s, 1)
            t0 = max(0, int(round((appear(t, b) - b.start) * 1000)))
            col = GOLD if t.gold else WHITE
            style = f"\\fn{FONT_NAMES[kind]}\\fs{size}\\i{1 if t.italic else 0}"
            fsp = ""
            if t.tight:
                fsp = f"\\fsp{round(size * 0.35)}\\t({t0},{t0 + 420},\\fsp0)"
            sep = " " if i else ""
            word = _esc(t.text)
            parts_txt.append(f"{{{style}\\c{col}\\alpha&HFF&\\blur7{fsp}\\t({t0},{t0 + 190},\\alpha&H00&\\blur0)}}{sep}{word}")
            parts_sh.append(f"{{{style}\\c&H000000&\\alpha&HFF&{fsp}\\t({t0},{t0 + 190},\\alpha&H70&)}}{sep}{word}")
        out_fx = "\\fad(0,120)"
        head = f"{{\\an{an}\\pos({x:.0f},{y:.0f}){out_fx}\\bord0\\shad0}}"
        head_sh = f"{{\\an{an}\\pos({x + 5:.0f},{y + 5:.0f}){out_fx}\\bord0\\shad0\\blur5}}"
        ev.append(f"Dialogue: 0,{_ts(b.start)},{_ts(b.end)},Base,,0,0,0,,{head_sh}{''.join(parts_sh)}")
        ev.append(f"Dialogue: 1,{_ts(b.start)},{_ts(b.end)},Base,,0,0,0,,{head}{''.join(parts_txt)}")
    return ev


def write_ass(blocks: list[Block], fonts_dir: Path, out: Path) -> Path:
    m = Measure(fonts_dir)
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Base,{FONT_NAMES['small']},{SMALL},&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,2,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    place(blocks, m)
    events = [e for b in blocks for e in block_events(b, m)]
    out.write_text(head + "\n".join(events) + "\n", encoding="utf-8")
    return out


def shown_words(blocks: list[Block]) -> list[str]:
    return [t.text for b in blocks for line in b.lines for t in line]

"""BTR v3 animated subtitles (style of claude/btr-subtitles-workflow.md), as an ASS file burned by libass.

Blocks of 2-7 stacked lines; small linking words in Monument Extended Regular, punch words in Heavy, gold
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
MARGIN = 60
EM = 1000 / (1040 + 320)      # libass scales the font so ascent+descent = size: 1 em = 0.735 × size
CAP = 0.72 * EM               # cap height in units of the size
DESC = 0.32 * EM              # descender, below the baseline
GOLD = "&H9ADFFC&"            # #FCDF9A in ASS (BGR)
WHITE = "&HFFFFFF&"
Y_FULL, Y_SPLIT = 1160, 960   # block centre: under the face on a full frame, on the seam of a split screen
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
    align: str = "c"          # c | l | stair
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
        meta.append(b.get("align", "c") if b.get("align") in ("c", "l", "stair") else "c")
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


def auto_blocks(words: list) -> list[Block]:
    """Fallback without the model: 2-3 lines of 1-3 words, the longest word of each block big."""
    blocks: list[Block] = []
    cur: list = []
    for i, w in enumerate(words):
        cur.append(w)
        end_sentence = bool(re.search(r"[.?!]$", w.text))
        gap = i + 1 < len(words) and words[i + 1].start - w.end > 0.35
        if len(cur) >= 7 or ((end_sentence or gap) and len(cur) >= 3) or i == len(words) - 1:
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
            blocks.append(Block(lines, "c"))
            cur = []
    return blocks


def timeline(blocks: list[Block], total: float, layout_at) -> None:
    """Block start/end on the reel, and where it sits (full frame or split screen)."""
    for i, b in enumerate(blocks):
        b.start = b.lines[0][0].start
        last = b.lines[-1][-1].end
        nxt = blocks[i + 1].lines[0][0].start if i + 1 < len(blocks) else total
        b.end = min(nxt, max(last + 0.35, b.start + 0.6), total)
        b.y_center = Y_SPLIT if layout_at(b.start + 0.05) == "split" else Y_FULL


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


def block_events(b: Block, m: Measure) -> list[str]:
    ev = []
    scales = [_line_sizes(line, m)[0] for line in b.lines]
    heights = [max((BIG if t.big else SMALL) * s for t in line) for line, s in zip(b.lines, scales)]
    total = sum(h * CAP for h in heights) + LINE_GAP * (len(heights) - 1)
    baseline = b.y_center - total / 2
    dur_ms = int(round((b.end - b.start) * 1000))
    for li, (line, s, hmax) in enumerate(zip(b.lines, scales, heights)):
        baseline += hmax * CAP + (LINE_GAP if li else 0)
        y = baseline + hmax * DESC                       # \an1/2: the anchor is the bottom of the line box
        if b.align == "c":
            an, x = 2, W / 2
        else:
            an, x = 1, MARGIN + (STAIR * li if b.align == "stair" else 0)
            x = min(x, W - MARGIN - _line_sizes(line, m)[1])
        parts_txt, parts_sh = [], []
        for i, t in enumerate(line):
            kind = "big" if t.big else "small"
            size = round((BIG if t.big else SMALL) * s, 1)
            t0 = max(0, int(round((t.start - b.start) * 1000)))
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
    events = [e for b in blocks for e in block_events(b, m)]
    out.write_text(head + "\n".join(events) + "\n", encoding="utf-8")
    return out


def shown_words(blocks: list[Block]) -> list[str]:
    return [t.text for b in blocks for line in b.lines for t in line]

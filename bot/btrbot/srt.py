"""SRT parsing helpers."""
import re
from dataclasses import dataclass

TC = re.compile(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})")


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _sec(m: re.Match) -> float:
    h, mi, s, ms = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000


def parse(text: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", text.replace("\r", "").strip()):
        lines = [l for l in block.split("\n") if l.strip()]
        for i, line in enumerate(lines):
            tcs = list(TC.finditer(line))
            if len(tcs) == 2 and "-->" in line:
                body = " ".join(lines[i + 1:]).strip()
                body = re.sub(r"<[^>]+>", "", body)
                if body:
                    cues.append(Cue(_sec(tcs[0]), _sec(tcs[1]), body))
                break
    return cues


def normalise_offset(cues: list[Cue]) -> tuple[list[Cue], float]:
    """DaVinci exports often start at 01:00:00:00. Shift so the video starts at 0."""
    if cues and cues[0].start >= 3600:
        off = 3600.0
        return [Cue(c.start - off, c.end - off, c.text) for c in cues], off
    return cues, 0.0


def plain_text(cues: list[Cue]) -> str:
    out, last = [], ""
    for c in cues:
        if c.text != last:  # YouTube ASR repeats rolling lines
            out.append(c.text)
        last = c.text
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def timed_text(cues: list[Cue], every: float = 30.0) -> str:
    """Transcript with a [mm:ss] marker roughly every `every` seconds (for chaptering / quote lookup)."""
    out, next_mark, last = [], 0.0, ""
    for c in cues:
        if c.start >= next_mark:
            out.append(f"\n[{fmt(c.start)}] ")
            next_mark = c.start + every
        if c.text != last:
            out.append(c.text + " ")
        last = c.text
    return "".join(out).strip()


def fmt(t: float) -> str:
    t = int(t)
    h, m, s = t // 3600, (t % 3600) // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def find_quote(cues: list[Cue], quote: str) -> float | None:
    """Start time of the cue window that best matches `quote` (fuzzy)."""
    from rapidfuzz import fuzz

    q = re.sub(r"[^\w\s']", "", quote.lower())
    best, best_t = 0.0, None
    for i in range(len(cues)):
        window = " ".join(c.text for c in cues[i:i + 4]).lower()
        window = re.sub(r"[^\w\s']", "", window)
        score = fuzz.partial_ratio(q, window)
        if score > best:
            best, best_t = score, cues[i].start
    return best_t if best >= 80 else None



def find_quote_start(cues: list[Cue], quote: str, near: float, within: float = 30.0) -> float | None:
    """Start of the cue where `quote` (first words of a short moment) BEGINS, near `near`: among the windows that
    hold it, the latest one (an earlier window only holds it because it also holds the cues before)."""
    from rapidfuzz import fuzz

    q = re.sub(r"[^\w\s']", "", (quote or "").lower())
    if not q.strip():
        return None
    scores = []
    for i, c in enumerate(cues):
        if abs(c.start - near) > within:
            continue
        window = re.sub(r"[^\w\s']", "", " ".join(x.text for x in cues[i:i + 3]).lower())
        scores.append((fuzz.partial_ratio(q, window), i))
    if not scores:
        return None
    best = max(sc for sc, _ in scores)
    if best < 80:
        return None
    return cues[max(i for sc, i in scores if sc >= best - 1)].start

def find_quote_end(cues: list[Cue], quote: str, after: float = 0.0, within: float = 150.0) -> float | None:
    """End time of the cue where `quote` (e.g. the last words of a moment) finishes, searching from `after`."""
    from rapidfuzz import fuzz

    q = re.sub(r"[^\w\s']", "", (quote or "").lower())
    if not q.strip():
        return None
    best, best_end = 0.0, None
    for i, c in enumerate(cues):
        if c.end < after or c.start > after + within:
            continue
        for j in range(i, min(i + 4, len(cues))):      # the shortest window that contains the phrase
            window = re.sub(r"[^\w\s']", "", " ".join(x.text for x in cues[i:j + 1]).lower())
            score = fuzz.partial_ratio(q, window)
            if score > best + 0.5:
                best, best_end = score, cues[j].end
            if score >= 95:
                break
    return best_end if best >= 80 else None


def _fold(s: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^\w\s']", " ", s)


def search(cues: list[Cue], query: str = "", at: float | None = None, around: int = 2, limit: int = 8) -> str:
    """What was said: the cues matching `query` (the phrase, else all its words within ~3 cues; plurals and case /
    accents ignored), each with `around` cues of context and its timecode; or the ~40 s around `at` (seconds)."""
    if not cues:
        return "pas de transcription pour cet épisode"
    if at is not None:
        sel = [c for c in cues if at - 20 <= c.start <= at + 20]
        return "\n".join(f"[{fmt(c.start)}] {c.text}" for c in sel) or "rien à ce moment-là"
    q = " ".join(_fold(query).split())
    words = [w for w in q.split() if len(w) >= 3] or q.split()
    if not q:
        return "rien à chercher"
    folded = [_fold(c.text) for c in cues]
    hits = []
    for i in range(len(cues)):
        win = " ".join(folded[i:i + 3])
        if q in " ".join(win.split()) or all(w in win for w in words):
            first = next((j for j in range(i, min(i + 3, len(cues))) if any(w in folded[j] for w in words)), i)
            if not hits or first > hits[-1] + around:
                hits.append(first)
    if not hits:
        return f"« {query} » n'est pas dans la transcription"
    out = []
    for i in hits[:limit]:
        lo, hi = max(0, i - around), min(len(cues), i + around + 1)
        out.append("\n".join(("» " if j == i else "  ") + f"[{fmt(cues[j].start)}] {cues[j].text}" for j in range(lo, hi)))
    more = f"\n(+ {len(hits) - limit} autres passages)" if len(hits) > limit else ""
    return f"{len(hits)} passage(s) :\n\n" + "\n\n".join(out) + more

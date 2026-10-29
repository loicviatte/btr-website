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

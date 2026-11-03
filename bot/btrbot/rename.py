"""A guest's name spelled wrong (Loïc 03.11: « Hannah Trever », not « Trevor »): the replacements used everywhere —
episode data, transcript, posts, ClickUp, Drive, YouTube. Pure functions (tests/guest_rename.py)."""
import json
import re
from pathlib import Path


def subs(old: str, new: str) -> list[tuple[re.Pattern, str]]:
    """The full name (also glued: #HannahTrevor, HANNAH-TREVOR / _ in file names) and each changed word alone (« Ms
    Trevor »), as written / UPPER / lower. Never inside another word nor an @handle."""
    ow, nw = old.split(), new.split()
    pairs = [(old, new)] + [(j.join(ow), j.join(nw)) for j in ("", "-", "_") if len(ow) > 1]
    if len(ow) == len(nw):
        pairs += [(a, b) for a, b in zip(ow, nw) if a != b and len(a) >= 3]
    out = []
    for a, b in dict.fromkeys(pairs):
        for f in (str, str.upper, str.lower):
            out.append((re.compile(r"(?<![A-Za-z@])" + re.escape(f(a)) + r"(?![A-Za-z])"), f(b)))
    return out


def fix(text: str, rules) -> str:
    for rx, to in rules:
        text = rx.sub(to, text)
    return text


def fix_obj(o, rules):
    """Every string of a JSON-like object, except local paths and links (a file name on disk / an id in a URL)."""
    if isinstance(o, dict):
        return {k: fix_obj(v, rules) for k, v in o.items()}
    if isinstance(o, list):
        return [fix_obj(v, rules) for v in o]
    if isinstance(o, str) and not o.startswith(("/", "file:", "http")):
        return fix(o, rules)
    return o


def fix_json(path: Path, rules) -> bool:
    """A JSON file fixed in place; True when something changed."""
    if not path.exists():
        return False
    before = json.loads(path.read_text())
    after = fix_obj(before, rules)
    if after == before:
        return False
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(after, ensure_ascii=False, indent=1))
    tmp.replace(path)
    return True


def fix_file(path: Path, rules) -> bool:
    text = path.read_text(encoding="utf-8", errors="replace")
    new = fix(text, rules)
    if new != text:
        path.write_text(new, encoding="utf-8")
    return new != text

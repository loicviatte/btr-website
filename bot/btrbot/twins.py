"""A video uploaded again (Loïc 07.11: EP15 Lene re-uploaded for a sound fix, same content and length).

A new unlisted video whose title or length matches an episode the bot already worked on is probably a V2 of it.
The bot asks which one to keep; when Loïc keeps the new one and reuses the V1 work, the whole episode folder is
moved under the new video id (thumbnails, axes, chapters, description, stories, reels…), the old id keeps a stub
(stage « replaced ») so nothing is done twice, and the V1's title / description / tags / thumbnail go on the V2.
"""
import json
import re
import shutil
import time
import unicodedata
from pathlib import Path

# words people add to a re-uploaded file name, never part of an episode title
_NOISE = r"\b(?:v\s*\d+|version\s*\d+|final|finale|new|nouvelle?|copy|copie|export|master|son|sound|audio|fix|fixed|mix)\b"
DURATION_TOL = 2          # seconds: same export = same length
MIN_LONG = 15 * 60        # a podcast episode, not a Short or a clip


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\.(mp4|mov|mkv|m4v|mxf)\b", " ", t)
    t = re.sub(r"\(\s*\d+\s*\)", " ", t)                     # « (1) » added by the OS to a copied file
    t = re.sub(r"[^a-z0-9]+", " ", t)                        # « EP15_Lene_FINAL » → words
    t = re.sub(_NOISE, " ", t)
    return " ".join(t.split())


def part_of(t: str) -> str | None:
    m = re.search(r"\bpart(?:ie)?\s*_?(\d)\b", t or "", re.I)
    return m.group(1) if m else None


def iso_seconds(d: str) -> int:
    """« PT1H52M3S » → 6723."""
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    dd, h, mi, s = (int(x or 0) for x in m.groups())
    return ((dd * 24 + h) * 60 + mi) * 60 + s


def is_twin(new_title: str, new_secs: int, old_titles: list[str], old_secs: int) -> str | None:
    """Why the new video looks like a re-upload of the old one (« titre » / « durée »), else None."""
    np_ = part_of(new_title)
    old_parts = {p for p in (part_of(t) for t in old_titles) if p}
    if np_ and old_parts and np_ not in old_parts:
        return None                                          # Part 1 vs Part 2 of the same guest
    nt = norm_title(new_title)
    if nt and any(nt == norm_title(t) for t in old_titles if t):
        return "titre"
    if new_secs >= MIN_LONG and old_secs >= MIN_LONG and abs(new_secs - old_secs) <= DURATION_TOL:
        return "durée"
    return None


def candidates(root: Path, exclude: str, max_age_days: int = 90) -> list[dict]:
    """Episodes the bot worked on recently (anything past the waiting stage, not already replaced)."""
    out = []
    eps = root / "episodes"
    if not eps.is_dir():
        return out
    now = time.time()
    for d in eps.iterdir():
        f = d / "state.json"
        if d.name == exclude or not f.is_file():
            continue
        try:
            s = json.loads(f.read_text())
        except ValueError:
            continue
        if s.get("stage") in ("new", "replaced") or s.get("replaced_by"):
            continue
        if now - float(s.get("created") or now) > max_age_days * 86400:
            continue
        titles = [s.get("title") or "", (s.get("final") or {}).get("title") or "", s.get("public_title") or ""]
        out.append({"vid": d.name, "titles": [t for t in titles if t], "stage": s.get("stage"),
                    "secs": int(s.get("duration_s") or 0), "created": float(s.get("created") or 0)})
    out.sort(key=lambda c: -c["created"])
    return out


def find(root: Path, vid: str, title: str, secs: int, duration_of=None) -> dict | None:
    """The episode this new video re-uploads, if any. `duration_of(vid)` asks YouTube for an old video's length
    when the bot never stored it (episodes made before 07.11)."""
    for c in candidates(root, vid):
        if not c["secs"] and duration_of:
            try:
                c["secs"] = int(duration_of(c["vid"]) or 0)
            except Exception:  # noqa: BLE001  (old video deleted / private to the API)
                c["secs"] = 0
        why = is_twin(title, secs, c["titles"], c["secs"])
        if why:
            return {**c, "why": why}
    return None


def _rewrite_ids(folder: Path, old: str, new: str) -> None:
    """Paths and links stored in the episode's JSON files follow the new id (ids are 11 unique characters)."""
    for f in folder.rglob("*.json"):
        try:
            txt = f.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if old in txt:
            f.write_text(txt.replace(old, new))


def move_episode(root: Path, old: str, new: str, title: str = "") -> None:
    """data/episodes/<old> becomes data/episodes/<new>; <old> keeps a stub that says where it went."""
    eps = root / "episodes"
    src, dst = eps / old, eps / new
    if not src.is_dir():
        raise RuntimeError(f"Dossier de l'épisode {old} introuvable.")
    if dst.exists():                                          # only an empty state can be there (just detected)
        if any(p.name != "state.json" for p in dst.iterdir()):
            raise RuntimeError(f"Le dossier {new} contient déjà du travail, je n'écrase rien.")
        shutil.rmtree(dst)
    src.rename(dst)
    _rewrite_ids(dst, old, new)
    st = json.loads((dst / "state.json").read_text())
    st["video_id"], st["replaces"], st["replaced_at"] = new, old, time.time()
    if title:
        st["upload_title"] = title
    (dst / "state.json").write_text(json.dumps(st, indent=1, ensure_ascii=False))
    src.mkdir()
    (src / "state.json").write_text(json.dumps(
        {"video_id": old, "stage": "replaced", "replaced_by": new, "created": st.get("created"),
         "title": st.get("title") or "", "replaced_at": time.time()}, indent=1, ensure_ascii=False))


def retire_episode(root: Path, old: str, new: str) -> Path:
    """Loïc wants everything made again on the new video: the old folder is put aside (data/replaced/<old>), out of
    every loop over the episodes, and <old> keeps a stub."""
    eps = root / "episodes"
    src = eps / old
    arch = root / "replaced" / old
    arch.parent.mkdir(parents=True, exist_ok=True)
    if arch.exists():
        shutil.rmtree(arch)
    st = json.loads((src / "state.json").read_text()) if (src / "state.json").is_file() else {}
    src.rename(arch)
    src.mkdir()
    (src / "state.json").write_text(json.dumps(
        {"video_id": old, "stage": "replaced", "replaced_by": new, "created": st.get("created"),
         "title": st.get("title") or "", "archived": str(arch), "replaced_at": time.time()}, indent=1, ensure_ascii=False))
    return arch


def move_registry(data: dict, old: str, new: str) -> None:
    """The registry's pointers to the old episode (active one, reels, topics, messages, badge) follow the new id."""
    if data.get("active") == old:
        data["active"] = new
    if data.get("reels_vid") == old:
        data["reels_vid"] = new
    for k, v in list((data.get("topic_ep") or {}).items()):
        if v == old:
            data["topic_ep"][k] = new
    for key in ("ep_msgs", "badges", "badges_applied"):
        d = data.get(key) or {}
        if old in d:
            val = d.pop(old)
            if isinstance(val, str):
                val = val.replace(f"/episodes/{old}/", f"/episodes/{new}/")
            d[new] = val

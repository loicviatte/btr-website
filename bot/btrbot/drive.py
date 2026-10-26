"""Watch the shared Google Drive folder where Loïc drops his DaVinci SRTs (folder shared by link, no login)."""
import re
import tempfile
from pathlib import Path

GENERIC = {"subtitle", "subtitles", "sous", "titres", "srt", "part", "partie", "final", "export", "copy", "ep", "episode",
           "btr", "the", "and", "with", "break", "routine", "podcast", "fr", "en", "eng"}


def list_srt(folder_id: str) -> list[tuple[str, str]]:
    """[(file_id, file_name)] of the .srt files in the folder."""
    import gdown
    with tempfile.TemporaryDirectory() as tmp:
        files = gdown.download_folder(id=folder_id, output=tmp, skip_download=True, quiet=True) or []
    return [(f.id, Path(f.path).name) for f in files if f.path.lower().endswith(".srt")]


def download(file_id: str, dest: Path) -> Path:
    import gdown
    dest.parent.mkdir(parents=True, exist_ok=True)
    gdown.download(id=file_id, output=str(dest), quiet=True)
    if not dest.exists() or dest.stat().st_size == 0:
        raise RuntimeError(f"téléchargement vide pour {dest.name}")
    return dest


def name_tokens(file_name: str) -> set[str]:
    stem = Path(file_name).stem.lower()
    words = re.split(r"[^a-zà-ÿ0-9]+", stem)
    return {w for w in words if len(w) >= 3 and w not in GENERIC and not re.fullmatch(r"(part|v)?\d+", w)}


def part_number(text: str) -> str | None:
    m = re.search(r"part(?:ie)?\s*_?(\d+)", text.lower())
    return m.group(1) if m else None


def matches(file_name: str, video_title: str) -> bool:
    """'oti_Subtitle_part2.srt' matches 'Oti Mabuse … part 2' (a name word, and the same part if both say one)."""
    title = (video_title or "").lower()
    if not any(t in title for t in name_tokens(file_name)):
        return False
    a, b = part_number(file_name), part_number(title)
    return a is None or b is None or a == b

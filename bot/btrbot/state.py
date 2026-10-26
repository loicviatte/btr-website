"""One JSON file per episode: data/episodes/<video_id>/state.json.

Stages, in order:
  new -> waiting_transcript -> axes_proposed -> frames_proposed -> thumbs_proposed
      -> published -> chapters_proposed -> done
"""
import json
import time
from pathlib import Path
from typing import Any

STAGES = [
    "new",
    "waiting_transcript",
    "axes_proposed",
    "frames_proposed",
    "thumbs_proposed",
    "published",
    "chapters_proposed",
    "done",
]


class Episode:
    def __init__(self, root: Path, video_id: str):
        self.video_id = video_id
        self.dir = root / "episodes" / video_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "state.json"
        self.data: dict[str, Any] = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text())
        else:
            self.data = {"video_id": video_id, "stage": "new", "created": time.time(), "chat": []}

    def __getitem__(self, k):
        return self.data.get(k)

    def __setitem__(self, k, v):
        self.data[k] = v

    def get(self, k, default=None):
        return self.data.get(k, default)

    @property
    def stage(self) -> str:
        return self.data["stage"]

    @stage.setter
    def stage(self, v: str) -> None:
        assert v in STAGES, v
        self.data["stage"] = v

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, ensure_ascii=False))
        tmp.replace(self.path)

    def file(self, name: str) -> Path:
        return self.dir / name


class Registry:
    """Which videos the bot has already seen, and which one is active in the chat."""

    def __init__(self, root: Path):
        self.root = root
        self.path = root / "registry.json"
        self.data = json.loads(self.path.read_text()) if self.path.exists() else {"seen": [], "active": None}

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=1))

    def seen(self, vid: str) -> bool:
        return vid in self.data["seen"]

    def mark_seen(self, vid: str) -> None:
        if vid not in self.data["seen"]:
            self.data["seen"].append(vid)
            self.save()

    @property
    def active(self) -> str | None:
        return self.data.get("active")

    @active.setter
    def active(self, vid: str | None) -> None:
        self.data["active"] = vid
        self.save()

    def episode(self, vid: str) -> Episode:
        return Episode(self.root, vid)

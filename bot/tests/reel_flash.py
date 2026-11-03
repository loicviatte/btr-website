"""A cut that lands a few frames before a camera switch: the other camera's flash is replaced by a held frame of the
neighbouring shot (Loïc 03.11, Hannah reel 7 at 23 s). Offline, no video."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402

fps = 25.0
shots = [{"a": 30.0, "b": 35.52, "kind": "guest", "cx": 0.4, "cy": 0.4, "fh": 0.2},
         {"a": 35.52, "b": 36.24, "kind": "marius", "cx": 0.6, "cy": 0.4, "fh": 0.2},
         {"a": 36.24, "b": 40.0, "kind": "guest", "cx": 0.45, "cy": 0.4, "fh": 0.2}]
pcs = R.pieces([(32.05, 35.52), (36.05, 39.64)], shots, fps, 60.0)
print([(round(p["out"], 2), p["frames"], p["kind"], p.get("hold")) for p in pcs])
flash = [p for p in pcs if p["frames"] < R.FLASH * fps]
assert len(flash) == 1 and flash[0]["kind"] == "guest" and abs(flash[0]["hold"] - 36.24) < 1e-6, flash
assert flash[0]["src"] == 36.04 and flash[0]["range"] == 1          # the sound stays where it was
assert sum(p["frames"] for p in pcs) == round((35.52 - 32.05) * fps) + round(39.64 * fps) - round(36.05 * fps)
# a whole range shorter than FLASH (no neighbour in its range) is left alone
pcs = R.pieces([(32.0, 35.0), (35.6, 35.8)], shots, fps, 60.0)
assert pcs[-1]["kind"] == "marius" and "hold" not in pcs[-1]
print("ok")

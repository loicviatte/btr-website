"""Frame accuracy of the reel cuts at any frame rate: a source whose frame k is painted with luma 20 + 4·(k % 50)
(so every output frame tells which source frame it came from), cut into pieces like a reel. Each piece must start
exactly on its first frame and run without skips or repeats, and the output must have exactly the planned frames.

    python tests/reel_frames.py <work_dir>
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402


def source(rate: str, path: Path, seconds: int = 14, offset: float = 0.0):
    g = f"color=c=gray:s=640x360:r={rate}:d={seconds},format=yuv420p,geq=lum='20+4*mod(N\\,50)':cb=128:cr=128"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", g, "-f", "lavfi", "-i",
           f"sine=f=440:d={seconds}", "-c:v", "libx264", "-preset", "ultrafast", "-qp", "0", "-g", "48",
           "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True)
    if offset:   # like yt-dlp's section download: stream copy from a non-keyframe start
        cut = path.with_name(path.stem + "_cut.mp4")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(offset), "-i", str(path), "-c", "copy", str(cut)], check=True)
        return cut
    return path


def frames_of(video: Path) -> list[int]:
    r = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(video), "-vf", "scale=32:18,format=yuv420p",
                        "-f", "rawvideo", "-"], capture_output=True, check=True)
    a = np.frombuffer(r.stdout, np.uint8).reshape(-1, 32 * 18 * 3 // 2)[:, :32 * 18]   # the Y plane, untouched
    return [int(round((v - 20) / 4)) % 50 for v in a.mean(axis=1)]


def check(rate: str, work: Path, offset: float = 0.0) -> int:
    src = source(rate, work / f"src_{rate.replace('/', '_')}.mp4", offset=offset)
    info = R.probe(src)
    fps = info["fps"]
    ranges = [(0.53, 2.31), (2.97, 4.4), (5.111, 7.9), (8.4, 11.07)]
    shots = [{"a": 0.0, "b": 3.6, "kind": "center"}, {"a": 3.6, "b": 6.4, "kind": "center"},
             {"a": 6.4, "b": 20.0, "kind": "center"}]
    pcs = R.pieces(ranges, shots, fps, info["duration"])
    info["w"], info["h"] = 640, 360
    video = R.render_video(src, pcs, info, work / f"pc_{rate.replace('/', '_')}_{offset}")
    got = frames_of(video)
    base = frames_of(src)[0]          # a source cut at `offset` starts on a later frame of the original
    want = [(base + p["f0"] + i) % 50 for p in pcs for i in range(p["frames"])]
    errors = sum(1 for g, w in zip(got, want) if g != w)
    print(f"{rate:>10} offset {offset}: {len(got)} frames (planned {len(want)}), wrong frames: {errors}")
    return errors + abs(len(got) - len(want))


if __name__ == "__main__":
    work = Path(sys.argv[1])
    work.mkdir(parents=True, exist_ok=True)
    bad = sum(check(r, work) for r in ("24000/1001", "25", "30000/1001", "50", "60"))
    bad += check("25", work, 3.3) + check("30000/1001", work, 4.27)
    assert bad == 0, bad
    print("OK")

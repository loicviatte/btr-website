"""Offline test of the reel render (no YouTube, no Claude): a synthetic clip with a Marius close-up, a guest close-up
and a wide shot of both, speech with silences. Checks the framing per shot, the silence cuts, the removed phrase,
that audio and video have the same length, and writes frames to look at.

    python tests/reel_offline.py <models_dir> <clip.mp4> <work_dir>
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402
from btrbot import subs  # noqa: E402
from btrbot.config import ASSETS  # noqa: E402
from btrbot.faces import Faces  # noqa: E402


def dur(p, kind):
    sel = "v:0" if kind == "v" else "a:0"
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", sel, "-show_entries", "stream=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def main(models, clip, work):
    models, clip, work = Path(models), Path(clip), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    info = R.probe(clip)
    words = R.Transcriber(models).words(R.extract_wav(clip, work / "a.wav"))
    i0, i1, conf = R.locate(words, "Well, I don't wish to see", "very like the old portrait.")
    assert i0 == 0 and conf > 90, (i0, conf)
    ranges = R.keep_ranges(words, i0, len(words) - 1, cut_phrases=["observed Phebe"])
    a, b = ranges[0][0], ranges[-1][1]
    faces = Faces(models)
    samples = [(t, R.classify(cv2.imread(str(p)), faces)) for t, p in R.sample_frames(clip, a, b, work / "frames")]
    shots = R.shot_layouts(samples, R.scene_cuts(clip, a, b), a, b)
    kinds = [s["kind"] for s in shots]
    print("shots:", [(round(s["a"], 2), round(s["b"], 2), s["kind"]) for s in shots])
    assert kinds == ["marius", "guest", "split"], kinds
    pcs = R.pieces(ranges, shots, info["fps"], info["duration"])
    video = R.render_video(clip, pcs, info, work / "pieces")
    audio = R.render_audio(clip, pcs, info["fps"], work)
    total = sum(p["frames"] for p in pcs) / info["fps"]
    ow = R.out_words(words, pcs, info["fps"])
    assert len(ow) == len(words) - 2, (len(ow), len(words))          # "observed Phebe" removed once
    blocks = subs.auto_blocks(ow)
    subs.timeline(blocks, total, lambda t: R.layout_at(pcs, t))
    fonts = subs.prepare_fonts(ASSETS, work / "fonts")
    out = R.final_mux(video, audio, subs.write_ass(blocks, fonts, work / "subs.ass"), fonts, work / "final.mp4", total)
    dv, da = dur(out, "v"), dur(out, "a")
    print(f"total {total:.2f}s · video {dv:.2f}s · audio {da:.2f}s · pieces {[(p['kind'], p.get('zoom'), p['frames']) for p in pcs]}")
    assert abs(dv - total) < 0.05 and abs(da - total) < 0.06, (dv, da, total)
    for t in (1.0, 3.5, 6.5, 12.5):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(out), "-frames:v", "1",
                        str(work / f"look_{t}.jpg")], check=True)
    (work / "report.json").write_text(json.dumps({"total": total, "pieces": len(pcs), "words": len(ow)}))
    print("OK")


if __name__ == "__main__":
    main(*sys.argv[1:4])

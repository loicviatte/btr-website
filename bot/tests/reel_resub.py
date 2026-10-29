"""Subtitles-only redo on a kept edit (base picture + sound + edit.json), with a word fix from Loïc. No network:
the layout model is unreachable here, so the automatic layout is used.

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/reel_resub.py <reel.mp4>
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot.config import Settings  # noqa: E402
from btrbot.pipeline import Pipeline  # noqa: E402
from btrbot.state import Episode  # noqa: E402
from btrbot import reels as R  # noqa: E402

src = Path(sys.argv[1])
cfg = Settings()
pipe = Pipeline(cfg)
ep = Episode(cfg.data_dir, "VIDRESUB001")
ep["guest_name"] = "Oti Mabuse"
work = ep.dir / "reels" / "r05"
work.mkdir(parents=True, exist_ok=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-an", "-c", "copy", str(work / "base.mp4")], check=True)
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-c", "copy", str(work / "audio.m4a")], check=True)
frames = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                             "stream=nb_read_frames", "-of", "csv=p=0", str(work / "base.mp4")],
                            capture_output=True, text=True).stdout.strip())
words = [{"text": t, "start": 0.5 + i * 0.45, "end": 0.9 + i * 0.45}
         for i, t in enumerate("and the key was to impress Muti and Craig, it's a checklist.".split())]
(work / "edit.json").write_text(json.dumps({"framing": R.FRAMING, "fps": 25.0, "frames": frames, "doubts": [], "confidence": 95, "missing_cuts": [],
                                            "words": words, "layout": [{"out": 0.0, "frames": frames, "kind": "guest"}]}))
res = pipe.reel_subtitles(ep, {"n": 5}, [{"from": "Muti", "to": "Motsi"}, {"from": "zebra", "to": "x"}], "")
print(res["said"], "|", res["fixes_not_found"], "|", res["on_screen"][:3])
assert "Motsi" in res["said"] and "Muti" not in res["said"] and res["fixes_not_found"] == ["zebra"]
assert Path(res["file"]).exists() and abs(res["duration"] - frames / 25) < 0.05
ass = (work / "subs.ass").read_text()
assert "Motsi" in ass and "Muti" not in ass
shutil.rmtree(ep.dir)
print("OK")

# a correction the model invents is refused; one with Loïc's own words, or a version heard in the SRT, is kept
ep2 = Episode(cfg.data_dir, "VIDRESUB002")
w2 = ep2.dir / "reels" / "r05"
w2.mkdir(parents=True, exist_ok=True)
(w2 / "edit.json").write_text(json.dumps({"alts": [{"audio": "its", "srt": "it's"}]}))
pipe.llm.reel_sub_feedback = lambda words, blocks, fb: {"fixes": [{"from": "Muti", "to": "Motsi"},
                                                                   {"from": "Its a checklist", "to": "gone with a checklist"},
                                                                   {"from": "its", "to": "it's"}], "reply": "ok."}
r = pipe.reel_feedback(ep2, 5, {"said": "Muti its a checklist"}, "je suis pas sûr de muti, peut-être sa soeur motsi")
assert [f["to"] for f in r["fixes"]] == ["Motsi", "it's"], r
assert "mots exacts" in r["reply"], r
shutil.rmtree(ep2.dir)
print("OK guard")

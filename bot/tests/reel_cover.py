"""Reel cover end to end, offline (the model's choices mocked): 4K stills of the guest kept at render time, face
sheet, cover rendered with the validated template, hook guarded (only words really said).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> MODELS_DIR=<models> python tests/reel_cover.py <clip.mp4>
"""
import json
import shutil
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402
from btrbot.config import Settings  # noqa: E402
from btrbot.pipeline import Pipeline  # noqa: E402
from btrbot.state import Episode  # noqa: E402

clip = Path(sys.argv[1])
cfg = Settings()
pipe = Pipeline(cfg)
ep = Episode(cfg.data_dir, "VIDCOVER001")
ep["guest_name"] = "Oti Mabuse"
ep.save()
work = ep.dir / "reels" / "r01"
work.mkdir(parents=True, exist_ok=True)
info = R.probe(clip)
samples = [(t, R.classify(cv2.imread(str(p)), pipe.faces)) for t, p in R.sample_frames(clip, 0, info["duration"], work / "frames")]
cands = R.cover_candidates(clip, samples, [(0.0, info["duration"])], work / "cover")
print("stills:", len(cands), [c["t"] for c in cands])
assert cands and all((work / "cover" / c["file"]).exists() for c in cands)
seen = {}


class FakeLLM:
    def reel_cover_pick(self, sheet):
        seen["sheet"] = sheet
        return [2, 1]

    def reel_captions(self, *a):
        return {"instagram": "x", "tiktok": "y", "cover": {"small": "I got", "big": "A", "gold": "YACHT"}}


pipe.llm = FakeLLM()
item = {"said": "I got a yacht for my husband", "captions": {"instagram": "x", "tiktok": "y"}}
res = pipe.reel_cover(ep, 1, item)
print(res)
assert Path(res["cover"]).exists() and seen.get("sheet") and res["cover_text"]["gold"] == "YACHT"
assert res["cover_pick"] == (2 if len(cands) > 1 else 1)
bad = pipe.reel_cover(ep, 1, dict(item, cover_text=res["cover_text"]), text={"small": "I never", "big": "GOT", "gold": "IT"})
assert bad["cover_text"]["gold"] == "YACHT", bad                       # words not said: hook kept from captions
again = pipe.reel_cover(ep, 1, item, pick=1)
assert again["cover_pick"] == 1
shutil.copy(res["cover"], Path(cfg.data_dir) / "cover_test.jpg")
print("OK")

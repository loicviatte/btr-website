"""Offline check: « 🎞️ Sélection » on The Chain's previous-guest photo (Loïc 03.11: he got Hannah's, not Oti's).

    TELEGRAM_BOT_TOKEN=x ANTHROPIC_API_KEY=x DATA_DIR=<tmp> python tests/prev_choices.py
"""
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import postmaker as PM, posts  # noqa: E402

tmp = Path(tempfile.mkdtemp())
ep = type("E", (), {})()
ep.dir, ep.video_id = tmp, "HANNAHVIDEO"
ep.get = lambda k, d=None: {"guest_name": "Hannah Trever"}.get(k, d)
st = posts.PostState.__new__(posts.PostState)
st.data = {"items": {"chain": {"kind": "chain", "files": ["x"]}},
           "shots": {"chain:prev": {"who": "prev", "t": None, "pt": 4322.0, "file": str(tmp / "prev_PjDZ8X_JWY0_4322.jpg"),
                                     "video": "PjDZ8X_JWY0", "name": "Oti Mabuse"}},
           "rejected": {"chain:prev": [4100.0]}}
st.save = lambda: None
M = PM.Maker.__new__(PM.Maker)
A = 3600.0
cands = [{"t": float(t), "kind": "guest", "cx": 0.5, "cy": 0.3, "fh": 0.2, "fw": 0.1, "top": 0.2, "sharp": 100 + t % 7,
          "n": 1, "area": 0.02} for t in range(0, 880, 2)]
M._prev_source = lambda ep_, name, sdir, vid=None: ("PjDZ8X_JWY0", "Oti Mabuse", A, tmp / "clip.mp4", cands)
M._prev_grab = lambda vid, a, clip, c, out: Image.new("RGB", (64, 36)).save(out)
M.refine = lambda shot: shot
posts.score = lambda c: c["sharp"]
out = M.choices(ep, st, "chain:prev")
assert 1 <= len(out) <= 10 and all(s["who"] == "prev" and s["t"] is None for s in out), out
assert all(abs(s["pt"] - 4322) > posts.REJECT_GAP and abs(s["pt"] - 4100) > posts.REJECT_GAP for s in out)
assert [s["n"] for s in out] == list(range(1, len(out) + 1)) and out == sorted(out, key=lambda s: s["pt"])
pick = PM.Maker.use_choice(st, "chain:prev", 3)
assert pick["who"] == "prev" and pick["pt"] == out[2]["pt"] and pick["video"] == "PjDZ8X_JWY0" and pick["name"] == "Oti Mabuse"
assert PM.Maker.prev_time(pick) == out[2]["pt"]
assert st.data["history"]["chain:prev"][-1]["pt"] == 4322.0
print("prev choices: OK")

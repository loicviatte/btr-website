"""Edge cases of the cut points (no audio model needed): the last word is never cut in half, start/end retouches
clip every range, and an impossible retouche fails with a clear message.

    python tests/reel_ranges.py <work_dir>
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402

work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
# speech = 440 Hz bursts; words with a 20 ms closure inside "the" and pauses of 0.2 s and 1.2 s
segs = [(0.5, 1.5), (1.7, 2.9), (4.1, 5.0), (5.2, 6.23), (6.25, 6.40), (6.45, 7.5), (8.7, 10.0), (10.2, 11.5)]
expr = "+".join(f"between(t,{a},{b})" for a, b in segs)
wav = work / "s.wav"
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=12:sample_rate=16000",
                "-af", f"volume='0.5*({expr})+0.001':eval=frame", "-ac", "1", str(wav)], check=True)
words = [R.Word(t, a, b) for t, (a, b) in zip("one two three four the five six seven".split(),
                                               [(0.5, 1.5), (1.7, 2.9), (4.1, 5.0), (5.2, 6.24), (6.24, 6.40),
                                                (6.45, 7.5), (8.7, 10.0), (10.2, 11.5)])]
E = R.Energy(wav)
# the moment ends on "the" while speech goes on: the end must not fall inside "the"
r, _ = R.keep_ranges(words, 0, 4, E)
print("end on 'the':", r[-1][1])
assert r[-1][1] >= 6.37, r
# long pause (1.2 s) shortened, short ones kept
r, _ = R.keep_ranges(words, 0, 7, E)
print("ranges:", [(round(a, 2), round(b, 2)) for a, b in r])
assert any(abs(b - 7.5) < 0.2 for a, b in r) and len(r) >= 3, r
# big retouches clip every range
r, _ = R.keep_ranges(words, 0, 7, E, end_shift=-9)
assert r[-1][1] < 3.0, r
r, _ = R.keep_ranges(words, 0, 7, E, start_shift=9.5)
assert r[0][0] > 9.5, r
try:
    R.keep_ranges(words, 0, 1, E, end_shift=-5)
    raise SystemExit("an impossible retouche should fail")
except RuntimeError as e:
    print("impossible retouche →", e)
print("OK")

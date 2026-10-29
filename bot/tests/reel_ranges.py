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

# a breath after the last word when the pause allows it, never into the next word
r, _ = R.keep_ranges(words, 0, 7, E)
assert 11.85 <= r[-1][1] <= 11.95, r                 # "seven" ends 11.5 → about +0.4 s
r, _ = R.keep_ranges(words, 0, 4, E)
assert 6.37 <= r[-1][1] < 6.45, r                     # "five" starts at 6.45: stop in the gap before it
# finish the sentence when the model stops one word short
fw = [R.Word(t, i * 0.3, i * 0.3 + 0.25) for i, t in enumerate("nothing left to give me. So then".split())]
assert R.finish_sentence(fw, 3) == 4, R.finish_sentence(fw, 3)
assert R.finish_sentence(fw, 4) == 4
fw2 = [R.Word(t, i * 0.3, i * 0.3 + 0.25) for i, t in enumerate("and then we went on and on and on and on".split())]
assert R.finish_sentence(fw2, 2) == 2                # no sentence end nearby: unchanged
# SRT vs audio: disagreements listed, nothing changed until a choice is made
from btrbot.srt import Cue  # noqa: E402
asr = [R.Word(t, 1 + i * 0.4, 1 + i * 0.4 + 0.35) for i, t in enumerate("and I had to impress muti and craig its a check list".split())]
cues = [Cue(100.0, 102.0, "And I had to impress Motsi"), Cue(102.0, 105.0, "and Craig, it's a checklist.")]
cased, diffs = R.compare_with_srt(asr, cues, 99.0)
assert [(d["audio"], d["srt"]) for d in diffs] == [("muti", "Motsi"), ("its", "it's"), ("check list", "checklist.")], diffs
assert [w.text for w in R.apply_choices(cased, diffs, {})][5] == "muti"          # no choice: the audio stays
chosen = R.apply_choices(cased, diffs, {0: "srt", 2: "srt"})
assert " ".join(w.text for w in chosen) == "And I had to impress Motsi and Craig, its a checklist.", chosen
fixed, nf = R.apply_fixes(chosen, [{"from": "its", "to": "it's"}])
assert " ".join(w.text for w in fixed) == "And I had to impress Motsi and Craig, it's a checklist." and not nf
print("OK 2")

# the moment's end found in the transcript, and the last words found despite a small word difference
cues2 = [Cue(10.0, 13.0, "I remember we had a trainer and I was like,"), Cue(13.0, 16.0, "could you please come and watch"),
         Cue(16.0, 19.5, "and she said it's disgusting."), Cue(19.5, 23.0, "So I got a yacht for my husband.")]
from btrbot import srt as S  # noqa: E402
assert S.find_quote_end(cues2, "I got a yacht for my husband", 10) == 23.0
assert S.find_quote_end(cues2, "she said it's disgusting", 10) == 19.5
ws = [R.Word(t, i * 0.3, i * 0.3 + 0.25) for i, t in enumerate("so I got a yacht for my husband and then".split())]
i, sc = R._find(ws, "I got the yacht for my husband", end=True)
assert ws[i].text == "husband" and sc >= 70, (i, sc)
print("OK 3")

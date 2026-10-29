"""Framing of one person: the tight (zoomed) window never cuts the head, even on a source close-up or when the person
moves during the shot.   python tests/reel_framing.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot import reels as R  # noqa: E402

W, H = 3840, 2160
cases = {
    "medium shot": dict(cx=0.55, cy=0.35, fh=0.18),
    "source close-up (Oti)": dict(cx=0.5, cy=0.38, fh=0.33),
    "moves left-right": dict(cx=0.5, cy=0.35, fh=0.15, cx_lo=0.46, cx_hi=0.54),
    "near the edge": dict(cx=0.9, cy=0.3, fh=0.2),
    "high in frame": dict(cx=0.5, cy=0.16, fh=0.2),
}
for name, p in cases.items():
    for tight in (False, True):
        w, h, x, y = R.single_box({"kind": "guest", **p}, W, H, tight)
        fh = p["fh"] * H
        lo, hi = p.get("cx_lo", p["cx"]) * W, p.get("cx_hi", p["cx"]) * W
        head_l, head_r = lo - 0.75 * fh, hi + 0.75 * fh            # face box + hair on each side
        head_t, head_b = p["cy"] * H - 0.5 * fh - 0.3 * fh, p["cy"] * H + 0.6 * fh
        inside = x <= max(0, head_l) and x + w >= min(W, head_r) and y <= max(0, head_t) and y + h >= min(H, head_b)
        assert abs(w / h - 1080 / 1920) < 0.01, (name, w, h)
        if head_r - head_l <= H * 1080 / 1920:            # else not possible in 9:16, even at full height
            assert inside, (name, tight, (w, h, x, y), (head_l, head_r, head_t, head_b))
        print(f"{name:24s} {'tight' if tight else 'wide '} zoom ×{H / h:.2f}")
print("OK")

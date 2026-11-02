#!/usr/bin/env python3
"""Straighten and crop a polaroid photo so none of the table/background shows.

python3 tools/auto/polaroid_crop.py <in.jpg> <out.jpg>
Finds the background (saturated or dark colour touching the photo's edges), fits a line on each side of the
polaroid, corrects the perspective to a rectangle, then trims any remaining background. Needs opencv-python.
"""
import sys
import cv2
import numpy as np


def bgmask(im):
    hsv = cv2.cvtColor(im, cv2.COLOR_BGR2HSV)
    cand = ((hsv[..., 1] > 70) | (hsv[..., 2] < 110)).astype(np.uint8)
    n, lab = cv2.connectedComponents(cand)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    return np.isin(lab, list(border)).astype(np.uint8)


def fit(bg, side):
    h, w = bg.shape
    P = []
    if side in 'lr':
        for y in range(int(h * .08), int(h * .92)):
            row = bg[y] if side == 'l' else bg[y][::-1]
            k = 0
            while k < w // 4 and row[k]:
                k += 1
            if 0 < k < w // 4:
                P.append((y, k if side == 'l' else w - k))
        if len(P) < h * .15:
            return (0.0, 0.0 if side == 'l' else w - 1)
    else:
        for x in range(int(w * .08), int(w * .92)):
            col = bg[:, x] if side == 't' else bg[:, x][::-1]
            k = 0
            while k < h // 4 and col[k]:
                k += 1
            if 0 < k < h // 4:
                P.append((x, k if side == 't' else h - k))
        if len(P) < w * .15:
            return (0.0, 0.0 if side == 't' else h - 1)
    P = np.array(P, float)
    a, b = np.polyfit(P[:, 0], P[:, 1], 1)
    r = np.abs(P[:, 1] - (a * P[:, 0] + b))
    keep = r < np.percentile(r, 80) + 1
    return tuple(np.polyfit(P[keep, 0], P[keep, 1], 1))


def inter(v, hz):  # v: x = a*y + b ; hz: y = c*x + d
    a, b = v
    c, d = hz
    y = (c * b + d) / (1 - c * a)
    return (a * y + b, y)


def crop(im):
    bg = bgmask(im)
    L, R, T, B = fit(bg, 'l'), fit(bg, 'r'), fit(bg, 't'), fit(bg, 'b')
    tl, tr, br, bl = inter(L, T), inter(R, T), inter(R, B), inter(L, B)
    W = int((np.hypot(tr[0] - tl[0], tr[1] - tl[1]) + np.hypot(br[0] - bl[0], br[1] - bl[1])) / 2)
    H = int((np.hypot(bl[0] - tl[0], bl[1] - tl[1]) + np.hypot(br[0] - tr[0], br[1] - tr[1])) / 2)
    M = cv2.getPerspectiveTransform(np.float32([tl, tr, br, bl]), np.float32([[0, 0], [W, 0], [W, H], [0, H]]))
    out = cv2.warpPerspective(im, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=(0, 140, 200))
    bg2 = cv2.dilate(bgmask(out), np.ones((3, 3), np.uint8))
    x0, y0, x1, y1 = 0, 0, W, H
    while True:
        sides = {'t': bg2[y0, x0:x1].sum(), 'b': bg2[y1 - 1, x0:x1].sum(), 'l': bg2[y0:y1, x0].sum(), 'r': bg2[y0:y1, x1 - 1].sum()}
        k = max(sides, key=sides.get)
        if sides[k] == 0:
            break
        if k == 't': y0 += 1
        elif k == 'b': y1 -= 1
        elif k == 'l': x0 += 1
        else: x1 -= 1
    m = 3
    return out[y0 + m:y1 - m, x0 + m:x1 - m]


if __name__ == '__main__':
    im = cv2.imread(sys.argv[1])
    cv2.imwrite(sys.argv[2], crop(im), [cv2.IMWRITE_JPEG_QUALITY, 90])

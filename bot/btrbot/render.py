"""Build the three thumbnails (YouTube, Instagram vertical, square) from chosen 4K frames, with the validated BTR templates."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
import numpy as np
from PIL import Image

from . import design, imaging
from .config import ASSETS, TEMPLATES

env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=select_autoescape(["html"]))


def _shot(html: Path, out_png: Path, w: int, h: int) -> dict:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.goto(html.as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_load_state("networkidle")
        info = pg.evaluate("window.fit()")
        pg.screenshot(path=str(out_png))
        b.close()
    return info


def _names(full: str) -> tuple[str, str]:
    parts = full.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def youtube(work: Path, guest_4k: Path, guest_cx: float, marius_4k: Path, marius_cx: float,
            quote: dict, guest_name: str, d: dict | None = None) -> Path:
    """guest_cx / marius_cx: face centre x as a fraction of frame width. d: layout settings (design.load)."""
    d = d or design.load(Path("/nonexistent"), "youtube")
    work.mkdir(parents=True, exist_ok=True)
    g = Image.open(guest_4k).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    m = Image.open(marius_4k).convert("RGB").resize((1920, 1080), Image.LANCZOS)
    g.save(work / "yt_guest_bg.jpg", quality=92)
    m.save(work / "yt_marius_bg.jpg", quality=92)
    imaging.cutout(g).save(work / "yt_guest_cut.png")
    imaging.cutout(m).save(work / "yt_marius_cut.png")
    # faces land where they sit in the validated template: guest ~x 400, Marius ~x 1560
    gl = int(max(-1100, min(0, 400 - guest_cx * 1920)))
    ml = int(max(450, min(1000, 1560 - marius_cx * 1920)))
    n1, n2 = _names(guest_name)
    html = env.get_template("youtube.html").render(
        assets=ASSETS.as_uri(), guest_bg="yt_guest_bg.jpg", marius_bg="yt_marius_bg.jpg",
        guest_cut="yt_guest_cut.png", marius_cut="yt_marius_cut.png", guest_left=gl, marius_left=ml,
        top=quote["top"], key=quote["key"], bottom=quote["bottom"], name1=n1, name2=n2,
        max_w=900, center=int((400 + 1560) / 2), d=d)
    page = work / "youtube.html"
    page.write_text(html)
    png = work / "thumb_youtube.png"
    _shot(page, png, 1920, 1080)
    jpg = work / "thumb_youtube.jpg"
    Image.open(png).convert("RGB").save(jpg, quality=90, optimize=True)  # YouTube limit: 2 MB
    return jpg


def instagram(work: Path, models_dir: Path, guest_4k: Path, face: dict, quote: dict, guest_name: str,
              d: dict | None = None) -> Path:
    """face: {cx, top, fh} from the scan (fractions of the frame). d: layout settings (design.load)."""
    d = d or design.load(Path("/nonexistent"), "instagram")
    work.mkdir(parents=True, exist_ok=True)
    src = Image.open(guest_4k).convert("RGB")
    W, H = src.size                       # usually 3840x2160
    k = W / 3840
    sw = int(1216 * k)                    # 9:16 strip width at source scale
    x0 = int(max(0, min(W - sw, face["cx"] * W - 0.46 * sw)))
    head_top = (face["top"] - 0.28 * face["fh"]) * H          # hair above the face box
    ext = int(max(0, min(900 * k, 585 * k - head_top)))      # head top lands ~y 520 of 1920
    full_h = int(sw * 16 / 9)
    crop = src.crop((x0, 0, x0 + sw, min(H, full_h - ext)))
    extended = imaging.extend_top(models_dir, crop, ext)
    s = 1080 / sw
    extended.resize((1080, 1920), Image.LANCZOS).save(work / "ig_bg.jpg", quality=92)
    cut = imaging.cutout(crop)
    cut_h = round(crop.size[1] * s)
    cut_r = cut.resize((1080, cut_h), Image.LANCZOS)
    cut_r.save(work / "ig_cut.png")
    alpha = np.asarray(cut_r.getchannel("A"))
    profile = []                          # head outline [canvas y, left x, right x]: the quote wraps around it
    for y in range(0, cut_h, 3):
        xs = np.where(alpha[y] > 128)[0]
        if len(xs):
            profile.append([y + round(ext * s), int(xs.min()), int(xs.max())])
    words = quote["bottom"].split()
    bl, br = (words[0], " ".join(words[1:])) if len(words) > 1 else ("", quote["bottom"])
    n1, n2 = _names(guest_name)
    html = env.get_template("instagram.html").render(
        assets=ASSETS.as_uri(), bg="ig_bg.jpg", cut="ig_cut.png", cut_top=round(ext * s), cut_h=cut_h,
        top=quote["top"], key=quote["key"], bottom_left=bl, bottom_right=br, name1=n1, name2=n2,
        profile=profile, max_w=860, d=d)
    page = work / "instagram.html"
    page.write_text(html)
    png = work / "thumb_instagram.png"
    _shot(page, png, 1080, 1920)
    jpg = work / "thumb_instagram.jpg"
    Image.open(png).convert("RGB").save(jpg, quality=92)
    return jpg


def square(work: Path, guest_cx: float, marius_cx: float, quote: dict, guest_name: str, d: dict | None = None) -> Path:
    """1080x1080 post, guest left / Marius right. Reuses the 1920x1080 frames and cutouts made by youtube()."""
    d = d or design.load(Path("/nonexistent"), "square")
    k = 1.1                                   # frames shown at 2112x1188, as in the validated canvas board
    w, h = round(1920 * k), round(1080 * k)
    gl = int(max(1080 - w, min(0, 300 - guest_cx * w)))     # guest face ~x 300
    ml = int(max(1080 - w, min(400, 790 - marius_cx * w)))  # Marius face ~x 790
    n1, n2 = _names(guest_name)
    html = env.get_template("square.html").render(
        assets=ASSETS.as_uri(), guest_bg="yt_guest_bg.jpg", marius_bg="yt_marius_bg.jpg",
        guest_cut="yt_guest_cut.png", marius_cut="yt_marius_cut.png", guest_left=gl, marius_left=ml,
        img_w=w, img_h=h, img_top=-10, marius_front=d["marius_front"], d=d, fade_a=max(0, 438 - ml), fade_b=max(1, 658 - ml),
        top=quote["top"], key=quote["key"], bottom=quote["bottom"], name1=n1, name2=n2, max_w=960)
    page = work / "square.html"
    page.write_text(html)
    png = work / "thumb_square.png"
    _shot(page, png, 1080, 1080)
    jpg = work / "thumb_square.jpg"
    Image.open(png).convert("RGB").save(jpg, quality=92)
    return jpg

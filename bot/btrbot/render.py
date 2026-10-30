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
        b = p.chromium.launch(timeout=60000)
        pg = b.new_page(viewport={"width": w, "height": h})
        pg.set_default_timeout(60000)
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


def badge(work: Path, bg: Path, part: str) -> Path:
    """An existing YouTube thumbnail (any size, 16:9) + the PART badge, as a 1920x1080 JPEG."""
    work.mkdir(parents=True, exist_ok=True)
    Image.open(bg).convert("RGB").resize((1920, 1080), Image.LANCZOS).save(work / "badge_bg.jpg", quality=95)
    page = work / "badge.html"
    page.write_text(env.get_template("badge.html").render(assets=ASSETS.as_uri(), bg="badge_bg.jpg", d={"part": part}))
    png = work / f"thumb_part{part}.png"
    _shot(page, png, 1920, 1080)
    jpg = work / f"thumb_part{part}.jpg"
    Image.open(png).convert("RGB").save(jpg, quality=90, optimize=True)
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


def cover_box(W: int, H: int, face: dict) -> tuple[float, float, float, float]:
    """(x0, y0, width, height) of the cover's 9:16 window in a W×H still: full height when the face sits in the upper
    part; a face lower in the frame is brought up to ~1/3 of the cover by cropping closer (never closer than 60 % of
    the height, never cutting the head), so the hook below does not run over it. face["zoom"] (Loïc's « zoom x1.25 »)
    tightens that window around the face, which keeps its place on the cover."""
    c, fh = face.get("cy", 0.35) * H, face.get("fh", 0.2) * H
    if abs(W / H - 9 / 16) < 0.02:                     # already vertical (a frame of the edit)
        x0, y0, sw, h = 0.0, 0.0, float(W), float(H)
    else:
        h = H if c <= 0.36 * H else min(H, max(0.6 * H, fh * 2.6, (H - c) / 0.68))
        y0 = max(0.0, min(H - h, c - 0.32 * h))
        sw = h * 9 / 16
        x0 = max(0.0, min(W - sw, face.get("cx", 0.5) * W - sw / 2))
    z = min(1.5, max(1.0, float(face.get("zoom") or 1)))
    if z > 1:
        cx = face.get("cx", 0.5) * W
        x0, y0 = cx - (cx - x0) / z, c - (c - y0) / z
        sw, h = sw / z, h / z
        x0, y0 = max(0.0, min(W - sw, x0)), max(0.0, min(H - h, y0))
    return x0, y0, sw, h


def cover_crop(src: Image.Image, face: dict) -> Image.Image:
    W, H = src.size
    x0, y0, sw, h = cover_box(W, H, face)
    if (x0, y0, sw, h) == (0.0, 0.0, float(W), float(H)):
        return src
    return src.crop((int(x0), int(y0), int(x0 + sw), int(y0 + h)))


GRID = {"centre": (240, 1680), "haut": (0, 1440)}   # Instagram profile grid (3:4) out of the 9:16 cover
TEXT_BOTTOM = 1400                                   # bottom of the hook block (bottom: 520 px in the template)


def grid_check(W: int, H: int, face: dict, text_top: float = 900.0) -> dict:
    """Where the head (hair included) and the hook land on the cover, and whether both stay whole in the 3:4 grid
    crops (centre = Instagram's default, haut = the team's rule « face and text inside the top 1080×1440 »)."""
    x0, y0, sw, h = cover_box(W, H, face)
    k = 1920 / h
    c, fh = face.get("cy", 0.35) * H, face.get("fh", 0.2) * H
    head_top, chin = (c - 0.6 * fh - y0) * k, (c + 0.6 * fh - y0) * k     # forehead (hair may go), chin
    issues = []
    for name, (a, b) in GRID.items():
        if head_top < a + 10:
            issues.append(f"visage coupé en haut (grille {name})")
        if TEXT_BOTTOM > b - 10:
            issues.append(f"texte coupé en bas (grille {name})")
    if chin > text_top + 60:
        issues.append("texte sur le menton")
    return {"head_top": round(head_top), "chin": round(chin), "text_top": round(text_top), "issues": issues}


def grid_preview(cover: Path, out: Path) -> Path:
    """The cover as the profile grid shows it: full 9:16, then the 3:4 crops (centre, haut), side by side."""
    from PIL import ImageDraw, ImageFont
    im = Image.open(cover).convert("RGB")
    tiles = [("reel 9:16", im)] + [(f"grille 3:4 ({n})", im.crop((0, a, 1080, b))) for n, (a, b) in GRID.items()]
    th = 640
    sizes = [(int(t.width * th / t.height), th) for _, t in tiles]
    sheet = Image.new("RGB", (sum(w for w, _ in sizes) + 20 * (len(tiles) - 1), th + 44), (20, 20, 20))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 24)
    except OSError:
        font = ImageFont.load_default()
    x = 0
    for (label, t), (w, h) in zip(tiles, sizes):
        sheet.paste(t.resize((w, h), Image.LANCZOS), (x, 44))
        d.text((x + 6, 8), label, fill=(254, 203, 122), font=font)
        x += w + 20
    sheet.save(out, quality=88)
    return out


def reel_cover(work: Path, still: Path, face: dict, text: dict, guest_name: str, out: Path) -> Path:
    """Reel cover 1080×1920 (template validated on Oti P2 « They just DON'T CARE. »): the 4K still cut to 9:16 on
    the guest's face (full height), dark + gold veils, then the hook: small line / BIG / BIG gold italic, and the name."""
    work.mkdir(parents=True, exist_ok=True)
    crop = cover_crop(Image.open(still).convert("RGB"), face)
    crop.resize((1080, 1920), Image.LANCZOS).save(work / "cover_bg.jpg", quality=94)
    html = env.get_template("reel_cover.html").render(
        assets=ASSETS.as_uri(), bg="cover_bg.jpg", name=guest_name,
        **{k: str(text.get(k) or "").replace("'", "’") for k in ("small", "big", "gold")})
    page = work / "reel_cover.html"
    page.write_text(html)
    png = work / "reel_cover.png"
    info = _shot(page, png, 1080, 1920) or {}
    Image.open(png).convert("RGB").save(out, quality=94)
    png.unlink(missing_ok=True)
    W, H = Image.open(still).size
    chk = grid_check(W, H, face, float(info.get("top") or 900))
    (out.parent / (out.stem + ".check.json")).write_text(__import__("json").dumps(chk))
    grid_preview(out, out.parent / (out.stem + "_grille.jpg"))
    return out


def cover_sheet(stills: list[Path], faces: list[dict], out: Path, cols: int = 4) -> Path:
    """Each candidate as the cover would show it (9:16 window, the hook zone darkened), numbered from 1."""
    from PIL import ImageDraw, ImageFont
    tw, th = 270, 480
    rows = (len(stills) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 34)
    except OSError:
        font = ImageFont.load_default()
    veil = Image.new("L", (tw, th))
    for y in range(th):                                # the template's dark veil from 34 % of the height
        veil.paste(int(150 * min(1, max(0, (y / th - 0.34) / 0.28))), (0, y, tw, y + 1))
    for i, (p, f) in enumerate(zip(stills, faces)):
        im = cover_crop(Image.open(p).convert("RGB"), f).resize((tw, th), Image.LANCZOS)
        im = Image.composite(Image.new("RGB", (tw, th), (8, 4, 3)), im, veil)
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 56, y + 46], fill=(0, 0, 0))
        d.text((x + 8, y + 2), str(i + 1), fill=(254, 203, 122), font=font)
    sheet.save(out, quality=88)
    return out


def mouth_sheet(frames: list[Path], faces: list[dict], out: Path, cols: int = 8) -> Path:
    """The guest's whole face (mouth included) on each frame, numbered from 1: to tell open mouths from closed ones."""
    from PIL import ImageDraw, ImageFont
    tw, th = 160, 200
    rows = (len(frames) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    for i, (p, f) in enumerate(zip(frames, faces)):
        im = Image.open(p).convert("RGB")
        W, H = im.size
        fh, fw = f.get("fh", 0.2), f.get("fw", 0.1)
        box = ((f["cx"] - fw * 0.75) * W, (f["cy"] - fh * 0.7) * H, (f["cx"] + fw * 0.75) * W, (f["cy"] + fh * 0.75) * H)
        crop = im.crop(tuple(int(max(0, v)) for v in box))
        crop.thumbnail((tw, th))
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(crop, (x, y))
        d.rectangle([x, y, x + 34, y + 26], fill=(0, 0, 0))
        d.text((x + 4, y + 1), str(i + 1), fill=(254, 203, 122), font=font)
    sheet.save(out, quality=88)
    return out

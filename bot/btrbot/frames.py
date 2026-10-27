"""Find good close-up frames of the guest and of Marius in the episode video."""
import json
import subprocess
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFont

from .faces import MATCH, NOT_MATCH, Faces, sharpness

YT = "https://www.youtube.com/watch?v={}"


def _ydl_opts(cookies: Path | None, fmt: str, out: str | None = None) -> dict:
    o = {"format": fmt, "quiet": True, "no_warnings": True, "noprogress": True}
    if cookies and cookies.exists():
        o["cookiefile"] = str(cookies)
    if out:
        o["outtmpl"] = out
    return o


def download_scan_copy(video_id: str, dest: Path, cookies: Path | None) -> Path:
    """Low-res video-only copy (720p) used to scan for faces."""
    import yt_dlp
    if dest.exists():
        return dest
    with yt_dlp.YoutubeDL(_ydl_opts(cookies, "bv*[height<=720][ext=mp4]/bv*[height<=720]", str(dest))) as y:
        y.download([YT.format(video_id)])
    return dest


def full_res_url(video_id: str, cookies: Path | None) -> str:
    import yt_dlp
    with yt_dlp.YoutubeDL(_ydl_opts(cookies, "bv*[height<=2160]")) as y:
        info = y.extract_info(YT.format(video_id), download=False)
    return info["url"]


def grab(src: str, t: float, out: Path) -> Path:
    """One frame at time t from a URL or file (seek before input = fast over HTTP)."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.2f}", "-i", src,
                    "-frames:v", "1", "-q:v", "1", str(out)], check=True)
    return out


def sample(video: Path, out_dir: Path, every: float = 2.0) -> list[tuple[float, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    if not any(out_dir.glob("f_*.jpg")):
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf",
                        f"fps=1/{every},scale=1280:-2", "-q:v", "3", str(out_dir / "f_%05d.jpg")], check=True)
    files = sorted(out_dir.glob("f_*.jpg"))
    # ffmpeg's fps filter takes frame n at the MIDDLE of its window: (n-1)*every + every/2
    return [((int(p.stem[2:]) - 1) * every + every / 2, p) for p in files]


def scan(frames: list[tuple[float, Path]], faces: Faces, cache: Path) -> list[dict]:
    """Single-person close-ups, tagged marius / guest."""
    if cache.exists():
        return json.loads(cache.read_text())
    out = []
    for t, p in frames:
        img = cv2.imread(str(p))
        fs = [f for f in faces.analyse(img) if f.score > 0.85]
        if len(fs) != 1:
            continue
        f = fs[0]
        H, W = img.shape[:2]
        x, y, w, h = f.box
        if h / H < 0.16:          # wide shot, not a close-up
            continue
        who = "marius" if f.sim_marius >= MATCH else ("guest" if f.sim_marius < NOT_MATCH else None)
        if not who:
            continue
        out.append({"t": t, "file": str(p), "who": who, "sim": round(f.sim_marius, 3),
                    "cx": (x + w / 2) / W, "cy": (y + h / 2) / H, "fw": w / W, "fh": h / H,
                    "top": y / H, "sharp": sharpness(img, f.box)})
    cache.write_text(json.dumps(out))
    return out


def shortlist(cands: list[dict], who: str, k: int = 12, near: float | None = None, exclude=()) -> list[dict]:
    """Sharpest close-up per 20 s window, spread over the episode (and around the quote for the guest)."""
    # stricter than the scan thresholds: only unmistakable Marius (>= .5) or unmistakable non-Marius (< .2)
    sure = (lambda c: c["sim"] >= 0.5) if who == "marius" else (lambda c: c["sim"] < 0.2)
    pool = [c for c in cands if c["who"] == who and sure(c) and c["t"] not in exclude]
    best: dict[int, dict] = {}
    for c in pool:
        b = int(c["t"] // 20)
        score = c["sharp"] * (0.6 + c["fh"])
        if b not in best or score > best[b]["_s"]:
            best[b] = {**c, "_s": score}
    ranked = sorted(best.values(), key=lambda c: -c["_s"])
    picks: list[dict] = []
    if near is not None:
        picks += sorted([c for c in ranked if abs(c["t"] - near) <= 120], key=lambda c: abs(c["t"] - near))[: k // 3]
    for c in ranked:
        if len(picks) >= k:
            break
        if c not in picks:
            picks.append(c)
    return sorted(picks, key=lambda c: c["t"])


def contact_sheet(cands: list[dict], out: Path, cols: int = 4) -> Path:
    tw, th = 480, 270
    rows = (len(cands) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 40)
    except OSError:
        font = ImageFont.load_default()
    for i, c in enumerate(cands):
        im = Image.open(c["file"]).convert("RGB").resize((tw, th))
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(im, (x, y))
        d.rectangle([x, y, x + 64, y + 52], fill=(0, 0, 0))
        d.text((x + 10, y + 4), str(i + 1), fill=(254, 203, 122), font=font)
    sheet.save(out, quality=85)
    return out


def face_sheet(cands: list[dict], out: Path, cols: int = 4) -> Path:
    """Big crops of the upper face (eyes) of each candidate, numbered, to spot closed eyes."""
    tw, th = 480, 300
    rows = (len(cands) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    for i, c in enumerate(cands):
        im = Image.open(c["file"]).convert("RGB")
        W, H = im.size
        x0, x1 = (c["cx"] - c["fw"] * 0.6) * W, (c["cx"] + c["fw"] * 0.6) * W
        y0, y1 = (c["top"] - c["fh"] * 0.05) * H, (c["top"] + c["fh"] * 0.65) * H
        crop = im.crop((max(int(x0), 0), max(int(y0), 0), int(x1), int(y1)))
        k = min(tw / crop.width, th / crop.height)
        crop = crop.resize((max(int(crop.width * k), 1), max(int(crop.height * k), 1)), Image.LANCZOS)
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.paste(crop, (x, y))
        d.rectangle([x, y, x + 56, y + 46], fill=(0, 0, 0))
        d.text((x + 8, y + 2), str(i + 1), fill=(254, 203, 122), font=font)
    sheet.save(out, quality=90)
    return out

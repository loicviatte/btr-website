"""Cut-outs (rembg) and top extension (LaMa) for the thumbnails."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

_sessions: dict = {}
_lama = None


def _session(name):
    from rembg import new_session
    if name not in _sessions:
        _sessions[name] = new_session(name)
    return _sessions[name]


def release() -> None:
    """Free the cut-out / LaMa models (≈ 2-3 GB) once a render batch is done: on the 4 GB server, keeping them while
    Claude Code (dev mode) runs got the whole bot killed by the OOM killer (03.11)."""
    global _lama
    _sessions.clear()
    _lama = None
    import gc
    gc.collect()
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:  # noqa: BLE001
        pass


def _largest(mask):
    from scipy import ndimage
    lab, n = ndimage.label(mask)
    if not n:
        return mask.astype(bool)
    sizes = ndimage.sum(np.ones_like(mask), lab, range(1, n + 1))
    return lab == int(np.argmax(sizes)) + 1


def cutout(img: Image.Image) -> Image.Image:
    """Person cut-out with clean edges and a SOLID body (Loïc 03.11, Hannah: « on voit le gradient jaune à travers
    elle »): the general model (isnet) gives the outline and the hair, but is unsure on dark clothes against a dark
    set (half-transparent sleeves / legs → the gold haze showed through). The human model (u2net_human_seg) says
    where the body is; it only counts where isnet saw something (it also grabs chairs). The silhouette is filled
    (holes, and small gaps against the bottom / side edges of the frame) and fully opaque inside; soft alpha only on
    the outline. Largest blob only, small bridges to the set removed."""
    import cv2
    from rembg import remove
    from scipy import ndimage
    rgb = img.convert("RGB")
    rgba = remove(rgb, session=_session("isnet-general-use")).convert("RGBA")
    a_is = np.asarray(rgba.getchannel("A")).astype(np.float32) / 255
    try:
        a_hu = np.asarray(remove(rgb, session=_session("u2net_human_seg"), only_mask=True)).astype(np.float32) / 255
    except Exception:  # noqa: BLE001  (model download failed: isnet alone, as before)
        a_hu = np.zeros_like(a_is)
    k = max(3, int(min(img.size) * 0.008)) | 1
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    a = np.clip((a_is - 0.3) / 0.45, 0, 1)
    seen = cv2.dilate((a_is > 0.06).astype(np.uint8), ker) > 0
    sil = ((a > 0.5) | ((a_hu > 0.5) & seen)).astype(np.uint8)
    sil = _largest(cv2.morphologyEx(sil, cv2.MORPH_OPEN, ker))
    # holes, and gaps against the frame's bottom / sides (they count as body, the top doesn't): filled when a model
    # saw the person there (a lost sleeve / knee), left open when it's set seen between an arm and the body
    pad = np.pad(sil, 1, constant_values=True)
    pad[0, :] = False
    gaps = ndimage.binary_fill_holes(pad)[1:-1, 1:-1] & ~sil
    lab, n = ndimage.label(gaps)
    for i in range(1, n + 1):
        g = lab == i
        inside = not (g[-1].any() or g[:, 0].any() or g[:, -1].any())
        if (inside or (g[-1].any() and g.sum() < 0.06 * g.size)) and (a_is[g].mean() > 0.1 or a_hu[g].mean() > 0.5):
            sil |= g
    core = cv2.erode(sil.astype(np.uint8) * 255, ker)
    core = np.asarray(Image.fromarray(core).filter(ImageFilter.GaussianBlur(k / 3))).astype(np.float32) / 255
    keep = ndimage.binary_dilation(sil, iterations=max(2, k // 2))
    a = np.maximum(a * keep, core)
    m = Image.fromarray((a * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))
    rgba.putalpha(m)
    return rgba


def _lama_model(models_dir: Path):
    global _lama
    if _lama is None:
        import torch
        _lama = torch.jit.load(str(models_dir / "big-lama.pt"), map_location="cpu").eval()
    return _lama


def _inpaint(models_dir: Path, img: Image.Image, mask: Image.Image) -> Image.Image:
    import torch
    w, h = img.size
    pw, ph = (8 - w % 8) % 8, (8 - h % 8) % 8
    a = np.pad(np.asarray(img).astype(np.float32) / 255, ((0, ph), (0, pw), (0, 0)), mode="reflect")
    m = np.pad((np.asarray(mask) > 127).astype(np.float32), ((0, ph), (0, pw)), mode="reflect")
    with torch.no_grad():
        out = _lama_model(models_dir)(torch.from_numpy(a).permute(2, 0, 1)[None], torch.from_numpy(m)[None, None])
    return Image.fromarray((out[0].permute(1, 2, 0).numpy().clip(0, 1) * 255).astype(np.uint8)[:h, :w])


def extend_top(models_dir: Path, img: Image.Image, ext: int, scale: float = 0.5) -> Image.Image:
    """Generate `ext` px of set above the image (LaMa at half res, soft seam)."""
    W, H = img.size
    canvas = Image.new("RGB", (W, H + ext))
    canvas.paste(img.convert("RGB"), (0, ext))
    if ext <= 0:
        return canvas
    mask = Image.new("L", (W, H + ext), 0)
    mask.paste(255, (0, 0, W, ext + 4))
    w, h = int(W * scale) // 8 * 8, int((H + ext) * scale) // 8 * 8
    gen = _inpaint(models_dir, canvas.resize((w, h), Image.LANCZOS), mask.resize((w, h), Image.NEAREST))
    gen = gen.resize((W, H + ext), Image.LANCZOS)
    # long feather INTO the real image: no visible line where the generated set meets the frame
    fade = max(40, W // 6)
    ramp = np.zeros(H + ext, np.float32)
    ramp[:ext] = 1
    t = np.clip(1 - np.arange(fade) / fade, 0, 1)
    ramp[ext:ext + fade] = (t * t * (3 - 2 * t))[: len(ramp[ext:ext + fade])]
    blend = Image.fromarray((np.repeat(ramp[:, None], W, axis=1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6))
    return Image.composite(gen, canvas, blend)


def fill_out(models_dir: Path, img: Image.Image, region: tuple[float, float, float, float], max_side: int = 1600) -> Image.Image:
    """The region (x0, y0, x1, y1 in the photo's pixels, may go past its edges) as a picture: what lies outside the
    photo is generated by LaMa (the set around), with a soft seam. Used to pull a photo back (« moins zoomé »)."""
    W, H = img.size
    x0, y0, x1, y1 = (int(round(v)) for v in region)
    cw, ch = x1 - x0, y1 - y0
    canvas = Image.new("RGB", (cw, ch))
    canvas.paste(img.convert("RGB"), (-x0, -y0))
    mask = Image.new("L", (cw, ch), 255)
    ix0, iy0, ix1, iy1 = max(0, -x0), max(0, -y0), min(cw, W - x0), min(ch, H - y0)
    mask.paste(0, (ix0 + 3 if ix0 else 0, iy0 + 3 if iy0 else 0, ix1 - 3 if ix1 < cw else cw, iy1 - 3 if iy1 < ch else ch))
    if ix0 == 0 and iy0 == 0 and ix1 == cw and iy1 == ch:
        return canvas
    k = min(1.0, max_side / max(cw, ch))
    w, h = max(8, int(cw * k) // 8 * 8), max(8, int(ch * k) // 8 * 8)
    gen = _inpaint(models_dir, canvas.resize((w, h), Image.LANCZOS), mask.resize((w, h), Image.NEAREST)).resize((cw, ch), Image.LANCZOS)
    feather = mask.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(max(6, int(min(cw, ch) * 0.02))))
    return Image.composite(gen, canvas, feather)

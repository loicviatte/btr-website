"""Cut-outs (rembg) and top extension (LaMa) for the thumbnails."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

_rembg_session = None
_lama = None


def cutout(img: Image.Image) -> Image.Image:
    """Person cut-out with clean edges: largest blob only, small bridges to the set removed."""
    global _rembg_session
    import cv2
    from rembg import new_session, remove
    from scipy import ndimage
    if _rembg_session is None:
        _rembg_session = new_session("isnet-general-use")
    rgba = remove(img.convert("RGB"), session=_rembg_session).convert("RGBA")
    a = np.asarray(rgba.getchannel("A")).astype(np.float32) / 255
    a = np.clip((a - 0.3) / 0.45, 0, 1)
    solid = (a > 0.5).astype(np.uint8)
    k = max(3, int(min(img.size) * 0.008)) | 1
    opened = cv2.morphologyEx(solid, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    lab, n = ndimage.label(opened)
    if n:
        sizes = ndimage.sum(np.ones_like(opened), lab, range(1, n + 1))
        keep = ndimage.binary_dilation(lab == int(np.argmax(sizes)) + 1, iterations=max(2, k // 2))
        a = a * keep
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
    return Image.composite(gen, canvas, mask.filter(ImageFilter.GaussianBlur(10)))

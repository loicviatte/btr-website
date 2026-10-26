"""Local check: faces -> positions -> both thumbnails, from two 4K stills."""
import sys, time
from pathlib import Path
import cv2
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from btrbot.faces import Faces
from btrbot import render

guest, marius, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
models = Path(__file__).resolve().parents[1] / "models"
F = Faces(models)
def info(p):
    img = cv2.imread(str(p)); H, W = img.shape[:2]
    fs = sorted(F.analyse(cv2.resize(img, (1280, 720))), key=lambda f: -f.box[3])
    f = fs[0]; x, y, w, h = f.box
    return {"cx": (x + w/2)/1280, "top": y/720, "fh": h/720, "sim": f.sim_marius}
gi, mi = info(guest), info(marius)
print("guest", gi); print("marius", mi)
q = {"top": "People were", "key": "BREAKING", "bottom": "the rules"}
t = time.time(); print(render.youtube(out, guest, gi["cx"], marius, mi["cx"], q, "Peter Nash"), round(time.time()-t), "s")
t = time.time(); print(render.instagram(out, models, guest, gi, q, "Peter Nash"), round(time.time()-t), "s")

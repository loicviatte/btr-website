"""Face detection (YuNet) + recognition (SFace) to tell Marius from the guest."""
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .config import ASSETS

MATCH = 0.36   # SFace cosine threshold: same person above this
NOT_MATCH = 0.25


@dataclass
class Face:
    box: tuple[float, float, float, float]  # x, y, w, h in pixels
    score: float
    sim_marius: float
    row: np.ndarray


class Faces:
    def __init__(self, models_dir: Path):
        self.det = cv2.FaceDetectorYN.create(str(models_dir / "face_detection_yunet_2023mar.onnx"), "", (320, 320), 0.8, 0.3, 5000)
        self.rec = cv2.FaceRecognizerSF.create(str(models_dir / "face_recognition_sface_2021dec.onnx"), "")
        self.marius = self._marius_embedding()

    def detect(self, img: np.ndarray) -> list[np.ndarray]:
        h, w = img.shape[:2]
        self.det.setInputSize((w, h))
        _, faces = self.det.detect(img)
        return [] if faces is None else list(faces)

    def embed(self, img: np.ndarray, row: np.ndarray) -> np.ndarray:
        crop = self.rec.alignCrop(img, row)
        return self.rec.feature(crop)

    def _marius_embedding(self) -> np.ndarray:
        feats = []
        for p in sorted((ASSETS / "marius_refs").glob("*.jpg")):
            img = cv2.imread(str(p))
            fs = sorted(self.detect(img), key=lambda f: -f[2] * f[3])
            if fs:
                feats.append(self.embed(img, fs[0]))
        if not feats:
            raise RuntimeError("No face found in Marius reference photos")
        return np.mean(np.vstack(feats), axis=0, keepdims=True).astype(np.float32)

    def analyse(self, img: np.ndarray) -> list[Face]:
        out = []
        for row in self.detect(img):
            e = self.embed(img, row)
            sim = float(self.rec.match(e, self.marius, cv2.FaceRecognizerSF_FR_COSINE))
            out.append(Face(tuple(map(float, row[:4])), float(row[14]), sim, row))
        return out


def sharpness(img: np.ndarray, box) -> float:
    x, y, w, h = (int(v) for v in box)
    crop = img[max(y, 0):y + h, max(x, 0):x + w]
    if crop.size == 0:
        return 0.0
    return float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

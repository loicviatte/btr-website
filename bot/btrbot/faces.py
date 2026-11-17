"""Face detection (YuNet) + recognition (SFace) to tell Marius from the guest."""
import threading
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

    # One detector shared by every thread (reels, posts, thumbnails, run_in_executor): setInputSize from one thread
    # while another one detects broke OpenCV 5 (17.11: « buf.shape() == m.shape() in forwardGraph », image search failed)
    LOCK = threading.RLock()

    def detect(self, img: np.ndarray, min_score: float | None = None) -> list[np.ndarray]:
        h, w = img.shape[:2]
        with self.LOCK:
            self.det.setInputSize((w, h))
            if min_score is not None:
                self.det.setScoreThreshold(min_score)
            try:
                _, faces = self.det.detect(img)
            finally:
                if min_score is not None:
                    self.det.setScoreThreshold(0.8)
        return [] if faces is None else list(faces)

    def embed(self, img: np.ndarray, row: np.ndarray) -> np.ndarray:
        with self.LOCK:
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

    def analyse(self, img: np.ndarray, min_score: float | None = None) -> list[Face]:
        out = []
        for row in self.detect(img, min_score):
            e = self.embed(img, row)
            with self.LOCK:
                sim = float(self.rec.match(e, self.marius, cv2.FaceRecognizerSF_FR_COSINE))
            out.append(Face(tuple(map(float, row[:4])), float(row[14]), sim, row))
        return out


def sharpness(img: np.ndarray, box) -> float:
    x, y, w, h = (int(v) for v in box)
    crop = img[max(y, 0):y + h, max(x, 0):x + w]
    if crop.size == 0:
        return 0.0
    return float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())

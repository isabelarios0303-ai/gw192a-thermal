"""Region-of-interest (ROI) analysis.

ROIs are rectangular regions (normalized 0..1 or absolute px) that the caregiver can draw,
move, resize, and lock on the live view. Typical infant ROIs: frente (forehead), pecho
(chest), torso, extremidades (limbs).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class ROI:
    id: str
    name: str
    x0: float
    y0: float
    x1: float
    y1: float
    locked: bool = False
    normalized: bool = True  # if True, coords are fractions of width/height

    def to_pixels(self, w: int, h: int) -> tuple[int, int, int, int]:
        if self.normalized:
            x0, x1 = int(self.x0 * w), int(self.x1 * w)
            y0, y1 = int(self.y0 * h), int(self.y1 * h)
        else:
            x0, x1, y0, y1 = int(self.x0), int(self.x1), int(self.y0), int(self.y1)
        x0, x1 = sorted((max(0, min(w, x0)), max(0, min(w, x1))))
        y0, y1 = sorted((max(0, min(h, y0)), max(0, min(h, y1))))
        return x0, y0, x1, y1


@dataclass(slots=True)
class ROIResult:
    id: str
    name: str
    t_min: float
    t_max: float
    t_mean: float
    t_std: float
    pixels: int

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "t_min": round(self.t_min, 3),
            "t_max": round(self.t_max, 3),
            "t_mean": round(self.t_mean, 3),
            "t_std": round(self.t_std, 3),
            "pixels": self.pixels,
        }


def analyze_roi(celsius: np.ndarray, roi: ROI) -> ROIResult:
    h, w = celsius.shape
    x0, y0, x1, y1 = roi.to_pixels(w, h)
    if x1 <= x0 or y1 <= y0:
        raise ValueError(f"empty ROI {roi.id}")
    region = celsius[y0:y1, x0:x1]
    return ROIResult(
        id=roi.id,
        name=roi.name,
        t_min=float(region.min()),
        t_max=float(region.max()),
        t_mean=float(region.mean()),
        t_std=float(region.std()),
        pixels=int(region.size),
    )


def analyze_rois(celsius: np.ndarray, rois: list[ROI]) -> list[ROIResult]:
    return [analyze_roi(celsius, r) for r in rois]

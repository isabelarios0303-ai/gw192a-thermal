"""Per-frame thermal statistics (NumPy)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(slots=True)
class FrameStatistics:
    t_min: float
    t_max: float
    t_mean: float
    t_std: float
    hotspot: tuple[int, int]   # (x, y)
    coldspot: tuple[int, int]  # (x, y)
    centroid: tuple[float, float]
    histogram: list[int] = field(default_factory=list)
    hist_lo: float = 0.0
    hist_hi: float = 0.0

    def to_dict(self) -> dict:
        return {
            "t_min": round(self.t_min, 3),
            "t_max": round(self.t_max, 3),
            "t_mean": round(self.t_mean, 3),
            "t_std": round(self.t_std, 3),
            "hotspot": list(self.hotspot),
            "coldspot": list(self.coldspot),
            "centroid": [round(self.centroid[0], 2), round(self.centroid[1], 2)],
            "histogram": self.histogram,
            "hist_lo": round(self.hist_lo, 3),
            "hist_hi": round(self.hist_hi, 3),
        }


def compute_statistics(celsius: np.ndarray, bins: int = 32) -> FrameStatistics:
    h, w = celsius.shape
    t_min = float(celsius.min())
    t_max = float(celsius.max())
    t_mean = float(celsius.mean())
    t_std = float(celsius.std())

    hot_idx = np.unravel_index(int(np.argmax(celsius)), celsius.shape)
    cold_idx = np.unravel_index(int(np.argmin(celsius)), celsius.shape)
    hotspot = (int(hot_idx[1]), int(hot_idx[0]))
    coldspot = (int(cold_idx[1]), int(cold_idx[0]))

    # thermal centroid: weight by temperature above mean (locate the warm body)
    weights = np.clip(celsius - t_mean, 0.0, None)
    wsum = float(weights.sum())
    if wsum > 0:
        ys, xs = np.indices(celsius.shape)
        cx = float((weights * xs).sum() / wsum)
        cy = float((weights * ys).sum() / wsum)
    else:
        cx, cy = w / 2.0, h / 2.0

    hist, _ = np.histogram(celsius, bins=bins, range=(t_min, t_max if t_max > t_min else t_min + 1))

    return FrameStatistics(
        t_min=t_min,
        t_max=t_max,
        t_mean=t_mean,
        t_std=t_std,
        hotspot=hotspot,
        coldspot=coldspot,
        centroid=(cx, cy),
        histogram=hist.astype(int).tolist(),
        hist_lo=t_min,
        hist_hi=t_max,
    )

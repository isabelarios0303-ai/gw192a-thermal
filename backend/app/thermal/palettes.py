"""Thermal color palettes (256-entry BGR lookup tables for OpenCV).

Palettes: iron, rainbow, white_hot, black_hot, medical, grayscale.
Each LUT is a (256, 1, 3) uint8 array in BGR order so it can be used directly with
``cv2.applyColorMap`` semantics via ``cv2.LUT`` on a normalized single-channel image.
"""
from __future__ import annotations

import numpy as np

PaletteName = str


def _interp_lut(stops: list[tuple[float, tuple[int, int, int]]]) -> np.ndarray:
    """Build a 256x1x3 BGR LUT from RGB control stops at positions in [0,1]."""
    xs = np.linspace(0.0, 1.0, 256)
    pos = np.array([s[0] for s in stops])
    r = np.interp(xs, pos, [s[1][0] for s in stops])
    g = np.interp(xs, pos, [s[1][1] for s in stops])
    b = np.interp(xs, pos, [s[1][2] for s in stops])
    bgr = np.stack([b, g, r], axis=1).clip(0, 255).astype(np.uint8)
    return bgr.reshape(256, 1, 3)


_IRON = _interp_lut([
    (0.00, (0, 0, 0)),
    (0.25, (60, 0, 110)),
    (0.50, (160, 30, 120)),
    (0.70, (230, 90, 40)),
    (0.85, (255, 170, 20)),
    (1.00, (255, 255, 220)),
])

_RAINBOW = _interp_lut([
    (0.00, (0, 0, 130)),
    (0.20, (0, 80, 255)),
    (0.40, (0, 220, 220)),
    (0.60, (0, 220, 60)),
    (0.80, (255, 230, 0)),
    (1.00, (255, 30, 0)),
])

_WHITE_HOT = _interp_lut([(0.0, (0, 0, 0)), (1.0, (255, 255, 255))])
_BLACK_HOT = _interp_lut([(0.0, (255, 255, 255)), (1.0, (0, 0, 0))])
_GRAYSCALE = _WHITE_HOT

# Medical palette: emphasizes the febrile band — cool blues -> green -> warning amber -> red.
_MEDICAL = _interp_lut([
    (0.00, (10, 20, 90)),
    (0.35, (0, 140, 180)),
    (0.55, (0, 170, 90)),
    (0.72, (240, 210, 40)),
    (0.86, (240, 120, 20)),
    (1.00, (220, 20, 30)),
])

PALETTES: dict[PaletteName, np.ndarray] = {
    "iron": _IRON,
    "rainbow": _RAINBOW,
    "white_hot": _WHITE_HOT,
    "black_hot": _BLACK_HOT,
    "medical": _MEDICAL,
    "grayscale": _GRAYSCALE,
}


def normalize_for_display(
    celsius: np.ndarray, t_lo: float | None = None, t_hi: float | None = None
) -> np.ndarray:
    """Scale a Celsius matrix to uint8 [0,255] using fixed or auto min/max bounds."""
    lo = float(np.min(celsius)) if t_lo is None else t_lo
    hi = float(np.max(celsius)) if t_hi is None else t_hi
    span = (hi - lo) or 1.0
    norm = np.clip((celsius - lo) / span, 0.0, 1.0)
    return (norm * 255.0).astype(np.uint8)


def apply_palette(
    celsius: np.ndarray,
    palette: PaletteName = "iron",
    t_lo: float | None = None,
    t_hi: float | None = None,
) -> np.ndarray:
    """Return a BGR uint8 image colorized with the requested palette.

    Requires OpenCV; imported lazily so the module stays importable without cv2.
    """
    import cv2

    lut = PALETTES.get(palette, PALETTES["iron"])
    gray = normalize_for_display(celsius, t_lo, t_hi)
    gray3 = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
    return cv2.LUT(gray3, lut)

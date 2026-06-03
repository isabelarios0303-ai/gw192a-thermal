"""Rendering: colorized heatmaps, marker overlays, and RGB+thermal fusion (OpenCV)."""
from __future__ import annotations

import base64
from dataclasses import dataclass

import numpy as np

from .palettes import apply_palette
from .roi import ROI
from .statistics import FrameStatistics


@dataclass(slots=True)
class FusionParams:
    alpha: float = 0.5      # thermal transparency over RGB (0..1)
    dx: int = 0             # alignment offset x (px)
    dy: int = 0             # alignment offset y (px)
    scale: float = 1.0      # thermal scale relative to RGB
    rotation: float = 0.0   # degrees


def colorize(
    celsius: np.ndarray,
    palette: str = "iron",
    t_lo: float | None = None,
    t_hi: float | None = None,
    upscale: int = 3,
) -> np.ndarray:
    """Colorized BGR heatmap, optionally upscaled with smooth interpolation."""
    import cv2

    img = apply_palette(celsius, palette, t_lo, t_hi)
    if upscale > 1:
        img = cv2.resize(
            img, (img.shape[1] * upscale, img.shape[0] * upscale), interpolation=cv2.INTER_CUBIC
        )
    return img


def draw_markers(
    img: np.ndarray,
    stats: FrameStatistics,
    rois: list[ROI] | None = None,
    scale: int = 3,
    crosshair: bool = True,
) -> np.ndarray:
    """Overlay hotspot/coldspot/crosshair and ROI rectangles onto a colorized image."""
    import cv2

    out = img.copy()
    h, w = out.shape[:2]

    def pt(x: int, y: int) -> tuple[int, int]:
        return int(x * scale), int(y * scale)

    # hotspot (red) and coldspot (cyan)
    hx, hy = pt(*stats.hotspot)
    cx, cy = pt(*stats.coldspot)
    cv2.drawMarker(out, (hx, hy), (40, 40, 255), cv2.MARKER_TRIANGLE_UP, 16, 2)
    cv2.putText(out, f"{stats.t_max:.1f}C", (hx + 6, hy), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (40, 40, 255), 1, cv2.LINE_AA)
    cv2.drawMarker(out, (cx, cy), (255, 200, 0), cv2.MARKER_TRIANGLE_DOWN, 16, 2)

    if crosshair:
        cv2.drawMarker(out, (w // 2, h // 2), (255, 255, 255), cv2.MARKER_CROSS, 18, 1)

    if rois:
        for r in rois:
            x0, y0, x1, y1 = r.to_pixels(w // scale, h // scale)
            color = (0, 215, 255) if not r.locked else (0, 165, 255)
            cv2.rectangle(out, pt(x0, y0), pt(x1, y1), color, 2)
            cv2.putText(out, r.name, pt(x0, y0 - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1,
                        cv2.LINE_AA)
    return out


def fuse(thermal_bgr: np.ndarray, rgb_bgr: np.ndarray, params: FusionParams) -> np.ndarray:
    """Alpha-blend a thermal heatmap over an RGB frame with alignment/scale/rotation."""
    import cv2

    h, w = rgb_bgr.shape[:2]
    therm = cv2.resize(thermal_bgr, (int(w * params.scale), int(h * params.scale)))

    if params.rotation:
        m = cv2.getRotationMatrix2D((therm.shape[1] / 2, therm.shape[0] / 2), params.rotation, 1.0)
        therm = cv2.warpAffine(therm, m, (therm.shape[1], therm.shape[0]))

    canvas = np.zeros_like(rgb_bgr)
    y0 = max(0, params.dy)
    x0 = max(0, params.dx)
    ty = max(0, -params.dy)
    tx = max(0, -params.dx)
    hh = min(therm.shape[0] - ty, h - y0)
    ww = min(therm.shape[1] - tx, w - x0)
    if hh > 0 and ww > 0:
        canvas[y0:y0 + hh, x0:x0 + ww] = therm[ty:ty + hh, tx:tx + ww]

    return cv2.addWeighted(rgb_bgr, 1.0 - params.alpha, canvas, params.alpha, 0.0)


def encode_png_b64(img_bgr: np.ndarray) -> str:
    """Encode a BGR image as base64 PNG for transport over WebSocket/JSON."""
    import cv2

    ok, buf = cv2.imencode(".png", img_bgr)
    if not ok:
        raise RuntimeError("PNG encode failed")
    return base64.b64encode(buf.tobytes()).decode("ascii")

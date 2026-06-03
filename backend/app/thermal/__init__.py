"""Thermal processing engine for the GW192A platform.

Pure, framework-free functions operating on NumPy arrays so they can be unit-tested in
isolation and reused by the gateway. The reference math is validated end-to-end (without
NumPy) in ``validate/validate_core.py``.
"""
from .alerts import AlertEngine, AlertResult
from .decoder import GW192ADecoder, decode_celsius_f32, decode_radiometric_u16
from .palettes import PALETTES, apply_palette
from .roi import ROI, analyze_roi
from .statistics import FrameStatistics, compute_statistics

__all__ = [
    "GW192ADecoder",
    "decode_radiometric_u16",
    "decode_celsius_f32",
    "PALETTES",
    "apply_palette",
    "FrameStatistics",
    "compute_statistics",
    "ROI",
    "analyze_roi",
    "AlertEngine",
    "AlertResult",
]

"""GW192A radiometric frame decoder.

The GW192A (InfiRay/Xtherm-class UVC camera) streams a *double-height* YUYV frame:
the top half is a colorized preview, the bottom half is 16-bit little-endian radiometric
data. Conversion to Celsius follows the InfiRay convention, with a configurable linear trim:

    T(C) = (raw16 / kelvin_scale - kelvin_offset) * gain + offset

See ``docs/01-gw192a-research.md`` for the protocol analysis.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class GW192ADecoder:
    """Stateless decoder configured with the device's calibration constants."""

    width: int = 192
    height: int = 192
    kelvin_scale: float = 64.0
    kelvin_offset: float = 273.15
    gain: float = 1.0
    offset: float = 0.0

    # --- raw count <-> celsius ------------------------------------------------------
    def raw_to_celsius(self, raw: np.ndarray) -> np.ndarray:
        c = raw.astype(np.float32) / self.kelvin_scale - self.kelvin_offset
        return c * self.gain + self.offset

    def celsius_to_raw(self, celsius: np.ndarray) -> np.ndarray:
        base = (celsius - self.offset) / self.gain
        return np.clip((base + self.kelvin_offset) * self.kelvin_scale, 0, 65535).astype(np.uint16)

    # --- frame decoding -------------------------------------------------------------
    def split_double_height(self, frame: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Split a (2H, W) frame into (image_half, thermal_half)."""
        if frame.shape[0] != 2 * self.height:
            raise ValueError(
                f"expected double-height frame {2 * self.height} rows, got {frame.shape[0]}"
            )
        return frame[: self.height], frame[self.height :]

    def decode_from_u16_buffer(self, buf: bytes) -> np.ndarray:
        """Decode a raw radiometric *half* (W*H uint16 LE) buffer to a Celsius matrix."""
        expected = self.width * self.height
        arr = np.frombuffer(buf, dtype="<u2")
        if arr.size < expected:
            raise ValueError(f"radiometric buffer too small: {arr.size} < {expected}")
        raw = arr[:expected].reshape(self.height, self.width)
        return self.raw_to_celsius(raw)

    def decode_from_double_height_u16(self, buf: bytes) -> np.ndarray:
        """Decode a full double-height uint16 frame buffer, returning the Celsius matrix."""
        full = np.frombuffer(buf, dtype="<u2").reshape(2 * self.height, self.width)
        _, thermal = self.split_double_height(full)
        return self.raw_to_celsius(thermal)


def decode_radiometric_u16(buf: bytes, width: int, height: int, **kw) -> np.ndarray:
    """Convenience: decode a W*H uint16 radiometric buffer to Celsius."""
    return GW192ADecoder(width=width, height=height, **kw).decode_from_u16_buffer(buf)


def decode_celsius_f32(buf: bytes, width: int, height: int) -> np.ndarray:
    """Decode a buffer that already holds float32 Celsius values (e.g. from the gateway)."""
    arr = np.frombuffer(buf, dtype="<f4")
    return arr[: width * height].reshape(height, width).astype(np.float32)

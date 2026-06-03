#!/usr/bin/env python3
"""
ThermoBaby — dependency-free validation of the core thermal pipeline.

This script reproduces, using ONLY the Python standard library, the exact math that the
production backend (`backend/app/thermal/*`) performs with NumPy/OpenCV. Its purpose is to
*prove the algorithms are correct* without needing to install anything.

Pipeline validated here:
  1. GW192A frame model: a double-height UVC YUYV frame where the bottom half carries
     16-bit little-endian radiometric data.  T(degC) = raw16 / 64 - 273.15
  2. Decoder: split the frame, extract the radiometric matrix, convert to Celsius.
  3. Statistics: min / max / mean / std / hotspot / coldspot / thermal centroid / histogram.
  4. ROI analysis over a rectangular region.
  5. Infant alert engine: body-temperature and ambient-temperature classification.

Run:  python3 validate/validate_core.py
Exit code is 0 only if every assertion passes.
"""
from __future__ import annotations

import math
import random
import struct
import sys
from dataclasses import dataclass, field, asdict

# --------------------------------------------------------------------------------------
# GW192A frame model  (kept identical to backend/app/thermal/decoder.py constants)
# --------------------------------------------------------------------------------------
# The GW192A reports a UVC YUYV stream whose height is 2x the sensor height. The top half is
# the visible/colorized image; the bottom half is raw 16-bit radiometric data. Native sensor
# geometry for the GW192A family is treated as W x H below (192x192 here; the 256x192 sibling
# works identically by changing W/H).
SENSOR_W = 192
SENSOR_H = 192

# InfiRay/Xtherm radiometric convention.
KELVIN_SCALE = 64.0          # raw counts per Kelvin
KELVIN_OFFSET = 273.15       # Kelvin -> Celsius


def celsius_to_raw16(temp_c: float) -> int:
    """Inverse of the device conversion, used to synthesize test frames."""
    raw = int(round((temp_c + KELVIN_OFFSET) * KELVIN_SCALE))
    return max(0, min(0xFFFF, raw))


def raw16_to_celsius(raw: int) -> float:
    return raw / KELVIN_SCALE - KELVIN_OFFSET


# --------------------------------------------------------------------------------------
# Synthesize a realistic GW192A radiometric half-frame (bytes, little-endian uint16)
# --------------------------------------------------------------------------------------
def synthesize_radiometric_bytes(
    w: int,
    h: int,
    ambient_c: float = 22.0,
    hotspot_c: float = 37.8,
    hotspot_xy: tuple[int, int] | None = None,
    noise: float = 0.05,
    seed: int = 7,
) -> bytes:
    """Create a Gaussian 'warm body' over a cool ambient background, as raw16 LE bytes."""
    rng = random.Random(seed)
    if hotspot_xy is None:
        hotspot_xy = (w // 2, h // 2)
    cx, cy = hotspot_xy
    sigma = w / 6.0
    out = bytearray(w * h * 2)
    for y in range(h):
        for x in range(w):
            d2 = (x - cx) ** 2 + (y - cy) ** 2
            gauss = math.exp(-d2 / (2 * sigma * sigma))
            temp = ambient_c + (hotspot_c - ambient_c) * gauss
            temp += rng.uniform(-noise, noise)
            raw = celsius_to_raw16(temp)
            struct.pack_into("<H", out, (y * w + x) * 2, raw)
    return bytes(out)


def build_double_height_frame(radiometric: bytes, w: int, h: int) -> bytes:
    """Top half = dummy visible image (zeros here), bottom half = radiometric bytes.
    Mirrors how the GW192A stacks image + thermal data in one UVC frame."""
    visible = bytes(w * h * 2)  # placeholder for the colorized half
    return visible + radiometric


# --------------------------------------------------------------------------------------
# Decoder (pure python equivalent of the NumPy version)
# --------------------------------------------------------------------------------------
def decode_radiometric(frame: bytes, w: int, h: int) -> list[list[float]]:
    """Extract the bottom half of a double-height frame and convert to a Celsius matrix."""
    half_bytes = w * h * 2
    if len(frame) < 2 * half_bytes:
        raise ValueError(
            f"frame too small: got {len(frame)} bytes, expected >= {2 * half_bytes}"
        )
    thermal = frame[half_bytes : 2 * half_bytes]
    matrix: list[list[float]] = []
    for y in range(h):
        row: list[float] = []
        base = y * w * 2
        for x in range(w):
            (raw,) = struct.unpack_from("<H", thermal, base + x * 2)
            row.append(raw16_to_celsius(raw))
        matrix.append(row)
    return matrix


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------
@dataclass
class ThermalStats:
    t_min: float
    t_max: float
    t_mean: float
    t_std: float
    hotspot: tuple[int, int]
    coldspot: tuple[int, int]
    centroid: tuple[float, float]
    histogram: list[int] = field(default_factory=list)


def compute_stats(matrix: list[list[float]], bins: int = 16) -> ThermalStats:
    h = len(matrix)
    w = len(matrix[0])
    n = w * h
    t_min = math.inf
    t_max = -math.inf
    s = 0.0
    s2 = 0.0
    hot_xy = (0, 0)
    cold_xy = (0, 0)
    # thermal centroid: weight pixels above mean by (T - mean)
    for y in range(h):
        for x in range(w):
            t = matrix[y][x]
            s += t
            s2 += t * t
            if t > t_max:
                t_max = t
                hot_xy = (x, y)
            if t < t_min:
                t_min = t
                cold_xy = (x, y)
    mean = s / n
    var = max(0.0, s2 / n - mean * mean)
    std = math.sqrt(var)

    # thermal centroid weighted by temperature above the mean
    wsum = 0.0
    cx = 0.0
    cy = 0.0
    for y in range(h):
        for x in range(w):
            wgt = max(0.0, matrix[y][x] - mean)
            wsum += wgt
            cx += wgt * x
            cy += wgt * y
    centroid = (cx / wsum, cy / wsum) if wsum > 0 else (w / 2.0, h / 2.0)

    # histogram
    hist = [0] * bins
    span = (t_max - t_min) or 1.0
    for y in range(h):
        for x in range(w):
            idx = int((matrix[y][x] - t_min) / span * (bins - 1))
            hist[idx] += 1

    return ThermalStats(
        t_min=round(t_min, 3),
        t_max=round(t_max, 3),
        t_mean=round(mean, 3),
        t_std=round(std, 3),
        hotspot=hot_xy,
        coldspot=cold_xy,
        centroid=(round(centroid[0], 2), round(centroid[1], 2)),
        histogram=hist,
    )


@dataclass
class ROIStats:
    name: str
    t_min: float
    t_max: float
    t_mean: float
    t_std: float


def analyze_roi(
    matrix: list[list[float]], x0: int, y0: int, x1: int, y1: int, name: str
) -> ROIStats:
    x0, x1 = sorted((max(0, x0), min(len(matrix[0]), x1)))
    y0, y1 = sorted((max(0, y0), min(len(matrix), y1)))
    vals = [matrix[y][x] for y in range(y0, y1) for x in range(x0, x1)]
    if not vals:
        raise ValueError("empty ROI")
    mean = sum(vals) / len(vals)
    var = sum((v - mean) ** 2 for v in vals) / len(vals)
    return ROIStats(
        name=name,
        t_min=round(min(vals), 3),
        t_max=round(max(vals), 3),
        t_mean=round(mean, 3),
        t_std=round(math.sqrt(var), 3),
    )


# --------------------------------------------------------------------------------------
# Infant alert engine (mirrors backend/app/thermal/alerts.py thresholds)
# --------------------------------------------------------------------------------------
BODY = {
    "normal_low": 36.5,
    "normal_high": 37.5,
    "crit_low": 36.0,
    "crit_high": 38.0,
}
AMBIENT = {"normal_low": 20.0, "normal_high": 24.0}


@dataclass
class Alert:
    level: str   # ok | warning | critical
    code: str
    message: str
    value: float


def evaluate_body_temp(peak_c: float) -> Alert:
    if peak_c >= BODY["crit_high"]:
        return Alert("critical", "BODY_CRIT_HIGH", "Temperatura critica (posible fiebre alta)", peak_c)
    if peak_c < BODY["crit_low"]:
        return Alert("critical", "BODY_CRIT_LOW", "Temperatura critica (hipotermia)", peak_c)
    if peak_c > BODY["normal_high"]:
        return Alert("warning", "BODY_WARN_HIGH", "Temperatura elevada (posible fiebre)", peak_c)
    if peak_c < BODY["normal_low"]:
        return Alert("warning", "BODY_WARN_LOW", "Hipotermia potencial", peak_c)
    return Alert("ok", "BODY_OK", "Temperatura corporal normal", peak_c)


def evaluate_ambient(ambient_c: float) -> Alert:
    if ambient_c < AMBIENT["normal_low"]:
        return Alert("warning", "AMB_COLD", "Ambiente muy frio", ambient_c)
    if ambient_c > AMBIENT["normal_high"]:
        return Alert("warning", "AMB_HOT", "Ambiente muy caliente", ambient_c)
    return Alert("ok", "AMB_OK", "Ambiente normal", ambient_c)


# --------------------------------------------------------------------------------------
# Validation harness
# --------------------------------------------------------------------------------------
def bar(value: int, peak: int, width: int = 40) -> str:
    n = int(value / peak * width) if peak else 0
    return "#" * n


def main() -> int:
    print("=" * 78)
    print(" ThermoBaby — core thermal pipeline validation (stdlib only)")
    print("=" * 78)

    failures = 0

    def check(label: str, condition: bool, detail: str = "") -> None:
        nonlocal failures
        status = "PASS" if condition else "FAIL"
        if not condition:
            failures += 1
        print(f"  [{status}] {label}{(' — ' + detail) if detail else ''}")

    # 1) round-trip conversion -----------------------------------------------------------
    print("\n[1] Radiometric conversion round-trip")
    for t in (35.9, 36.5, 37.0, 37.8, 38.2, 22.0):
        back = raw16_to_celsius(celsius_to_raw16(t))
        check(f"{t:>5.1f} C -> raw -> {back:6.3f} C", abs(back - t) < 0.02)

    # 2) synthesize + decode -------------------------------------------------------------
    print("\n[2] GW192A double-height frame decode")
    AMBIENT_C = 22.0
    HOTSPOT_C = 37.8
    HOT_XY = (118, 104)
    radio = synthesize_radiometric_bytes(
        SENSOR_W, SENSOR_H, ambient_c=AMBIENT_C, hotspot_c=HOTSPOT_C, hotspot_xy=HOT_XY
    )
    frame = build_double_height_frame(radio, SENSOR_W, SENSOR_H)
    expected_len = 2 * (SENSOR_W * SENSOR_H * 2)
    check(f"frame length = {len(frame)} bytes", len(frame) == expected_len,
          f"expected {expected_len}")
    matrix = decode_radiometric(frame, SENSOR_W, SENSOR_H)
    check("decoded matrix geometry", len(matrix) == SENSOR_H and len(matrix[0]) == SENSOR_W,
          f"{len(matrix[0])}x{len(matrix)}")

    # 3) statistics ----------------------------------------------------------------------
    print("\n[3] Statistics")
    stats = compute_stats(matrix)
    print(f"      min={stats.t_min} C  max={stats.t_max} C  mean={stats.t_mean} C  std={stats.t_std} C")
    print(f"      hotspot={stats.hotspot}  coldspot={stats.coldspot}  centroid={stats.centroid}")
    check("max temp near synthesized hotspot value",
          abs(stats.t_max - HOTSPOT_C) < 0.3, f"{stats.t_max} vs {HOTSPOT_C}")
    check("hotspot location within 3px of injected hotspot",
          abs(stats.hotspot[0] - HOT_XY[0]) <= 3 and abs(stats.hotspot[1] - HOT_XY[1]) <= 3,
          f"{stats.hotspot} vs {HOT_XY}")
    check("min temp near ambient",
          abs(stats.t_min - AMBIENT_C) < 0.5, f"{stats.t_min} vs {AMBIENT_C}")
    check("thermal centroid lands on the hotspot (weighted by T-mean)",
          abs(stats.centroid[0] - HOT_XY[0]) <= 5 and abs(stats.centroid[1] - HOT_XY[1]) <= 5,
          f"{stats.centroid} vs {HOT_XY}")

    print("\n      histogram (temperature distribution):")
    peak = max(stats.histogram)
    lo, hi = stats.t_min, stats.t_max
    for i, c in enumerate(stats.histogram):
        edge = lo + (hi - lo) * i / len(stats.histogram)
        print(f"        {edge:6.2f}C |{bar(c, peak)} {c}")

    # 4) ROI -----------------------------------------------------------------------------
    print("\n[4] ROI analysis (forehead-style region centered on hotspot)")
    roi = analyze_roi(matrix, HOT_XY[0] - 12, HOT_XY[1] - 12, HOT_XY[0] + 12, HOT_XY[1] + 12,
                      "frente")
    print(f"      ROI '{roi.name}': mean={roi.t_mean}C max={roi.t_max}C min={roi.t_min}C std={roi.t_std}C")
    check("ROI mean warmer than global mean", roi.t_mean > stats.t_mean,
          f"{roi.t_mean} > {stats.t_mean}")
    check("ROI max ~ hotspot", abs(roi.t_max - stats.t_max) < 0.1)

    # 5) alert engine --------------------------------------------------------------------
    print("\n[5] Infant alert engine")
    cases = [
        (35.8, "critical", "BODY_CRIT_LOW"),
        (36.2, "warning", "BODY_WARN_LOW"),
        (37.0, "ok", "BODY_OK"),
        (37.8, "warning", "BODY_WARN_HIGH"),
        (38.4, "critical", "BODY_CRIT_HIGH"),
    ]
    for temp, exp_level, exp_code in cases:
        a = evaluate_body_temp(temp)
        check(f"body {temp}C -> {a.level}/{a.code} ({a.message})",
              a.level == exp_level and a.code == exp_code, f"expected {exp_level}/{exp_code}")

    amb_cases = [(18.0, "warning", "AMB_COLD"), (22.0, "ok", "AMB_OK"), (26.0, "warning", "AMB_HOT")]
    for temp, exp_level, exp_code in amb_cases:
        a = evaluate_ambient(temp)
        check(f"ambient {temp}C -> {a.level}/{a.code} ({a.message})",
              a.level == exp_level and a.code == exp_code, f"expected {exp_level}/{exp_code}")

    # 6) end-to-end report ---------------------------------------------------------------
    print("\n[6] End-to-end frame report (what the server would emit per frame)")
    body_alert = evaluate_body_temp(stats.t_max)
    amb_alert = evaluate_ambient(stats.t_min)
    report = {
        "geometry": f"{SENSOR_W}x{SENSOR_H}",
        "stats": {k: v for k, v in asdict(stats).items() if k != "histogram"},
        "roi": asdict(roi),
        "body_alert": asdict(body_alert),
        "ambient_alert": asdict(amb_alert),
    }
    import json
    print(json.dumps(report, indent=2, ensure_ascii=False))

    print("\n" + "=" * 78)
    if failures:
        print(f" RESULT: {failures} check(s) FAILED")
        print("=" * 78)
        return 1
    print(" RESULT: all checks PASSED — core thermal pipeline is correct")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())

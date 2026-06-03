"""Unit tests for the thermal engine (requires numpy; opencv only for render tests).

Run: pytest -q   (from backend/)
The same logic is proven dependency-free in ../../validate/validate_core.py
"""
from __future__ import annotations

import numpy as np
import pytest

from app.thermal import (
    GW192ADecoder,
    analyze_roi,
    compute_statistics,
)
from app.thermal.alerts import AlertEngine, evaluate_ambient, evaluate_body
from app.thermal.roi import ROI

W = H = 192


def _synth_celsius(ambient=22.0, hot=37.8, hot_xy=(118, 104)) -> np.ndarray:
    ys, xs = np.indices((H, W))
    sigma = W / 6.0
    d2 = (xs - hot_xy[0]) ** 2 + (ys - hot_xy[1]) ** 2
    return (ambient + (hot - ambient) * np.exp(-d2 / (2 * sigma**2))).astype(np.float32)


def test_raw_celsius_roundtrip():
    dec = GW192ADecoder(width=W, height=H)
    for t in (35.9, 36.5, 37.0, 37.8, 38.2):
        raw = dec.celsius_to_raw(np.array([t], dtype=np.float32))
        back = dec.raw_to_celsius(raw)[0]
        assert abs(back - t) < 0.02


def test_double_height_decode():
    dec = GW192ADecoder(width=W, height=H)
    celsius = _synth_celsius()
    raw = dec.celsius_to_raw(celsius)
    visible = np.zeros_like(raw)
    frame = np.vstack([visible, raw])  # double-height
    decoded = dec.decode_from_double_height_u16(frame.tobytes())
    assert decoded.shape == (H, W)
    assert abs(float(decoded.max()) - 37.8) < 0.3


def test_statistics_hotspot():
    celsius = _synth_celsius(hot_xy=(118, 104))
    stats = compute_statistics(celsius)
    assert abs(stats.t_max - 37.8) < 0.3
    assert abs(stats.hotspot[0] - 118) <= 3 and abs(stats.hotspot[1] - 104) <= 3
    assert abs(stats.centroid[0] - 118) <= 6 and abs(stats.centroid[1] - 104) <= 6


def test_roi_warmer_than_global():
    celsius = _synth_celsius(hot_xy=(118, 104))
    stats = compute_statistics(celsius)
    roi = ROI(id="r1", name="frente", x0=106 / W, y0=92 / H, x1=130 / W, y1=116 / H)
    res = analyze_roi(celsius, roi)
    assert res.t_mean > stats.t_mean


@pytest.mark.parametrize("temp,level,code", [
    (35.8, "critical", "BODY_CRIT_LOW"),
    (36.2, "warning", "BODY_WARN_LOW"),
    (37.0, "ok", "BODY_OK"),
    (37.8, "warning", "BODY_WARN_HIGH"),
    (38.4, "critical", "BODY_CRIT_HIGH"),
])
def test_body_alerts(temp, level, code):
    a = evaluate_body(temp)
    assert a.level == level and a.code == code


@pytest.mark.parametrize("temp,level,code", [
    (18.0, "warning", "AMB_COLD"),
    (22.0, "ok", "AMB_OK"),
    (26.0, "warning", "AMB_HOT"),
])
def test_ambient_alerts(temp, level, code):
    a = evaluate_ambient(temp)
    assert a.level == level and a.code == code


def test_alert_engine_debounce():
    eng = AlertEngine(debounce_seconds=1000)
    first = eng.evaluate(body_peak_c=38.5, ambient_c=22.0)
    assert any(a.code == "BODY_CRIT_HIGH" for a in first)
    # same level within debounce window -> suppressed
    second = eng.evaluate(body_peak_c=38.6, ambient_c=22.0)
    assert second == []

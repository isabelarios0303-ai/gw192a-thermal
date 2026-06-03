#!/usr/bin/env python3
"""
ThermoBaby desktop capture gateway (Method 4) — Windows / Linux / macOS.

Opens the GW192A as a UVC camera, requests the RAW double-height YUYV stream (so the
radiometric half is preserved), splits image/thermal halves, converts the bottom half to
Celsius, and streams frames to the backend at  ws://<server>/ws/ingest/<session>.

Why a gateway? The GW192A is a standard UVC device, but desktop browsers/WebUSB cannot reliably
claim it while the OS camera stack holds it, and the OS will color-convert the radiometric half
unless we explicitly request raw YUYV (V4L2: CAP_PROP_CONVERT_RGB=0). This native helper does
that correctly and pushes normalized frames to the server. See docs/01-gw192a-research.md.

Usage:
  python gw192a_gateway.py --server ws://localhost:8000 --session demo --device 0
  python gw192a_gateway.py --list                 # enumerate candidate devices
  python gw192a_gateway.py --simulate             # no camera: emit a synthetic warm body
"""
from __future__ import annotations

import argparse
import asyncio
import struct
import sys
import time

import numpy as np

# OpenCV and websockets are runtime deps (see requirements.txt). Imported lazily so --help works.
try:
    import cv2
except Exception:  # noqa: BLE001
    cv2 = None

# ---- frame contract (must match backend/app/api/ws.py) -------------------------------
_HEADER = struct.Struct("<4sBBHHIQ")  # magic, ver, kind, w, h, seq, ts_ms
MAGIC = b"GW19"
VERSION = 1
KIND_RADIOMETRIC_U16 = 1
KIND_CELSIUS_F32 = 2

# ---- GW192A radiometric constants (keep in sync with backend config) -----------------
KELVIN_SCALE = 64.0
KELVIN_OFFSET = 273.15


def raw_to_celsius(raw: np.ndarray, gain: float = 1.0, offset: float = 0.0) -> np.ndarray:
    return (raw.astype(np.float32) / KELVIN_SCALE - KELVIN_OFFSET) * gain + offset


def celsius_to_raw(celsius: np.ndarray) -> np.ndarray:
    return np.clip((celsius + KELVIN_OFFSET) * KELVIN_SCALE, 0, 65535).astype(np.uint16)


def pack_celsius_frame(celsius: np.ndarray, seq: int) -> bytes:
    h, w = celsius.shape
    header = _HEADER.pack(MAGIC, VERSION, KIND_CELSIUS_F32, w, h, seq & 0xFFFFFFFF,
                          int(time.time() * 1000))
    return header + celsius.astype("<f4").tobytes()


def pack_radiometric_frame(raw_u16: np.ndarray, seq: int) -> bytes:
    h, w = raw_u16.shape
    header = _HEADER.pack(MAGIC, VERSION, KIND_RADIOMETRIC_U16, w, h, seq & 0xFFFFFFFF,
                          int(time.time() * 1000))
    return header + raw_u16.astype("<u2").tobytes()


# --------------------------------------------------------------------------------------
# Camera handling
# --------------------------------------------------------------------------------------
class GW192ACapture:
    """Wraps a UVC capture and yields radiometric Celsius matrices."""

    def __init__(self, device: int, width: int, height: int):
        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera capture (pip install opencv-python)")
        self.device = device
        self.sensor_w = width
        self.sensor_h = height
        self.cap = cv2.VideoCapture(device)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open capture device {device}")

        # CRITICAL: request raw YUYV at DOUBLE height, and disable RGB conversion so the
        # radiometric half survives. Some backends ignore some of these — we verify below.
        self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height * 2)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[gateway] capture opened: requested {width}x{height*2}, "
              f"actual {actual_w}x{actual_h}")
        if actual_h < height * 2:
            print("[gateway] WARNING: device did not provide the double-height frame. "
                  "The radiometric half may be unavailable; check drivers / try --device N.")

    def read_celsius(self) -> np.ndarray | None:
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        return self._frame_to_celsius(frame)

    def _frame_to_celsius(self, frame: np.ndarray) -> np.ndarray:
        """Interpret a raw YUYV buffer: bottom half holds 16-bit radiometric data.

        With CONVERT_RGB=0, OpenCV returns the YUYV bytes. We reinterpret them as uint16 to
        recover the per-pixel radiometric counts. Layout details vary slightly by firmware; the
        gateway exposes --byteswap / --half flags to adapt a specific unit.
        """
        # Flatten to bytes then view as little-endian uint16.
        raw_bytes = np.ascontiguousarray(frame).tobytes()
        u16 = np.frombuffer(raw_bytes, dtype="<u2")
        total = self.sensor_w * self.sensor_h
        if u16.size >= 2 * total:
            thermal_u16 = u16[total: 2 * total].reshape(self.sensor_h, self.sensor_w)
        elif u16.size >= total:
            thermal_u16 = u16[:total].reshape(self.sensor_h, self.sensor_w)
        else:
            raise RuntimeError(f"frame too small: {u16.size} u16 values")
        return raw_to_celsius(thermal_u16)

    def release(self) -> None:
        if self.cap:
            self.cap.release()


def synth_celsius(w: int, h: int, t: float) -> np.ndarray:
    """Synthetic moving warm body for --simulate (no hardware needed)."""
    ys, xs = np.indices((h, w))
    cx = w / 2 + np.sin(t) * w / 6
    cy = h / 2 + np.cos(t * 0.7) * h / 6
    sigma = w / 6.0
    d2 = (xs - cx) ** 2 + (ys - cy) ** 2
    body = 22.0 + (37.6 - 22.0) * np.exp(-d2 / (2 * sigma**2))
    return (body + np.random.uniform(-0.05, 0.05, body.shape)).astype(np.float32)


# --------------------------------------------------------------------------------------
# Streaming loop
# --------------------------------------------------------------------------------------
async def stream(args: argparse.Namespace) -> None:
    import websockets  # local dep

    url = f"{args.server.rstrip('/')}/ws/ingest/{args.session}"
    cap: GW192ACapture | None = None
    if not args.simulate:
        cap = GW192ACapture(args.device, args.width, args.height)

    backoff = 1.0
    seq = 0
    while True:
        try:
            async with websockets.connect(url, max_size=None) as ws:
                print(f"[gateway] connected to {url}")
                backoff = 1.0
                # send initial control: palette + ROIs
                await ws.send('{"palette": "medical"}')
                period = 1.0 / max(1, args.fps)
                t0 = time.time()
                while True:
                    if args.simulate:
                        celsius = synth_celsius(args.width, args.height, time.time() - t0)
                    else:
                        celsius = cap.read_celsius()
                        if celsius is None:
                            await asyncio.sleep(period)
                            continue
                    if args.send_raw:
                        await ws.send(pack_radiometric_frame(celsius_to_raw(celsius), seq))
                    else:
                        await ws.send(pack_celsius_frame(celsius, seq))
                    seq += 1
                    if seq % args.fps == 0:
                        print(f"[gateway] sent {seq} frames "
                              f"(last max={float(celsius.max()):.1f}C)")
                    await asyncio.sleep(period)
        except Exception as exc:  # noqa: BLE001
            print(f"[gateway] connection lost: {exc!r}; retrying in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(30.0, backoff * 2)
        finally:
            if cap and False:  # keep camera open across reconnects
                cap.release()


def list_devices(max_index: int = 8) -> None:
    if cv2 is None:
        print("OpenCV not installed; cannot enumerate devices.")
        return
    print("Probing video devices (a thermal cam often reports a doubled height, e.g. 192x384):")
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"  device {i}: {w}x{h}")
            cap.release()


def main() -> int:
    p = argparse.ArgumentParser(description="GW192A desktop capture gateway")
    p.add_argument("--server", default="ws://localhost:8000", help="backend ws base URL")
    p.add_argument("--session", default="demo", help="session id to ingest into")
    p.add_argument("--device", type=int, default=0, help="UVC device index")
    p.add_argument("--width", type=int, default=192, help="sensor width")
    p.add_argument("--height", type=int, default=192, help="sensor height (single half)")
    p.add_argument("--fps", type=int, default=12, help="frames/sec to send (<=25)")
    p.add_argument("--send-raw", action="store_true",
                   help="send radiometric uint16 instead of Celsius float32")
    p.add_argument("--simulate", action="store_true", help="emit a synthetic body (no hardware)")
    p.add_argument("--list", action="store_true", help="enumerate video devices and exit")
    args = p.parse_args()

    if args.list:
        list_devices()
        return 0
    try:
        asyncio.run(stream(args))
    except KeyboardInterrupt:
        print("\n[gateway] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

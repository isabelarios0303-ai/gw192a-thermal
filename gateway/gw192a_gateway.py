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

Windows note: OpenCV defaults to the MSMF backend, which frequently fails to grab frames from
cheap UVC thermal cameras ("can't grab frame. Error: -2147483638"). Use --backend dshow
(DirectShow) on Windows, which is the default of this tool on win32.

Usage:
  python gw192a_gateway.py --server ws://localhost:8000 --session demo --device 1
  python gw192a_gateway.py --list                       # enumerate candidate devices
  python gw192a_gateway.py --probe --device 1           # diagnose what a device delivers
  python gw192a_gateway.py --simulate                   # no camera: synthetic warm body
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


def resolve_backend(name: str) -> int:
    """Map a backend name to an OpenCV VideoCapture API preference constant."""
    if cv2 is None:
        return 0
    if name == "auto":
        if sys.platform.startswith("win"):
            return cv2.CAP_DSHOW          # MSMF is unreliable for UVC thermal cams on Windows
        if sys.platform == "darwin":
            return cv2.CAP_AVFOUNDATION
        return cv2.CAP_V4L2
    return {
        "dshow": cv2.CAP_DSHOW,
        "msmf": cv2.CAP_MSMF,
        "any": cv2.CAP_ANY,
        "v4l2": cv2.CAP_V4L2,
        "avfoundation": cv2.CAP_AVFOUNDATION,
    }.get(name, cv2.CAP_ANY)


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

    def __init__(self, device: int, width: int, height: int, backend: str = "auto",
                 raw_yuyv: bool = True):
        if cv2 is None:
            raise RuntimeError("OpenCV is required for camera capture (pip install opencv-python)")
        self.device = device
        self.sensor_w = width
        self.sensor_h = height
        api = resolve_backend(backend)
        self.cap = cv2.VideoCapture(device, api)
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Could not open device {device} with backend '{backend}'. "
                f"Try --backend dshow (Windows), msmf, any, or v4l2 (Linux)."
            )

        # Try to request raw YUYV at DOUBLE height and disable RGB conversion so the radiometric
        # half survives. Some backends silently ignore these; we report what we actually got.
        if raw_yuyv:
            self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
            self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height * 2)

        actual_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[gateway] capture opened (backend={backend}): "
              f"requested {width}x{height * 2}, actual {actual_w}x{actual_h}")
        if actual_h < height * 2:
            print("[gateway] WARNING: device did not provide the double-height frame. "
                  "Run with --probe to inspect the real frame, or try --backend dshow/msmf.")

    def read_celsius(self) -> np.ndarray | None:
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        return self._frame_to_celsius(frame)

    def _frame_to_celsius(self, frame: np.ndarray) -> np.ndarray:
        """Interpret the raw buffer: the bottom half holds 16-bit radiometric data.

        With CONVERT_RGB=0 the buffer is raw YUYV; we reinterpret the bytes as little-endian
        uint16 and take the bottom half (radiometric). Layout varies slightly by firmware.
        """
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
        cap = GW192ACapture(args.device, args.width, args.height, backend=args.backend)

    backoff = 1.0
    seq = 0
    fail_streak = 0
    while True:
        try:
            async with websockets.connect(url, max_size=None) as ws:
                print(f"[gateway] connected to {url}")
                backoff = 1.0
                await ws.send('{"palette": "medical"}')  # initial control
                period = 1.0 / max(1, args.fps)
                t0 = time.time()
                while True:
                    if args.simulate:
                        celsius = synth_celsius(args.width, args.height, time.time() - t0)
                    else:
                        celsius = cap.read_celsius()
                        if celsius is None:
                            fail_streak += 1
                            if fail_streak in (15, 75):
                                print("[gateway] no se pueden leer frames de la cámara. "
                                      "Prueba otro backend: --backend msmf  (o dshow/any), "
                                      "y revisa --probe. ¿Está la app THG Start cerrada?")
                            await asyncio.sleep(period)
                            continue
                        fail_streak = 0
                    if args.send_raw:
                        await ws.send(pack_radiometric_frame(celsius_to_raw(celsius), seq))
                    else:
                        await ws.send(pack_celsius_frame(celsius, seq))
                    seq += 1
                    if seq % max(1, args.fps) == 0:
                        print(f"[gateway] sent {seq} frames "
                              f"(last max={float(celsius.max()):.1f}C)")
                    await asyncio.sleep(period)
        except Exception as exc:  # noqa: BLE001
            print(f"[gateway] connection lost: {exc!r}; retrying in {backoff:.0f}s")
            await asyncio.sleep(backoff)
            backoff = min(30.0, backoff * 2)


def list_devices(max_index: int = 8, backend: str = "auto") -> None:
    if cv2 is None:
        print("OpenCV not installed; cannot enumerate devices.")
        return
    api = resolve_backend(backend)
    print(f"Probing video devices with backend '{backend}' "
          f"(a thermal cam often reports a doubled height, e.g. 192x384):")
    for i in range(max_index):
        cap = cv2.VideoCapture(i, api)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"  device {i}: {w}x{h}")
            cap.release()


def probe_device(device: int, backend: str = "auto", attempts: int = 30) -> None:
    """Open a device and report what frames it actually delivers (for diagnosis)."""
    if cv2 is None:
        print("OpenCV not installed; cannot probe.")
        return
    api = resolve_backend(backend)
    print(f"[probe] opening device {device} with backend '{backend}'...")
    cap = cv2.VideoCapture(device, api)
    if not cap.isOpened():
        print(f"[probe] FAILED to open device {device} with backend '{backend}'. "
              f"Try --backend msmf / dshow / any.")
        return
    cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0)
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    cc = "".join([chr((fourcc >> (8 * k)) & 0xFF) for k in range(4)])
    print(f"[probe] reported size {w}x{h}, fourcc='{cc}'")
    got = False
    for k in range(attempts):
        ok, frame = cap.read()
        if ok and frame is not None:
            got = True
            arr = np.asarray(frame)
            print(f"[probe] frame OK on attempt {k + 1}: shape={arr.shape}, dtype={arr.dtype}, "
                  f"bytes={arr.nbytes}, min={arr.min()}, max={arr.max()}")
            u16 = np.frombuffer(np.ascontiguousarray(arr).tobytes(), dtype='<u2')
            print(f"[probe] as uint16: count={u16.size}  "
                  f"(192x192 half needs 36864; 256x192 half needs 49152)")
            break
        time.sleep(0.1)
    if not got:
        print(f"[probe] could NOT grab any frame in {attempts} attempts with backend "
              f"'{backend}'. Try a different --backend, close other camera apps (THG Start), "
              f"or replug the camera.")
    cap.release()


def main() -> int:
    p = argparse.ArgumentParser(description="GW192A desktop capture gateway")
    p.add_argument("--server", default="ws://localhost:8000", help="backend ws base URL")
    p.add_argument("--session", default="demo", help="session id to ingest into")
    p.add_argument("--device", type=int, default=0, help="UVC device index")
    p.add_argument("--width", type=int, default=192, help="sensor width (single half)")
    p.add_argument("--height", type=int, default=192, help="sensor height (single half)")
    p.add_argument("--fps", type=int, default=12, help="frames/sec to send (<=25)")
    p.add_argument("--backend", default="auto",
                   choices=["auto", "dshow", "msmf", "any", "v4l2", "avfoundation"],
                   help="OpenCV capture backend (auto picks dshow on Windows)")
    p.add_argument("--send-raw", action="store_true",
                   help="send radiometric uint16 instead of Celsius float32")
    p.add_argument("--simulate", action="store_true", help="emit a synthetic body (no hardware)")
    p.add_argument("--list", action="store_true", help="enumerate video devices and exit")
    p.add_argument("--probe", action="store_true",
                   help="open --device and report the real frame format, then exit")
    args = p.parse_args()

    if args.list:
        list_devices(backend=args.backend)
        return 0
    if args.probe:
        probe_device(args.device, backend=args.backend)
        return 0
    try:
        asyncio.run(stream(args))
    except KeyboardInterrupt:
        print("\n[gateway] stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

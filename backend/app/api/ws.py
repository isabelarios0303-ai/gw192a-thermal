"""WebSocket endpoints.

  /ws/ingest/{session_id}      capture clients push raw thermal frames here
  /ws/stream/{session_id}      viewers subscribe to processed frames here

Binary ingest frame layout (little-endian):
  magic[4]="GW19" | version u8 | kind u8 | width u16 | height u16 | seq u32 | ts_ms u64 | payload
  kind: 1=radiometric_u16, 2=celsius_f32, 3=rgb_jpeg(reserved for RGB preview channel)
"""
from __future__ import annotations

import asyncio
import json
import struct
import time
from collections import defaultdict

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.thermal import GW192ADecoder, compute_statistics
from app.thermal.alerts import AlertEngine
from app.thermal.decoder import decode_celsius_f32
from app.thermal.render import colorize, draw_markers, encode_png_b64
from app.thermal.roi import ROI, analyze_rois

router = APIRouter(tags=["websocket"])

_HEADER = struct.Struct("<4sBBHHIQ")  # magic, ver, kind, w, h, seq, ts_ms
KIND_RADIOMETRIC_U16 = 1
KIND_CELSIUS_F32 = 2
KIND_RGB_JPEG = 3


class StreamHub:
    """Fan-out of processed frames to all viewers of a session."""

    def __init__(self) -> None:
        self._viewers: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._viewers[session_id].add(ws)

    async def unsubscribe(self, session_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._viewers[session_id].discard(ws)

    async def broadcast(self, session_id: str, message: str) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._viewers.get(session_id, ())):
            try:
                await ws.send_text(message)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.unsubscribe(session_id, ws)


hub = StreamHub()


def _parse_frame(data: bytes) -> dict | None:
    if len(data) < _HEADER.size:
        return None
    magic, ver, kind, w, h, seq, ts_ms = _HEADER.unpack_from(data, 0)
    if magic != b"GW19":
        return None
    return {"ver": ver, "kind": kind, "w": w, "h": h, "seq": seq, "ts_ms": ts_ms,
            "payload": data[_HEADER.size:]}


def _decode_to_celsius(frame: dict, decoder: GW192ADecoder) -> np.ndarray:
    if frame["kind"] == KIND_RADIOMETRIC_U16:
        return decoder.decode_from_u16_buffer(frame["payload"])
    if frame["kind"] == KIND_CELSIUS_F32:
        return decode_celsius_f32(frame["payload"], frame["w"], frame["h"])
    raise ValueError(f"unsupported kind {frame['kind']} for thermal processing")


@router.websocket("/ws/ingest/{session_id}")
async def ws_ingest(ws: WebSocket, session_id: str) -> None:
    """Capture clients (gateway / bridge / WebUSB) stream frames in; we process + fan out."""
    await ws.accept()
    decoder = GW192ADecoder(
        width=settings.sensor_width,
        height=settings.sensor_height,
        kelvin_scale=settings.kelvin_scale,
        kelvin_offset=settings.kelvin_offset,
        gain=settings.calib_gain,
        offset=settings.calib_offset,
    )
    alert_engine = AlertEngine()
    palette = "medical"
    rois: list[ROI] = []

    try:
        while True:
            msg = await ws.receive()
            if msg.get("type") == "websocket.disconnect":
                break

            # control messages (palette change, ROI updates) arrive as text JSON
            if msg.get("text") is not None:
                _apply_control(json.loads(msg["text"]), state := {"palette": palette, "rois": rois})
                palette, rois = state["palette"], state["rois"]
                continue

            data = msg.get("bytes")
            if not data:
                continue
            frame = _parse_frame(data)
            if frame is None:
                continue

            try:
                celsius = _decode_to_celsius(frame, decoder)
            except ValueError:
                continue

            processed = _process(celsius, frame, palette, rois, alert_engine, session_id)
            await hub.broadcast(session_id, processed)
    except WebSocketDisconnect:
        pass


def _apply_control(ctrl: dict, state: dict) -> None:
    if "palette" in ctrl:
        state["palette"] = ctrl["palette"]
    if "rois" in ctrl:
        state["rois"] = [ROI(**r) for r in ctrl["rois"]]


def _process(
    celsius: np.ndarray,
    frame: dict,
    palette: str,
    rois: list[ROI],
    alert_engine: AlertEngine,
    session_id: str,
) -> str:
    stats = compute_statistics(celsius)
    roi_results = analyze_rois(celsius, rois) if rois else []

    # body peak: prefer warmest ROI mean if ROIs exist (e.g. forehead), else global max
    body_peak = max((r.t_mean for r in roi_results), default=stats.t_max)
    ambient = stats.t_min  # coolest region approximates ambient/background
    alerts = alert_engine.evaluate(body_peak_c=body_peak, ambient_c=ambient)

    img = colorize(celsius, palette=palette, upscale=3)
    img = draw_markers(img, stats, rois=rois, scale=3)
    png_b64 = encode_png_b64(img)

    payload = {
        "seq": frame["seq"],
        "ts": frame["ts_ms"] or int(time.time() * 1000),
        "geometry": f"{frame['w']}x{frame['h']}",
        "palette": palette,
        "stats": stats.to_dict(),
        "rois": [r.to_dict() for r in roi_results],
        "alerts": [a.to_dict() for a in alerts],
        "image_png_b64": png_b64,
    }
    # NOTE: a background task should persist a downsampled Reading + any AlertEvent rows here.
    return json.dumps(payload)


@router.websocket("/ws/stream/{session_id}")
async def ws_stream(ws: WebSocket, session_id: str) -> None:
    """Viewers subscribe to receive processed frames for a session."""
    await ws.accept()
    await hub.subscribe(session_id, ws)
    try:
        while True:
            # viewers may send control messages (e.g. ping); we just keep the socket alive
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.unsubscribe(session_id, ws)

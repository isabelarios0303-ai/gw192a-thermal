# 03 — Platform-Specific Capture Strategies

The GW192A is UVC, but *reaching* it differs per platform (see the reachability matrix in
`01-gw192a-research.md`). The RGB camera is always available via `getUserMedia`. Below is the
recommended capture path for each target, in priority order.

---

## Android (Chrome / Edge / installed PWA)

**RGB camera:** `getUserMedia({ video: { facingMode: 'environment' | 'user' } })` — works in
Chrome/Edge and in the installed PWA. Requires HTTPS.

**GW192A thermal — recommended: native bridge app (Method 3).**
A minimal Android app claims the camera over USB-OTG and relays frames to the PWA/server:

1. Request USB permission (`UsbManager`, intent filter on attach).
2. Open the UVC stream with **`libuvc`** or **`saki4510t/UVCCamera`**, requesting the raw
   **YUYV double-height** format (do not let it convert to RGB).
3. Split image/thermal halves, convert the radiometric half to Celsius
   (`T = raw/64 − 273.15`).
4. Stream frames to `wss://<server>/ws/ingest/<session>` using the binary contract, **or**
   to the local PWA over `ws://localhost` (foreground service).

```
[GW192A]──OTG──>[Bridge app: UVCCamera/libuvc]──WebSocket──>[Server]──>[PWA viewer]
```

**Why not WebUSB on Android?** Chrome supports WebUSB, but the kernel `uvcvideo` driver usually
claims the camera interface first, so `claimInterface` fails. Our `lib/webusb.ts` tries and
falls back gracefully with a clear message. Android 12+ exposes some external-camera support via
`camera2`, but Chrome does not surface UVC cameras to `getUserMedia`, so the bridge app remains
the dependable route.

**Packaging:** ship the bridge as a tiny companion APK (or a Capacitor/Trusted-Web-Activity
plugin) and deep-link it from the PWA. The PWA handles all UI; the APK only does USB→WebSocket.

---

## iPhone / iPad (Safari / installed PWA)

**RGB camera:** `getUserMedia` works in Safari and the installed PWA (HTTPS + user gesture;
on iOS PWAs each camera start should follow a tap).

**GW192A thermal — reality check:**
- **No WebUSB** in Safari (or any iOS browser — they all use WebKit).
- iOS does not expose external/UVC cameras to `getUserMedia`.
- iPadOS 17+/iPhone 15 (USB-C) can expose a UVC **image** stream to **native** AVFoundation
  (`AVCaptureDevice` external type), but **not radiometric data**, and not to Safari.

**Recommended paths (in order):**
1. **Remote viewer (Method via server fan-out).** The iPhone subscribes to
   `wss://<server>/ws/stream/<session>` and displays thermal produced by another device
   (desktop gateway or an Android bridge). This is the most realistic "thermal on iPhone" story
   and needs zero special hardware access. Fully supported by this codebase today.
2. **Native companion app (Swift)** where business needs justify it: a bundled UVC reader
   (e.g. via `libuvc` compiled for iOS, on USB-C iPads/iPhone 15) streams frames to the server.
   Radiometric availability depends on the device/firmware and is **not guaranteed** by Apple's
   public APIs — validate per device.
3. **Built-in RGB only** as a degraded mode (no temperature).

> Bottom line: treat iOS as a **first-class viewer + RGB client**, and only attempt native
> thermal capture where a specific USB-C iPad/iPhone is confirmed to work.

---

## Desktop (Windows / macOS / Linux — Chrome / Edge)

**RGB camera:** `getUserMedia` works in Chrome/Edge.

**GW192A thermal — recommended: desktop gateway (Method 4).** Most reliable path overall.
Run `gateway/gw192a_gateway.py`:
- **Windows:** OpenCV uses Media Foundation/DirectShow; the camera appears as a webcam with a
  doubled height. Request YUYV; if RGB conversion can't be disabled, capture raw and reinterpret.
- **Linux:** V4L2. Critically set `CAP_PROP_CONVERT_RGB=0` so the radiometric half survives;
  the device shows up as `/dev/videoN` (often a doubled height like 192×384).
- **macOS:** AVFoundation backend; same YUYV-raw approach. If AVFoundation refuses the raw
  format, use a `libuvc` build.

```
[GW192A]──USB-C──>[gateway.py (OpenCV/libuvc)]──WebSocket──>[Server]──>[Browser PWA]
```

**WebUSB on desktop** can work in Chrome/Edge when the OS camera stack isn't holding the device,
but it requires reimplementing UVC streaming in JS; we keep it experimental and prefer the
gateway.

---

## Method summary (maps to the brief's four methods)

| Method | What | Best for | Reliability |
|---|---|---|---|
| **1 — WebUSB** | browser claims USB directly | desktop Chrome/Edge, some Android | ⚠️ low (OS claims UVC; unsupported on iOS) |
| **2 — WebRTC gateway** | local service captures + relays via WebRTC | LAN setups, low-latency multi-viewer | ✅ medium |
| **3 — Bridge app** | native Android/iOS app does USB→WebSocket | **Android (primary)**, iOS (where allowed) | ✅ high (Android) |
| **4 — Desktop gateway** | `gateway.py` captures UVC → WebSocket | **Windows/macOS/Linux (primary)** | ✅ high |

All four converge on the same server ingest contract, so the thermal engine and all viewers are
identical regardless of how the frame was captured.

---

## RGB / Thermal / Fusion across platforms

- **RGB** mode: `getUserMedia` → `<video>` → canvas. Available everywhere.
- **Thermal** mode: subscribe to processed frames; the server returns a colorized PNG + stats.
- **Fusion** mode: draw RGB on the canvas, then alpha-blend the thermal PNG with client-side
  **transparency / alignment (dx,dy) / scale / rotation** (`FusionControls`). Because alignment
  is interactive and device-dependent (the two lenses are offset), it's done on the client for
  zero latency while the server supplies the authoritative thermal layer + measurements.

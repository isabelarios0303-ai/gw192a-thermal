# 01 — GW192A Research & Protocol Analysis

> **Requisito crítico.** Before designing the architecture we determined how the GW192A actually
> exposes data, what protocols/formats it uses, and what each target platform can realistically
> reach. This document records those findings and the evidence behind them.

## 1. What the GW192A is

The **GOYOJO GW192A** is a compact **USB-C plug-and-play thermal imaging camera** marketed for
Android and iPhone (USB-C models). The vendor app is **THG Start** (also branded *Thermal
Master* on iOS). Advertised specs:

| Property | Value |
|---|---|
| Native IR resolution | **192×192** (some listings show 256×192; "SuperIR 512×384" is software upscaling) |
| Frame rate | **25 Hz** |
| Pixel pitch | 12 µm |
| Temperature range | approx. −20 °C … +550 °C (consumer listings: −4 °F … 752 °F) |
| Interface | **USB-C**, plug-and-play, no battery, no pairing |
| Companion app | **THG Start** (Android), **Thermal Master** (iOS) |

It belongs to the **InfiRay / Xtherm "Tiny" module family** — the same silicon and data format
used by the **Topdon TC001**, **Thermal Master P2/P3**, **InfiRay T2L/P2 Pro**, and many AliExpress
"256×192 USB-C" cameras. That family is **extensively reverse-engineered and open-sourced**, which
is what makes this project feasible.

## 2. How it actually transmits data

After cross-referencing the vendor material, a [public reverse-engineering discussion of the
GW192A's USB encoding](https://superuser.com/questions/1907764/what-might-be-the-encoding-of-this-gw192a-thermal-imaging-usb-cam),
and the open-source drivers for its sibling cameras
([Thermal-Camera-Redux for the TC001](https://github.com/92es/Thermal-Camera-Redux),
[GetThermal](https://github.com/groupgets/GetThermal),
[community thermal-camera notes](https://gist.github.com/marcelrv/e81253c14053bcd78753554df1230dd3)),
the picture is consistent:

### 2.1 It is a standard UVC device — *not* a custom USB protocol
The camera enumerates as a **USB Video Class (UVC)** device. This is the single most important
finding: it means standard OS camera stacks (V4L2 on Linux, AVFoundation on macOS, DirectShow/
Media Foundation on Windows, `libuvc` everywhere) can open it **without a vendor driver**.

- It is **not** an MJPEG webcam in the usual sense (no useful JPEG stream for thermal data).
- It is **not** a fully custom/vendor-specific bulk protocol.
- The pixel format is **YUYV (YUV 4:2:2, `YUY2`)**, uncompressed.

### 2.2 The frame is "double height": image half + radiometric half
The defining trick of this camera family: the UVC frame height is **twice** the sensor height.

```
┌───────────────────────────┐  ← row 0
│   VISIBLE / COLORIZED      │   top half  (W × H)  — pre-colorized preview image (YUV)
│   thermal preview image    │
├───────────────────────────┤  ← row H
│   RAW RADIOMETRIC DATA     │   bottom half (W × H) — 16-bit temperature counts packed in YUYV
│   (16-bit per pixel)       │
└───────────────────────────┘  ← row 2H
```

So a 192×192 sensor presents a **192×384** YUYV stream (a 256×192 sensor presents **256×384**).
The top half is what the vendor app shows as a "picture"; the bottom half is the **measurement
data** we actually need for medical-grade temperature.

### 2.3 Radiometric conversion
Each pixel in the bottom half is a **little-endian unsigned 16-bit** count. The InfiRay/Xtherm
convention used by this family is:

```
T(°C) = raw16 / 64 − 273.15
```

(Some firmware revisions use `/16` or apply an emissivity/ambient correction; the divisor and any
offset are exposed as **calibration parameters** in our config so a unit can be trimmed against a
reference thermometer — see §5.)

### 2.4 The critical capture gotcha
If the host requests an **RGB/BGR** stream, the OS/UVC driver will *convert* the YUYV data and
**destroy the radiometric half** (it gets color-mapped as if it were image pixels). You must:

- request the raw **YUYV** format at the **doubled** resolution, and
- on Linux V4L2 specifically, set `convert_rgb = 0` (OpenCV: `cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)`).

Some units also require a **UVC Extension Unit (XU) control** or a "switch to temperature mode"
command before the radiometric half appears. Our gateway probes both modes (see
`gateway/gw192a_gateway.py`).

## 3. THG Start (reference app) — what it implies

THG Start / Thermal Master is an Android+iOS app that does on-device: UVC capture → split frame →
radiometric decode → palette colorization → spot/area temperature readout → snapshot/record.
That it works **plug-and-play over USB-C on a stock phone** confirms:

1. The camera is UVC (no kernel driver sideload needed on the phone).
2. The app embeds a **UVC stack** (Android: `libuvc`/`UVCCamera`, claiming the USB interface via
   the OTG permission dialog; iOS: AVFoundation external-camera or a bundled UVC reader).
3. The radiometric decode + palette + measurement math lives **in the app**, not the firmware.

Our platform reproduces that decode/measurement pipeline **on the server** so that *any* client
(even a thin remote viewer) gets identical, auditable results.

## 4. Platform reachability matrix (the reason for a layered design)

| Platform / browser | getUserMedia (built-in cam) | Reach GW192A from the browser? | Reach GW192A natively? |
|---|---|---|---|
| **Android Chrome/Edge** | ✅ front/back | ⚠️ WebUSB *may* work only if the kernel UVC driver doesn't claim the interface (often it does) | ✅ native bridge app (`libuvc`/UVCCamera over OTG) |
| **Android installed PWA** | ✅ | ⚠️ same caveat as above | ✅ via companion bridge app + WebSocket |
| **iOS/iPadOS Safari** | ✅ front/back | ❌ **No WebUSB at all**; no external-cam in getUserMedia | ⚠️ limited: iPadOS 17+/iPhone 15 USB-C can expose a UVC *image* stream to native AVFoundation, but **not radiometric** and **not to Safari** |
| **Windows Chrome/Edge** | ✅ | ⚠️ WebUSB can claim it if not held by the OS camera stack | ✅ **desktop gateway** (OpenCV/Media Foundation) — most reliable |
| **macOS Chrome/Edge** | ✅ | ⚠️ WebUSB limited | ✅ desktop gateway (AVFoundation/libuvc) |
| **Linux Chrome/Edge** | ✅ | ⚠️ WebUSB works only if `uvcvideo` is unbound | ✅ desktop gateway (V4L2/libuvc) — most reliable |

**Conclusions that drive the architecture:**

- **Do not rely on WebUSB.** It is unsupported on iOS/Safari & Firefox and unreliable on Android
  (kernel grabs the UVC interface) and desktop (OS camera stack grabs it). We keep WebUSB as an
  *experimental, best-effort* path only.
- The **reliable** GW192A paths are **native (Android bridge app)** and **desktop gateway**.
- **iOS cannot read radiometric thermal in-browser.** iPhones/iPads are first-class **remote
  viewers** and **built-in-RGB** clients; thermal on iOS requires the native companion app where
  the platform permits, otherwise it consumes a thermal stream produced by another device.
- The **built-in RGB camera** is always reachable via `getUserMedia()` on every target, enabling
  the **Fusion** mode (thermal overlay on RGB) and standalone RGB monitoring.

## 5. Calibration & safety notes

- Skin-surface IR temperature ≠ core body temperature. We expose **emissivity**, **distance**,
  **ambient** and a **linear offset/gain** trim per device, and recommend a forehead/inner-canthus
  ROI. The product is **not a medical device** (see root README disclaimer).
- The radiometric divisor/offset (`KELVIN_SCALE=64`, `KELVIN_OFFSET=273.15`) are configurable so a
  unit can be matched against a clinical reference.

## 6. Sources

Information below was **rephrased/summarized for licensing compliance** (no long verbatim quotes):

- GOYOJO GW192A product pages & USB-C "THG Start / Thermal Master" plug-and-play description
  (goyojotools.com, Amazon, Newegg, Shopee, eBay listings).
- Reverse-engineering discussion of the GW192A USB encoding —
  <https://superuser.com/questions/1907764/what-might-be-the-encoding-of-this-gw192a-thermal-imaging-usb-cam>
- Open-source drivers for sibling InfiRay/Xtherm cameras (data format reference):
  - Topdon TC001 — <https://github.com/92es/Thermal-Camera-Redux>
  - GetThermal — <https://github.com/groupgets/GetThermal>
  - Community thermal-camera resource list — <https://gist.github.com/marcelrv/e81253c14053bcd78753554df1230dd3>
- Independent teardown/reviews of the sibling Thermal Master P2/P3 (256×192/25 Hz, UVC double-frame
  behavior) — goughlui.com.
- UVC-over-Android references: `saki4510t/UVCCamera`, `libuvc`, RealWear UVCCamera example.

> Content from external sources was rephrased for compliance with licensing restrictions.

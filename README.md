# ThermoBaby — Professional Infant Thermal Monitoring (GW192A)

Turn any phone, tablet, or PC into a clinical-grade **infant thermal monitor** using the
**GOYOJO GW192A** USB-C thermal camera (and/or the device's built-in RGB camera), with
**remote server-side processing** and real-time results.

> **Status:** Production-oriented reference implementation. The repository contains complete,
> reviewable source for the backend (FastAPI), the desktop capture gateway (OpenCV/UVC), and
> the frontend (Next.js PWA). A **dependency-free validation harness** (`validate/`) proves the
> core thermal math (GW192A decode → temperature → statistics → infant alert engine) and can be
> run with nothing but a Python 3 stdlib interpreter.

---

## Why this architecture

The GW192A is an **InfiRay/Xtherm-class UVC camera** (same family as Topdon TC001, Thermal
Master P2/P3). See [`docs/01-gw192a-research.md`](docs/01-gw192a-research.md) for the full
reverse-engineering analysis. The two facts that shape everything:

1. It is a **standard UVC device** emitting **YUYV** frames at **25 Hz**, but the frame is
   **double height**: the top half is the visible/colorized image and the **bottom half is
   16-bit radiometric (temperature) data**. Conversion: `T(°C) = raw16 / 64 − 273.15`.
2. **Browsers cannot universally reach it.** WebUSB is unsupported on iOS/Safari and Firefox,
   and on Android the kernel UVC driver usually claims the interface. So we use a layered
   capture strategy (native bridge on Android, desktop gateway, viewer-only fallback on iOS)
   and centralize all thermal processing on the server.

```
 GW192A (UVC, YUYV, double-height)  ─┐
 Built-in RGB camera (getUserMedia) ─┤→ Capture layer → WebSocket → FastAPI server
                                      │   (per platform)              (thermal engine)
 Remote viewers (phone/tablet/PC) ───┘                                      │
                                                                            ▼
                                                          PostgreSQL + heatmaps + alerts
```

## Monorepo layout

```
gw192a-thermal/
├── README.md                  ← you are here
├── docs/                      ← architecture, research, platform strategies, risks
├── backend/                   ← FastAPI + OpenCV + NumPy thermal server (REST + WS)
├── gateway/                   ← Desktop GW192A capture gateway (Win/Linux/macOS)
├── frontend/                  ← Next.js + React + TS + Tailwind PWA
└── validate/                  ← dependency-free runnable proof of the core math
```

## Quickstart

### 0. Validate the core thermal engine (no dependencies)
```bash
python3 validate/validate_core.py
```
This synthesizes a GW192A-style double-height frame, decodes the radiometric half, computes
statistics + ROI, and runs the infant alert engine — printing a full report. Use it to verify
the math before installing anything.

### 1. Backend (requires network for deps)
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Desktop gateway (captures the GW192A and streams to the backend)
```bash
cd gateway
pip install -r requirements.txt
python gw192a_gateway.py --server ws://localhost:8000/ws/ingest --device 0
```

### 3. Frontend PWA
```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

## Documentation index

| Doc | Contents |
|-----|----------|
| [`docs/01-gw192a-research.md`](docs/01-gw192a-research.md) | GW192A protocol/encoding analysis, THG Start reference, sources |
| [`docs/02-architecture.md`](docs/02-architecture.md) | System & component diagrams, data flow, folder structure |
| [`docs/03-platform-strategies.md`](docs/03-platform-strategies.md) | Android / iOS / Windows / macOS / Linux capture strategies |
| [`docs/04-deployment.md`](docs/04-deployment.md) | Docker, TLS, scaling, environments |
| [`docs/05-testing.md`](docs/05-testing.md) | Unit / integration / E2E / hardware-in-the-loop |
| [`docs/06-risks.md`](docs/06-risks.md) | GW192A technical risks + fallbacks if no standard USB access |

## ⚠️ Medical disclaimer

This is engineering reference software, **not a certified medical device**. Skin-surface
thermography is **not equivalent to core body temperature**. Do not use it as the sole basis
for clinical decisions about an infant. Always confirm with a validated clinical thermometer
and consult a healthcare professional.

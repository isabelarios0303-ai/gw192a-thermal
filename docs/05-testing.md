# 05 — Testing Strategy

## Test pyramid

```
            ┌───────────────────────────┐
            │  E2E (Playwright)          │  few: PWA flows, multi-device viewer
            ├───────────────────────────┤
            │  Integration               │  API + WS round-trips, DB, export
            ├───────────────────────────┤
            │  Unit (engine, lib)        │  many: decode/stats/ROI/alerts/palettes
            └───────────────────────────┘
   Hardware-in-the-loop (manual + CI-optional) runs alongside, gated on a real GW192A.
```

## 1. Engine unit tests (no hardware, no network)

- **`validate/validate_core.py`** — dependency-free proof of the whole math path
  (GW192A decode → temperature → stats → ROI → alerts). Runs anywhere with Python 3:
  ```bash
  python3 validate/validate_core.py   # exits 0 on success
  ```
- **`backend/tests/test_thermal.py`** — pytest + NumPy versions:
  - radiometric round-trip (`celsius_to_raw`↔`raw_to_celsius`) within 0.02 °C;
  - double-height decode recovers the injected hotspot;
  - statistics locate hotspot/centroid; ROI mean > global mean;
  - alert thresholds (body & ambient) at every boundary (35.8/36.2/37.0/37.8/38.4 …);
  - alert-engine debounce suppresses repeats.
  ```bash
  cd backend && pip install -r requirements.txt && pytest -q
  ```

## 2. Integration tests (backend)

- **REST**: register → login (JWT) → create patient → start session → readings/alerts → export
  CSV/JSON/PDF. Use `httpx.ASGITransport` against the FastAPI app (no live server needed).
- **WebSocket**: open `/ws/ingest/<s>`, push a synthesized binary frame (reuse the gateway's
  `pack_celsius_frame`), and assert a processed frame arrives on `/ws/stream/<s>` with correct
  stats/alerts. FastAPI's `TestClient` supports `websocket_connect`.
- **Auth/RBAC**: viewer cannot start sessions; expired/invalid tokens are rejected.
- **DB**: run against SQLite in CI; smoke-test against Postgres in staging.

## 3. Frontend tests

- **Type safety**: `npm run typecheck` (tsc) in CI.
- **Unit**: `lib/thermal.ts` classifiers (`classifyBody`/`classifyAmbient`), `lib/ws.ts`
  `packFrameHeader` byte layout (assert magic `GW19`, kind, LE width/height/seq).
- **Component**: render `StatsPanel`/`AlertBanner` with fixture frames (React Testing Library).
- **E2E (Playwright)**: load the PWA, mock `getUserMedia`, connect to a stub WS that emits
  recorded frames, verify the canvas updates, palette switches, and a critical frame raises the
  alert banner + (mocked) notification.

## 4. Hardware-in-the-loop (real GW192A)

Manual checklist per platform, optionally captured as fixtures for replay:
- **Desktop gateway**: `--list` shows a doubled-height device; live max temp tracks a warm object
  (hand/forehead); cold reference (ice pack) reads near 0 °C after calibration.
- **Calibration**: compare ROI mean to a clinical thermometer at 5 setpoints; tune
  `CALIB_GAIN`/`CALIB_OFFSET` (and verify the `/64` vs `/16` divisor for the unit).
- **Android bridge**: OTG permission prompt; reconnect on unplug/replug; battery/thermal behavior.
- **Latency**: measure capture→display end-to-end (<300 ms target on LAN).

## 5. Non-functional / load

- Soak test the WS ingest at 25 FPS for hours; watch memory (frame buffers), socket churn,
  reconnect/backoff.
- Multi-viewer fan-out: 1 ingest → N viewers; verify Redis-backed fan-out at N replicas.
- Accessibility: alert banner uses `role="alert"`/`aria-live`; color is paired with icon/text
  (not color-only) for color-blind safety.

## CI outline (GitHub Actions)

```yaml
jobs:
  engine:    # python3 validate/validate_core.py  (fast gate, no deps)
  backend:   # pip install -r backend/requirements.txt && pytest -q
  frontend:  # npm ci && npm run typecheck && npm run build
```

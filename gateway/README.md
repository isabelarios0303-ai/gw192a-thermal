# GW192A Desktop Capture Gateway (Method 4)

Captures the GW192A thermal camera over **UVC** on Windows / macOS / Linux and streams decoded
radiometric frames to the ThermoBaby backend. This is the **most reliable** GW192A path on a PC
(see [`../docs/01-gw192a-research.md`](../docs/01-gw192a-research.md) and
[`../docs/03-platform-strategies.md`](../docs/03-platform-strategies.md)).

## Install
```bash
pip install -r requirements.txt
```

## Run
```bash
# 1) Find the camera (a thermal cam usually reports a DOUBLED height, e.g. 192x384)
python gw192a_gateway.py --list

# 2) Stream to the backend
python gw192a_gateway.py --server ws://localhost:8000 --session demo --device 2

# No hardware? Emit a synthetic moving warm body to exercise the full pipeline:
python gw192a_gateway.py --simulate --session demo
```

## Key flags
| Flag | Meaning |
|------|---------|
| `--device N` | UVC device index (use `--list` to find it) |
| `--width/--height` | sensor geometry per *half* (default 192x192; use 256x192 for that sibling) |
| `--send-raw` | send radiometric `uint16` (`kind=1`) instead of Celsius `float32` (`kind=2`) |
| `--fps` | frames/sec to publish (≤25) |
| `--simulate` | no camera; synthesize a body for testing |

## How the decode works
The GW192A presents a **double-height YUYV** frame. We:
1. open the device, **disable RGB conversion** (`CAP_PROP_CONVERT_RGB=0`) and request `YUYV` at
   `width × (height*2)` — otherwise the OS color-maps and destroys the radiometric half;
2. reinterpret the raw bytes as little-endian `uint16`;
3. take the **bottom half** (`width*height` values) as radiometric counts;
4. convert `T(°C) = raw/64 − 273.15` (configurable trim) and send to `/ws/ingest/<session>`.

## Per-unit tuning
Firmware variants differ slightly. If temperatures look wrong:
- some units want the **top** half for radiometric — swap halves;
- some use `/16` instead of `/64`, or include an ambient/emissivity correction — adjust the
  constants at the top of `gw192a_gateway.py` (and the matching backend `.env`);
- trim against a clinical thermometer using `CALIB_GAIN` / `CALIB_OFFSET`.

## Packaging
Bundle as a one-file executable for non-technical users:
```bash
pip install pyinstaller
pyinstaller --onefile gw192a_gateway.py
```

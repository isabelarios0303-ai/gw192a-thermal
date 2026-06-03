// In-browser thermal demo engine.
//
// When the app is deployed (e.g. Netlify) there is no Python backend or gateway reachable, so
// this module synthesizes the SAME kind of processed frames the server would emit — entirely in
// the browser — so a phone/tablet can open the public URL and see ThermoBaby working instantly.
//
// It mirrors backend/app/thermal: a moving warm "body" over a cool background, with statistics
// (min/max/mean/std, hotspot, coldspot, centroid, histogram), the infant alert thresholds, and a
// colorized heatmap (palette LUT) drawn to an offscreen canvas and emitted as a PNG data URL.

import type { AlertItem, FrameStats, PaletteName, ProcessedFrame } from './thermal';
import { classifyAmbient, classifyBody } from './thermal';

const W = 96;
const H = 96;

type RGB = [number, number, number];

function buildLut(stops: [number, RGB][]): Uint8ClampedArray {
  const lut = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    const x = i / 255;
    let a = stops[0];
    let b = stops[stops.length - 1];
    for (let s = 0; s < stops.length - 1; s++) {
      if (x >= stops[s][0] && x <= stops[s + 1][0]) {
        a = stops[s];
        b = stops[s + 1];
        break;
      }
    }
    const span = b[0] - a[0] || 1;
    const t = (x - a[0]) / span;
    lut[i * 3] = a[1][0] + (b[1][0] - a[1][0]) * t;
    lut[i * 3 + 1] = a[1][1] + (b[1][1] - a[1][1]) * t;
    lut[i * 3 + 2] = a[1][2] + (b[1][2] - a[1][2]) * t;
  }
  return lut;
}

const LUTS: Record<PaletteName, Uint8ClampedArray> = {
  iron: buildLut([
    [0.0, [0, 0, 0]],
    [0.25, [110, 0, 60]],
    [0.5, [120, 30, 160]],
    [0.7, [40, 90, 230]],
    [0.85, [20, 170, 255]],
    [1.0, [220, 255, 255]],
  ]),
  rainbow: buildLut([
    [0.0, [130, 0, 0]],
    [0.2, [255, 80, 0]],
    [0.4, [220, 220, 0]],
    [0.6, [60, 220, 0]],
    [0.8, [0, 230, 255]],
    [1.0, [0, 30, 255]],
  ]),
  white_hot: buildLut([
    [0.0, [0, 0, 0]],
    [1.0, [255, 255, 255]],
  ]),
  black_hot: buildLut([
    [0.0, [255, 255, 255]],
    [1.0, [0, 0, 0]],
  ]),
  medical: buildLut([
    [0.0, [90, 20, 10]],
    [0.35, [180, 140, 0]],
    [0.55, [90, 170, 0]],
    [0.72, [40, 210, 240]],
    [0.86, [20, 120, 240]],
    [1.0, [30, 20, 220]],
  ]),
  grayscale: buildLut([
    [0.0, [0, 0, 0]],
    [1.0, [255, 255, 255]],
  ]),
};

function synthCelsius(t: number, ambient: number, peak: number): Float32Array {
  const grid = new Float32Array(W * H);
  const cx = W / 2 + Math.sin(t) * (W / 6);
  const cy = H / 2 + Math.cos(t * 0.7) * (H / 6);
  const sigma = W / 6;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const d2 = (x - cx) ** 2 + (y - cy) ** 2;
      const g = Math.exp(-d2 / (2 * sigma * sigma));
      const noise = (Math.random() - 0.5) * 0.1;
      grid[y * W + x] = ambient + (peak - ambient) * g + noise;
    }
  }
  return grid;
}

function computeStats(grid: Float32Array): FrameStats {
  let tMin = Infinity;
  let tMax = -Infinity;
  let sum = 0;
  let sum2 = 0;
  let hot = 0;
  let cold = 0;
  for (let i = 0; i < grid.length; i++) {
    const v = grid[i];
    sum += v;
    sum2 += v * v;
    if (v > tMax) {
      tMax = v;
      hot = i;
    }
    if (v < tMin) {
      tMin = v;
      cold = i;
    }
  }
  const n = grid.length;
  const mean = sum / n;
  const std = Math.sqrt(Math.max(0, sum2 / n - mean * mean));

  let wsum = 0;
  let cx = 0;
  let cy = 0;
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const w = Math.max(0, grid[y * W + x] - mean);
      wsum += w;
      cx += w * x;
      cy += w * y;
    }
  }
  const centroid: [number, number] = wsum > 0 ? [cx / wsum, cy / wsum] : [W / 2, H / 2];

  const bins = 24;
  const hist = new Array(bins).fill(0);
  const span = tMax - tMin || 1;
  for (let i = 0; i < grid.length; i++) {
    const idx = Math.min(bins - 1, Math.floor(((grid[i] - tMin) / span) * (bins - 1)));
    hist[idx]++;
  }

  return {
    t_min: tMin,
    t_max: tMax,
    t_mean: mean,
    t_std: std,
    hotspot: [hot % W, Math.floor(hot / W)],
    coldspot: [cold % W, Math.floor(cold / W)],
    centroid,
    histogram: hist,
    hist_lo: tMin,
    hist_hi: tMax,
  };
}

function colorize(grid: Float32Array, palette: PaletteName, stats: FrameStats): string {
  const lut = LUTS[palette] ?? LUTS.iron;
  const small = document.createElement('canvas');
  small.width = W;
  small.height = H;
  const sctx = small.getContext('2d')!;
  const img = sctx.createImageData(W, H);
  const span = stats.t_max - stats.t_min || 1;
  for (let i = 0; i < grid.length; i++) {
    const norm = Math.max(0, Math.min(1, (grid[i] - stats.t_min) / span));
    const li = Math.round(norm * 255) * 3;
    img.data[i * 4] = lut[li];
    img.data[i * 4 + 1] = lut[li + 1];
    img.data[i * 4 + 2] = lut[li + 2];
    img.data[i * 4 + 3] = 255;
  }
  sctx.putImageData(img, 0, 0);

  // upscale + draw markers on a bigger canvas for a crisp result
  const scale = 5;
  const big = document.createElement('canvas');
  big.width = W * scale;
  big.height = H * scale;
  const bctx = big.getContext('2d')!;
  bctx.imageSmoothingEnabled = true;
  bctx.drawImage(small, 0, 0, big.width, big.height);

  const [hx, hy] = stats.hotspot;
  const [cx, cy] = stats.coldspot;
  // hotspot marker
  bctx.strokeStyle = '#ff3030';
  bctx.lineWidth = 2;
  bctx.beginPath();
  bctx.arc(hx * scale, hy * scale, 10, 0, Math.PI * 2);
  bctx.stroke();
  bctx.fillStyle = '#ff3030';
  bctx.font = '16px monospace';
  bctx.fillText(`${stats.t_max.toFixed(1)}C`, hx * scale + 12, hy * scale);
  // coldspot marker
  bctx.strokeStyle = '#00c8ff';
  bctx.beginPath();
  bctx.arc(cx * scale, cy * scale, 8, 0, Math.PI * 2);
  bctx.stroke();
  // center crosshair
  bctx.strokeStyle = 'rgba(255,255,255,0.8)';
  bctx.lineWidth = 1;
  bctx.beginPath();
  bctx.moveTo(big.width / 2 - 10, big.height / 2);
  bctx.lineTo(big.width / 2 + 10, big.height / 2);
  bctx.moveTo(big.width / 2, big.height / 2 - 10);
  bctx.lineTo(big.width / 2, big.height / 2 + 10);
  bctx.stroke();

  return big.toDataURL('image/png').split(',')[1];
}

export interface DemoOptions {
  palette: PaletteName;
  fps?: number;
}

/**
 * Start the in-browser demo. Calls onFrame with synthesized ProcessedFrames until disposed.
 * Returns a stop function.
 */
export function startDemo(getPalette: () => PaletteName, onFrame: (f: ProcessedFrame) => void): () => void {
  let seq = 0;
  const t0 = performance.now();
  let raf = 0;
  let last = 0;
  const period = 1000 / 8; // ~8 fps

  const loop = (now: number) => {
    raf = requestAnimationFrame(loop);
    if (now - last < period) return;
    last = now;
    const t = (now - t0) / 1000;
    // body temperature gently drifts through normal/warning/critical to showcase alerts
    const peak = 37.0 + 1.4 * Math.sin(t / 9);
    const ambient = 22.0;
    const grid = synthCelsius(t, ambient, peak);
    const stats = computeStats(grid);
    const palette = getPalette();
    const image_png_b64 = colorize(grid, palette, stats);

    const alerts: AlertItem[] = [];
    const bodyLevel = classifyBody(stats.t_max);
    if (bodyLevel !== 'ok') {
      alerts.push({
        level: bodyLevel,
        code: bodyLevel === 'critical' ? 'BODY_CRIT' : 'BODY_WARN',
        message:
          stats.t_max >= 38
            ? 'Temperatura crítica'
            : stats.t_max > 37.5
              ? 'Temperatura elevada (posible fiebre)'
              : stats.t_max < 36
                ? 'Temperatura crítica (hipotermia)'
                : 'Hipotermia potencial',
        value: stats.t_max,
      });
    }
    const ambLevel = classifyAmbient(stats.t_min);
    if (ambLevel !== 'ok') {
      alerts.push({
        level: ambLevel,
        code: stats.t_min < 20 ? 'AMB_COLD' : 'AMB_HOT',
        message: stats.t_min < 20 ? 'Ambiente muy frío' : 'Ambiente muy caliente',
        value: stats.t_min,
      });
    }

    onFrame({
      seq: seq++,
      ts: Date.now(),
      geometry: `${W}x${H}`,
      palette,
      stats,
      rois: [
        {
          id: 'frente',
          name: 'frente',
          t_min: stats.t_mean,
          t_max: stats.t_max,
          t_mean: (stats.t_mean + stats.t_max) / 2,
          t_std: stats.t_std,
          pixels: 400,
        },
      ],
      alerts,
      image_png_b64,
    });
  };
  raf = requestAnimationFrame(loop);
  return () => cancelAnimationFrame(raf);
}

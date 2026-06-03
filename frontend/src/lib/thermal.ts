// Shared thermal types + thresholds (kept in sync with backend/app/thermal/alerts.py).

export type PaletteName =
  | 'iron'
  | 'rainbow'
  | 'white_hot'
  | 'black_hot'
  | 'medical'
  | 'grayscale';

export const PALETTES: PaletteName[] = [
  'iron',
  'rainbow',
  'white_hot',
  'black_hot',
  'medical',
  'grayscale',
];

export type DisplayMode = 'rgb' | 'thermal' | 'fusion';
export type AlertLevel = 'ok' | 'warning' | 'critical';

export const THRESHOLDS = {
  body: { normalLow: 36.5, normalHigh: 37.5, critLow: 36.0, critHigh: 38.0 },
  ambient: { normalLow: 20.0, normalHigh: 24.0 },
};

export interface FrameStats {
  t_min: number;
  t_max: number;
  t_mean: number;
  t_std: number;
  hotspot: [number, number];
  coldspot: [number, number];
  centroid: [number, number];
  histogram: number[];
  hist_lo: number;
  hist_hi: number;
}

export interface RoiResult {
  id: string;
  name: string;
  t_min: number;
  t_max: number;
  t_mean: number;
  t_std: number;
  pixels: number;
}

export interface AlertItem {
  level: AlertLevel;
  code: string;
  message: string;
  value: number;
}

export interface ProcessedFrame {
  seq: number;
  ts: number;
  geometry: string;
  palette: PaletteName;
  stats: FrameStats;
  rois: RoiResult[];
  alerts: AlertItem[];
  image_png_b64: string | null;
}

export interface Roi {
  id: string;
  name: string;
  x0: number; // normalized 0..1
  y0: number;
  x1: number;
  y1: number;
  locked: boolean;
  normalized: boolean;
}

export function classifyBody(t: number): AlertLevel {
  const b = THRESHOLDS.body;
  if (t >= b.critHigh || t < b.critLow) return 'critical';
  if (t > b.normalHigh || t < b.normalLow) return 'warning';
  return 'ok';
}

export function classifyAmbient(t: number): AlertLevel {
  const a = THRESHOLDS.ambient;
  if (t < a.normalLow || t > a.normalHigh) return 'warning';
  return 'ok';
}

export function levelColor(level: AlertLevel): string {
  return level === 'critical' ? '#ef4444' : level === 'warning' ? '#f59e0b' : '#22c55e';
}

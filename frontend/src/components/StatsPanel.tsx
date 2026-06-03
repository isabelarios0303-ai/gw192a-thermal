'use client';

import type { FrameStats, RoiResult } from '@/lib/thermal';
import { classifyBody, levelColor } from '@/lib/thermal';

function Metric({ label, value, unit = '°C', color }: { label: string; value: number; unit?: string; color?: string }) {
  return (
    <div className="card p-3">
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="stat-value text-2xl" style={{ color }}>
        {Number.isFinite(value) ? value.toFixed(1) : '--'}
        <span className="text-sm text-slate-500"> {unit}</span>
      </div>
    </div>
  );
}

export function StatsPanel({ stats, rois }: { stats: FrameStats | null; rois: RoiResult[] }) {
  const roiMean = rois[0]?.t_mean;
  const peak = stats?.t_max ?? NaN;
  return (
    <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
      <Metric label="Máxima" value={peak} color={levelColor(classifyBody(peak))} />
      <Metric label="Mínima" value={stats?.t_min ?? NaN} />
      <Metric label="Promedio" value={stats?.t_mean ?? NaN} />
      <Metric
        label="ROI promedio"
        value={roiMean ?? NaN}
        color={roiMean ? levelColor(classifyBody(roiMean)) : undefined}
      />
    </div>
  );
}

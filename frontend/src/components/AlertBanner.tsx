'use client';

import type { AlertItem } from '@/lib/thermal';

export function AlertBanner({ alerts }: { alerts: AlertItem[] }) {
  if (!alerts.length) {
    return (
      <div className="card flex items-center gap-2 p-3 text-sm text-ok">
        <span className="h-2 w-2 rounded-full bg-ok" /> Estado normal
      </div>
    );
  }
  const top = alerts.reduce((a, b) => (b.level === 'critical' ? b : a), alerts[0]);
  const isCrit = top.level === 'critical';
  return (
    <div
      className={`card flex items-center justify-between p-3 ${isCrit ? 'pulse-crit border-crit/40' : 'border-warn/40'}`}
      role="alert"
      aria-live="assertive"
    >
      <div className="flex items-center gap-3">
        <span
          className="inline-flex h-8 w-8 items-center justify-center rounded-full text-lg"
          style={{ background: isCrit ? '#ef4444' : '#f59e0b', color: '#0b1020' }}
        >
          {isCrit ? '!' : '⚠'}
        </span>
        <div>
          <div className="font-semibold" style={{ color: isCrit ? '#ef4444' : '#f59e0b' }}>
            {top.message}
          </div>
          <div className="text-xs text-slate-400">
            {top.value.toFixed(1)}°C · {top.code}
          </div>
        </div>
      </div>
      {alerts.length > 1 && <span className="text-xs text-slate-400">+{alerts.length - 1} más</span>}
    </div>
  );
}

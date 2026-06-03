'use client';

import type { DisplayMode } from '@/lib/thermal';

const MODES: { id: DisplayMode; label: string }[] = [
  { id: 'rgb', label: 'RGB' },
  { id: 'thermal', label: 'Térmico' },
  { id: 'fusion', label: 'Fusión' },
];

export function ModeSwitch({ value, onChange }: { value: DisplayMode; onChange: (m: DisplayMode) => void }) {
  return (
    <div className="inline-flex rounded-xl bg-bg-soft p-1">
      {MODES.map((m) => (
        <button
          key={m.id}
          onClick={() => onChange(m.id)}
          className={`rounded-lg px-4 py-1.5 text-sm transition ${
            value === m.id ? 'bg-accent text-bg font-semibold' : 'text-slate-300'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

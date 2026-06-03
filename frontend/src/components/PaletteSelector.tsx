'use client';

import { PALETTES, type PaletteName } from '@/lib/thermal';

const LABELS: Record<PaletteName, string> = {
  iron: 'Iron',
  rainbow: 'Rainbow',
  white_hot: 'White Hot',
  black_hot: 'Black Hot',
  medical: 'Medical',
  grayscale: 'Grayscale',
};

export function PaletteSelector({
  value,
  onChange,
}: {
  value: PaletteName;
  onChange: (p: PaletteName) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {PALETTES.map((p) => (
        <button
          key={p}
          onClick={() => onChange(p)}
          className={`rounded-lg px-3 py-1.5 text-sm transition ${
            value === p
              ? 'bg-accent text-bg font-semibold'
              : 'bg-bg-soft text-slate-300 hover:bg-white/10'
          }`}
        >
          {LABELS[p]}
        </button>
      ))}
    </div>
  );
}

'use client';

export interface FusionState {
  alpha: number;
  dx: number;
  dy: number;
  scale: number;
  rotation: number;
}

export const DEFAULT_FUSION: FusionState = { alpha: 0.5, dx: 0, dy: 0, scale: 1, rotation: 0 };

function Slider({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block">
      <div className="mb-1 flex justify-between text-xs text-slate-400">
        <span>{label}</span>
        <span className="stat-value">
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        className="w-full"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(parseFloat(e.target.value))}
      />
    </label>
  );
}

export function FusionControls({
  state,
  onChange,
}: {
  state: FusionState;
  onChange: (s: FusionState) => void;
}) {
  const set = (patch: Partial<FusionState>) => onChange({ ...state, ...patch });
  return (
    <div className="card space-y-3 p-4">
      <div className="text-sm font-semibold text-slate-200">Controles de fusión</div>
      <Slider label="Transparencia" value={state.alpha} min={0} max={1} step={0.05} onChange={(v) => set({ alpha: v })} />
      <Slider label="Alineación X" value={state.dx} min={-100} max={100} step={1} unit="px" onChange={(v) => set({ dx: v })} />
      <Slider label="Alineación Y" value={state.dy} min={-100} max={100} step={1} unit="px" onChange={(v) => set({ dy: v })} />
      <Slider label="Escala" value={state.scale} min={0.5} max={2} step={0.05} unit="x" onChange={(v) => set({ scale: v })} />
      <Slider label="Rotación" value={state.rotation} min={-180} max={180} step={1} unit="°" onChange={(v) => set({ rotation: v })} />
      <button onClick={() => onChange(DEFAULT_FUSION)} className="text-xs text-accent hover:underline">
        Restablecer
      </button>
    </div>
  );
}

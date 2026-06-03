'use client';

import { useEffect, useState } from 'react';
import { NavBar } from '@/components/NavBar';
import { api } from '@/lib/api';
import { isWebUsbSupported, tryClaimGw192a } from '@/lib/webusb';
import { THRESHOLDS } from '@/lib/thermal';

export default function SettingsPage() {
  const [health, setHealth] = useState<string>('…');
  const [webusbMsg, setWebusbMsg] = useState<string>('');

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h.status))
      .catch(() => setHealth('sin conexión'));
  }, []);

  const testWebUsb = async () => {
    const res = await tryClaimGw192a();
    setWebusbMsg(res.ok ? 'GW192A reclamada por WebUSB ✔' : `WebUSB no disponible: ${res.reason}`);
  };

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-3xl space-y-4 px-4 py-6">
        <h1 className="text-lg font-semibold text-slate-200">Settings</h1>

        <section className="card space-y-2 p-4">
          <h2 className="font-semibold text-slate-200">Servidor</h2>
          <div className="text-sm text-slate-400">API: {api.base}</div>
          <div className="text-sm text-slate-400">Estado: {health}</div>
        </section>

        <section className="card space-y-2 p-4">
          <h2 className="font-semibold text-slate-200">Captura de la GW192A</h2>
          <p className="text-sm text-slate-400">
            Método recomendado por plataforma: <b>Escritorio</b> → gateway local;{' '}
            <b>Android</b> → app puente USB; <b>iPhone/iPad</b> → visor remoto o app nativa.
          </p>
          <div className="text-sm">
            WebUSB: {isWebUsbSupported() ? 'disponible (experimental)' : 'no soportado'}
          </div>
          <button
            onClick={testWebUsb}
            disabled={!isWebUsbSupported()}
            className="w-fit rounded-lg bg-accent px-3 py-1.5 text-sm text-bg disabled:opacity-40"
          >
            Probar WebUSB
          </button>
          {webusbMsg && <div className="text-xs text-slate-400">{webusbMsg}</div>}
        </section>

        <section className="card space-y-2 p-4">
          <h2 className="font-semibold text-slate-200">Umbrales de alerta</h2>
          <div className="grid grid-cols-2 gap-2 text-sm text-slate-300">
            <div>Corporal normal</div>
            <div className="stat-value">
              {THRESHOLDS.body.normalLow}–{THRESHOLDS.body.normalHigh}°C
            </div>
            <div>Corporal crítica</div>
            <div className="stat-value">
              &lt;{THRESHOLDS.body.critLow} o ≥{THRESHOLDS.body.critHigh}°C
            </div>
            <div>Ambiente normal</div>
            <div className="stat-value">
              {THRESHOLDS.ambient.normalLow}–{THRESHOLDS.ambient.normalHigh}°C
            </div>
          </div>
        </section>

        <section className="card space-y-2 p-4">
          <h2 className="font-semibold text-slate-200">Aviso</h2>
          <p className="text-sm text-slate-400">
            Software de referencia, no es un dispositivo médico. Verifique siempre con un
            termómetro clínico validado.
          </p>
        </section>
      </main>
    </>
  );
}

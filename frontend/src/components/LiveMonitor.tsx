'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { isDemoMode, subscribeStream } from '@/lib/ws';
import { startDemo } from '@/lib/demo';
import { startCamera, stopStream } from '@/lib/camera';
import { makeAlertGate, requestNotificationPermission } from '@/lib/alerts';
import type { DisplayMode, PaletteName, ProcessedFrame } from '@/lib/thermal';
import { ThermalCanvas } from './ThermalCanvas';
import { StatsPanel } from './StatsPanel';
import { PaletteSelector } from './PaletteSelector';
import { AlertBanner } from './AlertBanner';
import { ModeSwitch } from './ModeSwitch';
import { FusionControls, DEFAULT_FUSION, type FusionState } from './FusionControls';

export function LiveMonitor({ sessionId = 'demo' }: { sessionId?: string }) {
  const [mode, setMode] = useState<DisplayMode>('thermal');
  const [palette, setPalette] = useState<PaletteName>('medical');
  const [fusion, setFusion] = useState<FusionState>(DEFAULT_FUSION);
  const [frame, setFrame] = useState<ProcessedFrame | null>(null);
  const [status, setStatus] = useState<'open' | 'closed' | 'error'>('closed');
  const [demo, setDemo] = useState(false);
  const [camOn, setCamOn] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const alertGate = useRef(makeAlertGate());
  const paletteRef = useRef<PaletteName>(palette);
  paletteRef.current = palette;

  // Either subscribe to the real backend stream, or run the in-browser demo (e.g. on Netlify).
  useEffect(() => {
    const useDemo = isDemoMode();
    setDemo(useDemo);
    if (useDemo) {
      setStatus('open');
      const stop = startDemo(
        () => paletteRef.current,
        (f) => {
          setFrame(f);
          if (f.alerts?.length) alertGate.current(f.alerts);
        }
      );
      return stop;
    }
    const dispose = subscribeStream(
      sessionId,
      (f) => {
        setFrame(f);
        if (f.alerts?.length) alertGate.current(f.alerts);
      },
      setStatus
    );
    return dispose;
  }, [sessionId]);

  // notifications permission on first interaction
  useEffect(() => {
    void requestNotificationPermission();
  }, []);

  const toggleCamera = useCallback(async () => {
    if (camOn) {
      stopStream(streamRef.current);
      streamRef.current = null;
      setCamOn(false);
      return;
    }
    try {
      const stream = await startCamera('environment');
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setCamOn(true);
    } catch (e) {
      alert('No se pudo abrir la cámara: ' + (e as Error).message);
    }
  }, [camOn]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <ModeSwitch value={mode} onChange={setMode} />
          <div className="flex items-center gap-2 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${status === 'open' ? 'bg-ok' : 'bg-crit'}`}
            />
            <span className="text-slate-400">
              {demo
                ? 'Modo demostración (en el navegador)'
                : status === 'open'
                  ? 'Conectado'
                  : 'Sin conexión'}{' '}
              · sesión {sessionId}
            </span>
          </div>
        </div>

        <AlertBanner alerts={frame?.alerts ?? []} />

        <video ref={videoRef} className="hidden" playsInline muted />
        <ThermalCanvas mode={mode} frame={frame} rgbVideo={videoRef.current} fusion={fusion} />

        <StatsPanel stats={frame?.stats ?? null} rois={frame?.rois ?? []} />
      </div>

      <aside className="space-y-4">
        <div className="card space-y-3 p-4">
          <button
            onClick={toggleCamera}
            className="w-full rounded-lg bg-accent px-4 py-2 font-semibold text-bg"
          >
            {camOn ? 'Detener cámara RGB' : 'Activar cámara RGB'}
          </button>
          <div className="text-xs text-slate-400">
            {demo
              ? 'Estás en modo demostración: el mapa térmico se genera en tu navegador, sin servidor. Activa la cámara para probar los modos RGB y Fusión con la cámara real de tu teléfono.'
              : 'La cámara integrada habilita los modos RGB y Fusión. El stream térmico llega del servidor (gateway / app puente / WebUSB).'}
          </div>
        </div>

        <div className="card space-y-2 p-4">
          <div className="text-sm font-semibold text-slate-200">Paleta térmica</div>
          <PaletteSelector value={palette} onChange={setPalette} />
        </div>

        {mode === 'fusion' && <FusionControls state={fusion} onChange={setFusion} />}

        {frame?.rois && frame.rois.length > 0 && (
          <div className="card space-y-2 p-4">
            <div className="text-sm font-semibold text-slate-200">Regiones (ROI)</div>
            {frame.rois.map((r) => (
              <div key={r.id} className="flex justify-between text-sm">
                <span className="text-slate-400">{r.name}</span>
                <span className="stat-value">{r.t_mean.toFixed(1)}°C</span>
              </div>
            ))}
          </div>
        )}
      </aside>
    </div>
  );
}

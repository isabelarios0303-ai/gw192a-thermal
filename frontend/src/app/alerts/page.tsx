'use client';

import { useEffect, useState } from 'react';
import { NavBar } from '@/components/NavBar';
import { api } from '@/lib/api';
import { levelColor } from '@/lib/thermal';

interface AlertEvent {
  ts: string;
  level: 'warning' | 'critical';
  code: string;
  message: string;
  value: number;
}

export default function AlertsPage() {
  const [sessionId, setSessionId] = useState('demo');
  const [events, setEvents] = useState<AlertEvent[]>([]);

  const load = async () => {
    try {
      setEvents(await api.alerts(sessionId));
    } catch {
      setEvents([]);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <div className="mb-4 flex items-center gap-2">
          <h1 className="text-lg font-semibold text-slate-200">Alerts</h1>
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="rounded-lg bg-bg-soft px-3 py-1.5 text-sm"
          />
          <button onClick={load} className="rounded-lg bg-accent px-3 py-1.5 text-sm text-bg">
            Cargar
          </button>
        </div>

        <div className="space-y-2">
          {events.map((e, i) => (
            <div key={i} className="card flex items-center gap-3 p-3">
              <span
                className="h-3 w-3 rounded-full"
                style={{ background: levelColor(e.level) }}
              />
              <div className="flex-1">
                <div className="font-medium" style={{ color: levelColor(e.level) }}>
                  {e.message}
                </div>
                <div className="text-xs text-slate-400">
                  {new Date(e.ts).toLocaleString()} · {e.code}
                </div>
              </div>
              <div className="stat-value text-lg">{e.value.toFixed(1)}°C</div>
            </div>
          ))}
          {!events.length && (
            <div className="card p-6 text-center text-slate-500">Sin eventos registrados.</div>
          )}
        </div>
      </main>
    </>
  );
}

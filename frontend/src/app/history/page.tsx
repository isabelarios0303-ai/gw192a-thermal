'use client';

import { useEffect, useState } from 'react';
import { NavBar } from '@/components/NavBar';
import { api } from '@/lib/api';

interface Reading {
  ts: string;
  t_min: number;
  t_max: number;
  t_mean: number;
  roi_mean: number | null;
  ambient: number | null;
}

export default function HistoryPage() {
  const [sessionId, setSessionId] = useState('demo');
  const [readings, setReadings] = useState<Reading[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setError(null);
      setReadings(await api.readings(sessionId));
    } catch (e) {
      setError((e as Error).message);
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
          <h1 className="text-lg font-semibold text-slate-200">History</h1>
          <input
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            className="rounded-lg bg-bg-soft px-3 py-1.5 text-sm"
            placeholder="session id"
          />
          <button onClick={load} className="rounded-lg bg-accent px-3 py-1.5 text-sm text-bg">
            Cargar
          </button>
          <div className="ml-auto flex gap-2 text-sm">
            <a href={api.exportUrl(sessionId, 'csv')} className="text-accent hover:underline">CSV</a>
            <a href={api.exportUrl(sessionId, 'json')} className="text-accent hover:underline">JSON</a>
            <a href={api.exportUrl(sessionId, 'pdf')} className="text-accent hover:underline">PDF</a>
          </div>
        </div>

        {error && <div className="card p-3 text-sm text-crit">Error: {error}</div>}

        <div className="card overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead className="bg-bg-soft text-left text-xs uppercase text-slate-400">
              <tr>
                <th className="p-3">Hora</th>
                <th className="p-3">Máx</th>
                <th className="p-3">Mín</th>
                <th className="p-3">Prom</th>
                <th className="p-3">ROI</th>
                <th className="p-3">Ambiente</th>
              </tr>
            </thead>
            <tbody className="stat-value">
              {readings.map((r, i) => (
                <tr key={i} className="border-t border-white/5">
                  <td className="p-3 text-slate-400">{new Date(r.ts).toLocaleTimeString()}</td>
                  <td className="p-3">{r.t_max.toFixed(1)}</td>
                  <td className="p-3">{r.t_min.toFixed(1)}</td>
                  <td className="p-3">{r.t_mean.toFixed(1)}</td>
                  <td className="p-3">{r.roi_mean?.toFixed(1) ?? '--'}</td>
                  <td className="p-3">{r.ambient?.toFixed(1) ?? '--'}</td>
                </tr>
              ))}
              {!readings.length && (
                <tr>
                  <td colSpan={6} className="p-6 text-center text-slate-500">
                    Sin lecturas para esta sesión.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </main>
    </>
  );
}

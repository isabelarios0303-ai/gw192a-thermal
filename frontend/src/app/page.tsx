import { NavBar } from '@/components/NavBar';
import { LiveMonitor } from '@/components/LiveMonitor';

export default function Page() {
  return (
    <>
      <NavBar />
      <main className="mx-auto max-w-6xl px-4 py-6">
        <h1 className="mb-4 text-lg font-semibold text-slate-200">Live Monitor</h1>
        <LiveMonitor sessionId="demo" />
        <p className="mt-6 text-center text-xs text-slate-500">
          Software de referencia de ingeniería. No es un dispositivo médico certificado. La
          temperatura cutánea no equivale a la temperatura corporal central.
        </p>
      </main>
    </>
  );
}

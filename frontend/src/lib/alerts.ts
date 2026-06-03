// Client-side alert delivery: sound, vibration, and push notifications.

import type { AlertItem } from './thermal';

let audioCtx: AudioContext | null = null;

function beep(freq: number, durationMs: number): void {
  try {
    audioCtx = audioCtx || new (window.AudioContext || (window as any).webkitAudioContext)();
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.frequency.value = freq;
    osc.type = 'sine';
    gain.gain.value = 0.15;
    osc.connect(gain).connect(audioCtx.destination);
    osc.start();
    osc.stop(audioCtx.currentTime + durationMs / 1000);
  } catch {
    /* audio not allowed before user gesture */
  }
}

export function vibrate(level: AlertItem['level']): void {
  if (!('vibrate' in navigator)) return;
  navigator.vibrate(level === 'critical' ? [300, 120, 300, 120, 300] : [200, 100, 200]);
}

export async function requestNotificationPermission(): Promise<boolean> {
  if (!('Notification' in window)) return false;
  if (Notification.permission === 'granted') return true;
  const p = await Notification.requestPermission();
  return p === 'granted';
}

export async function notify(alert: AlertItem): Promise<void> {
  // sound + vibration
  beep(alert.level === 'critical' ? 1000 : 700, alert.level === 'critical' ? 500 : 250);
  vibrate(alert.level);

  // system notification via the service worker if available
  if ('Notification' in window && Notification.permission === 'granted') {
    const reg = await navigator.serviceWorker?.getRegistration();
    const opts: NotificationOptions = {
      body: `${alert.message} (${alert.value.toFixed(1)}°C)`,
      tag: 'thermobaby-alert',
      requireInteraction: alert.level === 'critical',
    };
    if (reg) reg.showNotification('ThermoBaby — Alerta', opts);
    else new Notification('ThermoBaby — Alerta', opts);
  }
}

/** Deduplicate: only deliver an alert when its (code, level) changes. */
export function makeAlertGate() {
  let last = '';
  return (alerts: AlertItem[]) => {
    for (const a of alerts) {
      const key = `${a.code}:${a.level}`;
      if (key !== last) {
        last = key;
        void notify(a);
      }
    }
  };
}

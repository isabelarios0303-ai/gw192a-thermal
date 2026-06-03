// WebSocket client for processed thermal frames + binary frame packing for ingest.

import type { ProcessedFrame } from './thermal';

const WS_BASE = process.env.NEXT_PUBLIC_WS_BASE || 'ws://localhost:8000';

export const KIND_RADIOMETRIC_U16 = 1;
export const KIND_CELSIUS_F32 = 2;
export const KIND_RGB_JPEG = 3;

/** Subscribe to processed frames for a session. Returns a disposer. */
export function subscribeStream(
  sessionId: string,
  onFrame: (frame: ProcessedFrame) => void,
  onStatus?: (s: 'open' | 'closed' | 'error') => void
): () => void {
  let ws: WebSocket | null = null;
  let closed = false;
  let retry = 1000;

  const connect = () => {
    if (closed) return;
    ws = new WebSocket(`${WS_BASE}/ws/stream/${sessionId}`);
    ws.onopen = () => {
      retry = 1000;
      onStatus?.('open');
      // keepalive ping every 25s
      const ping = setInterval(() => ws?.readyState === 1 && ws.send('ping'), 25000);
      ws!.onclose = () => {
        clearInterval(ping);
        onStatus?.('closed');
        if (!closed) setTimeout(connect, (retry = Math.min(15000, retry * 2)));
      };
    };
    ws.onerror = () => onStatus?.('error');
    ws.onmessage = (ev) => {
      try {
        onFrame(JSON.parse(ev.data) as ProcessedFrame);
      } catch {
        /* ignore malformed */
      }
    };
  };
  connect();

  return () => {
    closed = true;
    ws?.close();
  };
}

/** Build the binary ingest header: magic|ver|kind|w|h|seq|ts (little-endian). */
export function packFrameHeader(kind: number, w: number, h: number, seq: number): ArrayBuffer {
  const buf = new ArrayBuffer(22);
  const dv = new DataView(buf);
  dv.setUint8(0, 0x47); // G
  dv.setUint8(1, 0x57); // W
  dv.setUint8(2, 0x31); // 1
  dv.setUint8(3, 0x39); // 9
  dv.setUint8(4, 1); // version
  dv.setUint8(5, kind);
  dv.setUint16(6, w, true);
  dv.setUint16(8, h, true);
  dv.setUint32(10, seq >>> 0, true);
  // ts_ms as 64-bit little-endian
  const ts = BigInt(Date.now());
  dv.setBigUint64(14, ts, true);
  return buf;
}

/** Concatenate header + payload into a single Blob for ws.send. */
export function packFrame(kind: number, w: number, h: number, seq: number, payload: ArrayBuffer): Blob {
  return new Blob([packFrameHeader(kind, w, h, seq), payload]);
}

/** Open an ingest socket (for WebUSB/browser-side capture paths). */
export function openIngest(sessionId: string): WebSocket {
  return new WebSocket(`${WS_BASE}/ws/ingest/${sessionId}`);
}

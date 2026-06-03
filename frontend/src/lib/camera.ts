// Built-in RGB camera access via getUserMedia (Android / iOS / desktop).

export interface CameraDevice {
  deviceId: string;
  label: string;
  facing?: 'user' | 'environment';
}

export async function listCameras(): Promise<CameraDevice[]> {
  if (!navigator.mediaDevices?.enumerateDevices) return [];
  const devices = await navigator.mediaDevices.enumerateDevices();
  return devices
    .filter((d) => d.kind === 'videoinput')
    .map((d) => ({ deviceId: d.deviceId, label: d.label || 'Cámara' }));
}

/**
 * Start a camera stream. `facing` selects front ('user') or back ('environment').
 * On iOS Safari the call must be triggered by a user gesture and over HTTPS.
 */
export async function startCamera(
  facing: 'user' | 'environment' = 'environment',
  deviceId?: string
): Promise<MediaStream> {
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error('getUserMedia no soportado en este navegador');
  }
  const constraints: MediaStreamConstraints = {
    audio: false,
    video: deviceId
      ? { deviceId: { exact: deviceId } }
      : { facingMode: { ideal: facing }, width: { ideal: 1280 }, height: { ideal: 720 } },
  };
  return navigator.mediaDevices.getUserMedia(constraints);
}

export function stopStream(stream: MediaStream | null): void {
  stream?.getTracks().forEach((t) => t.stop());
}

/** Grab a single frame from a video element into a canvas (for snapshots/fusion). */
export function grabFrame(video: HTMLVideoElement, canvas: HTMLCanvasElement): void {
  const ctx = canvas.getContext('2d');
  if (!ctx || !video.videoWidth) return;
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
}

'use client';

import { useEffect, useRef } from 'react';
import type { DisplayMode, ProcessedFrame } from '@/lib/thermal';
import type { FusionState } from './FusionControls';

interface Props {
  mode: DisplayMode;
  frame: ProcessedFrame | null;
  rgbVideo: HTMLVideoElement | null;
  fusion: FusionState;
}

/**
 * Renders the current view onto a canvas:
 *  - rgb     : the built-in camera video
 *  - thermal : the server-colorized PNG
 *  - fusion  : thermal alpha-blended over RGB with alignment/scale/rotation
 * The server already draws hotspot/coldspot/crosshair markers into the thermal PNG.
 */
export function ThermalCanvas({ mode, frame, rgbVideo, fusion }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const thermalImg = useRef<HTMLImageElement | null>(null);

  // decode the latest thermal PNG once per frame
  useEffect(() => {
    if (!frame?.image_png_b64) return;
    const img = new Image();
    img.src = `data:image/png;base64,${frame.image_png_b64}`;
    img.onload = () => {
      thermalImg.current = img;
    };
  }, [frame?.seq, frame?.image_png_b64]);

  useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext('2d');
      if (canvas && ctx) {
        const W = (canvas.width = canvas.clientWidth);
        const H = (canvas.height = canvas.clientHeight);
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = '#0b1020';
        ctx.fillRect(0, 0, W, H);

        const drawRgb = () => {
          if (rgbVideo && rgbVideo.videoWidth) {
            const s = Math.min(W / rgbVideo.videoWidth, H / rgbVideo.videoHeight);
            const w = rgbVideo.videoWidth * s;
            const h = rgbVideo.videoHeight * s;
            ctx.drawImage(rgbVideo, (W - w) / 2, (H - h) / 2, w, h);
          }
        };
        const drawThermal = (alpha = 1) => {
          const img = thermalImg.current;
          if (!img) return;
          ctx.save();
          ctx.globalAlpha = alpha;
          ctx.translate(W / 2 + fusion.dx, H / 2 + fusion.dy);
          ctx.rotate((fusion.rotation * Math.PI) / 180);
          const s = Math.min(W / img.width, H / img.height) * fusion.scale;
          const w = img.width * s;
          const h = img.height * s;
          ctx.imageSmoothingEnabled = true;
          ctx.drawImage(img, -w / 2, -h / 2, w, h);
          ctx.restore();
        };

        if (mode === 'rgb') drawRgb();
        else if (mode === 'thermal') drawThermal(1);
        else {
          drawRgb();
          drawThermal(fusion.alpha);
        }
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [mode, rgbVideo, fusion]);

  return (
    <div className="relative aspect-square w-full overflow-hidden rounded-2xl border border-white/10 bg-black">
      <canvas ref={canvasRef} className="h-full w-full" />
      {!frame && mode !== 'rgb' && (
        <div className="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
          Esperando frames térmicos…
        </div>
      )}
    </div>
  );
}

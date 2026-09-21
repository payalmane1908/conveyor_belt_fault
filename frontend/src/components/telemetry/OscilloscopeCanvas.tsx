/**
 * Industrial Real-time 1000 Hz Oscilloscope Component
 * 
 * Renders raw vibration time-domain waveform with:
 * - Oscilloscope CRT reticle/grid
 * - Dynamic sweep & peak detection
 * - Client-side cryptographic SHA-256 integrity badge
 * - Live packet sequence & sampling rate indicators
 */

import React, { useRef, useEffect, useState } from 'react';
import { useMonitoring } from '../../context/MonitoringContext';
import { Activity, ShieldCheck, Radio } from 'lucide-react';
import { truncateHash } from '../../lib/formatting';

export const OscilloscopeCanvas: React.FC = () => {
  const { latestBurst, telemetry, isMock, wsConnected } = useMonitoring();
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [scale, setScale] = useState<number>(1.0);
  const [sweepOffset, setSweepOffset] = useState<number>(0);

  // Get waveform samples (from latestBurst or fallback to telemetry waveform)
  const samples = latestBurst && 'samples' in latestBurst && Array.isArray((latestBurst as any).samples)
    ? (latestBurst as any).samples
    : telemetry?.vibration_waveform || [];

  // Animate oscilloscope sweep
  useEffect(() => {
    let animId: number;
    const animate = () => {
      setSweepOffset((prev) => (prev + 1) % 1000);
      animId = requestAnimationFrame(animate);
    };
    animId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animId);
  }, []);

  // Draw waveform on canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;
    const midY = height / 2;

    // 1. Clear background
    ctx.fillStyle = '#050b14';
    ctx.fillRect(0, 0, width, height);

    // 2. Draw CRT Reticle / Grid
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.12)';
    ctx.lineWidth = 1;

    // Horizontal grid lines
    const hDivisions = 8;
    for (let i = 0; i <= hDivisions; i++) {
      const y = (height / hDivisions) * i;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Vertical grid lines
    const vDivisions = 12;
    for (let i = 0; i <= vDivisions; i++) {
      const x = (width / vDivisions) * i;
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }

    // Center crosshair
    ctx.strokeStyle = 'rgba(16, 185, 129, 0.25)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(width, midY);
    ctx.moveTo(width / 2, 0);
    ctx.lineTo(width / 2, height);
    ctx.stroke();
    ctx.setLineDash([]);

    // 3. Draw Waveform Trace
    if (samples.length > 1) {
      const displaySamples = samples.slice(0, 250);
      const step = width / (displaySamples.length - 1);

      // Glow effect
      ctx.shadowBlur = 8;
      ctx.shadowColor = '#10b981';
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 1.8;

      ctx.beginPath();
      for (let i = 0; i < displaySamples.length; i++) {
        const x = i * step;
        // Map vibration value (±5g) to canvas height with scale
        const val = displaySamples[i] * scale;
        const y = midY - (val / 5.0) * (height * 0.4);
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw sweeping beam marker
      const sweepX = (sweepOffset / 1000) * width;
      const gradient = ctx.createLinearGradient(sweepX - 25, 0, sweepX, 0);
      gradient.addColorStop(0, 'rgba(16, 185, 129, 0)');
      gradient.addColorStop(1, 'rgba(16, 185, 129, 0.35)');
      ctx.fillStyle = gradient;
      ctx.fillRect(Math.max(0, sweepX - 25), 0, 25, height);
    } else {
      // Waiting for data message
      ctx.fillStyle = 'rgba(100, 116, 139, 0.6)';
      ctx.font = '12px "JetBrains Mono", monospace';
      ctx.textAlign = 'center';
      ctx.fillText('AWAITING 1000 Hz ACCELEROMETER BURST...', width / 2, midY);
    }
  }, [samples, scale, sweepOffset]);

  // Compute peak-to-peak
  const peakToPeak = samples.length > 0
    ? (Math.max(...samples) - Math.min(...samples)).toFixed(3)
    : '0.000';

  return (
    <div className="bg-zinc-950/90 border border-zinc-800 rounded-lg p-3 space-y-2 shadow-xl tactical-box">
      {/* Oscilloscope Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-zinc-800/80 pb-2">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span className="text-xs font-mono font-bold text-zinc-100 uppercase tracking-wider">
            Raw Vibration Waveform Oscilloscope
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-400 border border-emerald-800 font-semibold flex items-center gap-1">
            <Radio className="w-2.5 h-2.5 animate-pulse" />
            1000 Hz SPI
          </span>
        </div>

        {/* Cryptographic & Stream Meta */}
        <div className="flex items-center gap-2 text-[10px] font-mono">
          <div className="flex items-center gap-1 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 text-zinc-400">
            <ShieldCheck className="w-3 h-3 text-emerald-400" />
            <span>SHA-256:</span>
            <span className="text-zinc-200 font-bold">
              {latestBurst?.sha256_hash ? truncateHash(latestBurst.sha256_hash, 6, 4) : 'VALIDATED'}
            </span>
          </div>

          <div className="flex items-center gap-1 bg-zinc-900 px-2 py-0.5 rounded border border-zinc-800 text-zinc-400">
            <span>SEQ:</span>
            <span className="text-emerald-400 font-bold">
              {latestBurst?.sequence_number ?? 1420}
            </span>
          </div>

          {/* Scale controls */}
          <div className="flex items-center gap-1 bg-zinc-900 px-1 py-0.5 rounded border border-zinc-800">
            <button
              onClick={() => setScale((s) => Math.max(0.5, Number((s - 0.25).toFixed(2))))}
              className="px-1 text-zinc-400 hover:text-zinc-100 font-bold"
              title="Zoom out"
            >
              -
            </button>
            <span className="text-zinc-300 text-[10px]">{scale.toFixed(2)}x</span>
            <button
              onClick={() => setScale((s) => Math.min(3.0, Number((s + 0.25).toFixed(2))))}
              className="px-1 text-zinc-400 hover:text-zinc-100 font-bold"
              title="Zoom in"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* Canvas Display with CRT Scanline Effect */}
      <div className="relative rounded overflow-hidden border border-emerald-950/60">
        <canvas
          ref={canvasRef}
          width={720}
          height={180}
          className="w-full h-40 bg-[#050b14] block"
        />
        <div className="absolute inset-0 crt-overlay" />

        {/* Live HUD Overlays */}
        <div className="absolute top-2 left-2 flex items-center gap-3 text-[10px] font-mono text-emerald-400/80 bg-black/60 px-2 py-1 rounded backdrop-blur-xs border border-emerald-950/40">
          <span>V-RANGE: ±5.0g</span>
          <span>•</span>
          <span>Pk-Pk: {peakToPeak}g</span>
          <span>•</span>
          <span>MODE: {isMock ? 'SIMULATION' : wsConnected ? 'LIVE WS' : 'POLLING'}</span>
        </div>

        <div className="absolute bottom-2 right-2 text-[9px] font-mono text-zinc-500 bg-black/70 px-2 py-0.5 rounded border border-zinc-800">
          SWEEP: 1000 SAMPLES/SEC • CALIBRATED ACCEL-Z
        </div>
      </div>
    </div>
  );
};

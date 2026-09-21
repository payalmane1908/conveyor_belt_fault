/**
 * Circular Industrial Health Gauge
 * 
 * Renders an SVG radial dial with:
 * - High-contrast neon arc (color mapped by risk level)
 * - Numeric score readout (0–100)
 * - Band thresholds (NORMAL, WATCH, WARNING, CRITICAL)
 * - Honest zero-mock state when missing
 */

import React from 'react';
import { interpretHealthScore } from '../../lib/health';
import { Clock } from 'lucide-react';

interface HealthGaugeProps {
  score?: number | null;
  size?: number;
}

export const HealthGauge: React.FC<HealthGaugeProps> = ({ score, size = 180 }) => {
  const healthInfo = interpretHealthScore(score);
  const hasScore = score !== undefined && score !== null && !isNaN(score);

  const radius = (size - 24) / 2;
  const circumference = 2 * Math.PI * radius;
  // Use a 270-degree arc for industrial meter feel
  const arcPercentage = 0.75;
  const strokeLength = circumference * arcPercentage;

  const validScore = hasScore ? Math.min(100, Math.max(0, score)) : 0;
  const progressLength = (validScore / 100) * strokeLength;
  const strokeDashoffset = strokeLength - progressLength;

  // Arc color based on score
  let arcColor = '#10b981'; // emerald
  let glowColor = 'rgba(16, 185, 129, 0.4)';
  if (validScore < 50) {
    arcColor = '#ef4444'; // red
    glowColor = 'rgba(239, 68, 68, 0.4)';
  } else if (validScore < 75) {
    arcColor = '#f97316'; // orange
    glowColor = 'rgba(249, 115, 22, 0.4)';
  } else if (validScore < 90) {
    arcColor = '#eab308'; // yellow/amber
    glowColor = 'rgba(234, 179, 8, 0.4)';
  }

  return (
    <div className="flex flex-col items-center justify-center p-2 relative select-none">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          className="transform -rotate-135 origin-center"
          style={{ overflow: 'visible' }}
        >
          {/* Background Track Arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="#18181b"
            strokeWidth={10}
            strokeDasharray={`${strokeLength} ${circumference}`}
            strokeLinecap="round"
          />

          {/* Active Progress Arc */}
          {hasScore && (
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              stroke={arcColor}
              strokeWidth={10}
              strokeDasharray={`${strokeLength} ${circumference}`}
              strokeDashoffset={strokeDashoffset}
              strokeLinecap="round"
              style={{
                transition: 'stroke-dashoffset 0.8s ease-out, stroke 0.4s ease',
                filter: `drop-shadow(0 0 6px ${glowColor})`
              }}
            />
          )}
        </svg>

        {/* Center Digital Display */}
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          {hasScore ? (
            <>
              <div
                className="text-3xl font-mono font-black tracking-tight"
                style={{ color: arcColor }}
              >
                {score.toFixed(1)}
              </div>
              <div className="text-[10px] font-mono text-zinc-500 uppercase tracking-widest -mt-0.5">
                HEALTH INDEX
              </div>
              <div
                className="text-[10px] font-mono font-bold mt-1 px-1.5 py-0.5 rounded border"
                style={{
                  color: arcColor,
                  borderColor: `${arcColor}40`,
                  backgroundColor: `${arcColor}15`
                }}
              >
                {healthInfo.label}
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center text-zinc-500 space-y-1">
              <Clock className="w-5 h-5 text-zinc-600" />
              <span className="text-[11px] font-mono font-semibold">WAITING</span>
              <span className="text-[9px] text-zinc-600">FOR DATA</span>
            </div>
          )}
        </div>
      </div>

      {/* Threshold Legend Bar */}
      <div className="w-full max-w-[200px] mt-1 pt-2 border-t border-zinc-900 grid grid-cols-4 gap-1 text-[9px] font-mono text-center">
        <div className="text-red-400 bg-red-950/40 rounded py-0.5 border border-red-900/40">
          &lt;50
        </div>
        <div className="text-orange-400 bg-orange-950/40 rounded py-0.5 border border-orange-900/40">
          50-74
        </div>
        <div className="text-amber-400 bg-amber-950/40 rounded py-0.5 border border-amber-900/40">
          75-89
        </div>
        <div className="text-emerald-400 bg-emerald-950/40 rounded py-0.5 border border-emerald-900/40">
          90-100
        </div>
      </div>
    </div>
  );
};

/**
 * Semicircular Rainbow Tick Health Meter
 * 
 * Faithfully matches the speedometer-style tick gauge from reference screenshot media_1789973387545.jpg:
 * - Semicircle arc composed of distinct radial tick marks
 * - Color gradient flowing: Green (nominal) -> Yellow -> Orange -> Red (critical)
 * - Sharp royal blue pivot indicator needle indicating current health or load index
 */

import React from 'react';

interface RainbowHealthMeterProps {
  score?: number | null; // 0 to 100
  size?: number;
}

export const RainbowHealthMeter: React.FC<RainbowHealthMeterProps> = ({
  score = 96,
  size = 180
}) => {
  const validScore = score !== null && score !== undefined && !isNaN(score)
    ? Math.min(100, Math.max(0, score))
    : 0;

  // Total ticks around the 180-degree semicircle (from angle 180° to 0°/360°)
  const tickCount = 38;
  const cx = size / 2;
  const cy = size * 0.75;
  const outerR = size * 0.42;
  const innerR = size * 0.32;

  // Colors transitioning from green -> yellow -> red
  const ticks = React.useMemo(() => {
    const items = [];
    for (let i = 0; i < tickCount; i++) {
      const frac = i / (tickCount - 1); // 0 (left) to 1 (right)
      // Angle in radians: from PI (180 deg, left) down to 0 (right)
      const angle = Math.PI - frac * Math.PI;

      const x1 = cx + innerR * Math.cos(angle);
      const y1 = cy - innerR * Math.sin(angle);
      const x2 = cx + outerR * Math.cos(angle);
      const y2 = cy - outerR * Math.sin(angle);

      // Color computation
      let color = '#10b981'; // green
      if (frac > 0.75) {
        color = '#ef4444'; // red
      } else if (frac > 0.55) {
        color = '#f97316'; // orange
      } else if (frac > 0.35) {
        color = '#f59e0b'; // amber/yellow
      } else if (frac > 0.15) {
        color = '#84cc16'; // lime
      }

      items.push({ x1, y1, x2, y2, color, frac });
    }
    return items;
  }, [cx, cy, innerR, outerR, tickCount]);

  // Needle angle: mapped from score (0 = far left, 100 = far right)
  const needleFrac = validScore / 100;
  const needleAngle = Math.PI - needleFrac * Math.PI;
  const needleLength = outerR * 0.95;
  const nx = cx + needleLength * Math.cos(needleAngle);
  const ny = cy - needleLength * Math.sin(needleAngle);

  return (
    <div className="flex flex-col items-center justify-center select-none">
      <svg
        width={size}
        height={size * 0.82}
        viewBox={`0 0 ${size} ${size * 0.82}`}
        className="overflow-visible"
      >
        {/* Ticks */}
        {ticks.map((t, idx) => (
          <line
            key={idx}
            x1={t.x1}
            y1={t.y1}
            x2={t.x2}
            y2={t.y2}
            stroke={t.color}
            strokeWidth={2.5}
            strokeLinecap="round"
            className="transition-all duration-300"
          />
        ))}

        {/* Needle Line (Royal Blue) */}
        <line
          x1={cx}
          y1={cy}
          x2={nx}
          y2={ny}
          stroke="#0047ba"
          strokeWidth={3}
          strokeLinecap="round"
          className="transition-all duration-500 ease-out"
        />

        {/* Pivot Center Point */}
        <circle
          cx={cx}
          cy={cy}
          r={5.5}
          fill="#0047ba"
          stroke="#ffffff"
          strokeWidth={2}
        />
      </svg>
    </div>
  );
};

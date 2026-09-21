/**
 * Joint Health Interpretation & Scoring Helpers
 * 
 * Configurable engineering application thresholds (matches Phase 3 backend settings).
 * NOT universal industrial standards.
 */

import type { StatusLevel } from '../types';

export interface HealthBand {
  min: number;
  max: number;
  label: string;
  level: StatusLevel | 'WATCH';
  description: string;
}

export const HEALTH_BANDS: HealthBand[] = [
  { min: 90, max: 100, label: 'NORMAL', level: 'NORMAL', description: 'Splice baseline integrity nominal' },
  { min: 75, max: 89.9, label: 'WATCH', level: 'WATCH', description: 'Early vibration deviation detected' },
  { min: 50, max: 74.9, label: 'WARNING', level: 'WARNING', description: 'Sustained abnormal impact / looseness' },
  { min: 0, max: 49.9, label: 'CRITICAL', level: 'CRITICAL', description: 'Imminent splice damage or severe shock' },
];

export function interpretHealthScore(score: number | undefined | null): {
  level: StatusLevel | 'WATCH' | 'WAITING';
  label: string;
  description: string;
  colorClass: string;
} {
  if (score === undefined || score === null || isNaN(score)) {
    return {
      level: 'WAITING',
      label: 'WAITING FOR DATA',
      description: 'Insufficient observation bursts to compute health score',
      colorClass: 'text-zinc-500'
    };
  }

  if (score >= 90) {
    return {
      level: 'NORMAL',
      label: 'NORMAL HEALTH',
      description: 'Splice baseline integrity nominal (90-100)',
      colorClass: 'text-emerald-400'
    };
  } else if (score >= 75) {
    return {
      level: 'WATCH',
      label: 'WATCH ADVISORY',
      description: 'Early vibration deviation detected (75-89)',
      colorClass: 'text-amber-400'
    };
  } else if (score >= 50) {
    return {
      level: 'WARNING',
      label: 'WARNING STATE',
      description: 'Sustained abnormal impact or looseness (50-74)',
      colorClass: 'text-orange-400'
    };
  } else {
    return {
      level: 'CRITICAL',
      label: 'CRITICAL INTEGRITY',
      description: 'Imminent splice failure or high-amplitude shock (<50)',
      colorClass: 'text-red-400'
    };
  }
}

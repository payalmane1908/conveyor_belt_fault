/**
 * Centralized Industrial Status Logic & Alarm Limits
 * 
 * Strict rule: All status calculations are pure, testable, and centralized here.
 * Never communicate status through colour alone: ALWAYS use icon + text + colour.
 */

import type { StatusLevel } from '../types';

export interface AlarmLimit {
  warning: number;
  critical: number;
  unit: string;
  name: string;
}

export interface PlantAlarmLimits {
  vibration_rms: AlarmLimit; // g or m/s²
  temperature: AlarmLimit;   // °C
  acoustic_db: AlarmLimit;   // dB
  load: AlarmLimit;          // tonnes / %
  rpm: AlarmLimit;           // RPM
  tension: AlarmLimit;       // kN or N
  tracking_offset_mm: AlarmLimit; // mm
  crest_factor: AlarmLimit;  // ratio
  kurtosis: AlarmLimit;      // Fisher excess
}

/**
 * Plant Engineering Threshold Defaults
 * Note: Labeled as engineering application thresholds, calibrated per machine.
 */
export const DEFAULT_ALARM_LIMITS: PlantAlarmLimits = {
  vibration_rms: {
    warning: 3.5,
    critical: 5.0,
    unit: 'g',
    name: 'Vibration RMS'
  },
  temperature: {
    warning: 65.0,
    critical: 85.0,
    unit: '°C',
    name: 'Bearing Temperature'
  },
  acoustic_db: {
    warning: 85.0,
    critical: 95.0,
    unit: 'dB',
    name: 'Acoustic Emission'
  },
  load: {
    warning: 85.0,
    critical: 95.0,
    unit: '%',
    name: 'Belt Load'
  },
  rpm: {
    warning: 1350.0,
    critical: 1450.0,
    unit: 'RPM',
    name: 'Drive Speed'
  },
  tension: {
    warning: 160.0,
    critical: 200.0,
    unit: 'N',
    name: 'Take-up Tension'
  },
  tracking_offset_mm: {
    warning: 25.0,
    critical: 40.0,
    unit: 'mm',
    name: 'Tracking Drift'
  },
  crest_factor: {
    warning: 3.0,
    critical: 4.0,
    unit: 'ratio',
    name: 'Crest Factor'
  },
  kurtosis: {
    warning: 2.0,
    critical: 3.0,
    unit: 'Fisher',
    name: 'Kurtosis'
  }
};

/**
 * Evaluates a numeric value against warning and critical limits.
 * Returns null if value is undefined or null (strictly preserving zero-fabrication).
 */
export function evaluateLimit(value: number | undefined | null, limit: AlarmLimit): StatusLevel | null {
  if (value === undefined || value === null || isNaN(value)) {
    return null;
  }
  if (value >= limit.critical) {
    return 'CRITICAL';
  }
  if (value >= limit.warning) {
    return 'WARNING';
  }
  return 'NORMAL';
}

export interface StatusPresentation {
  level: StatusLevel | 'WAITING' | 'UNAVAILABLE';
  label: string;
  badgeBg: string;
  badgeBorder: string;
  badgeText: string;
  iconName: 'check-circle' | 'alert-triangle' | 'alert-octagon' | 'clock' | 'help-circle' | 'eye';
  ringColor: string;
}

export function getStatusPresentation(level: string | null | undefined): StatusPresentation {
  const norm = level ? String(level).toUpperCase().trim() : '';

  switch (norm) {
    case 'CRITICAL':
      return {
        level: 'CRITICAL',
        label: 'CRITICAL',
        badgeBg: 'bg-red-950/80',
        badgeBorder: 'border-red-600',
        badgeText: 'text-red-400',
        iconName: 'alert-octagon',
        ringColor: 'ring-red-500'
      };
    case 'WARNING':
      return {
        level: 'WARNING',
        label: 'WARNING',
        badgeBg: 'bg-orange-950/80',
        badgeBorder: 'border-orange-600',
        badgeText: 'text-orange-400',
        iconName: 'alert-triangle',
        ringColor: 'ring-orange-500'
      };
    case 'WATCH':
      return {
        level: 'WATCH',
        label: 'WATCH',
        badgeBg: 'bg-amber-950/80',
        badgeBorder: 'border-amber-600',
        badgeText: 'text-amber-400',
        iconName: 'alert-triangle',
        ringColor: 'ring-amber-500'
      };
    case 'NORMAL':
      return {
        level: 'NORMAL',
        label: 'NORMAL',
        badgeBg: 'bg-emerald-950/80',
        badgeBorder: 'border-emerald-600',
        badgeText: 'text-emerald-400',
        iconName: 'check-circle',
        ringColor: 'ring-emerald-500'
      };
    case 'UNAVAILABLE':
      return {
        level: 'UNAVAILABLE',
        label: 'NOT AVAILABLE',
        badgeBg: 'bg-zinc-900',
        badgeBorder: 'border-zinc-700',
        badgeText: 'text-zinc-400',
        iconName: 'help-circle',
        ringColor: 'ring-zinc-600'
      };
    case 'WAITING':
    default:
      return {
        level: 'WAITING',
        label: 'WAITING FOR DATA',
        badgeBg: 'bg-zinc-900',
        badgeBorder: 'border-zinc-700',
        badgeText: 'text-zinc-500',
        iconName: 'clock',
        ringColor: 'ring-zinc-700'
      };
  }
}

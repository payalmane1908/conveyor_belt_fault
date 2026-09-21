/**
 * Phase 1 Core Test Suite
 * 
 * Verifies:
 * 1. Status classification
 * 2. Alarm limits evaluation
 * 3. Undefined telemetry handling (undefined != zero)
 * 4. Mock scenarios integrity
 * 5. Health score display & interpretation logic
 */

import { describe, it, expect } from 'vitest';
import {
  evaluateLimit,
  DEFAULT_ALARM_LIMITS,
  getStatusPresentation
} from '../lib/status';
import { interpretHealthScore, HEALTH_BANDS } from '../lib/health';
import { formatValue, formatValueWithUnit } from '../lib/formatting';
import { MOCK_SCENARIOS } from '../services/mock';
import type { MockScenario } from '../services/mock';

describe('1. Status Classification & Alarm Limits', () => {
  it('correctly classifies nominal values as NORMAL', () => {
    const status = evaluateLimit(1.5, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(status).toBe('NORMAL');
  });

  it('correctly classifies elevated values as WARNING', () => {
    // warning threshold is 3.5
    const status = evaluateLimit(3.8, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(status).toBe('WARNING');
  });

  it('correctly classifies severe values as CRITICAL', () => {
    // critical threshold is 5.0
    const status = evaluateLimit(5.2, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(status).toBe('CRITICAL');
  });

  it('provides icon, text, and colour presentation for all status levels', () => {
    const criticalPres = getStatusPresentation('CRITICAL');
    expect(criticalPres.label).toBe('CRITICAL');
    expect(criticalPres.iconName).toBe('alert-octagon');
    expect(criticalPres.badgeText).toContain('text-red');

    const warningPres = getStatusPresentation('WARNING');
    expect(warningPres.label).toBe('WARNING');
    expect(warningPres.iconName).toBe('alert-triangle');

    const normalPres = getStatusPresentation('NORMAL');
    expect(normalPres.label).toBe('NORMAL');
    expect(normalPres.iconName).toBe('check-circle');
  });
});

describe('2. Undefined Telemetry Handling (undefined != zero)', () => {
  it('never substitutes undefined with zero or arbitrary values in evaluateLimit', () => {
    const resultUndefined = evaluateLimit(undefined, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(resultUndefined).toBeNull();

    const resultNull = evaluateLimit(null, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(resultNull).toBeNull();

    const resultNaN = evaluateLimit(NaN, DEFAULT_ALARM_LIMITS.vibration_rms);
    expect(resultNaN).toBeNull();
  });

  it('presents "WAITING FOR DATA" for undefined status presentation', () => {
    const pres = getStatusPresentation(null);
    expect(pres.label).toBe('WAITING FOR DATA');
    expect(pres.iconName).toBe('clock');
  });

  it('formats undefined numbers as "Waiting for data" instead of 0.00', () => {
    expect(formatValue(undefined)).toBe('Waiting for data');
    expect(formatValue(null)).toBe('Waiting for data');
    expect(formatValueWithUnit(undefined, 'g')).toBe('Waiting for data');
    expect(formatValue(0)).toBe('0.00'); // zero is genuinely 0.00, not waiting
  });
});

describe('3. Health Score Display Logic', () => {
  it('returns WAITING state when score is undefined or null', () => {
    const resUndefined = interpretHealthScore(undefined);
    expect(resUndefined.level).toBe('WAITING');
    expect(resUndefined.label).toBe('WAITING FOR DATA');

    const resNull = interpretHealthScore(null);
    expect(resNull.level).toBe('WAITING');
  });

  it('defines 4 standard health interpretation bands', () => {
    expect(HEALTH_BANDS.length).toBe(4);
    expect(HEALTH_BANDS[0].label).toBe('NORMAL');
  });

  it('classifies score 90-100 as NORMAL', () => {
    const res = interpretHealthScore(95.5);
    expect(res.level).toBe('NORMAL');
    expect(res.label).toBe('NORMAL HEALTH');
  });

  it('classifies score 75-89.9 as WATCH', () => {
    const res = interpretHealthScore(82.0);
    expect(res.level).toBe('WATCH');
    expect(res.label).toBe('WATCH ADVISORY');
  });

  it('classifies score 50-74.9 as WARNING', () => {
    const res = interpretHealthScore(65.0);
    expect(res.level).toBe('WARNING');
    expect(res.label).toBe('WARNING STATE');
  });

  it('classifies score < 50 as CRITICAL', () => {
    const res = interpretHealthScore(35.0);
    expect(res.level).toBe('CRITICAL');
    expect(res.label).toBe('CRITICAL INTEGRITY');
  });
});

describe('4. Mock Scenarios Coherence', () => {
  const scenarios: MockScenario[] = [
    'healthy',
    'warning',
    'critical',
    'bearing_fault',
    'pulley_fault',
    'belt_slippage',
    'joint_rupture'
  ];

  it('defines all 7 required scenarios with valid coherent telemetry', () => {
    scenarios.forEach((sc) => {
      const data = MOCK_SCENARIOS[sc];
      expect(data).toBeDefined();
      expect(data.telemetry).toBeDefined();
      expect(data.diagnosis).toBeDefined();
      expect(data.dspAnalysis).toBeDefined();
      expect(data.systemStatus).toBeDefined();

      // Check overall status matches scenario severity
      if (sc === 'healthy') {
        expect(data.telemetry.overall_status).toBe('NORMAL');
      } else if (sc === 'critical' || sc === 'joint_rupture') {
        expect(data.telemetry.overall_status).toBe('CRITICAL');
      } else {
        expect(data.telemetry.overall_status).toBe('WARNING');
      }

      // Check waveform exists and is non-empty
      expect(data.telemetry.vibration_waveform).toBeDefined();
      expect(data.telemetry.vibration_waveform!.length).toBeGreaterThan(0);
    });
  });
});

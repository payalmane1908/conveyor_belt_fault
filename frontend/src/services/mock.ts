/**
 * Centralized Mock System
 * 
 * Strict rule: ALL mock data resides here. Never scatter fake data in UI components.
 * Scenarios:
 * - healthy
 * - warning
 * - critical
 * - bearing_fault
 * - pulley_fault
 * - belt_slippage
 * - joint_rupture
 * 
 * Consistent state updates across Control Room, Joint Passport, Diagnosis, and Alerts.
 */

import type {
  Telemetry,
  Joint,
  AlertEvent,
  BurstDspAnalysis,
  SystemStatusResponse,
  ExplainableDiagnosis
} from '../types';

export type MockScenario =
  | 'healthy'
  | 'warning'
  | 'critical'
  | 'bearing_fault'
  | 'pulley_fault'
  | 'belt_slippage'
  | 'joint_rupture';

export interface MockScenarioData {
  name: string;
  label: string;
  telemetry: Telemetry;
  joints: Joint[];
  diagnosis: ExplainableDiagnosis;
  alerts: AlertEvent[];
  dspAnalysis: BurstDspAnalysis;
  systemStatus: SystemStatusResponse;
}

// Generate realistic sinusoidal waveforms
function generateWaveform(baseFreq: number, sampleCount: number, noiseAmp: number, shockAmp = 0): number[] {
  const samples: number[] = [];
  const dt = 1.0 / 1000.0; // 1000 Hz
  for (let i = 0; i < sampleCount; i++) {
    const t = i * dt;
    let s = Math.sin(2 * Math.PI * baseFreq * t);
    // Gaussian-ish noise
    const noise = (Math.random() + Math.random() + Math.random() - 1.5) * noiseAmp;
    s += noise;
    // Periodic shock/impact for faults
    if (shockAmp > 0 && i % 120 === 0) {
      s += (Math.random() > 0.5 ? 1 : -1) * shockAmp;
    }
    samples.push(Number(s.toFixed(4)));
  }
  return samples;
}

export const MOCK_SCENARIOS: Record<MockScenario, MockScenarioData> = {
  healthy: {
    name: 'healthy',
    label: 'Nominal Baseline (Healthy)',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1200,
      temperature: 42.5,
      load: 64.0,
      vibration: 1.06,
      acoustic_db: 72.4,
      tension: 110,
      tracking_offset_mm: 3.2,
      belt_health: 95.5,
      overall_status: 'NORMAL',
      fault_type: 'NONE (NOMINAL)',
      fault_confidence: 96.4,
      health_prediction: 'NORMAL OPERATION',
      health_confidence: 98.2,
      sensor_prediction: 'NOMINAL',
      image_prediction: 'NOMINAL_JOINT',
      confidence: 97.0,
      recommendation: 'Continue standard scheduled observation cycle.',
      explanation: 'Vibration RMS, crest factor, and kurtosis are within learned rolling baseline bounds.',
      vibration_waveform: generateWaveform(50, 100, 0.2, 0)
    },
    joints: [
      {
        id: 'joint-001',
        joint_code: 'J-01',
        belt_id: 'BELT-01',
        physical_position_meters: 120.0,
        identifier_type: 'OPTICAL',
        identifier_token: 'OPT-J01',
        splice_type: 'Finger Splice (Hot Vulcanized)',
        installation_date: '2026-01-15',
        current_risk: 'NORMAL',
        last_passage_timestamp_utc: new Date().toISOString(),
        consecutive_abnormal_count: 0,
        total_revolutions_count: 812
      },
      {
        id: 'joint-002',
        joint_code: 'J-02',
        belt_id: 'BELT-01',
        physical_position_meters: 250.0,
        identifier_type: 'OPTICAL',
        identifier_token: 'OPT-J02',
        splice_type: 'Finger Splice (Hot Vulcanized)',
        installation_date: '2026-01-15',
        current_risk: 'NORMAL',
        last_passage_timestamp_utc: new Date(Date.now() - 30000).toISOString(),
        consecutive_abnormal_count: 0,
        total_revolutions_count: 812
      }
    ],
    diagnosis: {
      faultType: 'None (Nominal Baseline)',
      faultConfidence: 96.4,
      healthPrediction: 'NORMAL_OPERATION',
      healthConfidence: 98.2,
      sensorPrediction: 'NORMAL',
      imagePrediction: 'Belt Joint (Intact)',
      detectionMode: 'SENSOR_VISION_AGREEMENT',
      evidenceList: [
        { name: 'Vibration RMS', value: 1.06, unit: 'g', status: 'NORMAL', baselineMedian: 1.06, deviation: '0.0σ', source: 'ADXL345 (SPI)' },
        { name: 'Crest Factor', value: 1.52, unit: 'ratio', status: 'NORMAL', baselineMedian: 1.52, deviation: '+0.1σ', source: 'DSP Analyzer' },
        { name: 'Drive Speed', value: 1200, unit: 'RPM', status: 'NORMAL', source: 'Drive Inverter' },
        { name: 'Take-up Tension', value: 110, unit: 'N', status: 'NORMAL', source: 'Pretension Rig' }
      ],
      explanation: 'All extracted DSP features conform to learned non-anomalous operating distribution.',
      recommendedAction: 'Continue standard scheduled monitoring cycle.',
      timestamp: new Date().toISOString(),
      jointId: 'joint-001'
    },
    alerts: [],
    dspAnalysis: {
      burst_id: 'mock-burst-healthy-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 1.062,
        peak: 1.624,
        peak_to_peak: 3.12,
        crest_factor: 1.529,
        kurtosis_fisher: -1.498,
        kurtosis_convention: 'Fisher/excess (Gaussian baseline ≈ 0)',
        skewness: 0.021,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 50.0,
        dominant_amplitude: 0.98,
        spectral_centroid_hz: 52.4,
        spectral_energy: 124.5,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, (_, i) => (i === 10 ? 0.98 : Math.random() * 0.05))
      },
      engineering_thresholds: {
        label: 'engineering_threshold — must be calibrated per plant/machine class',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health & Failure Prevention System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [
        {
          stream_id: 'accel-z',
          device_id: 'esp32-node-01',
          last_sequence_number: 1420,
          total_packets_received: 1420,
          dropped_packets_count: 0,
          last_hardware_timestamp_us: 142000000,
          rollover_count: 0,
          last_seen_utc: new Date().toISOString()
        }
      ],
      total_bursts_persisted: 1420,
      server_time_utc: new Date().toISOString()
    }
  },

  warning: {
    name: 'warning',
    label: 'Vibration Elevation (Warning)',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1200,
      temperature: 68.2,
      load: 78.0,
      vibration: 3.82,
      acoustic_db: 86.5,
      tension: 110,
      tracking_offset_mm: 12.4,
      belt_health: 72.0,
      overall_status: 'WARNING',
      fault_type: 'HARMONIC_LOOSENESS',
      fault_confidence: 84.5,
      health_prediction: 'WATCH ADVISORY',
      health_confidence: 86.0,
      sensor_prediction: 'ANOMALOUS_HARMONICS',
      image_prediction: 'Belt Joint (Minor Wear)',
      confidence: 85.0,
      recommendation: 'Inspect splice fasteners on Joint J-01 during next scheduled window.',
      explanation: 'Multi-harmonic resonance detected at 2x and 3x line frequency with sustained RMS elevation.',
      vibration_waveform: generateWaveform(50, 100, 0.4, 1.2)
    },
    joints: [
      {
        id: 'joint-001',
        joint_code: 'J-01',
        belt_id: 'BELT-01',
        physical_position_meters: 120.0,
        identifier_type: 'OPTICAL',
        identifier_token: 'OPT-J01',
        splice_type: 'Finger Splice (Hot Vulcanized)',
        installation_date: '2026-01-15',
        current_risk: 'WARNING',
        last_passage_timestamp_utc: new Date().toISOString(),
        consecutive_abnormal_count: 2,
        total_revolutions_count: 814
      }
    ],
    diagnosis: {
      faultType: 'Harmonic Looseness / Fastener Wear',
      faultConfidence: 84.5,
      healthPrediction: 'WARNING_STATE',
      healthConfidence: 86.0,
      sensorPrediction: 'ELEVATED_VIBRATION',
      imagePrediction: 'Belt Joint',
      detectionMode: 'SINGLE_SOURCE',
      evidenceList: [
        { name: 'Vibration RMS', value: 3.82, unit: 'g', status: 'WARNING', baselineMedian: 1.06, deviation: '+4.2σ', source: 'ADXL345' },
        { name: 'Crest Factor', value: 3.25, unit: 'ratio', status: 'WARNING', baselineMedian: 1.52, deviation: '+3.1σ', source: 'DSP Analyzer' },
        { name: 'Bearing Temp', value: 68.2, unit: '°C', status: 'WARNING', source: 'PT100' }
      ],
      explanation: 'Vibration exceeded the learned baseline and the anomaly persisted across 2 consecutive revolutions.',
      recommendedAction: 'Schedule mechanical splice inspection within 48 operational hours.',
      timestamp: new Date().toISOString(),
      jointId: 'joint-001'
    },
    alerts: [
      {
        id: 'mock-alt-w1',
        joint_id: 'joint-001',
        conveyor_id: 'CV-MINE-01',
        severity: 'WARNING',
        alert_type: 'VIBRATION_HARMONIC_ELEVATION',
        message: 'Joint J-01 RMS acceleration exceeded warning threshold across 2 consecutive revolutions.',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 60000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-warning-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 3.82,
        peak: 5.12,
        peak_to_peak: 9.8,
        crest_factor: 3.25,
        kurtosis_fisher: 2.14,
        kurtosis_convention: 'Fisher/excess',
        skewness: 0.18,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 100.0,
        dominant_amplitude: 2.45,
        spectral_centroid_hz: 115.0,
        spectral_energy: 312.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, (_, i) => (i === 10 ? 1.5 : i === 20 ? 2.45 : Math.random() * 0.1))
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1422,
      server_time_utc: new Date().toISOString()
    }
  },

  critical: {
    name: 'critical',
    label: 'Critical Anomaly (Emergency Warning)',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1200,
      temperature: 88.5,
      load: 92.0,
      vibration: 6.45,
      acoustic_db: 98.2,
      tension: 90,
      tracking_offset_mm: 38.0,
      belt_health: 32.0,
      overall_status: 'CRITICAL',
      fault_type: 'SPLICE_RUPTURE_IMMINENT',
      fault_confidence: 94.2,
      health_prediction: 'CRITICAL SHOCK',
      health_confidence: 96.0,
      sensor_prediction: 'HIGH_AMPLITUDE_IMPACT',
      image_prediction: 'Large Tear',
      confidence: 95.0,
      recommendation: 'CRITICAL: Slow drive immediately and inspect Joint J-01 for tear propagation.',
      explanation: 'Critical broadband vibration with heavy repetitive impacts and elevated crest factor (>4.5).',
      vibration_waveform: generateWaveform(50, 100, 0.8, 3.5)
    },
    joints: [
      {
        id: 'joint-001',
        joint_code: 'J-01',
        belt_id: 'BELT-01',
        physical_position_meters: 120.0,
        identifier_type: 'OPTICAL',
        identifier_token: 'OPT-J01',
        splice_type: 'Finger Splice',
        installation_date: '2026-01-15',
        current_risk: 'CRITICAL',
        last_passage_timestamp_utc: new Date().toISOString(),
        consecutive_abnormal_count: 4,
        total_revolutions_count: 816
      }
    ],
    diagnosis: {
      faultType: 'Splice Rupture / Severe Impact',
      faultConfidence: 94.2,
      healthPrediction: 'CRITICAL_INTEGRITY',
      healthConfidence: 96.0,
      sensorPrediction: 'SEVERE_IMPACT',
      imagePrediction: 'Large Tear',
      detectionMode: 'SENSOR_VISION_AGREEMENT',
      evidenceList: [
        { name: 'Vibration RMS', value: 6.45, unit: 'g', status: 'CRITICAL', baselineMedian: 1.06, deviation: '+7.8σ', source: 'ADXL345' },
        { name: 'Crest Factor', value: 4.82, unit: 'ratio', status: 'CRITICAL', baselineMedian: 1.52, deviation: '+5.4σ', source: 'DSP Analyzer' },
        { name: 'Fisher Kurtosis', value: 5.62, unit: 'Fisher', status: 'CRITICAL', baselineMedian: -1.49, deviation: '+6.1σ', source: 'DSP Analyzer' },
        { name: 'Optical Vision', value: 'Large Tear (0.91)', unit: 'YOLOv8', status: 'CRITICAL', source: 'CAM-SPLICE-01' }
      ],
      explanation: 'Repetitive high-g shock peaks detected coincident with optical detection of Large Tear on Joint J-01.',
      recommendedAction: 'Trigger operator interlock: decelerate conveyor drive and perform immediate physical walkdown.',
      timestamp: new Date().toISOString(),
      jointId: 'joint-001'
    },
    alerts: [
      {
        id: 'mock-alt-c1',
        joint_id: 'joint-001',
        conveyor_id: 'CV-MINE-01',
        severity: 'CRITICAL',
        alert_type: 'CRITICAL_IMPACT_SPIKE',
        message: 'Severe periodic impact peaks exceeding 6.4g on Joint J-01. Optical vision confirms Large Tear.',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 30000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-critical-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 6.45,
        peak: 9.85,
        peak_to_peak: 18.2,
        crest_factor: 4.82,
        kurtosis_fisher: 5.62,
        kurtosis_convention: 'Fisher/excess',
        skewness: 0.85,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 18.5,
        dominant_amplitude: 4.2,
        spectral_centroid_hz: 245.0,
        spectral_energy: 890.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, () => Math.random() * 2.0)
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1425,
      server_time_utc: new Date().toISOString()
    }
  },

  bearing_fault: {
    name: 'bearing_fault',
    label: 'Drive Pulley Bearing Fault',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1200,
      temperature: 84.0,
      load: 65.0,
      vibration: 4.95,
      acoustic_db: 91.0,
      tension: 110,
      tracking_offset_mm: 5.0,
      belt_health: 68.0,
      overall_status: 'WARNING',
      fault_type: 'BEARING_DEFECT_BPFO',
      fault_confidence: 89.0,
      health_prediction: 'WARNING STATE',
      health_confidence: 90.0,
      sensor_prediction: 'BEARING_INNER_RACE',
      image_prediction: 'Belt Joint (Normal)',
      confidence: 89.0,
      recommendation: 'Lubricate drive pulley outboard bearing; inspect with ultrasonic stethoscope.',
      explanation: 'Characteristic bearing defect frequency modulation with elevated temperature on bearing housing.',
      vibration_waveform: generateWaveform(120, 100, 0.5, 1.8)
    },
    joints: [],
    diagnosis: {
      faultType: 'Pulley Bearing Outer Race Defect (BPFO)',
      faultConfidence: 89.0,
      healthPrediction: 'WARNING_STATE',
      healthConfidence: 90.0,
      sensorPrediction: 'BEARING_MODULATION',
      imagePrediction: 'No Visual Belt Anomaly',
      detectionMode: 'SINGLE_SOURCE',
      evidenceList: [
        { name: 'Vibration RMS', value: 4.95, unit: 'g', status: 'WARNING', baselineMedian: 1.06, deviation: '+4.8σ', source: 'ADXL345' },
        { name: 'Bearing Temp', value: 84.0, unit: '°C', status: 'WARNING', source: 'Thermocouple' },
        { name: 'Acoustic Emission', value: 91.0, unit: 'dB', status: 'WARNING', source: 'Microphone' }
      ],
      explanation: 'Bearing housing temperature spiked to 84°C accompanied by high-frequency acoustic emissions.',
      recommendedAction: 'Apply bearing grease; check vibration decay over 2 operational hours.',
      timestamp: new Date().toISOString()
    },
    alerts: [
      {
        id: 'mock-alt-bf',
        joint_id: null,
        conveyor_id: 'CV-MINE-01',
        severity: 'WARNING',
        alert_type: 'BEARING_OVERHEAT_VIBRATION',
        message: 'Drive pulley bearing temperature (84°C) and vibration elevated.',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 45000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-bf-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 4.95,
        peak: 7.2,
        peak_to_peak: 14.1,
        crest_factor: 3.45,
        kurtosis_fisher: 2.85,
        kurtosis_convention: 'Fisher/excess',
        skewness: 0.35,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 120.0,
        dominant_amplitude: 3.1,
        spectral_centroid_hz: 145.0,
        spectral_energy: 410.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, (_, i) => (i === 24 ? 3.1 : Math.random() * 0.15))
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1428,
      server_time_utc: new Date().toISOString()
    }
  },

  pulley_fault: {
    name: 'pulley_fault',
    label: 'Pulley Misalignment / Belt Drift',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1200,
      temperature: 55.0,
      load: 70.0,
      vibration: 3.9,
      acoustic_db: 79.0,
      tension: 140,
      tracking_offset_mm: 32.0,
      belt_health: 74.0,
      overall_status: 'WARNING',
      fault_type: 'PULLEY_MISALIGNMENT',
      fault_confidence: 87.0,
      health_prediction: 'TRACKING DRIFT WARNING',
      health_confidence: 88.0,
      sensor_prediction: 'LATERAL_RUNOUT',
      confidence: 87.0,
      recommendation: 'Calibrate tail pulley take-up carriage alignment.',
      explanation: 'Lateral tracking offset exceeds 30 mm with 1x shaft rotational imbalance frequency.',
      vibration_waveform: generateWaveform(20, 100, 0.3, 0.8)
    },
    joints: [],
    diagnosis: {
      faultType: 'Pulley Angular Misalignment',
      faultConfidence: 87.0,
      healthPrediction: 'WARNING_STATE',
      healthConfidence: 88.0,
      sensorPrediction: 'LATERAL_RUNOUT',
      detectionMode: 'SINGLE_SOURCE',
      evidenceList: [
        { name: 'Tracking Offset', value: 32.0, unit: 'mm', status: 'WARNING', source: 'Optical Drift Sensor' },
        { name: 'Take-up Tension', value: 140.0, unit: 'N', status: 'NORMAL', source: 'Pretension Rig' }
      ],
      explanation: 'Continuous 1x shaft runout vibration coupled with lateral edge position drift.',
      recommendedAction: 'Adjust snub pulley tension bolts to re-center belt travel line.',
      timestamp: new Date().toISOString()
    },
    alerts: [
      {
        id: 'mock-alt-pf',
        joint_id: null,
        conveyor_id: 'CV-MINE-01',
        severity: 'WARNING',
        alert_type: 'BELT_TRACKING_DRIFT',
        message: 'Tracking drift (32.0 mm) exceeds operational threshold.',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 50000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-pf-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 3.9,
        peak: 5.4,
        peak_to_peak: 10.2,
        crest_factor: 2.8,
        kurtosis_fisher: 0.45,
        kurtosis_convention: 'Fisher/excess',
        skewness: 0.12,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 20.0,
        dominant_amplitude: 2.8,
        spectral_centroid_hz: 45.0,
        spectral_energy: 220.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, (_, i) => (i === 4 ? 2.8 : Math.random() * 0.1))
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1430,
      server_time_utc: new Date().toISOString()
    }
  },

  belt_slippage: {
    name: 'belt_slippage',
    label: 'Drive Slip / Speed Loss',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 980,
      temperature: 62.0,
      load: 88.0,
      vibration: 2.4,
      acoustic_db: 84.0,
      tension: 65,
      tracking_offset_mm: 8.0,
      belt_health: 64.0,
      overall_status: 'WARNING',
      fault_type: 'BELT_SLIPPAGE',
      fault_confidence: 91.0,
      health_prediction: 'SLIPPAGE ADVISORY',
      health_confidence: 92.0,
      sensor_prediction: 'SPEED_LOSS',
      confidence: 91.0,
      recommendation: 'Increase take-up carriage tension; inspect drive pulley lagging for rubber glaze.',
      explanation: 'Belt speed slipped below 85% of motor drive RPM with reduced tension (65 N).',
      vibration_waveform: generateWaveform(30, 100, 0.4, 0)
    },
    joints: [],
    diagnosis: {
      faultType: 'Belt Slippage on Drive Drum',
      faultConfidence: 91.0,
      healthPrediction: 'WARNING_STATE',
      healthConfidence: 92.0,
      sensorPrediction: 'SPEED_DIFFERENTIAL',
      detectionMode: 'SINGLE_SOURCE',
      evidenceList: [
        { name: 'Drive Speed', value: 980, unit: 'RPM', status: 'WARNING', source: 'Tachometer' },
        { name: 'Take-up Tension', value: 65, unit: 'N', status: 'WARNING', source: 'Pretension Rig' }
      ],
      explanation: 'Pulley tachometer reports 980 RPM vs nominal 1200 RPM, indicating frictional slip.',
      recommendedAction: 'Adjust counterweight take-up to restore 110 N nominal pretension.',
      timestamp: new Date().toISOString()
    },
    alerts: [
      {
        id: 'mock-alt-bs',
        joint_id: null,
        conveyor_id: 'CV-MINE-01',
        severity: 'WARNING',
        alert_type: 'BELT_SLIP_DETECTED',
        message: 'Drive speed dropped below nominal (980 RPM). Slippage detected.',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 25000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-bs-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 2.4,
        peak: 3.6,
        peak_to_peak: 6.8,
        crest_factor: 2.1,
        kurtosis_fisher: -0.2,
        kurtosis_convention: 'Fisher/excess',
        skewness: 0.05,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 30.0,
        dominant_amplitude: 1.8,
        spectral_centroid_hz: 42.0,
        spectral_energy: 160.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, (_, i) => (i === 6 ? 1.8 : Math.random() * 0.08))
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1432,
      server_time_utc: new Date().toISOString()
    }
  },

  joint_rupture: {
    name: 'joint_rupture',
    label: 'Joint Splice Failure / Rupture',
    telemetry: {
      timestamp: Date.now(),
      conveyor_id: 'CV-MINE-01',
      rpm: 1150,
      temperature: 75.0,
      load: 85.0,
      vibration: 8.2,
      acoustic_db: 102.0,
      tension: 40,
      tracking_offset_mm: 45.0,
      belt_health: 15.0,
      overall_status: 'CRITICAL',
      fault_type: 'SPLICE_JOINT_DELAMINATION',
      fault_confidence: 98.0,
      health_prediction: 'IMMINENT FAILURE',
      health_confidence: 99.0,
      sensor_prediction: 'CATASTROPHIC_IMPACT',
      image_prediction: 'Large Tear',
      confidence: 98.5,
      recommendation: 'EMERGENCY: Immediate controlled shutdown. Splice J-01 experiencing partial separation.',
      explanation: 'Extreme shock transient (>8g) with crest factor 5.4. Vision confirms severe transverse joint tear.',
      vibration_waveform: generateWaveform(40, 100, 1.2, 5.0)
    },
    joints: [
      {
        id: 'joint-001',
        joint_code: 'J-01',
        belt_id: 'BELT-01',
        physical_position_meters: 120.0,
        identifier_type: 'OPTICAL',
        identifier_token: 'OPT-J01',
        splice_type: 'Finger Splice (Separated)',
        installation_date: '2026-01-15',
        current_risk: 'CRITICAL',
        last_passage_timestamp_utc: new Date().toISOString(),
        consecutive_abnormal_count: 5,
        total_revolutions_count: 820
      }
    ],
    diagnosis: {
      faultType: 'Splice Delamination / Rupture Event',
      faultConfidence: 98.0,
      healthPrediction: 'CRITICAL_SPLICE_FAILURE',
      healthConfidence: 99.0,
      sensorPrediction: 'CATASTROPHIC_SHOCK',
      imagePrediction: 'Large Tear (0.96)',
      detectionMode: 'SENSOR_VISION_AGREEMENT',
      evidenceList: [
        { name: 'Vibration RMS', value: 8.2, unit: 'g', status: 'CRITICAL', baselineMedian: 1.06, deviation: '+9.4σ', source: 'ADXL345' },
        { name: 'Crest Factor', value: 5.4, unit: 'ratio', status: 'CRITICAL', baselineMedian: 1.52, deviation: '+6.8σ', source: 'DSP Analyzer' },
        { name: 'Fisher Kurtosis', value: 7.1, unit: 'Fisher', status: 'CRITICAL', baselineMedian: -1.49, deviation: '+8.2σ', source: 'DSP Analyzer' },
        { name: 'Tension Drop', value: 40, unit: 'N', status: 'CRITICAL', source: 'Pretension Rig' },
        { name: 'YOLOv8 Class', value: 'Large Tear', unit: 'P=0.96', status: 'CRITICAL', source: 'CAM-SPLICE-01' }
      ],
      explanation: 'Transverse splice tearing verified through dual-evidence agreement (vibration shock + optical confirmation).',
      recommendedAction: 'Engage emergency interlock. Lock out drive motor and inspect Joint J-01.',
      timestamp: new Date().toISOString(),
      jointId: 'joint-001'
    },
    alerts: [
      {
        id: 'mock-alt-jr',
        joint_id: 'joint-001',
        conveyor_id: 'CV-MINE-01',
        severity: 'CRITICAL',
        alert_type: 'SPLICE_RUPTURE_ALARM',
        message: 'EMERGENCY: Joint J-01 splice delamination detected. Extreme impact energy (>8g).',
        is_acknowledged: false,
        triggered_at_utc: new Date(Date.now() - 10000).toISOString(),
        data_provenance: 'SIMULATION'
      }
    ],
    dspAnalysis: {
      burst_id: 'mock-burst-jr-01',
      data_provenance: 'SIMULATION',
      sampling_rate_hz: 1000.0,
      sample_count: 1000,
      integrity_verified: true,
      time_domain: {
        rms: 8.2,
        peak: 12.8,
        peak_to_peak: 24.5,
        crest_factor: 5.4,
        kurtosis_fisher: 7.1,
        kurtosis_convention: 'Fisher/excess',
        skewness: 1.15,
        sample_count: 1000
      },
      frequency_domain: {
        dominant_frequency_hz: 15.0,
        dominant_amplitude: 5.8,
        spectral_centroid_hz: 310.0,
        spectral_energy: 1250.0,
        bin_count: 500,
        frequency_resolution_hz: 1.0
      },
      fft_bins: {
        frequencies_hz: Array.from({ length: 100 }, (_, i) => i * 5),
        amplitudes: Array.from({ length: 100 }, () => Math.random() * 3.5)
      },
      engineering_thresholds: {
        label: 'engineering_threshold',
        abs_rms_alert: 5.0,
        abs_crest_factor: 4.0,
        abs_kurtosis_fisher: 3.0
      }
    },
    systemStatus: {
      system_name: 'Conveyor Joint Health System',
      status: 'OPERATIONAL',
      serial_worker_enabled: false,
      serial_port: 'COM3',
      simulation_ingestion_allowed: true,
      active_streams: [],
      total_bursts_persisted: 1435,
      server_time_utc: new Date().toISOString()
    }
  }
};

/**
 * Helper to get mock data for a scenario or check query params
 */
export function getMockScenarioData(scenario: MockScenario = 'healthy'): MockScenarioData {
  return MOCK_SCENARIOS[scenario] || MOCK_SCENARIOS.healthy;
}

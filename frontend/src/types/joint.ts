/**
 * Joint Entity, Lifecycle, and Joint Passport Types
 */

import type { StatusLevel, ProvenanceType } from './telemetry';

export interface Joint {
  id: string;
  joint_code: string;
  belt_id: string;
  physical_position_meters: number;
  identifier_type: string;
  identifier_token: string;
  splice_type: string;
  installation_date: string;
  current_risk: StatusLevel;
  last_passage_timestamp_utc?: string | null;
  consecutive_abnormal_count: number;
  total_revolutions_count: number;
}

export interface JointObservationMetrics {
  revolution_index: number;
  timestamp_utc: string;
  health_score: number;
  risk_state: StatusLevel;
  anomaly_detected: boolean;
  rms: number;
  crest_factor: number;
  kurtosis: number;
  dominant_frequency_hz: number;
  rms_deviation?: number;
  baseline_status: string;
  data_provenance: ProvenanceType;
}

export interface JointBaseline {
  rms_median: number | null;
  crest_factor_median: number | null;
  kurtosis_median: number | null;
  dominant_freq_median: number | null;
  status: string;
  label: string;
}

export interface JointPassportResponse {
  passport_schema_version: string;
  joint_identity: {
    joint_id: string;
    joint_code: string;
    conveyor_section: string;
    installation_date: string;
    splice_type: string;
    total_revolutions: number;
    consecutive_abnormal_count: number;
    last_passage_utc: string | null;
  };
  evidence_sources: {
    vibration_dsp_evidence: {
      source: string;
      current_risk_state: StatusLevel;
      latest_observation: JointObservationMetrics | null;
      baseline: JointBaseline;
      health_score: number;
      consecutive_anomalies: number;
    };
    ml_anomaly_evidence: {
      available: boolean;
      model_version?: string;
      model_type?: string;
      model_status?: string;
      raw_anomaly_score?: number;
      anomaly_decision?: boolean;
      threshold_status?: string;
      operating_regime?: {
        speed_rpm: number;
        pretension_n: number;
      };
      baseline_deviation?: Array<{
        feature: string;
        value: number;
        unit: string;
        standardized_deviation: number;
      }>;
      provenance?: {
        dataset: string;
        doi: string;
      };
      scientific_scope?: string;
      rupture_prediction?: boolean;
      safety_interlock?: string;
    } | null;
    vision_optical_evidence: {
      status: string;
      message?: string;
      observation_id?: string;
      detected_classes?: string[];
      max_confidence?: number;
    };
    operational_telemetry: {
      belt_speed_mps?: number;
      motor_current_a?: number;
      ambient_temperature_c?: number;
      bearing_temperature_c?: number;
      status: string;
    };
  };
  joint_health_engine: {
    safety_status: string;
    recommended_action: string;
    ml_advisory: string;
    deterministic_rule_basis: string;
    active_alerts: Array<{
      alert_id: string;
      severity: string;
      alert_type: string;
      triggered_at_utc: string;
    }>;
  };
}

/**
 * Vibration ML & Anomaly Detection Types
 * Directly matches backend/app/ml_service.py and /ml/status /ml/score
 */

export interface OperatingRegime {
  speed_rpm: number;
  pretension_n: number;
}

export interface BaselineDeviationFeature {
  feature: string;
  value: number;
  unit: string;
  standardized_deviation: number;
}

export interface MlScoreResponse {
  available: boolean;
  model_version: string;
  model_type: string;
  model_status: string;
  raw_anomaly_score: number | null;
  anomaly_decision: boolean | null;
  threshold_status: string;
  threshold_methodology: string;
  operating_regime: OperatingRegime;
  baseline_deviation: BaselineDeviationFeature[];
  provenance?: {
    dataset: string;
    doi: string;
  };
  scientific_scope?: string;
  rupture_prediction?: boolean;
  safety_interlock?: string;
  error?: string;
}

export interface MlModelStatus {
  model_status: string;
  model_version: string;
  model_type: string;
  weights_path: string;
  input_feature_count: number;
  features_list: string[];
  scientific_scope: string;
  rupture_prediction: boolean;
  safety_guardrail: string;
}

/**
 * Explainable Diagnosis & ML/Vision Multi-Source Intelligence Types
 */

import type { StatusLevel } from './telemetry';

export interface SensorEvidenceItem {
  name: string;
  value: number | string | null;
  unit: string;
  status: StatusLevel | 'UNKNOWN';
  baselineMedian?: number | null;
  deviation?: string;
  source: string;
}

export interface ExplainableDiagnosis {
  faultType: string;
  faultConfidence: number;
  healthPrediction: string;
  healthConfidence: number;
  sensorPrediction: string;
  imagePrediction?: string | null;
  detectionMode: 'SINGLE_SOURCE' | 'SENSOR_VISION_AGREEMENT' | 'DISAGREEMENT' | 'NO_ANOMALY';
  evidenceList: SensorEvidenceItem[];
  explanation: string;
  recommendedAction: string;
  timestamp: string;
  jointId?: string;
}

/**
 * Alerts & Events Types
 */

import type { StatusLevel, ProvenanceType } from './telemetry';

export interface AlertEvent {
  id: string;
  joint_id?: string | null;
  conveyor_id?: string | null;
  severity: StatusLevel;
  alert_type: string;
  message: string;
  is_acknowledged: boolean;
  acknowledged_by?: string | null;
  acknowledged_at_utc?: string | null;
  triggered_at_utc: string;
  data_provenance: ProvenanceType;
  metrics_snapshot?: Record<string, any> | null;
}

export interface AlertListResponse {
  total: number;
  offset: number;
  limit: number;
  alerts: AlertEvent[];
}

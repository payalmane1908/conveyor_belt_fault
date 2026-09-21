/**
 * Telemetry Types & Industrial Sensor Data Contracts
 * 
 * Adheres strictly to Section 11 compatibility contract & Backend Ingestion Schemas.
 * Critical Rule: undefined != zero. If missing, UI shows "Waiting for data".
 */

export type StatusLevel = 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL';
export type ProvenanceType = 'LIVE' | 'EDGE_HARDWARE' | 'SIMULATION' | 'HISTORICAL' | 'RESEARCH_BENCHMARK';
export type CapabilityState = 'LIVE' | 'DEMO' | 'UNAVAILABLE';

/**
 * Standard Telemetry Compatibility Contract (Section 11)
 */
export interface Telemetry {
  timestamp: number;
  conveyor_id?: string;
  rpm?: number;
  temperature?: number;
  load?: number;
  vibration?: number;
  acoustic_db?: number;
  tension?: number;
  tracking_offset_mm?: number;
  belt_health?: number;
  sensor_prediction?: string;
  image_prediction?: string;
  confidence?: number;
  overall_status?: StatusLevel;
  fault_type?: string;
  fault_confidence?: number;
  health_prediction?: string;
  health_confidence?: number;
  recommendation?: string;
  explanation?: string;
  vibration_waveform?: number[];
}

/**
 * Backend Raw Telemetry Burst Summary
 */
export interface RawBurstSummary {
  id: string;
  device_id: string;
  stream_id: string;
  sensor_id: string;
  joint_id?: string | null;
  sequence_number: number;
  hardware_timestamp_us: number;
  unwrapped_hardware_timestamp_us: number;
  received_at_utc: string;
  sampling_rate_hz: number;
  sample_count: number;
  sha256_hash: string;
  quality_flags: string;
  data_provenance: ProvenanceType;
}

/**
 * Edge Stream Tracker Status
 */
export interface StreamStatus {
  stream_id: string;
  device_id: string;
  last_sequence_number: number;
  total_packets_received: number;
  dropped_packets_count: number;
  last_hardware_timestamp_us: number;
  rollover_count: number;
  last_seen_utc: string;
}

/**
 * Backend System Status Response
 */
export interface SystemStatusResponse {
  system_name: string;
  status: string;
  serial_worker_enabled: boolean;
  serial_port: string;
  simulation_ingestion_allowed: boolean;
  active_streams: StreamStatus[];
  total_bursts_persisted: number;
  server_time_utc: string;
}

/**
 * Live Telemetry Snapshot from /api/v1/telemetry/snapshot
 */
export interface TelemetrySnapshot {
  system_name: string;
  hardware_stream_state: 'LIVE HARDWARE' | 'SIMULATION' | 'NO ACTIVE STREAM' | 'HARDWARE OFFLINE';
  active_streams: StreamStatus[];
  latest_burst: (RawBurstSummary & {
    samples: number[];
    integrity_verified: boolean;
  }) | null;
  server_time_utc: string;
}

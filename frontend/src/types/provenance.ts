/**
 * Cryptographic Integrity & Dataset Provenance Types
 */

export interface DatasetProvenanceInfo {
  dataset_name: string;
  source_type: string;
  doi?: string;
  url?: string;
  description: string;
  total_samples: number;
  classes_or_conditions: string[];
  scientific_scope: string;
  license: string;
}

export interface TelemetryProvenanceRecord {
  record_id: string;
  timestamp: string;
  source: string;
  joint_id?: string | null;
  sha256_hash: string;
  verification_status: 'VERIFIED' | 'FAILED' | 'PENDING';
  storage_reference: string;
  provenance: 'LIVE' | 'SIMULATION' | 'HISTORICAL';
  quality_flags: string;
  sequence_number: number;
}

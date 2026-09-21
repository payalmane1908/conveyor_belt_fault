/**
 * Cryptographic Integrity & Telemetry Provenance Types
 */

import type { ProvenanceType } from './telemetry';

export interface TelemetryEvidenceRecord {
  record_id: string;
  timestamp: string;
  source: string;
  joint_id?: string | null;
  sha256_hash: string;
  verification_status: 'VERIFIED' | 'FAILED' | 'PENDING';
  storage_reference: string;
  provenance: ProvenanceType;
  quality_flags: string;
  sequence_number: number;
}

/**
 * DSP Feature Analytics & Spectral Types
 */

import type { ProvenanceType } from './telemetry';

export interface TimeDomainFeatures {
  rms: number;
  peak: number;
  peak_to_peak: number;
  crest_factor: number;
  kurtosis_fisher: number;
  kurtosis_convention: string;
  skewness: number;
  sample_count: number;
}

export interface FrequencyDomainFeatures {
  dominant_frequency_hz: number | null;
  dominant_amplitude: number | null;
  spectral_centroid_hz: number | null;
  spectral_energy: number | null;
  bin_count: number;
  frequency_resolution_hz: number | null;
}

export interface BurstDspAnalysis {
  burst_id: string;
  data_provenance: ProvenanceType;
  sampling_rate_hz: number;
  sample_count: number;
  integrity_verified: boolean;
  time_domain: TimeDomainFeatures;
  frequency_domain: FrequencyDomainFeatures;
  fft_bins: {
    frequencies_hz: number[];
    amplitudes: number[];
  };
  engineering_thresholds: {
    label: string;
    abs_rms_alert: number;
    abs_crest_factor: number;
    abs_kurtosis_fisher: number;
  };
}

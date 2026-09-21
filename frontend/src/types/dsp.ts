/**
 * Digital Signal Processing (DSP) & Frequency Domain Types
 * Directly matches backend/app/dsp.py and /analytics/bursts/{id}/dsp
 */

export interface TimeDomainMetrics {
  rms: number;
  peak: number;
  peak_to_peak: number;
  crest_factor: number;
  kurtosis_fisher: number;
  kurtosis_convention: string;
  skewness: number;
  sample_count: number;
}

export interface FrequencyDomainMetrics {
  dominant_frequency_hz: number | null;
  dominant_amplitude: number | null;
  spectral_centroid_hz: number | null;
  spectral_energy: number | null;
  bin_count: number;
  frequency_resolution_hz: number | null;
}

export interface FFTBins {
  frequencies_hz: number[];
  amplitudes: number[];
}

export interface BurstDspAnalysis {
  burst_id: string;
  data_provenance: string;
  sampling_rate_hz: number;
  sample_count: number;
  integrity_verified: boolean;
  time_domain: TimeDomainMetrics;
  frequency_domain: FrequencyDomainMetrics;
  fft_bins: FFTBins;
  engineering_thresholds: {
    label: string;
    abs_rms_alert: number;
    abs_crest_factor: number;
    abs_kurtosis_fisher: number;
  };
}

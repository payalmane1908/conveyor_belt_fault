/**
 * Centralized API Service Layer
 * 
 * Strict rule: All HTTP network requests must pass through this file.
 * Never call fetch() directly inside React components.
 * Only implements functions for endpoints that actually exist in the backend.
 */

import { config } from '../config';
import type {
  SystemStatusResponse,
  TelemetrySnapshot,
  RawBurstSummary,
  Joint,
  JointPassportResponse,
  AlertListResponse,
  BurstDspAnalysis,
  VisionObservation,
  VisionEngineStatus
} from '../types';

class ApiService {
  public get baseUrl(): string {
    return config.apiBaseUrl;
  }

  resolveMediaUrl(pathOrUrl?: string | null): string {
    if (!pathOrUrl) return '';
    if (pathOrUrl.startsWith('http://') || pathOrUrl.startsWith('https://')) {
      return pathOrUrl;
    }
    const cleanPath = pathOrUrl.startsWith('/') ? pathOrUrl : `/${pathOrUrl}`;
    return `${this.baseUrl}${cleanPath}`;
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    const response = await fetch(url, { ...options, headers });
    if (!response.ok) {
      const errorBody = await response.text().catch(() => '');
      throw new Error(`API Error ${response.status} on ${endpoint}: ${errorBody || response.statusText}`);
    }
    return response.json() as Promise<T>;
  }

  // 1. System & Edge Status
  async getSystemStatus(): Promise<SystemStatusResponse> {
    return this.request<SystemStatusResponse>('/api/v1/system/status');
  }

  async getHardwareSerialStatus(): Promise<{
    worker_running: boolean;
    com_port: string;
    baud_rate: number;
    bytes_read: number;
    packets_parsed: number;
    last_error: string | null;
  }> {
    return this.request('/api/v1/hardware/serial/status');
  }

  // 2. Telemetry & Snapshots
  async getTelemetrySnapshot(): Promise<TelemetrySnapshot> {
    return this.request<TelemetrySnapshot>('/api/v1/telemetry/snapshot');
  }

  async getLatestTelemetry(deviceId?: string, streamId?: string): Promise<RawBurstSummary | null> {
    const params = new URLSearchParams();
    if (deviceId) params.append('device_id', deviceId);
    if (streamId) params.append('stream_id', streamId);
    const qs = params.toString() ? `?${params.toString()}` : '';
    return this.request<RawBurstSummary | null>(`/api/v1/telemetry/latest${qs}`);
  }

  async getBurstDetail(burstId: string): Promise<RawBurstSummary & { samples: number[]; integrity_verified: boolean }> {
    return this.request(`/api/v1/telemetry/bursts/${encodeURIComponent(burstId)}`);
  }

  // 3. Conveyor & Joint Assets
  async getConveyors(): Promise<Array<{
    id: string;
    name: string;
    location: string;
    length_meters: number;
    nominal_speed_mps: number;
    created_at_utc: string;
  }>> {
    return this.request('/api/v1/conveyors');
  }

  async getJoints(): Promise<Joint[]> {
    return this.request<Joint[]>('/api/v1/joints');
  }

  async getJointHealth(jointId: string): Promise<any> {
    return this.request(`/api/v1/joints/${encodeURIComponent(jointId)}/health`);
  }

  async getJointPassport(jointId: string): Promise<JointPassportResponse> {
    return this.request<JointPassportResponse>(`/api/v1/joints/${encodeURIComponent(jointId)}/passport`);
  }

  async getJointObservations(jointId: string, limit = 50, offset = 0): Promise<{
    joint_id: string;
    joint_code: string;
    total: number;
    offset: number;
    limit: number;
    observations: any[];
  }> {
    return this.request(`/api/v1/joints/${encodeURIComponent(jointId)}/observations?limit=${limit}&offset=${offset}`);
  }

  async getJointLifecycle(jointId: string): Promise<any> {
    return this.request(`/api/v1/joints/${encodeURIComponent(jointId)}/lifecycle`);
  }

  async getJointMaintenanceLogs(jointId: string): Promise<any[]> {
    return this.request(`/api/v1/joints/${encodeURIComponent(jointId)}/maintenance`);
  }

  async logMaintenance(payload: {
    joint_id: string;
    technician_id: string;
    action_type: 'INSPECTION' | 'SPLICE_REPAIR' | 'RETENSIONING' | 'REPLACEMENT' | 'RECALIBRATION';
    notes?: string;
    baseline_reset?: boolean;
    data_provenance?: string;
  }): Promise<{
    id: string;
    joint_id: string;
    timestamp_utc: string;
    technician_id: string;
    action_type: string;
    notes?: string;
    risk_state_before: string;
    risk_state_after: string;
    baseline_reset: number;
    data_provenance: string;
    record_hash: string;
  }> {
    return this.request('/api/v1/maintenance/log', {
      method: 'POST',
      body: JSON.stringify(payload)
    });
  }

  // 4. Alerts
  async getAlerts(params: {
    severity?: string;
    joint_id?: string;
    unacknowledged_only?: boolean;
    limit?: number;
    offset?: number;
  } = {}): Promise<AlertListResponse> {
    const q = new URLSearchParams();
    if (params.severity) q.append('severity', params.severity);
    if (params.joint_id) q.append('joint_id', params.joint_id);
    if (params.unacknowledged_only !== undefined) q.append('unacknowledged_only', String(params.unacknowledged_only));
    if (params.limit) q.append('limit', String(params.limit));
    if (params.offset) q.append('offset', String(params.offset));
    const qs = q.toString() ? `?${q.toString()}` : '';
    return this.request<AlertListResponse>(`/api/v1/alerts${qs}`);
  }

  async acknowledgeAlert(alertId: string, acknowledgedBy = 'OPERATOR'): Promise<{
    status: string;
    alert_id: string;
    acknowledged_by: string;
    acknowledged_at_utc: string;
  }> {
    return this.request(`/api/v1/alerts/${encodeURIComponent(alertId)}/acknowledge?acknowledged_by=${encodeURIComponent(acknowledgedBy)}`, {
      method: 'POST'
    });
  }

  // 5. Phase 3 Analytics & DSP
  async getBurstDspAnalysis(burstId: string): Promise<BurstDspAnalysis> {
    return this.request<BurstDspAnalysis>(`/api/v1/analytics/bursts/${encodeURIComponent(burstId)}/dsp`);
  }

  // 6. ML & Anomaly Detection
  async getMlStatus(): Promise<any> {
    return this.request('/api/v1/ml/status');
  }

  async scoreVibrationFeatures(features: Record<string, any>): Promise<any> {
    return this.request('/api/v1/ml/score', {
      method: 'POST',
      body: JSON.stringify(features)
    });
  }

  // 7. Vision & Optical Inspection
  async getVisionStatus(): Promise<VisionEngineStatus> {
    return this.request<VisionEngineStatus>('/api/v1/vision/status');
  }

  async getCameraStatus(): Promise<{
    hardware_camera_available: boolean;
    device_index: number;
    camera_enabled: boolean;
    auto_trigger_on_joint: boolean;
    last_capture_utc: string | null;
    total_captures: number;
    last_observation_id: string | null;
    mode: string;
  }> {
    return this.request('/api/v1/vision/camera/status');
  }

  getCameraStreamUrl(): string {
    return this.resolveMediaUrl('/api/v1/vision/camera/stream');
  }

  async triggerCameraCapture(params?: {
    joint_code?: string;
    camera_id?: string;
    conf_threshold?: number;
    test_image_name?: string;
  }): Promise<any> {
    const q = new URLSearchParams();
    if (params?.joint_code) q.append('joint_code', params.joint_code);
    if (params?.camera_id) q.append('camera_id', params.camera_id);
    if (params?.conf_threshold) q.append('conf_threshold', String(params.conf_threshold));
    if (params?.test_image_name) q.append('test_image_name', params.test_image_name);
    const qs = q.toString() ? `?${q.toString()}` : '';
    return this.request(`/api/v1/vision/camera/capture${qs}`, {
      method: 'POST'
    });
  }

  async getVisionTestSamples(): Promise<{ total_test_samples: number; dataset_split: string; samples: string[] }> {
    return this.request('/api/v1/vision/test-samples');
  }

  async analyzeVisionFrame(
    testImageName?: string,
    jointCode?: string,
    cameraId = 'CAM-SPLICE-01',
    file?: File
  ): Promise<VisionObservation> {
    const q = new URLSearchParams();
    if (testImageName) q.append('test_image_name', testImageName);
    if (jointCode) q.append('joint_code', jointCode);
    if (cameraId) q.append('camera_id', cameraId);

    if (file) {
      const formData = new FormData();
      formData.append('file', file);
      const url = `${this.baseUrl}/api/v1/vision/analyze?${q.toString()}`;
      const response = await fetch(url, {
        method: 'POST',
        body: formData
      });
      if (!response.ok) {
        const err = await response.text();
        throw new Error(`Vision analysis failed: ${err || response.statusText}`);
      }
      return response.json();
    }

    return this.request<VisionObservation>(`/api/v1/vision/analyze?${q.toString()}`, {
      method: 'POST'
    });
  }

  getVisionFrameImageUrl(observationId: string): string {
    return `${this.baseUrl}/api/v1/vision/frame/${encodeURIComponent(observationId)}`;
  }

  async getVisionObservations(jointCode?: string, limit = 20, damagedOnly = false): Promise<VisionObservation[]> {
    const q = new URLSearchParams();
    if (jointCode) q.append('joint_code', jointCode);
    if (limit) q.append('limit', String(limit));
    if (damagedOnly) q.append('damaged_only', 'true');
    const qs = q.toString() ? `?${q.toString()}` : '';
    return this.request<VisionObservation[]>(`/api/v1/vision/observations${qs}`);
  }

  async getVisionMetrics(): Promise<any> {
    return this.request('/api/v1/vision/metrics');
  }

  async resetVision(jointId = 'joint-001'): Promise<any> {
    return this.request(`/api/v1/vision/reset?joint_id=${encodeURIComponent(jointId)}`, {
      method: 'POST'
    });
  }

  getVisionArtifactUrl(filename: string): string {
    return `${this.baseUrl}/api/v1/vision/artifacts/${encodeURIComponent(filename)}`;
  }

  // 8. Datasets & Provenance
  async getDatasetProvenance(): Promise<any> {
    return this.request('/api/v1/datasets/provenance');
  }

  async getDatasetProvenanceDetail(name: string): Promise<any> {
    return this.request(`/api/v1/datasets/provenance/${encodeURIComponent(name)}`);
  }

  // 9. Simulation & Fault Injection (Development Rig)
  async injectSimulationBurst(sensorId: string, fundamentalFreqHz = 50.0): Promise<RawBurstSummary> {
    return this.request<RawBurstSummary>(`/api/v1/telemetry/simulate/generate-burst?sensor_id=${encodeURIComponent(sensorId)}&fundamental_freq_hz=${fundamentalFreqHz}`, {
      method: 'POST'
    });
  }

  async injectFaultBurst(sensorId: string, faultMode: string, jointId?: string): Promise<RawBurstSummary> {
    const q = new URLSearchParams({
      sensor_id: sensorId,
      fault_mode: faultMode
    });
    if (jointId) q.append('joint_id', jointId);
    return this.request<RawBurstSummary>(`/api/v1/telemetry/simulate/generate-fault?${q.toString()}`, {
      method: 'POST'
    });
  }

  // 10. Historical Dataset Replay Controller
  async startHistoricalReplay(condition = 'ALL', speedHz = 0.5): Promise<any> {
    return this.request(`/api/v1/historical/replay/start?condition=${encodeURIComponent(condition)}&speed_hz=${speedHz}`, {
      method: 'POST'
    });
  }

  async stopHistoricalReplay(): Promise<any> {
    return this.request('/api/v1/historical/replay/stop', {
      method: 'POST'
    });
  }

  async stepHistoricalReplay(): Promise<any> {
    return this.request('/api/v1/historical/replay/step', {
      method: 'POST'
    });
  }

  async getHistoricalReplayStatus(): Promise<any> {
    return this.request('/api/v1/historical/replay/status');
  }
}

export const api = new ApiService();

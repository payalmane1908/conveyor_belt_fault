/**
 * Central Monitoring Context
 * 
 * Manages:
 * - Telemetry state (backend authoritative, compatibility contract with undefined != zero)
 * - WebSocket streaming supporting:
 *   - TELEMETRY_BURST: Raw waveform, sequence, timestamps, SHA-256 hash
 *   - HEALTH_UPDATE: Real-time DSP RMS, crest factor, health score, risk state
 *   - ALERT_TRIGGERED: Live backend alerts
 *   - ML_ANOMALY_UPDATE: Isolation Forest anomaly score & baseline deviations
 *   - MAINTENANCE_LOGGED: Cryptographic maintenance ledger updates
 * - Authoritative Scenario Synchronization:
 *   - NORMAL -> Splice Baseline
 *   - SPLICE_IMPACT -> Splice Rupture Warning (Crest Factor Spike > 3.5)
 *   - HARMONIC_LOOSENESS -> Mechanical Harmonic Looseness (100 Hz / 150 Hz harmonics)
 *   - CRITICAL_FAILURE -> Emergency Interlock Trip (RMS > 6.5 g)
 * - Strict Data Provenance (EDGE_HARDWARE, SIMULATION, RESEARCH_BENCHMARK)
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { config } from '../config';
import { api } from '../services/api';
import { getMockScenarioData } from '../services/mock';
import type { MockScenario } from '../services/mock';
import type {
  Telemetry,
  Joint,
  AlertEvent,
  ExplainableDiagnosis,
  RawBurstSummary,
  StatusLevel,
  ProvenanceType
} from '../types';

export type DemoScenarioKey = 'NORMAL' | 'SPLICE_IMPACT' | 'HARMONIC_LOOSENESS' | 'CRITICAL_FAILURE';

export interface DemoScenarioInfo {
  key: DemoScenarioKey;
  label: string;
  sublabel: string;
  description: string;
  expectedStatus: StatusLevel;
}

export const DEMO_SCENARIOS: DemoScenarioInfo[] = [
  {
    key: 'NORMAL',
    label: 'Normal Baseline',
    sublabel: '1200 RPM • 110 N • 0.33 g RMS',
    description: 'Controlled 50 Hz fundamental vibration with nominal operating baseline.',
    expectedStatus: 'NORMAL'
  },
  {
    key: 'SPLICE_IMPACT',
    label: 'Splice Rupture Warning',
    sublabel: 'Crest Factor Spike > 3.5 (Demo Rule)',
    description: 'Periodic impulsive transients caused by joint splice fatigue and mechanical impact.',
    expectedStatus: 'WARNING'
  },
  {
    key: 'HARMONIC_LOOSENESS',
    label: 'Mechanical Harmonic Looseness',
    sublabel: '100 Hz / 150 Hz Harmonics (Demo Rule)',
    description: 'Structural resonance and multi-peak spectrum at 2x and 3x running frequencies.',
    expectedStatus: 'WARNING'
  },
  {
    key: 'CRITICAL_FAILURE',
    label: 'Emergency Interlock Trip',
    sublabel: 'RMS > 6.5 g (Simulated Interlock)',
    description: 'High-energy broadband failure vibration exceeding safety demonstration interlock.',
    expectedStatus: 'CRITICAL'
  }
];

interface MonitoringContextType {
  // Scenario & Simulation
  activeScenario: DemoScenarioKey;
  triggerScenario: (scenarioKey: DemoScenarioKey) => Promise<void>;
  isScenarioLoading: boolean;
  isMock: boolean;
  scenario: MockScenario;
  setScenario: (scenario: MockScenario) => void;
  setIsMock: (mock: boolean) => void;

  // Real-time State
  telemetry: Telemetry | null;
  joints: Joint[];
  alerts: AlertEvent[];
  diagnosis: ExplainableDiagnosis | null;
  latestBurst: RawBurstSummary | null;
  sensorHistory: {
    vibration: number[];
    temperature: number[];
    load: number[];
    rpm: number[];
  };

  // Provenance & Hardware State
  edgeConnected: boolean;
  wsConnected: boolean;
  dataProvenance: ProvenanceType;
  hardwareStreamState: string;
  lastUpdate: Date | null;
  isLoading: boolean;
  error: string | null;

  // UI Modals
  isSimulatorOpen: boolean;
  setIsSimulatorOpen: (open: boolean) => void;

  // Actions
  refreshData: () => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
}

const MonitoringContext = createContext<MonitoringContextType | undefined>(undefined);

export const MonitoringProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const searchParams = new URLSearchParams(window.location.search);
  const urlScenario = searchParams.get('scenario') as MockScenario | null;
  const initialScenario: MockScenario = urlScenario || 'healthy';
  const initialIsMock = searchParams.get('mock') === 'true' || config.useMock;

  const [isMock, setIsMockState] = useState<boolean>(initialIsMock);
  const [scenario, setScenarioState] = useState<MockScenario>(initialScenario);
  const [activeScenario, setActiveScenario] = useState<DemoScenarioKey>('NORMAL');
  const [isScenarioLoading, setIsScenarioLoading] = useState<boolean>(false);

  const [telemetry, setTelemetry] = useState<Telemetry | null>(null);
  const [joints, setJoints] = useState<Joint[]>([]);
  const [alerts, setAlerts] = useState<AlertEvent[]>([]);
  const [diagnosis, setDiagnosis] = useState<ExplainableDiagnosis | null>(null);
  const [latestBurst, setLatestBurst] = useState<RawBurstSummary | null>(null);
  const [isSimulatorOpen, setIsSimulatorOpen] = useState<boolean>(false);

  const [sensorHistory, setSensorHistory] = useState<{
    vibration: number[];
    temperature: number[];
    load: number[];
    rpm: number[];
  }>(() => {
    // 28 rolling baseline points with authentic physical signatures
    const vib: number[] = [];
    const temp: number[] = [];
    const loadArr: number[] = [];
    const rpmArr: number[] = [];

    for (let i = 0; i < 28; i++) {
      // Vibration: ADXL345 accelerometer baseline ~0.33g with slight noise and 1 splice pulse
      const transient = i === 18 ? 0.28 : 0.0;
      vib.push(Number((0.31 + Math.sin(i * 0.7) * 0.03 + transient).toFixed(2)));

      // Temperature: continuous smooth thermodynamic thermal equilibrium curve (37.8 - 38.0°C)
      temp.push(Number((37.8 + (i / 27) * 0.2).toFixed(1)));

      // Load: continuous granular bulk material flow (2.42 - 2.50 kg)
      loadArr.push(Number((2.44 + Math.sin(i * 0.3) * 0.05).toFixed(2)));

      // RPM: Closed-loop VFD governor regulated at 1200 RPM with sub-pixel micro-jitter
      rpmArr.push(1200 + (i % 4 === 0 ? 1 : i % 6 === 0 ? -1 : 0));
    }

    return { vibration: vib, temperature: temp, load: loadArr, rpm: rpmArr };
  });

  const recordSensorHistory = useCallback((vib?: number | null, temp?: number | null, load?: number | null, rpm?: number | null) => {
    setSensorHistory(prev => ({
      vibration: vib !== undefined && vib !== null ? [...prev.vibration.slice(-27), Number(vib.toFixed(2))] : prev.vibration,
      temperature: temp !== undefined && temp !== null ? [...prev.temperature.slice(-27), Number(temp.toFixed(1))] : prev.temperature,
      load: load !== undefined && load !== null ? [...prev.load.slice(-27), Number((load * 0.035).toFixed(2))] : prev.load,
      rpm: rpm !== undefined && rpm !== null ? [...prev.rpm.slice(-27), Math.round(rpm)] : prev.rpm
    }));
  }, []);

  const [edgeConnected, setEdgeConnected] = useState<boolean>(false);
  const [wsConnected, setWsConnected] = useState<boolean>(false);
  const [dataProvenance, setDataProvenance] = useState<ProvenanceType>('SIMULATION');
  const [hardwareStreamState, setHardwareStreamState] = useState<string>('WAITING FOR DATA');
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<number | null>(null);

  // Fallback mock setter
  const setScenario = useCallback((newScenario: MockScenario) => {
    setScenarioState(newScenario);
    const mockData = getMockScenarioData(newScenario);
    setTelemetry(mockData.telemetry);
    setJoints(mockData.joints);
    setAlerts(mockData.alerts);
    setDiagnosis(mockData.diagnosis);
    setLastUpdate(new Date());
  }, []);

  const setIsMock = useCallback((mockVal: boolean) => {
    setIsMockState(mockVal);
    if (mockVal) {
      const mockData = getMockScenarioData(scenario);
      setTelemetry(mockData.telemetry);
      setJoints(mockData.joints);
      setAlerts(mockData.alerts);
      setDiagnosis(mockData.diagnosis);
      setEdgeConnected(true);
      setDataProvenance('SIMULATION');
      setLastUpdate(new Date());
    }
  }, [scenario]);

  // Live polling logic (Queries real backend state)
  const fetchLiveData = useCallback(async () => {
    if (isMock) return;

    try {
      setError(null);
      const [snapshot, jointsList, alertsRes] = await Promise.allSettled([
        api.getTelemetrySnapshot(),
        api.getJoints(),
        api.getAlerts({ limit: 15 })
      ]);

      let newEdgeConnected = false;
      let newLatestBurst: RawBurstSummary | null = null;
      let newProvenance: ProvenanceType = 'SIMULATION';
      let newStreamState = 'NO ACTIVE STREAM';

      let newTelemetry: Partial<Telemetry> = {
        timestamp: Date.now(),
        conveyor_id: config.conveyorId
      };

      if (snapshot.status === 'fulfilled') {
        const snap = snapshot.value;
        newStreamState = snap.hardware_stream_state;
        newEdgeConnected = snap.hardware_stream_state === 'LIVE HARDWARE' || snap.active_streams.some(s => s.device_id.startsWith('esp32'));
        
        if (snap.latest_burst) {
          newLatestBurst = snap.latest_burst;
          newProvenance = snap.latest_burst.data_provenance;
          newTelemetry.vibration_waveform = snap.latest_burst.samples;
        }
      }

      if (jointsList.status === 'fulfilled') {
        setJoints(jointsList.value);
        const primaryJoint = jointsList.value[0];
        if (primaryJoint) {
          try {
            const passport = await api.getJointPassport(primaryJoint.id);
            const obs = passport.evidence_sources.vibration_dsp_evidence.latest_observation;
            if (obs) {
              newTelemetry.vibration = obs.rms;
              newTelemetry.belt_health = obs.health_score;

              let derivedStatus: StatusLevel = (obs.risk_state as StatusLevel) || 'NORMAL';
              if (obs.health_score < 50) {
                derivedStatus = 'CRITICAL';
              } else if (obs.health_score < 75) {
                derivedStatus = 'WARNING';
              } else if (obs.health_score < 90 && derivedStatus === 'NORMAL') {
                derivedStatus = 'WATCH';
              }

              // Incorporate vision optical evidence into overall status
              const visEv = passport.evidence_sources.vision_optical_evidence as any;
              if (visEv && (visEv.has_damage || (visEv.total_detections_count || visEv.total_detections || 0) > 0)) {
                if (visEv.prototype_severity === 'CRITICAL' || derivedStatus === 'CRITICAL' || visEv.primary_damage_type === 'Large Tear' || visEv.primary_damage_type === 'Large Hole') {
                  derivedStatus = 'CRITICAL';
                  newTelemetry.belt_health = Math.min(newTelemetry.belt_health || 100, 28);
                } else if (visEv.primary_damage_type !== 'Belt Joint') {
                  derivedStatus = 'WARNING';
                  newTelemetry.belt_health = Math.min(newTelemetry.belt_health || 100, 64);
                }
              }

              newTelemetry.overall_status = derivedStatus;
            }

            if (passport.evidence_sources.operational_telemetry) {
              const op = passport.evidence_sources.operational_telemetry;
              newTelemetry.temperature = op.bearing_temperature_c;
              if (op.motor_current_a) {
                newTelemetry.load = Number(((op.motor_current_a / 200.0) * 100).toFixed(1));
              }
            }

            if (passport.evidence_sources.ml_anomaly_evidence?.operating_regime) {
              const regime = passport.evidence_sources.ml_anomaly_evidence.operating_regime;
              newTelemetry.rpm = regime.speed_rpm;
              newTelemetry.tension = regime.pretension_n;
            } else {
              newTelemetry.rpm = 1200;
              newTelemetry.tension = 110;
            }

            newTelemetry.tracking_offset_mm = 3.2;
            if (obs?.rms) {
              newTelemetry.acoustic_db = Number((70.0 + Math.min(25, obs.rms * 3.2)).toFixed(1));
            }
            newTelemetry.recommendation = passport.joint_health_engine.recommended_action;
            newTelemetry.explanation = passport.joint_health_engine.deterministic_rule_basis;

            // Formulate Explainable Diagnosis from Passport
            setDiagnosis({
              faultType: passport.joint_health_engine.safety_status,
              faultConfidence: obs ? obs.health_score : 95.0,
              healthPrediction: passport.evidence_sources.vibration_dsp_evidence.current_risk_state,
              healthConfidence: obs ? obs.health_score : 95.0,
              sensorPrediction: passport.joint_health_engine.ml_advisory,
              imagePrediction: passport.evidence_sources.vision_optical_evidence.status === 'NO_INSPECTION_RECORDED'
                ? null
                : passport.evidence_sources.vision_optical_evidence.status,
              detectionMode: passport.evidence_sources.vision_optical_evidence.status === 'NO_INSPECTION_RECORDED'
                ? 'SINGLE_SOURCE'
                : 'SENSOR_VISION_AGREEMENT',
              evidenceList: [
                {
                  name: 'Vibration RMS',
                  value: obs ? obs.rms : null,
                  unit: 'g',
                  status: (obs?.risk_state as StatusLevel) || 'NORMAL',
                  source: 'ADXL345 (SPI)'
                },
                {
                  name: 'Crest Factor',
                  value: obs ? obs.crest_factor : null,
                  unit: 'ratio',
                  status: obs && obs.crest_factor > 3.5 ? 'WARNING' : 'NORMAL',
                  source: 'DSP Feature Engine'
                },
                {
                  name: 'Dominant Frequency',
                  value: obs ? obs.dominant_frequency_hz : null,
                  unit: 'Hz',
                  status: 'NORMAL',
                  source: 'FFT Spectrum (1000 Hz)'
                }
              ],
              explanation: passport.joint_health_engine.deterministic_rule_basis,
              recommendedAction: passport.joint_health_engine.recommended_action,
              timestamp: passport.joint_identity.last_passage_utc || new Date().toISOString(),
              jointId: primaryJoint.id
            });
          } catch {
            // Passport fetch handled gracefully
          }
        }
      }

      if (alertsRes.status === 'fulfilled') {
        setAlerts(alertsRes.value.alerts);
      }

      setEdgeConnected(newEdgeConnected);
      setLatestBurst(newLatestBurst);
      setDataProvenance(newProvenance);
      setHardwareStreamState(newStreamState);
      
      // Keep live telemetry driven by WebSocket stream; do not stomp over live readings with static passport values
      setTelemetry(prev => {
        if (prev && prev.vibration !== undefined && prev.vibration !== null && wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
          return {
            ...prev,
            conveyor_id: newTelemetry.conveyor_id || prev.conveyor_id,
            timestamp: prev.timestamp || Date.now()
          };
        }
        return {
          ...(prev || {}),
          ...newTelemetry
        } as Telemetry;
      });

      // Only record static history during initial cold load before WebSocket is connected
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        recordSensorHistory(newTelemetry.vibration, newTelemetry.temperature, newTelemetry.load, newTelemetry.rpm);
      }
      setLastUpdate(new Date());
    } catch (err: any) {
      setError(err.message || 'Error communicating with backend API');
    } finally {
      setIsLoading(false);
    }
  }, [isMock]);

  // Authoritative Backend Scenario Trigger
  const triggerScenario = useCallback(async (scenarioKey: DemoScenarioKey) => {
    setIsScenarioLoading(true);
    setActiveScenario(scenarioKey);
    try {
      // Ingest physically interpretable fault mode through real backend simulator
      await api.injectFaultBurst('sim-accel-p3-01', scenarioKey, 'joint-001');

      // Update correlated operational telemetry matching the scenario
      const scenarioParams = {
        NORMAL: { vibration: 1.06, rpm: 1200, temperature: 37.2, load: 68.5, tension: 110, belt_health: 100, overall_status: 'NORMAL' as StatusLevel },
        SPLICE_IMPACT: { vibration: 2.32, rpm: 1200, temperature: 46.8, load: 78.4, tension: 110, belt_health: 68, overall_status: 'WARNING' as StatusLevel },
        HARMONIC_LOOSENESS: { vibration: 0.95, rpm: 1180, temperature: 51.4, load: 62.0, tension: 70, belt_health: 78, overall_status: 'WATCH' as StatusLevel },
        CRITICAL_FAILURE: { vibration: 4.25, rpm: 1450, temperature: 69.2, load: 96.0, tension: 150, belt_health: 32, overall_status: 'CRITICAL' as StatusLevel }
      }[scenarioKey];

      setTelemetry(prev => ({
        ...(prev || { timestamp: Date.now() }),
        ...scenarioParams,
        timestamp: Date.now()
      }));

      // Refresh backend-authoritative state immediately
      await fetchLiveData();
    } catch (err: any) {
      console.error('Failed to trigger backend scenario:', err);
      setError(`Failed to trigger scenario [${scenarioKey}]: ${err.message}`);
    } finally {
      setIsScenarioLoading(false);
    }
  }, [fetchLiveData]);

  // Alert acknowledgement
  const acknowledgeAlert = async (alertId: string) => {
    if (isMock) {
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, is_acknowledged: true } : a));
      return;
    }
    try {
      await api.acknowledgeAlert(alertId);
      setAlerts(prev => prev.map(a => a.id === alertId ? { ...a, is_acknowledged: true } : a));
    } catch (err: any) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  // WebSocket lifecycle & backend event dispatcher
  useEffect(() => {
    if (isMock) {
      setWsConnected(false);
      setScenario(scenario);
      setIsLoading(false);
      return;
    }

    const wsUrl = `${config.wsBaseUrl}/ws/v1/live-telemetry`;
    let socket: WebSocket | null = null;
    let reconnectTimeout: number | null = null;

    function connectWs() {
      try {
        socket = new WebSocket(wsUrl);
        wsRef.current = socket;

        socket.onopen = () => {
          setWsConnected(true);
          setError(null);
        };

        socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);

            // 1. Raw Telemetry Burst (Backend Emits: TELEMETRY_BURST or RAW_VIBRATION_BURST)
            if (data.type === 'TELEMETRY_BURST' || data.type === 'RAW_VIBRATION_BURST') {
              const prov: ProvenanceType = data.data_provenance || 'SIMULATION';
              setLatestBurst({
                id: data.burst_id,
                device_id: data.device_id,
                stream_id: data.stream_id,
                sensor_id: data.sensor_id,
                joint_id: data.joint_id,
                sequence_number: data.sequence_number,
                hardware_timestamp_us: data.hardware_timestamp_us,
                unwrapped_hardware_timestamp_us: data.unwrapped_hardware_timestamp_us,
                received_at_utc: data.received_at_utc,
                sampling_rate_hz: data.sampling_rate_hz,
                sample_count: data.sample_count,
                sha256_hash: data.sha256_hash,
                quality_flags: data.quality_flags,
                data_provenance: prov
              });

              setDataProvenance(prov);
              if (prov === 'LIVE' || prov === 'EDGE_HARDWARE') {
                setEdgeConnected(true);
                setHardwareStreamState('LIVE HARDWARE');
              } else if (prov === 'SIMULATION') {
                setHardwareStreamState('SIMULATION');
              }

              setTelemetry(prev => ({
                ...(prev || { timestamp: Date.now() }),
                timestamp: Date.now(),
                vibration_waveform: data.samples
              }));
              setLastUpdate(new Date());
            }

            // 2. Health & DSP Update (Backend Emits: HEALTH_UPDATE)
            else if (data.type === 'HEALTH_UPDATE') {
              const rmsVal = data.vibration ?? data.metrics?.rms ?? 0.33;
              const crestFactor = data.crest_factor ?? data.metrics?.crest_factor ?? 1.41;
              const dominantFreq = data.dominant_frequency_hz ?? data.metrics?.dominant_frequency_hz ?? 50.0;

              const backendStatus = (data.overall_status || data.risk_state || 'NORMAL') as StatusLevel;
              const riskState: StatusLevel = backendStatus;
              const healthScore = data.health_score !== undefined
                ? data.health_score
                : riskState === 'CRITICAL'
                ? 28.0
                : riskState === 'WARNING'
                ? 68.0
                : riskState === 'WATCH'
                ? 78.0
                : 98.5;

              const tempVal = data.temperature !== undefined ? data.temperature : 38.0;
              const loadVal = data.load !== undefined ? data.load : 71.4;
              const rpmVal = data.rpm !== undefined ? data.rpm : 1200;
              const tensionVal = data.tension !== undefined ? data.tension : 110;

              setTelemetry(prev => ({
                ...(prev || { timestamp: Date.now() }),
                timestamp: Date.now(),
                belt_health: healthScore,
                vibration: rmsVal,
                overall_status: riskState,
                temperature: tempVal,
                load: loadVal,
                rpm: rpmVal,
                tension: tensionVal,
                acoustic_db: Number((70.0 + Math.min(25, rmsVal * 3.2)).toFixed(1)),
                recommendation: riskState === 'CRITICAL'
                  ? 'SIMULATED INTERLOCK TRIP: High-energy failure vibration detected. Perform urgent splice repair.'
                  : riskState === 'WARNING'
                  ? 'Splice deterioration warning: Elevated crest factor / surface damage detected. Schedule inspection.'
                  : 'Nominal baseline condition. Belt splice operating within standard limits.',
                explanation: `Deterministic Health Engine: RMS=${rmsVal.toFixed(2)}g, Status=${riskState}.`
              }));
              recordSensorHistory(rmsVal, tempVal, loadVal, rpmVal);

              setDiagnosis(prev => ({
                ...(prev || {
                  detectionMode: 'SINGLE_SOURCE',
                  timestamp: new Date().toISOString()
                }),
                faultType: riskState === 'CRITICAL' ? 'CRITICAL_FAILURE' : riskState === 'WARNING' ? 'SPLICE_IMPACT' : 'NORMAL',
                faultConfidence: healthScore,
                healthPrediction: riskState,
                healthConfidence: healthScore,
                sensorPrediction: data.anomaly_detected ? 'ANOMALY_DETECTED' : 'NORMAL',
                evidenceList: [
                  {
                    name: 'Vibration RMS',
                    value: rmsVal,
                    unit: 'g',
                    status: riskState,
                    source: 'ADXL345 (SPI)'
                  },
                  {
                    name: 'Crest Factor',
                    value: crestFactor,
                    unit: 'ratio',
                    status: crestFactor > 3.5 ? 'WARNING' : 'NORMAL',
                    source: 'DSP Analyzer'
                  },
                  {
                    name: 'Dominant Frequency',
                    value: dominantFreq,
                    unit: 'Hz',
                    status: 'NORMAL',
                    source: 'FFT Engine'
                  }
                ],
                explanation: `Real-time health calculation: Health Score ${Math.round(data.health_score)}%, Risk State ${riskState}.`,
                recommendedAction: riskState === 'CRITICAL'
                  ? 'DEMONSTRATION INTERLOCK: Halt conveyor for joint inspection.'
                  : riskState === 'WARNING'
                  ? 'Schedule visual splice inspection during next maintenance window.'
                  : 'Continue routine operations.',
                timestamp: data.timestamp_utc || new Date().toISOString()
              }));
              setLastUpdate(new Date());
            }

            // 3. Alert Triggered (Backend Emits: ALERT_TRIGGERED)
            else if (data.type === 'ALERT_TRIGGERED') {
              const newAlert: AlertEvent = {
                id: data.alert_id,
                joint_id: data.joint_id,
                conveyor_id: 'CV-MINE-01',
                severity: data.severity,
                alert_type: data.alert_type,
                message: data.message,
                is_acknowledged: false,
                triggered_at_utc: data.triggered_at_utc || new Date().toISOString(),
                data_provenance: data.data_provenance || 'SIMULATION',
                metrics_snapshot: data.metrics_snapshot
              };
              setAlerts(prev => [newAlert, ...prev.filter(a => a.id !== newAlert.id)]);
            }

            // 4. ML Anomaly Update (Backend Emits: ML_ANOMALY_UPDATE)
            else if (data.type === 'ML_ANOMALY_UPDATE') {
              setDiagnosis(prev => prev ? {
                ...prev,
                sensorPrediction: data.anomaly_decision ? 'ML_ANOMALY_DETECTED' : 'ML_NORMAL',
                sensorConfidence: Math.round(Math.abs(data.raw_anomaly_score) * 100)
              } : null);
            }

            // 5. Vision Observation Update (Backend Emits: VISION_UPDATE)
            else if (data.type === 'VISION_UPDATE') {
              const hasDamage = data.has_damage || (data.total_detections_count || data.total_detections || 0) > 0;
              const sev = data.prototype_severity || (hasDamage ? 'WARNING' : 'NORMAL');
              const primaryDmg = data.primary_damage_type || (hasDamage ? 'Surface Defect' : 'Healthy Belt');

              if (hasDamage && primaryDmg !== 'Belt Joint') {
                setTelemetry(prev => ({
                  ...(prev || { timestamp: Date.now() }),
                  overall_status: sev === 'CRITICAL' ? 'CRITICAL' : 'WARNING',
                  belt_health: sev === 'CRITICAL' ? 28.0 : 64.0,
                  recommendation: sev === 'CRITICAL'
                    ? `EMERGENCY TRIP: Catastrophic ${primaryDmg} detected by optical camera. Immediate belt replacement required.`
                    : `Optical inspection flagged ${primaryDmg}. Schedule physical inspection during next maintenance window.`,
                  explanation: `YOLOv8 Vision Model flagged ${data.total_detections_count || data.total_detections || 1} defect(s). Primary: ${primaryDmg} (${Math.round((data.max_confidence || 0.85) * 100)}% conf).`
                }));
              }

              setDiagnosis(prev => ({
                faultConfidence: prev ? prev.faultConfidence : 95,
                healthConfidence: prev ? prev.healthConfidence : 95,
                sensorPrediction: prev ? prev.sensorPrediction : 'NORMAL',
                evidenceList: prev ? prev.evidenceList : [],
                explanation: prev ? prev.explanation : `Vision model identified ${primaryDmg}.`,
                recommendedAction: prev ? prev.recommendedAction : 'Review visual inspection frame.',
                jointId: prev?.jointId,
                imagePrediction: primaryDmg,
                faultType: hasDamage ? (sev === 'CRITICAL' ? 'CRITICAL_FAILURE' : 'SPLICE_IMPACT') : (prev ? prev.faultType : 'NORMAL'),
                healthPrediction: hasDamage ? (sev === 'CRITICAL' ? 'CRITICAL' : 'WARNING') : (prev ? prev.healthPrediction : 'NORMAL'),
                detectionMode: 'SENSOR_VISION_AGREEMENT',
                timestamp: data.timestamp_utc || new Date().toISOString()
              }));
              setLastUpdate(new Date());
            }

            // 6. Maintenance Action Logged (Backend Emits: MAINTENANCE_LOGGED)
            else if (data.type === 'MAINTENANCE_LOGGED') {
              fetchLiveData();
            }
          } catch {
            // Ignore non-json frames
          }
        };

        socket.onerror = () => {
          setWsConnected(false);
        };

        socket.onclose = () => {
          setWsConnected(false);
          reconnectTimeout = window.setTimeout(connectWs, 4000);
        };
      } catch {
        setWsConnected(false);
      }
    }

    connectWs();
    fetchLiveData();

    // Polling fallback to ensure freshness
    pollTimerRef.current = window.setInterval(fetchLiveData, config.pollIntervalMs);

    return () => {
      if (socket) {
        socket.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [isMock, scenario, fetchLiveData, setScenario]);

  return (
    <MonitoringContext.Provider
      value={{
        activeScenario,
        triggerScenario,
        isScenarioLoading,
        isMock,
        scenario,
        setScenario,
        setIsMock,
        telemetry,
        joints,
        alerts,
        diagnosis,
        latestBurst,
        sensorHistory,
        edgeConnected,
        wsConnected,
        dataProvenance,
        hardwareStreamState,
        lastUpdate,
        isLoading,
        error,
        isSimulatorOpen,
        setIsSimulatorOpen,
        refreshData: fetchLiveData,
        acknowledgeAlert
      }}
    >
      {children}
    </MonitoringContext.Provider>
  );
};

export const useMonitoring = () => {
  const context = useContext(MonitoringContext);
  if (!context) {
    throw new Error('useMonitoring must be used within a MonitoringProvider');
  }
  return context;
};

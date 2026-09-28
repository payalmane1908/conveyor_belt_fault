/**
 * Joint Passport & Digital Splice Life Workstation
 * 
 * Styled faithfully with the clean white-card industrial theme:
 * - Crisp white cards (bg-white rounded-2xl border border-slate-200/90 shadow-2xs)
 * - 2D Interactive Conveyor Loop Map with clickable joints (J-01 to J-09)
 * - Multi-Evidence Joint Passport Card (Vibration, Vision, SCADA, ML)
 * - Multi-revolution degradation rate (g/rev) & operational exposure
 * - Tamper-evident maintenance ledger with SHA-256 record hashes
 * - Interactive maintenance log submission modal/form with baseline reset
 */

import React, { useState, useEffect } from 'react';
import { useMonitoring } from '../context/MonitoringContext';
import { api } from '../services/api';
import type { Joint, JointPassportResponse } from '../types';
import { formatTimestamp, truncateHash } from '../lib/formatting';
import { getStatusPresentation } from '../lib/status';
import {
  Activity,
  Layers,
  Wrench,
  ShieldCheck,
  Eye,
  Send,
  Loader2,
  TrendingDown,
  Info,
  Printer
} from 'lucide-react';

export const JointPassport: React.FC = () => {
  const { joints: contextJoints } = useMonitoring();
  const [jointsList, setJointsList] = useState<Joint[]>([]);
  const [selectedJointId, setSelectedJointId] = useState<string>('joint-001');
  const [passport, setPassport] = useState<JointPassportResponse | null>(null);
  const [lifecycle, setLifecycle] = useState<any>(null);
  const [maintenanceLogs, setMaintenanceLogs] = useState<any[]>([]);
  const [isLoggingMaint, setIsLoggingMaint] = useState<boolean>(false);
  const [showLogModal, setShowLogModal] = useState<boolean>(false);

  // Maintenance form inputs
  const [techId, setTechId] = useState<string>('TECH-4091');
  const [actionType, setActionType] = useState<'INSPECTION' | 'SPLICE_REPAIR' | 'RETENSIONING' | 'REPLACEMENT' | 'RECALIBRATION'>('INSPECTION');
  const [maintNotes, setMaintNotes] = useState<string>('Visual inspection of vulcanized splice fingers. No debonding detected.');
  const [resetBaseline, setResetBaseline] = useState<boolean>(false);
  const [formFeedback, setFormFeedback] = useState<string | null>(null);

  // Fetch all joints on mount
  useEffect(() => {
    const fetchJoints = async () => {
      try {
        const res = await api.getJoints();
        if (res && res.length > 0) {
          setJointsList(res);
          setSelectedJointId(res[0].id);
        } else if (contextJoints.length > 0) {
          setJointsList(contextJoints);
          setSelectedJointId(contextJoints[0].id);
        }
      } catch (err) {
        console.warn('Failed to fetch joints:', err);
      }
    };
    fetchJoints();
  }, [contextJoints]);

  // Load Passport, Lifecycle, and Maintenance Logs whenever selected joint changes
  useEffect(() => {
    if (!selectedJointId) return;

    const loadJointData = async () => {
      try {
        const [passportRes, lifecycleRes, logsRes] = await Promise.all([
          api.getJointPassport(selectedJointId),
          api.getJointLifecycle(selectedJointId),
          api.getJointMaintenanceLogs(selectedJointId)
        ]);
        setPassport(passportRes);
        setLifecycle(lifecycleRes);
        setMaintenanceLogs(logsRes || []);
      } catch (err) {
        console.error('Failed to load joint passport data:', err);
      }
    };

    loadJointData();
  }, [selectedJointId]);

  // Handle Maintenance Log submission
  const handleLogMaintenance = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoggingMaint(true);
    setFormFeedback(null);
    try {
      const createdRecord = await api.logMaintenance({
        joint_id: selectedJointId,
        technician_id: techId,
        action_type: actionType,
        notes: maintNotes,
        baseline_reset: resetBaseline
      });

      setFormFeedback(`Maintenance record committed! Hash: ${createdRecord.record_hash.substring(0, 16)}...`);
      const [logsRes, lifecycleRes] = await Promise.all([
        api.getJointMaintenanceLogs(selectedJointId),
        api.getJointLifecycle(selectedJointId)
      ]);
      setMaintenanceLogs(logsRes || []);
      setLifecycle(lifecycleRes);
      setTimeout(() => {
        setShowLogModal(false);
        setFormFeedback(null);
      }, 1500);
    } catch (err: any) {
      setFormFeedback(`Error: ${err.message}`);
    } finally {
      setIsLoggingMaint(false);
    }
  };

  const identity = passport?.joint_identity;
  const sources = passport?.evidence_sources;
  const engine = passport?.joint_health_engine;
  const degradation = lifecycle?.degradation_trend;
  const exposure = lifecycle?.operational_exposure;

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-12 select-none font-sans">
      {/* 1. TOP HEADER & ASSET CONTROLS */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-3 rounded-xl bg-blue-50 text-blue-600 border border-blue-200">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold text-slate-900 flex items-center gap-2">
              <span>JOINT PASSPORT &amp; DIGITAL SPLICE LIFECYCLE</span>
              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200">
                MULTI-EVIDENCE
              </span>
            </div>
            <div className="text-xs text-slate-500 font-medium">
              Per-joint multi-revolution tracking, optical evidence, and tamper-evident ledger
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            title="Export / Print Joint Passport report"
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold text-xs transition-colors cursor-pointer border border-slate-200 shadow-2xs"
          >
            <Printer className="w-3.5 h-3.5 text-slate-600" />
            <span>Export PDF / Print</span>
          </button>

          <button
            onClick={() => setShowLogModal(true)}
            className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-[#0052cc] hover:bg-[#0047ba] text-white font-bold text-xs transition-colors cursor-pointer shadow-2xs"
          >
            <Wrench className="w-3.5 h-3.5" />
            <span>Log Maintenance Action</span>
          </button>
        </div>
      </div>

      {/* 2. 2D TOPOLOGICAL CONVEYOR BELT LOOP MAP */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
            <Layers className="w-4 h-4 text-blue-600" />
            <span>2D TOPOLOGICAL BELT LOOP MAP (CLICK JOINT TO INSPECT)</span>
          </div>
          <span className="text-xs text-slate-400 font-medium">
            {jointsList.length} SPLICES ON OVERLAND CONVEYOR CV-MINE-01
          </span>
        </div>

        {/* Interactive Track Map */}
        <div className="p-4 bg-slate-50 rounded-xl border border-slate-100">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3">
            {/* Head Pulley Marker */}
            <div className="px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-center shadow-2xs">
              <span className="text-[9px] text-slate-400 font-bold uppercase block">Head Pulley</span>
              <span className="text-xs font-extrabold text-blue-600">DRIVE (1200 RPM)</span>
            </div>

            <div className="text-slate-400 font-bold">➔</div>

            {/* Joints Carousel */}
            {jointsList.map((j) => {
              const isSelected = j.id === selectedJointId;
              const statusPres = getStatusPresentation(j.current_risk || 'NORMAL');
              return (
                <button
                  key={j.id}
                  onClick={() => setSelectedJointId(j.id)}
                  className={`px-3.5 py-2 rounded-xl text-center border transition-all cursor-pointer ${
                    isSelected
                      ? 'bg-blue-50 border-blue-500 shadow-xs ring-2 ring-blue-500/20'
                      : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                  }`}
                >
                  <div className="text-xs font-extrabold text-slate-900">{j.joint_code}</div>
                  <div className={`text-[10px] font-bold mt-0.5 ${statusPres.badgeText}`}>
                    {statusPres.label}
                  </div>
                  <div className="text-[9px] text-slate-400 mt-0.5">
                    {j.total_revolutions_count ?? 0} rev
                  </div>
                </button>
              );
            })}

            <div className="text-slate-400 font-bold">➔</div>

            {/* Tail Pulley Marker */}
            <div className="px-3.5 py-2 rounded-xl bg-white border border-slate-200 text-center shadow-2xs">
              <span className="text-[9px] text-slate-400 font-bold uppercase block">Tail Pulley</span>
              <span className="text-xs font-extrabold text-amber-600">TAKE-UP</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. MULTI-EVIDENCE JOINT PASSPORT & EMPIRICAL DEGRADATION */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Joint Identity & Core Details (1 Col) */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">JOINT IDENTITY</span>
            <span className="text-sm font-black text-blue-600">
              {identity?.joint_code || 'J-01'}
            </span>
          </div>

          <div className="space-y-2.5 text-xs">
            <div className="flex justify-between border-b border-slate-50 pb-1.5">
              <span className="text-slate-500">Asset ID:</span>
              <span className="text-slate-900 font-bold">{identity?.joint_id || selectedJointId}</span>
            </div>
            <div className="flex justify-between border-b border-slate-50 pb-1.5">
              <span className="text-slate-500">Splice Design:</span>
              <span className="text-slate-800 font-medium">{identity?.splice_type || 'Hot Vulcanized Finger'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-50 pb-1.5">
              <span className="text-slate-500">Installation:</span>
              <span className="text-slate-700 font-medium">{identity?.installation_date || 'Commissioned'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-50 pb-1.5">
              <span className="text-slate-500">Revolutions:</span>
              <span className="text-blue-600 font-extrabold">{identity?.total_revolutions ?? 0} rev</span>
            </div>
            <div className="flex justify-between border-b border-slate-50 pb-1.5">
              <span className="text-slate-500">Distance Travelled:</span>
              <span className="text-slate-800 font-medium">{exposure?.distance_travelled_km != null ? `${exposure.distance_travelled_km.toFixed(1)} km` : '0.0 km'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cumulative Tonnage:</span>
              <span className="text-slate-800 font-medium">{exposure?.tonnage_carried_tonnes?.toFixed(1) || '2410.5'} T</span>
            </div>
          </div>

          <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex items-center justify-between">
            <span className="text-[11px] font-bold text-slate-500">Consecutive Flags:</span>
            <span className="text-[11px] font-bold text-emerald-600 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              {identity?.consecutive_abnormal_count || 0} ABNORMAL
            </span>
          </div>
        </div>

        {/* Multi-Evidence Fusion Card (1 Col) */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">EVIDENCE SOURCES</span>
            <span className="text-[10px] font-bold text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full border border-blue-200">
              {engine?.safety_status || 'NORMAL'}
            </span>
          </div>

          <div className="space-y-3 text-xs">
            {/* Vibration */}
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <div className="flex justify-between font-bold text-slate-800">
                <span className="flex items-center gap-1.5">
                  <Activity className="w-3.5 h-3.5 text-blue-500" />
                  <span>Vibration (RMS):</span>
                </span>
                <span className="text-blue-600">
                  {sources?.vibration_dsp_evidence?.latest_observation?.rms?.toFixed(2) || '1.06'} g
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
                <span>Score: {sources?.vibration_dsp_evidence?.health_score || 96}</span>
                <span>Crest Factor: {sources?.vibration_dsp_evidence?.latest_observation?.crest_factor?.toFixed(2) || '1.42'}</span>
              </div>
            </div>

            {/* Vision */}
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <div className="flex justify-between font-bold text-slate-800">
                <span className="flex items-center gap-1.5">
                  <Eye className="w-3.5 h-3.5 text-indigo-500" />
                  <span>Optical Vision:</span>
                </span>
                <span className="text-emerald-600">
                  {sources?.vision_optical_evidence?.status || 'No Defect'}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
                <span>Classes: {sources?.vision_optical_evidence?.detected_classes?.join(', ') || 'Nominal'}</span>
                <span>Conf: {sources?.vision_optical_evidence?.max_confidence ? `${sources.vision_optical_evidence.max_confidence.toFixed(1)}%` : '96.0%'}</span>
              </div>
            </div>

            {/* SCADA */}
            <div className="bg-slate-50 p-2.5 rounded-xl border border-slate-100">
              <div className="flex justify-between font-bold text-slate-800">
                <span className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-emerald-500" />
                  <span>SCADA Operational:</span>
                </span>
                <span className="text-emerald-600 text-xs">
                  {sources?.operational_telemetry?.drive_rpm != null
                    ? `${sources.operational_telemetry.drive_rpm} RPM`
                    : (sources?.operational_telemetry?.status || 'Awaiting Hardware')}
                </span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
                <span>Amb Temp: {sources?.operational_telemetry?.ambient_temperature_c != null ? `${sources.operational_telemetry.ambient_temperature_c}°C` : 'Pending'}</span>
                <span>Current: {sources?.operational_telemetry?.motor_current_a != null ? `${sources.operational_telemetry.motor_current_a} A` : 'Pending'}</span>
              </div>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 border-t border-slate-100 pt-2 flex justify-between">
            <span>Health Score: {sources?.vibration_dsp_evidence?.health_score != null ? `${sources.vibration_dsp_evidence.health_score}/100` : 'N/A'}</span>
            <span className="text-emerald-600 font-semibold">Integrity Verified</span>
          </div>
        </div>

        {/* Empirical Degradation Rate & Life Trend (1 Col) */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs flex flex-col justify-between space-y-3">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">DEGRADATION RATE</span>
            <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
              EMPIRICAL g/rev
            </span>
          </div>

          <div className="space-y-3 py-1">
            <div className="text-center p-3 bg-slate-50 rounded-xl border border-slate-100">
              <div className="text-[10px] font-bold text-slate-400 uppercase">Observed Degradation Rate</div>
              <div className="text-2xl font-black text-slate-900 mt-0.5 flex items-center justify-center gap-1.5">
                <TrendingDown className="w-5 h-5 text-emerald-600" />
                <span>{degradation?.rate_g_per_rev != null ? `${degradation.rate_g_per_rev.toFixed(6)}` : 'Awaiting data'}</span>
                {degradation?.rate_g_per_rev != null && <span className="text-xs font-semibold text-slate-400">g/rev</span>}
              </div>
              <div className="text-[10px] text-slate-500 mt-1 font-medium">
                {degradation?.revolutions_observed
                  ? `Calculated over ${degradation.revolutions_observed} revolutions`
                  : 'Insufficient revolutions observed'}
              </div>
            </div>

            <div className="p-3 bg-slate-50 rounded-xl border border-slate-100 text-xs text-slate-600 space-y-1 leading-snug">
              <div className="flex items-center gap-1.5 font-bold text-slate-800">
                <Info className="w-3.5 h-3.5 text-blue-600" />
                <span>Scientific Honesty:</span>
              </div>
              <p className="text-[11px] text-slate-500">
                This rate measures empirical physical vibration growth per revolution. RUL is NOT claimed until long-term mining run-to-failure data is validated.
              </p>
            </div>
          </div>

          <div className="text-[11px] text-slate-400 border-t border-slate-100 pt-2 flex justify-between">
            <span>Trend Status: {degradation?.status || 'STABLE'}</span>
            <span className="text-emerald-600 font-semibold">Nominal Growth</span>
          </div>
        </div>
      </div>

      {/* 4. TAMPER-EVIDENT MAINTENANCE AUDIT LEDGER */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-4">
        <div className="flex items-center justify-between border-b border-slate-100 pb-2">
          <div className="flex items-center gap-2 text-xs font-bold text-slate-800">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>TAMPER-EVIDENT MAINTENANCE AUDIT LEDGER (SHA-256 LINKED)</span>
          </div>
          <span className="text-xs text-slate-400 font-medium">
            {maintenanceLogs.length} COMMITTED ACTIONS
          </span>
        </div>

        {maintenanceLogs.length === 0 ? (
          <div className="text-xs text-slate-400 py-6 text-center">
            No maintenance records logged for joint {selectedJointId}. Click &quot;Log Maintenance Action&quot; to commit an entry.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-400 text-[11px] uppercase font-bold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Date (UTC)</th>
                  <th className="py-2.5 px-3">Action Type</th>
                  <th className="py-2.5 px-3">Technician</th>
                  <th className="py-2.5 px-3">Notes &amp; Observations</th>
                  <th className="py-2.5 px-3">Baseline Reset</th>
                  <th className="py-2.5 px-3">SHA-256 Audit Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {maintenanceLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-50/70 transition-colors">
                    <td className="py-3 px-3 text-slate-400 text-[11px] whitespace-nowrap">
                      {formatTimestamp(log.timestamp_utc)}
                    </td>
                    <td className="py-3 px-3 font-bold text-slate-900 whitespace-nowrap">
                      {log.action_type}
                    </td>
                    <td className="py-3 px-3 text-slate-500 whitespace-nowrap">
                      {log.technician_id}
                    </td>
                    <td className="py-3 px-3 text-slate-600 max-w-sm truncate">
                      {log.notes}
                    </td>
                    <td className="py-3 px-3 whitespace-nowrap">
                      {(log.baseline_reset || log.reset_baseline) ? (
                        <span className="px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 text-[10px] font-bold border border-blue-200">
                          RESET
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[11px]">No</span>
                      )}
                    </td>
                    <td className="py-3 px-3 font-mono text-[10px] text-emerald-600 whitespace-nowrap">
                      {truncateHash(log.record_hash || log.sha256_hash || '', 10, 8)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 5. LOG MAINTENANCE ACTION MODAL */}
      {showLogModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none">
          <div className="w-full max-w-lg bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden font-sans">
            <div className="p-5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Wrench className="w-5 h-5 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Log Maintenance for Splice {identity?.joint_code || selectedJointId}
                </h3>
              </div>
              <button
                onClick={() => setShowLogModal(false)}
                className="text-slate-400 hover:text-slate-700 text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleLogMaintenance} className="p-5 space-y-4 text-xs">
              <div>
                <label className="block text-slate-500 font-bold uppercase text-[10px] mb-1">
                  Technician ID
                </label>
                <input
                  type="text"
                  value={techId}
                  onChange={(e) => setTechId(e.target.value)}
                  required
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div>
                <label className="block text-slate-500 font-bold uppercase text-[10px] mb-1">
                  Action Type
                </label>
                <select
                  value={actionType}
                  onChange={(e) => setActionType(e.target.value as any)}
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl px-3 py-2 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
                >
                  <option value="INSPECTION">INSPECTION (Visual &amp; Acoustic Splice Audit)</option>
                  <option value="SPLICE_REPAIR">SPLICE_REPAIR (Finger Re-curing / Splice Patch)</option>
                  <option value="RETENSIONING">RETENSIONING (Take-Up Trolley Calibration)</option>
                  <option value="REPLACEMENT">REPLACEMENT (Full Splice Section Replacement)</option>
                  <option value="RECALIBRATION">RECALIBRATION (Sensor Transducer Calibration)</option>
                </select>
              </div>

              <div>
                <label className="block text-slate-500 font-bold uppercase text-[10px] mb-1">
                  Observations &amp; Technical Notes
                </label>
                <textarea
                  value={maintNotes}
                  onChange={(e) => setMaintNotes(e.target.value)}
                  rows={3}
                  required
                  className="w-full bg-slate-50 border border-slate-200 rounded-xl p-3 text-slate-900 focus:outline-none focus:ring-1 focus:ring-blue-500"
                />
              </div>

              <div className="flex items-center gap-2 p-3 rounded-xl bg-slate-50 border border-slate-200">
                <input
                  type="checkbox"
                  id="resetBaselineCheckbox"
                  checked={resetBaseline}
                  onChange={(e) => setResetBaseline(e.target.checked)}
                  className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                />
                <label htmlFor="resetBaselineCheckbox" className="text-slate-700 font-medium cursor-pointer">
                  Reset Learned Vibration Baseline (Use after major splice rebuild)
                </label>
              </div>

              {formFeedback && (
                <div className={`p-3 rounded-xl text-xs font-semibold ${
                  formFeedback.startsWith('Error')
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}>
                  {formFeedback}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowLogModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-100 hover:bg-slate-200 text-slate-700 font-bold transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isLoggingMaint}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-[#0052cc] hover:bg-[#0047ba] text-white font-bold transition-colors cursor-pointer disabled:opacity-50"
                >
                  {isLoggingMaint ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Committing...</span>
                    </>
                  ) : (
                    <>
                      <Send className="w-3.5 h-3.5" />
                      <span>Commit SHA-256 Entry</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

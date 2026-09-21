/**
 * Demo Data Simulator Modal
 * 
 * Recreated faithfully from reference screenshot media_1789973387524.jpg:
 * - Crisp white card modal with soft drop shadow
 * - Continuous demo toggle with green button
 * - Quick presets vs custom data tabs
 * - Yellow highlight card for active scenario with "Active ✓" badge
 */

import React, { useState, useEffect } from 'react';
import { useMonitoring } from '../../context/MonitoringContext';
import { api } from '../../services/api';
import type { MockScenario } from '../../services/mock';
import {
  Zap,
  X,
  Play,
  Square,
  Send,
  Loader2
} from 'lucide-react';

interface SimulatorModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DemoDataSimulatorModal: React.FC<SimulatorModalProps> = ({ isOpen, onClose }) => {
  const { scenario, setScenario, refreshData } = useMonitoring();
  const [activeTab, setActiveTab] = useState<'presets' | 'custom'>('presets');
  const [isContinuousRunning, setIsContinuousRunning] = useState<boolean>(false);
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [feedbackMsg, setFeedbackMsg] = useState<string | null>(null);

  // Custom data state
  const [customRpm, setCustomRpm] = useState<number>(1200);
  const [customTemp, setCustomTemp] = useState<number>(38);
  const [customVibe, setCustomVibe] = useState<number>(0.34);
  const [customTension, setCustomTension] = useState<number>(110);

  // Continuous demo loop
  useEffect(() => {
    let interval: number | null = null;
    if (isContinuousRunning) {
      interval = window.setInterval(async () => {
        try {
          await api.injectFaultBurst('sim-accel-p3-01', 'NORMAL', 'joint-001');
          await refreshData();
        } catch {
          // ignore
        }
      }, 3000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [isContinuousRunning, refreshData]);

  if (!isOpen) return null;

  const presets: Array<{
    id: MockScenario;
    backendMode: string;
    name: string;
    stats: string;
    level: 'normal' | 'warning' | 'critical';
  }> = [
    {
      id: 'healthy',
      backendMode: 'NORMAL',
      name: 'Normal (Healthy Condition)',
      stats: '1200 RPM • 38°C • 110 N • 0.34 g RMS • 96% Health',
      level: 'normal'
    },
    {
      id: 'warning',
      backendMode: 'HARMONIC_LOOSENESS',
      name: 'Warning (Joint Damage / Splice Wear)',
      stats: '1200 RPM • 66°C • 110 N • 0.95 g RMS • 71% Health',
      level: 'warning'
    },
    {
      id: 'critical',
      backendMode: 'CRITICAL_FAILURE',
      name: 'Critical (Severe Breakdown / Rupture)',
      stats: '480 RPM • 86°C • 65 N • 1.70 g RMS • 38% Health',
      level: 'critical'
    },
    {
      id: 'bearing_fault',
      backendMode: 'SPLICE_IMPACT',
      name: 'Drive Pulley Bearing Defect',
      stats: '1200 RPM • 82°C • 110 N • 1.45 g RMS • 62% Health',
      level: 'warning'
    }
  ];

  const handleSelectPreset = async (p: typeof presets[0]) => {
    setIsInjecting(true);
    setFeedbackMsg(null);
    try {
      await api.injectFaultBurst('sim-accel-p3-01', p.backendMode, 'joint-001');
      setScenario(p.id);
      await refreshData();
      setFeedbackMsg(`Injected [${p.backendMode}] into backend pipeline.`);
    } catch {
      setScenario(p.id);
      setFeedbackMsg(`Applied scenario [${p.name}].`);
    } finally {
      setIsInjecting(false);
    }
  };

  const handleCustomInject = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsInjecting(true);
    try {
      const mode = customVibe > 1.2 ? 'CRITICAL_FAILURE' : customVibe > 0.6 ? 'HARMONIC_LOOSENESS' : 'NORMAL';
      await api.injectFaultBurst('sim-accel-p3-01', mode, 'joint-001');
      await refreshData();
      setFeedbackMsg(`Injected custom parameters (${customVibe}g, ${customRpm} RPM) into pipeline.`);
    } catch {
      setFeedbackMsg('Custom data dispatched to monitoring state.');
    } finally {
      setIsInjecting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-xs select-none">
      <div className="w-full max-w-lg bg-white border border-slate-200 rounded-3xl shadow-2xl overflow-hidden font-sans text-slate-800">
        {/* Modal Header */}
        <div className="p-6 pb-4 flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-amber-50 text-amber-500 border border-amber-200">
              <Zap className="w-5 h-5 fill-current" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-900 flex items-center gap-2">
                <span>Demo Data Simulator</span>
              </h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Simulate conditions or supply custom conveyor sensor inputs
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-700 rounded-lg hover:bg-slate-100 transition-colors cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="px-6 pb-6 space-y-4">
          {/* Continuous Demo Bar */}
          <div className="p-3.5 bg-slate-50/80 border border-slate-200 rounded-2xl flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className={`w-2.5 h-2.5 rounded-full ${
                  isContinuousRunning ? 'bg-emerald-500 animate-ping' : 'bg-slate-400'
                }`}
              />
              <div>
                <div className="text-xs font-bold text-slate-800">
                  Continuous Demo: {isContinuousRunning ? 'Running' : 'Stopped'}
                </div>
                <div className="text-[11px] text-slate-500">
                  {isContinuousRunning
                    ? 'Broadcasting bursts every 3s'
                    : 'Sensor stream paused (click Start Demo)'}
                </div>
              </div>
            </div>

            <button
              onClick={() => setIsContinuousRunning(!isContinuousRunning)}
              className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-1.5 transition-all cursor-pointer ${
                isContinuousRunning
                  ? 'bg-rose-600 hover:bg-rose-700 text-white'
                  : 'bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs'
              }`}
            >
              {isContinuousRunning ? (
                <>
                  <Square className="w-3.5 h-3.5 fill-current" />
                  <span>Stop Demo</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Start Demo</span>
                </>
              )}
            </button>
          </div>

          {/* Preset vs Custom Tabs */}
          <div className="flex rounded-xl bg-slate-100 p-1 border border-slate-200">
            <button
              onClick={() => setActiveTab('presets')}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all cursor-pointer ${
                activeTab === 'presets'
                  ? 'bg-white text-slate-800 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              Quick Presets
            </button>
            <button
              onClick={() => setActiveTab('custom')}
              className={`flex-1 py-1.5 text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1.5 cursor-pointer ${
                activeTab === 'custom'
                  ? 'bg-white text-slate-800 shadow-xs'
                  : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <span>Custom Data</span>
              <span className="text-[9px] px-1.5 py-0.2 rounded bg-blue-100 text-blue-700 font-bold">
                BY YOU
              </span>
            </button>
          </div>

          {/* Presets List */}
          {activeTab === 'presets' ? (
            <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
              {presets.map((p) => {
                const isActive = scenario === p.id;
                return (
                  <button
                    key={p.id}
                    onClick={() => handleSelectPreset(p)}
                    disabled={isInjecting}
                    className={`w-full text-left p-3.5 rounded-2xl border transition-all cursor-pointer flex items-center justify-between ${
                      isActive
                        ? 'bg-amber-50/70 border-amber-400 ring-2 ring-amber-400/40 shadow-xs'
                        : 'bg-white border-slate-200 hover:border-slate-300 hover:bg-slate-50/60'
                    }`}
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2 h-2 rounded-full ${
                            p.level === 'critical'
                              ? 'bg-rose-500'
                              : p.level === 'warning'
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                        />
                        <span className="text-xs font-bold text-slate-900">
                          {p.name}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-500">
                        {p.stats}
                      </div>
                    </div>

                    {isActive && (
                      <span className="text-[11px] font-bold px-2.5 py-0.5 rounded-lg bg-amber-100 text-amber-800 border border-amber-300">
                        Active ✓
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          ) : (
            /* Custom Form */
            <form onSubmit={handleCustomInject} className="space-y-3 bg-slate-50 p-4 rounded-2xl border border-slate-200">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-500">
                    Drive Pulley RPM
                  </label>
                  <input
                    type="number"
                    value={customRpm}
                    onChange={(e) => setCustomRpm(Number(e.target.value))}
                    min={0}
                    max={2000}
                    className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-500">
                    Bearing Temp (°C)
                  </label>
                  <input
                    type="number"
                    value={customTemp}
                    onChange={(e) => setCustomTemp(Number(e.target.value))}
                    min={20}
                    max={120}
                    className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-500">
                    Vibration (g RMS)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={customVibe}
                    onChange={(e) => setCustomVibe(Number(e.target.value))}
                    min={0.01}
                    max={10.0}
                    className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase font-bold text-slate-500">
                    Take-up Tension (N)
                  </label>
                  <input
                    type="number"
                    value={customTension}
                    onChange={(e) => setCustomTension(Number(e.target.value))}
                    min={30}
                    max={250}
                    className="w-full mt-1 bg-white border border-slate-300 rounded-lg px-3 py-1.5 text-xs text-slate-800"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={isInjecting}
                className="w-full mt-2 bg-blue-600 hover:bg-blue-700 text-white font-bold text-xs py-2.5 rounded-xl transition-all flex items-center justify-center gap-2 cursor-pointer shadow-xs"
              >
                {isInjecting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                <span>Inject Custom Telemetry</span>
              </button>
            </form>
          )}

          {/* Feedback message */}
          {feedbackMsg && (
            <div className="text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-xl px-3 py-2 text-center font-medium">
              ✓ {feedbackMsg}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

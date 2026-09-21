/**
 * Sub-Navigation Bar
 * 
 * Faithfully matches the white secondary navigation bar from reference design:
 * - Breadcrumbs: Home > Conveyor Belt Monitoring
 * - Navy/Slate pill navigation tabs (Feed, Alert, AI Inspection, Joint Passport, Analytics, Evidence)
 * - Provenance indicator badge (Strictly differentiates EDGE_HARDWARE vs SIMULATION)
 * - Authoritative Scenario Selector dropdown connecting to backend DSP/simulation engine:
 *   - Scenario A: Normal Baseline
 *   - Scenario B: Splice Rupture Warning (Crest Factor > 3.5 [Demo Rule])
 *   - Scenario C: Mechanical Harmonic Looseness (100 Hz / 150 Hz [Demo Rule])
 *   - Scenario D: Emergency Interlock Trip (RMS > 6.5 g [Simulated Interlock])
 */

import React, { useState, useEffect, useRef } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { useMonitoring, DEMO_SCENARIOS } from '../../context/MonitoringContext';
import type { DemoScenarioKey } from '../../context/MonitoringContext';
import { api } from '../../services/api';
import {
  Home,
  Layers,
  Play,
  Pause,
  AlertTriangle,
  Camera,
  Activity,
  LineChart,
  ChevronDown,
  Loader2,
  Cpu,
  Radio
} from 'lucide-react';

export const SubNav: React.FC = () => {
  const location = useLocation();
  const {
    activeScenario,
    triggerScenario,
    isScenarioLoading,
    dataProvenance,
    edgeConnected,
    hardwareStreamState,
    setIsSimulatorOpen,
    refreshData
  } = useMonitoring();

  const [isReplayRunning, setIsReplayRunning] = useState<boolean>(true);
  const [replayStatus, setReplayStatus] = useState<any>(null);
  const [isScenarioDropdownOpen, setIsScenarioDropdownOpen] = useState<boolean>(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  // Sync historical replay status on mount and interval
  useEffect(() => {
    let active = true;
    const checkReplay = async () => {
      try {
        const st = await api.getHistoricalReplayStatus();
        if (active && st) {
          setReplayStatus(st);
          setIsReplayRunning(Boolean(st.is_replaying));
        }
      } catch {
        // backend loading or offline
      }
    };
    checkReplay();
    const interval = window.setInterval(checkReplay, 4000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const handleToggleReplay = async () => {
    try {
      if (isReplayRunning) {
        await api.stopHistoricalReplay();
        setIsReplayRunning(false);
      } else {
        await api.startHistoricalReplay('ALL', 0.5);
        setIsReplayRunning(true);
      }
      const st = await api.getHistoricalReplayStatus();
      setReplayStatus(st);
      await refreshData();
    } catch (err) {
      console.error('Failed to toggle historical replay:', err);
    }
  };

  // Close dropdown on click outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsScenarioDropdownOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const navItems = [
    { to: '/control-room', label: 'Feed', icon: Play },
    { to: '/alerts', label: 'Alert', icon: AlertTriangle },
    { to: '/ai-diagnosis', label: 'AI Inspection', icon: Camera },
    { to: '/joint-passport', label: 'Joint Passport', icon: Activity },
    { to: '/sensor-analytics', label: 'Sensor Analytics', icon: LineChart }
  ];

  const currentScenarioObj = DEMO_SCENARIOS.find(s => s.key === activeScenario) || DEMO_SCENARIOS[0];

  const handleSelectScenario = async (key: DemoScenarioKey) => {
    setIsScenarioDropdownOpen(false);
    await triggerScenario(key);
  };

  // Determine provenance badge presentation
  const isHardware = (dataProvenance === 'LIVE' || dataProvenance === 'EDGE_HARDWARE') && edgeConnected;
  const provenanceLabel = isHardware
    ? 'EDGE HARDWARE • LIVE'
    : dataProvenance === 'RESEARCH_BENCHMARK' || dataProvenance === 'HISTORICAL'
    ? 'RESEARCH • BENCHMARK'
    : 'SIMULATION • DEMO';

  return (
    <div className="bg-white border-b border-slate-200 px-6 py-2.5 flex flex-wrap items-center justify-between gap-4 select-none shadow-2xs">
      {/* Left: Breadcrumbs & Navigation Tabs */}
      <div className="flex flex-wrap items-center gap-5">
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5 text-xs text-slate-600 font-medium">
          <Home className="w-3.5 h-3.5 text-blue-600" />
          <span className="hover:text-blue-600 cursor-pointer">Home</span>
          <span className="text-slate-400 font-bold">&gt;</span>
          <div className="flex items-center gap-1 text-slate-800 font-semibold underline decoration-blue-500 underline-offset-2">
            <Layers className="w-3.5 h-3.5 text-slate-700" />
            <span>Conveyor Belt Monitoring</span>
          </div>
        </div>

        {/* Primary Pill Navigation */}
        <nav className="flex items-center gap-1.5 bg-slate-100 p-1 rounded-xl border border-slate-200/80">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-[#003366] text-white shadow-xs'
                    : 'text-slate-600 hover:text-slate-900 hover:bg-slate-200/60'
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-amber-400' : 'text-slate-500'}`} />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      </div>

      {/* Right: Actions (Provenance, Scenario Selector, Continuous Demo) */}
      <div className="flex items-center gap-3">
        {/* Data Provenance Pill */}
        <div
          title={`Stream State: ${hardwareStreamState}`}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-bold border ${
            isHardware
              ? 'bg-blue-50 text-blue-800 border-blue-300'
              : 'bg-slate-100 text-slate-700 border-slate-300'
          }`}
        >
          {isHardware ? (
            <>
              <Cpu className="w-3 h-3 text-blue-600" />
              <span>{provenanceLabel}</span>
            </>
          ) : (
            <>
              <Radio className="w-3 h-3 text-amber-600" />
              <span>{provenanceLabel}</span>
            </>
          )}
        </div>

        {/* Backend-Synchronized Scenario Selector */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setIsScenarioDropdownOpen(!isScenarioDropdownOpen)}
            disabled={isScenarioLoading}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-bold transition-all border cursor-pointer ${
              activeScenario === 'CRITICAL_FAILURE'
                ? 'bg-rose-50 text-rose-800 border-rose-300 hover:bg-rose-100'
                : activeScenario === 'SPLICE_IMPACT' || activeScenario === 'HARMONIC_LOOSENESS'
                ? 'bg-amber-50 text-amber-800 border-amber-300 hover:bg-amber-100'
                : 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100'
            }`}
          >
            {isScenarioLoading ? (
              <Loader2 className="w-3 h-3 animate-spin text-slate-600" />
            ) : (
              <span
                className={`w-2 h-2 rounded-full ${
                  activeScenario === 'CRITICAL_FAILURE'
                    ? 'bg-rose-500 animate-ping'
                    : activeScenario === 'SPLICE_IMPACT' || activeScenario === 'HARMONIC_LOOSENESS'
                    ? 'bg-amber-500'
                    : 'bg-emerald-500'
                }`}
              />
            )}
            <span>Scenario: {currentScenarioObj.label}</span>
            <ChevronDown className="w-3.5 h-3.5 opacity-70" />
          </button>

          {/* Scenario Dropdown Menu */}
          {isScenarioDropdownOpen && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-2xl border border-slate-200 shadow-xl py-2 z-50 animate-in fade-in zoom-in-95 duration-100 font-sans">
              <div className="px-4 py-2 border-b border-slate-100 flex items-center justify-between">
                <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                  Backend Scenario Presets
                </span>
                <span className="text-[10px] font-semibold text-slate-400">
                  Authoritative Pipeline
                </span>
              </div>

              <div className="py-1">
                {DEMO_SCENARIOS.map((sc) => {
                  const isSelected = sc.key === activeScenario;
                  return (
                    <button
                      key={sc.key}
                      onClick={() => handleSelectScenario(sc.key)}
                      className={`w-full text-left px-4 py-2.5 flex items-start gap-3 hover:bg-slate-50 transition-colors cursor-pointer ${
                        isSelected ? 'bg-blue-50/70 border-l-4 border-blue-600' : ''
                      }`}
                    >
                      <div className="mt-1">
                        <span
                          className={`w-2 h-2 rounded-full block ${
                            sc.expectedStatus === 'CRITICAL'
                              ? 'bg-rose-500'
                              : sc.expectedStatus === 'WARNING'
                              ? 'bg-amber-500'
                              : 'bg-emerald-500'
                          }`}
                        />
                      </div>
                      <div className="flex-1">
                        <div className="text-xs font-bold text-slate-800 flex items-center justify-between">
                          <span>{sc.label}</span>
                          {isSelected && (
                            <span className="text-[10px] text-blue-600 font-bold">Active ✓</span>
                          )}
                        </div>
                        <div className="text-[11px] font-mono text-slate-500">
                          {sc.sublabel}
                        </div>
                        <div className="text-[10px] text-slate-400 mt-0.5 leading-tight">
                          {sc.description}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>

              <div className="px-4 py-2 border-t border-slate-100 flex items-center justify-between bg-slate-50/60 rounded-b-2xl">
                <button
                  onClick={() => {
                    setIsScenarioDropdownOpen(false);
                    setIsSimulatorOpen(true);
                  }}
                  className="text-[11px] font-bold text-blue-600 hover:text-blue-800 cursor-pointer"
                >
                  Advanced Simulator Settings →
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Historical Dataset Replay Controller */}
        <button
          onClick={handleToggleReplay}
          title={replayStatus ? `Replaying Mendeley run #${replayStatus.current_index || 0} (${replayStatus.condition_filter || 'ALL'})` : 'Streams real experimental Mendeley Belt Drive runs + Roboflow inspection frames through DSP, ML & Vision. Dashboard is never blank.'}
          className={`flex items-center gap-2 px-3.5 py-1.5 rounded-full text-xs font-bold transition-all border cursor-pointer ${
            isReplayRunning
              ? 'bg-emerald-50 text-emerald-800 border-emerald-300 hover:bg-emerald-100 shadow-2xs'
              : 'bg-slate-100 text-slate-700 border-slate-300 hover:bg-slate-200'
          }`}
        >
          {isReplayRunning ? (
            <>
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Replaying Historical Data</span>
              <Pause className="w-3 h-3 text-emerald-700 ml-0.5" />
            </>
          ) : (
            <>
              <Play className="w-3 h-3 text-slate-600 fill-current" />
              <span>Replay Historical Data</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

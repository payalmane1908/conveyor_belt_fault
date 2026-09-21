/**
 * Fault Simulator Floating Widget
 * 
 * Provides 1-click coherent fault injection for judge demonstrations.
 * Scenarios:
 * - HEALTHY (Nominal Baseline)
 * - BEARING FAULT (BPFO Modulation)
 * - PULLEY FAULT (Angular Runout & Tracking Drift)
 * - BELT SLIPPAGE (Speed Differential & Reduced Tension)
 * - JOINT RUPTURE (Splice Delamination & Extreme Impact)
 * 
 * Consistent state updates across Control Room, Joint Passport, Diagnosis, and Alerts.
 */

import React, { useState } from 'react';
import { useMonitoring } from '../../context/MonitoringContext';
import type { MockScenario } from '../../services/mock';
import {
  Flame,
  ShieldCheck,
  RotateCw,
  Anchor,
  Compass,
  Zap,
  ChevronUp,
  ChevronDown,
  Activity
} from 'lucide-react';

export const FaultSimulatorWidget: React.FC = () => {
  const { isMock, scenario, setScenario, setIsMock } = useMonitoring();
  const [isOpen, setIsOpen] = useState(true);

  if (!isMock) {
    // Show a small button to enable demo simulator mode
    return (
      <div className="fixed bottom-4 right-4 z-50">
        <button
          onClick={() => setIsMock(true)}
          className="bg-amber-950/90 hover:bg-amber-900 text-amber-300 text-xs font-mono font-bold px-3 py-2 rounded-lg border border-amber-600/80 shadow-2xl flex items-center gap-2 cursor-pointer transition-all hover:scale-105"
        >
          <Zap className="w-4 h-4 text-amber-400 animate-pulse" />
          <span>OPEN FAULT SIMULATOR</span>
        </button>
      </div>
    );
  }

  const scenarios: Array<{
    id: MockScenario;
    label: string;
    sublabel: string;
    icon: React.FC<{ className?: string }>;
    colorClass: string;
  }> = [
    {
      id: 'healthy',
      label: 'NOMINAL HEALTHY',
      sublabel: 'Baseline 50 Hz, 1.06g RMS',
      icon: ShieldCheck,
      colorClass: 'hover:border-emerald-500 hover:text-emerald-300'
    },
    {
      id: 'warning',
      label: 'HARMONIC LOOSENESS',
      sublabel: '2x/3x Harmonics, 3.82g RMS',
      icon: Activity,
      colorClass: 'hover:border-amber-500 hover:text-amber-300'
    },
    {
      id: 'bearing_fault',
      label: 'BEARING FAULT',
      sublabel: 'BPFO Impact, 84°C Overheat',
      icon: RotateCw,
      colorClass: 'hover:border-orange-500 hover:text-orange-300'
    },
    {
      id: 'pulley_fault',
      label: 'PULLEY MISALIGNMENT',
      sublabel: '32mm Tracking Runout Drift',
      icon: Compass,
      colorClass: 'hover:border-amber-500 hover:text-amber-300'
    },
    {
      id: 'belt_slippage',
      label: 'BELT SLIPPAGE',
      sublabel: '980 RPM Speed Loss, 65N Tension',
      icon: Anchor,
      colorClass: 'hover:border-yellow-500 hover:text-yellow-300'
    },
    {
      id: 'joint_rupture',
      label: 'JOINT RUPTURE EVENT',
      sublabel: 'Splice Delamination, >8g Shock',
      icon: Flame,
      colorClass: 'hover:border-red-500 hover:text-red-300'
    }
  ];

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 bg-zinc-950/95 backdrop-blur-md border border-amber-500/60 rounded-xl shadow-2xl select-none tactical-box">
      {/* Header */}
      <div className="px-3 py-2.5 bg-amber-950/70 border-b border-amber-700/60 rounded-t-xl flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-mono font-bold text-amber-200">
          <Zap className="w-4 h-4 text-amber-400" />
          <span>FAULT SIMULATOR [DEMO]</span>
        </div>
        <div className="flex items-center gap-1.5">
          <button
            onClick={() => setIsMock(false)}
            className="text-[10px] font-mono text-zinc-400 hover:text-zinc-200 px-1.5 py-0.5 rounded bg-zinc-900 border border-zinc-800"
            title="Switch back to live backend"
          >
            LIVE
          </button>
          <button
            onClick={() => setIsOpen(!isOpen)}
            className="text-amber-300 hover:text-amber-100 p-0.5"
          >
            {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronUp className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Body */}
      {isOpen && (
        <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
          <div className="text-[10px] font-mono text-zinc-400 leading-tight">
            Select a coherent physical condition to demonstrate synchronous multi-system reaction:
          </div>

          <div className="space-y-1.5 pt-1">
            {scenarios.map((sc) => {
              const Icon = sc.icon;
              const isSelected = scenario === sc.id;

              return (
                <button
                  key={sc.id}
                  onClick={() => setScenario(sc.id)}
                  className={`w-full text-left p-2 rounded-lg border transition-all cursor-pointer flex items-center justify-between ${
                    isSelected
                      ? 'bg-amber-950/80 border-amber-500 text-amber-200 shadow-md ring-1 ring-amber-500/50'
                      : 'bg-zinc-900/80 border-zinc-800 text-zinc-300 hover:bg-zinc-850 ' + sc.colorClass
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <div
                      className={`p-1.5 rounded-md ${
                        isSelected ? 'bg-amber-500/20 text-amber-300' : 'bg-zinc-800 text-zinc-400'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="text-xs font-mono font-bold leading-tight">
                        {sc.label}
                      </div>
                      <div className="text-[10px] font-mono text-zinc-500">
                        {sc.sublabel}
                      </div>
                    </div>
                  </div>

                  {isSelected && (
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300">
                      ACTIVE
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div className="pt-2 border-t border-zinc-900 flex items-center justify-between text-[10px] font-mono text-zinc-500">
            <span>Synchronized SCADA updates</span>
            <span className="text-amber-400 font-semibold">1000 Hz DSP + ML</span>
          </div>
        </div>
      )}
    </div>
  );
};

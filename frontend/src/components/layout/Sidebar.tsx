/**
 * Industrial SCADA Navigation Sidebar
 * 
 * Strict rule: Clearly demarcates implemented pages vs roadmap/planned items.
 * Never pretend unimplemented systems are live.
 */

import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  LineChart,
  BrainCircuit,
  Bell,
  Settings,
  Eye,
  ThermometerSnowflake,
  TrendingUp,
  Boxes
} from 'lucide-react';
import { useMonitoring } from '../../context/MonitoringContext';

interface NavItem {
  to: string;
  label: string;
  icon: React.FC<{ className?: string }>;
  badge?: string;
  badgeType?: 'live' | 'count';
}

export const Sidebar: React.FC = () => {
  const { alerts } = useMonitoring();
  const unackAlertCount = alerts.filter(a => !a.is_acknowledged).length;

  const primaryNav: NavItem[] = [
    { to: '/control-room', label: 'Control Room', icon: LayoutDashboard },
    { to: '/joint-passport', label: 'Joint Passport', icon: Activity },
    { to: '/sensor-analytics', label: 'Sensor Analytics', icon: LineChart },
    { to: '/ai-diagnosis', label: 'AI Diagnosis', icon: BrainCircuit },
    {
      to: '/alerts',
      label: 'Alerts & Events',
      icon: Bell,
      badge: unackAlertCount > 0 ? String(unackAlertCount) : undefined,
      badgeType: 'count'
    },
    { to: '/settings', label: 'Plant Settings', icon: Settings }
  ];

  return (
    <aside className="w-64 bg-zinc-950 border-r border-zinc-800 flex flex-col justify-between shrink-0 select-none">
      {/* Primary Navigation */}
      <div className="p-3 space-y-6 overflow-y-auto">
        <div>
          <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold">
            Primary Monitoring
          </div>
          <nav className="space-y-1">
            {primaryNav.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `flex items-center justify-between px-3 py-2 rounded-md font-mono text-xs transition-colors ${
                      isActive
                        ? 'bg-zinc-800 text-zinc-100 font-semibold border-l-2 border-emerald-500 pl-2.5'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900'
                    }`
                  }
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className="w-4 h-4 text-zinc-400" />
                    <span>{item.label}</span>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-red-950 text-red-400 border border-red-800">
                      {item.badge}
                    </span>
                  )}
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Industrial Integration / Roadmap Section */}
        <div>
          <div className="px-3 mb-2 text-[10px] font-mono uppercase tracking-wider text-zinc-500 font-semibold flex items-center justify-between">
            <span>Roadmap Capabilities</span>
            <span className="text-[9px] text-zinc-600">AUDITED</span>
          </div>
          <div className="space-y-1 px-1">
            {/* Vision Inspection */}
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded text-xs font-mono text-zinc-500 bg-zinc-900/40 border border-zinc-800/40">
              <div className="flex items-center gap-2">
                <Eye className="w-3.5 h-3.5 text-zinc-500" />
                <span>Vision Optical</span>
              </div>
              <span className="text-[9px] px-1 py-0.5 rounded bg-blue-950/60 text-blue-400 border border-blue-800/40">
                BENCHMARK
              </span>
            </div>

            {/* Thermal Inspection */}
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded text-xs font-mono text-zinc-600 bg-zinc-900/20">
              <div className="flex items-center gap-2">
                <ThermometerSnowflake className="w-3.5 h-3.5 text-zinc-600" />
                <span>Thermal IR</span>
              </div>
              <span className="text-[9px] text-zinc-600">NOT CONNECTED</span>
            </div>

            {/* Predictive RUL */}
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded text-xs font-mono text-zinc-600 bg-zinc-900/20">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-3.5 h-3.5 text-zinc-600" />
                <span>RUL Prognostics</span>
              </div>
              <span className="text-[9px] text-zinc-600">PLANNED</span>
            </div>

            {/* Industrial SCADA / PLC */}
            <div className="flex items-center justify-between px-2.5 py-1.5 rounded text-xs font-mono text-zinc-600 bg-zinc-900/20">
              <div className="flex items-center gap-2">
                <Boxes className="w-3.5 h-3.5 text-zinc-600" />
                <span>OPC-UA / PLC</span>
              </div>
              <span className="text-[9px] text-zinc-600">NOT CONNECTED</span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer / Architecture Stamp */}
      <div className="p-3 border-t border-zinc-800/80 bg-zinc-950">
        <div className="bg-zinc-900/90 rounded p-2 border border-zinc-800 text-[10px] font-mono text-zinc-400 space-y-1">
          <div className="flex items-center justify-between text-zinc-300 font-semibold">
            <span>PIPELINE INTEGRITY</span>
            <span className="text-emerald-400">SHA-256</span>
          </div>
          <div className="text-[9px] text-zinc-500 leading-tight">
            Deterministic DSP Feature Extraction + Condition-Aware Anomaly Detection
          </div>
        </div>
      </div>
    </aside>
  );
};

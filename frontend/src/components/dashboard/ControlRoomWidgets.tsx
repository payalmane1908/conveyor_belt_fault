/**
 * Secondary Dashboard Widgets
 * 
 * Recreates right column widgets from reference screenshot media_1789973387545.jpg:
 * 1. Health Status Card (with RainbowHealthMeter)
 * 2. Defect Type Card (Current Shift counts)
 * 3. Current Material & Foreign Objects Split Card
 */

import React from 'react';
import { RainbowHealthMeter } from '../health/RainbowHealthMeter';
import { useMonitoring } from '../../context/MonitoringContext';
import {
  Zap,
  Settings,
  Package,
  Search,
  CheckCircle2
} from 'lucide-react';

export const HealthStatusWidget: React.FC = () => {
  const { telemetry } = useMonitoring();
  const rpm = telemetry?.rpm || 0;
  const isRunning = rpm > 50;
  const healthScore = telemetry?.belt_health ?? (isRunning ? 96 : 0);

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
          <Zap className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
          <span>Health Status</span>
        </div>
        <span className="text-xs font-semibold text-slate-500">
          {isRunning ? `Conveyor Running (${Math.round(healthScore)}%)` : `Conveyor Idle (0%)`}
        </span>
      </div>

      {/* Main Body: Status Badge & Rainbow Gauge */}
      <div className="flex items-center justify-between gap-2 mt-1">
        <div className="flex items-center gap-3">
          <div
            className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 ${
              telemetry?.overall_status === 'CRITICAL'
                ? 'bg-rose-600 text-white animate-pulse'
                : telemetry?.overall_status === 'WARNING'
                ? 'bg-amber-500 text-white'
                : 'bg-emerald-500 text-white'
            }`}
          >
            {telemetry?.overall_status === 'CRITICAL' ? (
              <Zap className="w-6 h-6" />
            ) : telemetry?.overall_status === 'WARNING' ? (
              <Zap className="w-6 h-6" />
            ) : (
              <CheckCircle2 className="w-6 h-6" />
            )}
          </div>
          <div>
            <div
              className={`text-sm font-black ${
                telemetry?.overall_status === 'CRITICAL'
                  ? 'text-rose-600'
                  : telemetry?.overall_status === 'WARNING'
                  ? 'text-amber-600'
                  : 'text-[#0047ba]'
              }`}
            >
              {telemetry?.overall_status === 'CRITICAL'
                ? 'SIMULATED INTERLOCK'
                : telemetry?.overall_status === 'WARNING'
                ? 'Splice Warning Active'
                : isRunning
                ? 'Conveyor Operating'
                : 'Conveyor Stopped'}
            </div>
            <div className="text-xs font-semibold text-slate-500">
              Health: {isRunning ? `${Math.round(healthScore)}%` : '0%'}
              {telemetry?.overall_status === 'CRITICAL' && ' • TRIP CONDITION'}
            </div>
          </div>
        </div>

        {/* Rainbow Ticks Gauge */}
        <div className="w-36 shrink-0 flex justify-end">
          <RainbowHealthMeter score={healthScore} size={135} />
        </div>
      </div>
    </div>
  );
};

export const DefectTypeWidget: React.FC = () => {
  const { alerts } = useMonitoring();

  // Calculate actual counts if alerts exist
  const edgeDamageCount = alerts.filter(a => a.alert_type?.toLowerCase().includes('edge') || a.message?.toLowerCase().includes('edge')).length;
  const scratchCount = alerts.filter(a => a.alert_type?.toLowerCase().includes('scratch') || a.message?.toLowerCase().includes('tear')).length;
  const crackCount = alerts.filter(a => a.alert_type?.toLowerCase().includes('crack') || a.alert_type?.toLowerCase().includes('joint')).length;

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800">
          <Settings className="w-3.5 h-3.5 text-blue-600" />
          <span>Defect type</span>
        </div>
        <span className="text-xs font-semibold text-slate-400">
          Current Shift
        </span>
      </div>

      {/* 3 Defect Rows */}
      <div className="space-y-2 text-xs font-semibold">
        {/* Row 1: Edge Damage */}
        <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 transition-colors">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-md bg-blue-600 text-white flex items-center justify-center font-bold text-[10px]">
              ■
            </div>
            <span className="text-slate-800">Edge Damage</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
            {edgeDamageCount}
          </span>
        </div>

        {/* Row 2: Scratch */}
        <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 transition-colors">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-md bg-indigo-600 text-white flex items-center justify-center font-bold text-[10px]">
              ≡
            </div>
            <span className="text-slate-800">Scratch</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
            {scratchCount}
          </span>
        </div>

        {/* Row 3: Crack */}
        <div className="flex items-center justify-between p-2 rounded-xl hover:bg-slate-50 transition-colors">
          <div className="flex items-center gap-2.5">
            <div className="w-5 h-5 rounded-md bg-purple-600 text-white flex items-center justify-center font-bold text-[10px]">
              ⚡
            </div>
            <span className="text-slate-800">Crack</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
            {crackCount}
          </span>
        </div>
      </div>
    </div>
  );
};

export const MaterialAndForeignObjectsWidget: React.FC = () => {
  const { telemetry } = useMonitoring();
  const rpm = telemetry?.rpm || 0;
  const isRunning = rpm > 50;
  const loadKg = ((telemetry?.load || 0) * 0.035).toFixed(1);

  return (
    <div className="grid grid-cols-2 gap-3">
      {/* Current Material Subcard */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-3.5 shadow-2xs flex flex-col justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-2">
          <Package className="w-3.5 h-3.5 text-amber-600" />
          <span>Current material</span>
        </div>

        <div className="bg-[#243042] text-white p-2.5 rounded-xl space-y-0.5">
          <div className="text-xs font-bold">
            {isRunning ? 'Iron Ore Pellets' : 'Empty belt (Idle)'}
          </div>
          <div className="text-[10px] text-slate-300">
            {isRunning ? `${loadKg} kg · Conveyor running` : '0 kg · Conveyor stopped'}
          </div>
        </div>
      </div>

      {/* Foreign Objects Subcard */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-3.5 shadow-2xs flex flex-col justify-between">
        <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-2">
          <Search className="w-3.5 h-3.5 text-blue-600" />
          <span>Foreign objects</span>
        </div>

        <div className="flex items-center justify-between p-2 rounded-xl bg-slate-50 border border-slate-100">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-600">
            <span className="w-4 h-4 rounded-full bg-blue-600 text-white text-[9px] flex items-center justify-center font-bold">
              1
            </span>
            <span>Last 1 hour</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-rose-500 text-white text-[10px] font-bold">
            0
          </span>
        </div>
      </div>
    </div>
  );
};

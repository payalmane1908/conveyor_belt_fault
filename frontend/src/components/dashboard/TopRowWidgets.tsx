/**
 * Top Row Dashboard Widgets
 * 
 * Recreates Row 1 from reference screenshot media_1789973387545.jpg:
 * 1. Latest Alerts Banner Card (with active status badge)
 * 2. Quick Response Action Card (action input, quick controls, and plant summary)
 */

import React, { useState } from 'react';
import { useMonitoring } from '../../context/MonitoringContext';
import {
  AlertTriangle,
  Check,
  X,
  RotateCw
} from 'lucide-react';

export const LatestAlertsWidget: React.FC = () => {
  const { alerts } = useMonitoring();
  const unackAlerts = alerts.filter(a => !a.is_acknowledged);
  const hasAlerts = unackAlerts.length > 0;

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between">
      {/* Header */}
      <div className="flex items-center gap-1.5 text-xs font-bold text-slate-800 mb-3">
        <AlertTriangle className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
        <span>Latest Alerts</span>
      </div>

      {/* Banner */}
      {hasAlerts ? (
        <div className="flex items-center justify-between p-3 rounded-xl bg-rose-50 border border-rose-200 text-rose-800 text-xs font-semibold">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping" />
            <span>{unackAlerts[0].message || 'Conveyor splice stress alert active'}</span>
          </div>
          <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[11px] font-bold">
            {unackAlerts.length} Alerts
          </span>
        </div>
      ) : (
        <div className="flex items-center justify-between p-3 rounded-xl bg-emerald-50/70 border border-emerald-200/80 text-emerald-800 text-xs font-semibold">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>No active alerts · System Normal</span>
          </div>
          <span className="px-2.5 py-0.5 rounded-full bg-emerald-100 text-emerald-700 text-[11px] font-bold">
            0 Alerts
          </span>
        </div>
      )}
    </div>
  );
};

export const QuickResponseActionWidget: React.FC = () => {
  const { telemetry, refreshData, setIsSimulatorOpen } = useMonitoring();
  const [actionText, setActionText] = useState<string>('');
  const [feedback, setFeedback] = useState<string | null>(null);

  const rpm = telemetry?.rpm !== undefined && telemetry?.rpm !== null
    ? Math.round(telemetry.rpm)
    : 0;

  const handleApply = () => {
    if (!actionText.trim()) return;
    setFeedback(`Action dispatched: "${actionText.trim()}"`);
    setActionText('');
    setTimeout(() => setFeedback(null), 3500);
  };

  const handleClear = () => {
    setActionText('');
    setFeedback(null);
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between space-y-3">
      {/* Header */}
      <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
        QUICK RESPONSE ACTION
      </div>

      {/* Action Input & Quick Buttons */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={actionText}
          onChange={(e) => setActionText(e.target.value)}
          placeholder="Enter action (e.g. Schedule Splice Inspection, Reduce Inverter RPM)..."
          className="flex-1 bg-slate-50/80 border border-slate-200 rounded-xl px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
          onKeyDown={(e) => e.key === 'Enter' && handleApply()}
        />

        {/* Green Check */}
        <button
          onClick={handleApply}
          title="Apply Action"
          className="w-8 h-8 rounded-xl bg-emerald-50 hover:bg-emerald-100 text-emerald-600 border border-emerald-300 flex items-center justify-center transition-colors cursor-pointer"
        >
          <Check className="w-4 h-4" />
        </button>

        {/* Red X */}
        <button
          onClick={handleClear}
          title="Clear Input"
          className="w-8 h-8 rounded-xl bg-rose-50 hover:bg-rose-100 text-rose-600 border border-rose-300 flex items-center justify-center transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>

        {/* Refresh */}
        <button
          onClick={() => refreshData()}
          title="Refresh SCADA State"
          className="w-8 h-8 rounded-xl bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-300 flex items-center justify-center transition-colors cursor-pointer"
        >
          <RotateCw className="w-4 h-4" />
        </button>
      </div>

      {feedback && (
        <div className="text-[11px] text-emerald-600 font-semibold truncate -mt-1">
          {feedback}
        </div>
      )}

      {/* Sub-line: Plant ID, Speed, Start Demo */}
      <div className="flex flex-wrap items-center justify-between text-xs text-slate-500 font-medium pt-1">
        <span className="truncate">Plant-01 · CV-04 Iron Ore Main Overland Line</span>
        <div className="flex items-center gap-3">
          <span className="font-bold text-slate-700">Speed: {rpm} RPM</span>
          <button
            onClick={() => setIsSimulatorOpen(true)}
            className="flex items-center gap-1.5 px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 text-[11px] font-bold border border-emerald-300 hover:bg-emerald-100 transition-colors cursor-pointer"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span>Start Demo</span>
          </button>
        </div>
      </div>
    </div>
  );
};

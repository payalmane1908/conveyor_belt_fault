/**
 * Incident & Defect Alerts Log Component
 * 
 * Faithfully matches the bottom card from reference screenshot media_1789972547946.jpg:
 * - Card header: "Incident & Defect Alerts Log", right link: "View all alerts →"
 * - Content: "No active alerts. All conveyor parameters within limits." or live incident log rows
 */

import React from 'react';
import { Link } from 'react-router-dom';
import { useMonitoring } from '../../context/MonitoringContext';
import { formatTimestamp } from '../../lib/formatting';

export const IncidentAlertsLogWidget: React.FC = () => {
  const { alerts, acknowledgeAlert } = useMonitoring();
  const unackAlerts = alerts.filter(a => !a.is_acknowledged);

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-sm font-bold text-slate-900">
          Incident &amp; Defect Alerts Log
        </div>
        <Link
          to="/alerts"
          className="text-xs font-bold text-blue-600 hover:text-blue-800 transition-colors flex items-center gap-1"
        >
          <span>View all alerts</span>
          <span>&rarr;</span>
        </Link>
      </div>

      {/* Log Body */}
      {unackAlerts.length === 0 ? (
        <div className="text-xs text-slate-400 py-3">
          No active alerts. All conveyor parameters within limits.
        </div>
      ) : (
        <div className="space-y-2 pt-1">
          {unackAlerts.slice(0, 3).map((alert) => (
            <div
              key={alert.id}
              className="flex items-center justify-between p-3 rounded-xl bg-slate-50 border border-slate-200/70 text-xs"
            >
              <div className="flex items-center gap-3">
                <span className="px-2 py-0.5 rounded-full bg-rose-100 text-rose-700 text-[10px] font-bold border border-rose-200">
                  {alert.severity}
                </span>
                <span className="font-bold text-slate-800">{alert.alert_type}</span>
                <span className="text-slate-500 hidden sm:inline">{alert.message}</span>
              </div>

              <div className="flex items-center gap-3">
                <span className="text-[11px] text-slate-400">
                  {formatTimestamp(alert.triggered_at_utc)}
                </span>
                <button
                  onClick={() => acknowledgeAlert(alert.id)}
                  className="px-2.5 py-1 rounded-lg bg-white border border-slate-300 hover:bg-slate-100 text-slate-700 text-[11px] font-bold transition-colors cursor-pointer"
                >
                  Acknowledge
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

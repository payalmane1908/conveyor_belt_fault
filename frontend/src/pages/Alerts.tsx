/**
 * Alerts & Operational Maintenance Events Workstation
 * 
 * Faithfully matches reference screenshot media_1789973387663.jpg:
 * 1. Top Metric Cards:
 *    - Card 1: TOTAL ALERTS (Big bold number) & TIME TO ACTION
 *    - Card 2: LAST ALERT & PREVENTABLE count
 *    - Card 3: Status blocks (Resolved [Green], Unresolved [Amber], Overdue [Red])
 *    - Card 4: Severity blocks (Low [Light Pink], Medium [Coral], High [Red])
 * 2. Filter Bar:
 *    - Dropdowns: All Plants, All Profiles, Filter alerts search input
 * 3. Main Card:
 *    - "Historical Alerts & Maintenance Incidents" table with real backend /api/v1/alerts data
 */

import React, { useState, useEffect } from 'react';
import { useMonitoring } from '../context/MonitoringContext';
import { api } from '../services/api';
import type { AlertEvent, StatusLevel } from '../types';
import { formatTimestamp } from '../lib/formatting';
import { getStatusPresentation } from '../lib/status';
import {
  Search,
  ChevronDown,
  RefreshCw,
  CheckCircle2,
  ShieldCheck
} from 'lucide-react';

export const Alerts: React.FC = () => {
  const { acknowledgeAlert, refreshData } = useMonitoring();
  const [alertsList, setAlertsList] = useState<AlertEvent[]>([]);
  const [totalAlerts, setTotalAlerts] = useState<number>(0);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [plantFilter, setPlantFilter] = useState<string>('All Plants');
  const [profileFilter, setProfileFilter] = useState<string>('All Profiles');
  const [statusTab, setStatusTab] = useState<'ALL' | 'RESOLVED' | 'UNRESOLVED' | 'OVERDUE'>('ALL');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [selectedAlertForSnapshot, setSelectedAlertForSnapshot] = useState<AlertEvent | null>(null);

  const fetchAlerts = async () => {
    setIsLoading(true);
    try {
      const res = await api.getAlerts({ limit: 100 });
      setAlertsList(res.alerts || []);
      setTotalAlerts(res.total || 0);
    } catch (err) {
      console.warn('Failed to fetch alerts:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleAck = async (alertId: string) => {
    try {
      await acknowledgeAlert(alertId);
      await fetchAlerts();
      await refreshData();
    } catch (err) {
      console.error('Failed to acknowledge alert:', err);
    }
  };

  // Metrics counters matching screenshot blocks
  const resolvedCount = alertsList.filter((a) => a.is_acknowledged).length;
  const unresolvedCount = alertsList.filter((a) => !a.is_acknowledged).length;
  const overdueCount = alertsList.filter((a) => !a.is_acknowledged && a.severity === 'CRITICAL').length;

  const lowCount = alertsList.filter((a) => a.severity === 'WATCH' || a.severity === 'NORMAL').length;
  const mediumCount = alertsList.filter((a) => a.severity === 'WARNING').length;
  const highCount = alertsList.filter((a) => a.severity === 'CRITICAL').length;

  // Filtered alerts
  const filteredAlerts = alertsList.filter((a) => {
    if (statusTab === 'RESOLVED' && !a.is_acknowledged) return false;
    if (statusTab === 'UNRESOLVED' && a.is_acknowledged) return false;
    if (statusTab === 'OVERDUE' && (a.is_acknowledged || a.severity !== 'CRITICAL')) return false;

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchMsg = a.message?.toLowerCase().includes(q);
      const matchType = a.alert_type?.toLowerCase().includes(q);
      const matchJoint = a.joint_id?.toLowerCase().includes(q);
      if (!matchMsg && !matchType && !matchJoint) return false;
    }
    return true;
  });

  const lastAlertTime = alertsList.length > 0
    ? formatTimestamp(alertsList[0].triggered_at_utc)
    : 'No Alerts';

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-12 font-sans select-none">
      {/* 1. TOP METRIC CARDS ROW (Matching media_1789973387663.jpg) */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-stretch">
        {/* Card 1: TOTAL ALERTS & TIME TO ACTION (Col 3) */}
        <div className="md:col-span-3 bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              TOTAL ALERTS
            </span>
            <span className="text-2xl font-black text-[#0047ba]">
              {totalAlerts}
            </span>
          </div>
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs text-slate-500">
            <span className="font-bold text-slate-400 uppercase tracking-wider text-[11px]">
              TIME TO ACTION
            </span>
            <span className="font-semibold text-slate-700">N/A</span>
          </div>
        </div>

        {/* Card 2: LAST ALERT & PREVENTABLE (Col 3) */}
        <div className="md:col-span-3 bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between">
          <div className="flex items-start justify-between">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">
              LAST ALERT
            </span>
            <span className="text-xs font-bold text-slate-800 truncate max-w-[120px]">
              {lastAlertTime}
            </span>
          </div>
          <div className="flex items-center justify-between pt-3 border-t border-slate-100 text-xs text-slate-500">
            <span className="font-bold text-slate-400 uppercase tracking-wider text-[11px]">
              PREVENTABLE
            </span>
            <span className="font-black text-slate-900 text-sm">0</span>
          </div>
        </div>

        {/* Card 3: Status Blocks: Resolved [Green], Unresolved [Amber], Overdue [Red] (Col 3) */}
        <div className="md:col-span-3 bg-white border border-slate-200/90 rounded-2xl p-3.5 shadow-2xs flex items-center justify-between gap-2">
          {/* Resolved */}
          <div
            onClick={() => setStatusTab(statusTab === 'RESOLVED' ? 'ALL' : 'RESOLVED')}
            className={`flex-1 rounded-xl p-2.5 text-center cursor-pointer transition-all ${
              statusTab === 'RESOLVED' ? 'ring-2 ring-emerald-400 shadow-sm' : ''
            } bg-[#00a651] text-white`}
          >
            <div className="text-[11px] font-medium opacity-90">Resolved</div>
            <div className="text-xl font-black mt-0.5">{resolvedCount}</div>
          </div>

          {/* Unresolved */}
          <div
            onClick={() => setStatusTab(statusTab === 'UNRESOLVED' ? 'ALL' : 'UNRESOLVED')}
            className={`flex-1 rounded-xl p-2.5 text-center cursor-pointer transition-all ${
              statusTab === 'UNRESOLVED' ? 'ring-2 ring-amber-400 shadow-sm' : ''
            } bg-[#f7941d] text-white`}
          >
            <div className="text-[11px] font-medium opacity-90">Unresolved</div>
            <div className="text-xl font-black mt-0.5">{unresolvedCount}</div>
          </div>

          {/* Overdue */}
          <div
            onClick={() => setStatusTab(statusTab === 'OVERDUE' ? 'ALL' : 'OVERDUE')}
            className={`flex-1 rounded-xl p-2.5 text-center cursor-pointer transition-all ${
              statusTab === 'OVERDUE' ? 'ring-2 ring-rose-400 shadow-sm' : ''
            } bg-[#ed1c24] text-white`}
          >
            <div className="text-[11px] font-medium opacity-90">Overdue</div>
            <div className="text-xl font-black mt-0.5">{overdueCount}</div>
          </div>
        </div>

        {/* Card 4: Severity Blocks: Low [Light Pink], Medium [Coral], High [Red] (Col 3) */}
        <div className="md:col-span-3 bg-white border border-slate-200/90 rounded-2xl p-3.5 shadow-2xs flex items-center justify-between gap-2">
          {/* Low */}
          <div className="flex-1 rounded-xl p-2.5 text-center bg-[#fed7d7] text-[#c53030]">
            <div className="text-[11px] font-bold">Low</div>
            <div className="text-xl font-black mt-0.5">{lowCount}</div>
          </div>

          {/* Medium */}
          <div className="flex-1 rounded-xl p-2.5 text-center bg-[#feb2b2] text-[#9b2c2c]">
            <div className="text-[11px] font-bold">Medium</div>
            <div className="text-xl font-black mt-0.5">{mediumCount}</div>
          </div>

          {/* High */}
          <div className="flex-1 rounded-xl p-2.5 text-center bg-[#e53e3e] text-white">
            <div className="text-[11px] font-bold">High</div>
            <div className="text-xl font-black mt-0.5">{highCount}</div>
          </div>
        </div>
      </div>

      {/* 2. FILTER TOOLBAR ROW (Matching media_1789973387663.jpg) */}
      <div className="bg-white border border-slate-200/90 rounded-2xl px-4 py-3 shadow-2xs flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {/* Plant Dropdown */}
          <div className="relative">
            <select
              value={plantFilter}
              onChange={(e) => setPlantFilter(e.target.value)}
              className="appearance-none bg-slate-50 border border-slate-200 rounded-xl pl-3 pr-8 py-1.5 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option>All Plants</option>
              <option>Plant-01 (Iron Ore Overland)</option>
              <option>Plant-02 (Crusher Discharge)</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Profile Dropdown */}
          <div className="relative">
            <select
              value={profileFilter}
              onChange={(e) => setProfileFilter(e.target.value)}
              className="appearance-none bg-slate-50 border border-slate-200 rounded-xl pl-3 pr-8 py-1.5 text-xs font-semibold text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500 cursor-pointer"
            >
              <option>All Profiles</option>
              <option>Splice Rupture Risk</option>
              <option>Bearing Overheat</option>
              <option>Belt Mistracking</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Search Input */}
          <div className="relative min-w-[240px]">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filter alerts..."
              className="w-full bg-slate-50 border border-slate-200 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-700 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="flex items-center gap-3">
          <span className="text-xs text-slate-400 font-medium">
            Showing {filteredAlerts.length} of {totalAlerts}
          </span>
          <button
            onClick={fetchAlerts}
            title="Refresh alerts"
            className="p-1.5 rounded-lg bg-slate-50 hover:bg-slate-100 text-slate-600 border border-slate-200 transition-colors cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* 3. HISTORICAL ALERTS & MAINTENANCE INCIDENTS CARD (Matching media_1789973387663.jpg) */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 shadow-2xs space-y-4">
        <div className="text-sm font-bold text-slate-900">
          Historical Alerts &amp; Maintenance Incidents
        </div>

        {filteredAlerts.length === 0 ? (
          <div className="text-xs text-slate-400 py-8 text-center">
            No active alerts. All conveyor parameters within limits.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-700">
              <thead className="bg-slate-50 text-slate-400 text-[11px] uppercase font-bold border-b border-slate-100">
                <tr>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Alert Type</th>
                  <th className="py-2.5 px-3">Location / Joint</th>
                  <th className="py-2.5 px-3">Advisory Message</th>
                  <th className="py-2.5 px-3">Triggered (UTC)</th>
                  <th className="py-2.5 px-3">Audit Trail</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 font-medium">
                {filteredAlerts.map((alert) => {
                  const pres = getStatusPresentation(alert.severity as StatusLevel);
                  return (
                    <tr key={alert.id} className="hover:bg-slate-50/70 transition-colors">
                      <td className="py-3 px-3 whitespace-nowrap">
                        <span
                          className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border ${pres.badgeBg} ${pres.badgeBorder} ${pres.badgeText}`}
                        >
                          {pres.label}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-bold text-slate-900 whitespace-nowrap">
                        {alert.alert_type}
                      </td>
                      <td className="py-3 px-3 text-slate-500 whitespace-nowrap">
                        {alert.joint_id || alert.conveyor_id || 'CV-MINE-01'}
                      </td>
                      <td className="py-3 px-3 text-slate-600 max-w-sm truncate">
                        {alert.message}
                      </td>
                      <td className="py-3 px-3 text-slate-400 text-[11px] whitespace-nowrap">
                        {formatTimestamp(alert.triggered_at_utc)}
                      </td>
                      <td className="py-3 px-3 whitespace-nowrap text-[11px]">
                        {alert.is_acknowledged ? (
                          <span className="text-emerald-600 font-bold flex items-center gap-1">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                            <span>ACK: {alert.acknowledged_by || 'OPERATOR'}</span>
                          </span>
                        ) : (
                          <span className="text-amber-600 font-bold">PENDING ACK</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right whitespace-nowrap space-x-2">
                        {alert.metrics_snapshot && (
                          <button
                            onClick={() => setSelectedAlertForSnapshot(alert)}
                            className="text-[11px] font-bold px-2 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
                          >
                            Snapshot
                          </button>
                        )}
                        {!alert.is_acknowledged && (
                          <button
                            onClick={() => handleAck(alert.id)}
                            className="text-[11px] font-bold px-3 py-1 rounded-lg bg-[#0052cc] hover:bg-[#0047ba] text-white transition-colors cursor-pointer shadow-2xs"
                          >
                            Acknowledge
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Snapshot Modal */}
      {selectedAlertForSnapshot && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs select-none">
          <div className="w-full max-w-md bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden font-sans">
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-blue-600" />
                <h3 className="text-sm font-bold text-slate-900">
                  Alert Telemetry Snapshot
                </h3>
              </div>
              <button
                onClick={() => setSelectedAlertForSnapshot(null)}
                className="text-slate-400 hover:text-slate-700 text-sm cursor-pointer"
              >
                ✕
              </button>
            </div>

            <div className="p-4 space-y-3 text-xs">
              <div className="text-slate-500">
                Captured metrics at <strong className="text-slate-800">{formatTimestamp(selectedAlertForSnapshot.triggered_at_utc)}</strong>
              </div>

              <div className="bg-slate-50 p-3 rounded-xl border border-slate-200/80 space-y-1.5 text-slate-700">
                {Object.entries(selectedAlertForSnapshot.metrics_snapshot || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-slate-200/60 pb-1">
                    <span className="text-slate-500 capitalize">{k.replace(/_/g, ' ')}:</span>
                    <span className="font-bold text-slate-900">{String(v)}</span>
                  </div>
                ))}
              </div>

              <div className="text-[11px] text-slate-400 flex justify-between pt-1">
                <span>Alert ID: {selectedAlertForSnapshot.id.slice(0, 16)}...</span>
                <span className="text-emerald-600 font-bold">Immutable Audit Record</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

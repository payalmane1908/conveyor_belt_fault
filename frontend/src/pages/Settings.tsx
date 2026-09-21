/**
 * Plant Settings & Alarm Limits (Phase 1 Shell)
 * 
 * Scheduled for Phase 3 implementation.
 */

import React from 'react';
import { Settings as SettingsIcon, Clock } from 'lucide-react';

export const SettingsPage: React.FC = () => {
  return (
    <div className="space-y-4 max-w-7xl mx-auto">
      <div className="bg-zinc-950 border border-zinc-800 rounded-lg p-6 space-y-3">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-zinc-900 border border-zinc-700 rounded-lg text-zinc-300">
            <SettingsIcon className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-base font-mono font-bold text-zinc-100 uppercase">
              Plant Settings & Alarm Limits
            </h1>
            <p className="text-xs font-mono text-zinc-400">
              Configure engineering application thresholds, polling intervals, and unit standards.
            </p>
          </div>
        </div>

        <div className="bg-zinc-900/60 border border-zinc-800/80 rounded p-4 text-xs font-mono text-zinc-400 flex items-center gap-2">
          <Clock className="w-4 h-4 text-zinc-500" />
          <span>Phase 1 Shell Active — Configurable alarm limits editor scheduled for Phase 3.</span>
        </div>
      </div>
    </div>
  );
};

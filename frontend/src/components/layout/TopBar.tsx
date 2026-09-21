/**
 * Industrial SCADA Top Bar
 * 
 * Recreated faithfully from reference screenshot media_1789973387545.jpg.
 * Cobalt Blue header (#0052cc / #0047ba) with search bar, shortcuts, and operator profile.
 */

import React from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  Search,
  Maximize2,
  LogOut,
  Radio
} from 'lucide-react';

export const TopBar: React.FC = () => {
  const { user, logout } = useAuth();

  const handleToggleFullscreen = () => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  };

  return (
    <header className="h-14 bg-[#0047ba] px-6 flex items-center justify-between select-none shrink-0 z-30 shadow-sm text-white">
      {/* Left: Brand / Logo */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 font-black text-xl tracking-tight">
          <div className="w-7 h-7 rounded-full border-2 border-white flex items-center justify-center">
            <Radio className="w-4 h-4 text-white" />
          </div>
          <span className="font-sans font-extrabold text-white tracking-wide">Orbit</span>
          <span className="text-[10px] font-mono uppercase bg-white/20 px-1.5 py-0.5 rounded text-white font-semibold">
            SCADA
          </span>
        </div>
      </div>

      {/* Center: Search Bar */}
      <div className="flex-1 max-w-md mx-6">
        <div className="relative">
          <Search className="w-4 h-4 text-blue-200 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            placeholder="Search Orbit..."
            className="w-full bg-[#003893] border border-blue-400/40 rounded-lg pl-9 pr-14 py-1.5 text-xs text-white placeholder-blue-200/70 focus:outline-none focus:ring-1 focus:ring-white"
          />
          <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-900/60 text-blue-200 border border-blue-400/30">
            Ctrl K
          </span>
        </div>
      </div>

      {/* Right: Operator Profile & Actions */}
      <div className="flex items-center gap-4 text-xs font-medium">
        <div className="font-bold tracking-wide uppercase text-white">
          HI, {user?.name || 'ADMIN'}
        </div>

        <button
          onClick={handleToggleFullscreen}
          title="Toggle Fullscreen"
          className="p-1 text-blue-100 hover:text-white transition-colors cursor-pointer"
        >
          <Maximize2 className="w-4 h-4" />
        </button>

        <button
          onClick={logout}
          title="Sign out session"
          className="p-1 text-blue-100 hover:text-white transition-colors cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
};

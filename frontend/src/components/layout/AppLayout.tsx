/**
 * Primary Application Layout
 * 
 * Recreated faithfully from reference screenshot media_1789973387545.jpg:
 * - Cobalt Blue TopBar
 * - Secondary White SubNav with Breadcrumbs and Pill Tabs
 * - Full-width clean slate canvas
 * - Global white Demo Data Simulator modal
 */

import React from 'react';
import { Outlet } from 'react-router-dom';
import { TopBar } from './TopBar';
import { SubNav } from './SubNav';
import { useMonitoring } from '../../context/MonitoringContext';
import { DemoDataSimulatorModal } from '../simulator/DemoDataSimulatorModal';

export const AppLayout: React.FC = () => {
  const { isSimulatorOpen, setIsSimulatorOpen } = useMonitoring();

  return (
    <div className="flex flex-col min-h-screen w-screen bg-[#f0f4f9] text-slate-800 font-sans antialiased overflow-x-hidden">
      {/* 1. Cobalt Blue Top Bar */}
      <TopBar />

      {/* 2. Secondary Breadcrumb & Pill Tab Navigation Bar */}
      <SubNav />

      {/* 3. Main Content Canvas */}
      <main className="flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto">
        <Outlet />
      </main>

      {/* 4. Global Demo Data Simulator Modal (White Theme) */}
      <DemoDataSimulatorModal
        isOpen={isSimulatorOpen}
        onClose={() => setIsSimulatorOpen(false)}
      />
    </div>
  );
};

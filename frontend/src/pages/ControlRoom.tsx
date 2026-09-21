/**
 * Control Room (Industrial SCADA Workstation)
 * 
 * Faithful recreation of the reference layout in media_1789973387545.jpg,
 * media_1789972547876.jpg, media_1789972547925.jpg, and media_1789972547946.jpg.
 * 
 * Layout Architecture:
 * - Row 1: Latest Alerts Banner (Left) + Quick Response Action (Right)
 * - Row 2: Top 1 Conveyor Feed Viewport (Left) + Health Status / Defect Types / Material (Right)
 * - Row 3: 4 Clean White Sensor Cards (Vibration, Bearing Temp, Chute Load, Drive RPM)
 * - Row 4: AI Health Prediction & Recommendation (Left) + Vibration Waveform Analysis (Right)
 * - Row 5: Incident & Defect Alerts Log
 */

import React from 'react';
import { useMonitoring } from '../context/MonitoringContext';
import { DEFAULT_ALARM_LIMITS, evaluateLimit } from '../lib/status';
import { SensorCard } from '../components/telemetry/SensorCard';
import { ConveyorFeedViewport } from '../components/vision/ConveyorFeedViewport';
import {
  HealthStatusWidget,
  DefectTypeWidget,
  MaterialAndForeignObjectsWidget
} from '../components/dashboard/ControlRoomWidgets';
import {
  LatestAlertsWidget,
  QuickResponseActionWidget
} from '../components/dashboard/TopRowWidgets';
import { AIHealthPredictionCard } from '../components/dashboard/AIHealthPredictionCard';
import { VibrationWaveformCard } from '../components/dashboard/VibrationWaveformCard';
import { IncidentAlertsLogWidget } from '../components/dashboard/IncidentAlertsLogWidget';

export const ControlRoom: React.FC = () => {
  const { telemetry, sensorHistory } = useMonitoring();

  // 4 Primary Sensors corresponding directly to the reference screenshot
  const vibrationStatus = evaluateLimit(telemetry?.vibration, DEFAULT_ALARM_LIMITS.vibration_rms);
  const tempStatus = evaluateLimit(telemetry?.temperature, DEFAULT_ALARM_LIMITS.temperature);
  const loadStatus = evaluateLimit(telemetry?.load, DEFAULT_ALARM_LIMITS.load);
  const rpmStatus = evaluateLimit(telemetry?.rpm, DEFAULT_ALARM_LIMITS.rpm);

  // Load in kg scaled for test-rig (2.4 kg nominal up to 4.2 kg overloaded)
  const loadKg = telemetry?.load !== undefined && telemetry?.load !== null
    ? Number((telemetry.load * 0.035).toFixed(1))
    : 2.4;

  return (
    <div className="space-y-4 max-w-7xl mx-auto pb-12">
      {/* ROW 1: Latest Alerts (Left) + Quick Response Action (Right) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
        <div className="lg:col-span-7 flex flex-col">
          <LatestAlertsWidget />
        </div>
        <div className="lg:col-span-5 flex flex-col">
          <QuickResponseActionWidget />
        </div>
      </section>

      {/* ROW 2: Top 1 Conveyor Feed Viewport (Left) + Health Status & Defect Breakdown (Right) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
        {/* Left Column (Approx 60%): Top 1 Conveyor Belt Viewport */}
        <div className="lg:col-span-7">
          <ConveyorFeedViewport />
        </div>

        {/* Right Column (Approx 40%): Health Status, Defect Type, and Material Widgets */}
        <div className="lg:col-span-5 space-y-4">
          <HealthStatusWidget />
          <DefectTypeWidget />
          <MaterialAndForeignObjectsWidget />
        </div>
      </section>

      {/* ROW 3: 4 Sensor Cards (VIBRATION, BEARING TEMP, CHUTE LOAD, DRIVE RPM) */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* 1. VIBRATION */}
        <SensorCard
          id="vibration"
          name="VIBRATION"
          value={telemetry?.vibration !== undefined && telemetry?.vibration !== null ? Number(telemetry.vibration.toFixed(2)) : 0.33}
          unit="g"
          status={vibrationStatus}
          history={sensorHistory?.vibration}
        />

        {/* 2. BEARING TEMPERATURE */}
        <SensorCard
          id="temperature"
          name="BEARING TEMPERATURE"
          value={telemetry?.temperature ? Math.round(telemetry.temperature) : 38}
          unit="°C"
          status={tempStatus}
          history={sensorHistory?.temperature}
        />

        {/* 3. CHUTE MATERIAL LOAD */}
        <SensorCard
          id="load"
          name="CHUTE MATERIAL LOAD"
          value={loadKg}
          unit="kg"
          status={loadStatus}
          history={sensorHistory?.load}
        />

        {/* 4. DRIVE PULLEY RPM */}
        <SensorCard
          id="rpm"
          name="DRIVE PULLEY RPM"
          value={telemetry?.rpm ? Math.round(telemetry.rpm) : 1200}
          unit="rpm"
          status={rpmStatus}
          history={sensorHistory?.rpm}
        />
      </section>

      {/* ROW 4: AI Health Prediction (Left) + Vibration Waveform Analysis (Right) */}
      <section className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
        <div className="lg:col-span-7 flex flex-col">
          <AIHealthPredictionCard />
        </div>
        <div className="lg:col-span-5 flex flex-col">
          <VibrationWaveformCard />
        </div>
      </section>

      {/* ROW 5: Incident & Defect Alerts Log */}
      <section>
        <IncidentAlertsLogWidget />
      </section>
    </div>
  );
};

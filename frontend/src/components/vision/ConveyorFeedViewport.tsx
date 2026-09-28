/**
 * Conveyor Optical Camera Feed & Joint Shutter Viewport (SCADA Optical Station)
 * 
 * Features:
 * 1. Live Continuous Optical Video Stream (from physical USB webcam or industrial benchmark stream) via MJPEG.
 * 2. High-speed magnetic joint shutter synchronization (auto-triggered on joint passage or manual button).
 * 3. Benchmark Dataset Browser: Pick and inspect any of the 65 held-out test frames with trained YOLOv8.
 * 4. Browse & Upload Custom Image: Select any image from computer to run immediate YOLOv8 defect inference.
 * 5. Industrial SCADA HUD: Belt speed telemetry (m/s), live RPM, UTC clock watermark, and detection badges.
 * 6. Direct routing to dedicated offline AI Forensic Lab (/ai-diagnosis).
 */

import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useMonitoring } from '../../context/MonitoringContext';
import { api } from '../../services/api';
import type { VisionObservation } from '../../types';
import {
  Camera,
  Maximize2,
  Loader2,
  AlertTriangle,
  ChevronDown,
  Sparkles,
  RotateCcw,
  ExternalLink,
  ShieldCheck,
  Video,
  Upload,
  RefreshCw
} from 'lucide-react';

export const ConveyorFeedViewport: React.FC = () => {
  const navigate = useNavigate();
  const { telemetry, refreshData } = useMonitoring();

  // Mode: continuous live CCTV stream vs. inspected snapshot / uploaded frame
  const [viewMode, setViewMode] = useState<'LIVE_STREAM' | 'INSPECTED_FRAME'>('LIVE_STREAM');
  const [cameraStatus, setCameraStatus] = useState<any>(null);
  const [streamError, setStreamError] = useState<boolean>(false);
  const [streamRetryKey, setStreamRetryKey] = useState<number>(0);
  const [isCapturing, setIsCapturing] = useState<boolean>(false);
  const [isInjecting, setIsInjecting] = useState<boolean>(false);
  const [shutterFlash, setShutterFlash] = useState<boolean>(false);
  const [showInsertMenu, setShowInsertMenu] = useState<boolean>(false);
  const [latestObservation, setLatestObservation] = useState<VisionObservation | null>(null);
  const [inspectedImageUrl, setInspectedImageUrl] = useState<string | null>(null);
  const [notificationMsg, setNotificationMsg] = useState<string | null>(null);

  // Test samples & custom image upload
  const [testSamples, setTestSamples] = useState<string[]>([]);
  const [selectedSample, setSelectedSample] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Load camera status and benchmark test samples on mount
  useEffect(() => {
    let isMounted = true;

    const fetchInitialData = async () => {
      try {
        const [cStatus, obsList, samplesRes] = await Promise.all([
          api.getCameraStatus().catch(() => null),
          api.getVisionObservations('J-01', 1).catch(() => []),
          api.getVisionTestSamples().catch(() => null)
        ]);

        if (!isMounted) return;

        if (cStatus) setCameraStatus(cStatus);
        if (samplesRes?.samples && samplesRes.samples.length > 0) {
          setTestSamples(samplesRes.samples);
          setSelectedSample(samplesRes.samples[0]);
        }
        if (obsList && obsList.length > 0) {
          const latest = obsList[0];
          setLatestObservation(latest);
          if (latest.image_reference) {
            setInspectedImageUrl(api.resolveMediaUrl(latest.image_reference));
          }
        }
      } catch (err) {
        console.warn('ConveyorFeedViewport: initial data warning', err);
      }
    };

    fetchInitialData();
    const interval = setInterval(async () => {
      if (!isMounted) return;
      const cStatus = await api.getCameraStatus().catch(() => null);
      if (cStatus && isMounted) setCameraStatus(cStatus);
    }, 4000);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  // Trigger high-speed joint snapshot & YOLO inspection from live camera
  const handleTriggerJointCapture = async (jointCode = 'J-01') => {
    setIsCapturing(true);
    setShutterFlash(true);
    setTimeout(() => setShutterFlash(false), 200);

    try {
      const res = await api.triggerCameraCapture({ joint_code: jointCode, conf_threshold: 0.35 });
      setLatestObservation(res);

      if (res.image_reference) {
        setInspectedImageUrl(`${api.resolveMediaUrl(res.image_reference)}?t=${Date.now()}`);
      }

      const detCount = (res.total_detections_count ?? (res as any).total_detections ?? res.detections?.length ?? 0);
      if (detCount > 0 && res.primary_damage_type !== 'NORMAL_SURFACE') {
        setNotificationMsg(`Joint ${jointCode} inspected: ${detCount} defect(s) detected (${res.primary_damage_type})`);
      } else {
        setNotificationMsg(`Joint ${jointCode} inspected: Belt surface intact. No tears, holes, or splice damages.`);
      }

      setViewMode('INSPECTED_FRAME');
      await refreshData();
    } catch (err: any) {
      console.error('Trigger capture failed:', err);
      setNotificationMsg(`Inspection trigger error: ${err.message || 'Check camera'}`);
    } finally {
      setIsCapturing(false);
    }
  };

  // Analyze a benchmark dataset frame
  const handleAnalyzeSample = async (sampleName: string) => {
    if (!sampleName) return;
    setSelectedSample(sampleName);
    setIsCapturing(true);

    try {
      const res = await api.triggerCameraCapture({
        joint_code: 'J-01',
        test_image_name: sampleName,
        conf_threshold: 0.35
      });
      setLatestObservation(res);

      if (res.image_reference) {
        setInspectedImageUrl(`${api.resolveMediaUrl(res.image_reference)}?t=${Date.now()}`);
      }

      const detCount = (res.total_detections_count ?? (res as any).total_detections ?? res.detections?.length ?? 0);
      if (detCount > 0 && res.primary_damage_type !== 'NORMAL_SURFACE') {
        setNotificationMsg(`Benchmark sample '${sampleName.substring(0, 18)}...': ${detCount} defect(s) detected (${res.primary_damage_type})`);
      } else {
        setNotificationMsg(`Benchmark sample '${sampleName.substring(0, 18)}...': Belt surface intact.`);
      }

      setViewMode('INSPECTED_FRAME');
      await refreshData();
    } catch (err: any) {
      console.error('Sample analysis error:', err);
      setNotificationMsg(`Analysis notice: ${err.message || 'Complete'}`);
    } finally {
      setIsCapturing(false);
    }
  };

  // Browse & Upload custom image from user computer
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsCapturing(true);

    try {
      const obs = await api.analyzeVisionFrame(undefined, 'J-01', 'CAM-SPLICE-01', file);
      setLatestObservation(obs);

      if (obs.image_reference) {
        setInspectedImageUrl(`${api.resolveMediaUrl(obs.image_reference)}?t=${Date.now()}`);
      }

      const detCount = (obs.total_detections_count ?? (obs as any).total_detections ?? obs.detections?.length ?? 0);
      if (detCount > 0 && obs.primary_damage_type !== 'NORMAL_SURFACE') {
        setNotificationMsg(`Uploaded image '${file.name}': ${detCount} defect(s) detected (${obs.primary_damage_type})`);
      } else {
        setNotificationMsg(`Uploaded image '${file.name}': No conveyor belt damage detected (surface intact).`);
      }

      setViewMode('INSPECTED_FRAME');
      await refreshData();
    } catch (err: any) {
      console.error('File upload analysis error:', err);
      setNotificationMsg(`Upload error: ${err.message || 'Analysis failed'}`);
    } finally {
      setIsCapturing(false);
      e.target.value = '';
    }
  };

  // Inject a fault burst for demonstration
  const handleInsertFault = async (type: 'SPLICE_IMPACT' | 'HARMONIC_LOOSENESS') => {
    setIsInjecting(true);
    setShowInsertMenu(false);
    try {
      await api.injectFaultBurst('sim-accel-p3-01', type, 'joint-001');
      await handleTriggerJointCapture('J-01');
      await refreshData();
      setNotificationMsg(`Injected fault burst: ${type}. Corroborating optical & vibration signatures.`);
    } catch (err: any) {
      console.error('Fault injection error:', err);
    } finally {
      setIsInjecting(false);
    }
  };

  // Reset visual state
  const handleResetVision = async () => {
    try {
      await api.resetVision('joint-001');
      setLatestObservation(null);
      setInspectedImageUrl(null);
      setViewMode('LIVE_STREAM');
      setNotificationMsg('Vision and splice health baseline reset to healthy state.');
      await refreshData();
    } catch (err: any) {
      console.error('Reset error:', err);
    }
  };

  // Toggle fullscreen
  const toggleFullscreen = () => {
    if (containerRef.current) {
      if (!document.fullscreenElement) {
        containerRef.current.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    }
  };

  const isLiveHardware = cameraStatus?.hardware_camera_available;
  const liveStreamUrl = `${api.getCameraStreamUrl()}?retry=${streamRetryKey}`;

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl p-4 shadow-2xs flex flex-col justify-between space-y-3.5">
      {/* 1. Header: Camera ID, Live Status, Mode Toggle */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 flex items-center justify-center shadow-2xs">
            <Video className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900 tracking-tight">
                Optical Inspection Feed
              </span>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center gap-1 ${
                  isLiveHardware
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-amber-50 text-amber-700 border border-amber-200'
                }`}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${isLiveHardware ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
                {isLiveHardware ? 'USB CAMERA ONLINE' : 'BENCHMARK FEED'}
              </span>
            </div>
            <span className="text-[10px] text-slate-400 block font-mono">
              STATION: CAM-SPLICE-01 · HEAD DRIVE PULLEY HOOD
            </span>
          </div>
        </div>

        {/* View Mode Toggle: Live MJPEG Stream vs Last Inspected Snapshot */}
        <div className="flex items-center gap-1 p-1 bg-slate-100 rounded-xl text-[11px] font-bold">
          <button
            onClick={() => setViewMode('LIVE_STREAM')}
            className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
              viewMode === 'LIVE_STREAM'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            Live Video Stream
          </button>
          <button
            onClick={() => {
              if (!inspectedImageUrl) {
                handleTriggerJointCapture('J-01');
              } else {
                setViewMode('INSPECTED_FRAME');
              }
            }}
            className={`px-3 py-1 rounded-lg transition-all cursor-pointer flex items-center gap-1.5 ${
              viewMode === 'INSPECTED_FRAME'
                ? 'bg-white text-blue-700 shadow-xs'
                : 'text-slate-600 hover:text-slate-900'
            }`}
          >
            <Sparkles className="w-3 h-3 text-amber-500" />
            Inspected Frame
          </button>
        </div>
      </div>

      {/* 2. Main Viewport: Live MJPEG Stream or Inspected Snapshot */}
      <div
        ref={containerRef}
        className="relative w-full rounded-xl overflow-hidden bg-[#0a0c10] aspect-[16/9] flex items-center justify-center shadow-inner border border-slate-800"
      >
        {/* Shutter flash animation overlay */}
        {shutterFlash && (
          <div className="absolute inset-0 bg-white z-40 animate-out fade-out duration-200 pointer-events-none" />
        )}

        {viewMode === 'LIVE_STREAM' ? (
          <div className="relative w-full h-full flex items-center justify-center">
            {!streamError ? (
              <img
                src={liveStreamUrl}
                alt="Conveyor Live Optical Stream"
                onError={() => setStreamError(true)}
                className="w-full h-full object-cover select-none"
              />
            ) : (
              <div className="text-center p-6 text-slate-400">
                <AlertTriangle className="w-8 h-8 mx-auto mb-2 text-amber-500" />
                <p className="text-xs font-semibold text-slate-200">Video Stream Reconnecting</p>
                <p className="text-[11px] text-slate-400 mt-1">Waiting for optical server connection...</p>
                <button
                  onClick={() => {
                    setStreamError(false);
                    setStreamRetryKey(k => k + 1);
                  }}
                  className="mt-3 px-3 py-1.5 rounded-lg bg-blue-600 text-white text-xs font-bold hover:bg-blue-500 transition-colors flex items-center gap-1.5 mx-auto cursor-pointer"
                >
                  <RefreshCw className="w-3.5 h-3.5" />
                  Retry Connection
                </button>
              </div>
            )}

            {/* Industrial HUD Telemetry Overlay */}
            <div className="absolute bottom-2.5 left-2.5 right-2.5 flex items-center justify-between pointer-events-none text-white/90 text-[10px] font-mono bg-black/50 backdrop-blur-xs px-3 py-1.5 rounded-lg border border-white/10">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1 text-emerald-400 font-bold">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping" />
                  LIVE CCTV
                </span>
                <span>SPEED: {(((telemetry?.rpm ?? 1200) / 1200) * 2.5).toFixed(1)} m/s</span>
                <span>RPM: {telemetry?.rpm ?? 1200}</span>
                <span>JOINT APERTURE: J-01</span>
              </div>
              <div className="hidden sm:block text-slate-400">
                MODEL: YOLOv8 (conf &ge; 0.35)
              </div>
            </div>
          </div>
        ) : (
          <div className="relative w-full h-full flex items-center justify-center bg-black/95">
            {inspectedImageUrl ? (
              <img
                src={inspectedImageUrl}
                alt="High-Speed Joint Inspection Frame"
                className="w-full h-full object-contain select-none"
              />
            ) : (
              <div className="text-center p-6 text-slate-400 text-xs">
                <Camera className="w-8 h-8 mx-auto mb-2 text-slate-600" />
                <p>No splice inspection frame captured yet.</p>
                <p className="text-[10px] text-slate-500 mt-1">
                  Click &quot;Trigger Joint Shutter&quot;, pick a benchmark sample, or upload an image.
                </p>
              </div>
            )}

            {/* Inspected Frame Metadata Overlay */}
            {latestObservation && (
              <div className="absolute top-2.5 left-2.5 bg-black/80 backdrop-blur-xs px-3 py-1.5 rounded-lg border border-slate-700 text-xs text-white shadow-lg pointer-events-none">
                <div className="flex items-center gap-2">
                  <span className="font-extrabold text-blue-300">
                    {latestObservation.frame_name ? latestObservation.frame_name.substring(0, 24) : `Joint ${latestObservation.joint_code || 'J-01'}`}
                  </span>
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                    YOLOv8
                  </span>
                </div>
                <div className="text-[10px] text-slate-300 mt-0.5 font-mono">
                  Detections: {latestObservation.total_detections_count ?? (latestObservation as any).total_detections ?? latestObservation.detections?.length ?? 0} | Status: {latestObservation.primary_damage_type || 'NORMAL_SURFACE'}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Fullscreen Button */}
        <button
          onClick={toggleFullscreen}
          title="Toggle Fullscreen"
          className="absolute bottom-2.5 right-2.5 p-1.5 rounded-lg bg-black/60 hover:bg-black/80 text-white/80 hover:text-white transition-all cursor-pointer backdrop-blur-xs border border-white/10 z-10"
        >
          <Maximize2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* 3. Action Toolbar: High-Speed Joint Trigger, Benchmark Browser, Upload, Fault Injection, Reset */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-0.5">
        <div className="flex flex-wrap items-center gap-2">
          {/* Primary Action: Trigger High-Speed Joint Shutter */}
          <button
            onClick={() => handleTriggerJointCapture('J-01')}
            disabled={isCapturing}
            className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold transition-all shadow-xs cursor-pointer flex items-center gap-1.5 disabled:opacity-60"
          >
            {isCapturing ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                <span>Running YOLO...</span>
              </>
            ) : (
              <>
                <Camera className="w-3.5 h-3.5" />
                <span>Trigger Joint Shutter</span>
              </>
            )}
          </button>

          {/* Browse Benchmark Test Samples from Dataset */}
          {testSamples.length > 0 && (
            <div className="flex items-center gap-1">
              <select
                value={selectedSample}
                onChange={(e) => handleAnalyzeSample(e.target.value)}
                disabled={isCapturing}
                title="Browse and analyze conveyor test dataset samples"
                className="px-2.5 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs max-w-[145px] truncate"
              >
                {testSamples.map((sampleName, idx) => (
                  <option key={sampleName} value={sampleName}>
                    Sample {idx + 1}: {sampleName.substring(0, 16)}...
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Browse & Upload Custom Image from User Computer */}
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={isCapturing}
            title="Browse your computer and analyze a conveyor belt photo with YOLOv8"
            className="px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs flex items-center gap-1.5"
          >
            <Upload className="w-3.5 h-3.5 text-slate-500" />
            <span>Upload &amp; Analyze</span>
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            accept="image/*"
            className="hidden"
          />

          {/* Fault Simulation Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowInsertMenu(!showInsertMenu)}
              disabled={isInjecting}
              className="px-3 py-2 rounded-lg bg-white border border-slate-300 text-slate-700 text-xs font-bold hover:bg-slate-50 transition-colors cursor-pointer shadow-2xs flex items-center gap-1.5"
            >
              <span>{isInjecting ? 'Simulating...' : 'Inject Test Fault'}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>

            {showInsertMenu && (
              <div className="absolute left-0 mt-1 w-52 bg-white border border-slate-200 rounded-xl shadow-xl z-30 p-1.5 text-xs font-medium space-y-1">
                <button
                  onClick={() => handleInsertFault('SPLICE_IMPACT')}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-rose-50 hover:text-rose-700 transition-colors cursor-pointer flex items-center justify-between"
                >
                  <span>Splice Impact Tear</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-100 text-rose-800">Tear</span>
                </button>
                <button
                  onClick={() => handleInsertFault('HARMONIC_LOOSENESS')}
                  className="w-full text-left px-3 py-2 rounded-lg hover:bg-amber-50 hover:text-amber-700 transition-colors cursor-pointer flex items-center justify-between"
                >
                  <span>Harmonic Joint Looseness</span>
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-amber-100 text-amber-800">Vibe</span>
                </button>
              </div>
            )}
          </div>

          {/* Reset Baseline */}
          <button
            onClick={handleResetVision}
            title="Reset vision state to clean baseline"
            className="px-2.5 py-2 rounded-lg bg-slate-100 hover:bg-slate-200 text-slate-700 text-xs font-bold transition-colors cursor-pointer border border-slate-200 flex items-center gap-1"
          >
            <RotateCcw className="w-3.5 h-3.5 text-slate-500" />
            <span>Reset</span>
          </button>
        </div>

        {/* Clear separation: Link to the Forensic AI Lab */}
        <button
          onClick={() => navigate('/ai-diagnosis')}
          className="px-3 py-2 rounded-lg bg-slate-50 hover:bg-slate-100 border border-slate-300 text-slate-700 hover:text-blue-700 text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 shadow-2xs"
        >
          <span>Open AI Forensic Lab</span>
          <ExternalLink className="w-3.5 h-3.5 text-slate-400" />
        </button>
      </div>

      {/* 4. Notification & Industrial Context Banner */}
      <div className="pt-2 border-t border-slate-100 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          {latestObservation && (latestObservation.total_detections_count ?? (latestObservation as any).total_detections ?? 0) > 0 && latestObservation.primary_damage_type !== 'NORMAL_SURFACE' ? (
            <div className="flex items-center gap-1.5 text-rose-700 font-semibold">
              <AlertTriangle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{notificationMsg || `Optical Defect Detected: ${latestObservation.primary_damage_type}`}</span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-slate-600">
              <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
              <span>
                {notificationMsg || 'Optical station operational. Monitoring continuous belt passage.'}
              </span>
            </div>
          )}
        </div>

        {latestObservation?.detections && latestObservation.detections.length > 0 && (
          <div className="flex items-center gap-1.5">
            {latestObservation.detections.map((d: any, i: number) => (
              <span
                key={i}
                className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-rose-50 text-rose-700 border border-rose-200 font-bold"
              >
                {d.class_name} ({Math.round(d.confidence * 100)}%)
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

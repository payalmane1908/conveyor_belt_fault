/**
 * Computer Vision & Optical Damage Monitoring Types
 * Directly matches backend/app/vision_service.py and /vision/ endpoints
 */

export interface BoundingBox {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface VisionDetection {
  class_id: number;
  class_name: 'damage' | 'Belt Joint' | 'Large Hole' | 'Large Tear' | 'Small Hole' | 'Small Tear' | string;
  confidence: number;
  bbox: BoundingBox;
  is_joint: boolean;
}

export interface VisionObservation {
  id?: string;
  observation_id: string;
  joint_code?: string | null;
  camera_id: string;
  timestamp_utc: string;
  model_status: string;
  model_version: string;
  source_type: string;
  frame_name?: string;
  image_reference: string;
  local_frame_path?: string;
  total_detections_count: number;
  primary_damage_type: string | null;
  prototype_severity: 'NORMAL' | 'WARNING' | 'CRITICAL' | string;
  severity_label?: string;
  max_confidence: number;
  detections: VisionDetection[];
}

export interface VisionEngineStatus {
  model_status: 'TRAINED_MODEL' | 'CLASSICAL_CV_BASELINE' | 'MODEL_NOT_TRAINED' | string;
  model_version: string;
  weights_path: string;
  supported_classes: Record<string, string>;
  crack_class_supported: boolean;
  scientific_disclaimer: string;
  active_cameras: Array<{
    camera_id: string;
    location: string;
    resolution: string;
    fps: number;
    status: string;
  }>;
}

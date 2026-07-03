export type Role = "admin" | "reviewer" | "mechanic";

export interface User {
  id: string;
  tenant_id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type ClaimStatus =
  | "draft"
  | "queued"
  | "processing"
  | "ready_for_review"
  | "reviewed"
  | "needs_more_evidence"
  | "failed";

export interface Claim {
  id: string;
  tenant_id: string;
  claim_number: string;
  vin: string | null;
  status: ClaimStatus;
  component_id: string | null;
  template_id: string | null;
  claim_reason: string | null;
  mechanic_narrative: string | null;
  removed_serial: string | null;
  replacement_serial: string | null;
  created_by_user_id: string;
  assigned_reviewer_id: string | null;
  completeness_score: number | null;
  risk_score: number | null;
  submitted_at: string | null;
  processed_at: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export interface ClaimList {
  items: Claim[];
  page: number;
  size: number;
  total: number;
}

export type MediaKind = "video" | "image";

export interface MediaAsset {
  id: string;
  claim_id: string;
  kind: MediaKind;
  content_type: string;
  size_bytes: number | null;
  status: string;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  url?: string | null;
}

export interface Frame {
  id: string;
  media_asset_id: string;
  timestamp_s: number;
  frame_index: number;
  is_keyframe: boolean;
  sharpness: number | null;
  url?: string | null;
}

export interface Evidence {
  media: MediaAsset[];
  frames: Frame[];
}

export interface UploadSlot {
  asset_id: string;
  upload_url: string;
  s3_key: string;
}

export interface StageStatus {
  stage: string;
  status: string;
  error: string | null;
}

export interface ClaimStatusResponse {
  claim_id: string;
  status: ClaimStatus;
  processing_error: string | null;
  stages: StageStatus[];
}

export interface Transcript {
  id: string;
  media_asset_id: string | null;
  language: string | null;
  full_text: string;
  segments: { start: number; end: number; text: string }[];
  model_version: string | null;
}

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Detection {
  id: string;
  frame_id: string | null;
  component_label: string | null;
  defect_label: string | null;
  confidence: number;
  severity: number | null;
  bbox: BBox | null;
}

export interface OcrResult {
  id: string;
  field_type: "vin" | "serial" | "label" | "other";
  raw_text: string | null;
  normalized_value: string | null;
  confidence: number;
}

export interface VlmAnalysis {
  id: string;
  frame_id: string | null;
  description: string | null;
  findings: Record<string, unknown> | null;
  model_version: string | null;
}

export interface Completeness {
  id: string;
  required: Record<string, unknown>;
  present: Record<string, boolean>;
  missing: string[];
  score: number;
}

export interface RiskFactor {
  indicator: string;
  weight: number;
  severity: string;
  confidence: number;
  contribution: number;
  evidence_refs: string[];
  source: string;
  note?: string;
}

export interface Risk {
  id: string;
  score: number;
  factors: RiskFactor[];
  rationale: string | null;
  model_version: string | null;
}

export interface Report {
  id: string;
  version: number;
  summary: string | null;
  payload: Record<string, unknown>;
  pdf_url: string | null;
  html_url: string | null;
}

export type Decision = "approved" | "rejected" | "needs_more_evidence" | "escalated";

export interface Review {
  id: string;
  reviewer_id: string;
  decision: Decision;
  notes: string | null;
  created_at: string;
}

export interface PartEvent {
  id: string;
  claim_id: string | null;
  vin: string | null;
  serial: string | null;
  component_code: string | null;
  event_type: string;
  note: string | null;
  created_at: string;
}

export interface BatteryReport {
  id: string;
  source: string;
  vin: string | null;
  pack_id: string | null;
  chemistry: string | null;
  soh_percent: number | null;
  rul_cycles: number | null;
  rul_ci_low: number | null;
  rul_ci_high: number | null;
  capacity_fade_percent: number | null;
  charging: Record<string, unknown> | null;
  faults: { code?: string; desc?: string; severity?: string; ts?: string }[] | null;
  abuse_indicators: string[] | null;
  warranty_leaning: "supports_warranty" | "inconclusive" | "suggests_misuse" | null;
  assessment_note: string | null;
}

export interface VehicleListItem {
  vin: string;
  make: string | null;
  model: string | null;
  profile: string | null;
}

export interface VehiclePassport {
  vin: string;
  vehicle: { make: string | null; model: string | null; profile: string | null; manufactured_at: string | null } | null;
  parts: { serial: string; component_code: string | null; is_active: boolean }[];
  claims: { id: string; claim_number: string; status: ClaimStatus; risk_score: number | null; created_at: string }[];
  part_events: { serial: string | null; event_type: string; created_at: string }[];
  battery_reports: { id: string; soh_percent: number | null; rul_cycles: number | null; warranty_leaning: string | null; created_at: string }[];
  telemetry: TelemetryAssessment;
}

export interface Verdict {
  verdict:
    | "likely_manufacturing_defect"
    | "likely_misuse_or_external"
    | "inconclusive"
    | "insufficient_data";
  confidence: number;
  score: number;
  sources: { source: string; leaning: string; weight: number; contribution: number; note: string | null }[];
  integrity_concern: boolean;
  integrity_notes: string[];
  rationale: string;
  disclaimer: string;
}

export interface TelemetryAssessment {
  vin: string;
  profile: string | null;
  summary: {
    days?: number;
    odometer_km?: number;
    motor_overtemp_days?: number;
    controller_overtemp_days?: number;
    harsh_events?: number;
    overcurrent_events?: number;
    water_ingress_events?: number;
    impact_events?: number;
    motor_temp_slope?: number;
    controller_temp_slope?: number;
  };
  factors: RiskFactor[];
  leaning: string;
  note: string;
  series: { day: string; motor: number | null; controller: number | null }[];
}

export interface DashboardOverview {
  total: number;
  by_status: Record<string, number>;
  pending_review: number;
  processing: number;
}

export interface RiskDistribution {
  low: number;
  elevated: number;
  high: number;
}

export interface CompletenessStats {
  average: number | null;
  lowest: number | null;
  scored_claims: number;
}

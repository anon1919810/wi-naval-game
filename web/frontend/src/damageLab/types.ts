import type { AnalysisResult, ProjectDocument, ProjectDiagnostic, RunStatus } from '../types';

export type Vec3 = [number, number, number];
export type Box = { center_m: Vec3; size_m: Vec3 };
export interface Metadata { source: string | Record<string, unknown>; estimate: boolean }
export interface Room extends Metadata {
  id: string; label?: string; x_m: number; y_m: number; keel_to_bottom_m: number;
  length_m: number; beam_m: number; height_m: number; permeability: number;
}
export interface Module extends Metadata {
  id: string; label: string; role: string; compartment_id: string; box: Box;
  weight_item_ids: string[]; required_staff: number; initial_integrity: number; nominal_shaft_power_kw: number | null;
}
export interface CrewGroup extends Metadata {
  id: string; label: string; compartment_id: string; module_id: string | null; station_box: Box; personnel: number | null;
}
export interface Breach extends Metadata {
  id: string; from_id: string; to_id: string; position_m: Vec3; area_m2: number; discharge_coefficient: number;
}
export interface Experiment extends Metadata {
  schema: 'plimsoll-damage-lab-experiment-1'; duration_s: number; time_step_s: number;
  initial_water_m3: Record<string, number>; modules: Module[]; crew_groups: CrewGroup[]; breaches: Breach[];
  impact: Metadata & { position_m: Vec3; severity: number; radius_m: number };
  rules: Metadata & { casualty_fraction: number; fatal_fraction: number; module_flood_threshold: number; evacuate_fill_fraction: number };
  remaining_gz_angles_deg: number[];
}
export interface LabRequest {
  schema: 'plimsoll-damage-lab-request-1'; condition_id: string; experiment: Experiment; method_versions: Record<string, string>;
}
export interface ModuleState {
  id: string; label: string; compartment_id: string; mechanical_integrity: number;
  flooding_availability: number; staffing_availability: number | null; effective_availability: number | null;
  available_shaft_power_kw: number | null; status: string; causes: string[];
}
export interface CrewState {
  id: string; label: string; compartment_id: string; module_id: string | null; initial_personnel: number | null;
  available: number | null; incapacitated: number | null; dead: number | null; evacuated: number | null;
  location: string; casualty_location: string; evacuated_location: string | null; evacuation_triggered: boolean; causes: string[];
}
export interface Equilibrium { p: number; q: number; waterline_d_m: number; heel_deg: number; trim_deg: number }
export interface TankState { tank_id: string; volume_m3: number; plane_normal: Vec3 | null; plane_offset_m: number | null; fill_fraction: number }
export interface ShipState {
  time_s: number; equilibrium: Equilibrium; total_onboard_water_mass_t: number; total_onboard_water_volume_m3: number;
  mass_conservation_error_t: number; tanks: TankState[];
}
export interface LabState {
  time_s: number; event_index: number; ship: ShipState | null;
  compartments: Array<{ id: string; volume_m3: number; capacity_m3: number; fill_fraction: number }>;
  modules: ModuleState[]; crew_groups: CrewState[];
  capabilities: { shaft_power_kw: number | null; known_shaft_power_subtotal_kw: number };
}
export interface LabEvent { index: number; time_s: number; kind: string; target_id: string | null; message: string }
export interface LabResult {
  schema: 'plimsoll-damage-lab-result-1'; status: RunStatus; condition_id: string; request: LabRequest;
  request_fingerprint: string; input_snapshot: ProjectDocument; core_analysis: AnalysisResult;
  method_versions: Record<string, string>; validity: Record<string, unknown>; diagnostics: ProjectDiagnostic[];
  events: LabEvent[]; snapshots: LabState[]; final_state: LabState; simulated_duration_s: number;
  elapsed_wall_seconds: number; assumptions: string[];
}
export interface LabRun {
  id: string; project_id: string; revision: number; condition_id: string; status: RunStatus;
  request_fingerprint: string; request: LabRequest; result: LabResult | null;
  cancel_requested: boolean; created_at: string; error: { message: string; code: string } | null;
  has_result: boolean;
}
export interface Setup { revision: number; experiment: Experiment | null; diagnostics: ProjectDiagnostic[] }

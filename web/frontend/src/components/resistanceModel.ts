import { numericProblem, numericValue, object, rows, sourceText, type NumericDomain, type Raw } from './formModel';
import type { Dimension } from './units';

// Resistance scenario input contract.
//
// RESISTANCE_INPUTS mirrors `RESISTANCE_INPUTS` in
// tools/plimsoll/project_extensions.py, including each field's numeric domain.
// The only supported methods are the two canonical ones; a sample or invented
// method id would be refused by the schema validator.
//
// An unknown input is omitted from `inputs` (and from `input_provenance`):
// project_extensions rejects orphan provenance keys, so the two objects are
// always written and removed together here.

export interface InputSpec { key: string; label: string; kind: NumericDomain; dimension?: Dimension; storedUnit?: string }

// Density, gravity and kinematic viscosity stay explicitly canonical: no
// dimension is declared for them, so they are typed and shown unchanged.
export const RESISTANCE_INPUTS: InputSpec[] = [
  { key: 'c_stern', label: '艉部系数 c_stern', kind: 'signed' },
  { key: 'bulb_area_m2', label: '球鼻艏面积', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' },
  { key: 'bulb_height_m', label: '球鼻艏高度', kind: 'nonnegative', dimension: 'length', storedUnit: 'm' },
  { key: 'transom_area_m2', label: '浸没尾板面积', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' },
  { key: 'additional_roughness_delta_ca', label: '附加粗糙度 ΔCa', kind: 'nonnegative' },
  { key: 'delta_cf', label: '粗糙度摩擦增量 ΔCf', kind: 'nonnegative' },
  { key: 'x_fore_perpendicular_m', label: '艏垂线纵向位置', kind: 'signed', dimension: 'length', storedUnit: 'm' },
  { key: 'x_aft_perpendicular_m', label: '艉垂线纵向位置', kind: 'signed', dimension: 'length', storedUnit: 'm' },
  { key: 'density_kg_m3', label: '水密度 · kg/m³', kind: 'positive' },
  { key: 'gravity_m_s2', label: '重力加速度 · m/s²', kind: 'positive' },
  { key: 'kinematic_viscosity_m2_s', label: '运动黏度 · m²/s', kind: 'positive' },
];

export const RESISTANCE_METHODS = [
  { id: 'holtrop_mennen_1982', label: 'Holtrop–Mennen 1982' },
  { id: 'taylor_gertler_source_axis_strict', label: 'Taylor–Gertler 源轴严格插值' },
] as const;

export const ATTITUDE_POLICIES = [
  { id: 'strict_upright', label: '严格正浮 strict_upright' },
  { id: 'selected_plane_longitudinal_trim_proxy_v1', label: '所选平面纵倾代理（非主工况 · 估算）' },
] as const;

export const FRICTION_METHOD = 'schoenherr_implicit_ittc_0.242';
export const INTERPOLATION_METHOD = 'taylor_gertler_source_axis_strict';
export const SPEED_CONVERSION_METHOD = 'international_knot_exact';

export const APPENDAGE_AREA: InputSpec = { key: 'area_m2', label: '附体面积', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' };
export const APPENDAGE_FACTOR: InputSpec = { key: 'factor', label: '附体阻力增量系数', kind: 'positive' };
export const THRUSTER_DIAMETER: InputSpec = { key: 'diameter_m', label: '首侧推隧道直径', kind: 'positive', dimension: 'length', storedUnit: 'm' };
export const THRUSTER_COEFFICIENT: InputSpec = { key: 'coefficient', label: '首侧推增量系数', kind: 'positive' };

export function scenarioInputs(scenario: Raw): Raw { return object(scenario.inputs); }
export function inputProvenance(scenario: Raw): Raw { return object(scenario.input_provenance); }

// Write or clear one scalar input together with its provenance entry. Clearing
// removes both keys: an orphan provenance key is a schema error, and an omitted
// input is the explicit "unknown" of this contract. An out-of-domain value is
// refused with a message and never written into the draft.
export function patchInput(scenario: Raw, spec: InputSpec, raw: string): { scenario: Raw; problem: string | null } {
  const problem = numericProblem(spec.kind, raw);
  if (problem) return { scenario, problem };
  const inputs = { ...scenarioInputs(scenario) };
  const provenance = { ...inputProvenance(scenario) };
  if (raw.trim() === '') {
    delete inputs[spec.key];
    delete provenance[spec.key];
    return { scenario: { ...scenario, inputs, input_provenance: provenance }, problem: null };
  }
  inputs[spec.key] = numericValue(raw);
  provenance[spec.key] = { source: null, estimate: null, ...object(provenance[spec.key]) };
  return { scenario: { ...scenario, inputs, input_provenance: provenance }, problem: null };
}

// Store an already-canonical value (from a converted input) with its provenance,
// keeping inputs and input_provenance in step.
export function patchInputValue(scenario: Raw, spec: InputSpec, value: number | null): Raw {
  const inputs = { ...scenarioInputs(scenario) };
  const provenance = { ...inputProvenance(scenario) };
  if (value === null) {
    delete inputs[spec.key];
    delete provenance[spec.key];
  } else {
    inputs[spec.key] = value;
    provenance[spec.key] = { source: null, estimate: null, ...object(provenance[spec.key]) };
  }
  return { ...scenario, inputs, input_provenance: provenance };
}

export function patchProvenance(scenario: Raw, key: string, patch: Raw): Raw {
  const inputs = { ...scenarioInputs(scenario) };
  // Provenance without a value is legitimate research input ("the source is
  // known, the number is not"), so an explicit nullable input is written. An
  // orphan `input_provenance` key would be refused on save.
  if (!(key in inputs)) inputs[key] = null;
  const provenance = { ...inputProvenance(scenario) };
  provenance[key] = { ...object(provenance[key]), ...patch };
  return { ...scenario, inputs, input_provenance: provenance };
}

// `[]` is declared absence for appendages and `{present: false}` for the bow
// thruster; an omitted or null entry is unknown. All six transitions work per
// structured key, and the thruster geometry keys are dropped when it becomes
// absent because project_extensions rejects an absent thruster that still
// carries `diameter_m` / `coefficient`.
export type PresenceState = 'unknown' | 'absent' | 'present';
export type StructuredKey = 'appendages' | 'bow_thruster';

const STRUCTURED_SHAPE: Record<StructuredKey, 'list' | 'object'> = {
  appendages: 'list', bow_thruster: 'object',
};

export function presenceState(scenario: Raw, key: StructuredKey): PresenceState {
  const inputs = scenarioInputs(scenario);
  if (!(key in inputs) || inputs[key] === null) return 'unknown';
  const value = inputs[key];
  if (STRUCTURED_SHAPE[key] === 'list') {
    if (!Array.isArray(value)) return 'unknown';
    return value.length === 0 ? 'absent' : 'present';
  }
  const record = object(value);
  if (record.present === false) return 'absent';
  return record.present === true ? 'present' : 'unknown';
}

export function setPresence(scenario: Raw, key: StructuredKey, state: PresenceState): Raw {
  const inputs = { ...scenarioInputs(scenario) };
  const provenance = { ...inputProvenance(scenario) };
  if (state === 'unknown') {
    delete inputs[key];
    delete provenance[key];
    return { ...scenario, inputs, input_provenance: provenance };
  }
  if (STRUCTURED_SHAPE[key] === 'list') {
    const current = Array.isArray(inputs[key]) ? inputs[key] as Raw[] : [];
    // Declared presence without geometry is one unknown row, never an empty
    // list: `[]` means declared absence.
    inputs[key] = state === 'absent' ? [] : (current.length ? current : [{ area_m2: null, factor: null }]);
  } else {
    inputs[key] = state === 'absent' ? { present: false } : { present: true, diameter_m: null, coefficient: null };
  }
  provenance[key] = { source: null, estimate: null, ...object(provenance[key]) };
  return { ...scenario, inputs, input_provenance: provenance };
}

export function appendages(scenario: Raw): Raw[] { return rows(scenarioInputs(scenario).appendages); }
export function bowThruster(scenario: Raw): Raw { return object(scenarioInputs(scenario).bow_thruster); }

// An empty appendage list is declared absence: removing the last row is an
// explicit "this scenario has no appendages" statement, not a silent unknown.
export function withAppendages(scenario: Raw, list: Raw[]): Raw {
  const provenance = { ...inputProvenance(scenario) };
  provenance.appendages = { source: null, estimate: null, ...object(provenance.appendages) };
  return { ...scenario, inputs: { ...scenarioInputs(scenario), appendages: list }, input_provenance: provenance };
}
export function addAppendage(scenario: Raw): Raw {
  return withAppendages(scenario, [...appendages(scenario), { area_m2: null, factor: null }]);
}
export function removeAppendage(scenario: Raw, index: number): Raw {
  return withAppendages(scenario, appendages(scenario).filter((_, i) => i !== index));
}
export function patchAppendage(scenario: Raw, index: number, patch: Raw): Raw {
  return withAppendages(scenario, appendages(scenario).map((row, i) => i === index ? { ...row, ...patch } : row));
}
export function patchThruster(scenario: Raw, patch: Raw): Raw {
  const provenance = { ...inputProvenance(scenario) };
  provenance.bow_thruster = { source: null, estimate: null, ...object(provenance.bow_thruster) };
  return { ...scenario, inputs: { ...scenarioInputs(scenario), bow_thruster: { ...bowThruster(scenario), ...patch } }, input_provenance: provenance };
}

export function newScenario(id: string): Raw {
  return {
    id, method: 'holtrop_mennen_1982', attitude_policy: 'strict_upright',
    source: null, estimate: null, inputs: {}, input_provenance: {},
  };
}

export function scenarioSource(scenario: Raw): string { return sourceText(scenario.source); }

function knownSource(value: unknown): boolean {
  return typeof value === 'string' ? value.trim() !== '' : !!value && typeof value === 'object' && Object.keys(value).length > 0;
}

// Inline readiness hints only. The backend remains the authority for whether a
// scenario is calculable; this never claims that a result exists.
export function scenarioHints(scenario: Raw): string[] {
  const hints: string[] = [];
  if (!knownSource(scenario.source)) hints.push('缺少研究来源');
  if (typeof scenario.estimate !== 'boolean') hints.push('缺少估算状态声明');
  const inputs = scenarioInputs(scenario);
  const provenance = inputProvenance(scenario);
  for (const spec of RESISTANCE_INPUTS) {
    if (!(spec.key in inputs)) continue;
    const entry = object(provenance[spec.key]);
    if (!knownSource(entry.source) || typeof entry.estimate !== 'boolean') hints.push(`${spec.label} 缺少来源或估算状态`);
  }
  for (const key of ['appendages', 'bow_thruster'] as StructuredKey[]) {
    if (!(key in inputs) || inputs[key] === null) continue;
    const entry = object(provenance[key]);
    if (!knownSource(entry.source) || typeof entry.estimate !== 'boolean') {
      hints.push(`${key === 'appendages' ? '附体' : '首侧推'}声明缺少来源或估算状态`);
    }
  }
  for (const [index, item] of appendages(scenario).entries()) {
    if (numericProblem('nonnegative', item.area_m2 == null ? '' : String(item.area_m2))
      || numericProblem('positive', item.factor == null ? '' : String(item.factor))) {
      hints.push(`附体 ${index + 1} 的面积或增量系数未声明`);
    }
  }
  const thruster = bowThruster(scenario);
  if (thruster.present === true
    && (numericProblem('positive', thruster.diameter_m == null ? '' : String(thruster.diameter_m))
      || numericProblem('positive', thruster.coefficient == null ? '' : String(thruster.coefficient)))) {
    hints.push('首侧推存在时直径与增量系数都必须为正数');
  }
  if (thruster.present === false && ('diameter_m' in thruster || 'coefficient' in thruster)) {
    hints.push('已声明不存在的首侧推不能携带增量几何');
  }
  const fore = inputs.x_fore_perpendicular_m;
  const aft = inputs.x_aft_perpendicular_m;
  if (typeof fore === 'number' && typeof aft === 'number' && fore <= aft) {
    hints.push('艏垂线必须位于艉垂线之前');
  }
  if ('qpc_sensitivity' in scenario) {
    const sensitivity = object(scenario.qpc_sensitivity);
    const values = sensitivity.values;
    const increasing = Array.isArray(values) && values.length >= 1 && values.length <= 21
      && values.every((value: unknown) => typeof value === 'number' && value > 0)
      && values.every((value: number, i: number) => i === 0 || value > values[i - 1]);
    if (!increasing) hints.push('QPC 敏感性须为 1–21 个严格递增正数');
    if (!knownSource(sensitivity.source) || typeof sensitivity.estimate !== 'boolean') {
      hints.push('QPC 敏感性缺少来源或估算状态');
    }
  }
  if ('qpc' in scenario) {
    const qpc = object(scenario.qpc);
    if (typeof qpc.value !== 'number' || !(qpc.value > 0) || !knownSource(qpc.source) || typeof qpc.estimate !== 'boolean') {
      hints.push('QPC 需要正数、来源和明确估算状态');
    }
  }
  if (typeof scenario.table_sha256 === 'string' && !/^[0-9a-f]{64}$/.test(scenario.table_sha256)) {
    hints.push('表身份 SHA-256 必须是 64 位小写十六进制');
  }
  return hints;
}
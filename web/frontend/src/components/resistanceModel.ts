import { englishCopy, numericProblem, numericValue, object, rows, sourceText, type NumericDomain, type Raw } from './formModel';
import type { Copy } from './diagnosticGuidance';
import type { Dimension } from './units';
import type { WorkspaceKey } from '../i18n/workspace';

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
//
// Every label and every readiness hint is a dictionary key read through the
// `Copy` the caller passes, so this module stays pure and language-neutral.

export interface InputSpec { key: string; label: WorkspaceKey; kind: NumericDomain; dimension?: Dimension; storedUnit?: string }

// Density, gravity and kinematic viscosity stay explicitly canonical: no
// dimension is declared for them, so they are typed and shown unchanged.
export const RESISTANCE_INPUTS: InputSpec[] = [
  { key: 'c_stern', label: 'resistanceInput.c_stern', kind: 'signed' },
  { key: 'bulb_area_m2', label: 'resistanceInput.bulb_area_m2', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' },
  { key: 'bulb_height_m', label: 'resistanceInput.bulb_height_m', kind: 'nonnegative', dimension: 'length', storedUnit: 'm' },
  { key: 'transom_area_m2', label: 'resistanceInput.transom_area_m2', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' },
  { key: 'additional_roughness_delta_ca', label: 'resistanceInput.additional_roughness_delta_ca', kind: 'nonnegative' },
  { key: 'delta_cf', label: 'resistanceInput.delta_cf', kind: 'nonnegative' },
  { key: 'x_fore_perpendicular_m', label: 'resistanceInput.x_fore_perpendicular_m', kind: 'signed', dimension: 'length', storedUnit: 'm' },
  { key: 'x_aft_perpendicular_m', label: 'resistanceInput.x_aft_perpendicular_m', kind: 'signed', dimension: 'length', storedUnit: 'm' },
  { key: 'density_kg_m3', label: 'resistanceInput.density_kg_m3', kind: 'positive' },
  { key: 'gravity_m_s2', label: 'resistanceInput.gravity_m_s2', kind: 'positive' },
  { key: 'kinematic_viscosity_m2_s', label: 'resistanceInput.kinematic_viscosity_m2_s', kind: 'positive' },
];

/**
 * A method's own name is a proper noun and reads the same in both languages, so
 * it still gets a key: routing it through the dictionary keeps every label on
 * this page in one place without inventing a translation for a citation.
 */
export const RESISTANCE_METHODS = [
  { id: 'holtrop_mennen_1982', label: 'resistanceMethod.holtropMennen' },
  { id: 'taylor_gertler_source_axis_strict', label: 'resistanceMethod.taylorGertler' },
] as const satisfies ReadonlyArray<{ id: string; label: WorkspaceKey }>;

export const ATTITUDE_POLICIES = [
  { id: 'strict_upright', label: 'resistancePolicy.upright' },
  { id: 'selected_plane_longitudinal_trim_proxy_v1', label: 'resistancePolicy.trimProxy' },
] as const satisfies ReadonlyArray<{ id: string; label: WorkspaceKey }>;

export const FRICTION_METHOD = 'schoenherr_implicit_ittc_0.242';
export const INTERPOLATION_METHOD = 'taylor_gertler_source_axis_strict';
export const SPEED_CONVERSION_METHOD = 'international_knot_exact';

export const APPENDAGE_AREA: InputSpec = { key: 'area_m2', label: 'resistanceInput.appendageArea', kind: 'nonnegative', dimension: 'area', storedUnit: 'm' };
export const APPENDAGE_FACTOR: InputSpec = { key: 'factor', label: 'resistanceInput.appendageFactor', kind: 'positive' };
export const THRUSTER_DIAMETER: InputSpec = { key: 'diameter_m', label: 'resistanceInput.thrusterDiameter', kind: 'positive', dimension: 'length', storedUnit: 'm' };
export const THRUSTER_COEFFICIENT: InputSpec = { key: 'coefficient', label: 'resistanceInput.thrusterCoefficient', kind: 'positive' };

export function scenarioInputs(scenario: Raw): Raw { return object(scenario.inputs); }
export function inputProvenance(scenario: Raw): Raw { return object(scenario.input_provenance); }

// Write or clear one scalar input together with its provenance entry. Clearing
// removes both keys: an orphan provenance key is a schema error, and an omitted
// input is the explicit "unknown" of this contract. An out-of-domain value is
// refused with a message and never written into the draft.
export function patchInput(scenario: Raw, spec: InputSpec, raw: string, w: Copy = englishCopy): { scenario: Raw; problem: string | null } {
  const problem = numericProblem(spec.kind, raw, w);
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
export function scenarioHints(scenario: Raw, w: Copy = englishCopy): string[] {
  const hints: string[] = [];
  if (!knownSource(scenario.source)) hints.push(w('resistance.hint.source'));
  if (typeof scenario.estimate !== 'boolean') hints.push(w('resistance.hint.estimate'));
  const inputs = scenarioInputs(scenario);
  const provenance = inputProvenance(scenario);
  for (const spec of RESISTANCE_INPUTS) {
    if (!(spec.key in inputs)) continue;
    const entry = object(provenance[spec.key]);
    if (!knownSource(entry.source) || typeof entry.estimate !== 'boolean') hints.push(w('resistance.hint.provenance', { label: w(spec.label) }));
  }
  for (const key of ['appendages', 'bow_thruster'] as StructuredKey[]) {
    if (!(key in inputs) || inputs[key] === null) continue;
    const entry = object(provenance[key]);
    if (!knownSource(entry.source) || typeof entry.estimate !== 'boolean') {
      hints.push(w('resistance.hint.structured', { part: w(key === 'appendages' ? 'resistance.part.appendages' : 'resistance.part.thruster') }));
    }
  }
  for (const [index, item] of appendages(scenario).entries()) {
    if (numericProblem('nonnegative', item.area_m2 == null ? '' : String(item.area_m2), w)
      || numericProblem('positive', item.factor == null ? '' : String(item.factor), w)) {
      hints.push(w('resistance.hint.appendage', { index: index + 1 }));
    }
  }
  const thruster = bowThruster(scenario);
  if (thruster.present === true
    && (numericProblem('positive', thruster.diameter_m == null ? '' : String(thruster.diameter_m), w)
      || numericProblem('positive', thruster.coefficient == null ? '' : String(thruster.coefficient), w))) {
    hints.push(w('resistance.hint.thrusterPositive'));
  }
  if (thruster.present === false && ('diameter_m' in thruster || 'coefficient' in thruster)) {
    hints.push(w('resistance.hint.thrusterAbsent'));
  }
  const fore = inputs.x_fore_perpendicular_m;
  const aft = inputs.x_aft_perpendicular_m;
  if (typeof fore === 'number' && typeof aft === 'number' && fore <= aft) {
    hints.push(w('resistance.hint.perpendicular'));
  }
  if ('qpc_sensitivity' in scenario) {
    const sensitivity = object(scenario.qpc_sensitivity);
    const values = sensitivity.values;
    const increasing = Array.isArray(values) && values.length >= 1 && values.length <= 21
      && values.every((value: unknown) => typeof value === 'number' && value > 0)
      && values.every((value: number, i: number) => i === 0 || value > values[i - 1]);
    if (!increasing) hints.push(w('resistance.hint.qpcSensitivity'));
    if (!knownSource(sensitivity.source) || typeof sensitivity.estimate !== 'boolean') {
      hints.push(w('resistance.hint.qpcSource'));
    }
  }
  if ('qpc' in scenario) {
    const qpc = object(scenario.qpc);
    if (typeof qpc.value !== 'number' || !(qpc.value > 0) || !knownSource(qpc.source) || typeof qpc.estimate !== 'boolean') {
      hints.push(w('resistance.hint.qpc'));
    }
  }
  if (typeof scenario.table_sha256 === 'string' && !/^[0-9a-f]{64}$/.test(scenario.table_sha256)) {
    hints.push(w('resistance.hint.sha256'));
  }
  return hints;
}
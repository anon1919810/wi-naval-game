import { englishCopy, numericProblem, numericValue, object, rows, stringList, type NumericDomain, type Raw } from './formModel';
import type { Copy } from './diagnosticGuidance';
import type { Dimension } from './units';
import type { WorkspaceKey } from '../i18n/workspace';

// Physical mass-model contract for system leaves.
//
// The four methods, their input keys and their numeric domains mirror
// tools/plimsoll/systems.py (`_calculated_mass`, `_declared_count`,
// `_physical_model_metadata`). Nothing is computed here: a model only proposes
// a mass, the selected loading ledger stays the single mass authority, and a
// proposal is never applied to `weight_groups` by this editor.
//
// Every label this module owns is a dictionary key rather than a string: the
// module stays pure, so it reads the words from the `Copy` the caller passes and
// falls back to English when it has none.

export interface ModelField { key: string; label: WorkspaceKey; kind: NumericDomain; dimension?: Dimension; storedUnit?: string }
export interface MethodSpec {
  id: string; label: WorkspaceKey; fields: ModelField[];
  counted: boolean; ammunition: boolean;
}

// Material density stays canonical under every reader preference, so it declares
// no dimension; geometry and mass inputs are typed in the reader's unit.
export const VOLUME_DENSITY: ModelField[] = [
  { key: 'volume_m3', label: 'massModel.field.volume', kind: 'nonnegative', dimension: 'volume' },
  { key: 'density_kg_m3', label: 'massModel.field.density', kind: 'positive' },
];
export const PLATE_FIELDS: ModelField[] = [
  { key: 'area_m2', label: 'massModel.field.area', kind: 'nonnegative', dimension: 'area' },
  { key: 'thickness_m', label: 'massModel.field.thickness', kind: 'nonnegative', dimension: 'length' },
  { key: 'density_kg_m3', label: 'massModel.field.density', kind: 'positive' },
];
export const UNIT_MASS: ModelField[] = [{ key: 'unit_mass_t', label: 'massModel.field.unitMass', kind: 'nonnegative', dimension: 'mass' }];
export const AMMUNITION_FIELDS: ModelField[] = [
  { key: 'projectile_mass_kg', label: 'massModel.field.projectileMass', kind: 'nonnegative', dimension: 'mass', storedUnit: 'kg' },
  { key: 'charge_mass_kg', label: 'massModel.field.chargeMass', kind: 'nonnegative', dimension: 'mass', storedUnit: 'kg' },
];

export const MASS_METHODS: MethodSpec[] = [
  { id: 'volume_density_mass', label: 'massModel.method.volumeDensity', fields: VOLUME_DENSITY, counted: false, ammunition: false },
  { id: 'plate_area_thickness_density_mass', label: 'massModel.method.plateArea', fields: PLATE_FIELDS, counted: false, ammunition: false },
  { id: 'counted_unit_mass', label: 'massModel.method.countedUnit', fields: UNIT_MASS, counted: true, ammunition: false },
  { id: 'counted_ammunition_mass', label: 'massModel.method.countedAmmunition', fields: AMMUNITION_FIELDS, counted: true, ammunition: true },
];

// Installed counts only. Broadside fields are rejected as mass multipliers by
// the core and must not be offered here either.
export const COUNT_FIELDS = [
  { id: 'installed_count', label: 'massModel.count.installedCount' },
  { id: 'installed_guns', label: 'massModel.count.installedGuns' },
  { id: 'installed_tubes', label: 'massModel.count.installedTubes' },
] as const;

export const ROUNDS_FIELD = 'rounds_per_gun';

export function methodSpec(method: unknown): MethodSpec | null {
  return MASS_METHODS.find(spec => spec.id === method) ?? null;
}

// System leaves are the containers that declare their own ledger/status/mass
// boundary, mirroring systems._system_leaves. Their dotted IDs are the keys the
// systems result uses, so the same ID selects both input and result.
export interface SystemLeaf { id: string; leaf: Raw; labels: string[] }

export function systemLeaves(systems: unknown): SystemLeaf[] {
  const found: SystemLeaf[] = [];
  function visit(value: unknown, prefix: string, labels: string[]) {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return;
    const entries = value as Record<string, unknown>;
    for (const [key, child] of Object.entries(entries)) {
      if (!child || typeof child !== 'object' || Array.isArray(child)) continue;
      const id = prefix ? `${prefix}.${key}` : key;
      const nextLabels = [...labels, key];
      if (['weight_item_ids', 'status', 'mass_models'].some(field => field in (child as Raw))) {
        found.push({ id, leaf: child as Raw, labels: nextLabels });
      } else {
        visit(child, id, nextLabels);
      }
    }
  }
  visit(systems, '', []);
  return found;
}

export function defaultInputs(method: string): Raw {
  const spec = methodSpec(method);
  const inputs: Raw = {};
  for (const field of spec?.fields ?? []) inputs[field.key] = null;
  // The ammunition model names the installed-count field it reads; the core
  // rejects anything other than `rounds_per_gun` (systems._calculated_mass).
  if (spec?.ammunition) inputs.rounds_field = ROUNDS_FIELD;
  return inputs;
}

// Text-valued inputs carry provenance too: an estimated model needs a source and
// estimate flag for *every* input key, not only its numeric ones.
export const TEXT_INPUTS: ModelField[] = [
  { key: 'count_field', label: 'massModel.text.countField', kind: 'signed' },
  { key: 'count_basis', label: 'massModel.text.countBasis', kind: 'signed' },
  { key: 'rounds_field', label: 'massModel.text.roundsField', kind: 'signed' },
];

export function textInputsFor(method: string): ModelField[] {
  const spec = methodSpec(method);
  if (!spec?.counted) return [];
  return spec.ammunition ? TEXT_INPUTS : TEXT_INPUTS.filter(field => field.key !== 'rounds_field');
}

export function newModel(id: string, method: string, linkedWeightItemId: string | null): Raw {
  return {
    id, method, linked_weight_item_id: linkedWeightItemId,
    inputs: defaultInputs(method), input_provenance: {},
    comparison_tolerance: { relative: null, absolute_t: null },
    source: null, estimate: null,
  };
}

export function modelInputs(model: Raw): Raw { return object(model.inputs); }
export function modelProvenance(model: Raw): Raw { return object(model.input_provenance); }

export function patchModelInput(model: Raw, field: ModelField, raw: string, w: Copy = englishCopy): { model: Raw; problem: string | null } {
  const problem = numericProblem(field.kind, raw, w);
  if (problem) return { model, problem };
  const inputs = { ...modelInputs(model) };
  inputs[field.key] = numericValue(raw);
  return { model: { ...model, inputs }, problem: null };
}

export function patchInputProvenance(model: Raw, key: string, patch: Raw): Raw {
  const provenance = { ...modelProvenance(model) };
  provenance[key] = { ...object(provenance[key]), ...patch };
  return { ...model, input_provenance: provenance };
}

function knownSource(value: unknown): boolean {
  return typeof value === 'string' ? value.trim() !== ''
    : !!value && typeof value === 'object' && Object.keys(value).length > 0;
}

// Mirrors _declared_count: exactly one of count_field or count_value, a named
// basis with count_value, and an installed count the system actually declares.
export function countHints(model: Raw, leaf: Raw, w: Copy = englishCopy): string[] {
  const spec = methodSpec(model.method);
  if (!spec?.counted) return [];
  const hints: string[] = [];
  const inputs = modelInputs(model);
  const hasField = 'count_field' in inputs;
  const hasValue = 'count_value' in inputs;
  if (hasField === hasValue) hints.push(w('massModel.hint.countExclusive'));
  if (hasValue) {
    const value = inputs.count_value;
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) hints.push(w('massModel.hint.countValueInteger'));
    if (typeof inputs.count_basis !== 'string' || !inputs.count_basis.trim()) hints.push(w('massModel.hint.countValueBasis'));
  }
  if (hasField && !COUNT_FIELDS.some(field => field.id === inputs.count_field)) {
    hints.push(w('massModel.hint.countFieldId'));
  }
  if (hasField && !hasValue) {
    const field = inputs.count_field as string;
    const count = leaf[field];
    if (typeof count !== 'number' || !Number.isInteger(count) || count < 0) {
      hints.push(w('massModel.hint.countUndeclared', { field }));
    }
  }
  if (spec.ammunition) {
    if (inputs.rounds_field !== ROUNDS_FIELD) hints.push(w('massModel.hint.roundsField', { field: ROUNDS_FIELD }));
    const rounds = leaf[ROUNDS_FIELD];
    if (typeof rounds !== 'number' || !Number.isInteger(rounds) || rounds < 0) {
      hints.push(w('massModel.hint.roundsUndeclared', { field: ROUNDS_FIELD }));
    }
  }
  return hints;
}

export function toleranceHint(model: Raw, w: Copy = englishCopy): string | null {
  const tolerance = object(model.comparison_tolerance);
  const relative = tolerance.relative;
  const absolute = tolerance.absolute_t;
  if (typeof relative !== 'number' || relative < 0 || typeof absolute !== 'number' || absolute < 0) {
    return w('massModel.hint.tolerance');
  }
  return null;
}

// Everything the editor can check without running a kernel: the model stays
// readable as a draft; the kernel rejects an incomplete model instead of
// proposing a mass from incomplete inputs.
function inputLabel(w: Copy, method: string, key: string): string {
  const found = [...(methodSpec(method)?.fields ?? []), ...textInputsFor(method)]
    .find(field => field.key === key);
  return found ? w(found.label) : key;
}

export function modelHints(model: Raw, leaf: Raw, w: Copy = englishCopy): string[] {
  const spec = methodSpec(model.method);
  const hints: string[] = [];
  if (!spec) hints.push(w('massModel.hint.method'));
  const linked = model.linked_weight_item_id;
  if (typeof linked !== 'string' || !linked) hints.push(w('massModel.hint.binding'));
  else if (!stringList(leaf.weight_item_ids).includes(linked)) hints.push(w('massModel.hint.bindingOutside'));
  if (!knownSource(model.source)) hints.push(w('massModel.hint.source'));
  if (typeof model.estimate !== 'boolean') hints.push(w('massModel.hint.estimate'));
  const tolerance = toleranceHint(model, w);
  if (tolerance) hints.push(tolerance);
  const inputs = modelInputs(model);
  for (const field of spec?.fields ?? []) {
    const value = inputs[field.key];
    if (typeof value !== 'number' || !Number.isFinite(value) || numericProblem(field.kind, String(value), w)) {
      hints.push(w('massModel.hint.value', { label: w(field.label) }));
    }
  }
  hints.push(...countHints(model, leaf, w));
  if (model.estimate === true) {
    const provenance = modelProvenance(model);
    for (const key of Object.keys(modelInputs(model))) {
      const entry = object(provenance[key]);
      if (typeof entry.source !== 'string' || !entry.source.trim() || typeof entry.estimate !== 'boolean') {
        hints.push(w('massModel.hint.estimateProvenance', { label: inputLabel(w, String(model.method), key) }));
      }
    }
  }
  return hints;
}

export function modelList(leaf: Raw): Raw[] { return rows(leaf.mass_models); }

export function patchTextInput(model: Raw, key: string, value: string): Raw {
  const inputs = { ...modelInputs(model) };
  if (value === '') delete inputs[key];
  else inputs[key] = value;
  return { ...model, inputs };
}

export function toleranceValue(model: Raw, key: 'relative' | 'absolute_t', raw: string): Raw {
  return { ...model, comparison_tolerance: { ...object(model.comparison_tolerance), [key]: numericValue(raw) } };
}
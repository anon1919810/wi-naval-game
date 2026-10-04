import { numericProblem, numericValue, object, rows, stringList, type NumericDomain, type Raw } from './formModel';
import type { Dimension } from './units';

// Physical mass-model contract for system leaves.
//
// The four methods, their input keys and their numeric domains mirror
// tools/plimsoll/systems.py (`_calculated_mass`, `_declared_count`,
// `_physical_model_metadata`). Nothing is computed here: a model only proposes
// a mass, the selected loading ledger stays the single mass authority, and a
// proposal is never applied to `weight_groups` by this editor.

export interface ModelField { key: string; label: string; kind: NumericDomain; dimension?: Dimension; storedUnit?: string }
export interface MethodSpec {
  id: string; label: string; fields: ModelField[];
  counted: boolean; ammunition: boolean;
}

// Material density stays canonical under every reader preference, so it declares
// no dimension; geometry and mass inputs are typed in the reader's unit.
export const VOLUME_DENSITY: ModelField[] = [
  { key: 'volume_m3', label: '体积', kind: 'nonnegative', dimension: 'volume' },
  { key: 'density_kg_m3', label: '密度 · kg/m³', kind: 'positive' },
];
export const PLATE_FIELDS: ModelField[] = [
  { key: 'area_m2', label: '面积', kind: 'nonnegative', dimension: 'area' },
  { key: 'thickness_m', label: '厚度', kind: 'nonnegative', dimension: 'length' },
  { key: 'density_kg_m3', label: '密度 · kg/m³', kind: 'positive' },
];
export const UNIT_MASS: ModelField[] = [{ key: 'unit_mass_t', label: '单具质量', kind: 'nonnegative', dimension: 'mass' }];
export const AMMUNITION_FIELDS: ModelField[] = [
  { key: 'projectile_mass_kg', label: '弹丸质量', kind: 'nonnegative', dimension: 'mass', storedUnit: 'kg' },
  { key: 'charge_mass_kg', label: '装药质量', kind: 'nonnegative', dimension: 'mass', storedUnit: 'kg' },
];

export const MASS_METHODS: MethodSpec[] = [
  { id: 'volume_density_mass', label: '体积 × 密度', fields: VOLUME_DENSITY, counted: false, ammunition: false },
  { id: 'plate_area_thickness_density_mass', label: '面积 × 厚度 × 密度', fields: PLATE_FIELDS, counted: false, ammunition: false },
  { id: 'counted_unit_mass', label: '计数 × 单具质量', fields: UNIT_MASS, counted: true, ammunition: false },
  { id: 'counted_ammunition_mass', label: '计数 × 每炮携弹 × 弹重', fields: AMMUNITION_FIELDS, counted: true, ammunition: true },
];

// Installed counts only. Broadside fields are rejected as mass multipliers by
// the core and must not be offered here either.
export const COUNT_FIELDS = [
  { id: 'installed_count', label: '装舰数量 installed_count' },
  { id: 'installed_guns', label: '装舰炮数 installed_guns' },
  { id: 'installed_tubes', label: '装舰管数 installed_tubes' },
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
  { key: 'count_field', label: '装舰数量字段', kind: 'signed' },
  { key: 'count_basis', label: '计数依据', kind: 'signed' },
  { key: 'rounds_field', label: '携弹数字段', kind: 'signed' },
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

export function patchModelInput(model: Raw, field: ModelField, raw: string): { model: Raw; problem: string | null } {
  const problem = numericProblem(field.kind, raw);
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
export function countHints(model: Raw, leaf: Raw): string[] {
  const spec = methodSpec(model.method);
  if (!spec?.counted) return [];
  const hints: string[] = [];
  const inputs = modelInputs(model);
  const hasField = 'count_field' in inputs;
  const hasValue = 'count_value' in inputs;
  if (hasField === hasValue) hints.push('必须且只能声明 count_field 或 count_value 之一');
  if (hasValue) {
    const value = inputs.count_value;
    if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) hints.push('count_value 必须是非负整数');
    if (typeof inputs.count_basis !== 'string' || !inputs.count_basis.trim()) hints.push('count_value 必须声明 count_basis');
  }
  if (hasField && !COUNT_FIELDS.some(field => field.id === inputs.count_field)) {
    hints.push('count_field 必须是装舰数量字段，不能使用单舷字段');
  }
  if (hasField && !hasValue) {
    const field = inputs.count_field as string;
    const count = leaf[field];
    if (typeof count !== 'number' || !Number.isInteger(count) || count < 0) {
      hints.push(`本系统未声明 ${field} 的装舰数量，核心不能用未知计数计算`);
    }
  }
  if (spec.ammunition) {
    if (inputs.rounds_field !== ROUNDS_FIELD) hints.push(`rounds_field 必须是 ${ROUNDS_FIELD}`);
    const rounds = leaf[ROUNDS_FIELD];
    if (typeof rounds !== 'number' || !Number.isInteger(rounds) || rounds < 0) {
      hints.push(`弹药模型需要本系统声明 ${ROUNDS_FIELD}`);
    }
  }
  return hints;
}

export function toleranceHint(model: Raw): string | null {
  const tolerance = object(model.comparison_tolerance);
  const relative = tolerance.relative;
  const absolute = tolerance.absolute_t;
  if (typeof relative !== 'number' || relative < 0 || typeof absolute !== 'number' || absolute < 0) {
    return '比较容差必须显式声明相对值与绝对值（核心不接受缺省）';
  }
  return null;
}

// Everything the editor can check without running a kernel: the model stays
// readable as a draft; the kernel rejects an incomplete model instead of
// proposing a mass from incomplete inputs.
function inputLabel(method: string, key: string): string {
  return [...(methodSpec(method)?.fields ?? []), ...textInputsFor(method)]
    .find(field => field.key === key)?.label ?? key;
}

export function modelHints(model: Raw, leaf: Raw): string[] {
  const spec = methodSpec(model.method);
  const hints: string[] = [];
  if (!spec) hints.push('未选择已审查的质量模型方法');
  const linked = model.linked_weight_item_id;
  if (typeof linked !== 'string' || !linked) hints.push('必须绑定本系统已链接的账本条目');
  else if (!stringList(leaf.weight_item_ids).includes(linked)) hints.push('绑定条目不在本系统的 weight_item_ids 内');
  if (!knownSource(model.source)) hints.push('缺少模型来源');
  if (typeof model.estimate !== 'boolean') hints.push('缺少模型估算状态');
  const tolerance = toleranceHint(model);
  if (tolerance) hints.push(tolerance);
  const inputs = modelInputs(model);
  for (const field of spec?.fields ?? []) {
    const value = inputs[field.key];
    if (typeof value !== 'number' || !Number.isFinite(value) || numericProblem(field.kind, String(value))) {
      hints.push(`${field.label} 未声明或超出数值域`);
    }
  }
  hints.push(...countHints(model, leaf));
  if (model.estimate === true) {
    const provenance = modelProvenance(model);
    for (const key of Object.keys(modelInputs(model))) {
      const entry = object(provenance[key]);
      if (typeof entry.source !== 'string' || !entry.source.trim() || typeof entry.estimate !== 'boolean') {
        hints.push(`估算模型必须为输入 ${inputLabel(String(model.method), key)} 声明来源与估算状态`);
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

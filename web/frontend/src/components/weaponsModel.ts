import { object, rows, stringList, type Raw } from './formModel';

// Weapons-page contract helpers.
//
// `TYPED_FIELDS` mirrors `PAGE_ROW_TYPED_FIELDS` in
// tools/plimsoll/project_extensions.py, including each field's numeric domain.
// Unknown always stays `null`; an out-of-domain entry is refused with a message
// instead of being written into the project, because the contract validator
// rejects it with a blocking diagnostic on save.
//
// The SPS Weapons page is the torpedo store plus the five positional
// miscellaneous zones. Their contract leaves are `torpedo` and `misc_weight`
// (see tools/plimsoll/cases/projects/queen_mary_1913.project.json); every other
// `systems.weapons` leaf is a gun battery and is edited on the Guns page.

export type TypedKind = 'text' | 'integer' | 'positive' | 'nonnegative' | 'signed';

export const TYPED_FIELDS: Record<string, { label: string; kind: TypedKind }> = {
  tubes: { label: '管数', kind: 'integer' },
  carried: { label: '携带数', kind: 'integer' },
  sets: { label: '组数', kind: 'integer' },
  diameter_mm: { label: '雷径 · mm', kind: 'positive' },
  length_m: { label: '雷长 · m', kind: 'positive' },
  arrangement: { label: '布置', kind: 'text' },
  count: { label: '数量', kind: 'integer' },
  reloads: { label: '再装填', kind: 'integer' },
  kind: { label: '类型', kind: 'text' },
  unit_weight_kg: { label: '单具质量 · kg', kind: 'nonnegative' },
  mass_t: { label: '质量 · t', kind: 'nonnegative' },
  height_m: { label: '高度 · m', kind: 'positive' },
  inclination_deg: { label: '倾角 · °', kind: 'signed' },
  beam_between_m: { label: '间距 · m', kind: 'positive' },
  construction_type: { label: '构造型式', kind: 'text' },
  coverage_pct: { label: '覆盖度 · %', kind: 'nonnegative' },
};

export function typedProblem(field: string, raw: string): string | null {
  const spec = TYPED_FIELDS[field];
  if (!spec) return '该字段不在契约允许的类型化字段中';
  if (raw.trim() === '') return null;
  if (spec.kind === 'text') return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return '必须是有限数值';
  if (spec.kind === 'integer') return Number.isInteger(value) && value >= 0 ? null : '必须是非负整数';
  if (spec.kind === 'positive') return value > 0 ? null : '必须是正数';
  if (spec.kind === 'nonnegative') return value >= 0 ? null : '不能为负数';
  return null;
}

export function typedValue(field: string, raw: string): unknown {
  if (raw.trim() === '') return null;
  return TYPED_FIELDS[field]?.kind === 'text' ? raw : Number(raw);
}

export const TORPEDO_LEAF = 'torpedo';
export const MISC_LEAF = 'misc_weight';
export const WEAPONS_PAGE_LEAVES = [TORPEDO_LEAF, MISC_LEAF] as const;
export type WeaponsLeafId = typeof WEAPONS_PAGE_LEAVES[number];

export function isWeaponsPageLeaf(id: string): boolean {
  return WEAPONS_PAGE_LEAVES.includes(id as WeaponsLeafId);
}

export interface RowTemplate { id: string; label: string; typed: Record<string, null> }

export const TORPEDO_TEMPLATES: RowTemplate[] = [
  { id: 'torpedo_main', label: '鱼雷管（主）', typed: { tubes: null, carried: null, diameter_mm: null, length_m: null, arrangement: null } },
  { id: 'torpedo_secondary', label: '鱼雷管（副）', typed: { tubes: null, carried: null, diameter_mm: null, length_m: null, arrangement: null } },
  { id: 'mines', label: '水雷', typed: { count: null, kind: null, unit_weight_kg: null } },
  { id: 'depth_charges', label: '深弹', typed: { count: null, kind: null, unit_weight_kg: null } },
];

export const MISC_TEMPLATES: RowTemplate[] = [
  { id: 'hull_below', label: '水下船体', typed: { mass_t: null } },
  { id: 'hull_above', label: '水上船体', typed: { mass_t: null } },
  { id: 'on_deck', label: '甲板上', typed: { mass_t: null } },
  { id: 'above_deck', label: '甲板以上', typed: { mass_t: null } },
  { id: 'void', label: '空舱', typed: { mass_t: null } },
];

export function templatesFor(leafId: WeaponsLeafId): RowTemplate[] {
  return leafId === TORPEDO_LEAF ? TORPEDO_TEMPLATES : MISC_TEMPLATES;
}

export function declaredRows(leaf: Raw): Raw[] { return rows(leaf.page_rows); }

// A weapons leaf must keep an explicit ledger boundary key: without
// weight_item_ids / status / mass_models the core treats the dict as a nested
// system container and refuses it (systems._system_leaves).
export function withBoundary(leaf: Raw, ids: string[]): Raw {
  return { ...leaf, weight_item_ids: ids };
}

// `page_rows` must be a nonempty array (project_extensions._page_rows), so an
// empty declaration is expressed by omitting the key rather than by `[]`.
export function withRows(leaf: Raw, declared: Raw[]): Raw {
  const next = { ...leaf };
  if (declared.length === 0) delete next.page_rows;
  else next.page_rows = declared;
  return next;
}
export function rowBoundIds(declared: Raw[]): string[] {
  return [...new Set(declared.flatMap(row => stringList(row.weight_item_ids)))];
}
export function declaredMass(row: Raw): number | null {
  const value = object(row.typed).mass_t;
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
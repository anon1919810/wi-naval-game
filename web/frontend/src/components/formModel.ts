import type { ProjectDocument, RunView } from '../types';

export type Raw = Record<string, unknown>;

export function object(value: unknown): Raw {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Raw : {};
}
export function rows(value: unknown): Raw[] { return Array.isArray(value) ? value.map(object) : []; }
export function number(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}
export function inputNumber(value: string): number | null {
  return value.trim() === '' ? null : number(Number(value));
}
export function sourceText(value: unknown): string {
  return typeof value === 'string' ? value : value == null ? '' : JSON.stringify(value);
}
export function fact(value: unknown): Raw {
  return { value: null, source: null, estimate: null, ...object(value) };
}
export function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((id): id is string => typeof id === 'string' && id !== '') : [];
}

// Only these two statuses carry a stored analysis payload (web/backend/plimsoll_web/
// worker.py writes `result` exactly when the analysis status is completed/partial).
export const RESULT_STATUSES: ReadonlyArray<string> = ['completed', 'partial'];

// Newest completed/partial run of exactly this saved revision and condition.
// Any other revision or condition describes a different selected loading and must
// never be presented as the current one.
export function eligibleResultRun(runs: RunView[], revision: number, conditionId: string): RunView | null {
  if (!conditionId) return null;
  let best: RunView | null = null;
  for (const run of runs) {
    if (!RESULT_STATUSES.includes(run.status)) continue;
    if (run.revision !== revision || run.condition_id !== conditionId) continue;
    if (!best || String(run.created_at ?? '') > String(best.created_at ?? '')) best = run;
  }
  return best;
}

// A run may be presented as the current result only when it describes exactly
// this project, this saved revision and this condition, carries a payload, and
// the draft is clean (an unsaved draft is not the analysed input).
export function currentRun(result: RunView | null, projectId: string, revision: number,
  conditionId: string, dirty: boolean): RunView | null {
  if (dirty || !result || !result.result) return null;
  if (result.project_id !== projectId || result.revision !== revision) return null;
  if (result.condition_id !== conditionId) return null;
  return RESULT_STATUSES.includes(result.status) ? result : null;
}
export function stageData(run: RunView | null, stage: string): Raw { return object(run?.result?.stages[stage]?.data); }

// Ledger items are the only source of system mass; every binding must name one.
export function ledgerItems(project: ProjectDocument): Array<{ id: string; label: string }> {
  return project.weight_groups.flatMap(group => group.items
    .filter(item => item && typeof item.id === 'string' && item.id !== '')
    .map(item => ({ id: String(item.id), label: `${group.label || group.id} / ${item.id}` })));
}
export function unassignedIds(previous: string[], bound: string[]): string[] {
  const taken = new Set(bound);
  return previous.filter(id => !taken.has(id));
}
export function uniqueId(base: string, taken: ReadonlyArray<unknown>): string {
  if (!taken.includes(base)) return base;
  let n = 2;
  while (taken.includes(`${base}_${n}`)) n += 1;
  return `${base}_${n}`;
}

// Mirrors the numeric domains of tools/plimsoll/project_extensions.py and the
// mass-model checks in tools/plimsoll/systems.py. An empty input means unknown
// and stays unknown; a typed out-of-domain value is refused with a message
// instead of being written into the project.
export type NumericDomain = 'signed' | 'nonnegative' | 'positive' | 'integer';

export function numericProblem(kind: NumericDomain, raw: string): string | null {
  if (raw.trim() === '') return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return '必须是有限数值';
  if (kind === 'integer') return Number.isInteger(value) && value >= 0 ? null : '必须是非负整数';
  if (kind === 'positive') return value > 0 ? null : '必须是正数';
  if (kind === 'nonnegative') return value >= 0 ? null : '不能为负数';
  return null;
}

export function numericValue(raw: string): number | null {
  return raw.trim() === '' ? null : Number(raw);
}
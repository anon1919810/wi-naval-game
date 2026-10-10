import type { LabResult, LabRun } from './types';

function ordered(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(ordered);
  if (value && typeof value === 'object') return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b))
    .map(([key, child]) => [key, ordered(child)]));
  return value;
}
export const draftIdentity = (value: unknown) => JSON.stringify(ordered(value));

export function visibleResult(run: LabRun | null, projectId: string, revision: number, condition: string, experiment: unknown): LabResult | null {
  return run?.project_id === projectId && run.revision === revision && run.condition_id === condition
    && draftIdentity(run.request.experiment) === draftIdentity(experiment) ? run.result : null;
}
export function frameAt(result: LabResult | null, position: number) {
  if (!result?.snapshots.length) return null;
  return result.snapshots[Math.max(0, Math.min(result.snapshots.length - 1, Math.trunc(position)))];
}
export const active = (run: LabRun | null) => run?.status === 'queued' || run?.status === 'running';
export const numeric = (value: number | null | undefined, digits = 1) => value == null || !Number.isFinite(value) ? '未知' : value.toFixed(digits);
export const percent = (value: number | null | undefined) => value == null ? '未知' : `${Math.round(value*100)}%`;
export const STATUS: Record<string, string> = { queued: '排队中', running: '计算中', completed: '计算完成', partial: '部分结果', canceled: '已取消', failed: '失败' };

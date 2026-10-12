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

/**
 * The run statuses this page can show.
 *
 * The status strings are not here any more: they belong to the laboratory
 * dictionary, so they follow the one language state rather than being a frozen
 * Chinese literal inside a model module. `format.status` resolves them.
 */
export const STATUS_KEYS = ['queued', 'running', 'completed', 'partial', 'canceled', 'failed'] as const;

import { call } from '../api';
import type { ProjectDocument, ProjectView } from '../types';
import type { Experiment, LabRun, Setup } from './types';

const segment = encodeURIComponent;
export const readProject = (id: string, signal?: AbortSignal) => call<ProjectView>(`/projects/${segment(id)}`, { signal });
export const readSetup = (id: string, signal?: AbortSignal) => call<Setup>(`/projects/${segment(id)}/damage-lab-setup`, { signal });
export const listRuns = (id: string, signal?: AbortSignal) => call<LabRun[]>(`/projects/${segment(id)}/damage-lab-runs`, { signal });
export const readRun = (id: string, signal?: AbortSignal) => call<LabRun>(`/damage-lab-runs/${segment(id)}`, { signal });
export const enqueue = (id: string, revision: number, condition_id: string, experiment: Experiment) =>
  call<LabRun>(`/projects/${segment(id)}/damage-lab-runs`, { method: 'POST', body: JSON.stringify({ revision, condition_id, experiment }) });
export const preview = (id: string, revision: number, condition_id: string, experiment: unknown, signal?: AbortSignal) =>
  call<{ experiment: Experiment; request_fingerprint: string }>(`/projects/${segment(id)}/damage-lab-preview`, {
    method: 'POST', body: JSON.stringify({ revision, condition_id, experiment }), signal });
export const cancel = (id: string) => call<LabRun>(`/damage-lab-runs/${segment(id)}/cancel`, { method: 'POST', body: '{}' });
export const readDemo = () => call<{ project: ProjectDocument; experiment: Experiment }>('/damage-lab-demo');
export const exportUrl = (id: string, format: 'json' | 'csv') => `/api/damage-lab-runs/${segment(id)}/export?format=${format}`;

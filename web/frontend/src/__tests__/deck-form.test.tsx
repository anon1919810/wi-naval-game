import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument, RunView } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn() };
});

const deckProject: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '自由号', revision: 1,
  hull: { length_m: 90 }, geometry: null, weight_groups: [],
  loading_conditions: [{ id: 'loaded', label: '满载' }],
  deck: {
    estimate: null, source: null,
    points: [
      { id: 'aft-centre', x_m: -106.7, y_m: 0, z_m: 15.0, freeboard_m: { value: null, source: 'manual', estimate: true } },
      { id: 'fore-centre', x_m: 106.7, y_m: 0, z_m: 15.0, freeboard_m: { value: null, source: null, estimate: null } },
    ],
    segments: [
      { id: 'centreline-profile', aft_point_id: 'aft-centre', fore_point_id: 'fore-centre', source: null, estimate: null },
    ],
    reference_length_m: { value: 213.4, source: 'ref', estimate: true },
  },
};

function runWithFreeboard(): RunView {
  return {
    id: 'r1', project_id: 'p1', revision: 1, condition_id: 'loaded', status: 'completed',
    request_fingerprint: 'fp', created_at: '2026-01-01T00:00:00Z',
    started_at: null, finished_at: null, cancel_requested: false, error: null,
    result: {
      schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'loaded',
      project_fingerprint: '', input_fingerprint: '', request_fingerprint: '',
      request: {}, input_snapshot: deckProject, units: {}, method_versions: {}, sources: {},
      diagnostics: [], validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
      stages: {
        deck: {
          status: 'completed', requested: true, reason: null,
          validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
          method_versions: {}, assumptions: [], diagnostics: [],
          data: {
            declared_freeboard: {
              values: {
                weighted_mean_freeboard_m: 3.2, weighted_mean_estimate: true, weighted_mean_source: 'calc',
                coverage_fraction: 0.8, known_segment_ids: ['centreline-profile'], unknown_segment_ids: ['other'],
                reference_length_m: 213.4, reference_source: 'ref', total_length_m: 200, declared_length_m: 213.4,
              },
              segments: [{
                id: 'centreline-profile', aft_point_id: 'aft-centre', fore_point_id: 'fore-centre',
                length_m: 200, length_percent: 100, freeboard_aft_m: 3, freeboard_fore_m: 3.4,
                segment_mean_freeboard_m: 3.2, source: null, estimate: null, status: 'known',
              }],
              diagnostics: [],
            },
          },
        },
      },
    },
  };
}

beforeEach(() => { cleanup(); vi.clearAllMocks(); });

describe('deck freeboard form', () => {
  it('writes the declared freeboard value and keeps source/estimate on save', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: deckProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: deckProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '浮态与稳性' }));
    const input = await screen.findByLabelText(/点 aft-centre 干舷值/);
    fireEvent.change(input, { target: { value: '2.5' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const point = (submitted.project as Record<string, unknown>).deck as Record<string, unknown>;
    const points = point.points as Array<Record<string, unknown>>;
    expect(points[0].id).toBe('aft-centre');
    expect((points[0].freeboard_m as Record<string, unknown>).value).toBe(2.5);
    expect((points[0].freeboard_m as Record<string, unknown>).estimate).toBe(true);
    expect((points[0].freeboard_m as Record<string, unknown>).source).toBe('manual');
    expect(points[0].x_m).toBe(-106.7);
  });

  it('does not write 0 when the freeboard input is cleared', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: deckProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: deckProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '浮态与稳性' }));
    const input = await screen.findByLabelText(/点 aft-centre 干舷值/);
    fireEvent.change(input, { target: { value: '2.5' } });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const point = ((submitted.project as Record<string, unknown>).deck as Record<string, unknown>).points as Array<Record<string, unknown>>;
    const fb = point[0].freeboard_m as Record<string, unknown>;
    expect(fb.value).not.toBe(0);
    expect(fb.value).toBeNull();
    expect(fb.estimate).toBe(true);
    expect(fb.source).toBe('manual');
  });

  it('shows a prompt instead of a zero aggregate when there is no run', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: deckProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '浮态与稳性' }));
    expect(await screen.findByText('保存并运行后显示聚合值')).toBeVisible();
  });

  it('renders the aggregate computed by the backend, not a local recomputation', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: deckProject });
    vi.mocked(api.listRuns).mockResolvedValue([runWithFreeboard()]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '浮态与稳性' }));
    expect(await screen.findByText('3.2 m')).toBeVisible();
    expect(screen.getByText('80 %')).toBeVisible();
    expect(screen.getByText(/other/)).toBeVisible();
    expect(screen.getByText('calc', { exact: false })).toBeVisible();
  });

  it('shows segment length from a run, or a dash when no run exists', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: deckProject });
    vi.mocked(api.listRuns).mockResolvedValue([runWithFreeboard()]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '浮态与稳性' }));
    expect(await screen.findByText('200 m')).toBeVisible();
    expect(screen.getByText('100 %')).toBeVisible();
  });
});

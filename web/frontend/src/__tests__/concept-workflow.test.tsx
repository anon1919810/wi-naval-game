import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { conceptCopy } from '../i18n/concept';
import { workspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import { Workbench } from '../pages/Workbench';
import { BASE_STAGES } from '../components/PerformanceEditor';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

// The apply-and-recompute chain is the part of this workflow that can quietly do
// damage: it writes a revision, then re-queues a calculation, and a late answer
// to either step could land on a project, revision, condition, request or draft
// the reader has already moved away from. These tests drive the real Workbench
// with deferred promises so each of those boundaries is crossed deliberately.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(),
  getRun: vi.fn(), applyMassProposals: vi.fn() }));

const w = (key: WorkspaceKey, params?: Record<string, string | number>) => workspaceCopy('en', key, params);

const LEDGER = {
  id: 'weights', label: 'declared',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'weapons.mounts', mass_t: 152.407, x_m: 104 },
  ],
};

function project(overrides: Partial<ProjectDocument> = {}): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null,
    loading_conditions: [{ id: 'normal', label: 'Normal' }, { id: 'deep', label: 'Deep' }],
    weight_groups: [LEDGER],
    systems: { weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts'] } } },
    ...overrides,
  } as ProjectDocument;
}

function proposal() {
  return {
    operation: 'replace_weight_item_mass', item_id: 'weapons.guns', current_mass_t: 60.9628,
    proposed_mass_t: 49.79, difference_t: -11.17,
    source_system_id: 'weapons.main', source_model_id: 'concept.main.guns', requires_review: true,
    condition_id: 'normal', target: 'selected_condition', project_fingerprint: 'pf',
    input_fingerprint: 'if', request_fingerprint: 'rf',
    model: { id: 'concept.main.guns', method: 'empirical_estimate_v1', concept_component: 'guns',
      source: { declaration: 'a declared study design' } },
  };
}

function stage(status: StageEnvelope['status'], data: StageEnvelope['data']): StageEnvelope {
  return { status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data };
}

function result(conditionId = 'normal'): AnalysisResult {
  return {
    schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: conditionId,
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: { options: { stages: [...BASE_STAGES] } }, input_snapshot: project(), units: {}, method_versions: {}, sources: {}, diagnostics: [],
    validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    stages: {
      systems: stage('completed', { update_proposals: [proposal()] }),
      design_balance: stage('completed', { status: 'completed', values: { structure_demand_long_tons: 2606.33 } }),
    },
  } as unknown as AnalysisResult;
}

function run(overrides: Partial<RunView> = {}): RunView {
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'rf', created_at: '2026-10-15T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, result: result(), error: null, ...overrides } as RunView;
}

/** A promise whose resolution the test controls. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

let onRun = vi.fn();

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  onRun = vi.fn();
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: /max-width:\s*1280px/.test(query), media: query,
    addEventListener: () => {}, removeEventListener: () => {},
  }));
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: project() });
  vi.mocked(api.listRuns).mockResolvedValue([run()]);
  vi.mocked(api.getRun).mockResolvedValue(run());
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) =>
    ({ project_id: 'p1', revision: 2, project: input.project }));
  vi.mocked(api.enqueueRun).mockResolvedValue({ ...run(), id: 'run-b', revision: 2 } as RunView);
  vi.mocked(api.applyMassProposals).mockResolvedValue({
    project_id: 'p1', revision: 2, project: project({ revision: 2 }),
    changes: [{ target: 'selected_condition', condition_id: 'normal', item_id: 'weapons.guns',
      old_mass_t: 60.9628, new_mass_t: 49.79, estimate: true, source: { method: 'accepted_selected_condition_empirical_estimate' } }],
  });
});

afterEach(() => { vi.unstubAllGlobals(); });

async function openWeights() {
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
  fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
  await screen.findByLabelText('weapons.guns Select');
}

function selectAndApply() {
  fireEvent.click(screen.getByLabelText('weapons.guns Select'));
  fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
}

describe('applying a reviewed batch', () => {
  it('sends the saved revision, run, condition, request and the selected proposals', async () => {
    await openWeights();
    selectAndApply();
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    const [id, body] = vi.mocked(api.applyMassProposals).mock.calls[0];
    expect(id).toBe('p1');
    expect(body.base_revision).toBe(1);
    expect(body.run_id).toBe('run-a');
    expect(body.condition_id).toBe('normal');
    expect(body.proposals).toHaveLength(1);
    // The options are this browser's own assembly, not the normalized request.
    expect(body.current_options).toHaveProperty('stages');
  });

  it('re-queues the same options on the new revision and shows that run', async () => {
    await openWeights();
    selectAndApply();
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalledTimes(1));
    const [id, body] = vi.mocked(api.enqueueRun).mock.calls[0];
    expect(id).toBe('p1');
    expect(body.revision).toBe(2);
    expect(body.condition_id).toBe('normal');
    await waitFor(() => expect(onRun).toHaveBeenCalledWith('run-b'));
  });

  it('refuses a second click while one apply is in flight', async () => {
    await openWeights();
    const first = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    const answer = { project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] };
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(first.promise);
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    const button = screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') });
    fireEvent.click(button);
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    expect(button).toBeDisabled();
    // A second click on the element itself still cannot issue a second request.
    fireEvent.click(button);
    fireEvent.click(button);
    expect(api.applyMassProposals).toHaveBeenCalledTimes(1);
    await act(async () => {
      first.resolve(answer ?? { project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await first.promise;
    });
  });

  it('says the save stands and offers the run again when only the re-run failed', async () => {
    vi.mocked(api.enqueueRun).mockRejectedValue(new api.ApiError(429, 'one active calculation is allowed per account'));
    await openWeights();
    selectAndApply();
    const notice = await screen.findByText(/could not be queued/);
    expect(notice).toHaveTextContent('2');
    expect(notice.textContent).not.toMatch(/roll ?back|undone|discarded the change/i);
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.rerun') }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalledTimes(2));
  });

  it.each(['condition', 'draft'] as const)('does not navigate from a retry after the %s changes', async change => {
    const queued = deferred<RunView>();
    vi.mocked(api.enqueueRun).mockRejectedValueOnce(new api.ApiError(429, 'queue busy'))
      .mockReturnValueOnce(queued.promise);
    await openWeights(); selectAndApply();
    fireEvent.click(await screen.findByRole('button', { name: conceptCopy('en', 'proposals.rerun') }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalledTimes(2));
    if (change === 'condition') {
      fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'deep' } });
      fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'normal' } });
    } else {
      fireEvent.change(screen.getByLabelText(w('editor.ledger.massLabel', { item: 'weights hull.structure' })),
        { target: { value: '4242' } });
    }
    await act(async () => { queued.resolve(run({ id: 'late-retry', revision: 2 })); await queued.promise; });
    expect(onRun).not.toHaveBeenCalled();
    expect(screen.getByRole('button', { name: w('workbench.run.action') })).toBeInTheDocument();
  });

  it('reports a rejected batch with the server’s own reason and writes nothing', async () => {
    vi.mocked(api.applyMassProposals).mockRejectedValue(new api.ApiError(422, [
      { code: 'analysis.proposal_stale', message: 'proposal identity no longer matches', path: '$.proposals[0]' }]));
    await openWeights();
    selectAndApply();
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('proposal identity no longer matches');
    expect(api.enqueueRun).not.toHaveBeenCalled();
    expect(onRun).not.toHaveBeenCalled();
  });

  it('reports a revision conflict from another browser without pretending to save', async () => {
    vi.mocked(api.applyMassProposals).mockRejectedValue(new api.ApiError(409, { current_revision: 7 }));
    await openWeights();
    selectAndApply();
    expect(await screen.findByRole('alert')).toHaveTextContent('7');
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });
});

describe('answers that arrive after the reader has moved on', () => {
  it('hides the old document while the newly selected project is loading', async () => {
    const page = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    await screen.findByLabelText('weapons.guns Select');
    const loading = deferred<Awaited<ReturnType<typeof api.getProject>>>();
    vi.mocked(api.getProject).mockReturnValueOnce(loading.promise);
    const foreign = run({ id: 'p2-run', project_id: 'p2', result: { ...result(), project_id: 'p2' } });
    vi.mocked(api.listRuns).mockResolvedValueOnce([foreign]);
    page.rerender(<Workbench projectId="p2" onBack={vi.fn()} onRun={onRun} />);
    await waitFor(() => expect(api.listRuns).toHaveBeenCalledWith('p2'));
    expect(screen.queryByLabelText('weapons.guns Select')).toBeNull();
    expect(screen.queryByRole('button', { name: w('chapter.weights.label') })).toBeNull();
    expect(api.applyMassProposals).not.toHaveBeenCalled();
    await act(async () => { loading.resolve({ project_id: 'p2', revision: 1,
      project: project({ id: 'p2', name: 'other vessel' }) }); await loading.promise; });
    await screen.findAllByText('other vessel');
  });

  it('retires the saved-but-not-queued notice when another project opens', async () => {
    vi.mocked(api.enqueueRun).mockRejectedValue(new api.ApiError(429, 'queue busy'));
    const page = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    await screen.findByLabelText('weapons.guns Select'); selectAndApply();
    await screen.findByText(/could not be queued/);
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p2', revision: 5,
      project: project({ id: 'p2', revision: 5, name: 'other vessel' }) });
    page.rerender(<Workbench projectId="p2" onBack={vi.fn()} onRun={onRun} />);
    await screen.findAllByText('other vessel');
    expect(screen.queryByText(/could not be queued/)).toBeNull();
    expect(screen.queryByRole('button', { name: conceptCopy('en', 'proposals.rerun') })).toBeNull();
  });

  it('does not let a late save overwrite a newer draft on the same project', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    // The reader types into the ledger while the apply is in flight.
    fireEvent.change(screen.getByLabelText(w('editor.ledger.massLabel', { item: 'weights hull.structure' })),
      { target: { value: '4242' } });
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    await waitFor(() => expect(screen.getByText(w('workbench.save.dirty'))).toBeVisible());
    // The newer edit is still on screen and no re-run was queued for a draft the
    // reader never reviewed.
    expect(screen.getByDisplayValue('4242')).toBeVisible();
    expect(api.enqueueRun).not.toHaveBeenCalled();
    expect(onRun).not.toHaveBeenCalled();
  });

  it('does not let a late save overwrite unapplied raw-JSON edits', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    fireEvent.click(screen.getByRole('button', { name: w('chapter.json.label') }));
    const editor = document.querySelector<HTMLTextAreaElement>('#chapter-json')!;
    fireEvent.change(editor, { target: { value: '{"weight_groups": []}' } });
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(screen.getByText(w('workbench.save.unapplied'))).toBeVisible();
    expect(screen.getByDisplayValue('{"weight_groups": []}')).toBeVisible();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('does not queue a recompute for a condition the reader has left', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    // Switch away and back: the condition identity really did change and change back.
    fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'deep' } });
    fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'normal' } });
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(api.enqueueRun).not.toHaveBeenCalled();
    expect(onRun).not.toHaveBeenCalled();
  });

  it('does not queue a recompute for a request the reader has changed', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    // Enabling the concept screen adds a stage, which is a different request.
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.enable')));
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(api.enqueueRun).not.toHaveBeenCalled();
    expect(onRun).not.toHaveBeenCalled();
  });

  it('does not write into another project when the id changes under an in-flight apply', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    const view = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    await screen.findByLabelText('weapons.guns Select');
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    // The same component instance, a different project: no unmount in between.
    vi.mocked(api.getProject).mockResolvedValue({
      project_id: 'p2', revision: 5, project: project({ id: 'p2', name: 'other vessel', revision: 5 }) });
    view.rerender(<Workbench projectId="p2" onBack={vi.fn()} onRun={onRun} />);
    await screen.findAllByText('other vessel');
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(api.enqueueRun).not.toHaveBeenCalled();
    expect(onRun).not.toHaveBeenCalled();
    // The second project's own state is untouched by the first project's answer.
    expect(screen.getAllByText('other vessel').length).toBeGreaterThan(0);
    expect(screen.queryByText(w('workbench.conflict.title', { revision: 2 }))).toBeNull();
  });

  it('does not navigate from a page the reader has already left', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    const { unmount } = render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    await screen.findByLabelText('weapons.guns Select');
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    await waitFor(() => expect(api.applyMassProposals).toHaveBeenCalledTimes(1));
    unmount();
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(onRun).not.toHaveBeenCalled();
  });
});

describe('the request a draft asks for', () => {
  it('retires proposals when the visible request differs from the saved result', async () => {
    await openWeights();
    fireEvent.click(screen.getByRole('button', { name: w('chapter.performance.label') }));
    fireEvent.change(screen.getByLabelText(w('performance.request.trim')), { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: w('chapter.weights.label') }));
    expect(screen.queryByLabelText('weapons.guns Select')).toBeNull();
    expect(api.applyMassProposals).not.toHaveBeenCalled();
  });

  it('does not navigate for a late enqueue after a condition switch away and back', async () => {
    const queued = deferred<RunView>();
    vi.mocked(api.enqueueRun).mockReturnValueOnce(queued.promise);
    await openWeights();
    selectAndApply();
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'deep' } });
    fireEvent.change(screen.getByLabelText(w('workbench.condition.label')), { target: { value: 'normal' } });
    await act(async () => { queued.resolve(run({ id: 'late', revision: 2 })); await queued.promise; });
    expect(onRun).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: conceptCopy('en', 'proposals.applyBusy') })).toBeNull();
  });

  it('retires an apply after request edits even when the values are restored', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights();
    selectAndApply();
    fireEvent.click(screen.getByRole('button', { name: w('chapter.performance.label') }));
    const trim = screen.getByLabelText(w('performance.request.trim'));
    fireEvent.change(trim, { target: { value: '2' } });
    fireEvent.change(trim, { target: { value: '' } });
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('preserves the context after JSON is edited and explicitly discarded during apply', async () => {
    const answer = deferred<Awaited<ReturnType<typeof api.applyMassProposals>>>();
    vi.mocked(api.applyMassProposals).mockReturnValueOnce(answer.promise);
    await openWeights(); selectAndApply();
    fireEvent.click(screen.getByRole('button', { name: w('chapter.json.label') }));
    fireEvent.change(document.querySelector('#chapter-json')!, { target: { value: '{}' } });
    fireEvent.click(screen.getByRole('button', { name: w('editor.json.discard') }));
    await act(async () => {
      answer.resolve({ project_id: 'p1', revision: 2, project: project({ revision: 2 }), changes: [] });
      await answer.promise;
    });
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });

  it('adds the concept stage only while the section exists, and old projects keep their defaults', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    await screen.findByRole('button', { name: w('chapter.performance.label') });
    fireEvent.click(screen.getByRole('button', { name: w('workbench.run.action') }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
    const stages = vi.mocked(api.enqueueRun).mock.calls[0][1].options.stages as string[];
    expect(stages).not.toContain('design_balance');
  });

  it('asks for the concept screen once the reader has declared one', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.getRun).mockRejectedValue(new Error('no stored result'));
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    fireEvent.click(await screen.findByLabelText(conceptCopy('en', 'concept.enable')));
    // A request only ever runs against a saved revision.
    fireEvent.click(screen.getByRole('button', { name: w('workbench.save.action') }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole('button', { name: w('workbench.run.action') })).toBeEnabled());
    fireEvent.click(screen.getByRole('button', { name: w('workbench.run.action') }));
    await waitFor(() => expect(api.enqueueRun).toHaveBeenCalled());
    const stages = vi.mocked(api.enqueueRun).mock.calls[0][1].options.stages as string[];
    expect(stages).toContain('design_balance');
    expect(stages.filter(name => name === 'design_balance')).toHaveLength(1);
  });
});

describe('the concept editor inside the workbench', () => {
  it('is reachable from the chapters a concept design touches', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    for (const chapter of [w('chapter.guns.label'), w('chapter.propulsion.label'), w('chapter.performance.label')]) {
      fireEvent.click(await screen.findByRole('button', { name: chapter }));
      const entry = within(document.body)
        .getAllByRole('button', { name: /Concept design screen|Machinery|Concept design balance/ })
        .find(node => node.className.includes('text-button'));
      expect(entry).toBeTruthy();
      fireEvent.click(entry!);
      await screen.findByLabelText('weapons.guns Select');
    }
  });

  it('writes the reader’s declaration into the draft and marks it unsaved', async () => {
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={onRun} />);
    fireEvent.click(await screen.findByRole('button', { name: w('chapter.weights.label') }));
    fireEvent.click(await screen.findByLabelText(conceptCopy('en', 'concept.enable')));
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.source.label')),
      { target: { value: 'my declared study design' } });
    expect(screen.getByText(w('workbench.save.dirty'))).toBeVisible();
    expect(screen.getByRole('button', { name: w('workbench.save.action') })).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: w('workbench.save.action') }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const saved = vi.mocked(api.saveProject).mock.calls[0][1].project as Record<string, any>;
    expect(saved.concept_design.source).toBe('my declared study design');
    expect(saved.concept_design.schema).toBe('plimsoll-concept-design-1');
  });
});

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { ConceptComponentReadings } from '../components/ConceptComponentReadings';
import { MassProposalPanel } from '../components/MassProposalPanel';
import { compareReports } from '../components/reportComparison';
import { reportMetrics } from '../components/reportMetrics';
import { UnitProvider } from '../components/UnitProvider';
import {
  BATTERY_ALLOCATION_METHOD, BATTERY_ALLOCATION_POLICY, IDLE_APPLY, allocationLayoutIds,
  batteryMassAllocationEnabled, batteryMassAllocationOf, claimedTargetIds, componentBindings,
  invalidAllocationLayoutIds, newConcept,
} from '../components/conceptDesign';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import { workspaceCopy } from '../i18n/workspace';
import { zhCopy } from './locale';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';
import * as api from '../api';

// The whole-battery mount allocation is one optional declaration of scope, one
// reviewed *cohort* of proposals and one pair of read-only server readings. This
// suite checks that the form never chooses a layout for the reader and keeps an
// unknown selection distinct from an explicit empty one, that a cohort is
// selected and cleared as a whole and never left partial, that selection
// ownership retires synchronously on any identity/dirty/request change, and that
// the readings and their comparison keep the SPS source total, the product
// allocation policy and the selected ledger apart.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);

const SHA = '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc';
const SOURCE_METHOD = 'sps-3b3-battery-totals-v1';

const LEDGER = {
  id: 'weights', label: 'declared concept design',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'weapons.mounts.a', mass_t: 152.407, x_m: 104 },
    { id: 'weapons.mounts.b', mass_t: 80.0, x_m: 104 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts.a', 'weapons.mounts.b'] } },
};

function battery(id: string) {
  return { id, system_id: 'weapons.main', guns_item_id: null, mounts_item_id: null,
    ammunition_item_id: null, calibre_mm: null, mount_count: null };
}

const LAYOUT = {
  id: 'main_layout', source: 'recovered two-group layout',
  group1: { battery_id: 'battery_a' }, group2: { battery_id: 'battery_b' },
};

function declaredConfig(over: Record<string, unknown> = {}): Record<string, unknown> {
  return { ...newConcept(), source: 'a declared study design',
    batteries: [battery('battery_a'), battery('battery_b')],
    battery_layouts: [{ ...LAYOUT }], ...over };
}

function project(over: Record<string, unknown> = {}): ProjectDocument {
  return { schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS,
    concept_design: declaredConfig(over) } as unknown as ProjectDocument;
}

const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;

function mount(initial: ProjectDocument) {
  const written: ProjectDocument[] = [];
  function Harness() {
    const [draft, setDraft] = useState(initial);
    return <UnitProvider preferences={null}>
      <ConceptDesignEditor project={draft}
        onChange={next => { setDraft(next); written.push(next); }} />
    </UnitProvider>;
  }
  render(<Harness />);
  return { document: () => written[written.length - 1] ?? initial };
}

const allocationPanel = () =>
  screen.getByText(copy('concept.group.batteryAllocation')).closest('div.form-card') as HTMLElement;

beforeEach(() => {
  cleanup(); vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => { vi.unstubAllGlobals(); });

// --- the declaration form ----------------------------------------------------

describe('the whole-battery allocation declaration', () => {
  it('is absent until enabled, and enabling writes an unknown selection, not an empty one', () => {
    const { document } = mount(project());
    expect(batteryMassAllocationEnabled(config(document()))).toBe(false);
    expect('battery_mass_allocation' in config(document())).toBe(false);
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.batteryAllocation.use') }));
    const section = config(document()).battery_mass_allocation;
    expect(section).toEqual({ source: null, layout_ids: null });
    // Unknown selection: the layout picker is not even offered, and nothing was
    // chosen for the reader.
    expect(allocationLayoutIds(config(document()))).toBeNull();
    expect(within(allocationPanel())
      .queryByLabelText(`${LAYOUT.id} ${copy('concept.batteryAllocation.layouts')}`)).toBeNull();
  });

  it('keeps an unknown selection distinct from an explicit empty one and never auto-selects', () => {
    const { document } = mount(project());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.batteryAllocation.use') }));
    const scope = screen.getByRole('checkbox', { name: copy('concept.batteryAllocation.scopeKnown') });
    expect(scope).not.toBeChecked();
    fireEvent.click(scope);
    // Explicit, declared empty: distinct from unknown, and no layout is picked.
    expect(allocationLayoutIds(config(document()))).toEqual([]);
    const layoutBox = screen.getByLabelText(`${LAYOUT.id} ${copy('concept.batteryAllocation.layouts')}`);
    expect(layoutBox).not.toBeChecked();
    fireEvent.click(layoutBox);
    expect(allocationLayoutIds(config(document()))).toEqual([LAYOUT.id]);
    fireEvent.click(layoutBox);
    expect(allocationLayoutIds(config(document()))).toEqual([]);
    // Back to unknown: null again, not an empty array.
    fireEvent.click(scope);
    expect(allocationLayoutIds(config(document()))).toBeNull();
  });

  it('names a selected layout that no longer resolves and never clears it silently', () => {
    const initial = project({ battery_mass_allocation: { source: 'x', layout_ids: ['ghost'] } });
    mount(initial);
    expect(invalidAllocationLayoutIds(config(initial))).toEqual(['ghost']);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent(copy('concept.batteryAllocation.invalid'));
    expect(alert).toHaveTextContent('ghost');
    // The dangling reference is still stored exactly as the reader left it.
    expect(allocationLayoutIds(config(initial))).toEqual(['ghost']);
  });

  it('claims no ledger target, so it never enters the component bindings', () => {
    const enabled = { ...newConcept(), battery_mass_allocation: { source: null, layout_ids: [] } };
    const withSection = config(project(enabled as Record<string, unknown>));
    expect(claimedTargetIds(withSection)).toEqual(claimedTargetIds(config(project())));
    expect(componentBindings(withSection)).toEqual(componentBindings(config(project())));
  });

  it('protects a selected layout from deletion and from an identifier repoint', () => {
    const initial = project({ battery_mass_allocation: { source: 'x', layout_ids: [LAYOUT.id] } });
    const { document } = mount(initial);
    // Deletion is refused with a precise reason and the layout is kept.
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.remove') }));
    expect(config(document()).battery_layouts).toHaveLength(1);
    expect(screen.getByRole('alert')).toHaveTextContent(copy('concept.layout.reference.allocated'));
    // The identifier cannot be repointed while it is selected.
    fireEvent.change(screen.getByLabelText(copy('concept.layout.id')), { target: { value: 'renamed' } });
    expect(config(document()).battery_layouts[0].id).toBe(LAYOUT.id);
    expect(screen.getAllByRole('alert').map(node => node.textContent).join(' '))
      .toContain(copy('concept.layout.reference.allocated'));
  });

  it('keeps English and Chinese words for every allocation label it prints', () => {
    const keys: ConceptKey[] = [
      'concept.group.batteryAllocation', 'concept.batteryAllocation.note',
      'concept.batteryAllocation.use', 'concept.batteryAllocation.source',
      'concept.batteryAllocation.sourceHint', 'concept.batteryAllocation.scopeKnown',
      'concept.batteryAllocation.scopeUnknown', 'concept.batteryAllocation.scopeEmptyHint',
      'concept.batteryAllocation.layouts', 'concept.batteryAllocation.noLayouts',
      'concept.batteryAllocation.invalid', 'concept.batteryAllocation.policy',
      'concept.batteryAllocation.separate', 'concept.batteryAllocation.reference',
      'concept.layout.reference.allocated',
      'balance.batteryAllocation.title', 'balance.batteryAllocation.note',
      'balance.batteryAllocation.method', 'balance.batteryAllocation.sourceMethod',
      'balance.batteryAllocation.policy', 'balance.batteryAllocation.declaredSource',
      'balance.batteryAllocation.totals', 'balance.batteryAllocation.sourceTotal',
      'balance.batteryAllocation.legacyTotal', 'balance.batteryAllocation.allocatedTotal',
      'balance.batteryAllocation.selectedTotal', 'balance.batteryAllocation.records',
      'balance.batteryAllocation.member', 'balance.batteryAllocation.target',
      'balance.batteryAllocation.weight', 'balance.batteryAllocation.share',
      'balance.batteryAllocation.allocated', 'balance.batteryAllocation.selected',
      'balance.batteryAllocation.partial', 'balance.batteryAllocation.unavailable',
      'balance.batteryAllocation.diagnostics', 'balance.batteryAllocation.unidentified',
      'proposals.allocation.cohort', 'proposals.allocation.policy', 'proposals.allocation.hint',
    ];
    for (const key of keys) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copy(key), key).not.toBe(key);
      expect(conceptCopy('zh-CN', key).trim(), key).not.toBe('');
      expect(conceptCopy('zh-CN', key), key).not.toBe(copy(key));
    }
    // The source total and the product policy are separate names, not one label.
    expect(copy('balance.batteryAllocation.sourceTotal'))
      .not.toBe(copy('balance.batteryAllocation.allocatedTotal'));
  });
});

// --- the proposal cohort -----------------------------------------------------

function proposal(item: string, component: string, model: string, current: number | null, next: number) {
  return {
    operation: 'replace_weight_item_mass', item_id: item, current_mass_t: current,
    proposed_mass_t: next, difference_t: current === null ? null : next - current,
    source_system_id: 'weapons.main', source_model_id: model, requires_review: true,
    condition_id: 'normal', target: 'selected_condition', project_fingerprint: 'pf',
    input_fingerprint: 'if', request_fingerprint: 'rf',
    model: {
      id: model, method: 'empirical_estimate_v1', concept_component: component,
      source: { declaration: 'a declared study design', sha256: '82ecc3fe' },
      boundary: 'recovered 3b3 formulas, adapted to the explicit ledger',
    },
  } as Record<string, any>;
}

function allocation(item: string, group: string, current: number | null, next: number) {
  const row = proposal(item, 'mounts', 'concept.main.mounts', current, next);
  row.model.inputs = {
    method_version: BATTERY_ALLOCATION_METHOD, allocation_group_id: group,
    allocation_policy: BATTERY_ALLOCATION_POLICY, allocation_target_ids: [item],
  };
  return row;
}

function stage(status: StageEnvelope['status'], data: StageEnvelope['data']): StageEnvelope {
  return { status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data };
}

function runWith(proposals: unknown[]): RunView {
  const result = {
    schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: {}, input_snapshot: {}, units: {}, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    stages: { systems: stage('completed', { update_proposals: proposals }) },
  } as unknown as AnalysisResult;
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'rf', created_at: '', started_at: null, finished_at: null,
    cancel_requested: false, result, error: null } as RunView;
}

function panel(run: RunView | null, over: Partial<Parameters<typeof MassProposalPanel>[0]> = {}) {
  const onApply = vi.fn();
  const view = render(<UnitProvider preferences={null}>
    <MassProposalPanel run={run} identity="a" dirty={false} apply={IDLE_APPLY}
      onApply={onApply} onRerun={vi.fn()} {...over} /></UnitProvider>);
  return { onApply, ...view };
}

const COHORT = 'battery-mounts:main_layout';

describe('the reviewed allocation cohort', () => {
  it('selects every pending member of a cohort and deselects the whole group', () => {
    const run = runWith([
      allocation('weapons.mounts.a', COHORT, 100, 80),
      allocation('weapons.mounts.b', COHORT, 100, 80),
      proposal('weapons.guns', 'guns', 'concept.main.guns', 60, 50),
    ]);
    const { onApply } = panel(run);
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).toBeChecked();
    expect(screen.getByLabelText('weapons.mounts.b Select')).toBeChecked();
    expect(screen.getByLabelText('weapons.guns Select')).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: copy('proposals.apply') }));
    expect(onApply.mock.calls[0][0]).toHaveLength(2);
    // Deselecting any member clears the complete cohort, never a partial one.
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    expect(screen.getByLabelText('weapons.mounts.b Select')).not.toBeChecked();
    expect(screen.getByRole('button', { name: copy('proposals.apply') })).toBeDisabled();
  });

  it('explains the cohort and its product policy beside the estimate', () => {
    panel(runWith([allocation('weapons.mounts.a', COHORT, 100, 80)]));
    expect(screen.getByText(copy('proposals.allocation.cohort', { group: COHORT }))).toBeVisible();
    expect(screen.getByText(copy('proposals.allocation.policy', { policy: BATTERY_ALLOCATION_POLICY })))
      .toBeVisible();
    expect(screen.getByText(copy('proposals.allocation.hint'))).toBeVisible();
  });

  it('clears the whole cohort when a different model is chosen for a colliding target', () => {
    const run = runWith([
      allocation('weapons.mounts.a', COHORT, 100, 80),
      allocation('weapons.mounts.b', COHORT, 100, 80),
      proposal('weapons.mounts.a', 'mounts', 'physical_mounts', 100, 90),
    ]);
    const { onApply } = panel(run);
    const colliding = screen.getAllByLabelText('weapons.mounts.a Select');
    expect(colliding).toHaveLength(2);
    fireEvent.click(colliding[0]); // the allocation member
    expect(screen.getByLabelText('weapons.mounts.b Select')).toBeChecked();
    fireEvent.click(screen.getAllByLabelText('weapons.mounts.a Select')[1]); // the physical alternative
    expect(screen.getByLabelText('weapons.mounts.b Select')).not.toBeChecked();
    expect(screen.getAllByLabelText('weapons.mounts.a Select')[0]).not.toBeChecked();
    expect(screen.getAllByLabelText('weapons.mounts.a Select')[1]).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: copy('proposals.apply') }));
    const applied = onApply.mock.calls[0][0];
    expect(applied).toHaveLength(1);
    expect(applied[0].source_model_id).toBe('physical_mounts');
  });

  it('clears an alternative and retires a conflicting cohort when a cohort is selected across its members', () => {
    const OTHER = 'battery-mounts:second_layout';
    const alt = allocation('weapons.mounts.b', OTHER, 100, 90);
    alt.source_model_id = 'concept.alt.mounts';
    alt.model.id = 'concept.alt.mounts';
    const run = runWith([
      allocation('weapons.mounts.a', COHORT, 100, 80),
      allocation('weapons.mounts.b', COHORT, 100, 80),
      allocation('weapons.mounts.c', OTHER, 100, 80),
      alt,
      proposal('weapons.mounts.b', 'mounts', 'physical_mounts', 100, 95),
    ]);
    const { onApply } = panel(run);
    const b = () => screen.getAllByLabelText('weapons.mounts.b Select');
    expect(b()).toHaveLength(3); // cohort A, cohort B, the physical alternative
    // Select the alternative first — the exact order that used to leave it behind.
    fireEvent.click(b()[2]);
    expect(b()[2]).toBeChecked();
    // Selecting the cohort by one member clears the alternative for the *other*
    // member it covers, and selects the whole cohort.
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(b()[2]).not.toBeChecked();
    expect(b()[0]).toBeChecked();
    expect(b()[1]).not.toBeChecked();
    // A second cohort that shares a member then retires the first in full.
    fireEvent.click(screen.getByLabelText('weapons.mounts.c Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    expect(b()[0]).not.toBeChecked();
    expect(b()[1]).toBeChecked();
    expect(screen.getByLabelText('weapons.mounts.c Select')).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: copy('proposals.apply') }));
    const applied = onApply.mock.calls[0][0];
    expect(applied.map((row: Record<string, unknown>) => row.item_id).sort())
      .toEqual(['weapons.mounts.b', 'weapons.mounts.c']);
    expect(applied.every((row: Record<string, unknown>) =>
      (((row.model as Record<string, unknown>).inputs as Record<string, unknown>)
        .allocation_group_id) === OTHER)).toBe(true);
  });

  it('claims a cohort by its declared targets even when its exact members are not pending', () => {
    // Cohort A is already exact, so it has no pending rows: only the physical
    // alternative for its target `mounts.a` is on screen. Cohort B is pending and
    // declares both `mounts.a` and `mounts.b` as its recomputed targets.
    const B = 'battery-mounts:pending_layout';
    const altA = () => proposal('weapons.mounts.a', 'mounts', 'physical_mounts', 100, 95);
    const bRow = () => {
      const row = allocation('weapons.mounts.b', B, 100, 80);
      (row.model.inputs as Record<string, unknown>).allocation_target_ids =
        ['weapons.mounts.a', 'weapons.mounts.b'];
      return row;
    };
    const run = runWith([altA(), bRow()]);

    // Order 1: choose the physical alternative for mounts.a, then the cohort.
    const first = panel(run);
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).toBeChecked();
    fireEvent.click(screen.getByLabelText('weapons.mounts.b Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: copy('proposals.apply') }));
    expect(first.onApply.mock.calls[0][0].map((row: Record<string, unknown>) => row.item_id))
      .toEqual(['weapons.mounts.b']);

    // Order 2: choose the cohort first, then the physical alternative for its
    // declared but already-exact target. The chosen cohort is retired in full.
    cleanup();
    const second = panel(run);
    fireEvent.click(screen.getByLabelText('weapons.mounts.b Select'));
    expect(screen.getByLabelText('weapons.mounts.b Select')).toBeChecked();
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.b Select')).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: copy('proposals.apply') }));
    expect(second.onApply.mock.calls[0][0].map((row: Record<string, unknown>) => row.item_id))
      .toEqual(['weapons.mounts.a']);
  });

  it('treats an allocation-shaped model without a group id as an ordinary proposal', () => {
    const row = allocation('weapons.mounts.a', '', 100, 80);
    panel(runWith([row]));
    expect(screen.queryByText(copy('proposals.allocation.hint'))).toBeNull();
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.a Select')).toBeChecked();
  });

  it('retires the choice synchronously when the draft becomes dirty or the request changes', () => {
    const run = runWith([allocation('weapons.mounts.a', COHORT, 100, 80),
      allocation('weapons.mounts.b', COHORT, 100, 80)]);
    const { rerender } = render(<UnitProvider preferences={null}>
      <MassProposalPanel run={run} identity="a" dirty={false} apply={IDLE_APPLY}
        onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.b Select')).toBeChecked();
    rerender(<UnitProvider preferences={null}>
      <MassProposalPanel run={run} identity="a" dirty apply={IDLE_APPLY}
        onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
    // The dirty draft hides the batch entirely.
    expect(screen.getByText(copy('proposals.emptyDirty'))).toBeVisible();
    rerender(<UnitProvider preferences={null}>
      <MassProposalPanel run={run} identity="a" dirty={false} requestChanged apply={IDLE_APPLY}
        onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
    expect(screen.getByText(copy('proposals.requestChanged'))).toBeVisible();
    rerender(<UnitProvider preferences={null}>
      <MassProposalPanel run={run} identity="a" dirty={false} apply={IDLE_APPLY}
        onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
    // Coming back to the same clean, current result does not restore the choice.
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    expect(screen.getByLabelText('weapons.mounts.b Select')).not.toBeChecked();
  });

  it('permanently retires the choice across A → B → A rather than masking it', () => {
    const run = runWith([allocation('weapons.mounts.a', COHORT, 100, 80),
      allocation('weapons.mounts.b', COHORT, 100, 80)]);
    const { rerender } = panel(run, { identity: 'a' });
    fireEvent.click(screen.getByLabelText('weapons.mounts.a Select'));
    expect(screen.getByLabelText('weapons.mounts.b Select')).toBeChecked();
    const rerenderIdentity = (identity: string) => rerender(<UnitProvider preferences={null}>
      <MassProposalPanel run={run} identity={identity} dirty={false} apply={IDLE_APPLY}
        onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
    rerenderIdentity('b');
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    rerenderIdentity('a');
    expect(screen.getByLabelText('weapons.mounts.a Select')).not.toBeChecked();
    expect(screen.getByLabelText('weapons.mounts.b Select')).not.toBeChecked();
  });
});

// --- the readings ------------------------------------------------------------

const ALLOCATION = {
  id: 'main_layout', method_version: BATTERY_ALLOCATION_METHOD, status: 'available',
  values: { source_mounts_t: 300.5, legacy_mounts_t: 280.0, allocated_total_t: 300.5,
    selected_mounts_t: 288.25 },
  records: [
    { id: 'battery_a', method_version: BATTERY_ALLOCATION_METHOD, target_id: 'weapons.mounts.a',
      weight_t: 160.0, share: 0.5, allocated_mass_t: 150.25, selected_mass_t: 144.0 },
    { id: 'battery_b', method_version: BATTERY_ALLOCATION_METHOD, target_id: 'weapons.mounts.b',
      weight_t: 160.0, share: 0.5, allocated_mass_t: 150.25, selected_mass_t: 144.25 },
  ],
  diagnostics: [],
  provenance: { source_method_version: SOURCE_METHOD, allocation_policy: BATTERY_ALLOCATION_POLICY,
    declared_source: 'a declared study design', source_sha256: SHA },
};

function readings(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}, policy: 'independent' | 'report' = 'independent') {
  const envelope = { status: 'completed', requested: true, ...over } as StageEnvelope;
  return render(<UnitProvider preferences={null}>
    <ConceptComponentReadings data={data} envelope={envelope} policy={policy} /></UnitProvider>);
}

describe('the whole-battery allocation reading', () => {
  it('prints the SPS source total, the product allocation and the selected ledger apart', () => {
    readings({ battery_mass_allocation: [ALLOCATION] });
    expect(screen.getByText(copy('balance.batteryAllocation.title'))).toBeVisible();
    // The SPS source total and the product's allocated total happen to be equal
    // here; both are printed under their own labels, so the label is what keeps
    // them apart and each appears once.
    expect(screen.getAllByText('300.5 t')).toHaveLength(2);
    expect(screen.getByText(copy('balance.batteryAllocation.sourceTotal'))).toBeVisible();
    expect(screen.getByText(copy('balance.batteryAllocation.allocatedTotal'))).toBeVisible();
    expect(screen.getByText('280 t')).toBeVisible();
    expect(screen.getByText('288.25 t')).toBeVisible();
    // The SPS source method and the product policy are named separately.
    expect(screen.getByText(copy('balance.batteryAllocation.sourceMethod'))).toBeVisible();
    expect(screen.getByText(SOURCE_METHOD)).toBeVisible();
    expect(screen.getByText(BATTERY_ALLOCATION_POLICY)).toBeVisible();
    // Per-battery records keep the battery id, its target, weight, share, and the
    // allocated and selected masses in metric tonnes.
    expect(screen.getByText('battery_a')).toBeVisible();
    expect(screen.getByText('weapons.mounts.a')).toBeVisible();
    // Both members declare the same weight, so the figure appears once per member.
    expect(screen.getAllByText('160 t')).toHaveLength(2);
    expect(screen.getAllByText('0.500').length).toBe(2);
    expect(screen.getAllByText('150.25 t').length).toBe(2);
  });

  it('marks a partial reading as partial rather than refused, keeping the known selected facts', () => {
    readings({ battery_mass_allocation: [{ ...ALLOCATION, status: 'partial',
      values: { ...ALLOCATION.values, source_mounts_t: null, allocated_total_t: null } }] });
    expect(screen.getByText(copy('balance.batteryAllocation.partial', { status: 'partial' })))
      .toBeVisible();
    // The independently selected total is still read.
    expect(screen.getByText('288.25 t')).toBeVisible();
  });

  it('adds no section at all when the feature was never declared, and hides numbers behind the report gate', () => {
    const { rerender } = readings({ other: 1 });
    expect(screen.queryByText(copy('balance.batteryAllocation.title'))).toBeNull();
    rerender(<UnitProvider preferences={null}>
      <ConceptComponentReadings data={{ battery_mass_allocation: [ALLOCATION] }}
        envelope={{ requested: true, status: 'failed' } as StageEnvelope} policy="report" /></UnitProvider>);
    expect(screen.queryByText('300.5 t')).toBeNull();
  });
});

// --- the comparison metrics --------------------------------------------------

function conceptStage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return { ...stage('completed', data),
    method_versions: { methods: { battery_mass_allocation: BATTERY_ALLOCATION_METHOD } }, ...over };
}

function result(stageEnvelope: StageEnvelope): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1',
    condition_id: 'normal', project_fingerprint: 'p', input_fingerprint: 'i', request_fingerprint: 'r',
    request: {}, input_snapshot: {}, units: { mass: 't' }, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: true, converged: null, model_applicable: null,
      historical_validated: null }, stages: { design_balance: stageEnvelope } } as unknown as AnalysisResult;
}

function clone<T>(value: T): T { return structuredClone(value); }

describe('keyed allocation metrics for the comparison', () => {
  it('matches layouts and members by their own stable ids, never by array position', () => {
    const before = conceptStage({ battery_mass_allocation: [ALLOCATION] });
    const reordered = clone({ battery_mass_allocation: [ALLOCATION] }) as Record<string, unknown>;
    (reordered.battery_mass_allocation as any[])[0].records.reverse();
    const after = conceptStage(reordered);
    const ids = (m: ReturnType<typeof reportMetrics>) =>
      m.filter(x => x.id.startsWith('battery_mass_allocation:')).map(x => x.id).sort();
    expect(ids(reportMetrics('design_balance', before)))
      .toEqual(ids(reportMetrics('design_balance', after)));
    const cells = compareReports({ result: result(before) }, { result: result(after) },
      (k, p) => zhCopy(k as never, p)).groups.flatMap(g => g.cells);
    expect(cells.filter(c => c.path.includes('battery_mass_allocation')).every(c => c.delta === 0))
      .toBe(true);
  });

  it('names the masses as tonnes and the share as dimensionless', () => {
    const metrics = reportMetrics('design_balance', conceptStage({ battery_mass_allocation: [ALLOCATION] }));
    expect(metrics.find(m => m.id === 'battery_mass_allocation:main_layout:values.source_mounts_t'))
      .toMatchObject({ key: 'allocation_source_mounts_t', dimension: 'mass', storedUnit: 't', blocked: false });
    expect(metrics.find(m => m.id === 'battery_mass_allocation:main_layout:values.selected_mounts_t'))
      .toMatchObject({ key: 'allocation_selected_mounts_t', dimension: 'mass', blocked: false });
    const member = metrics.find(m => m.id === 'battery_mass_allocation:main_layout:battery_a:weight_t')!;
    expect(member).toMatchObject({ key: 'allocation_weight_t', dimension: 'mass', storedUnit: 't' });
    const share = metrics.find(m => m.id === 'battery_mass_allocation:main_layout:battery_a:share')!;
    expect(share).toMatchObject({ key: 'allocation_share', dimension: undefined, blocked: false });
  });

  it('blocks a repeated, missing, unavailable or method-mismatched layout or member', () => {
    const cases: Array<[string, Record<string, unknown>]> = [
      ['duplicate', { battery_mass_allocation: [ALLOCATION, { ...ALLOCATION }] }],
      ['missing', { battery_mass_allocation: [{ ...ALLOCATION, id: null }] }],
      ['unavailable', { battery_mass_allocation: [{ ...ALLOCATION, status: 'unavailable' }] }],
      ['mismatch', { battery_mass_allocation: [{ ...ALLOCATION, method_version: 'sps-3b3-battery-totals-v2' }] }],
      ['member-mismatch', { battery_mass_allocation: [{ ...ALLOCATION,
        records: [{ ...ALLOCATION.records[0], method_version: 'other' }] }] }],
      ['member-duplicate', { battery_mass_allocation: [{ ...ALLOCATION,
        records: [ALLOCATION.records[0], { ...ALLOCATION.records[0] }] }] }],
    ];
    for (const [name, patch] of cases) {
      const metrics = reportMetrics('design_balance', conceptStage(patch));
      expect(metrics.filter(m => m.id.startsWith('battery_mass_allocation:')).every(m => m.blocked), name)
        .toBe(true);
    }
  });

  it('shows a delta when both parents completed and the family method matches', () => {
    const before = conceptStage({ battery_mass_allocation: [ALLOCATION] });
    const changed = clone({ battery_mass_allocation: [ALLOCATION] }) as Record<string, unknown>;
    (changed.battery_mass_allocation as any[])[0].values.selected_mounts_t = 290.25;
    const after = conceptStage(changed);
    const cells = compareReports({ result: result(before) }, { result: result(after) },
      (k, p) => zhCopy(k as never, p)).groups.flatMap(g => g.cells);
    const selected = cells.find(c => c.path.endsWith('values.selected_mounts_t'))!;
    expect(selected).toMatchObject({ state: 'known', dimension: 'mass', delta: 2 });
  });

  it('names every new allocation metric in both languages', () => {
    for (const key of ['allocation_source_mounts_t', 'allocation_legacy_mounts_t',
      'allocation_allocated_total_t', 'allocation_selected_mounts_t', 'allocation_weight_t',
      'allocation_share', 'allocation_allocated_mass_t', 'allocation_selected_mass_t']) {
      const english = workspaceCopy('en', `data.${key}` as never);
      const chinese = zhCopy(`data.${key}` as never);
      expect(english, key).not.toBe(`data.${key}`);
      expect(chinese, key).not.toBe(english);
    }
  });
});

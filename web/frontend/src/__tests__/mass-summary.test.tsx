import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { DesignBalanceResults } from '../components/DesignBalanceResults';
import { StageStatus } from '../components/StageStatus';
import { compareReports } from '../components/reportComparison';
import { reportMetrics } from '../components/reportMetrics';
import { UnitProvider } from '../components/UnitProvider';
import {
  armourTotalReading, batteryTotalReadings, claimedTargetIds, componentBindings, massSummaryEnabled,
  massSummaryOf, newConcept, newMassSummary, patchMassSummary, removeMassSummary,
} from '../components/conceptDesign';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import { workspaceCopy } from '../i18n/workspace';
import { zhCopy } from './locale';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';
import * as api from '../api';

// The optional whole-battery and armour mass summary is a *scope declaration* and
// a pair of read-only server readings. This suite checks that the form writes one
// source and one complete-scope flag and nothing else, that the readings keep the
// declared estimate and the current condition apart (a partial reading is never a
// total, an absent feature adds no section), and that the comparison matches on
// stable ids and double method identity and never by array position.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);
const copyZh = (key: ConceptKey) => conceptCopy('zh-CN', key);
const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;

const SHA = '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc';
const BATTERY_METHOD = 'sps-3b3-battery-totals-v1';
const ARMOUR_METHOD = 'sps-3b3-armour-totals-v1';

// --- the payload the server returns -----------------------------------------

const LAYOUT_A = {
  id: 'main_layout', method_version: BATTERY_METHOD, status: 'available',
  values: { guns_t: 120.5, mounts_t: 80.25, armour_t: 300.0, total_t: 500.75 },
  selected_values: { guns_t: 118.0, mounts_t: 79.5, armour_t: 290.0, total_t: 487.5 },
  diagnostics: [],
  provenance: { method_version: BATTERY_METHOD, source_sha256: SHA },
};

const LAYOUT_B = {
  id: 'secondary_layout', method_version: BATTERY_METHOD, status: 'available',
  values: { guns_t: 60.0, mounts_t: 40.0, armour_t: 150.0, total_t: 250.0 },
  selected_values: { guns_t: 59.0, mounts_t: 39.5, armour_t: 148.0, total_t: 246.5 },
  diagnostics: [],
  provenance: { method_version: BATTERY_METHOD, source_sha256: SHA },
};

const BATTERY_TOTALS = [LAYOUT_A, LAYOUT_B];

const ARMOUR_TOTALS = {
  id: 'ship_armour', method_version: ARMOUR_METHOD, status: 'available',
  values: { estimated_belts_t: 210.0, estimated_total_t: null, known_estimate_subtotal_t: 480.25,
    selected_belts_t: 205.0, selected_total_t: 630.0 },
  coverage: { uncovered_component_ids: ['fixed:deck'] },
  diagnostics: [],
  provenance: { method_version: ARMOUR_METHOD, source_sha256: SHA,
    inputs: { declared_complete: false } },
};

const BASE = {
  schema: 'plimsoll-concept-balance-1', status: 'completed',
  method_version: 'sps-3b3-adapted-v1', method_scope: 'recovered 3b3',
  values: { selected_total_mass_t: 6963.78 }, structure: {}, strength: {}, space: {},
  stability: {}, seakeeping: {}, crew: {}, hull_proxy: {}, power: {}, design_warnings: [],
};

const DATA = { ...BASE, battery_totals: BATTERY_TOTALS, armour_totals: ARMOUR_TOTALS };

// --- the stage and result envelopes -----------------------------------------

function stage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return { status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
    method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1' },
    validity: { complete: true, converged: null, model_applicable: null, historical_validated: null },
    data, ...over };
}

/** The stage with the declared family methods the core copies into `method_versions`. */
function conceptStage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return stage(data, { method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1',
    methods: { battery_totals: BATTERY_METHOD, armour_totals: ARMOUR_METHOD,
      fixed_armour: 'sps-3b3-fixed-armour-v1', layout: 'sps-3b3-battery-layout-v1',
      cost: 'sps-3b3-cost-v1' } }, ...over });
}

function result(stages: Record<string, StageEnvelope>, over: Partial<AnalysisResult> = {}): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1',
    condition_id: 'normal', project_fingerprint: 'p', input_fingerprint: 'i',
    request_fingerprint: 'r', request: {}, input_snapshot: {} as never,
    units: { mass: 't' }, method_versions: { coordinator: 'analysis-1' }, sources: {},
    diagnostics: [], validity: { complete: true, converged: null, model_applicable: null,
      historical_validated: null }, stages, ...over } as unknown as AnalysisResult;
}

/** The saved full report renders the readings under the strict requested-and-completed gate. */
function report(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}, preferences: unknown = null) {
  render(<UnitProvider preferences={preferences}>
    <StageStatus name="design_balance" stage={conceptStage(data, over)} />
  </UnitProvider>);
}

function clone<T>(value: T): T { return structuredClone(value); }

/** The innermost reading section whose own `<h5>` names the id. */
const readingSection = (id: string): HTMLElement =>
  [...document.querySelectorAll('section.concept-balance-group')]
    .filter(node => node.querySelector('h5')?.textContent === id).at(-1) as HTMLElement;

// --- the edited project, for the form ---------------------------------------

const LEDGER = {
  id: 'weights', label: 'declared concept design',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns'] } },
  propulsion: { machinery: { weight_item_ids: ['propulsion.machinery'] },
    fuel: { weight_item_ids: ['propulsion.fuel'] } },
};

function enabledProject(): ProjectDocument {
  const declared = newConcept();
  declared.source = 'a declared study design';
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS, concept_design: declared,
  } as unknown as ProjectDocument;
}

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

const panel = () =>
  screen.getByText(copy('concept.group.massSummary')).closest('div.form-card') as HTMLElement;

beforeEach(() => { cleanup(); vi.clearAllMocks(); vi.mocked(api.listProjects).mockResolvedValue([]); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the mass-summary section is a scope declaration, not a mass', () => {
  it('is absent from a project that never enabled it, so an old project is untouched', () => {
    const { document } = mount(enabledProject());
    expect(massSummaryEnabled(config(document()))).toBe(false);
    expect('mass_summary' in config(document())).toBe(false);
    expect(within(panel()).getByRole('checkbox', { name: copy('concept.massSummary.use') }))
      .not.toBeChecked();
    // Nothing to type into while it is off: the whole section is the switch.
    expect(within(panel()).queryByLabelText(copy('concept.massSummary.source'))).toBeNull();
    expect(within(panel()).queryByLabelText(copy('concept.massSummary.complete'))).toBeNull();
  });

  it('writes one source and one complete-scope flag when turned on, both null until they are set', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.massSummary.use') }));
    expect(config(document()).mass_summary).toEqual({ source: null, armour_scope_complete: null });
    expect(massSummaryEnabled(config(document()))).toBe(true);
    // An empty source is unknown, not an empty claim of a source.
    fireEvent.change(screen.getByLabelText(copy('concept.massSummary.source')),
      { target: { value: 'the recovered gun outfit table' } });
    expect(config(document()).mass_summary.source).toBe('the recovered gun outfit table');
    expect(config(document()).mass_summary.armour_scope_complete).toBeNull();
    fireEvent.change(screen.getByLabelText(copy('concept.massSummary.source')), { target: { value: '' } });
    expect(config(document()).mass_summary.source).toBeNull();
  });

  it('treats a null or unchecked flag as not complete, and only an explicit true completes', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.massSummary.use') }));
    expect(massSummaryOf(config(document()))!.armour_scope_complete).toBeNull();
    fireEvent.click(screen.getByLabelText(copy('concept.massSummary.complete')));
    expect(config(document()).mass_summary.armour_scope_complete).toBe(true);
    // Unchecking writes an explicit false, which is still not a claim of completeness.
    fireEvent.click(screen.getByLabelText(copy('concept.massSummary.complete')));
    expect(config(document()).mass_summary.armour_scope_complete).toBe(false);
  });

  it('turns off by removing only the declaration', () => {
    const project = enabledProject();
    const declared = { ...config(project), mass_summary: { source: 'x', armour_scope_complete: true } };
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const before = document();
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.massSummary.use') }));
    expect(config(document()).mass_summary).toBeNull();
    expect(config(document()).batteries).toEqual(config(before).batteries);
    expect(config(document()).balance).toEqual(config(before).balance);
    // Disabling again is idempotent and writes the same shape.
    expect(removeMassSummary(removeMassSummary(config(document()))).mass_summary).toBeNull();
    expect(patchMassSummary({ mass_summary: null }, { source: 'x' }))
      .toMatchObject({ mass_summary: { source: 'x', armour_scope_complete: null } });
    expect(newMassSummary()).toEqual({ source: null, armour_scope_complete: null });
  });

  it('claims no ledger target, so it can never enter the component bindings', () => {
    const project = enabledProject();
    const before = claimedTargetIds(config(project));
    const declared = { ...config(project), mass_summary: newMassSummary() };
    expect(claimedTargetIds(declared)).toEqual(before);
    expect(componentBindings(declared)).toEqual(componentBindings(config(project)));
    expect(JSON.stringify(componentBindings(declared))).not.toMatch(/mass_summary/);
  });

  it('offers no mass adoption at all: the section is only a switch, a source and a flag', () => {
    mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.massSummary.use') }));
    // Nothing on this card proposes or adopts a mass — the readings live elsewhere.
    expect(within(panel()).queryByRole('button')).toBeNull();
    const card = panel();
    expect(card.textContent).toContain(copy('concept.massSummary.separate'));
    expect(card.textContent).toContain(copy('concept.massSummary.completeHint'));
  });

  it('keeps English and Chinese words for every label the section prints', () => {
    for (const key of ['concept.group.massSummary', 'concept.massSummary.note',
      'concept.massSummary.use', 'concept.massSummary.source', 'concept.massSummary.sourceHint',
      'concept.massSummary.complete', 'concept.massSummary.completeHint',
      'concept.massSummary.separate',
      'balance.batteryTotals.title', 'balance.batteryTotals.note', 'balance.batteryTotals.method',
      'balance.batteryTotals.estimated', 'balance.batteryTotals.selected',
      'balance.batteryTotals.metric.guns', 'balance.batteryTotals.metric.mounts',
      'balance.batteryTotals.metric.armour', 'balance.batteryTotals.metric.total',
      'balance.batteryTotals.ammunition', 'balance.batteryTotals.unavailable',
      'balance.batteryTotals.diagnostics', 'balance.batteryTotals.unidentified',
      'balance.armourTotals.title', 'balance.armourTotals.note', 'balance.armourTotals.method',
      'balance.armourTotals.declared', 'balance.armourTotals.selected',
      'balance.armourTotals.metric.estimatedBelts', 'balance.armourTotals.metric.estimatedTotal',
      'balance.armourTotals.metric.knownSubtotal', 'balance.armourTotals.metric.selectedBelts',
      'balance.armourTotals.metric.selectedTotal', 'balance.armourTotals.scopeComplete',
      'balance.armourTotals.complete', 'balance.armourTotals.fullUnavailable',
      'balance.armourTotals.incomplete', 'balance.armourTotals.uncovered',
      'balance.armourTotals.unavailable', 'balance.armourTotals.diagnostics'] as ConceptKey[]) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });
});

describe('the whole-battery reading keeps the estimate and the selected ledger apart', () => {
  it('prints one row per declared layout, with the declared estimate beside the selected ledger', () => {
    report(DATA);
    expect(screen.getByText(copy('balance.batteryTotals.title'))).toBeVisible();
    const main = readingSection('main_layout');
    // The two columns share the same four metric names, on purpose: the labels say
    // which column each number is, and the two sets are never added together.
    expect(within(main).getAllByText(copy('balance.batteryTotals.metric.total'))).toHaveLength(2);
    expect(within(main).getByText(copy('balance.batteryTotals.estimated'))).toBeVisible();
    expect(within(main).getByText(copy('balance.batteryTotals.selected'))).toBeVisible();
    // Declared estimate (metric tonnes, the reader's canonical mass unit).
    expect(within(main).getByText('120.5 t')).toBeVisible();
    expect(within(main).getByText('80.25 t')).toBeVisible();
    expect(within(main).getByText('300 t')).toBeVisible();
    expect(within(main).getByText('500.75 t')).toBeVisible();
    // Current condition: the selected ledger, a different set of numbers.
    expect(within(main).getByText('118 t')).toBeVisible();
    expect(within(main).getByText('79.5 t')).toBeVisible();
    expect(within(main).getByText('290 t')).toBeVisible();
    expect(within(main).getByText('487.5 t')).toBeVisible();
    // No summed column anywhere: 500.75 and 487.5 are never added.
    expect(within(main).queryByText('988.25 t')).toBeNull();
  });

  it('states that the source total excludes ammunition', () => {
    report(DATA);
    // The note sits beside each layout's declared estimate, so it is repeated per
    // declared layout rather than said once for the whole family.
    expect(screen.getAllByText(copy('balance.batteryTotals.ammunition')).length).toBe(2);
    expect(within(readingSection('main_layout')).getByText(copy('balance.batteryTotals.ammunition')))
      .toBeVisible();
    expect(copy('balance.batteryTotals.ammunition')).toMatch(/ammunition/i);
  });

  it('follows the reader’s mass preference without touching the canonical value', () => {
    report(DATA, {}, { mass: 'kg' });
    // 500.75 t is shown in kilograms once the reader prefers them.
    expect(screen.getByText('500,750 kg')).toBeVisible();
    expect(screen.queryByText('500.75 t')).toBeNull();
  });

  it('shows an unavailable record as unknown with the server’s own reasons', () => {
    report({ ...DATA, battery_totals: [{ ...LAYOUT_A, status: 'unavailable',
      values: { guns_t: null, mounts_t: null, armour_t: null, total_t: null },
      selected_values: { guns_t: null, mounts_t: null, armour_t: null, total_t: null },
      diagnostics: [{ code: 'battery_totals.unknown_armour', severity: 'warning', blocking: false,
        path: '$.concept_design.battery_layouts',
        message: 'the current layout armour is unknown, so the whole-battery total is unknown while the gun and mount masses stay readable' }],
    }] });
    const main = readingSection('main_layout');
    expect(within(main).getAllByText(copy('proposals.unknownMass')).length).toBeGreaterThan(0);
    expect(within(main).getByText(copy('balance.batteryTotals.unavailable', { status: 'unavailable' })))
      .toBeVisible();
    expect(within(main).getByText(copy('balance.batteryTotals.diagnostics'))).toBeVisible();
    expect(document.body.textContent).toContain('the gun and mount masses stay readable');
    // No plausible zero total anywhere in the panel.
    expect(within(main).queryByText('0 t')).toBeNull();
  });

  it('says when a layout carries no identifier, so its reading cannot be matched', () => {
    report({ ...DATA, battery_totals: [{ ...LAYOUT_A, id: '' }] });
    expect(screen.getByText(copy('balance.batteryTotals.unidentified'))).toBeVisible();
    expect(screen.queryByText('main_layout')).toBeNull();
  });

  it('adds no section at all when the feature was never declared', () => {
    report(BASE);
    expect(screen.queryByText(copy('balance.batteryTotals.title'))).toBeNull();
    expect(screen.queryByText(copy('balance.batteryTotals.note'))).toBeNull();
    expect(screen.getByText(copy('balance.title'))).toBeVisible();
    const run = { result: { stages: { design_balance: conceptStage(BASE) } } } as unknown as RunView;
    expect(batteryTotalReadings(run)).toEqual([]);
    expect(armourTotalReading(run)).toBeNull();
  });

  it('stays readable in the workbench while the parent stage is only partial', () => {
    const run = { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal',
      status: 'partial', request_fingerprint: 'r', created_at: '', started_at: null,
      finished_at: null, cancel_requested: false, error: null,
      result: result({ design_balance: conceptStage(DATA, { status: 'partial' as StageEnvelope['status'] }) }),
    } as unknown as RunView;
    render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={run} available />
    </UnitProvider>);
    // The independent workbench policy exposes the reading before the early returns.
    expect(screen.getByText(copy('balance.batteryTotals.title'))).toBeVisible();
    expect(within(readingSection('main_layout')).getByText('500.75 t')).toBeVisible();
    // The saved full report keeps the stricter requested-and-completed gate.
    cleanup();
    report(DATA, { status: 'partial' as StageEnvelope['status'] });
    expect(screen.queryByText(copy('balance.batteryTotals.title'))).toBeNull();
  });
});

describe('the armour-totals reading separates belts, the complete total and the known subtotal', () => {
  const armour = () => screen.getByText(copy('balance.armourTotals.title'))
    .closest('section') as HTMLElement;

  it('prints the three belts, the complete total and the selected actual', () => {
    report(DATA);
    expect(screen.getByText(copy('balance.armourTotals.title'))).toBeVisible();
    expect(within(armour()).getByText('210 t')).toBeVisible();
    expect(within(armour()).getByText('480.25 t')).toBeVisible();
    expect(within(armour()).getByText('205 t')).toBeVisible();
    expect(within(armour()).getByText('630 t')).toBeVisible();
  });

  it('keeps an unconfirmed complete total unknown and calls only the subtotal the subtotal', () => {
    report(DATA);
    // The complete-scope flag is false, so the estimated total is null and only the
    // known subtotal is reported; the panel says a partial reading is not a total.
    expect(within(armour()).getByText(copy('balance.armourTotals.incomplete'))).toBeVisible();
    expect(within(armour()).getByText(copy('balance.armourTotals.metric.knownSubtotal')))
      .toBeVisible();
    // Comment: the unknown estimated total is one of the unknowns in the card.
    expect(within(armour()).getAllByText(copy('proposals.unknownMass')).length).toBe(1);
  });

  it('names the components that have no derived mass', () => {
    report(DATA);
    expect(within(armour()).getByText(copy('balance.armourTotals.uncovered', { ids: 'fixed:deck' })))
      .toBeVisible();
  });

  it('calls the estimated total complete only when the scope is confirmed complete', () => {
    report({ ...DATA, armour_totals: { ...ARMOUR_TOTALS,
      values: { ...ARMOUR_TOTALS.values, estimated_total_t: 640.5 },
      provenance: { ...ARMOUR_TOTALS.provenance, inputs: { declared_complete: true } } } });
    expect(within(armour()).getByText(copy('balance.armourTotals.scopeComplete'))).toBeVisible();
    expect(within(armour()).getByText(copy('balance.armourTotals.complete'))).toBeVisible();
    expect(within(armour()).getByText('640.5 t')).toBeVisible();
  });

  it('confirms the scope without claiming a full total the server did not return', () => {
    // The scope is confirmed, but a declared component has no derived mass, so the
    // server returns no full estimated total. The confirmed range is stated, the
    // known subtotal is reported, and the full total is named unavailable — never
    // asserted to exist because a flag was set.
    report({ ...DATA, armour_totals: { ...ARMOUR_TOTALS,
      values: { estimated_belts_t: 210.0, estimated_total_t: null, known_estimate_subtotal_t: 480.25,
        selected_belts_t: 205.0, selected_total_t: 630.0 },
      coverage: { uncovered_component_ids: ['fixed:deck'] },
      provenance: { ...ARMOUR_TOTALS.provenance, inputs: { declared_complete: true } } } });
    const card = armour();
    // The confirmed range is stated as a scope fact, accurate whatever is missing.
    expect(within(card).getByText(copy('balance.armourTotals.scopeComplete'))).toBeVisible();
    // The full estimate is named unavailable, and the known subtotal is reported.
    expect(within(card).getByText(copy('balance.armourTotals.fullUnavailable'))).toBeVisible();
    expect(within(card).getByText('480.25 t')).toBeVisible();
    expect(within(card).getByText(copy('balance.armourTotals.uncovered', { ids: 'fixed:deck' })))
      .toBeVisible();
    // The full total reads as unknown, and nothing claims it is complete.
    expect(within(card).getAllByText(copy('proposals.unknownMass'))).toHaveLength(1);
    expect(within(card).queryByText(copy('balance.armourTotals.complete'))).toBeNull();
    expect(within(card).queryByText('640.5 t')).toBeNull();
  });

  it('shows an unavailable armour reading as unknown with the server’s reasons', () => {
    report({ ...DATA, armour_totals: { ...ARMOUR_TOTALS, status: 'unavailable',
      values: { estimated_belts_t: null, estimated_total_t: null, known_estimate_subtotal_t: null,
        selected_belts_t: null, selected_total_t: null },
      diagnostics: [{ code: 'armour_totals.unknown_role', severity: 'warning', blocking: false,
        path: '$.concept_design.mass_summary',
        message: 'a required armour role is unknown, so no complete armour total is reported' }] } });
    expect(within(armour()).getByText(copy('balance.armourTotals.unavailable', { status: 'unavailable' })))
      .toBeVisible();
    expect(within(armour()).getByText(copy('balance.armourTotals.diagnostics'))).toBeVisible();
    expect(document.body.textContent).toContain('no complete armour total is reported');
  });

  it('adds no armour section when the feature was never declared', () => {
    report(BASE);
    expect(screen.queryByText(copy('balance.armourTotals.title'))).toBeNull();
  });
});

describe('keyed mass-summary metrics for the comparison', () => {
  it('matches battery rows by their own stable id, never by array position', () => {
    const before = conceptStage(DATA);
    const reordered = clone(DATA) as Record<string, unknown>;
    reordered.battery_totals = [LAYOUT_B, LAYOUT_A];
    const after = conceptStage(reordered);
    const ids = (m: ReturnType<typeof reportMetrics>) =>
      m.filter(x => x.id.startsWith('battery_totals:')).map(x => x.id).sort();
    expect(ids(reportMetrics('design_balance', before)))
      .toEqual(ids(reportMetrics('design_balance', after)));
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    // The reordered declaration has no difference to attribute to any layout.
    expect(cells.filter(c => c.path.includes('battery_totals')).every(c => c.delta === 0)).toBe(true);
  });

  it('keeps the declared estimate and the selected ledger as distinct metric ids', () => {
    const metrics = reportMetrics('design_balance', conceptStage(DATA));
    const ids = metrics.map(m => m.id);
    expect(ids).toContain('battery_totals:main_layout:values.total_t');
    expect(ids).toContain('battery_totals:main_layout:selected_values.total_t');
    // Same canonical mass unit and dimension on both sides of the reader's reading.
    expect(metrics.find(m => m.id === 'battery_totals:main_layout:values.total_t'))
      .toMatchObject({ key: 'total_t', dimension: 'mass', storedUnit: 't', blocked: false });
    expect(metrics.find(m => m.id === 'battery_totals:main_layout:selected_values.total_t'))
      .toMatchObject({ key: 'selected_total_t', dimension: 'mass', storedUnit: 't', blocked: false });
  });

  it('blocks a repeated, missing, unavailable or method-mismatched record', () => {
    const cases: Array<[string, Record<string, unknown>]> = [
      ['duplicate', { battery_totals: [LAYOUT_A, { ...LAYOUT_A, values: { ...LAYOUT_A.values } }] }],
      ['missing', { battery_totals: [{ ...LAYOUT_A, id: null }] }],
      ['unavailable', { battery_totals: [{ ...LAYOUT_A, status: 'unavailable' }] }],
      ['mismatch', { battery_totals: [{ ...LAYOUT_A, method_version: 'sps-3b3-battery-totals-v2' }] }],
    ];
    for (const [name, patch] of cases) {
      const metrics = reportMetrics('design_balance', conceptStage({ ...DATA, ...patch }));
      expect(metrics.filter(m => m.id.startsWith('battery_totals:')).every(m => m.blocked), name)
        .toBe(true);
    }
    // The armour-totals record keeps the same rule against its own family version.
    for (const [name, patch] of [
      ['unavailable', { status: 'unavailable' }],
      ['mismatch', { method_version: 'sps-3b3-armour-totals-v2' }],
      ['missing', { id: null }],
    ] as Array<[string, Record<string, unknown>]>) {
      const metrics = reportMetrics('design_balance',
        conceptStage({ ...DATA, armour_totals: { ...ARMOUR_TOTALS, ...patch } }));
      expect(metrics.filter(m => m.id.startsWith('armour_totals:')).every(m => m.blocked), name)
        .toBe(true);
    }
  });

  it('keeps a partial record’s known figures and lets only its nulls stay unknown', () => {
    const partial = { ...LAYOUT_A, status: 'partial',
      values: { ...LAYOUT_A.values, total_t: null } };
    const metrics = reportMetrics('design_balance', conceptStage({ ...DATA, battery_totals: [partial] }));
    const guns = metrics.find(m => m.id === 'battery_totals:main_layout:values.guns_t')!;
    const total = metrics.find(m => m.id === 'battery_totals:main_layout:values.total_t')!;
    // A partial reading is not a refused one: its known figures stay readable.
    expect(guns).toMatchObject({ value: 120.5, blocked: false });
    expect(total).toMatchObject({ value: null, blocked: false });
  });

  it('shows a delta when both parents completed and the saved family methods match', () => {
    const before = conceptStage(DATA);
    const changed = clone(DATA) as Record<string, unknown>;
    changed.battery_totals = [{ ...LAYOUT_A,
      values: { ...LAYOUT_A.values, total_t: 520.5 },
      selected_values: { ...LAYOUT_A.selected_values, total_t: 495.0 } }, LAYOUT_B];
    changed.armour_totals = { ...ARMOUR_TOTALS,
      values: { ...ARMOUR_TOTALS.values, selected_total_t: 641.0 } };
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: conceptStage(changed) }) },
      (k, p) => zhCopy(k as never, p)).groups.flatMap(g => g.cells);
    const estimate = cells.find(c => c.path.includes('main_layout')
      && c.path.endsWith('values.total_t'))!;
    expect(estimate).toMatchObject({ state: 'known', dimension: 'mass', delta: 19.75 });
    const selected = cells.find(c => c.path.includes('main_layout')
      && c.path.endsWith('selected_values.total_t'))!;
    expect(selected).toMatchObject({ state: 'known', delta: 7.5 });
    const armour = cells.find(c => c.path.endsWith('values.selected_total_t'))!;
    expect(armour).toMatchObject({ state: 'known', delta: 11.0 });
  });

  it('withholds the delta when a family method changed between the two runs', () => {
    const before = conceptStage(DATA);
    const after = conceptStage(clone(DATA) as Record<string, unknown>, {
      method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1',
        methods: { battery_totals: 'sps-3b3-battery-totals-v2', armour_totals: ARMOUR_METHOD,
          fixed_armour: 'sps-3b3-fixed-armour-v1', layout: 'sps-3b3-battery-layout-v1',
          cost: 'sps-3b3-cost-v1' } },
    });
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    expect(cells.filter(c => c.path.includes('battery_totals')).every(c => c.delta === null))
      .toBe(true);
  });

  it('withholds the delta when the parent stage did not run on one side', () => {
    const before = conceptStage(DATA);
    const after = conceptStage(DATA, { requested: false, status: 'not_requested' as StageEnvelope['status'] });
    const comparison = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p));
    const cells = comparison.groups.flatMap(g => g.cells);
    expect(cells.filter(c => c.path.includes('battery_totals')).every(c => c.state === 'unrequested'))
      .toBe(true);
    expect(cells.every(c => c.delta === null)).toBe(true);
  });

  it('names every new mass-summary metric in both languages', () => {
    const keys = ['guns_t', 'mounts_t', 'armour_t', 'total_t', 'selected_guns_t',
      'selected_mounts_t', 'selected_armour_t', 'selected_total_t', 'armour_estimated_belts_t',
      'armour_estimated_total_t', 'armour_known_estimate_subtotal_t', 'armour_selected_belts_t',
      'armour_selected_total_t'];
    for (const key of keys) {
      const english = workspaceCopy('en', `data.${key}` as never);
      const chinese = zhCopy(`data.${key}` as never);
      expect(english, key).not.toBe(`data.${key}`);
      expect(english.trim(), key).not.toBe('');
      expect(chinese.trim(), key).not.toBe('');
      expect(chinese, key).not.toBe(english);
    }
    // Two families both carry a selected total: the label keys must stay distinct.
    expect(workspaceCopy('en', 'data.selected_total_t' as never))
      .not.toBe(workspaceCopy('en', 'data.armour_selected_total_t' as never));
  });
});

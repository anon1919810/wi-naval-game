import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptComponentReadings, componentReadings, readingsAllowed }
  from '../components/ConceptComponentReadings';
import { ConceptReviewGuide } from '../components/ConceptReviewGuide';
import { DesignBalanceResults } from '../components/DesignBalanceResults';
import { StageStatus } from '../components/StageStatus';
import { compareReports } from '../components/reportComparison';
import { reportMetrics } from '../components/reportMetrics';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import { workspaceCopy } from '../i18n/workspace';
import { zhCopy } from './locale';
import type { AnalysisResult, RunView, StageEnvelope } from '../types';
import * as api from '../api';

// The concept screen's optional component readings must be readable in the saved
// full report and comparable between two runs without ever relaxing the parent
// stage's own gate. This suite checks that gate, the shared projection, the keyed
// metric identity, and the method/version conditions that withhold a delta.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);

const SHA = '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc';

function stage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return { status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
    method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1' },
    validity: { complete: true, converged: null, model_applicable: null, historical_validated: null },
    data, ...over };
}

const FIXED_ARMOUR = [
  { id: 'main_belt', kind: 'belt_main', method_version: 'sps-3b3-fixed-armour-v1',
    status: 'available', values: { total_long_tons: 412.5, mass_t: 419.02,
      plate_long_tons: 412.5 }, diagnostics: [],
    provenance: { method_version: 'sps-3b3-fixed-armour-v1', source_sha256: SHA } },
  { id: 'deck', kind: 'deck', method_version: 'sps-3b3-fixed-armour-v1',
    status: 'available', values: { total_long_tons: 88.25, mass_t: 89.68,
      central_long_tons: 60.0, fore_long_tons: 20.0, quarter_long_tons: 8.25 },
    diagnostics: [], provenance: { method_version: 'sps-3b3-fixed-armour-v1', source_sha256: SHA } },
];

const LAYOUTS = [{
  id: 'main_layout', method_version: 'sps-3b3-battery-layout-v1', status: 'available',
  freeboard_m: 5.0, super_factor: 1.08, mounts: 6, barrels: 12, groups: {}, diagnostics: [],
  provenance: { source_sha256: SHA },
}];

const COST = {
  method_version: 'sps-3b3-cost-v1', status: 'available',
  values: { usd_million: 4.812, gbp_million: 1.203, load_long_tons: 1919.2,
    light_basis_long_tons: 4969.4, year_factor: 1.1068 },
  diagnostics: [], provenance: { source_sha256: SHA },
};

/** The stage with the declared methods the core copies into `method_versions`. */
function conceptStage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return stage(data, { method_versions: { coordinator: 'analysis-1',
    kernel: 'sps-3b3-adapted-v1',
    methods: { fixed_armour: 'sps-3b3-fixed-armour-v1', cost: 'sps-3b3-cost-v1',
      layout: 'sps-3b3-battery-layout-v1' } }, ...over });
}

const DATA = { schema: 'plimsoll-concept-balance-1', status: 'completed',
  method_version: 'sps-3b3-adapted-v1', method_scope: 'recovered 3b3',
  values: { selected_total_mass_t: 6963.78 }, structure: {}, strength: {}, space: {},
  stability: {}, seakeeping: {}, crew: {}, hull_proxy: {}, power: {}, design_warnings: [],
  fixed_armour: FIXED_ARMOUR, battery_layouts: LAYOUTS, cost: COST };

function report(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}) {
  render(<UnitProvider preferences={null}>
    <StageStatus name="design_balance" stage={conceptStage(data, over)} />
  </UnitProvider>);
}

function result(stages: Record<string, StageEnvelope>, over: Partial<AnalysisResult> = {}): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1',
    condition_id: 'normal', project_fingerprint: 'p', input_fingerprint: 'i',
    request_fingerprint: 'r', request: {}, input_snapshot: {} as never,
    units: { mass: 't' }, method_versions: { coordinator: 'analysis-1' }, sources: {},
    diagnostics: [], validity: { complete: true, converged: null, model_applicable: null,
      historical_validated: null }, stages, ...over } as unknown as AnalysisResult;
}

function clone<T>(value: T): T { return structuredClone(value); }

beforeEach(() => { cleanup(); vi.clearAllMocks(); vi.mocked(api.listProjects).mockResolvedValue([]); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the full report gate on the concept readings', () => {
  it('shows the component readings of a requested, completed envelope', () => {
    report(DATA);
    expect(screen.getByText(copy('balance.fixedArmour.title'))).toBeVisible();
    expect(screen.getByText(copy('balance.layout.title'))).toBeVisible();
    expect(screen.getByText(copy('balance.cost.title'))).toBeVisible();
    // The belt's own total and its single-plate contribution are two named
    // readings of the same recovered figure, not one number printed twice.
    expect(screen.getAllByText('412.500 long tons')).toHaveLength(2);
    expect(screen.getByText('4.812 million USD')).toBeVisible();
  });

  it.each(['unavailable', 'failed', 'canceled', 'model_limit', 'not_requested'] as const)
    ('withholds every number from a %s envelope while keeping its evidence', status => {
      report(DATA, { status });
      expect(screen.queryByText(copy('balance.fixedArmour.title'))).toBeNull();
      expect(screen.queryByText(copy('balance.layout.title'))).toBeNull();
      expect(screen.queryByText(copy('balance.cost.title'))).toBeNull();
      expect(screen.queryByText('412.500 long tons')).toBeNull();
      // The raw payload stays reachable: the evidence is withheld, not deleted.
      expect(screen.getByText(workspaceCopy('en', 'stage.card.raw'))).toBeVisible();
    });

  it('withholds them from a completed envelope that was never requested', () => {
    report(DATA, { requested: false, status: 'not_requested' });
    expect(screen.queryByText(copy('balance.cost.title'))).toBeNull();
    expect(screen.queryByText('412.500 long tons')).toBeNull();
  });

  it('writes the gate once, as requested-and-completed and nothing weaker', () => {
    expect(readingsAllowed('report', conceptStage(DATA))).toBe(true);
    expect(readingsAllowed('report', conceptStage(DATA, { status: 'partial' as StageEnvelope['status'] })))
      .toBe(false);
    expect(readingsAllowed('report', conceptStage(DATA, { requested: false }))).toBe(false);
    expect(readingsAllowed('report', null)).toBe(false);
    // The workbench keeps its own independent policy for its own panel.
    expect(readingsAllowed('independent', null)).toBe(true);
  });

  it('adds no section for an optional feature nobody declared', () => {
    const bare = clone(DATA) as Record<string, unknown>;
    delete bare.fixed_armour; delete bare.battery_layouts; delete bare.cost;
    report(bare);
    expect(screen.queryByText(copy('balance.fixedArmour.title'))).toBeNull();
    expect(screen.queryByText(copy('balance.layout.title'))).toBeNull();
    expect(screen.queryByText(copy('balance.cost.title'))).toBeNull();
    expect(componentReadings(bare)).toEqual({ fixedArmour: [], layouts: [], auxiliaryWeapons: [], cost: null });
    // An empty list is absent, and an absent feature never becomes an empty one.
    expect(reportMetrics('design_balance', conceptStage(bare))).toEqual([]);
  });

  it('shares one projection between the report and the workbench', () => {
    const payload = clone(DATA) as Record<string, unknown>;
    // The workbench panel keeps its independent policy: the same readings are
    // readable while the rest of the screen is incomplete.
    const run = { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal',
      status: 'completed', request_fingerprint: 'r', created_at: '', started_at: null,
      finished_at: null, cancel_requested: false, error: null,
      result: result({ design_balance: conceptStage(payload, { status: 'partial' as StageEnvelope['status'] }) }),
    } as unknown as RunView;
    const { unmount } = render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={run} available />
    </UnitProvider>);
    const workbench = screen.getByText(copy('balance.fixedArmour.title')).textContent;
    unmount();
    report(payload, { status: 'partial' as StageEnvelope['status'] });
    // Same words, same numbers, and the report still shows nothing at all.
    expect(screen.queryByText(copy('balance.fixedArmour.title'))).toBeNull();
    expect(workbench).toBe(copy('balance.fixedArmour.title'));
  });

  it('reads the recovered per-term breakdown a region actually has', () => {
    report(DATA);
    const section = (id: string): HTMLElement =>
      // The innermost matching section: the family group wraps every reading and
      // shares its first heading, so the last match is the one region itself.
      [...document.querySelectorAll('section.concept-balance-group')]
        .filter(node => node.querySelector('h5')?.textContent === id).at(-1) as HTMLElement;
    const deck = section('deck');
    expect(within(deck).getByText(copy('balance.fixedArmour.metric.central'))).toBeTruthy();
    expect(within(deck).getByText('60.000 long tons')).toBeVisible();
    // A deck has no fore or aft conning tower: the breakdown is the kind's own,
    // never a superset every region is shown.
    expect(within(deck).queryByText(copy('balance.fixedArmour.metric.foreTower'))).toBeNull();
    expect(within(deck).queryByText(copy('balance.fixedArmour.metric.aftTower'))).toBeNull();
    expect(within(deck).queryByText(copy('balance.fixedArmour.plate'))).toBeNull();
    const belt = section('main_belt');
    expect(within(belt).getByText(copy('balance.fixedArmour.plate'))).toBeTruthy();
    expect(within(belt).queryByText(copy('balance.fixedArmour.metric.central'))).toBeNull();
  });

  it('reads the conning tower as its own fore and aft contributions', () => {
    report({ ...DATA, fixed_armour: [{ ...FIXED_ARMOUR[1], id: 'tower', kind: 'conning',
      values: { ...FIXED_ARMOUR[1].values, central_long_tons: null,
        quarter_long_tons: null, fore_long_tons: 5.0, aft_long_tons: 3.0 } }] });
    const conning = [...document.querySelectorAll('section.concept-balance-group')]
      .filter(node => node.querySelector('h5')?.textContent === 'tower').at(-1) as HTMLElement;
    expect(within(conning).getByText(copy('balance.fixedArmour.metric.foreTower'))).toBeTruthy();
    expect(within(conning).getByText(copy('balance.fixedArmour.metric.aftTower'))).toBeTruthy();
    // The combined figure is the one proposed total, counted exactly once.
    expect(within(conning).getAllByText('88.250 long tons')).toHaveLength(1);
    expect(within(conning).getByText('5.000 long tons')).toBeVisible();
    expect(within(conning).getByText('3.000 long tons')).toBeVisible();
  });

  it('says when a region carries no identifier, so its reading cannot be matched', () => {
    report({ ...DATA, fixed_armour: [{ ...FIXED_ARMOUR[0], id: '' }] });
    expect(screen.getByText(copy('balance.fixedArmour.unidentified'))).toBeVisible();
    expect(screen.queryByText('main_belt')).toBeNull();
  });
});

describe('keyed component metrics for the comparison', () => {
  it('matches rows by their identifier, never by array position', () => {
    const before = conceptStage(DATA);
    const reordered = clone(DATA) as Record<string, unknown>;
    reordered.fixed_armour = [FIXED_ARMOUR[1], FIXED_ARMOUR[0]];
    const after = conceptStage(reordered);
    // The same declaration in another order is the same identity set.
    expect(reportMetrics('design_balance', before).map(m => m.id).sort())
      .toEqual(reportMetrics('design_balance', after).map(m => m.id).sort());
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p)).groups
      .flatMap(g => g.cells);
    expect(cells.every(cell => cell.delta === 0)).toBe(true);
  });

  it('keeps long tons and the source’s money labels, and converts nothing', () => {
    const metrics = reportMetrics('design_balance', conceptStage(DATA));
    const total = metrics.find(m => m.id === 'fixed_armour:main_belt:total_long_tons');
    expect(total).toMatchObject({ canonicalUnit: 'LT', dimension: undefined, blocked: false });
    expect(metrics.find(m => m.id === 'cost:usd_million')).toMatchObject({ canonicalUnit: 'million USD' });
    expect(metrics.find(m => m.id === 'cost:gbp_million')).toMatchObject({ canonicalUnit: 'million GBP' });
    expect(metrics.find(m => m.id === 'cost:load_long_tons')).toMatchObject({ canonicalUnit: 'LT' });
    // The reader's unit preference never reaches these: there is no dimension to
    // convert through, so no live rate and no inflation can be implied either.
    expect(metrics.every(m => m.dimension === undefined)).toBe(true);
  });

  it('blocks a repeated, missing, unavailable or method-mismatched record', () => {
    const cases: Array<[string, Record<string, unknown>]> = [
      ['duplicate', { fixed_armour: [FIXED_ARMOUR[0], { ...FIXED_ARMOUR[0] }] }],
      ['missing', { fixed_armour: [{ ...FIXED_ARMOUR[0], id: null }] }],
      ['unavailable', { fixed_armour: [{ ...FIXED_ARMOUR[0], status: 'unavailable' }] }],
      ['mismatch', { fixed_armour: [{ ...FIXED_ARMOUR[0], method_version: 'sps-3b3-fixed-armour-v2' }] }],
    ];
    for (const [name, patch] of cases) {
      const metrics = reportMetrics('design_balance', conceptStage({ ...DATA, ...patch }));
      expect(metrics.filter(m => m.id.startsWith('fixed_armour:')).every(m => m.blocked), name)
        .toBe(true);
    }
    // The layout rows and the cost reading keep their own same rules.
    const layout = reportMetrics('design_balance', conceptStage({ ...DATA,
      battery_layouts: [{ ...LAYOUTS[0], status: 'unavailable' }] }));
    expect(layout.filter(m => m.id.startsWith('battery_layouts:')).every(m => m.blocked)).toBe(true);
    const cost = reportMetrics('design_balance', conceptStage({ ...DATA,
      cost: { ...COST, status: 'unavailable' } }));
    expect(cost.filter(m => m.id.startsWith('cost:')).every(m => m.blocked)).toBe(true);
  });

  it('shows a delta when both parents completed and the saved methods match', () => {
    const before = conceptStage(DATA);
    const changed = clone(DATA) as Record<string, unknown>;
    changed.fixed_armour = [{ ...FIXED_ARMOUR[0], values: { ...FIXED_ARMOUR[0].values,
      total_long_tons: 430.0, mass_t: 436.8, plate_long_tons: 430.0 } }, FIXED_ARMOUR[1]];
    changed.cost = { ...COST, values: { ...COST.values, usd_million: 4.95 } };
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: conceptStage(changed) }) },
      (k, p) => zhCopy(k as never, p)).groups.flatMap(g => g.cells);
    const total = cells.find(c => c.path.includes('main_belt')
      && c.path.endsWith('total_long_tons'));
    expect(total).toMatchObject({ state: 'known', delta: 17.5, canonicalUnit: 'LT' });
    const money = cells.find(c => c.path.endsWith('usd_million'));
    expect(money).toMatchObject({ state: 'known', canonicalUnit: 'million USD' });
    expect(money!.delta).toBeCloseTo(0.138, 9);
  });

  it('withholds the delta when a component method changed between the two runs', () => {
    const before = conceptStage(DATA);
    const after = conceptStage(clone(DATA) as Record<string, unknown>, {
      method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1',
        methods: { fixed_armour: 'sps-3b3-fixed-armour-v2', cost: 'sps-3b3-cost-v1',
          layout: 'sps-3b3-battery-layout-v1' } },
    });
    const comparison = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p));
    expect(comparison.groups.flatMap(g => g.cells).every(c => c.delta === null)).toBe(true);
  });

  it('names every new report metric in both languages', () => {
    const keys = ['total_long_tons', 'mass_t', 'plate_long_tons', 'central_long_tons',
      'fore_long_tons', 'quarter_long_tons', 'aft_long_tons', 'freeboard_m', 'super_factor',
      'mounts', 'barrels', 'usd_million', 'gbp_million', 'base_usd_million',
      'light_usd_million', 'machinery_usd_million', 'borne_usd_million', 'load_long_tons',
      'light_basis_long_tons', 'year_factor'];
    for (const key of keys) {
      const english = workspaceCopy('en', `data.${key}` as never);
      const chinese = zhCopy(`data.${key}` as never);
      expect(english, key).not.toBe(`data.${key}`);
      expect(english.trim(), key).not.toBe('');
      expect(chinese.trim(), key).not.toBe('');
      expect(chinese, key).not.toBe(english);
    }
  });
});

describe('the current-revision review guide', () => {
  function guide(over: Partial<Parameters<typeof ConceptReviewGuide>[0]> = {}) {
    cleanup();
    render(<UnitProvider preferences={null}><ConceptReviewGuide enabled dirty={false} revision={7}
      conditionId="normal" current={null} requested requestCurrent {...over} /></UnitProvider>);
    return screen.getByLabelText(copy('concept.guide.title')) as HTMLElement;
  }

  const savedRun = { id: 'run-a', project_id: 'p1', revision: 7, condition_id: 'normal',
    status: 'completed', result: { stages: {} } } as unknown as RunView;

  it('names the revision and the condition it is talking about', () => {
    const root = guide();
    expect(root.textContent).toContain(copy('concept.guide.revision',
      { revision: 7, condition: 'normal' }));
  });

  it('says the saved revision is saved, and the next step is to run it', () => {
    const root = guide();
    expect(root.textContent).toContain(copy('concept.guide.state.declare'));
    expect(root.textContent).toContain(copy('concept.guide.state.save', { revision: 7 }));
    expect(root.textContent).toContain(copy('concept.guide.state.runNone'));
  });

  it('says the draft has to be saved before a run can read it', () => {
    const root = guide({ dirty: true });
    expect(root.textContent).toContain(copy('concept.guide.state.saveDirty'));
    expect(root.textContent).not.toContain(copy('concept.guide.state.save', { revision: 7 }));
  });

  it('refuses to call a proposal reviewable when the request no longer matches', () => {
    const matching = guide({ current: savedRun, requestCurrent: true });
    expect(matching.textContent).toContain(copy('concept.guide.state.review'));
    const changed = guide({ current: savedRun, requestCurrent: false });
    expect(changed.textContent).toContain(copy('concept.guide.state.reviewChanged'));
    // The run itself is still the current result; only the review is withheld,
    // so the reader is never offered a proposal against a stale request.
    expect(changed.textContent).toContain(copy('concept.guide.state.run'));
    expect(changed.textContent).not.toContain(copy('concept.guide.state.review', {}));
  });

  it('never presents an older check as the current result', () => {
    const none = guide();
    expect(none.textContent).toContain(copy('concept.guide.state.runNone'));
    // An older check of the same project stays history, and the guide says so
    // rather than offering proposals against it.
    expect(none.textContent).toContain(copy('concept.guide.state.reviewStale'));
    expect(none.textContent).not.toContain(copy('concept.guide.state.review'));
    // A screen the request does not ask for is its own refusal, named as such.
    const unrequested = guide({ requested: false });
    expect(unrequested.textContent).toContain(copy('concept.guide.state.runUnrequested'));
    const off = guide({ enabled: false });
    expect(off.textContent).toContain(copy('concept.guide.state.declareOff'));
  });

  it('states that cost follows the selected masses and an explicit adoption', () => {
    const root = guide();
    expect(root.textContent).toContain(copy('concept.guide.cost'));
    expect(copy('concept.guide.cost')).toMatch(/selected/i);
    expect(copy('concept.guide.state.apply')).toMatch(/explicit/i);
  });

  it('keeps both languages for every word the guide prints', () => {
    for (const key of ['concept.guide.title', 'concept.guide.note', 'concept.guide.revision',
      'concept.guide.step.declare', 'concept.guide.step.save', 'concept.guide.step.run',
      'concept.guide.step.review', 'concept.guide.step.apply', 'concept.guide.step.rerun',
      'concept.guide.done', 'concept.guide.pending', 'concept.guide.state.declare',
      'concept.guide.state.declareOff', 'concept.guide.state.save', 'concept.guide.state.saveDirty',
      'concept.guide.state.run', 'concept.guide.state.runNone', 'concept.guide.state.runUnrequested',
      'concept.guide.state.review', 'concept.guide.state.reviewChanged',
      'concept.guide.state.apply', 'concept.guide.state.rerun', 'concept.guide.cost',
    ] as ConceptKey[]) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(conceptCopy('zh-CN', key).trim(), key).not.toBe('');
      expect(conceptCopy('zh-CN', key), key).not.toBe(copy(key));
    }
  });
});

import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { DesignBalanceResults } from '../components/DesignBalanceResults';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

// The layout readings are the server's own numbers. This suite only checks that
// each declared value arrives with its own unit, that an unknown reading is
// printed as unknown rather than as a zero, and that the server's own reasons
// are shown instead of being re-derived or swallowed.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);

function baseProject(): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [], systems: {},
  };
}

function stage(status: StageEnvelope['status'], data: StageEnvelope['data']): StageEnvelope {
  return { status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null,
      historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data };
}

function balanceRun(data: StageEnvelope['data'], status = 'completed'): RunView {
  const result = {
    schema: 'plimsoll-analysis-1', status: 'partial', project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: {}, input_snapshot: baseProject(), units: {}, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: false, converged: null, model_applicable: true,
      historical_validated: null },
    stages: { design_balance: stage(status as StageEnvelope['status'], data) },
  } as unknown as AnalysisResult;
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'partial',
    request_fingerprint: 'rf', created_at: '', started_at: null, finished_at: null,
    cancel_requested: false, result, error: null } as RunView;
}

const BASE = {
  schema: 'plimsoll-concept-balance-1', status: 'completed',
  method_version: 'sps-3b3-adapted-v1', method_scope: 'recovered 3b3',
  values: { selected_total_mass_t: 6963.78 }, structure: {}, strength: {}, space: {},
  stability: {}, seakeeping: {}, crew: {}, hull_proxy: {}, power: {}, design_warnings: [],
};

function groupReading(over: Record<string, unknown> = {}) {
  return { battery_id: 'main', state: 'declared', mount_selector: 4, layout_index: 1,
    elevated_mounts: 1, deck_mounts: 1, depressed_mounts: 2, mounts: 4, barrels_per_mount: 2,
    barrels: 8, per_mount: 2, weight_adjustment: 1, diameter_ft: 1.05, mounts_for: 2,
    freeboard_m: 5.4, ...over };
}

const AVAILABLE = {
  ...BASE,
  battery_layouts: [{
    id: 'main_layout', method_version: 'sps-3b3-battery-layout-v1', status: 'available',
    groups: { group1: groupReading(),
      group2: groupReading({ battery_id: 'wing', layout_index: 7, mounts: 2,
        elevated_mounts: null, deck_mounts: 1, depressed_mounts: 1, mounts_for: 0,
        barrels: 4, freeboard_m: 4.2, mount_selector: 3 }) },
    mounts: 6, barrels: 12, freeboard_m: 5.0, super_factor: 1.08,
    armour: {
      values: { status: 'available', face_long_tons: 560.1, rear_roof_long_tons: 210.4,
        barbette_long_tons: 41.9, total_long_tons: 812.4, mounts_group1: 4, mounts_group2: 2,
        barrels: 12, face_mm: 150, rear_roof_mm: 100, barbette_mm: 75 },
      provenance: { method: 'sps-3b3-battery-armour-v2',
        source_sha256: '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc' },
      diagnostics: [],
    },
    diagnostics: [],
    provenance: { method: 'sps-3b3-battery-layout-v1', kernel: 'battery_layout_freeboard_and_super',
      source_sha256: '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc' },
  }],
};

function read(data: unknown, preferences: unknown = null) {
  render(<UnitProvider preferences={preferences}>
    <DesignBalanceResults run={balanceRun(data as StageEnvelope['data'])} available />
  </UnitProvider>);
}

/** One layout's own block, addressed by the identifier its heading prints. */
function layoutPanel(id: string): HTMLElement {
  return screen.getByText(id).closest('section') as HTMLElement;
}

beforeEach(() => { cleanup(); vi.clearAllMocks(); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the layout readings of the saved screen', () => {
  it('prints each layout as its own result, with its method and its own identity', () => {
    read(AVAILABLE);
    expect(screen.getByText(copy('balance.layout.title'))).toBeVisible();
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText(copy('balance.layout.freeboard'))).toBeTruthy();
    expect(panel.textContent).toContain('sps-3b3-battery-layout-v1');
    expect(panel.textContent).toContain('sps-3b3-battery-armour-v2');
    expect(panel.textContent).toContain('82ecc3fe');
  });

  it('reads the derived freeboard in metres and the height factor as the server sent them', () => {
    read(AVAILABLE);
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText('5 m')).toBeVisible();
    expect(within(panel).getByText('1.080')).toBeVisible();
    // Counts are counts: they are printed as the integers the server derived.
    expect(within(panel).getByText(copy('balance.layout.mounts')).textContent).toBeTruthy();
    expect(panel.textContent).toContain('6');
    expect(panel.textContent).toContain('12');
  });

  it('follows the reader’s length unit for the freeboard without changing the stored one', () => {
    read(AVAILABLE, { length: 'ft' });
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText(/^16\.40\d* ft$/)).toBeVisible();
  });

  it('shows each group’s own reading beside its identity', () => {
    read(AVAILABLE);
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText(copy('balance.layout.group1'))).toBeTruthy();
    expect(within(panel).getByText(copy('balance.layout.group2'))).toBeTruthy();
    expect(within(panel).getByText('main')).toBeTruthy();
    expect(within(panel).getByText('wing')).toBeTruthy();
    expect(within(panel).getByText('5.4 m')).toBeVisible();
    expect(within(panel).getByText('4.2 m')).toBeVisible();
  });

  it('prints the complete two-group armour as long tons, component by component', () => {
    read(AVAILABLE);
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText(copy('balance.layout.armour'))).toBeTruthy();
    expect(within(panel).getByText('560.100 long tons')).toBeVisible();
    expect(within(panel).getByText('210.400 long tons')).toBeVisible();
    expect(within(panel).getByText('41.900 long tons')).toBeVisible();
    expect(within(panel).getByText('812.400 long tons')).toBeVisible();
  });

  it('says so when a layout declares no armour, without withholding its layout readings', () => {
    const noArmour = { ...AVAILABLE, battery_layouts: [{ ...AVAILABLE.battery_layouts[0], armour: null }] };
    read(noArmour);
    const panel = layoutPanel('main_layout');
    expect(within(panel).getByText(copy('balance.layout.armourNone'))).toBeVisible();
    expect(within(panel).getByText('5 m')).toBeVisible();
  });

  it('shows an unavailable reading as unknown and prints the server’s own reasons', () => {
    const unavailable = { ...AVAILABLE, battery_layouts: [{
      ...AVAILABLE.battery_layouts[0], status: 'unavailable', freeboard_m: null, super_factor: null,
      mounts: null, barrels: null, armour: null,
      groups: { group1: { ...groupReading(), state: 'unknown_facts', barrels: null,
          freeboard_m: null, mount_selector: null },
        group2: { ...groupReading({ battery_id: 'wing', layout_index: 7, mounts: null,
          barrels: null, freeboard_m: null }) } },
      diagnostics: [
        { code: 'battery_layout.unknown', severity: 'warning', field: 'barrels', blocking: false,
          path: '$.concept_design.battery_layouts[main_layout]',
          message: 'the recovered barrel count of both groups is unknown, so the height factor is unknown' },
      ],
    }] };
    read(unavailable);
    const panel = layoutPanel('main_layout');
    expect(within(panel).getAllByText(copy('proposals.unknownMass')).length).toBeGreaterThan(0);
    expect(panel.textContent).not.toMatch(/0\.000 m/);
    expect(within(panel).getByText(copy('balance.layout.diagnostics'))).toBeTruthy();
    expect(panel.textContent)
      .toContain('the recovered barrel count of both groups is unknown, so the height factor is unknown');
  });

  it('never prints a known zero as unknown, for a layout with no mounts at all', () => {
    const empty = { ...AVAILABLE, battery_layouts: [{
      ...AVAILABLE.battery_layouts[0], status: 'available', mounts: 0, barrels: 0,
      freeboard_m: 0, super_factor: 1,
      groups: { group1: { ...groupReading(), mounts: 0, barrels: 0, freeboard_m: 0, state: 'empty' },
        group2: { ...groupReading({ battery_id: 'wing', mounts: 0, barrels: 0, freeboard_m: 0,
          state: 'empty' }) } },
      armour: null,
    }] };
    read(empty);
    const panel = layoutPanel('main_layout');
    // A determined zero is a reading, not a missing one: the layout's own
    // freeboard and both groups' freeboards are all an explicit zero metre.
    expect(within(panel).getAllByText('0 m').length).toBe(3);
    expect(within(panel).getAllByText('1.000').length).toBeGreaterThan(0);
    expect(within(panel).queryByText(copy('proposals.unknownMass'))).toBeNull();
  });

  it('keeps the old screen untouched when no layout is declared', () => {
    read(BASE);
    expect(screen.getByText(copy('balance.title'))).toBeVisible();
    expect(screen.queryByText(copy('balance.layout.title'))).toBeNull();
  });

  it('prints every declared layout, not only the first one', () => {
    const two = { ...AVAILABLE, battery_layouts: [AVAILABLE.battery_layouts[0],
      { ...AVAILABLE.battery_layouts[0], id: 'aft_layout', freeboard_m: 3.5, super_factor: null }] };
    read(two);
    expect(screen.getByText(copy('balance.layout.title'))).toBeVisible();
    expect(within(layoutPanel('main_layout')).getByText('5 m')).toBeVisible();
    expect(within(layoutPanel('aft_layout')).getByText('3.5 m')).toBeVisible();
    expect(within(layoutPanel('aft_layout')).getByText(copy('proposals.unknownMass'))).toBeVisible();
  });
});

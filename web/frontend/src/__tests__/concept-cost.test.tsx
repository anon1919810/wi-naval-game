import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { DesignBalanceResults } from '../components/DesignBalanceResults';
import {
  claimedTargetIds, componentBindings, costEnabled, costOf, costReading, newConcept, newCost,
  patchCost, removeCost,
} from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import * as api from '../api';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

// Money in the recovered source is a *reading*, never a weight. This suite checks
// that the section is an explicit on/off with one source field and no target at
// all, that disabling it removes nothing else, and that a returned reading is
// printed in the source's own historical labels with its own status — never as a
// modern price, never as a proposal, and never from a stale result.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

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

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);
const copyZh = (key: ConceptKey) => conceptCopy('zh-CN', key);
const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;

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

function stage(status: StageEnvelope['status'], data: StageEnvelope['data']): StageEnvelope {
  return { status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null,
      historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data };
}

function balanceRun(data: StageEnvelope['data'], status: StageEnvelope['status'] = 'completed'): RunView {
  const result = {
    schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'normal',
    project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
    request: {}, input_snapshot: enabledProject(), units: {}, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: true, converged: null, model_applicable: true,
      historical_validated: null },
    stages: { design_balance: stage(status, data) },
  } as unknown as AnalysisResult;
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'rf', created_at: '', started_at: null, finished_at: null,
    cancel_requested: false, result, error: null } as RunView;
}

const BASE = {
  schema: 'plimsoll-concept-balance-1', status: 'completed',
  method_version: 'sps-3b3-adapted-v1', method_scope: 'recovered 3b3',
  values: { selected_total_mass_t: 6963.78 }, structure: {}, strength: {}, space: {},
  stability: {}, seakeeping: {}, crew: {}, hull_proxy: {}, power: {}, design_warnings: [],
};

const COST_AVAILABLE = {
  method_version: 'sps-3b3-cost-v1', status: 'available',
  currency_convention: 'empirical historical reading in the source’s own labels',
  inputs: { displacement_t: 7000, hull_year: 1918, machinery_mass_t: 1168.4539,
    ammunition_mass_t: 45.7221, fuel_mass_t: 711.2328, borne_mass_t: 60.9628,
    displacement_long_tons: 6888.6, load_long_tons: 1919.2, light_basis_long_tons: 4969.4 },
  values: { usd_million: 4.812, gbp_million: 1.203, base_usd_million: 4.35,
    light_usd_million: 0.6957, machinery_usd_million: 0.6662, borne_usd_million: 0.2048,
    load_long_tons: 1919.2, light_basis_long_tons: 4969.4, year_factor: 1.1068181818181819 },
  diagnostics: [],
  provenance: { method_version: 'sps-3b3-cost-v1', kernel: 'empirical_cost_usd_million',
    source_sha256: '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc',
    currency_convention: 'million US dollars and million pounds with the source’s own 4:1 ratio' },
};

const COST_UNAVAILABLE = {
  method_version: 'sps-3b3-cost-v1', status: 'unavailable',
  values: { usd_million: null, gbp_million: null, base_usd_million: null,
    light_usd_million: null, machinery_usd_million: null, borne_usd_million: null,
    load_long_tons: null, light_basis_long_tons: null, year_factor: null },
  inputs: { displacement_t: 7000, hull_year: null, machinery_mass_t: 1168.4539,
    ammunition_mass_t: 45.7221, fuel_mass_t: 711.2328, borne_mass_t: null },
  diagnostics: [{ code: 'concept_cost.unknown', severity: 'error', blocking: false,
    path: '$.concept_design.cost',
    message: 'the recovered cost expression needs the selected displacement, machinery, ammunition, fuel and borne masses; borne_mass_t is unknown and is never read as zero' }],
  provenance: { method_version: 'sps-3b3-cost-v1', source_sha256: '82ecc3fe' },
};

function read(data: unknown, available = true) {
  render(<UnitProvider preferences={null}>
    <DesignBalanceResults run={balanceRun(data as StageEnvelope['data'])} available={available} />
  </UnitProvider>);
}

beforeEach(() => { cleanup(); vi.clearAllMocks(); vi.mocked(api.listProjects).mockResolvedValue([]); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the cost section is an explicit on/off and a source, and nothing else', () => {
  it('is absent from a project that never enabled it, so an old project is untouched', () => {
    const { document } = mount(enabledProject());
    expect(costEnabled(config(document()))).toBe(false);
    expect('cost' in config(document())).toBe(false);
    expect(within(screen.getByText(copy('concept.group.cost')).closest('div.form-card') as HTMLElement)
      .getByRole('checkbox', { name: copy('concept.cost.use') })).not.toBeChecked();
  });

  it('writes one source field when turned on, and an explicit null until it is typed', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.cost.use') }));
    expect(config(document()).cost).toEqual({ source: null });
    expect(costEnabled(config(document()))).toBe(true);
    fireEvent.change(screen.getByLabelText(copy('concept.cost.source')),
      { target: { value: 'the yard’s own cost return' } });
    expect(config(document()).cost.source).toBe('the yard’s own cost return');
    // A cleared source is unknown, not an empty claim of a source.
    fireEvent.change(screen.getByLabelText(copy('concept.cost.source')), { target: { value: '' } });
    expect(config(document()).cost.source).toBeNull();
  });

  it('claims no ledger target, so it can never enter the component bindings', () => {
    const project = enabledProject();
    const before = claimedTargetIds(config(project));
    const declared = { ...config(project), cost: newCost() };
    expect(claimedTargetIds(declared)).toEqual(before);
    expect(componentBindings(declared)).toEqual(componentBindings(config(project)));
    // Money is not a mass: nothing in the roles table names a cost item.
    expect(JSON.stringify(componentBindings(declared))).not.toMatch(/cost/);
  });

  it('turns off by removing only the declaration', () => {
    const project = enabledProject();
    const declared = { ...config(project), cost: { source: 'yard return' } };
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const before = document();
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.cost.use') }));
    expect(config(document()).cost).toBeNull();
    expect(config(document()).batteries).toEqual(config(before).batteries);
    expect(config(document()).balance).toEqual(config(before).balance);
    // Disabling again is idempotent and writes the same shape.
    expect(removeCost(removeCost(config(document()))).cost).toBeNull();
    expect(patchCost(config(project), { source: 'x' })).toMatchObject({ cost: { source: 'x' } });
    expect(costOf({ cost: { source: null } })).toEqual({ source: null });
    expect(costOf({ cost: null })).toBeNull();
  });

  it('says plainly that the reading follows the selected masses', () => {
    mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.cost.use') }));
    const card = screen.getByText(copy('concept.cost.selectedOnly')).closest('div.form-card') as HTMLElement;
    expect(card.textContent).toMatch(/selected/i);
    // It says what does not move it either: armour alone is not a cost input.
    expect(card.textContent).toMatch(/armour/i);
  });

  it('keeps English and Chinese words for every label it prints', () => {
    for (const key of ['concept.group.cost', 'concept.cost.note', 'concept.cost.use',
      'concept.cost.source', 'concept.cost.sourceHint', 'concept.cost.selectedOnly',
      'balance.cost.title', 'balance.cost.method', 'balance.cost.currency',
      'balance.cost.metric.usd', 'balance.cost.metric.gbp', 'balance.cost.metric.load',
      'balance.cost.metric.light', 'balance.cost.metric.yearFactor',
      'balance.cost.metric.lightShare', 'balance.cost.metric.machineryShare',
      'balance.cost.metric.borneShare', 'balance.cost.unitConvention',
      'proposals.component.fixedArmour'] as ConceptKey[]) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });
});

describe('the returned cost reading', () => {
  it('prints both money figures in the source’s own historical labels', () => {
    read({ ...BASE, cost: COST_AVAILABLE });
    expect(screen.getByText(copy('balance.cost.title'))).toBeVisible();
    expect(screen.getByText('4.812 million USD')).toBeVisible();
    expect(screen.getByText('1.203 million GBP')).toBeVisible();
    // The convention is stated beside the numbers rather than assumed: no live
    // rate, no inflation adjustment, no modern currency estimate.
    expect(screen.getByText(copy('balance.cost.currency'))).toBeVisible();
    expect(screen.getByText(copy('balance.cost.unitConvention'))).toBeVisible();
  });

  it('keeps the recovered long-ton masses in long tons and the year factor dimensionless', () => {
    read({ ...BASE, cost: COST_AVAILABLE });
    expect(screen.getByText('1919.200 long tons')).toBeVisible();
    expect(screen.getByText('4969.400 long tons')).toBeVisible();
    expect(screen.getByText('1.107')).toBeVisible();
    // The three cost contributions the recovered expression actually has.
    expect(screen.getByText('0.696 million USD')).toBeVisible();
    expect(screen.getByText('0.666 million USD')).toBeVisible();
    expect(screen.getByText('0.205 million USD')).toBeVisible();
    expect(screen.getByText(copy('balance.cost.method', {
      method: 'sps-3b3-cost-v1',
      source: '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc' })))
      .toBeVisible();
  });

  it('shows an unavailable reading as unknown and prints the server’s own reasons', () => {
    read({ ...BASE, cost: COST_UNAVAILABLE });
    expect(screen.getByText(copy('balance.cost.title'))).toBeVisible();
    expect(screen.getAllByText(copy('proposals.unknownMass')).length).toBeGreaterThan(0);
    expect(screen.getByText(copy('balance.cost.unavailable', { status: 'unavailable' })))
      .toBeVisible();
    expect(screen.getByText(copy('balance.cost.diagnostics'))).toBeVisible();
    expect(document.body.textContent)
      .toContain('borne_mass_t is unknown and is never read as zero');
    // No plausible zero price anywhere in the panel.
    expect(document.body.textContent).not.toMatch(/0\.000 million/);
  });

  it('adds no section at all when the feature was never declared', () => {
    read(BASE);
    expect(screen.getByText(copy('balance.title'))).toBeVisible();
    expect(screen.queryByText(copy('balance.cost.title'))).toBeNull();
    // Absent is not an empty section: an empty one would claim the screen looked.
    expect(screen.queryByText(copy('balance.cost.note'))).toBeNull();
    expect(costReading(balanceRun(BASE as StageEnvelope['data']))).toBeNull();
  });

  it('stays readable while the rest of the screen is unavailable', () => {
    // The cost reading is exposed before the screen's early returns, so an
    // unrelated physical failure does not withhold it.
    read({ ...BASE, status: 'unavailable', reason: 'the design hull proxy is unavailable',
      cost: COST_AVAILABLE }, true);
    expect(screen.getByText(copy('balance.cost.title'))).toBeVisible();
    expect(screen.getByText('4.812 million USD')).toBeVisible();
  });

  it('withholds every reading while the saved revision is not the one on screen', () => {
    // The workbench's own gate: an edited draft has no current result, so no
    // cost — and no armour — may be presented against it.
    read({ ...BASE, cost: COST_AVAILABLE }, false);
    expect(screen.queryByText(copy('balance.cost.title'))).toBeNull();
    expect(screen.queryByText('4.812 million USD')).toBeNull();
    expect(screen.getByText(copy('balance.notConfigured'))).toBeVisible();
  });
});

import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { DesignBalanceResults } from '../components/DesignBalanceResults';
import { MassProposalPanel } from '../components/MassProposalPanel';
import { conceptEnabled, newConcept, requestDesignBalance, requestOptionsKey, withDesignBalance } from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy } from '../i18n/concept';
import { storedTemplateName, workspaceCopy } from '../i18n/workspace';
import { Library } from '../pages/Library';
import * as api from '../api';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';

// The concept editor is driven through real events against a real stateful
// parent, because the thing under test is what the *document* ends up holding:
// a control that renders correctly but never writes is exactly the defect this
// suite exists to catch.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const LEDGER = {
  id: 'weights', label: 'declared concept design',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'weapons.mounts', mass_t: 152.407, x_m: 104 },
    { id: 'weapons.ammunition', mass_t: 45.7221, x_m: 92 },
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts', 'weapons.ammunition'] } },
  propulsion: { machinery: { weight_item_ids: ['propulsion.machinery'] }, fuel: { weight_item_ids: ['propulsion.fuel'] } },
};

function baseProject(): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS,
  };
}

function Harness({ initial, onDocument }: { initial: ProjectDocument; onDocument: (next: ProjectDocument) => void }) {
  const [draft, setDraft] = useState(initial);
  return <UnitProvider preferences={null}>
    <ConceptDesignEditor project={draft} onChange={next => { setDraft(next); onDocument(next); }} />
  </UnitProvider>;
}

/** A stateful editor plus the document it has written so far. */
function mount(initial: ProjectDocument) {
  const written: ProjectDocument[] = [];
  const view = render(<Harness initial={initial} onDocument={next => written.push(next)} />);
  return { view, written, document: () => written[written.length - 1] ?? initial };
}

const CONFIG_KEY = conceptCopy('en', 'concept.enable');

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.createProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: baseProject() });
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('the concept design editor', () => {
  it('is off for a project that never declared one, and turning it on writes the section', () => {
    const { document } = mount(baseProject());
    expect(screen.getByRole('checkbox', { name: CONFIG_KEY })).not.toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: CONFIG_KEY }));
    const next = document();
    expect(conceptEnabled(next)).toBe(true);
    expect((next as Record<string, unknown>).concept_design).toMatchObject({
      schema: 'plimsoll-concept-design-1', method: 'sps-3b3-adapted-v1', estimate: true,
    });
  });

  it('removes the section again when it is switched off, so old defaults return', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('checkbox', { name: CONFIG_KEY }));
    expect(conceptEnabled(document())).toBe(false);
    expect((document() as Record<string, unknown>).concept_design).toBeUndefined();
  });

  it('writes the declaration source as the reader’s own words, never a fabricated one', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    const field = screen.getByLabelText(conceptCopy('en', 'concept.source.label'));
    expect(field).toHaveValue('');
    expect(screen.getByRole('alert')).toHaveTextContent(conceptCopy('en', 'concept.missingSource'));
    fireEvent.change(field, { target: { value: 'a declared study design' } });
    expect(((document() as Record<string, any>).concept_design).source).toBe('a declared study design');
  });

  it('keeps an empty numerical input null and editable rather than inventing a default', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    const target = screen.getByLabelText(conceptCopy('en', 'concept.target.label'));
    expect(target).toHaveValue(null);
    fireEvent.change(target, { target: { value: '8200' } });
    expect(((document() as Record<string, any>).concept_design).target_displacement_t).toBe(8200);
    fireEvent.change(target, { target: { value: '' } });
    expect(((document() as Record<string, any>).concept_design).target_displacement_t).toBeNull();
  });

  it('offers the starting balance assumptions explicitly and lets each one be edited', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    expect(screen.getByText(conceptCopy('en', 'concept.balance.presetsNote'))).toBeVisible();
    const steadiness = screen.getByLabelText(conceptCopy('en', 'concept.balance.steadiness'));
    expect(steadiness).toHaveValue(50);
    expect(screen.getByLabelText(conceptCopy('en', 'concept.balance.spaceHull'))).toHaveValue(0);
    expect(screen.getByLabelText(conceptCopy('en', 'concept.balance.strengthTarget'))).toHaveValue(1);
    fireEvent.change(steadiness, { target: { value: '62' } });
    expect(((document() as Record<string, any>).concept_design).balance.steadiness).toBe(62);
  });

  it('adds a battery row and writes every ordinary battery field into the document', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    const config = () => ((document() as Record<string, any>).concept_design);
    expect(config().batteries).toHaveLength(1);
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.system')), { target: { value: 'weapons.main' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.guns')), { target: { value: 'weapons.guns' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.mounts')), { target: { value: 'weapons.mounts' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.ammunition')), { target: { value: 'weapons.ammunition' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.calibre')), { target: { value: '152.4' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.year')), { target: { value: '1918' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.mountCount')), { target: { value: '4' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.barrelsPerMount')), { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.rounds')), { target: { value: '120' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.gunType')), { target: { value: 'breech_loading' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.mountType')), { target: { value: 'deck_hoist' } });
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.battery.sharedCradle')));
    const battery = config().batteries[0];
    expect(battery).toMatchObject({
      system_id: 'weapons.main', guns_item_id: 'weapons.guns', mounts_item_id: 'weapons.mounts',
      ammunition_item_id: 'weapons.ammunition', calibre_mm: 152.4, year: 1918, mount_count: 4,
      barrels_per_mount: 2, rounds_per_gun: 120, gun_type: 'breech_loading',
      mount_type: 'deck_hoist', shared_cradle: true,
    });
  });

  it('writes a manual shell mass in kilograms and keeps it empty when the formula should estimate', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    const shell = screen.getByLabelText(conceptCopy('en', 'concept.battery.shell'));
    expect(shell).toHaveValue(null);
    fireEvent.change(shell, { target: { value: '45' } });
    expect(((document() as Record<string, any>).concept_design).batteries[0].shell_mass_kg).toBe(45);
    fireEvent.change(shell, { target: { value: '' } });
    expect(((document() as Record<string, any>).concept_design).batteries[0].shell_mass_kg).toBeNull();
  });

  it('offers only the items the chosen system owns, and never lets two bindings share one', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.system')), { target: { value: 'weapons.main' } });
    const guns = screen.getByLabelText(conceptCopy('en', 'concept.battery.guns')) as HTMLSelectElement;
    expect([...guns.options].map(option => option.value)).toEqual(['', 'weapons.guns', 'weapons.mounts', 'weapons.ammunition']);
    fireEvent.change(guns, { target: { value: 'weapons.mounts' } });
    const mounts = screen.getByLabelText(conceptCopy('en', 'concept.battery.mounts')) as HTMLSelectElement;
    const ammunition = screen.getByLabelText(conceptCopy('en', 'concept.battery.ammunition')) as HTMLSelectElement;
    // The item just taken by the guns picker is offered to neither of the others,
    // so three distinct items is a property of the controls, not a warning.
    expect([...mounts.options].map(option => option.value)).not.toContain('weapons.mounts');
    expect([...ammunition.options].map(option => option.value)).toEqual(['', 'weapons.guns', 'weapons.ammunition']);
    const battery = ((document() as Record<string, any>).concept_design).batteries[0];
    expect(battery.guns_item_id).toBe('weapons.mounts');
  });

  it('clears bindings that the newly chosen system does not own, without inventing one', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.system')), { target: { value: 'weapons.main' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.guns')), { target: { value: 'weapons.guns' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.battery.system')), { target: { value: 'propulsion.machinery' } });
    const battery = ((document() as Record<string, any>).concept_design).batteries[0];
    expect(battery.guns_item_id).toBeNull();
    expect(battery.mounts_item_id).toBeNull();
    expect(battery.ammunition_item_id).toBeNull();
    expect([...(screen.getByLabelText(conceptCopy('en', 'concept.battery.guns')) as HTMLSelectElement).options]
      .map(option => option.value)).toEqual(['', 'propulsion.machinery']);
  });

  it('keeps a fractional count as typed and marks it, instead of truncating it', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    const count = screen.getByLabelText(conceptCopy('en', 'concept.battery.mountCount'));
    fireEvent.change(count, { target: { value: '2.5' } });
    expect(((document() as Record<string, any>).concept_design).batteries[0].mount_count).toBe(2.5);
    expect(count).toHaveAttribute('aria-invalid', 'true');
  });

  it('deletes a battery row', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    expect(((document() as Record<string, any>).concept_design).batteries).toHaveLength(2);
    fireEvent.click(screen.getAllByRole('button', { name: conceptCopy('en', 'concept.battery.remove') })[0]);
    expect(((document() as Record<string, any>).concept_design).batteries).toHaveLength(1);
  });

  it('keeps keyboard focus while the battery identifier is renamed', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'concept.battery.add') }));
    const name = screen.getByLabelText(conceptCopy('en', 'concept.battery.id'));
    name.focus(); fireEvent.change(name, { target: { value: 'b' } });
    expect(screen.getByLabelText(conceptCopy('en', 'concept.battery.id'))).toHaveFocus();
    fireEvent.change(name, { target: { value: 'battery_alpha' } });
    expect((document() as any).concept_design.batteries[0].id).toBe('battery_alpha');
  });

  it('declares machinery and fuel against the items their own system owns', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.machinery.use')));
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.machinery.system')), { target: { value: 'propulsion.machinery' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.machinery.item')), { target: { value: 'propulsion.machinery' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.machinery.kind')), { target: { value: 'compound' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.machinery.speed')), { target: { value: '18' } });
    const config = () => ((document() as Record<string, any>).concept_design);
    expect(config().machinery).toMatchObject({ system_id: 'propulsion.machinery', item_id: 'propulsion.machinery', kind: 'compound', speed_kn: 18 });
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.fuel.use')));
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.fuel.system')), { target: { value: 'propulsion.fuel' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.fuel.item')), { target: { value: 'propulsion.fuel' } });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.fuel.range')), { target: { value: '4000' } });
    expect(config().fuel).toMatchObject({ system_id: 'propulsion.fuel', item_id: 'propulsion.fuel', range_nm: 4000 });
  });

  it('treats a fuel range as a distance in nautical miles, never as a speed', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.machinery.use')));
    fireEvent.click(screen.getByLabelText(conceptCopy('en', 'concept.fuel.use')));
    const range = screen.getByLabelText(conceptCopy('en', 'concept.fuel.range'));
    expect(range.closest('.field-label')?.textContent).toContain('nm');
    fireEvent.change(range, { target: { value: '4000' } });
    // No speed or length conversion: the stored value is the typed one.
    expect(((document() as Record<string, any>).concept_design).fuel.range_nm).toBe(4000);
  });

  it('binds the sole adjustable structure item from the chosen structure system', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.change(screen.getByLabelText(conceptCopy('en', 'concept.balance.structureSystem')), { target: { value: 'hull.structure' } });
    const target = screen.getByLabelText(conceptCopy('en', 'concept.balance.structureItem')) as HTMLSelectElement;
    expect([...target.options].map(option => option.value)).toEqual(['', 'hull.structure']);
    fireEvent.change(target, { target: { value: 'hull.structure' } });
    expect(((document() as Record<string, any>).concept_design).balance.structure_item_id).toBe('hull.structure');
  });

  it('assigns one role per ledger item and leaves the rest explicitly unallocated', () => {
    const { document } = mount({ ...baseProject(), concept_design: newConcept() });
    fireEvent.change(screen.getByLabelText('hull.structure Ledger roles'), { target: { value: 'structure' } });
    const roles = ((document() as Record<string, any>).concept_design).balance.roles;
    expect(roles).toEqual({ 'hull.structure': 'structure' });
    expect(screen.getByLabelText('weapons.guns Ledger roles')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('weapons.guns Ledger roles'), { target: { value: 'guns' } });
    expect(((document() as Record<string, any>).concept_design).balance.roles['weapons.guns']).toBe('guns');
  });

  it('writes the translated label on an enum option, not the stored identifier', () => {
    mount({ ...baseProject(), concept_design: newConcept() });
    const stern = screen.getByLabelText(conceptCopy('en', 'concept.stern.label')) as HTMLSelectElement;
    const option = [...stern.options].find(entry => entry.value === 'large_transom');
    expect(option?.textContent).toBe(conceptCopy('en', 'concept.stern.large_transom'));
    expect(option?.textContent).not.toBe('large_transom');
  });

  it('shows its own words in Chinese too', () => {
    const project = { ...baseProject(), concept_design: newConcept() };
    render(<Harness initial={project} onDocument={() => {}} />);
    // The helper dictionary is bilingual by construction; both languages resolve.
    expect(conceptCopy('zh-CN', 'concept.enable')).toBe('概念设计校核');
    expect(conceptCopy('zh-CN', 'proposals.apply')).toBe('应用所选估计并重算');
    expect(conceptCopy('en', 'concept.enable')).toBe('Concept design screen');
  });
});

describe('the request a draft produces', () => {
  it('matches reordered stages and the server default equilibrium fields', () => {
    const raw = { stages: ['systems', 'loading'], equilibrium: { target_trim_deg: 2 } };
    const saved = { stages: ['loading', 'systems'], equilibrium: { target_trim_deg: 2,
      rho_t_m3: 1.025, heel_bounds_deg: [-85, 85], trim_bounds_deg: [-45, 45],
      max_iterations: 50, initial: { heel_deg: 0, trim_deg: 0 }, liquid_loads: [] },
      gz_angles_deg: null, hydrostatic_waterlines_above_keel_m: null,
      bonjean_waterlines_above_keel_m: null, resistance: null, endurance_scenario_id: null, flooding: null };
    expect(requestOptionsKey(raw)).toBe(requestOptionsKey(saved));
    expect(requestOptionsKey({ ...raw, equilibrium: { target_trim_deg: 3 } })).not.toBe(requestOptionsKey(saved));
  });

  it('keeps scenario choices and sample values in the proposal request identity', () => {
    const raw = { stages: ['resistance'], resistance: { scenario_id: 'a', speeds_kn: [10, 12] } };
    expect(requestOptionsKey(raw)).toBe(requestOptionsKey({ ...raw, resistance: { ...raw.resistance, mode: 'predict_power' } }));
    expect(requestOptionsKey(raw)).not.toBe(requestOptionsKey({ ...raw, resistance: { ...raw.resistance, scenario_id: 'b' } }));
    expect(requestOptionsKey(raw)).not.toBe(requestOptionsKey({ ...raw, resistance: { ...raw.resistance, speeds_kn: [10, 13] } }));
  });

  it('asks for the concept screen only while the section exists', () => {
    expect(requestDesignBalance(baseProject())).toBe(false);
    expect(withDesignBalance(['loading', 'systems'], baseProject())).toEqual(['loading', 'systems']);
    const enabled = { ...baseProject(), concept_design: newConcept() };
    expect(requestDesignBalance(enabled)).toBe(true);
    expect(withDesignBalance(['loading', 'systems'], enabled)).toEqual(['loading', 'systems', 'design_balance']);
  });

  it('never lists the stage twice', () => {
    const enabled = { ...baseProject(), concept_design: newConcept() };
    expect(withDesignBalance(['design_balance', 'systems'], enabled)).toEqual(['design_balance', 'systems']);
  });
});

// --- the reviewed batch ------------------------------------------------------

function proposal(item: string, component: string, model: string, current: number | null, next: number) {
  return {
    operation: 'replace_weight_item_mass', item_id: item, current_mass_t: current,
    proposed_mass_t: next, difference_t: current === null ? null : next - current,
    source_system_id: 'weapons.main', source_model_id: model, requires_review: true,
    condition_id: 'normal', target: 'selected_condition', project_fingerprint: 'pf',
    input_fingerprint: 'if', request_fingerprint: 'rf',
    model: {
      id: model, method: 'empirical_estimate_v1', concept_component: component,
      formula: 'mass_t = estimate_long_tons x 1016.0469088 / 1000',
      source: { declaration: 'a declared study design', sha256: '82ecc3fe' },
      boundary: 'recovered 3b3 formulas, adapted to the explicit ledger',
    },
  };
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
    request: {}, input_snapshot: baseProject(), units: {}, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    stages: { systems: stage('completed', { update_proposals: proposals }) },
  } as unknown as AnalysisResult;
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'rf', created_at: '2026-10-15T00:00:00Z', started_at: null, finished_at: null,
    cancel_requested: false, result, error: null } as RunView;
}

describe('the proposal panel', () => {
  const run = runWith([
    proposal('weapons.guns', 'guns', 'concept.main.guns', 60.96, 49.79),
    proposal('weapons.mounts', 'mounts', 'concept.main.mounts', null, 185.27),
  ]);

  function panel(overrides: Partial<Parameters<typeof MassProposalPanel>[0]> = {}) {
    const onApply = vi.fn();
    const onRerun = vi.fn();
    render(<UnitProvider preferences={null}><MassProposalPanel run={run} identity="a" dirty={false}
      apply={{ phase: 'idle', revision: null, reason: null }} onApply={onApply} onRerun={onRerun} {...overrides} /></UnitProvider>);
    return { onApply, onRerun };
  }

  it('shows the current mass, the estimate and the difference of every proposal', () => {
    panel();
    expect(screen.getByText(/^60\.9\d* t$/)).toBeVisible();
    expect(screen.getByText(/^49\.7\d* t$/)).toBeVisible();
    expect(screen.getByText(/^-11\.1\d* t$/)).toBeVisible();
    // An unknown target mass is shown as unknown, never as zero.
    expect(screen.getAllByText(conceptCopy('en', 'proposals.unknownMass')).length).toBeGreaterThan(0);
  });

  it('shows the method, the declaration and the boundary of each estimate', () => {
    panel();
    expect(screen.getAllByText('concept.main.guns').length).toBeGreaterThan(0);
    expect(screen.getAllByText('a declared study design').length).toBe(2);
    expect(screen.getAllByText(/recovered 3b3 formulas/).length).toBe(2);
  });

  it('selects nothing for the reader and applies only what was ticked', () => {
    const { onApply } = panel();
    const button = screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    expect(button).toBeEnabled();
    fireEvent.click(button);
    expect(onApply).toHaveBeenCalledTimes(1);
    expect(onApply.mock.calls[0][0]).toHaveLength(1);
    expect(onApply.mock.calls[0][0][0].item_id).toBe('weapons.guns');
  });

  it('keeps only the most recently selected model for the same ledger item', () => {
    const alternatives = runWith([
      proposal('weapons.guns', 'guns', 'empirical', 60, 50),
      proposal('weapons.guns', 'guns', 'physical', 60, 55),
    ]);
    const { onApply } = panel({ run: alternatives });
    const choices = screen.getAllByLabelText('weapons.guns Select');
    fireEvent.click(choices[0]); fireEvent.click(choices[1]);
    expect(choices[0]).not.toBeChecked(); expect(choices[1]).toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    expect(onApply.mock.calls[0][0]).toHaveLength(1);
    expect(onApply.mock.calls[0][0][0].source_model_id).toBe('physical');
  });

  it('reads the real server source shape and method version', () => {
    const p = proposal('weapons.guns', 'guns', 'concept.main.guns', 60, 50);
    p.model.source = { source: 'real server declaration', method_version: 'sps-3b3-adapted-v1' } as any;
    panel({ run: runWith([p]) });
    expect(screen.getByText('real server declaration')).toBeVisible();
    expect(screen.getByText(/sps-3b3-adapted-v1/)).toBeVisible();
  });

  it('drops the selection when the reviewed result changes', () => {
    const { onApply } = panel();
    fireEvent.click(screen.getByLabelText('weapons.guns Select'));
    cleanup();
    panel({ identity: 'b' });
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.apply') }));
    expect(onApply).not.toHaveBeenCalled();
  });

  it('says the save stands when only the follow-up run failed, and offers the run again', () => {
    const { onRerun } = panel({ apply: { phase: 'queueFailed', revision: 3, reason: 'no active calculation' } });
    const notice = screen.getAllByRole('status').find(node => /3/.test(node.textContent ?? ''));
    expect(notice).toHaveTextContent('3');
    expect(notice).toHaveTextContent('no active calculation');
    expect(notice?.textContent).not.toMatch(/roll ?back|undo/i);
    fireEvent.click(screen.getByRole('button', { name: conceptCopy('en', 'proposals.rerun') }));
    expect(onRerun).toHaveBeenCalledTimes(1);
  });

  it('hides the batch while the draft is being edited', () => {
    panel({ dirty: true });
    expect(screen.getByText(conceptCopy('en', 'proposals.emptyDirty'))).toBeVisible();
    expect(screen.queryByRole('button', { name: conceptCopy('en', 'proposals.apply') })).toBeNull();
  });
});

// --- the adapted screen ------------------------------------------------------

describe('the concept balance screen', () => {
  function balanceRun(data: StageEnvelope['data'], status = 'completed') {
    const result = {
      schema: 'plimsoll-analysis-1', status: 'partial', project_id: 'p1', condition_id: 'normal',
      project_fingerprint: 'pf', input_fingerprint: 'if', request_fingerprint: 'rf',
      request: {}, input_snapshot: baseProject(), units: {}, method_versions: {}, sources: {},
      diagnostics: [], validity: { complete: false, converged: null, model_applicable: null, historical_validated: null },
      stages: { design_balance: stage(status as StageEnvelope['status'], data) },
    } as unknown as AnalysisResult;
    return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'partial',
      request_fingerprint: 'rf', created_at: '', started_at: null, finished_at: null, cancel_requested: false,
      result, error: null } as RunView;
  }

  const data = {
    schema: 'plimsoll-concept-balance-1', status: 'completed', method_version: 'sps-3b3-adapted-v1',
    method_scope: 'recovered 3b3', historical_validated: null,
    basis: 'declared design displacement, selected ledger allocations',
    assumption_source: 'editable estimates',
    values: { selected_total_mass_t: 6963.78, target_displacement_t: 8200, difference_t: 1236.2,
      nonstructure_mass_long_tons: 4675, remaining_structural_budget_long_tons: 3395.5,
      structure_demand_long_tons: 2606.33, structure_margin_long_tons: -427.5 },
    structure: { current_structure_long_tons: 2178.8, structure_item_id: 'hull.structure',
      current_adjustable_structure_long_tons: 2178.8, other_structure_long_tons: 0,
      required_total_long_tons: 2606.33, required_adjustable_long_tons: 2606.33,
      structure_margin_long_tons: -427.5, strength_target: 1 },
    strength: { cross: 0.86, longitudinal: 0.82, composite: 0.836, composite_target: 1, broadside_lb: 871.4 },
    space: { hull_ratio: 0.95, deck_ratio: 1.35 },
    stability: { score: 1.379, adjusted: 1.379 },
    seakeeping: { seaboat: 1.49, steadiness_score: 74.7, score: 1.49 },
    crew: { crew_min: 425, crew_max: 553 },
    hull_proxy: { natural_speed_kn: 22.3, wetted_surface_sqft: 9000, waterplane_area_sqft: 1400,
      co_sharp: 0.62, effective_length_ft: 498.7 },
    power: { hp_max: 8923, friction_fraction: 0.674 },
    design_warnings: [{ code: 'design_balance.structure_shortfall', message: 'composite strength 0.836 is below 1.000' }],
  };

  it('shows the adapted metrics as their own result, apart from the physical ones', () => {
    render(<UnitProvider preferences={null}><DesignBalanceResults run={balanceRun(data)} available /></UnitProvider>);
    expect(screen.getByText(conceptCopy('en', 'balance.title'))).toBeVisible();
    expect(screen.getAllByText('2606.330 long tons').length).toBeGreaterThan(0);
    expect(screen.getAllByText('-427.500 long tons').length).toBeGreaterThan(0);
    expect(screen.getAllByText('1.379').length).toBe(2);
    expect(screen.getByText('74.700')).toBeVisible();
    expect(screen.getByText('553.000')).toBeVisible();
    // The design warning is retained rather than folded away.
    expect(screen.getByText('composite strength 0.836 is below 1.000')).toBeVisible();
    expect(screen.getByText(conceptCopy('en', 'balance.stabilityNote'))).toBeVisible();
  });

  it('labels metric tonnes and displayed preferences without calling them long tons', () => {
    render(<UnitProvider preferences={null}><DesignBalanceResults run={balanceRun(data)} available /></UnitProvider>);
    expect(screen.getByText(/6,?963\.78 t/)).toBeVisible();
    expect(screen.queryByText('6963.780 long tons')).toBeNull();
    expect(screen.getByText(/9000\.000 ft²/)).toBeVisible();
    expect(screen.getByText(/498\.700 ft/)).toBeVisible();
    expect(screen.getByText('22.3 kn')).toBeVisible();
  });

  it('says the screen does not apply to a project that declares none', () => {
    render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={balanceRun({ status: 'not_configured', values: {} })} available /></UnitProvider>);
    expect(screen.getByText(conceptCopy('en', 'balance.notConfigured'))).toBeVisible();
  });

  it('shows a partial screen as partial, with the missing half named rather than hidden', () => {
    const partial = { ...data, status: 'partial', reason: 'the screen is incomplete', structure: {}, strength: {}, space: {}, seakeeping: {} };
    render(<UnitProvider preferences={null}><DesignBalanceResults run={balanceRun(partial, 'partial')} available /></UnitProvider>);
    const notice = screen.getAllByRole('status').find(node =>
      node.textContent === conceptCopy('en', 'balance.partial'));
    expect(notice).toBeTruthy();
    // The mass group is still read; the strength and space groups are not invented.
    expect(screen.getByText('3395.500 long tons')).toBeVisible();
    expect(screen.queryByText(conceptCopy('en', 'balance.section.strength'))).toBeNull();
    expect(screen.getAllByText(conceptCopy('en', 'proposals.unknownMass')).length).toBeGreaterThan(0);
  });

  it('names the unclassified positive mass that leaves the screen incomplete', () => {
    render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={balanceRun({ ...data, unclassified_item_ids: ['weapons.other'] })} available /></UnitProvider>);
    expect(screen.getAllByRole('status').map(node => node.textContent)
      .join(' ')).toContain('weapons.other');
  });
});

// --- the template card -------------------------------------------------------

describe('the library template cards', () => {
  it('offers the synthetic concept design as its own bilingual card', async () => {
    render(<Library onOpen={vi.fn()} />);
    const card = await screen.findByText(workspaceCopy('en', 'library.template.concept_cruiser.name'));
    expect(card).toBeVisible();
    expect(screen.getByText(workspaceCopy('en', 'library.template.concept_cruiser.tag'))).toBeVisible();
    const button = card.closest('.template-card') as HTMLButtonElement;
    fireEvent.click(button);
    await vi.waitFor(() => expect(api.createProject).toHaveBeenCalledWith('concept_cruiser',
      storedTemplateName('concept_cruiser')));
  });
});

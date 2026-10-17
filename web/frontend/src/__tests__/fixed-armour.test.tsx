import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import {
  changeFixedArmourKind, claimedTargetIds, componentBindings, duplicateFixedArmourIds,
  duplicateTargets, fixedArmour, fixedArmourRole, fixedArmourTargetConflicts,
  FIXED_ARMOUR_ROLE_BY_KIND, MAX_FIXED_ARMOUR_RECORDS, mismatchedRoles, newBattery,
  newBatteryLayout, newConcept, newFixedArmour, patchFixedArmour, removeFixedArmour,
} from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import * as api from '../api';
import type { ProjectDocument } from '../types';

// The seven recovered fixed armour regions are ordinary project input here, so
// every assertion is about what the *document* ends up holding after a real
// event. Nothing in this suite knows a belt, deck or conning expression: a mass
// is the server's, and this editor's whole duty is to keep an unknown unknown,
// keep the regions distinct, and never invent a target or a mass.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const LEDGER = {
  id: 'weights', label: 'declared concept design',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'weapons.mounts', mass_t: 152.407, x_m: 104 },
    { id: 'weapons.ammunition', mass_t: 45.7221, x_m: 92 },
    { id: 'weapons.gun_house_armour', mass_t: 40.0, x_m: 104 },
    { id: 'weapons.layout_armour', mass_t: 0, x_m: 104 },
    { id: 'weapons.main_belt', mass_t: 0, x_m: 104 },
    { id: 'weapons.bulge', mass_t: 0, x_m: 104 },
    { id: 'weapons.conning', mass_t: 0, x_m: 104 },
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts',
    'weapons.ammunition', 'weapons.gun_house_armour', 'weapons.layout_armour',
    'weapons.main_belt', 'weapons.bulge', 'weapons.conning'] } },
  armour: { fixed: { weight_item_ids: ['weapons.main_belt', 'weapons.bulge',
    'weapons.conning'] } },
  propulsion: { machinery: { weight_item_ids: ['propulsion.machinery'] },
    fuel: { weight_item_ids: ['propulsion.fuel'] } },
};

function baseProject(): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS,
  } as unknown as ProjectDocument;
}

/** An enabled concept design with the one battery row a layout may reference. */
function enabledProject(): ProjectDocument {
  const config = newConcept();
  config.source = 'a declared study design';
  config.batteries = [{
    ...newBattery([]), id: 'main', system_id: 'weapons.main',
    guns_item_id: 'weapons.guns', mounts_item_id: 'weapons.mounts',
    ammunition_item_id: 'weapons.ammunition',
    calibre_mm: 152.4, barrel_calibres: 45, year: 1918,
    gun_type: 'breech_loading', mount_type: 'deck_hoist',
    mount_count: 4, barrels_per_mount: 2, rounds_per_gun: 120,
  }];
  return { ...baseProject(), concept_design: config } as ProjectDocument;
}

function mount(initial: ProjectDocument, preferences: unknown = null) {
  const written: ProjectDocument[] = [];
  function UnitsHarness() {
    const [draft, setDraft] = useState(initial);
    return <UnitProvider preferences={preferences}>
      <ConceptDesignEditor project={draft}
        onChange={next => { setDraft(next); written.push(next); }} />
    </UnitProvider>;
  }
  render(<UnitsHarness />);
  return { written, document: () => written[written.length - 1] ?? initial };
}

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);
const copyZh = (key: ConceptKey) => conceptCopy('zh-CN', key);
const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;
const record = (document: unknown, index = 0): Record<string, any> =>
  fixedArmour(config(document))[index];

/** One region's own disclosure, addressed by the identifier its summary prints. */
function regionPanel(id: string): HTMLElement {
  return screen.getByText(id).closest('details') as HTMLElement;
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.createProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: baseProject() });
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('adding a fixed armour region', () => {
  it('declares nothing but an identity and the editor’s initial kind', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    expect(record(document())).toEqual({
      id: 'fixed_armour_1', kind: 'belt_main', system_id: null, item_id: null, source: '',
      thickness_mm: null, length_m: null, height_m: null,
    });
    // A belt's own extents are absent rather than zero: an unknown extent is
    // never read as a zero extent, and nothing is clamped or filled in.
    expect(record(document()).length_m).toBeNull();
    expect(record(document()).height_m).toBeNull();
  });

  it('gives every region its own identifier, even after one is deleted', () => {
    const first = newFixedArmour([]);
    const second = newFixedArmour([first]);
    expect([first.id, second.id]).toEqual(['fixed_armour_1', 'fixed_armour_2']);
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    fireEvent.click(within(regionPanel('fixed_armour_2'))
      .getByRole('button', { name: copy('concept.fixedArmour.remove') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    // A new identifier is never one another record already holds, so the third
    // region cannot inherit the identifier the deleted second one left behind.
    expect(fixedArmour(config(document())).map(row => row.id))
      .toEqual(['fixed_armour_1', 'fixed_armour_3', 'fixed_armour_4']);
  });

  it('refuses a fifty-first region instead of writing one the server would reject', () => {
    const project = enabledProject();
    const declared = config(project);
    const records: Record<string, unknown>[] = [];
    for (let index = 0; index < MAX_FIXED_ARMOUR_RECORDS; index += 1) records.push(newFixedArmour(records));
    declared.fixed_armour = records;
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const add = screen.getByRole('button', { name: copy('concept.fixedArmour.add') });
    expect(add).toBeDisabled();
    expect(screen.getByText(copy('concept.fixedArmour.max',
      { count: MAX_FIXED_ARMOUR_RECORDS }))).toBeVisible();
    fireEvent.click(add);
    expect(fixedArmour(config(document()))).toHaveLength(MAX_FIXED_ARMOUR_RECORDS);
  });

  it('deletes a region and leaves the battery rows, the ledger and every mass alone', () => {
    const project = enabledProject();
    const declared = config(project);
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'conning',
      system_id: 'armour.fixed', item_id: 'weapons.conning', thickness_mm: 300, aft_mm: 200 }];
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const before = document();
    fireEvent.click(within(regionPanel('fixed_armour_1'))
      .getByRole('button', { name: copy('concept.fixedArmour.remove') }));
    expect(fixedArmour(config(document()))).toEqual([]);
    expect(config(document()).batteries).toEqual(config(before).batteries);
    // The adopted mass is a ledger fact and survives the declaration.
    expect((document() as Record<string, any>).weight_groups).toEqual((before as Record<string, any>).weight_groups);
  });
});

describe('the recovered regions keep their own identity', () => {
  it('keeps the identifier, the source and the binding when the kind changes', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    const panel = (id: string) => regionPanel(id);
    fireEvent.change(within(panel('fixed_armour_1'))
      .getByLabelText(copy('concept.fixedArmour.id')), { target: { value: 'main_belt' } });
    fireEvent.change(within(panel('main_belt'))
      .getByLabelText(copy('concept.fixedArmour.source')),
      { target: { value: 'the recovered armour plan' } });
    fireEvent.change(within(panel('main_belt'))
      .getByLabelText(copy('concept.fixedArmour.system')), { target: { value: 'armour.fixed' } });
    fireEvent.change(within(panel('main_belt'))
      .getByLabelText(copy('concept.fixedArmour.item')),
      { target: { value: 'weapons.main_belt' } });
    fireEvent.change(within(panel('main_belt'))
      .getByLabelText(copy('concept.fixedArmour.kind')), { target: { value: 'bulge' } });
    const row = record(document());
    expect(row.id).toBe('main_belt');
    expect(row.source).toBe('the recovered armour plan');
    expect(row.kind).toBe('bulge');
    expect(row.system_id).toBe('armour.fixed');
    expect(row.item_id).toBe('weapons.main_belt');
  });

  it('drops the geometry the new region does not have, and never adopts a value', () => {
    const declared = config(enabledProject());
    const deck = { ...newFixedArmour([]), kind: 'deck', thickness_mm: 100,
      coverage_index: 4, forecastle_fraction: 0.26, quarterdeck_fraction: 0.2,
      forecastle_mm: 80, quarterdeck_mm: 60, length_m: 90, height_m: 4 };
    const conning = changeFixedArmourKind(deck, 'conning');
    // A conning tower has a fore and an aft plate, and no declared length, height,
    // coverage selector or fractional deck extent at all.
    expect(conning).toEqual({ id: 'fixed_armour_1', kind: 'conning', system_id: null,
      item_id: null, source: '', thickness_mm: 100, aft_mm: null });
    // The declared central thickness is the same field, not a carried-over value:
    // nothing was moved from the deck's own aft deck reading into the tower.
    expect(conning.thickness_mm).toBe(100);
    expect(conning.aft_mm).toBeNull();

    const mainBelt = changeFixedArmourKind(deck, 'belt_main');
    expect(mainBelt).toEqual({ id: 'fixed_armour_1', kind: 'belt_main', system_id: null,
      item_id: null, source: '', thickness_mm: 100, length_m: null, height_m: null });
    // The deck's own selector, its fractions and its regional thicknesses are
    // gone: a belt has no coverage choice. And a stray length on the deck record
    // cannot silently become the belt's declared length.
    expect('coverage_index' in mainBelt).toBe(false);
    expect('forecastle_mm' in mainBelt).toBe(false);
    expect('quarterdeck_fraction' in mainBelt).toBe(false);
  });

  it('keeps a shared plate thickness across two planar regions', () => {
    const belt = { ...newFixedArmour([]), kind: 'belt_main', thickness_mm: 150,
      length_m: 96, height_m: 4.5 };
    const bulkhead = changeFixedArmourKind(belt, 'bulkhead');
    // Both planar kinds declare the same three fields, so all three keep their own
    // declared values: nothing is moved and nothing is invented.
    expect(bulkhead).toEqual({ id: 'fixed_armour_1', kind: 'bulkhead', system_id: null,
      item_id: null, source: '', thickness_mm: 150, length_m: 96, height_m: 4.5 });
    // A declared zero stays a declared zero across a kind change.
    expect(changeFixedArmourKind({ ...belt, thickness_mm: 0 }, 'bulkhead').thickness_mm).toBe(0);
    // An unknown thickness stays unknown through a kind change too.
    const unknown = changeFixedArmourKind({ ...newFixedArmour([]), kind: 'belt_main' }, 'bulkhead');
    expect(unknown.thickness_mm).toBeNull();
    expect(unknown.length_m).toBeNull();
  });

  it('keeps every declared field when the kind changes back and forth', () => {
    const declared = config(enabledProject());
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'belt_main', thickness_mm: 150,
      length_m: 96, height_m: 4.5, source: 'plan sheet 4' }];
    const other = changeFixedArmourKind(declared.fixed_armour[0], 'bulkhead');
    // Two planar regions share the same three fields, so a round trip is lossless.
    expect(other).toMatchObject({ kind: 'bulkhead', thickness_mm: 150, length_m: 96, height_m: 4.5 });
    const roundTrip = changeFixedArmourKind(other, 'belt_main');
    expect(roundTrip).toEqual({ id: 'fixed_armour_1', kind: 'belt_main', system_id: null,
      item_id: null, source: 'plan sheet 4', thickness_mm: 150, length_m: 96, height_m: 4.5 });
  });

  it('treats an undeclared kind as no region at all rather than a default', () => {
    const declared = config(enabledProject());
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'bulkhead', thickness_mm: 150 }];
    const cleared = changeFixedArmourKind(declared.fixed_armour[0], 'belt_main');
    const without = patchFixedArmour(declared, 0, { kind: null });
    expect(fixedArmourRole(fixedArmour(without)[0])).toBeNull();
    expect(fixedArmourRole(cleared)).toBe('belt_main');
    // A region with no kind claims no role and no target, so the battery row's own
    // three bindings are all that is left — nothing was invented for it.
    expect(componentBindings(without)).toEqual({ 'weapons.guns': 'guns',
      'weapons.mounts': 'mounts', 'weapons.ammunition': 'ammunition' });
  });

  it('drops the previous geometry on screen too, not only in the helper', () => {
    const declared = config(enabledProject());
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'belt_main', thickness_mm: 150,
      length_m: 96, height_m: 4.5, system_id: 'armour.fixed', item_id: 'weapons.main_belt' }];
    const { document } = mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    fireEvent.change(within(regionPanel('fixed_armour_1'))
      .getByLabelText(copy('concept.fixedArmour.kind')), { target: { value: 'conning' } });
    // The merged record would still be carrying the belt's own extents; the
    // replaced one declares exactly what a conning tower has.
    expect(record(document())).toEqual({ id: 'fixed_armour_1', kind: 'conning',
      system_id: 'armour.fixed', item_id: 'weapons.main_belt', source: '',
      thickness_mm: 150, aft_mm: null });
    expect(within(regionPanel('fixed_armour_1'))
      .queryByLabelText(copy('concept.fixedArmour.height'))).toBeNull();
  });
});

describe('declared geometry, units and unknowns', () => {
  function deckProject(): ProjectDocument {
    const declared = config(enabledProject());
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'deck' }];
    return { ...enabledProject(), concept_design: declared } as ProjectDocument;
  }

  it('stores a plate thickness in millimetres whatever unit the reader sees', () => {
    const { document } = mount(enabledProject(), { length: 'ft' });
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    const panel = () => regionPanel('fixed_armour_1');
    expect(within(panel()).getByLabelText(copy('concept.fixedArmour.thickness'))
      .closest('.field-label')?.textContent).toContain('ft');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.thickness')),
      { target: { value: '0.984251968503937' } });
    expect(record(document()).thickness_mm).toBeCloseTo(300, 6);
    // A declared zero stays a declared zero and is never confused with unknown.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.thickness')),
      { target: { value: '0' } });
    expect(record(document()).thickness_mm).toBe(0);
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.thickness')),
      { target: { value: '' } });
    expect(record(document()).thickness_mm).toBeNull();
  });

  it('stores the declared extents in metres and keeps a cleared one unknown', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    const panel = () => regionPanel('fixed_armour_1');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.length')),
      { target: { value: '96' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.height')),
      { target: { value: '4.5' } });
    expect(record(document())).toMatchObject({ length_m: 96, height_m: 4.5 });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.height')),
      { target: { value: '' } });
    expect(record(document()).height_m).toBeNull();
  });

  it('offers the recovered seven-way deck coverage as its own names', () => {
    const { document } = mount(deckProject());
    const panel = () => regionPanel('fixed_armour_1');
    const coverage = within(panel())
      .getByLabelText(copy('concept.fixedArmour.coverage')) as HTMLSelectElement;
    expect([...coverage.options].map(option => option.value)).toEqual(['', '0', '1', '2', '3', '4', '5', '6']);
    // The recovered names, not indices: a box over machinery is not selector 4.
    const box = [...coverage.options].find(option => option.value === '4');
    expect(box?.textContent).toMatch(/machinery/i);
    expect(box?.textContent).not.toBe('4');
    expect(coverage).toHaveValue('');
    fireEvent.change(coverage, { target: { value: '6' } });
    expect(record(document()).coverage_index).toBe(6);
    // A cleared selector stays unknown; it is never inferred as selector 0.
    fireEvent.change(coverage, { target: { value: '' } });
    expect(record(document()).coverage_index).toBeNull();
  });

  it('keeps the deck fractions as fractions and the thicknesses in millimetres', () => {
    const { document } = mount(deckProject());
    const panel = () => regionPanel('fixed_armour_1');
    // The reader's preferred length unit is metres, and the project keeps
    // millimetres: 0.08 m typed is 80 mm stored, not 0.08 mm.
    expect(within(panel()).getByLabelText(copy('concept.fixedArmour.forecastleThickness'))
      .closest('.field-label')?.textContent).toContain('m');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.forecastleFraction')),
      { target: { value: '0.26' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.quarterdeckFraction')),
      { target: { value: '0.2' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.forecastleThickness')),
      { target: { value: '0.08' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.quarterdeckThickness')),
      { target: { value: '0.06' } });
    expect(record(document())).toMatchObject({ forecastle_fraction: 0.26,
      quarterdeck_fraction: 0.2, forecastle_mm: 80, quarterdeck_mm: 60 });
    // An out-of-domain fraction is kept as typed: nothing is clamped to the domain.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.forecastleFraction')),
      { target: { value: '1.4' } });
    expect(record(document()).forecastle_fraction).toBe(1.4);
    // A cleared thickness is unknown again, never a zero deck.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.forecastleThickness')),
      { target: { value: '' } });
    expect(record(document()).forecastle_mm).toBeNull();
  });

  it('declares the conning tower as a fore and an aft plate, and nothing else', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    fireEvent.change(within(regionPanel('fixed_armour_1'))
      .getByLabelText(copy('concept.fixedArmour.kind')), { target: { value: 'conning' } });
    const panel = () => regionPanel('fixed_armour_1');
    // No tower extent is ever asked for: the original infers no height, width or
    // position, and this screen must not ask the reader to invent one either.
    expect(within(panel()).queryByLabelText(copy('concept.fixedArmour.height'))).toBeNull();
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.foreThickness')),
      { target: { value: '0.3' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.fixedArmour.aftThickness')),
      { target: { value: '0.2' } });
    expect(record(document())).toEqual({ id: 'fixed_armour_1', kind: 'conning',
      system_id: null, item_id: null, source: '', thickness_mm: 300, aft_mm: 200 });
  });

  it('names the two doubled plate regions and never the taper terms as fields', () => {
    const declared = config(enabledProject());
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'belt_ends', thickness_mm: 100,
      length_m: 6, height_m: 4 }];
    mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    const panel = regionPanel('fixed_armour_1');
    expect(within(panel).getByText(copy('concept.fixedArmour.bulkheadHint'))).toBeVisible();
    // The recovered taper term reads the hull, and is the server's business.
    expect(within(panel).queryByText(/taper/i)).toBeNull();
  });
});

describe('one ledger item, one component', () => {
  function boundProject(): ProjectDocument {
    const declared = config(enabledProject());
    const layout = newBatteryLayout([]);
    layout.group1 = { battery_id: 'main', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    layout.armour = { system_id: 'weapons.main', item_id: 'weapons.layout_armour',
      face_mm: 150, rear_roof_mm: 100, barbette_mm: 75 };
    declared.battery_layouts = [layout];
    declared.fixed_armour = [{ ...newFixedArmour([]), kind: 'belt_main',
      system_id: 'armour.fixed', item_id: 'weapons.main_belt', thickness_mm: 150 }];
    return { ...enabledProject(), concept_design: declared } as ProjectDocument;
  }

  it('offers only items the chosen system owns and nothing else has claimed', () => {
    const { document } = mount(boundProject());
    const panel = () => regionPanel('fixed_armour_1');
    const picker = within(panel())
      .getByLabelText(copy('concept.fixedArmour.item')) as HTMLSelectElement;
    const options = [...picker.options].map(option => option.value);
    expect(options).toContain('weapons.main_belt');
    expect(options).toContain('weapons.bulge');
    expect(options).toContain('weapons.conning');
    // The layout's complete two-group armour and the row's own three targets are
    // never offered: one target under two components is refused by the contract.
    expect(options).not.toContain('weapons.layout_armour');
    expect(options).not.toContain('weapons.guns');
    expect(options).not.toContain('weapons.mounts');
    expect(options).not.toContain('weapons.ammunition');
    expect(options).not.toContain('hull.structure');
    expect(claimedTargetIds(config(document()))).toContain('weapons.layout_armour');
  });

  it('clears only this binding when the owning system changes', () => {
    const { document } = mount(boundProject());
    fireEvent.change(within(regionPanel('fixed_armour_1'))
      .getByLabelText(copy('concept.fixedArmour.system')),
      { target: { value: 'weapons.main' } });
    const row = record(document());
    expect(row.system_id).toBe('weapons.main');
    expect(row.item_id).toBeNull();
    // Nothing else moved with it: the layout's own binding and the row's.
    expect(config(document()).battery_layouts[0].armour.item_id).toBe('weapons.layout_armour');
    expect(config(document()).batteries[0].mounts_item_id).toBe('weapons.mounts');
  });

  it('names the recovered role each region’s own target must carry', () => {
    const base = config(boundProject());
    expect(componentBindings(base)['weapons.main_belt']).toBe('belt_main');
    expect(mismatchedRoles(base)).toContain('weapons.main_belt');
    const withRole = { ...base, balance: { ...base.balance,
      roles: { ...base.balance.roles, 'weapons.main_belt': 'belt_main' } } };
    expect(mismatchedRoles(withRole)).not.toContain('weapons.main_belt');

    // All seven keep their own recovered role, and none of them is a rotating one.
    for (const [kind, role] of Object.entries(FIXED_ARMOUR_ROLE_BY_KIND)) {
      const one = { ...base, fixed_armour: [{ ...newFixedArmour([]), kind, item_id: 'weapons.conning' }] };
      expect(componentBindings(one)['weapons.conning'], kind).toBe(role);
    }
    expect(Object.values(FIXED_ARMOUR_ROLE_BY_KIND)).not.toContain('rotating_armour');
  });

  it('says so when two regions name one item, and removes nothing', () => {
    const declared = config(boundProject());
    declared.fixed_armour = [
      { ...newFixedArmour([]), kind: 'belt_main', system_id: 'armour.fixed',
        item_id: 'weapons.conning', thickness_mm: 150 },
      { ...newFixedArmour([]), kind: 'conning', system_id: 'armour.fixed',
        item_id: 'weapons.conning', aft_mm: 200 },
    ];
    const { document } = mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect(fixedArmourTargetConflicts(declared)).toEqual(['weapons.conning']);
    expect(duplicateTargets(declared)).toEqual(['weapons.conning']);
    // Both declarations and both masses are still there for the reader to decide.
    // One notice on the section names the colliding item once, and each of the two
    // rows names it again where the reader is editing.
    expect(screen.getAllByText(copy('concept.fixedArmour.targetConflict',
      { item: 'weapons.conning' })).length).toBe(3);
    expect(fixedArmour(config(document()))).toHaveLength(2);
  });

  it('keeps one identifier out of two records, and names the duplicate', () => {
    const declared = config(enabledProject());
    declared.fixed_armour = [
      { ...newFixedArmour([]), id: 'belt' },
      { ...newFixedArmour([]), id: 'belt' },
    ];
    expect(duplicateFixedArmourIds(declared)).toEqual(['belt']);
    mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect(screen.getAllByText(copy('concept.fixedArmour.duplicateId', { id: 'belt' })).length).toBe(2);
  });

  it('marks an identifier the contract would refuse, without rewriting it', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.fixedArmour.add') }));
    fireEvent.change(within(regionPanel('fixed_armour_1'))
      .getByLabelText(copy('concept.fixedArmour.id')), { target: { value: 'a b' } });
    expect(record(document()).id).toBe('a b');
    expect(screen.getByText(copy('concept.fixedArmour.invalidId'))).toBeVisible();
  });
});

describe('the language of the fixed armour section', () => {
  it('keeps English and Chinese words for every label it prints', () => {
    const keys: ConceptKey[] = ['concept.group.fixedArmour', 'concept.fixedArmour.note',
      'concept.fixedArmour.add', 'concept.fixedArmour.remove', 'concept.fixedArmour.max',
      'concept.fixedArmour.id', 'concept.fixedArmour.source', 'concept.fixedArmour.kind',
      'concept.fixedArmour.system', 'concept.fixedArmour.item', 'concept.fixedArmour.roleHint',
      'concept.fixedArmour.thickness', 'concept.fixedArmour.length', 'concept.fixedArmour.height',
      'concept.fixedArmour.foreThickness', 'concept.fixedArmour.aftThickness',
      'concept.fixedArmour.coverage', 'concept.fixedArmour.forecastleFraction',
      'concept.fixedArmour.quarterdeckFraction', 'concept.fixedArmour.forecastleThickness',
      'concept.fixedArmour.quarterdeckThickness', 'concept.fixedArmour.bulkheadHint',
      'concept.fixedArmour.conningHint', 'concept.fixedArmour.duplicateId',
      'concept.fixedArmour.invalidId', 'concept.fixedArmour.targetConflict',
      'concept.fixedArmour.separate', 'concept.fixedArmour.unownedHint',
      'balance.fixedArmour.title', 'balance.fixedArmour.method',
      'balance.fixedArmour.metric.central', 'balance.fixedArmour.metric.foreTower'];
    for (let index = 0; index < 7; index += 1) {
      keys.push(`concept.fixedArmour.coverage.${index}` as ConceptKey);
      keys.push(`concept.fixedArmour.kind.${['belt_main', 'belt_upper', 'belt_ends',
        'bulkhead', 'bulge', 'deck', 'conning'][index]}` as ConceptKey);
    }
    for (const key of keys) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });
});

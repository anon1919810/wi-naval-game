import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import {
  auxiliaryWeaponIdValid, auxiliaryWeaponKind, auxiliaryWeaponLocationCount,
  auxiliaryWeaponRole, auxiliaryWeaponTargetConflicts, auxiliaryWeapons,
  AUXILIARY_WEAPON_FIELDS_BY_KIND, AUXILIARY_WEAPON_LOCATION_KEYS, AUXILIARY_WEAPON_ROLE,
  changeAuxiliaryWeaponKind, claimedTargetIds, componentBindings, componentTargetClaims,
  duplicateAuxiliaryWeaponIds, duplicateTargets, MAX_AUXILIARY_WEAPONS, mismatchedRoles,
  newAuxiliaryWeapon, newBattery, newBatteryLayout, newConcept, patchBattery,
  removeAuxiliaryWeapon,
} from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { object } from '../components/formModel';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import * as api from '../api';
import type { ProjectDocument } from '../types';

// The recovered auxiliary weapons are ordinary project input here, so every
// assertion is about what the *document* ends up holding after a real event.
// Nothing in this suite knows the recovered torpedo or mine expression: a mass is
// the server's, and this editor's whole duty is to keep an unknown unknown, keep
// the three families distinct, keep `loads` meaning what its own family means,
// and never invent a target, a location or a mass.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const LEDGER = {
  id: 'weights', label: 'declared concept design',
  items: [
    { id: 'hull.structure', mass_t: 2213.763, x_m: 82 },
    { id: 'hull.adjustable', mass_t: 120.0, x_m: 82 },
    { id: 'weapons.guns', mass_t: 60.9628, x_m: 104 },
    { id: 'weapons.mounts', mass_t: 152.407, x_m: 104 },
    { id: 'weapons.ammunition', mass_t: 45.7221, x_m: 92 },
    { id: 'weapons.gun_house_armour', mass_t: 40.0, x_m: 104 },
    { id: 'weapons.layout_armour', mass_t: 0, x_m: 104 },
    { id: 'weapons.main_belt', mass_t: 0, x_m: 104 },
    { id: 'aux.torpedo_main', mass_t: 0, x_m: 100 },
    { id: 'aux.mine_rack', mass_t: 0, x_m: 60 },
    { id: 'aux.dc_main', mass_t: 0, x_m: 40 },
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure', 'hull.adjustable'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts',
    'weapons.ammunition', 'weapons.gun_house_armour', 'weapons.layout_armour',
    'weapons.main_belt'] } },
  armour: { fixed: { weight_item_ids: ['weapons.main_belt'] } },
  auxiliary: { weapons: { weight_item_ids: ['aux.torpedo_main', 'aux.mine_rack',
    'aux.dc_main'] } },
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

function enabledProject(): ProjectDocument {
  const declared = newConcept();
  declared.source = 'a declared study design';
  declared.batteries = [{
    ...newBattery([]), id: 'main', system_id: 'weapons.main',
    guns_item_id: 'weapons.guns', mounts_item_id: 'weapons.mounts',
    ammunition_item_id: 'weapons.ammunition',
    calibre_mm: 152.4, barrel_calibres: 45, year: 1918,
    gun_type: 'breech_loading', mount_type: 'deck_hoist',
    mount_count: 4, barrels_per_mount: 2, rounds_per_gun: 120,
  }];
  declared.machinery = { system_id: 'propulsion.machinery', item_id: 'propulsion.machinery',
    year: 1918, kind: 'turbine', coal_pct: null, speed_kn: 25, shaft_power_kw: null };
  declared.fuel = { system_id: 'propulsion.fuel', item_id: 'propulsion.fuel' };
  declared.balance = { ...object(declared.balance), structure_item_id: 'hull.adjustable' };
  return { ...baseProject(), concept_design: declared } as ProjectDocument;
}

function mount(initial: ProjectDocument, preferences: unknown = null) {
  cleanup();
  const written: ProjectDocument[] = [];
  function Harness() {
    const [draft, setDraft] = useState(initial);
    return <UnitProvider preferences={preferences}>
      <ConceptDesignEditor project={draft}
        onChange={next => { setDraft(next); written.push(next); }} />
    </UnitProvider>;
  }
  render(<Harness />);
  return { document: () => written[written.length - 1] ?? initial };
}

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);
const copyZh = (key: ConceptKey) => conceptCopy('zh-CN', key);
const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;
const record = (document: unknown, index = 0): Record<string, any> =>
  auxiliaryWeapons(config(document))[index];

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

describe('adding an auxiliary weapon', () => {
  it('declares nothing but an identity and the editor’s initial family', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    // Every count, reload, location, diameter and length is an explicit unknown:
    // the recovered expressions treat a declared zero as a determined zero, so a
    // filled-in default would be a different fact and not a kinder one.
    expect(record(document())).toEqual({ id: 'auxiliary_1', kind: 'torpedo',
      system_id: null, item_id: null, source: '',
      count: null, loads: null, location_index: null, diameter_mm: null, length_m: null });
    expect(auxiliaryWeapons(config(document()))).toHaveLength(1);
  });

  it('gives every declaration its own identifier, even after one is deleted', () => {
    expect(newAuxiliaryWeapon([]).id).toBe('auxiliary_1');
    expect(newAuxiliaryWeapon([{ id: 'auxiliary_1' }]).id).toBe('auxiliary_2');
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    fireEvent.click(within(regionPanel('auxiliary_2'))
      .getByRole('button', { name: copy('concept.auxiliary.remove') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    expect(auxiliaryWeapons(config(document())).map(row => row.id))
      .toEqual(['auxiliary_1', 'auxiliary_3', 'auxiliary_4']);
  });

  it('refuses a fifty-first declaration instead of writing one the server would reject', () => {
    const project = enabledProject();
    const declared = config(project);
    const records: Record<string, unknown>[] = [];
    for (let index = 0; index < MAX_AUXILIARY_WEAPONS; index += 1) {
      records.push(newAuxiliaryWeapon(records));
    }
    declared.auxiliary_weapons = records;
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const add = screen.getByRole('button', { name: copy('concept.auxiliary.add') });
    expect(add).toBeDisabled();
    expect(screen.getByText(copy('concept.auxiliary.max',
      { count: MAX_AUXILIARY_WEAPONS }))).toBeVisible();
    fireEvent.click(add);
    expect(auxiliaryWeapons(config(document()))).toHaveLength(MAX_AUXILIARY_WEAPONS);
  });

  it('deletes a declaration and leaves every other component and mass alone', () => {
    const project = enabledProject();
    const declared = config(project);
    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'mine',
      system_id: 'auxiliary.weapons', item_id: 'aux.mine_rack', count: 24, loads: 6,
      location_index: 2, unit_mass_kg: 1200 }];
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const before = document();
    fireEvent.click(within(regionPanel('auxiliary_1'))
      .getByRole('button', { name: copy('concept.auxiliary.remove') }));
    expect(auxiliaryWeapons(config(document()))).toEqual([]);
    expect(config(document()).batteries).toEqual(config(before).batteries);
    expect(config(document()).balance).toEqual(config(before).balance);
    // The adopted mass is a ledger fact and survives the declaration.
    expect((document() as Record<string, any>).weight_groups)
      .toEqual((before as Record<string, any>).weight_groups);
  });

  it('is absent from a project that never enabled it', () => {
    const { document } = mount(enabledProject());
    expect(auxiliaryWeapons(config(document()))).toEqual([]);
    expect('auxiliary_weapons' in config(document())).toBe(false);
  });
});

describe('the three families keep their own fields', () => {
  function torpedoProject(): ProjectDocument {
    const declared = config(enabledProject());
    declared.auxiliary_weapons = [{
      ...newAuxiliaryWeapon([]), kind: 'torpedo', count: 6, loads: 2, location_index: 4,
      diameter_mm: 533.4, length_m: 7.62, source: 'the recovered torpedo plan',
      system_id: 'auxiliary.weapons', item_id: 'aux.torpedo_main',
    }];
    return { ...enabledProject(), concept_design: declared } as ProjectDocument;
  }

  it('declares a torpedo as a diameter, a length, a count and a location', () => {
    const { document } = mount(torpedoProject());
    const panel = () => regionPanel('auxiliary_1');
    expect(within(panel()).getByLabelText(copy('concept.auxiliary.diameter'))).toBeVisible();
    expect(within(panel()).getByLabelText(copy('concept.auxiliary.length'))).toBeVisible();
    // A torpedo has no whole-unit mass: that is the other two families' field.
    expect(within(panel()).queryByLabelText(copy('concept.auxiliary.unitMass'))).toBeNull();
    expect(record(document())).toMatchObject({ diameter_mm: 533.4, length_m: 7.62,
      count: 6, loads: 2, location_index: 4 });
  });

  it('declares a mine as a whole-unit mass and never as a length', () => {
    const project = torpedoProject();
    const { document } = mount(project);
    fireEvent.change(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.kind')), { target: { value: 'mine' } });
    const panel = () => regionPanel('auxiliary_1');
    expect(within(panel()).getByLabelText(copy('concept.auxiliary.unitMass'))).toBeVisible();
    expect(within(panel()).queryByLabelText(copy('concept.auxiliary.diameter'))).toBeNull();
    expect(within(panel()).queryByLabelText(copy('concept.auxiliary.length'))).toBeNull();
    // A mine's whole-unit mass is never derived from the torpedo's diameter, and
    // the identity, source and binding survive the change untouched.
    expect(record(document())).toEqual({ id: 'auxiliary_1', kind: 'mine',
      system_id: 'auxiliary.weapons', item_id: 'aux.torpedo_main',
      source: 'the recovered torpedo plan',
      count: 6, loads: null, location_index: null, unit_mass_kg: null });
  });

  it('clears the location on a kind change rather than adopting the index', () => {
    // Torpedo location 4 and mine location 4 are different places with different
    // recovered mount factors, so a carried index would be an adopted one.
    const torpedo = changeAuxiliaryWeaponKind({ ...newAuxiliaryWeapon([]), location_index: 4,
      count: 2 }, 'torpedo');
    const mine = changeAuxiliaryWeaponKind(torpedo, 'mine');
    expect(torpedo.location_index).toBe(4);
    expect(mine.location_index).toBeNull();
    // The counts the two families do share are the reader's own and survive.
    expect(mine.count).toBe(2);
  });

  it('preserves full unit mass and reloads between the two store families', () => {
    const mine = { id: 'stores', kind: 'mine', count: 12, loads: 6,
      unit_mass_kg: 500, location_index: 1 };
    const depthCharge = changeAuxiliaryWeaponKind(mine, 'depth_charge');
    expect(depthCharge).toMatchObject({ count: 12, loads: 6, unit_mass_kg: 500, location_index: null });
    expect(changeAuxiliaryWeaponKind(depthCharge, 'mine'))
      .toMatchObject({ count: 12, loads: 6, unit_mass_kg: 500, location_index: null });
  });

  it('clears every engineering field when the family is undeclared', () => {
    const declared = config(enabledProject());
    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'mine', count: 12,
      unit_mass_kg: 900 }];
    const { document } = mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    fireEvent.change(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.kind')), { target: { value: '' } });
    expect(record(document())).toEqual({ id: 'auxiliary_1', kind: null,
      system_id: null, item_id: null, source: '',
      count: null, loads: null, location_index: null, unit_mass_kg: null,
      diameter_mm: null, length_m: null });
    // No family means no component, so no role and no target claim either.
    expect(auxiliaryWeaponRole(record(document()))).toBeNull();
    expect(componentBindings(withoutAux(config(document())))).not.toHaveProperty('aux.mine_rack');
  });

  it('declares exactly the fields its family has and nothing else', () => {
    expect(AUXILIARY_WEAPON_FIELDS_BY_KIND.torpedo)
      .toEqual(['count', 'loads', 'location_index', 'diameter_mm', 'length_m']);
    expect(AUXILIARY_WEAPON_FIELDS_BY_KIND.mine)
      .toEqual(['count', 'loads', 'location_index', 'unit_mass_kg']);
    expect(AUXILIARY_WEAPON_FIELDS_BY_KIND.depth_charge)
      .toEqual(AUXILIARY_WEAPON_FIELDS_BY_KIND.mine);
  });
});

describe('declared counts, units and unknowns', () => {
  function mineProject(): ProjectDocument {
    const declared = config(enabledProject());
    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'mine' }];
    return { ...enabledProject(), concept_design: declared } as ProjectDocument;
  }

  it('stores a whole-unit mass in kilograms whatever unit the reader sees', () => {
    const { document } = mount(mineProject(), { mass: 't' });
    const panel = () => regionPanel('auxiliary_1');
    expect(within(panel()).getByLabelText(copy('concept.auxiliary.unitMass'))
      .closest('.field-label')?.textContent).toContain('t');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.unitMass')),
      { target: { value: '1.2' } });
    expect(record(document()).unit_mass_kg).toBeCloseTo(1200, 6);
    // A declared zero is a determined zero, not a missing unit mass.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.unitMass')),
      { target: { value: '0' } });
    expect(record(document()).unit_mass_kg).toBe(0);
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.unitMass')),
      { target: { value: '' } });
    expect(record(document()).unit_mass_kg).toBeNull();
  });

  it('stores a torpedo diameter in millimetres and its length in metres', () => {
    const project = mineProject();
    const declared = config(project);
    declared.auxiliary_weapons[0] = { ...declared.auxiliary_weapons[0], kind: 'torpedo' };
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const panel = () => regionPanel('auxiliary_1');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.diameter')),
      { target: { value: '0.5334' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.length')),
      { target: { value: '7.62' } });
    expect(record(document())).toMatchObject({ diameter_mm: 533.4, length_m: 7.62 });
  });

  it('keeps the counts as typed and a cleared one unknown', () => {
    const { document } = mount(mineProject());
    const panel = () => regionPanel('auxiliary_1');
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.count')),
      { target: { value: '24' } });
    fireEvent.change(within(panel())
      .getByLabelText(copy('concept.auxiliary.loads.reload')), { target: { value: '6' } });
    expect(record(document())).toMatchObject({ count: 24, loads: 6 });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.auxiliary.count')),
      { target: { value: '' } });
    expect(record(document()).count).toBeNull();
    expect(record(document()).loads).toBe(6);
    // A fractional count is kept as typed and marked, never truncated for the reader.
    const count = within(panel()).getByLabelText(copy('concept.auxiliary.count'));
    fireEvent.change(count, { target: { value: '2.5' } });
    expect(record(document()).count).toBe(2.5);
    expect(count).toHaveAttribute('aria-invalid', 'true');
  });

  it('never rewrites a declared zero reload into a one', () => {
    const { document } = mount(mineProject());
    const panel = () => regionPanel('auxiliary_1');
    fireEvent.change(within(panel())
      .getByLabelText(copy('concept.auxiliary.loads.reload')), { target: { value: '0' } });
    // The recovered form substitutes a one inside its own area calculation; that
    // is an area detail and must never rewrite the declared input.
    expect(record(document()).loads).toBe(0);
  });

  it('labels `loads` by what it means in each family', () => {
    expect(copy('concept.auxiliary.loads.torpedo')).toBe('Torpedo sets');
    expect(copyZh('concept.auxiliary.loads.torpedo')).toBe('鱼雷组数');
    const { document } = mount(mineProject());
    expect(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.loads.reload'))).toBeVisible();
    const declared = config(document());
    declared.auxiliary_weapons[0] = { ...declared.auxiliary_weapons[0], kind: 'torpedo' };
    mount({ ...(document() as ProjectDocument), concept_design: declared } as ProjectDocument);
    expect(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.loads.torpedo'))).toBeVisible();
    expect(screen.queryByLabelText(copy('concept.auxiliary.loads.reload'))).toBeNull();
    // The two are different quantities of the same field, and each says so.
    expect(copy('concept.auxiliary.loads.torpedoHint')).toMatch(/not a weight multiplier/i);
    expect(copy('concept.auxiliary.loads.reloadHint')).toMatch(/never a charge weight/i);
  });

  it('offers the recovered location choices as their own names, per family', () => {
    expect(auxiliaryWeaponLocationCount('torpedo')).toBe(9);
    expect(auxiliaryWeaponLocationCount('mine')).toBe(4);
    expect(auxiliaryWeaponLocationCount('depth_charge')).toBe(4);
    const project = mineProject();
    const declared = config(project);
    const { document } = mount({ ...project, concept_design: declared } as ProjectDocument);
    const picker = (id: string) => within(regionPanel(id))
      .getByLabelText(copy('concept.auxiliary.location')) as HTMLSelectElement;
    const mineOptions = [...picker('auxiliary_1').options].map(option => option.value);
    expect(mineOptions).toEqual(['', '0', '1', '2', '3']);
    const rack = [...picker('auxiliary_1').options].find(option => option.value === '0');
    expect(rack?.textContent).not.toBe('0');
    expect(rack?.textContent).toMatch(/stern/i);
    expect(picker('auxiliary_1')).toHaveValue('');
    fireEvent.change(picker('auxiliary_1'), { target: { value: '2' } });
    expect(record(document()).location_index).toBe(2);
    // A cleared location stays unknown: a positive weapon at an unknown location
    // cannot produce a complete estimate, and this screen must not pick one.
    fireEvent.change(picker('auxiliary_1'), { target: { value: '' } });
    expect(record(document()).location_index).toBeNull();

    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'torpedo' }];
    mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect([...picker('auxiliary_1').options].map(option => option.value))
      .toEqual(['', '0', '1', '2', '3', '4', '5', '6', '7', '8']);
    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'depth_charge' }];
    mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect([...picker('auxiliary_1').options].map(option => option.value))
      .toEqual(['', '0', '1', '2', '3']);
    const mortar = [...picker('auxiliary_1').options].find(option => option.value === '2');
    expect(mortar?.textContent).toMatch(/hedgehog/i);
  });
});

describe('one ledger item, one component', () => {
  function boundProject(): ProjectDocument {
    const project = enabledProject();
    const declared = config(project);
    const layout = newBatteryLayout([]);
    layout.group1 = { battery_id: 'main', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    layout.armour = { system_id: 'weapons.main', item_id: 'weapons.layout_armour',
      face_mm: 150, rear_roof_mm: 100, barbette_mm: 75 };
    declared.battery_layouts = [layout];
    declared.batteries = patchBattery(declared, 0,
      { armour: { system_id: 'weapons.main', item_id: 'weapons.gun_house_armour',
        face_mm: 150, rear_roof_mm: 100, barbette_mm: 75, freeboard_m: 4.6,
        super_factor: 1 } }).batteries as any;
    declared.balance.structure_item_id = 'hull.adjustable';
    declared.auxiliary_weapons = [{
      ...newAuxiliaryWeapon([]), kind: 'torpedo', system_id: 'auxiliary.weapons',
      item_id: 'aux.torpedo_main', count: 4,
    }];
    return { ...project, concept_design: declared } as ProjectDocument;
  }

  it('offers only items the chosen system owns and nothing else has claimed', () => {
    const { document } = mount(boundProject());
    const picker = within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.item')) as HTMLSelectElement;
    const options = [...picker.options].map(option => option.value);
    expect(options).toContain('aux.torpedo_main');
    expect(options).toContain('aux.mine_rack');
    expect(options).toContain('aux.dc_main');
    // The global claim covers every other generated component and the balance.
    expect(options).not.toContain('weapons.guns');
    expect(options).not.toContain('weapons.mounts');
    expect(options).not.toContain('weapons.ammunition');
    expect(options).not.toContain('weapons.layout_armour');
    expect(options).not.toContain('weapons.gun_house_armour');
    expect(options).not.toContain('weapons.main_belt');
    expect(options).not.toContain('propulsion.machinery');
    expect(options).not.toContain('propulsion.fuel');
    expect(options).not.toContain('hull.adjustable');
    expect(options).not.toContain('hull.structure');
    const claims = claimedTargetIds(config(document()));
    for (const item of ['weapons.guns', 'weapons.layout_armour', 'weapons.gun_house_armour',
      'propulsion.fuel', 'hull.adjustable', 'aux.torpedo_main']) {
      expect(claims, item).toContain(item);
    }
  });

  it('clears only this binding when the owning system changes', () => {
    const { document } = mount(boundProject());
    fireEvent.change(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.system')), { target: { value: 'weapons.main' } });
    expect(record(document()).system_id).toBe('weapons.main');
    expect(record(document()).item_id).toBeNull();
    // Nothing else moved with it.
    expect(config(document()).battery_layouts[0].armour.item_id).toBe('weapons.layout_armour');
    expect(config(document()).batteries[0].mounts_item_id).toBe('weapons.mounts');
  });

  it('carries the combined mass in the existing other role, never as guns', () => {
    const base = config(boundProject());
    expect(AUXILIARY_WEAPON_ROLE).toBe('other');
    expect(componentBindings(base)['aux.torpedo_main']).toBe('other');
    expect(mismatchedRoles(base)).toContain('aux.torpedo_main');
    const withRole = { ...base, balance: { ...base.balance,
      roles: { ...base.balance.roles, 'aux.torpedo_main': 'other' } } };
    expect(mismatchedRoles(withRole)).not.toContain('aux.torpedo_main');
    // It is not silently relabelled as a bare gun or an ammunition mass.
    expect(componentBindings(withRole)['aux.torpedo_main']).not.toBe('guns');
    expect(componentBindings(withRole)['aux.torpedo_main']).not.toBe('ammunition');
    expect(auxiliaryWeaponRole({ kind: 'mine' })).toBe('other');
    expect(auxiliaryWeaponRole({ kind: 'depth_charge' })).toBe('other');
    expect(auxiliaryWeaponRole({ kind: null })).toBeNull();
    expect(auxiliaryWeaponKind('torpedo')).toBe('torpedo');
    expect(auxiliaryWeaponKind('torp')).toBeNull();
  });

  it('names the claim that carries it, so a collision is visible', () => {
    const declared = config(boundProject());
    expect(componentTargetClaims(declared).map(claim => claim.owner))
      .toContain('auxiliary weapon auxiliary_1');
    expect(duplicateTargets(declared)).toEqual([]);
  });

  it('says so when two declarations name one item, and removes nothing', () => {
    const declared = config(boundProject());
    declared.auxiliary_weapons = [
      { ...newAuxiliaryWeapon([]), kind: 'torpedo', system_id: 'auxiliary.weapons',
        item_id: 'aux.mine_rack', count: 4 },
      { ...newAuxiliaryWeapon([]), kind: 'mine', system_id: 'auxiliary.weapons',
        item_id: 'aux.mine_rack', count: 24 },
    ];
    expect(auxiliaryWeaponTargetConflicts(declared)).toEqual(['aux.mine_rack']);
    expect(duplicateTargets(declared)).toEqual(['aux.mine_rack']);
    const { document } = mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    // One notice on the section and one on each of the two rows.
    expect(screen.getAllByText(copy('concept.auxiliary.targetConflict',
      { item: 'aux.mine_rack' })).length).toBe(3);
    expect(auxiliaryWeapons(config(document()))).toHaveLength(2);
  });

  it('refuses an item another component already owns, and leaves it owned', () => {
    const declared = config(boundProject());
    // A hand-edited document naming a battery row's guns as a torpedo target.
    declared.auxiliary_weapons = [{ ...newAuxiliaryWeapon([]), kind: 'torpedo',
      system_id: 'weapons.main', item_id: 'weapons.guns', count: 4 }];
    expect(duplicateTargets(declared)).toEqual(['weapons.guns']);
    const { document } = mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect(screen.getAllByText(copy('concept.auxiliary.targetConflict',
      { item: 'weapons.guns' })).length).toBeGreaterThan(0);
    // The battery row's own binding and its mass are untouched.
    expect(config(document()).batteries[0].guns_item_id).toBe('weapons.guns');
    expect(componentBindings(config(document()))['weapons.guns']).toBe('guns');
  });

  it('keeps one identifier out of two declarations, and names the duplicate', () => {
    const declared = config(enabledProject());
    declared.auxiliary_weapons = [
      { ...newAuxiliaryWeapon([]), id: 'torp' }, { ...newAuxiliaryWeapon([]), id: 'torp' },
    ];
    expect(duplicateAuxiliaryWeaponIds(declared)).toEqual(['torp']);
    mount({ ...enabledProject(), concept_design: declared } as ProjectDocument);
    expect(screen.getAllByText(copy('concept.auxiliary.duplicateId', { id: 'torp' })).length).toBe(2);
  });

  it('marks an identifier the contract would refuse, without rewriting it', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.auxiliary.add') }));
    fireEvent.change(within(regionPanel('auxiliary_1'))
      .getByLabelText(copy('concept.auxiliary.id')), { target: { value: 'torp 1' } });
    expect(record(document()).id).toBe('torp 1');
    expect(auxiliaryWeaponIdValid('torp 1')).toBe(false);
    expect(auxiliaryWeaponIdValid('torp_1.a-b')).toBe(true);
    expect(screen.getByText(copy('concept.auxiliary.invalidId'))).toBeVisible();
  });

  it('removing one declaration leaves the others and the ledger alone', () => {
    const declared = config(enabledProject());
    declared.auxiliary_weapons = [
      { ...newAuxiliaryWeapon([]), kind: 'torpedo', system_id: 'auxiliary.weapons',
        item_id: 'aux.torpedo_main' },
      { ...newAuxiliaryWeapon([]), kind: 'mine', system_id: 'auxiliary.weapons',
        item_id: 'aux.mine_rack' },
    ];
    const base = { ...enabledProject(), concept_design: declared } as ProjectDocument;
    const after = removeAuxiliaryWeapon(declared, 0);
    expect(auxiliaryWeapons(after)).toHaveLength(1);
    expect(auxiliaryWeapons(after)[0].item_id).toBe('aux.mine_rack');
    // The declaration is gone; the ledger item and the role table are not touched.
    expect((base as Record<string, any>).weight_groups).toHaveLength(1);
    expect(auxiliaryWeapons(removeAuxiliaryWeapon(declared, 0))[0].item_id).toBe('aux.mine_rack');
  });
});

describe('the language of the auxiliary weapons section', () => {
  it('keeps English and Chinese words for every label it prints', () => {
    const keys: ConceptKey[] = ['concept.group.auxiliary', 'concept.auxiliary.note',
      'concept.auxiliary.add', 'concept.auxiliary.remove', 'concept.auxiliary.max',
      'concept.auxiliary.id', 'concept.auxiliary.idHint', 'concept.auxiliary.source',
      'concept.auxiliary.kind', 'concept.auxiliary.kindHint', 'concept.auxiliary.system',
      'concept.auxiliary.item', 'concept.auxiliary.bindingHint', 'concept.auxiliary.roleHint',
      'concept.auxiliary.count', 'concept.auxiliary.countHint',
      'concept.auxiliary.loads.torpedo', 'concept.auxiliary.loads.torpedoHint',
      'concept.auxiliary.loads.reload', 'concept.auxiliary.loads.reloadHint',
      'concept.auxiliary.location', 'concept.auxiliary.locationUnknown',
      'concept.auxiliary.diameter', 'concept.auxiliary.length', 'concept.auxiliary.unitMass',
      'concept.auxiliary.unitMassHint', 'concept.auxiliary.separate',
      'concept.auxiliary.duplicateId', 'concept.auxiliary.invalidId',
      'concept.auxiliary.targetConflict', 'concept.auxiliary.kind.torpedo',
      'concept.auxiliary.kind.mine', 'concept.auxiliary.kind.depth_charge',
      'balance.auxiliary.title', 'balance.auxiliary.method', 'balance.auxiliary.metric.weapon',
      'balance.auxiliary.metric.mount', 'balance.auxiliary.metric.total',
      'balance.auxiliary.metric.factor', 'balance.auxiliary.diagnostics',
      'balance.auxiliary.unitConvention', 'proposals.component.auxiliary'];
    for (const kind of ['torpedo', 'mine', 'depth_charge'] as const) {
      for (const name of AUXILIARY_WEAPON_LOCATION_KEYS[kind]) keys.push(name);
    }
    for (const key of keys) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });

  it('translates all seventeen recovered location choices rather than printing an index', () => {
    const total = AUXILIARY_WEAPON_LOCATION_KEYS.torpedo.length
      + AUXILIARY_WEAPON_LOCATION_KEYS.mine.length
      + AUXILIARY_WEAPON_LOCATION_KEYS.depth_charge.length;
    expect(total).toBe(17);
    for (const [kind, names] of Object.entries(AUXILIARY_WEAPON_LOCATION_KEYS)) {
      expect(new Set(names).size, kind).toBe(names.length);
      for (const name of names) {
        expect(copy(name).trim(), name).not.toMatch(/^\d+$/);
        expect(copyZh(name), name).not.toBe(copy(name));
      }
    }
  });
});

/** The declared configuration without the auxiliary weapons this suite added. */
function withoutAux(declared: Record<string, unknown>): Record<string, unknown> {
  const { auxiliary_weapons: _dropped, ...rest } = declared;
  return rest;
}

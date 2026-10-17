import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { MassProposalPanel } from '../components/MassProposalPanel';
import {
  batteryLayoutReferences, batteryLayouts, componentBindings, duplicateLayoutReferences,
  layoutArmourConflicts, MAX_BATTERY_LAYOUTS, mismatchedRoles, newBattery, newBatteryLayout,
  newConcept, patchBattery, patchBatteryLayout, removeBatteryLayout,
} from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import * as api from '../api';
import type { ProjectDocument, RunView } from '../types';

// The two-group layout section is ordinary project input, so every assertion here
// is about what the *document* ends up holding after a real event. Nothing in
// this suite knows a freeboard expression: a derived number is the server's,
// and the editor's whole duty is to keep an unknown value unknown.

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
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts',
    'weapons.ammunition', 'weapons.gun_house_armour', 'weapons.layout_armour'] } },
  armour: { fixed: { weight_item_ids: ['weapons.gun_house_armour'] } },
  propulsion: { machinery: { weight_item_ids: ['propulsion.machinery'] },
    fuel: { weight_item_ids: ['propulsion.fuel'] } },
};

function baseProject(): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS,
  };
}

/** An enabled concept design with the two battery rows a layout may reference. */
function enabledProject(): ProjectDocument {
  const config = newConcept();
  config.source = 'a declared study design';
  config.batteries = [
    { ...newBattery([]), id: 'main', system_id: 'weapons.main',
      guns_item_id: 'weapons.guns', mounts_item_id: 'weapons.mounts',
      ammunition_item_id: 'weapons.ammunition',
      calibre_mm: 152.4, barrel_calibres: 45, year: 1918,
      gun_type: 'breech_loading', mount_type: 'deck_hoist',
      mount_count: 4, barrels_per_mount: 2, rounds_per_gun: 120 },
    { ...newBattery([]), id: 'wing', system_id: 'weapons.main',
      guns_item_id: 'weapons.guns', mounts_item_id: 'weapons.mounts',
      ammunition_item_id: 'weapons.ammunition',
      calibre_mm: 152.4, barrel_calibres: 45, year: 1918,
      gun_type: 'breech_loading', mount_type: 'deck_hoist',
      mount_count: 2, barrels_per_mount: 2, rounds_per_gun: 120 },
  ];
  return { ...baseProject(), concept_design: config } as ProjectDocument;
}

function Harness({ initial, onDocument }: {
  initial: ProjectDocument; onDocument: (next: ProjectDocument) => void;
}) {
  const [draft, setDraft] = useState(initial);
  return <UnitProvider preferences={null}>
    <ConceptDesignEditor project={draft} onChange={next => { setDraft(next); onDocument(next); }} />
  </UnitProvider>;
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

/** One layout's own disclosure, addressed by the id its summary prints. */
function layoutPanel(id: string): HTMLElement {
  return screen.getByText(id).closest('details') as HTMLElement;
}

/** The label of one field inside one layout's own panel. */
function field(group: ConceptKey, name: ConceptKey, params?: Record<string, string | number>): string {
  return `${copy(group, params)} · ${copy(name)}`;
}

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.createProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: baseProject() });
});

afterEach(() => { vi.unstubAllGlobals(); });

describe('the two-group layout section', () => {
  it('adds a layout with nothing declared in it: both groups absent and both flags unknown', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const layouts = config(document()).battery_layouts;
    expect(layouts).toHaveLength(1);
    expect(layouts[0]).toEqual({
      id: 'layout_1', source: '', group1: null, group2: null,
      group2_double_elevation: null, group2_double_depression: null,
      deck_profile: { forecastle_fraction: null, forward_deck_fraction: null,
        forward_fore_m: null, forward_aft_m: null, aft_fore_m: null, aft_aft_m: null },
      armour: null,
    });
    // An absent group is not a known zero: no counts, selector or layout is written.
    expect(layouts[0].group1).toBeNull();
    expect(config(document()).batteries).toHaveLength(2);
  });

  it('gives every new layout its own stable identifier, even after one is deleted', () => {
    const first = newBatteryLayout([]);
    const second = newBatteryLayout([first]);
    const third = newBatteryLayout([second]);
    expect([first.id, second.id, third.id]).toEqual(['layout_1', 'layout_2', 'layout_3']);
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    expect(config(document()).battery_layouts.map((row: any) => row.id))
      .toEqual(['layout_1', 'layout_2']);
  });

  it('writes an editable source of its own, never the concept-level one', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const id = within(layoutPanel('layout_1')).getByLabelText(copy('concept.layout.id'));
    fireEvent.change(id, { target: { value: 'main_layout' } });
    expect(config(document()).battery_layouts[0].id).toBe('main_layout');
    const source = within(layoutPanel('main_layout')).getByLabelText(copy('concept.layout.source'));
    fireEvent.change(source, { target: { value: 'declared synthetic layout' } });
    expect(config(document()).battery_layouts[0].source).toBe('declared synthetic layout');
    // The declaration's own source is a separate fact and is untouched.
    expect(config(document()).source).toBe('a declared study design');
  });

  it('references two existing battery rows and never restates their facts', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    fireEvent.change(within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.battery')),
      { target: { value: 'main' } });
    fireEvent.change(within(panel()).getByLabelText(field('concept.layout.group2', 'concept.layout.group.battery')),
      { target: { value: 'wing' } });
    const layout = config(document()).battery_layouts[0];
    expect(layout.group1.battery_id).toBe('main');
    expect(layout.group2.battery_id).toBe('wing');
    // Identity facts stay on the row: a group carries no calibre, year or class.
    expect(Object.keys(layout.group1).sort())
      .toEqual(['battery_id', 'deck_mounts', 'depressed_mounts', 'elevated_mounts',
        'layout_index', 'mount_selector']);
    expect(layout.group1.calibre_mm).toBeUndefined();
    // The row itself is unchanged by being referenced.
    expect(config(document()).batteries[0].calibre_mm).toBe(152.4);
    expect(config(document()).batteries[0].mount_count).toBe(4);
    expect(panel().textContent).toContain('152.4');
    expect(panel().textContent).toContain('1918');
  });

  it('offers only rows that no other layout and no sibling group has claimed', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    fireEvent.change(within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.battery')),
      { target: { value: 'main' } });
    const picker = within(panel())
      .getByLabelText(field('concept.layout.group2', 'concept.layout.group.battery')) as HTMLSelectElement;
    expect([...picker.options].map(option => option.value)).toEqual(['', 'wing']);
    // The sibling's own row is never offered to the other group, and an empty
    // choice keeps the group absent rather than declaring a known zero.
    fireEvent.change(picker, { target: { value: '' } });
    expect(config(document()).battery_layouts[0].group2).toBeNull();
  });

  it('writes the recovered selector and layout readings as integers and keeps a blank unknown', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    const group = field('concept.layout.group1', 'concept.layout.group.battery');
    fireEvent.change(within(panel()).getByLabelText(group), { target: { value: 'main' } });
    const group1 = () => config(document()).battery_layouts[0].group1;
    const selector = within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.selector'));
    const layout = within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.layoutIndex'));
    expect(selector).toHaveValue('');
    expect(layout).toHaveValue('');
    fireEvent.change(selector, { target: { value: '4' } });
    fireEvent.change(layout, { target: { value: '7' } });
    expect(group1().mount_selector).toBe(4);
    expect(group1().layout_index).toBe(7);
    // The recovered tables are 0..14 and 0..17; nothing outside them is offered.
    expect([...(selector as HTMLSelectElement).options].map(option => option.value))
      .toEqual(['', ...Array.from({ length: 15 }, (_, index) => String(index))]);
    expect([...(layout as HTMLSelectElement).options].map(option => option.value))
      .toEqual(['', ...Array.from({ length: 18 }, (_, index) => String(index))]);
    // A cleared reading is unknown again, never inferred as layout 0.
    fireEvent.change(layout, { target: { value: '' } });
    expect(group1().layout_index).toBeNull();
    expect(group1().mount_selector).toBe(4);
  });

  it('keeps the layer counts as typed and empty as unknown, without filling the gap', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    fireEvent.change(within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.battery')),
      { target: { value: 'main' } });
    const elevated = within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.elevated'));
    const deck = within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.deck'));
    const depressed = within(panel()).getByLabelText(field('concept.layout.group1', 'concept.layout.group.depressed'));
    fireEvent.change(elevated, { target: { value: '1' } });
    fireEvent.change(deck, { target: { value: '1' } });
    fireEvent.change(depressed, { target: { value: '2' } });
    expect(config(document()).battery_layouts[0].group1)
      .toMatchObject({ elevated_mounts: 1, deck_mounts: 1, depressed_mounts: 2 });
    fireEvent.change(depressed, { target: { value: '' } });
    expect(config(document()).battery_layouts[0].group1.depressed_mounts).toBeNull();
    // A fractional count is kept as typed and marked, never truncated for the reader.
    fireEvent.change(depressed, { target: { value: '2.5' } });
    expect(config(document()).battery_layouts[0].group1.depressed_mounts).toBe(2.5);
    expect(depressed).toHaveAttribute('aria-invalid', 'true');
  });

  it('writes the two group-2 doubled flags as true, false and unknown, and never fills in a false', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    const elevation = within(panel()).getByLabelText(copy('concept.layout.flag.elevation'));
    const depression = within(panel()).getByLabelText(copy('concept.layout.flag.depression'));
    const layout = () => config(document()).battery_layouts[0];
    expect(layout().group2_double_elevation).toBeNull();
    expect(layout().group2_double_depression).toBeNull();
    fireEvent.change(elevation, { target: { value: 'true' } });
    fireEvent.change(depression, { target: { value: 'false' } });
    expect(layout().group2_double_elevation).toBe(true);
    // An explicit "no" is a declared boolean, and it is stored as one.
    expect(layout().group2_double_depression).toBe(false);
    fireEvent.change(elevation, { target: { value: '' } });
    expect(layout().group2_double_elevation).toBeNull();
    // A flag says nothing about a group that is not configured at all.
    expect(layout().group2).toBeNull();
  });

  it('writes the six deck profile facts: fractions as fractions, freeboards in metres', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    const profile = () => config(document()).battery_layouts[0].deck_profile;
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.forecastle')),
      { target: { value: '0.2' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.forwardDeck')),
      { target: { value: '0.3' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.forwardFore')),
      { target: { value: '7' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.forwardAft')),
      { target: { value: '5' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.aftFore')),
      { target: { value: '5' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.aftAft')),
      { target: { value: '4' } });
    expect(profile()).toEqual({ forecastle_fraction: 0.2, forward_deck_fraction: 0.3,
      forward_fore_m: 7, forward_aft_m: 5, aft_fore_m: 5, aft_aft_m: 4 });
    // An out-of-range fraction is kept as typed: nothing is clamped to the domain.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.forecastle')),
      { target: { value: '1.4' } });
    expect(profile().forecastle_fraction).toBe(1.4);
    // An empty one stays unknown rather than becoming a known zero.
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.deck.aftAft')),
      { target: { value: '' } });
    expect(profile().aft_aft_m).toBeNull();
  });

  it('converts a displayed deck freeboard back to metres through the reader’s own unit', () => {
    const { document } = mount(enabledProject(), { length: 'ft' });
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    const panel = () => layoutPanel('layout_1');
    const field7 = within(panel()).getByLabelText(copy('concept.layout.deck.forwardFore'));
    expect(field7.closest('.field-label')?.textContent).toContain('ft');
    fireEvent.change(field7, { target: { value: '22.9658897638' } });
    expect(config(document()).battery_layouts[0].deck_profile.forward_fore_m).toBeCloseTo(7, 5);
  });

  it('is absent from a project that declares none, so an old project is untouched', () => {
    const project = enabledProject();
    const bare = { ...project, concept_design: newConcept() } as ProjectDocument;
    const { document } = mount(bare);
    expect(batteryLayouts(config(document()))).toEqual([]);
    expect(copy('concept.layout.add')).toBeTruthy();
  });

  it('refuses a fifty-first layout and says why, rather than writing one the server would reject', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    const layouts: any[] = [];
    for (let index = 0; index < MAX_BATTERY_LAYOUTS; index += 1) layouts.push(newBatteryLayout(layouts));
    layoutConfig.battery_layouts = layouts;
    const { document } = mount({ ...project, concept_design: layoutConfig } as ProjectDocument);
    const add = screen.getByRole('button', { name: copy('concept.layout.add') });
    expect(add).toBeDisabled();
    expect(screen.getByText(copy('concept.layout.max', { count: MAX_BATTERY_LAYOUTS }))).toBeVisible();
    fireEvent.click(add);
    expect(config(document()).battery_layouts).toHaveLength(MAX_BATTERY_LAYOUTS);
  });

  it('deletes a layout and leaves the batteries, the ledger and every mass alone', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    const first = newBatteryLayout([]);
    const second = newBatteryLayout([first]);
    layoutConfig.battery_layouts = [first, second];
    const armed = patchBattery(layoutConfig, 0, { armour: armourBlock() });
    layoutConfig.batteries = armed.batteries as any;
    const { document } = mount({ ...project, concept_design: layoutConfig } as ProjectDocument);
    const before = document();
    fireEvent.click(within(layoutPanel('layout_1'))
      .getByRole('button', { name: copy('concept.layout.remove') }));
    const after = config(document());
    expect(after.battery_layouts.map((row: any) => row.id)).toEqual(['layout_2']);
    // Nothing but the layout list moved: the rows, their armour and the ledger.
    expect(after.batteries).toEqual(config(before).batteries);
    expect((document() as Record<string, any>).weight_groups).toEqual((before as Record<string, any>).weight_groups);
  });
});

describe('the layout’s own complete two-group armour', () => {
  function layoutProject(): ProjectDocument {
    const project = enabledProject();
    const layoutConfig = config(project);
    layoutConfig.battery_layouts = [newBatteryLayout([])];
    layoutConfig.battery_layouts[0].group1 = { battery_id: 'main', mount_selector: 4,
      layout_index: 1, elevated_mounts: 1, deck_mounts: 1, depressed_mounts: 2 };
    layoutConfig.battery_layouts[0].group2 = { battery_id: 'wing', mount_selector: 3,
      layout_index: 7, elevated_mounts: null, deck_mounts: 1, depressed_mounts: 1 };
    return { ...project, concept_design: layoutConfig } as ProjectDocument;
  }

  it('is absent until it is turned on, and then holds its own owned target', () => {
    const { document } = mount(layoutProject());
    expect(config(document()).battery_layouts[0].armour).toBeNull();
    const box = within(layoutPanel('layout_1')).getByRole('checkbox', { name: copy('concept.layout.armour.use') });
    expect(box).not.toBeChecked();
    fireEvent.click(box);
    expect(config(document()).battery_layouts[0].armour).toEqual({
      system_id: null, item_id: null, face_mm: null, rear_roof_mm: null, barbette_mm: null,
    });
    const panel = layoutPanel('layout_1');
    fireEvent.change(within(panel).getByLabelText(copy('concept.layout.armour.system')),
      { target: { value: 'weapons.main' } });
    const picker = within(panel).getByLabelText(copy('concept.layout.armour.item')) as HTMLSelectElement;
    const options = [...picker.options].map(option => option.value);
    // Only an item this system owns; the row's own three targets are never
    // offered, because one target under two components is refused.
    expect(options).toContain('weapons.layout_armour');
    expect(options).not.toContain('weapons.guns');
    expect(options).not.toContain('weapons.mounts');
    expect(options).not.toContain('weapons.ammunition');
    fireEvent.change(picker, { target: { value: 'weapons.layout_armour' } });
    expect(config(document()).battery_layouts[0].armour.item_id).toBe('weapons.layout_armour');
  });

  it('stores the three thicknesses in millimetres whatever the reader’s unit is', () => {
    const { document } = mount(layoutProject(), { length: 'ft' });
    const panel = () => layoutPanel('layout_1');
    fireEvent.click(within(panel()).getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.face')),
      { target: { value: '0.984251968503937' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.side')),
      { target: { value: '0.3937007874015748' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.barbette')),
      { target: { value: '0.2952755905511812' } });
    const armour = config(document()).battery_layouts[0].armour;
    expect(armour.face_mm).toBeCloseTo(300, 6);
    expect(armour.rear_roof_mm).toBeCloseTo(120, 6);
    expect(armour.barbette_mm).toBeCloseTo(90, 6);
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.face')),
      { target: { value: '' } });
    expect(config(document()).battery_layouts[0].armour.face_mm).toBeNull();
  });

  it('clears only its own binding when the owning system changes', () => {
    const { document } = mount(layoutProject());
    const panel = () => layoutPanel('layout_1');
    fireEvent.click(within(panel()).getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.system')),
      { target: { value: 'weapons.main' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.item')),
      { target: { value: 'weapons.layout_armour' } });
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.system')),
      { target: { value: 'armour.fixed' } });
    const layout = config(document()).battery_layouts[0];
    expect(layout.armour.system_id).toBe('armour.fixed');
    expect(layout.armour.item_id).toBeNull();
    // The referenced rows and their own bindings did not move with it.
    expect(layout.group1.battery_id).toBe('main');
    expect(config(document()).batteries[0].mounts_item_id).toBe('weapons.mounts');
  });

  it('names the complete-armour role for its own target, exactly like a row estimate', () => {
    const base = config(layoutProject());
    const declared = patchBatteryLayout(base, 0, { armour: {
      system_id: 'weapons.main', item_id: 'weapons.layout_armour', face_mm: 150,
      rear_roof_mm: 100, barbette_mm: 75 } }) as Record<string, any>;
    expect(componentBindings(declared)['weapons.layout_armour']).toBe('gun_mount_armour');
    expect(mismatchedRoles(declared)).toContain('weapons.layout_armour');
    declared.balance.roles = { 'weapons.layout_armour': 'gun_mount_armour' };
    expect(mismatchedRoles(declared)).not.toContain('weapons.layout_armour');
    mount({ ...baseProject(), concept_design: declared } as ProjectDocument);
    expect(screen.getAllByRole('option', { name: copy('concept.role.gun_mount_armour') }).length)
      .toBeGreaterThan(0);
  });

  it('explains the conflict with a referenced row’s own estimate, and never drops it', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    layoutConfig.batteries = patchBattery(layoutConfig, 0,
      { armour: armourBlock() }).batteries as any;
    layoutConfig.battery_layouts = [newBatteryLayout([])];
    layoutConfig.battery_layouts[0].group1 = { battery_id: 'main', mount_selector: null,
      layout_index: null, elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    const armed = { ...project, concept_design: layoutConfig } as ProjectDocument;
    expect(layoutArmourConflicts(layoutConfig, 0)).toEqual(['main']);
    const { document } = mount(armed);
    fireEvent.click(within(layoutPanel('layout_1'))
      .getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    const notice = within(layoutPanel('layout_1')).getByRole('alert');
    expect(notice.textContent).toContain('main');
    // The old declaration is still there, untouched, for the reader to decide on.
    expect(config(document()).batteries[0].armour).toEqual(armourBlock());
  });

  it('says nothing about a conflict while the complete estimate is off: layout-only readings are legal', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    layoutConfig.batteries = patchBattery(layoutConfig, 0,
      { armour: armourBlock() }).batteries as any;
    layoutConfig.battery_layouts = [newBatteryLayout([])];
    layoutConfig.battery_layouts[0].group1 = { battery_id: 'main', mount_selector: 4,
      layout_index: 1, elevated_mounts: 1, deck_mounts: 1, depressed_mounts: 2 };
    const { document } = mount({ ...project, concept_design: layoutConfig } as ProjectDocument);
    // The referenced row does keep its own single-group estimate…
    expect(layoutArmourConflicts(layoutConfig, 0)).toEqual(['main']);
    // …and a layout that derives readings without a second armour model is not
    // a warning: the reader asked for one model of this battery's armour.
    expect(within(layoutPanel('layout_1')).queryByRole('alert')).toBeNull();
    expect(screen.queryByText(copy('concept.layout.armour.conflict', { batteries: 'main' }))).toBeNull();
    expect(config(document()).battery_layouts[0].armour).toBeNull();
    // The moment the reader asks for the second model, the reason appears.
    fireEvent.click(within(layoutPanel('layout_1'))
      .getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    expect(within(layoutPanel('layout_1')).getByRole('alert')).toHaveTextContent('main');
    // And switching it back off leaves the row's own declaration intact.
    fireEvent.click(within(layoutPanel('layout_1'))
      .getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    expect(within(layoutPanel('layout_1')).queryByRole('alert')).toBeNull();
    expect(config(document()).batteries[0].armour).toEqual(armourBlock());
  });

  it('turning the layout estimate off removes only its own inputs', () => {
    const { document } = mount(layoutProject());
    const panel = () => layoutPanel('layout_1');
    fireEvent.click(within(panel()).getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    fireEvent.change(within(panel()).getByLabelText(copy('concept.layout.armour.face')),
      { target: { value: '0.15' } });
    fireEvent.click(within(panel()).getByRole('checkbox', { name: copy('concept.layout.armour.use') }));
    const layout = config(document()).battery_layouts[0];
    expect(layout.armour).toBeNull();
    expect(layout.group1).toEqual({ battery_id: 'main', mount_selector: 4, layout_index: 1,
      elevated_mounts: 1, deck_mounts: 1, depressed_mounts: 2 });
    expect(config(document()).batteries).toHaveLength(2);
  });
});

function armourBlock() {
  return { system_id: 'weapons.main', item_id: 'weapons.gun_house_armour', face_mm: 150,
    rear_roof_mm: 100, barbette_mm: 75, freeboard_m: 4.6, super_factor: 1 };
}

describe('references between layouts and rows', () => {
  it('names the layouts that reference one row, so a deletion can be explained', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    const first = newBatteryLayout([]);
    first.group1 = { battery_id: 'main', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    const second = newBatteryLayout([first]);
    second.group1 = { battery_id: null, mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    second.group2 = { battery_id: 'wing', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    layoutConfig.battery_layouts = [first, second];
    expect(batteryLayoutReferences(layoutConfig, 'main')).toEqual(['layout_1']);
    expect(batteryLayoutReferences(layoutConfig, 'wing')).toEqual(['layout_2']);
    expect(batteryLayoutReferences(layoutConfig, 'nowhere')).toEqual([]);
    expect(duplicateLayoutReferences(layoutConfig)).toEqual([]);
    first.group2 = { battery_id: 'main', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    expect(duplicateLayoutReferences(layoutConfig)).toContain('main');
  });

  it('stops naming a row after its layout is removed', () => {
    const declared = config(enabledProject());
    const first = newBatteryLayout([]);
    first.group1 = { battery_id: 'main', mount_selector: null, layout_index: null,
      elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    declared.battery_layouts = [first];
    expect(batteryLayoutReferences(declared, 'main')).toEqual(['layout_1']);
    const after = removeBatteryLayout(declared, 0);
    expect(after.battery_layouts).toEqual([]);
    expect(batteryLayoutReferences(after, 'main')).toEqual([]);
  });

  it('blocks deleting a referenced row and names the layout that still points at it', () => {
    const project = enabledProject();
    const layoutConfig = config(project);
    layoutConfig.battery_layouts = [newBatteryLayout([])];
    layoutConfig.battery_layouts[0].group1 = { battery_id: 'main', mount_selector: null,
      layout_index: null, elevated_mounts: null, deck_mounts: null, depressed_mounts: null };
    const { document } = mount({ ...project, concept_design: layoutConfig } as ProjectDocument);
    fireEvent.click(screen.getAllByRole('button', { name: copy('concept.battery.remove') })[0]);
    // Nothing was deleted, and the reason names the layout to clear first.
    expect(config(document()).batteries).toHaveLength(2);
    const alert = screen.getAllByRole('alert').find(node => /layout_1/.test(node.textContent ?? ''));
    expect(alert).toBeTruthy();
    expect(alert?.textContent).toContain(copy('concept.battery.removeBlocked',
      { layouts: 'layout_1' }));
    // Once the reference is gone the row deletes exactly as before.
    fireEvent.click(within(layoutPanel('layout_1'))
      .getByRole('button', { name: copy('concept.layout.remove') }));
    fireEvent.click(screen.getAllByRole('button', { name: copy('concept.battery.remove') })[0]);
    expect(config(document()).batteries).toHaveLength(1);
    expect(config(document()).batteries[0].id).toBe('wing');
  });

  it('keeps both English and Chinese words for every label it prints', () => {
    const keys: ConceptKey[] = ['concept.layout.title', 'concept.layout.add', 'concept.layout.remove',
      'concept.layout.max', 'concept.layout.id', 'concept.layout.source', 'concept.layout.group1',
      'concept.layout.group2', 'concept.layout.group.battery', 'concept.layout.group.selector',
      'concept.layout.group.layoutIndex', 'concept.layout.group.elevated',
      'concept.layout.group.deck', 'concept.layout.group.depressed', 'concept.layout.flag.elevation',
      'concept.layout.flag.depression', 'concept.layout.flag.unknown', 'concept.layout.deck.forecastle',
      'concept.layout.deck.forwardDeck', 'concept.layout.deck.forwardFore',
      'concept.layout.deck.forwardAft', 'concept.layout.deck.aftFore', 'concept.layout.deck.aftAft',
      'concept.layout.armour.use', 'concept.layout.armour.system', 'concept.layout.armour.item',
      'concept.layout.armour.face', 'concept.layout.armour.side', 'concept.layout.armour.barbette',
      'concept.layout.armour.conflict', 'concept.battery.removeBlocked',
      'balance.layout.title', 'balance.layout.freeboard', 'balance.layout.super'];
    for (const key of keys) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });

  it('translates the recovered selector and arrangement readings rather than printing an index', () => {
    mount(enabledProject());
    fireEvent.click(screen.getByRole('button', { name: copy('concept.layout.add') }));
    fireEvent.change(within(layoutPanel('layout_1'))
      .getByLabelText(field('concept.layout.group1', 'concept.layout.group.battery')),
      { target: { value: 'main' } });
    const selector = within(layoutPanel('layout_1'))
      .getByLabelText(field('concept.layout.group1', 'concept.layout.group.selector')) as HTMLSelectElement;
    const twin = [...selector.options].find(entry => entry.value === '3');
    const pair = [...selector.options].find(entry => entry.value === '4');
    // The recovered names, so a two-column mount stays distinct from a single
    // column of the same barrel count.
    expect(twin?.textContent).not.toBe('3');
    expect(twin?.textContent).toMatch(/twin/i);
    expect(pair?.textContent).toMatch(/2-gun/i);
    const layout = within(layoutPanel('layout_1'))
      .getByLabelText(field('concept.layout.group1', 'concept.layout.group.layoutIndex')) as HTMLSelectElement;
    const layoutOption = [...layout.options].find(entry => entry.value === '7');
    expect(layoutOption?.textContent).not.toBe('7');
    expect(layoutOption?.textContent).toMatch(/aft deck/i);  });
});

// --- the reviewable proposal of a layout's complete armour -------------------
describe('a layout armour proposal in the reviewed batch', () => {
  const run = { result: { stages: { systems: { data: { update_proposals: [{
    item_id: 'weapons.layout_armour', source_system_id: 'weapons.main',
    source_model_id: 'concept_layout.main_layout.armour',
    current_mass_t: null, proposed_mass_t: 812.4, delta_t: null,
    model: { concept_component: 'armour', method: 'empirical_estimate_v1',
      source: { method_version: 'sps-3b3-battery-armour-v2' } },
  }] } } } } } as unknown as RunView;

  function panel(overrides: Partial<Parameters<typeof MassProposalPanel>[0]> = {}) {
    const onApply = vi.fn();
    render(<UnitProvider preferences={null}><MassProposalPanel run={run} identity="layout-run"
      dirty={false} apply={{ phase: 'idle', revision: null, reason: null }}
      onApply={onApply} onRerun={vi.fn()} {...overrides} /></UnitProvider>);
    return { onApply };
  }

  it('is named by the existing translated armour component, with its own model id', () => {
    panel();
    expect(screen.getByRole('cell', { name: copy('proposals.component.armour') })).toBeTruthy();
    expect(screen.getAllByText('concept_layout.main_layout.armour').length).toBeGreaterThan(0);
    expect(screen.getByText(/sps-3b3-battery-armour-v2/)).toBeVisible();
  });

  it('selects nothing by itself and applies only what the reader ticked', () => {
    const { onApply } = panel();
    const button = screen.getByRole('button', { name: copy('proposals.apply') });
    expect(button).toBeDisabled();
    fireEvent.click(screen.getByLabelText('weapons.layout_armour Select'));
    fireEvent.click(button);
    expect(onApply.mock.calls[0][0][0].source_model_id).toBe('concept_layout.main_layout.armour');
  });

  it('keeps the same stale-result protection as every other estimate', () => {
    panel({ dirty: true });
    expect(screen.queryByRole('button', { name: copy('proposals.apply') })).toBeNull();
    expect(screen.getByText(copy('proposals.emptyDirty'))).toBeVisible();
  });
});

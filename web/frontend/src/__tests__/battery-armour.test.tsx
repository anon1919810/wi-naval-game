import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { MassProposalPanel } from '../components/MassProposalPanel';
import {
  componentBindings, conceptEnabled, mismatchedRoles, newBattery, newConcept, patchBattery,
} from '../components/conceptDesign';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy } from '../i18n/concept';
import * as api from '../api';
import type { ProjectDocument, RunView } from '../types';

// The armour block is ordinary project input: every assertion here is about what
// the *document* ends up holding after a real event, not about what the control
// renders. A control that draws correctly but never writes is exactly the defect
// this suite exists to catch.

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
    { id: 'propulsion.machinery', mass_t: 1168.4539, x_m: 58 },
    { id: 'propulsion.fuel', mass_t: 711.2328, x_m: 40 },
  ],
};

const SYSTEMS = {
  hull: { structure: { weight_item_ids: ['hull.structure'] } },
  weapons: { main: { weight_item_ids: ['weapons.guns', 'weapons.mounts',
    'weapons.ammunition', 'weapons.gun_house_armour'] } },
  armour: { fixed: { weight_item_ids: ['weapons.gun_house_armour'] } },
  propulsion: { machinery: { weight_item_ids: ['propulsion.machinery'] },
    fuel: { weight_item_ids: ['propulsion.fuel'] } },
};

const ARMOUR_ITEM = 'weapons.gun_house_armour';

function baseProject(): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS,
  };
}

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

function Harness({ initial, onDocument }: {
  initial: ProjectDocument; onDocument: (next: ProjectDocument) => void }) {
  const [draft, setDraft] = useState(initial);
  return <UnitProvider preferences={null}>
    <ConceptDesignEditor project={draft} onChange={next => { setDraft(next); onDocument(next); }} />
  </UnitProvider>;
}

function mount(initial: ProjectDocument) {
  const written: ProjectDocument[] = [];
  render(<Harness initial={initial} onDocument={next => written.push(next)} />);
  return { written, document: () => written[written.length - 1] ?? initial };
}

function armourOf(document: ProjectDocument) {
  return (document as Record<string, any>).concept_design?.batteries?.[0]?.armour;
}

const copy = (key: Parameters<typeof conceptCopy>[1]) => conceptCopy('en', key);
const copyZh = (key: Parameters<typeof conceptCopy>[1]) => conceptCopy('zh-CN', key);

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.createProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: baseProject() });
});

afterEach(() => { vi.unstubAllGlobals(); });

it('names an armour proposal as the complete gun-house and barbette component', () => {
  const run = { result: { stages: { systems: { data: { update_proposals: [{
    item_id: ARMOUR_ITEM, source_system_id: 'weapons.main', source_model_id: 'concept.main.armour',
    current_mass_t: 40, proposed_mass_t: 60, delta_t: 20,
    model: { concept_component: 'armour', method: 'empirical_estimate_v1',
      source: { method_version: 'sps-3b3-battery-armour-v1' } },
  }] } } } } } as unknown as RunView;
  render(<UnitProvider preferences={null}><MassProposalPanel run={run} identity="armour-run"
    dirty={false} apply={{ phase: 'idle', revision: null, reason: null }}
    onApply={vi.fn()} onRerun={vi.fn()} /></UnitProvider>);
  expect(screen.getByRole('cell', { name: 'Gun-house and barbette armour' })).toBeTruthy();
});

describe('the optional battery armour estimate block', () => {
  it('rebases thickness display preferences while preserving canonical millimetres', () => {
    const initial = enabledProject();
    (initial as Record<string, any>).concept_design.batteries[0].armour = {
      system_id: 'weapons.main', item_id: ARMOUR_ITEM, face_mm: 254,
      rear_roof_mm: 127, barbette_mm: 101.6, freeboard_m: 4.6, super_factor: 1,
    };
    let last = initial;
    function UnitsHarness() {
      const [draft, setDraft] = useState(initial);
      const [length, setLength] = useState('m');
      return <UnitProvider preferences={{ length }}>
        <button onClick={() => setLength('ft')}>Show feet</button>
        <button onClick={() => setLength('m')}>Show metres</button>
        <ConceptDesignEditor project={draft} onChange={next => { last = next; setDraft(next); }} />
      </UnitProvider>;
    }
    render(<UnitsHarness />);
    const face = () => screen.getByLabelText(copy('concept.armour.face')) as HTMLInputElement;
    expect(Number(face().value)).toBeCloseTo(0.254, 12);
    fireEvent.click(screen.getByRole('button', { name: 'Show feet' }));
    expect(Number(face().value)).toBeCloseTo(0.254 / 0.3048, 9);
    expect(armourOf(last).face_mm).toBe(254);
    fireEvent.change(face(), { target: { value: '1' } });
    expect(armourOf(last).face_mm).toBeCloseTo(304.8, 9);
    fireEvent.click(screen.getByRole('button', { name: 'Show metres' }));
    expect(Number(face().value)).toBeCloseTo(0.3048, 9);
    expect(armourOf(last).face_mm).toBeCloseTo(304.8, 9);
    fireEvent.change(face(), { target: { value: '' } });
    expect(armourOf(last).face_mm).toBeNull();
  });
  it('is absent until the reader turns it on, so an old project is untouched', () => {
    const { document } = mount(enabledProject());
    expect(armourOf(document())).toBeUndefined();
    expect(screen.getByRole('checkbox', { name: copy('concept.armour.use') })).not.toBeChecked();
    expect(screen.queryByLabelText(copy('concept.armour.face'))).toBeNull();
    expect(screen.queryByLabelText(copy('concept.armour.item'))).toBeNull();
  });

  it('turning it on writes the block with empty, editable inputs rather than defaults', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    expect(armourOf(document())).toEqual({
      system_id: null, item_id: null, face_mm: null, rear_roof_mm: null,
      barbette_mm: null, freeboard_m: null, super_factor: null,
    });
  });

  it('converts each displayed metre thickness back to canonical millimetres', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    for (const [key, typed] of [['concept.armour.face', '0.254'],
      ['concept.armour.side', '0.127'], ['concept.armour.barbette', '0.1016']] as const) {
      fireEvent.change(screen.getByLabelText(copy(key)), { target: { value: typed } });
    }
    const armour = armourOf(document());
    expect(armour.face_mm).toBe(254);
    expect(armour.rear_roof_mm).toBe(127);
    expect(armour.barbette_mm).toBe(101.6);
  });

  it('labels the side/top thickness as an average and the barbette as below deck', () => {
    mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    expect(screen.getByText(copy('concept.armour.side'))).toBeTruthy();
    expect(screen.getByText(copy('concept.armour.barbette'))).toBeTruthy();
    // The source control names, not a rear-only reading.
    expect(copy('concept.armour.side')).toMatch(/side\s*\/\s*top/i);
    expect(copy('concept.armour.barbette')).toMatch(/barbette\s*\/\s*below deck/i);
    expect(copyZh('concept.armour.side')).toMatch(/侧面\/顶部/);
    expect(copyZh('concept.armour.barbette')).toMatch(/炮座筒\/甲板下/);
  });

  it('keeps an empty numeric input null and editable', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    const field = screen.getByLabelText(copy('concept.armour.face'));
    fireEvent.change(field, { target: { value: '0.15' } });
    expect(armourOf(document()).face_mm).toBe(150);
    fireEvent.change(field, { target: { value: '' } });
    expect(armourOf(document()).face_mm).toBeNull();
  });

  it('declares the freeboard in metres and the height factor as its own number', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    fireEvent.change(screen.getByLabelText(copy('concept.armour.freeboard')),
      { target: { value: '4.6' } });
    fireEvent.change(screen.getByLabelText(copy('concept.armour.super')),
      { target: { value: '1.2' } });
    expect(armourOf(document()).freeboard_m).toBe(4.6);
    expect(armourOf(document()).super_factor).toBe(1.2);
  });

  it('refuses an out-of-domain thickness without rewriting what was typed', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    const field = screen.getByLabelText(copy('concept.armour.face'));
    fireEvent.change(field, { target: { value: '-5' } });
    expect(armourOf(document()).face_mm).toBeNull();
    expect(field).toHaveValue(-5);
    expect(screen.getAllByRole('alert').length).toBeGreaterThan(0);
  });

  it('binds the armour to its own owned item, never to the mount item', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    fireEvent.change(screen.getByLabelText(copy('concept.armour.system')),
      { target: { value: 'weapons.main' } });
    const picker = screen.getByLabelText(copy('concept.armour.item'));
    const options = Array.from((picker as HTMLSelectElement).options).map(o => o.value);
    expect(options).toContain(ARMOUR_ITEM);
    // The row's own three items are never offered as the armour target.
    expect(options).not.toContain('weapons.mounts');
    expect(options).not.toContain('weapons.guns');
    expect(options).not.toContain('weapons.ammunition');
    fireEvent.change(picker, { target: { value: ARMOUR_ITEM } });
    expect(armourOf(document()).item_id).toBe(ARMOUR_ITEM);
  });

  it('changing the armour system clears only this block’s item binding', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    fireEvent.change(screen.getByLabelText(copy('concept.armour.system')),
      { target: { value: 'weapons.main' } });
    fireEvent.change(screen.getByLabelText(copy('concept.armour.item')),
      { target: { value: ARMOUR_ITEM } });
    const before = (document() as Record<string, any>).concept_design;
    expect(before.batteries[0].armour.item_id).toBe(ARMOUR_ITEM);
    fireEvent.change(screen.getByLabelText(copy('concept.armour.system')),
      { target: { value: 'armour.fixed' } });
    const after = (document() as Record<string, any>).concept_design;
    expect(after.batteries[0].armour.item_id).toBeNull();
    expect(after.batteries[0].armour.system_id).toBe('armour.fixed');
    // Nothing outside this block moved.
    expect(after.batteries[0].guns_item_id).toBe(before.batteries[0].guns_item_id);
    expect(after.batteries[0].mounts_item_id).toBe(before.batteries[0].mounts_item_id);
    expect(after.batteries[0].ammunition_item_id).toBe(before.batteries[0].ammunition_item_id);
    expect(after.batteries[0].system_id).toBe(before.batteries[0].system_id);
    expect(after.batteries[0].armour.face_mm).toBe(before.batteries[0].armour.face_mm);
  });

  it('turning the block off removes only the armour inputs', () => {
    const { document } = mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    fireEvent.change(screen.getByLabelText(copy('concept.armour.face')), { target: { value: '150' } });
    const box = screen.getByRole('checkbox', { name: copy('concept.armour.use') });
    fireEvent.click(box);
    const battery = armourOf(document());
    expect(battery).toBeUndefined();
    // The rest of the declared configuration, and the section itself, survive.
    expect(conceptEnabled(document())).toBe(true);
    expect((document() as Record<string, any>).concept_design.batteries[0].calibre_mm)
      .toBe(152.4);
  });

  it('states the single-column scope and the separate-counting requirement', () => {
    mount(enabledProject());
    fireEvent.click(screen.getByRole('checkbox', { name: copy('concept.armour.use') }));
    expect(screen.getByText(copy('concept.armour.scope'))).toBeTruthy();
    expect(copy('concept.armour.scope')).toMatch(/homogeneous/i);
    expect(copy('concept.armour.scope')).toMatch(/single-column|one mount group/i);
    expect(copy('concept.armour.separate')).toBeTruthy();
    expect(copyZh('concept.armour.scope')).toBeTruthy();
    expect(copyZh('concept.armour.separate')).toBeTruthy();
  });

  it('offers the new complete-armour role in the role picker and the quick assignment', () => {
    const base = enabledProject().concept_design as Record<string, any>;
    base.balance.roles = { [ARMOUR_ITEM]: 'gun_mount_armour' };
    const withArmour = patchBattery(base, 0, { armour: {
      system_id: 'weapons.main', item_id: ARMOUR_ITEM, face_mm: 150,
      rear_roof_mm: 100, barbette_mm: 75, freeboard_m: 4.6, super_factor: 1 } });
    expect(componentBindings(withArmour)[ARMOUR_ITEM]).toBe('gun_mount_armour');
    expect(mismatchedRoles(withArmour)).not.toContain(ARMOUR_ITEM);

    const mislabelled = patchBattery(base, 0, { armour: {
      system_id: 'weapons.main', item_id: ARMOUR_ITEM } });
    const balance = mislabelled.balance as Record<string, unknown>;
    const wrong = { ...mislabelled,
      balance: { ...balance, roles: { [ARMOUR_ITEM]: 'rotating_armour' } } };
    expect(mismatchedRoles(wrong)).toContain(ARMOUR_ITEM);

    mount({ ...baseProject(), concept_design: withArmour } as ProjectDocument);
    expect(screen.getAllByRole('option',
      { name: copy('concept.role.gun_mount_armour') }).length).toBeGreaterThan(0);
  });

  it('has both English and Chinese copy for every armour string it prints', () => {
    for (const key of ['concept.armour.use', 'concept.armour.scope', 'concept.armour.face',
      'concept.armour.side', 'concept.armour.barbette', 'concept.armour.freeboard',
      'concept.armour.super', 'concept.armour.item', 'concept.armour.system',
      'concept.armour.separate', 'concept.role.gun_mount_armour'] as const) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });
});

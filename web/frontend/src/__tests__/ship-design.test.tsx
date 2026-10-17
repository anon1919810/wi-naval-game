import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';

import * as api from '../api';
import { ShipDesignLedgerSection, ShipDesignOverview, useShipDesignHost } from '../components/ShipDesignEditor';
import { effectiveItemMass, mergeDesignReply } from '../components/shipDesign';
import { shipDesignOf, sourceViewOfShipDesign } from '../components/sps3b3Model';
import { shipDesignCopy } from '../i18n/shipDesign';
import type { DesignReply, ProjectDocument, ShipDesign, ShipDesignLedger, ShipDesignResult } from '../types';

vi.mock('../api', async original => ({
  ...await original<typeof import('../api')>(),
  designCatalog: vi.fn(), designPreview: vi.fn(), designInitialize: vi.fn(),
  designImportPreview: vi.fn(), designFromMigration: vi.fn(),
}));

const d = (key: Parameters<typeof shipDesignCopy>[1]) => shipDesignCopy('en', key);

const catalogue = {
  fields: {},
  page_order: ['hull', 'freeboard', 'guns', 'weapons', 'armour', 'engine', 'performance'],
  pages: Object.fromEntries(['hull', 'freeboard', 'guns', 'weapons', 'armour', 'engine', 'performance']
    .map(page => [page, { fields: [] }])),
};

function nativeDesign(over: Partial<ShipDesign> = {}): ShipDesign {
  return {
    schema: 'plimsoll-ship-design-1', condition_id: 'loaded', source: 'controlled test',
    parameters: {}, editing: {}, notes: null, mass_bindings: {}, ...over,
  };
}

const baseProject: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: 'Native test', revision: 1,
  hull: { lwl_m: 100, beam_m: 12 }, geometry: null,
  loading_conditions: [{ id: 'loaded', label: 'Loaded' }],
  weight_groups: [{ id: 'g1', label: 'Group', items: [{ id: 'sd-guns', mass_t: 0 }] }],
  ship_design: nativeDesign(),
};

/** The ledger the core reports for a fully declared design. */
const completeLedger: ShipDesignLedger = {
  schema: 'plimsoll-ship-design-ledger-1', owner: 'ship_design',
  condition_id: 'loaded', basis_condition_id: 'loaded',
  roles: {
    guns: { mode: 'estimated', estimate_t: 120, selected_mass_t: 120, target_mass_t: 120, difference_t: 0, item_ids: ['sd-guns'] },
    other: { mode: 'estimated', estimate_t: null, item_ids: [] },
  },
  selected_mass_t: 120, estimated_mass_t: 120, target_displacement_t: 120, difference_t: 0,
  needs_binding: [], complete: true,
};

const declaredLedger: ShipDesignLedger = {
  ...completeLedger,
  roles: {
    guns: { mode: 'declared', estimate_t: 120, selected_mass_t: 100, target_mass_t: 100, difference_t: 0, item_ids: ['sd-guns'] },
    other: { mode: 'estimated', estimate_t: null, item_ids: [] },
  },
};

function replyOf(project: ProjectDocument, ledger: ShipDesignLedger = completeLedger): DesignReply {
  const design = shipDesignOf(project) ?? nativeDesign();
  return {
    project,
    design: sourceViewOfShipDesign(design),
    preview: { schema: 'plimsoll-ship-design-result-1', status: 'available', ledger } as unknown as ShipDesignResult,
    status: 'available',
    diagnostics: [],
  };
}

/** One governed condition whose declared mass the core wrote for `sd-guns`. */
function declaredCondition(mass: number, owner = 'ship_design'): ProjectDocument['loading_conditions'] {
  return [{
    id: 'loaded', label: 'Loaded',
    overrides: { 'sd-guns': { mass_t: mass } },
    override_provenance: { 'sd-guns': { mass_t: { source: { owner, kind: 'set_declared_mass', manual: true } } } },
  }];
}

function Harness({ initial, onChangeSpy, file }: {
  initial: ProjectDocument;
  onChangeSpy?: (next: ProjectDocument) => void;
  file?: File;
}) {
  const [project, setProject] = useState<ProjectDocument>(initial);
  const [pending, setPending] = useState(0);
  const host = useShipDesignHost({
    project,
    onChange: next => { onChangeSpy?.(next); setProject(next); },
    onPendingChange: setPending,
  });
  const condition = project.loading_conditions.find(entry => entry.id === 'loaded');
  const overrides = condition?.overrides as Record<string, unknown> | undefined;
  return <div>
    <span data-testid="project-id">{project.id}</span>
    <span data-testid="hull">{JSON.stringify(project.hull)}</span>
    <span data-testid="pending">{pending}</span>
    <span data-testid="override">{JSON.stringify(overrides?.['sd-guns'] ?? null)}</span>
    <button type="button" data-testid="import" onClick={() => { if (file) host.importFile(file); }}>import</button>
    <ShipDesignLedgerSection host={host} disabled={false} />
    <ShipDesignOverview host={host} disabled={false} />
  </div>;
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(api.designCatalog).mockResolvedValue(catalogue as never);
  vi.mocked(api.designPreview).mockImplementation(async project => replyOf(project, completeLedger));
});
afterEach(cleanup);

it('blocks save/run during a legacy upgrade and adopts it under StrictMode', async () => {
  let finish!: (reply: DesignReply) => void;
  vi.mocked(api.designInitialize).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const legacy: ProjectDocument = { ...baseProject, sps_3b3_design: sourceViewOfShipDesign(nativeDesign()) };
  delete legacy.ship_design;
  render(<StrictMode><Harness initial={legacy} /></StrictMode>);
  await waitFor(() => expect(api.designInitialize).toHaveBeenCalled());
  await waitFor(() => expect(screen.getByTestId('pending')).toHaveTextContent('1'));
  await act(async () => { finish(replyOf(baseProject)); });
  expect(await screen.findByText(d('shipDesign.conditionHint'))).toBeVisible();
  await waitFor(() => expect(screen.getByTestId('pending')).toHaveTextContent('0'));
});

it('renders the native ledger role table and never counts an item-less optional role as pending', async () => {
  render(<Harness initial={baseProject} />);
  expect(await screen.findByRole('rowheader', { name: 'Guns' })).toBeVisible();
  expect(screen.getByRole('rowheader', { name: 'Other payload' })).toBeVisible();
  // `schema` and `owner` are ledger scalars, never roles.
  expect(screen.queryByRole('rowheader', { name: 'ship_design' })).toBeNull();
  expect(screen.queryByRole('rowheader', { name: 'schema' })).toBeNull();
  expect(screen.getByText(d('shipDesign.ledger.complete'))).toBeVisible();
  expect(screen.queryByText(d('shipDesign.ledger.needsBinding'))).toBeNull();
  expect(screen.queryByText(/Unbound ledger items/)).toBeNull();
});

it('adopts the declared mass a bind reply writes into the existing basis condition', () => {
  const latest: ProjectDocument = {
    ...baseProject,
    loading_conditions: [
      { id: 'loaded', label: 'Loaded', overrides: { 'sd-guns': { mass_t: 0, comment: 'mine' } },
        override_provenance: { 'sd-guns': { mass_t: { source: { owner: 'reader' } } } } },
      { id: 'reserve', label: 'Reserve' },
    ],
    sps_3b3_design: { schema: 'plimsoll-sps3b3-design-1', source: 'legacy', parameters: {}, editing: {}, notes: '' },
    ship_design: nativeDesign({ mass_bindings: { guns: { item_ids: ['sd-guns'], mode: 'declared' } } }),
  };
  const reply: ProjectDocument = {
    ...baseProject,
    loading_conditions: declaredCondition(123.4, 'ship_design'),
    ship_design: nativeDesign({ mass_bindings: { guns: { item_ids: ['sd-guns'], mode: 'declared' } } }),
  };
  const merged = mergeDesignReply(latest, reply);
  const condition = merged.loading_conditions.find(entry => entry.id === 'loaded')!;
  // The server-authored mass is adopted and the reader's own fields survive.
  expect((condition.overrides as Record<string, Record<string, unknown>>)['sd-guns'])
    .toMatchObject({ mass_t: 123.4, comment: 'mine' });
  expect((condition.override_provenance as Record<string, Record<string, unknown>>)['sd-guns'])
    .toMatchObject({ mass_t: { source: { owner: 'ship_design' } } });
  expect(merged.loading_conditions.find(entry => entry.id === 'reserve')).toBeDefined();
  // The native section retires the legacy one.
  expect((merged as Record<string, unknown>).sps_3b3_design).toBeUndefined();
});

it('writes a later declared mass back even though only the condition override changed', async () => {
  const initial: ProjectDocument = {
    ...baseProject, loading_conditions: declaredCondition(100),
    ship_design: nativeDesign({ mass_bindings: { guns: { item_ids: ['sd-guns'], mode: 'declared' } } }),
  };
  vi.mocked(api.designPreview).mockImplementation(async (_project, command) => {
    const next = (command as Record<string, unknown> | undefined)?.kind === 'set_declared_mass'
      ? { ...initial, loading_conditions: declaredCondition(250) } : initial;
    return replyOf(next, declaredLedger);
  });
  render(<Harness initial={initial} />);
  const input = await screen.findByLabelText('Declared mass Guns sd-guns');
  await waitFor(() => expect(input).toHaveValue(100));
  fireEvent.change(input, { target: { value: '250' } });
  fireEvent.blur(input);
  await waitFor(() => expect(api.designPreview).toHaveBeenCalledWith(
    expect.anything(), { kind: 'set_declared_mass', item_id: 'sd-guns', value: 250 }, expect.anything()));
  await waitFor(() => expect(screen.getByTestId('override').textContent).toContain('250'));
});

it('reads the effective declared mass from the own-case override, never a base zero', () => {
  const project: ProjectDocument = {
    ...baseProject, loading_conditions: declaredCondition(77),
    ship_design: nativeDesign({ condition_id: 'loaded' }),
  };
  expect(effectiveItemMass(project, 'sd-guns')).toBe(77);
  // A managed estimate is the core's overlay and wins while it is present.
  expect(effectiveItemMass({
    ...project,
    weight_groups: [{ id: 'g1', label: 'Group', items: [{ id: 'sd-guns', mass_t: 0, design_mass: { mass_t: 55 } }] }],
  }, 'sd-guns')).toBe(55);
  // With neither, the item's own base mass is the honest reading.
  expect(effectiveItemMass({ ...project, loading_conditions: [{ id: 'loaded', label: 'Loaded' }] }, 'sd-guns')).toBe(0);
});

it('drops a late reply that belongs to another project', async () => {
  const spy = vi.fn();
  vi.mocked(api.designPreview).mockImplementation(async () =>
    replyOf({ ...baseProject, id: 'p2', hull: { lwl_m: 999 } }, completeLedger));
  render(<Harness initial={baseProject} onChangeSpy={spy} />);
  // The ledger arrives, so the reply was consumed by the queue...
  expect(await screen.findByRole('rowheader', { name: 'Guns' })).toBeVisible();
  // ...and yet another project's project never reaches the draft.
  expect(spy).not.toHaveBeenCalled();
  expect(screen.getByTestId('project-id')).toHaveTextContent('p1');
  expect(screen.getByTestId('hull')).toHaveTextContent('"lwl_m":100');
});

it('leaves an untouched draft unedited when the settled reply is equal', async () => {
  const spy = vi.fn();
  vi.mocked(api.designPreview).mockImplementation(async () => replyOf(baseProject, completeLedger));
  render(<Harness initial={baseProject} onChangeSpy={spy} />);
  expect(await screen.findByRole('rowheader', { name: 'Guns' })).toBeVisible();
  expect(spy).not.toHaveBeenCalled();
});

it('counts a busy import as pending until it settles', async () => {
  let finish!: (reply: DesignReply) => void;
  vi.mocked(api.designImportPreview).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const file = { name: 'a.sship', arrayBuffer: async () => new ArrayBuffer(4) } as unknown as File;
  render(<Harness initial={baseProject} file={file} />);
  await waitFor(() => expect(api.designPreview).toHaveBeenCalled());
  expect(screen.getByTestId('pending')).toHaveTextContent('0');
  fireEvent.click(screen.getByTestId('import'));
  await waitFor(() => expect(api.designImportPreview).toHaveBeenCalledWith(expect.anything(), 'a.sship', expect.any(String)));
  await waitFor(() => expect(screen.getByTestId('pending')).toHaveTextContent('1'));
  await act(async () => { finish(replyOf(baseProject, completeLedger)); });
  await waitFor(() => expect(screen.getByTestId('pending')).toHaveTextContent('0'));
});

it('binds a role to its existing ledger item once, without a second owner', async () => {
  render(<Harness initial={baseProject} />);
  expect(await screen.findByRole('rowheader', { name: 'Guns' })).toBeVisible();
  const article = document.querySelector('article[data-role="guns"]') as HTMLElement;
  fireEvent.click(within(article).getByRole('button', { name: d('shipDesign.bind.apply') }));
  await waitFor(() => expect(api.designPreview).toHaveBeenCalledWith(
    expect.anything(), { kind: 'bind_mass', role: 'guns', item_ids: ['sd-guns'], mode: 'estimated' }, expect.anything()));
});

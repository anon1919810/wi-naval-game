import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useLayoutEffect, useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { DesignBalanceResults } from '../components/DesignBalanceResults';
import { StageStatus } from '../components/StageStatus';
import { compareReports } from '../components/reportComparison';
import { reportMetrics } from '../components/reportMetrics';
import { UnitProvider } from '../components/UnitProvider';
import {
  ARMOUR_DEFAULT_VALUE_KEYS, ARMOUR_DEFAULTS_METHOD, applyArmourDefaults, armourDefaultsEnabled,
  armourDefaultsOf, armourDefaultsReading, armourDefaultCandidate, newArmourDefaults,
  patchArmourDefaults, planArmourDefaults, removeArmourDefaults,
} from '../components/armourDefaults';
import { claimedTargetIds, componentBindings, newConcept } from '../components/conceptDesign';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import { workspaceCopy } from '../i18n/workspace';
import { zhCopy } from './locale';
import type { AnalysisResult, ProjectDocument, RunView, StageEnvelope } from '../types';
import * as api from '../api';

// The recovered default armour sizes are an ordinary declaration and one pure,
// explicit copy. This suite checks that turning the section on writes only the
// declaration, that the copy is atomic and preserves everything it must, that the
// stale guard retires a suggestion the current run cannot vouch for, and that the
// reading is shared between the workbench and the saved report under one gate.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const copy = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);
const copyZh = (key: ConceptKey) => conceptCopy('zh-CN', key);
const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;
const clone = <T,>(value: T): T => structuredClone(value);
const records = (raw: Record<string, unknown>): Record<string, any>[] =>
  (raw.fixed_armour as Record<string, any>[]) ?? [];

const SHA = '82ecc3fedf76af222dd13ad68258f3ae92146e9fad7dc6a4a96f3270fccf71fc';

// --- the payload the server returns -----------------------------------------

const VALUES: Record<string, number | null> = {
  main_length_m: 121.92, main_height_m: 7.62,
  ends_length_m: 18.0, ends_height_m: 5.2,
  upper_length_m: 110.0, upper_height_m: 3.0,
  bulkhead_length_m: 9.0, bulkhead_height_m: 5.2,
};

function availabilityOf(over: Record<string, unknown> = {}): Record<string, unknown> {
  const rows: Array<[string, unknown]> = ARMOUR_DEFAULT_VALUE_KEYS.map(([, , key]) =>
    [key, { state: 'available', reason: null }]);
  return Object.fromEntries(rows.concat(Object.entries(over)));
}

function reading(over: Record<string, unknown> = {}): Record<string, unknown> {
  return { id: 'armour_defaults', method_version: ARMOUR_DEFAULTS_METHOD, status: 'available',
    values: { ...VALUES }, availability: availabilityOf(),
    diagnostics: [], provenance: { method_version: ARMOUR_DEFAULTS_METHOD, source_sha256: SHA },
    ...over };
}

/** One `design_balance` payload that declares the default sizes. */
function payload(over: Record<string, unknown> = {}): Record<string, unknown> {
  return { schema: 'plimsoll-concept-balance-1', status: 'completed',
    method_version: 'sps-3b3-adapted-v1', values: {}, armour_defaults: reading(), ...over };
}

const DEFAULT_DATA = payload();

// --- the edited project, for the form ---------------------------------------

const LEDGER = { id: 'weights', label: 'declared concept design',
  items: [{ id: 'weapons.guns', mass_t: 60.9628, x_m: 104 }] };
const SYSTEMS = { weapons: { main: { weight_item_ids: ['weapons.guns'] } } };

const BELT = { id: 'main_belt', kind: 'belt_main', system_id: 'weapons.main', item_id: 'weapons.guns',
  source: 'the yard’s own belt table', thickness_mm: 254, length_m: 100.5, height_m: 4.0 };
const BELT_2 = { id: 'main_belt_2', kind: 'belt_main', system_id: null, item_id: null,
  source: '', thickness_mm: 203, length_m: null, height_m: null };
const BULKHEAD = { id: 'bh_1', kind: 'bulkhead', system_id: null, item_id: null,
  source: 'the bulkhead table', thickness_mm: 152, length_m: null, height_m: null };
const DECK = { id: 'deck_1', kind: 'deck', system_id: null, item_id: null, source: '',
  thickness_mm: 100, coverage_index: 0 };

function defaultsConfig(records: Record<string, unknown>[]): Record<string, any> {
  const declared = newConcept() as Record<string, any>;
  declared.source = 'a declared study design';
  declared.fixed_armour = clone(records);
  return declared;
}

function project(declared: Record<string, any>): ProjectDocument {
  return {
    schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [LEDGER], systems: SYSTEMS, concept_design: declared,
  } as unknown as ProjectDocument;
}

// --- the run and stage envelopes --------------------------------------------

function stage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return { status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
    method_versions: { coordinator: 'analysis-1', kernel: 'sps-3b3-adapted-v1',
      methods: { armour_defaults: ARMOUR_DEFAULTS_METHOD } },
    validity: { complete: true, converged: null, model_applicable: null, historical_validated: null },
    data, ...over };
}

function result(stages: Record<string, StageEnvelope>): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1',
    condition_id: 'normal', project_fingerprint: 'p', input_fingerprint: 'i',
    request_fingerprint: 'r', request: {}, input_snapshot: {} as never, units: { mass: 't' },
    method_versions: { coordinator: 'analysis-1' }, sources: {}, diagnostics: [],
    validity: { complete: true, converged: null, model_applicable: null, historical_validated: null },
    stages } as unknown as AnalysisResult;
}

function balanceRun(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): RunView {
  return { id: 'run-a', project_id: 'p1', revision: 1, condition_id: 'normal', status: 'completed',
    request_fingerprint: 'r', created_at: '', started_at: null, finished_at: null,
    cancel_requested: false, error: null,
    result: result({ design_balance: stage(data, over) }) } as unknown as RunView;
}

/** The saved full report renders the reading under the strict requested-and-completed gate. */
function report(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}) {
  render(<UnitProvider preferences={null}>
    <StageStatus name="design_balance" stage={stage(data, over)} />
  </UnitProvider>);
}

// --- the concept editor harness ---------------------------------------------

interface HarnessProps {
  initial: ProjectDocument;
  run?: RunView | null;
  identity?: string;
  dirty?: boolean;
  requestCurrent?: boolean;
  preferences?: unknown;
  capture: ProjectDocument[];
}

function Harness({ initial, run = null, identity = 'id-1', dirty = false, requestCurrent = false,
  preferences = null, capture }: HarnessProps) {
  const [draft, setDraft] = useState(initial);
  return <UnitProvider preferences={preferences as never}>
    <ConceptDesignEditor project={draft} run={run} identity={identity} dirty={dirty}
      requestCurrent={requestCurrent}
      onChange={next => { setDraft(next); capture.push(next); }} />
  </UnitProvider>;
}

function mount(initial: ProjectDocument, props: Partial<HarnessProps> = {}) {
  const capture: ProjectDocument[] = [];
  const view = render(<Harness initial={initial} capture={capture} {...props} />);
  return { view, document: () => capture[capture.length - 1] ?? initial };
}

const panel = () =>
  screen.getByText(copy('concept.group.armourDefaults')).closest('div.form-card') as HTMLElement;

const enable = () => fireEvent.click(screen.getByRole('checkbox', {
  name: copy('concept.armourDefaults.use') }));

function fillCheckbox(recordId: string, field: ConceptKey) {
  return screen.getByRole('checkbox', { name: copy('concept.armourDefaults.fill',
    { record: recordId, field: copy(field) }) });
}
const copyButton = () => screen.getByRole('button', { name: copy('concept.armourDefaults.copy') });

beforeEach(() => { cleanup(); vi.clearAllMocks(); vi.mocked(api.listProjects).mockResolvedValue([]); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('the default-size section is an ordinary, optional declaration', () => {
  it('is absent from a project that never enabled it, so an old project is untouched', () => {
    const { document } = mount(project(defaultsConfig([BELT])));
    expect(armourDefaultsEnabled(config(document()))).toBe(false);
    expect('armour_defaults' in config(document())).toBe(false);
    const box = within(panel()).getByRole('checkbox', { name: copy('concept.armourDefaults.use') });
    expect(box).not.toBeChecked();
    // The whole section is the switch while it is off.
    expect(within(panel()).queryByLabelText(copy('concept.armourDefaults.source'))).toBeNull();
  });

  it('writes one source and two fractions, all null until they are set', () => {
    const { document } = mount(project(defaultsConfig([BELT])));
    enable();
    expect(config(document()).armour_defaults)
      .toEqual({ source: null, forecastle_fraction: null, quarterdeck_fraction: null });
    expect(armourDefaultsEnabled(config(document()))).toBe(true);
    fireEvent.change(screen.getByLabelText(copy('concept.armourDefaults.source')),
      { target: { value: 'the recovered sizing rule' } });
    expect(config(document()).armour_defaults.source).toBe('the recovered sizing rule');
    fireEvent.change(screen.getByLabelText(copy('concept.armourDefaults.forecastle')),
      { target: { value: '0.1' } });
    expect(config(document()).armour_defaults.forecastle_fraction).toBe(0.1);
    // A cleared source is unknown, not an empty claim of a source.
    fireEvent.change(screen.getByLabelText(copy('concept.armourDefaults.source')), { target: { value: '' } });
    expect(config(document()).armour_defaults.source).toBeNull();
  });

  it('turns off by removing only the declaration, and is idempotent', () => {
    const declared = { ...defaultsConfig([BELT]),
      armour_defaults: { source: 'x', forecastle_fraction: 0.1, quarterdeck_fraction: null } };
    const { document } = mount(project(declared));
    const before = document();
    enable();
    expect(config(document()).armour_defaults).toBeNull();
    expect(config(document()).fixed_armour).toEqual(config(before).fixed_armour);
    expect(config(document()).balance).toEqual(config(before).balance);
    expect(removeArmourDefaults(removeArmourDefaults(config(document()))).armour_defaults).toBeNull();
    expect(newArmourDefaults())
      .toEqual({ source: null, forecastle_fraction: null, quarterdeck_fraction: null });
    expect(patchArmourDefaults({ armour_defaults: null }, { source: 'x' }))
      .toMatchObject({ armour_defaults: { source: 'x', forecastle_fraction: null,
        quarterdeck_fraction: null } });
    expect(armourDefaultsOf({ armour_defaults: null })).toBeNull();
  });

  it('claims no ledger target, so it can never enter the component bindings', () => {
    const declared = defaultsConfig([BELT]);
    const declaredBefore = claimedTargetIds(declared);
    const enabled = { ...declared, armour_defaults: newArmourDefaults() };
    expect(claimedTargetIds(enabled)).toEqual(declaredBefore);
    expect(componentBindings(enabled)).toEqual(componentBindings(declared));
    expect(JSON.stringify(componentBindings(enabled))).not.toMatch(/armour_defaults/);
  });
});

describe('the pure copy writes one atomic draft and preserves everything else', () => {
  const one = [{ record_id: 'main_belt', fields: ['length_m'] }];

  it('fills one dimension, keeping the id, binding, thickness, other dimension and source text', () => {
    const declared = defaultsConfig([BELT]);
    const before = clone(declared);
    const next = applyArmourDefaults(declared, reading(), one as never, 'run-a');
    // The input is untouched; the copy is a new draft.
    expect(declared).toEqual(before);
    expect(next).not.toBe(declared);
    const record = records(next)[0];
    expect(record).toMatchObject({ id: 'main_belt', kind: 'belt_main', system_id: 'weapons.main',
      item_id: 'weapons.guns', thickness_mm: 254, height_m: 4.0, length_m: 121.92 });
    // One plain annotation, naming the method and the source run; the old text stays.
    expect(record.source).toContain('the yard’s own belt table');
    expect(record.source).toContain(ARMOUR_DEFAULTS_METHOD);
    expect(record.source).toContain('run-a');
    // No mass is adopted and nothing else is written.
    expect(record).not.toHaveProperty('mass_t');
    expect('update_proposals' in next).toBe(false);
    expect(next.batteries).toEqual(before.batteries);
    expect(JSON.stringify(next)).not.toMatch(/adopt/i);
  });

  it('fills several same-kind records individually, all or nothing', () => {
    const declared = defaultsConfig([BELT, BELT_2]);
    const before = clone(declared);
    const next = applyArmourDefaults(declared, reading(),
      [{ record_id: 'main_belt', fields: ['length_m', 'height_m'] },
        { record_id: 'main_belt_2', fields: ['height_m'] }] as never, 'run-a');
    expect(declared).toEqual(before);
    const first = records(next)[0];
    const second = records(next)[1];
    expect(first.length_m).toBe(121.92);
    expect(first.height_m).toBe(7.62);
    expect(second.height_m).toBe(7.62);
    // An empty source becomes the annotation alone.
    expect(second.source).toBe(`[${ARMOUR_DEFAULTS_METHOD} · run run-a]`);
    expect(second.length_m).toBeNull();
  });

  it('is idempotent: applying the same annotation twice never repeats it', () => {
    const declared = defaultsConfig([BELT]);
    const once = applyArmourDefaults(declared, reading(), one as never, 'run-a');
    const twice = applyArmourDefaults(once, reading(), one as never, 'run-a');
    expect(records(twice)[0].source).toBe(records(once)[0].source);
  });

  it('leaves the whole draft unchanged when any part of the selection is invalid', () => {
    const cases: Array<[string, Record<string, unknown>, unknown]> = [
      ['unavailable', reading({ availability: availabilityOf({
        main_length_m: { state: 'unavailable', reason: 'the hull draught is unknown' } }) }),
        [{ record_id: 'main_belt', fields: ['length_m'] }]],
      ['unknown', reading({ values: { ...VALUES, main_length_m: null } }),
        [{ record_id: 'main_belt', fields: ['length_m'] }]],
      ['out-of-domain', reading({ values: { ...VALUES, bulkhead_length_m: 9000 } }),
        [{ record_id: 'main_belt', fields: ['length_m'] }, { record_id: 'bh_1', fields: ['length_m'] }]],
    ];
    for (const [name, preview, selections] of cases) {
      const declared = defaultsConfig([BELT, BULKHEAD]);
      const before = clone(declared);
      const next = applyArmourDefaults(declared, preview, selections as never, 'run-a');
      // No record is half-written: the whole selection is refused together.
      expect(next, name).toEqual(before);
      expect(declared, name).toEqual(before);
    }
  });

  it('refuses every reason it cannot honestly copy, before writing anything', () => {
    const declared = defaultsConfig([BELT, DECK]);
    const sel = [{ record_id: 'main_belt', fields: ['length_m'] }];
    const reason = (preview: unknown, selections: unknown, runId: string | null) =>
      planArmourDefaults(declared, preview as never, selections as never, runId).reason;
    expect(reason(reading(), sel, '')).toBe('no-run');
    expect(reason(null, sel, 'run-a')).toBe('method-conflict');
    expect(reason(reading({ method_version: 'sps-3b3-armour-defaults-v2' }), sel, 'run-a'))
      .toBe('method-conflict');
    expect(reason(reading(), [], 'run-a')).toBe('no-selection');
    expect(reason(reading(), [{ record_id: 'nope', fields: ['length_m'] }], 'run-a'))
      .toBe('missing-record');
    expect(reason(reading(), [{ record_id: 'deck_1', fields: ['length_m'] }], 'run-a'))
      .toBe('illegal-kind');
    expect(reason(reading(), [{ record_id: 'main_belt', fields: [] }], 'run-a')).toBe('no-fields');
    expect(reason(reading(), [{ record_id: 'main_belt', fields: ['length_m', 'length_m'] }], 'run-a'))
      .toBe('duplicate-field');
    expect(reason(reading(), [{ record_id: 'main_belt', fields: ['thickness_mm'] }], 'run-a'))
      .toBe('illegal-field');
    expect(reason(reading(), [{ record_id: 'main_belt', fields: ['length_m'] },
      { record_id: 'main_belt', fields: ['height_m'] }], 'run-a')).toBe('repeated-record');
    expect(reason(reading(), [{ record_id: '', fields: ['length_m'] }], 'run-a')).toBe('invalid-id');
    // A duplicated identifier in the declaration cannot be filled either.
    const duplicated = defaultsConfig([BELT, { ...BELT }]);
    const duplicate = [{ record_id: 'main_belt', fields: ['length_m'] }];
    expect(planArmourDefaults(duplicated, reading(), duplicate as never, 'run-a').reason)
      .toBe('duplicate-record');
  });

  it('reports each dimension’s own availability and selectability without computing', () => {
    const preview = reading({ availability: availabilityOf({
      main_length_m: { state: 'unavailable', reason: 'no main draught' } }) });
    const unavailable = armourDefaultCandidate(preview, 'belt_main', 'length_m');
    expect(unavailable).toMatchObject({ value: 121.92, available: false, selectable: false,
      reason: 'no main draught' });
    const ok = armourDefaultCandidate(preview, 'belt_main', 'height_m');
    expect(ok).toMatchObject({ value: 7.62, available: true, selectable: true });
    const outside = armourDefaultCandidate(reading({ values: { ...VALUES, ends_length_m: 6000 } }),
      'belt_ends', 'length_m');
    expect(outside).toMatchObject({ available: true, selectable: false });
  });
});

describe('the panel copies only from the current saved run', () => {
  it('refuses copying when the stage method is missing or conflicts with its record', () => {
    for (const methods of [{}, { armour_defaults: 'different-method' }]) {
      cleanup();
      mount(project(defaultsConfig([BELT])), { run: balanceRun(DEFAULT_DATA,
        { method_versions: { methods } }), requestCurrent: true });
      enable();
      fireEvent.click(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength'));
      expect(copyButton()).toBeDisabled();
    }
  });

  it('retires choices in the first committed render before passive effects run', () => {
    const declared = defaultsConfig([BELT]); declared.armour_defaults = newArmourDefaults();
    const initial = project(declared); const observed: boolean[] = [];
    function Frame({ identity }: { identity: string }) {
      useLayoutEffect(() => { observed.push((copyButton() as HTMLButtonElement).disabled); }, [identity]);
      return <Harness initial={initial} capture={[]} run={{ ...balanceRun(DEFAULT_DATA), id: identity }}
        identity={identity} requestCurrent />;
    }
    const view = render(<Frame identity="run-a" />);
    fireEvent.click(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength'));
    expect(copyButton()).toBeEnabled();
    view.rerender(<Frame identity="run-b" />);
    expect(observed.at(-1)).toBe(true);
  });

  it('discloses run inputs and full canonical metres before copying under feet display', () => {
    const value = 121.923456789;
    const raw = reading({ values: { ...VALUES, main_length_m: value }, provenance: {
      inputs: { length_m: 152, beam_m: 18.3, draught_m: 5.2, block_coeff: .5,
        freeboard_m: 4.6, forecastle_fraction: .2, quarterdeck_fraction: .15 } } });
    mount(project(defaultsConfig([BELT])), { run: balanceRun(payload({ armour_defaults: raw })),
      requestCurrent: true, preferences: { length: 'ft' } });
    enable();
    expect(within(panel()).getByText(/run-a/)).toBeVisible();
    expect(within(panel()).getByText(`${value} m`)).toBeVisible();
    expect(within(panel()).getByText('152 m')).toBeVisible();
  });
  it('offers nothing to copy without a current, matching, saved run', () => {
    mount(project(defaultsConfig([BELT])), { run: null, requestCurrent: true });
    enable();
    expect(panel().textContent).toContain(copy('concept.armourDefaults.stale'));
    expect(copyButton()).toBeDisabled();
  });

  it('retires the suggestion when the draft has unsaved edits', () => {
    mount(project(defaultsConfig([BELT])), { run: balanceRun(DEFAULT_DATA), requestCurrent: true, dirty: true });
    enable();
    expect(panel().textContent).toContain(copy('concept.armourDefaults.stale'));
    expect(copyButton()).toBeDisabled();
  });

  it('retires the suggestion when the request options no longer match', () => {
    mount(project(defaultsConfig([BELT])), { run: balanceRun(DEFAULT_DATA), requestCurrent: false });
    enable();
    expect(copyButton()).toBeDisabled();
  });

  it('copies the chosen dimensions into the draft from a matching run', () => {
    const { document } = mount(project(defaultsConfig([BELT, BULKHEAD])),
      { run: balanceRun(DEFAULT_DATA), requestCurrent: true });
    enable();
    expect(panel().textContent).toContain(copy('concept.armourDefaults.choose'));
    fireEvent.click(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength'));
    fireEvent.click(fillCheckbox('bh_1', 'concept.armourDefaults.bulkheadHeight'));
    expect(panel().textContent).toContain(copy('concept.armourDefaults.ready'));
    fireEvent.click(copyButton());
    expect(config(document()).fixed_armour[0].length_m).toBe(121.92);
    expect(config(document()).fixed_armour[1].height_m).toBe(5.2);
    expect(config(document()).fixed_armour[1].source).toContain('run-a');
    // No proposals are required for any of this, and nothing else changes.
    expect(config(document()).fixed_armour[0].source).toContain('the yard’s own belt table');
  });

  it('shows a dimension it cannot select as unavailable, with the server’s reason', () => {
    mount(project(defaultsConfig([BELT])),
      { run: balanceRun(payload({ armour_defaults: reading({ availability: availabilityOf({
        main_length_m: { state: 'unavailable', reason: 'the side draught is unknown' } }) }) })),
      requestCurrent: true });
    enable();
    expect(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength')).toBeDisabled();
    expect(panel().textContent).toContain('the side draught is unknown');
  });

  it('retires a selection when the saved identity changes', () => {
    const initial = project(defaultsConfig([BELT]));
    const props = { run: balanceRun(DEFAULT_DATA), requestCurrent: true };
    const { view } = mount(initial, { ...props, identity: 'id-1' });
    enable();
    fireEvent.click(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength'));
    expect(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength')).toBeChecked();
    // A different result retires the choice: a checkbox never approves a run it
    // was not set for.
    view.rerender(<Harness initial={initial} capture={[]} {...props} identity="id-2" />);
    expect(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength')).not.toBeChecked();
  });

  it.each(['identity','requestCurrent','dirty'])('permanently retires choices after %s changes and returns', key => {
    const initial=project(defaultsConfig([BELT]));
    const props={run:balanceRun(DEFAULT_DATA),requestCurrent:true,dirty:false,identity:'id-1'};
    const {view}=mount(initial,props);enable();
    fireEvent.click(fillCheckbox('main_belt','concept.armourDefaults.mainLength'));
    const changed={...props,[key]:key==='identity'?'id-2':key==='dirty'};
    view.rerender(<Harness initial={initial} capture={[]} {...changed}/>);
    view.rerender(<Harness initial={initial} capture={[]} {...props}/>);
    expect(fillCheckbox('main_belt','concept.armourDefaults.mainLength')).not.toBeChecked();
    expect(copyButton()).toBeDisabled();
  });

  it('shows the canonical metres in the reader’s own unit but copies exact metres', () => {
    const { document } = mount(project(defaultsConfig([BELT])),
      { run: balanceRun(DEFAULT_DATA), requestCurrent: true, preferences: { length: 'ft' } });
    enable();
    // 121.92 m and 7.62 m are exactly 400 ft and 25 ft.
    expect(within(panel()).getByText('400 ft')).toBeVisible();
    expect(within(panel()).getByText('25 ft')).toBeVisible();
    fireEvent.click(fillCheckbox('main_belt', 'concept.armourDefaults.mainLength'));
    fireEvent.click(copyButton());
    // The saved value is the canonical, unrounded metre, never the shown feet.
    expect(config(document()).fixed_armour[0].length_m).toBe(121.92);
  });
});

describe('the default-size reading is one shared projection under one gate', () => {
  const armour = (): HTMLElement =>
    screen.getByText(copy('balance.armourDefaults.title')).closest('section') as HTMLElement;

  it('prints the eight sizes in metres with the source beside them', () => {
    report(DEFAULT_DATA);
    const card = armour();
    expect(within(card).getByText('121.92 m')).toBeVisible();
    expect(within(card).getByText('7.62 m')).toBeVisible();
    expect(within(card).getByText('18 m')).toBeVisible();
    expect(within(card).getByText(copy('balance.armourDefaults.note'))).toBeVisible();
    expect(within(card).getByText(copy('balance.armourDefaults.method',
      { method: ARMOUR_DEFAULTS_METHOD, source: SHA }))).toBeVisible();
  });

  it('names a dimension the core could not derive as unavailable, never as zero', () => {
    report(payload({ armour_defaults: reading({ values: { ...VALUES, bulkhead_height_m: null },
      availability: availabilityOf({
        bulkhead_height_m: { state: 'unavailable', reason: 'the block coefficient is unknown' } }) }) }));
    const card = armour();
    expect(within(card).getByText(/the block coefficient is unknown/)).toBeVisible();
    expect(within(card).queryByText('0 m')).toBeNull();
  });

  it('adds no section when the feature was never declared', () => {
    report({ schema: 'plimsoll-concept-balance-1', status: 'completed', values: {} });
    expect(screen.queryByText(copy('balance.armourDefaults.title'))).toBeNull();
    const run = balanceRun({ schema: 'plimsoll-concept-balance-1', status: 'completed', values: {} });
    expect(armourDefaultsReading(run)).toBeNull();
  });

  it('stays readable in the workbench while the parent stage is only partial', () => {
    render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={balanceRun(DEFAULT_DATA, { status: 'partial' as StageEnvelope['status'] })} available />
    </UnitProvider>);
    expect(screen.getByText(copy('balance.armourDefaults.title'))).toBeVisible();
    expect(screen.getByText('121.92 m')).toBeVisible();
    // The saved full report keeps the stricter requested-and-completed gate.
    cleanup();
    report(DEFAULT_DATA, { status: 'partial' as StageEnvelope['status'] });
    expect(screen.queryByText(copy('balance.armourDefaults.title'))).toBeNull();
  });

  it('withholds the reading from a completed envelope that was never requested', () => {
    report(DEFAULT_DATA, { requested: false, status: 'not_requested' });
    expect(screen.queryByText(copy('balance.armourDefaults.title'))).toBeNull();
  });

  it('reads the same reading in the workbench and the report, under each policy', () => {
    const run = balanceRun(DEFAULT_DATA, { status: 'partial' as StageEnvelope['status'] });
    const { unmount } = render(<UnitProvider preferences={null}>
      <DesignBalanceResults run={run} available />
    </UnitProvider>);
    const workbench = screen.getByText(copy('balance.armourDefaults.title')).textContent;
    unmount();
    report(DEFAULT_DATA);
    expect(screen.getByText(copy('balance.armourDefaults.title')).textContent).toBe(workbench);
  });
});

describe('keyed default-size metrics for the comparison', () => {
  const ids = (m: ReturnType<typeof reportMetrics>) =>
    m.filter(x => x.id.startsWith('armour_defaults:')).map(x => x.id).sort();

  it('keys every dimension by the record’s stable id at a canonical metre', () => {
    const metrics = reportMetrics('design_balance', stage(DEFAULT_DATA));
    expect(ids(metrics)).toEqual(ARMOUR_DEFAULT_VALUE_KEYS.map(([, , key]) =>
      `armour_defaults:armour_defaults:${key}`).sort());
    expect(metrics.find(m => m.id === 'armour_defaults:armour_defaults:main_length_m'))
      .toMatchObject({ key: 'main_length_m', dimension: 'length', storedUnit: 'm', blocked: false,
        value: 121.92 });
  });

  it('blocks a missing id, an unavailable record or a mismatched method', () => {
    const cases: Array<[string, Record<string, unknown>]> = [
      ['missing', payload({ armour_defaults: { ...reading(), id: null } })],
      ['unavailable', payload({ armour_defaults: { ...reading(), status: 'unavailable' } })],
      ['mismatch', payload({ armour_defaults: { ...reading(),
        method_version: 'sps-3b3-armour-defaults-v2' } })],
    ];
    for (const [name, data] of cases) {
      const metrics = reportMetrics('design_balance', stage(data));
      expect(metrics.filter(m => m.id.startsWith('armour_defaults:')).every(m => m.blocked), name)
        .toBe(true);
    }
  });

  it('withholds a delta per dimension when that dimension is unavailable, keeping the rest', () => {
    const before = stage(DEFAULT_DATA);
    const after = stage(payload({ armour_defaults: reading({ values: { ...VALUES, ends_length_m: 19.0 },
      availability: availabilityOf({
        main_length_m: { state: 'unavailable', reason: 'the side draught is unknown' } }) }) }));
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    // The unavailable dimension is incompatible at once: no number is attributed.
    const held = cells.find(c => c.path.endsWith('values.main_length_m'))!;
    expect(held).toMatchObject({ state: 'incompatible' });
    expect(held.delta).toBeNull();
    // A valid partial number is still comparable: the derived end length moved.
    const moved = cells.find(c => c.path.endsWith('values.ends_length_m'))!;
    expect(moved.state).toBe('known');
    expect(moved.delta).toBeCloseTo(1.0, 9);
  });

  it('shows a delta when both parents completed and the saved method matches', () => {
    const before = stage(DEFAULT_DATA);
    const after = stage(payload({ armour_defaults: reading({ values: { ...VALUES, main_length_m: 122.5 } }) }));
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    const cell = cells.find(c => c.path.endsWith('values.main_length_m'))!;
    expect(cell.state).toBe('known');
    expect(cell.dimension).toBe('length');
    expect(cell.delta).toBeCloseTo(0.58, 9);
  });

  it('withholds the delta when a stage method changed between the two runs', () => {
    const before = stage(DEFAULT_DATA);
    const after = stage(DEFAULT_DATA, { method_versions: { coordinator: 'analysis-1',
      kernel: 'sps-3b3-adapted-v1', methods: { armour_defaults: 'sps-3b3-armour-defaults-v2' } } });
    const cells = compareReports({ result: result({ design_balance: before }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    expect(cells.filter(c => c.path.includes('armour_defaults')).every(c => c.delta === null)).toBe(true);
  });

  it('withholds the delta when the parent stage did not run on one side', () => {
    const after = stage(DEFAULT_DATA, { requested: false, status: 'not_requested' as StageEnvelope['status'] });
    const cells = compareReports({ result: result({ design_balance: stage(DEFAULT_DATA) }) },
      { result: result({ design_balance: after }) }, (k, p) => zhCopy(k as never, p))
      .groups.flatMap(g => g.cells);
    expect(cells.filter(c => c.path.includes('armour_defaults')).every(c => c.state === 'unrequested'))
      .toBe(true);
  });

  it('names every new default-size metric in both languages', () => {
    for (const [, , key] of ARMOUR_DEFAULT_VALUE_KEYS) {
      const english = workspaceCopy('en', `data.${key}` as never);
      const chinese = zhCopy(`data.${key}` as never);
      expect(english, key).not.toBe(`data.${key}`);
      expect(english.trim(), key).not.toBe('');
      expect(chinese.trim(), key).not.toBe('');
      expect(chinese, key).not.toBe(english);
    }
  });
});

describe('every word the default-size section prints exists in both languages', () => {
  it('keeps English and Chinese for the panel, the reading and the labels', () => {
    for (const key of ['concept.group.armourDefaults', 'concept.armourDefaults.note',
      'concept.armourDefaults.use', 'concept.armourDefaults.source',
      'concept.armourDefaults.sourceHint', 'concept.armourDefaults.forecastle',
      'concept.armourDefaults.quarterdeck', 'concept.armourDefaults.fractionHint',
      'concept.armourDefaults.previewTitle', 'concept.armourDefaults.previewNote',
      'concept.armourDefaults.noPreview', 'concept.armourDefaults.method',
      'concept.armourDefaults.selectTitle', 'concept.armourDefaults.selectNote',
      'concept.armourDefaults.noRecords', 'concept.armourDefaults.duplicateRecord',
      'concept.armourDefaults.fill', 'concept.armourDefaults.state.available',
      'concept.armourDefaults.state.unavailable', 'concept.armourDefaults.copy',
      'concept.armourDefaults.stale', 'concept.armourDefaults.choose',
      'concept.armourDefaults.refuse', 'concept.armourDefaults.ready',
      'concept.armourDefaults.annotation',
      'concept.armourDefaults.mainLength', 'concept.armourDefaults.mainHeight',
      'concept.armourDefaults.endsLength', 'concept.armourDefaults.endsHeight',
      'concept.armourDefaults.upperLength', 'concept.armourDefaults.upperHeight',
      'concept.armourDefaults.bulkheadLength', 'concept.armourDefaults.bulkheadHeight',
      'balance.armourDefaults.title', 'balance.armourDefaults.note',
      'balance.armourDefaults.method', 'balance.armourDefaults.unavailable',
      'balance.armourDefaults.diagnostics', 'balance.armourDefaults.state.available',
      'balance.armourDefaults.state.unavailable'] as ConceptKey[]) {
      expect(copy(key).trim(), key).not.toBe('');
      expect(copyZh(key).trim(), key).not.toBe('');
      expect(copyZh(key), key).not.toBe(copy(key));
    }
  });
});

import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../api';
import { QuantityField, QuantityListField } from '../components/QuantityField';
import { buildOptions, EMPTY_REQUEST } from '../components/PerformanceEditor';
import { UnitProvider } from '../components/UnitProvider';
import { FloodingResults } from '../components/FloodingResults';
import { EnginesEditor } from '../components/EnginesEditor';
import { Workbench } from '../pages/Workbench';
import type { AnalysisResult, ProjectDocument, RunView } from '../types';
import {
  burnRateText, classifyKey, displayUnit, fromDisplay, readPreferences, toDisplay, unitLabel,
} from '../components/units';
import { completedFixture } from './fixtures';

// Display units are a reading choice. These tests pin the exact factors, the
// storage-unit semantics of a field, the unknown/zero rules, and the fact that
// saving or switching a preference never rewrites the stored canonical value.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), enqueueRun: vi.fn(), getRun: vi.fn() }));

const FT = readPreferences({ length: 'ft' });
const KG = readPreferences({ mass: 'kg' });
const KG_FT = readPreferences({ mass: 'kg', length: 'ft' });
const SHP = readPreferences({ power: 'shp' });
const MS = readPreferences({ speed: 'm_s' });
const RAD = readPreferences({ angle: 'rad' });

const project: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '单位样例', revision: 1,
  hull: { loa_m: 100, lwl_m: 98, beam_m: 12, draught_normal_m: 5, block_coeff: 0.62 },
  geometry: null,
  weight_groups: [{ id: 'structure', label: '结构', items: [
    { id: 'plate', mass_t: 250, x_m: 3, y_m: 0, kg_m: 5, source: 'survey', estimate: false }] }],
  loading_conditions: [{ id: 'normal', label: '正常', overrides: {} }],
  systems: { armour: { fixed: { weight_item_ids: ['plate'],
    page_rows: [{ row: 'belt', thickness_mm: 229, extents_m: { aft_m: -30, fore_m: 30 },
      weight_item_ids: ['plate'], typed: { height_m: 9, construction_type: 'belt' }, source: 'survey', estimate: false }] } } },
};

let saved: ProjectDocument = project;

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  saved = structuredClone(project);
  vi.mocked(api.getProject).mockImplementation(async () => ({ project_id: 'p1', revision: 1, project: structuredClone(saved) }));
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.getRun).mockRejectedValue(new Error('no stored result'));
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) => {
    saved = structuredClone(input.project) as ProjectDocument;
    return { project_id: 'p1', revision: 2, project: structuredClone(saved) };
  });
  vi.mocked(api.enqueueRun).mockResolvedValue({ id: 'run-1' } as RunView);
});

function harness(preferences: unknown, children: React.ReactNode) {
  return render(<UnitProvider preferences={preferences}>{children}</UnitProvider>);
}

describe('unit factors are exact and reversible', () => {
  it('converts the six reader dimensions with the core factors', () => {
    expect(toDisplay('length', 1, FT)).toBeCloseTo(1 / 0.3048, 12);
    expect(toDisplay('mass', 1, KG)).toBe(1000);
    expect(toDisplay('mass', 1, readPreferences({ mass: 'long_ton' }))).toBeCloseTo(1 / 1.0160469088, 12);
    expect(toDisplay('power', 1, SHP)).toBeCloseTo(1 / 0.7456998715822702, 12);
    expect(toDisplay('speed', 1, MS)).toBeCloseTo(1852 / 3600, 12);
    expect(toDisplay('angle', 1, RAD)).toBeCloseTo(Math.PI / 180, 12);
  });

  it('inverts every conversion back to the stored value', () => {
    for (const [dimension, prefs] of [['length', FT], ['mass', KG], ['power', SHP], ['speed', MS], ['angle', RAD]] as const) {
      expect(fromDisplay(dimension, toDisplay(dimension, 7.25, prefs), prefs)).toBeCloseTo(7.25, 12);
    }
    // Derived quantities convert by the matching exponent of their base length.
    expect(toDisplay('area', 100, FT)).toBeCloseTo(100 / 0.3048 ** 2, 10);
    expect(toDisplay('volume', 1000, FT)).toBeCloseTo(1000 / 0.3048 ** 3, 6);
  });

  it('keeps a field stored in another unit correct in both directions', () => {
    // 500 kg is 0.5 t; a kilogram field must not be read as 500 tonnes.
    expect(toDisplay('mass', 500, readPreferences({ mass: 't' }), 'kg')).toBe(0.5);
    expect(toDisplay('mass', 500, KG, 'kg')).toBe(500);
    expect(fromDisplay('mass', 0.6, readPreferences({ mass: 't' }), 'kg')).toBeCloseTo(600, 9);
    // 229 mm of plate reads as feet for a foot reader and saves back as mm.
    expect(toDisplay('length', 229, FT, 'mm')).toBeCloseTo(0.229 / 0.3048, 9);
    expect(fromDisplay('length', 0.8, FT, 'mm')).toBeCloseTo(243.84, 6);
  });

  it('labels units for the reader and keeps compounds explicit', () => {
    expect(unitLabel('length', displayUnit('length', FT))).toBe('ft');
    expect(unitLabel('area', displayUnit('area', FT))).toBe('ft²');
    expect(unitLabel('volume', displayUnit('volume', FT))).toBe('ft³');
    expect(unitLabel('mass', displayUnit('mass', readPreferences({ mass: 'long_ton' })))).toBe('long ton');
    expect(unitLabel('speed', displayUnit('speed', MS))).toBe('m/s');
    expect(unitLabel('angle', displayUnit('angle', RAD))).toBe('rad');
    expect(unitLabel('angle', 'deg')).toBe('°');
    // A defined compound: the day is fixed while the mass component follows the
    // reader's mass unit.
    expect(burnRateText(40, KG)).toBe('40,000 kg/day');
    expect(burnRateText(40, readPreferences({ mass: 'long_ton' }))).toBe('39.368261 long ton/day');
    expect(burnRateText(40, readPreferences({ mass: 't' }))).toBe('40 t/day');
  });

  it('never converts a density, viscosity, rate, force or time', () => {
    for (const key of ['density_kg_m3', 'fluid_density_t_m3', 'rho_t_m3', 'kinematic_viscosity_m2_s',
      'burn_t_per_day', 'total_resistance_kn', 'roll_period_s', 'qpc']) {
      expect(classifyKey(key), key).toBeNull();
    }
    expect(classifyKey('speed_kn')).toEqual({ dimension: 'speed' });
    expect(classifyKey('projectile_mass_kg')).toEqual({ dimension: 'mass', storedUnit: 'kg' });
    expect(classifyKey('awp_m2')).toEqual({ dimension: 'area' });
    expect(classifyKey('kg_m')).toEqual({ dimension: 'length' });
    expect(classifyKey('ledger_mass_t')).toEqual({ dimension: 'mass' });
  });

  it('falls back to canonical units for an old project without preferences', () => {
    const preferences = readPreferences(undefined);
    expect(preferences).toEqual({ length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' });
    // An unsupported stored value is never honoured.
    expect(readPreferences({ length: 'mm', mass: 'stone' })).toEqual({
      length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg',
    });
  });
});

describe('quantity fields type in the reader unit and store canonical', () => {
  it('daily fuel input describes its denominator and stores tonnes per day', () => {
    const change = vi.fn();
    const doc = { ...project, endurance_scenarios: [{ id: 'study', fuels: { coal: { burn_t_per_day: 40 } } }] };
    harness(KG, <EnginesEditor project={doc} run={null} onChange={change} />);
    const input = screen.getByLabelText('study coal burn_t_per_day');
    expect(input).toHaveAccessibleDescription('kg/day');
    expect(input).toHaveValue(40000);
    fireEvent.change(input, { target: { value: '50000' } });
    expect(change.mock.calls[0][0].endurance_scenarios[0].fuels.coal.burn_t_per_day).toBe(50);
  });
  it('flooding time remains seconds with foot display preferences', () => {
    harness(FT, <FloodingResults data={{ scenario: { duration_s: 60 }, final_state: { time_s: 60 },
      timeline: [{ time_s: 60, equilibrium: {} }] }} />);
    const cells = within(screen.getByRole('table')).getAllByRole('cell');
    expect(cells[0]).toHaveTextContent(/^60$/);
    expect(screen.queryByText('196.850394')).not.toBeInTheDocument();
  });
  it('invalid list input cannot submit the previous valid request', () => {
    const change = vi.fn();
    const view = harness(MS, <QuantityListField label="速度采样" value={[10, 20]} dimension="speed" onChange={change} />);
    fireEvent.change(view.getByLabelText('速度采样'), { target: { value: '5, invalid' } });
    const speeds = change.mock.calls[0][0];
    expect(buildOptions({ ...EMPTY_REQUEST, scenario: 'study', speeds }).error).toBeTruthy();
    fireEvent.change(view.getByLabelText('速度采样'), { target: { value: '5, 10' } });
    expect(buildOptions({ ...EMPTY_REQUEST, scenario: 'study', speeds: change.mock.calls[1][0] }).error).toBe('');
  });
  function field(preferences: unknown, stored: number | null, storedUnit?: string, onChange = vi.fn()) {
    const view = render(<UnitProvider preferences={preferences}>
      <QuantityField label="船长" value={stored} dimension="length" storedUnit={storedUnit} onChange={onChange} />
    </UnitProvider>);
    return { input: view.getByLabelText('船长') as HTMLInputElement, onChange };
  }

  it('shows the reader unit and converts a typed value back to canonical', () => {
    const change = vi.fn();
    const { input } = field(FT, 100, 'm', change);
    expect(input.value).toBe('328.0839895013123');
    fireEvent.change(input, { target: { value: '328.084' } });
    // 328.084 ft is stored as the metre value it represents.
    expect(change).toHaveBeenCalledTimes(1);
    expect(change.mock.calls[0][0]).toBeCloseTo(100.0000032, 6);
  });

  it('keeps unknown null and an exact zero exact', () => {
    const change = vi.fn();
    const { input } = field(KG_FT, null, 't', change);
    expect(input.value).toBe('');
    fireEvent.change(input, { target: { value: '0' } });
    expect(change.mock.calls[0][0]).toBe(0);
  });

  it('rebases a focused field when the preference switches mid-edit', () => {
    const change = vi.fn();
    const view = render(<UnitProvider preferences={{ length: 'm' }}>
      <QuantityField label="船长" value={100} dimension="length" onChange={change} />
    </UnitProvider>);
    const input = view.getByLabelText('船长') as HTMLInputElement;
    fireEvent.focus(input);
    expect(input.value).toBe('100');
    // The reader switches to feet while the field is focused.
    view.rerender(<UnitProvider preferences={{ length: 'ft' }}>
      <QuantityField label="船长" value={100} dimension="length" onChange={change} />
    </UnitProvider>);
    expect(input.value).toBe('328.0839895013123');
    fireEvent.change(input, { target: { value: '100' } });
    // 100 ft must be stored as metres, not as the previous 100 m.
    expect(change.mock.calls[0][0]).toBeCloseTo(30.48, 9);
  });

  it('converts a typed sample list and preserves order', () => {
    const change = vi.fn();
    const view = render(<UnitProvider preferences={MS}>
      <QuantityListField label="速度采样" value={[10, 12]} dimension="speed" onChange={change} />
    </UnitProvider>);
    const input = view.getByLabelText('速度采样') as HTMLInputElement;
    // 10 kn is 5.144444 m/s in a metre-per-second reading.
    expect(input.value.startsWith('5.14444')).toBe(true);
    // A new list (11 kn and 13 kn) so the controlled input really changes.
    const typed = [11, 13].map(value => String(toDisplay('speed', value, MS))).join(', ');
    fireEvent.change(input, { target: { value: typed } });
    // typed is a genuinely new list, so the controlled input fires a change.
    const stored = (change.mock.calls[0]?.[0] ?? []) as number[];
    expect(stored.length).toBe(2);
    expect(stored[0]).toBeCloseTo(11, 5);
    expect(stored[1]).toBeCloseTo(13, 5);
    expect(input.value).toBe(typed);
  });
});

describe('workbench display units', () => {
  async function open(chapter: string, preferences?: Record<string, string>) {
    // Reopening always starts from the last saved revision, as the real page does.
    const doc = { ...structuredClone(saved), display_preferences: preferences };
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: doc });
    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: chapter }));
  }
  async function persist(): Promise<ProjectDocument> {
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    return saved;
  }

  it('converts hull, weight and armour inputs while saving canonical metres, tonnes and millimetres', async () => {
    await open('船型与几何', { length: 'ft', mass: 'kg' });
    const length = await screen.findByLabelText('船长');
    expect(length).toHaveValue(328.0839895013123);
    fireEvent.change(length, { target: { value: '196.85' } });
    fireEvent.click(screen.getByRole('button', { name: '重量与载荷' }));
    const mass = await screen.findByLabelText('structure plate 质量');
    expect(mass).toHaveValue(250000);
    fireEvent.change(mass, { target: { value: '300000' } });
    fireEvent.click(screen.getByRole('button', { name: '装甲与武备' }));
    const thickness = await screen.findByLabelText('belt 厚度 · mm') as HTMLInputElement;
    // 229 mm reads as feet, not as 229 ft.
    expect(Number(thickness.value)).toBeCloseTo(0.229 / 0.3048, 6);
    fireEvent.change(thickness, { target: { value: '0.98425' } });
    const doc = await persist();
    expect(doc.hull.loa_m).toBeCloseTo(59.9998, 3);
    expect(doc.weight_groups[0].items[0].mass_t).toBe(300);
    expect((doc.systems as any).armour.fixed.page_rows[0].thickness_mm).toBeCloseTo(300, 1);
    // No other field, provenance or ledger identity was disturbed.
    expect(doc.weight_groups[0].items[0].source).toBe('survey');
    expect(doc.hull.block_coeff).toBe(0.62);
  });

  it('does not drift when the preference is switched repeatedly', async () => {
    await open('船型与几何', { length: 'm' });
    fireEvent.change(await screen.findByLabelText('船长'), { target: { value: '101' } });
    const doc = await persist();
    expect(doc.hull.loa_m).toBe(101);
    // Switching to feet and back must show the same numbers every time: the
    // stored metre value is the only thing that persists.
    const footReadings: string[] = [];
    for (const preference of ['ft', 'm', 'ft']) {
      cleanup();
      await open('船型与几何', { length: preference });
      footReadings.push(((await screen.findByLabelText('船长')) as HTMLInputElement).value);
      cleanup();
      await open('船型与几何', { length: 'm' });
    }
    expect(Number(footReadings[0])).toBeCloseTo(101 / 0.3048, 6);
    expect(footReadings[0]).toBe(footReadings[2]);
    expect(Number(footReadings[1])).toBe(101);
    // No preference switch ever rewrote the stored value.
    expect(saved.hull.loa_m).toBe(101);
  });

  it('leaves a dimensionless hull coefficient as a plain number', async () => {
    await open('船型与几何', { length: 'ft' });
    const coefficient = await screen.findByLabelText('方形系数') as HTMLInputElement;
    expect(coefficient).toHaveValue(0.62);
    fireEvent.change(coefficient, { target: { value: '0.61' } });
    const doc = await persist();
    expect(doc.hull.block_coeff).toBe(0.61);
  });
});

describe('stored results and the immutable report', () => {
  function result(preferences?: Record<string, string>): AnalysisResult {
    const result = structuredClone(completedFixture);
    result.input_snapshot = { ...result.input_snapshot, display_preferences: preferences ?? {} };
    result.stages.hydrostatics = {
      status: 'completed', requested: true, reason: null,
      validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
      method_versions: {}, assumptions: [], diagnostics: [],
      data: { total_mass_t: 27200, awp_m2: 1450, volume_m3: 27200, heel_deg: 0 },
    };
    // A second stage carries the canonical-only quantities: density, force,
    // burn rate and period must never take a reader unit.
    result.stages.propulsion = {
      status: 'completed', requested: true, reason: null,
      validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
      method_versions: {}, assumptions: [], diagnostics: [],
      data: { burn_t_per_day: 40, coal_t: 120, rho_t_m3: 1.025, density_kg_m3: 1025,
        total_resistance_kn: 1800, roll_period_s: 12.5, range_nm: 3200 },
    };
    return result;
  }

  async function reportFor(preferences?: Record<string, string>, compare?: AnalysisResult) {
    const { Report } = await import('../pages/Report');
    const data = result(preferences);
    render(<Report result={data} runId="run-7" compareResult={compare} />);
    return data;
  }

  it('converts stage values, keeps densities and forces canonical', async () => {
    await reportFor({ length: 'ft', mass: 'kg', angle: 'rad' });
    // A stored tonne mass reads as kilograms; an area reads as square feet.
    expect(screen.getAllByText('27,200,000 kg').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/15,607\.670104 ft²/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('120,000 kg').length).toBeGreaterThan(0);
    // Densities, forces, rates and times keep their canonical unit.
    expect(screen.getByText('1.025 t/m³')).toBeVisible();
    expect(screen.getByText('1,025 kg/m³')).toBeVisible();
    expect(screen.getByText('1,800 kN')).toBeVisible();
    expect(screen.getByText('40 t/day')).toBeVisible();
    expect(screen.getByText('12.5 s')).toBeVisible();
  });

  it('converts both comparison sides and the difference by the row key', async () => {
    const left = result({ length: 'ft', mass: 'kg' });
    const right = structuredClone(left);
    right.stages.hydrostatics.data = { ...left.stages.hydrostatics.data, total_mass_t: 27000, awp_m2: 1400, volume_m3: 27000 };
    right.stages.propulsion.data = { ...left.stages.propulsion.data, coal_t: 110, total_resistance_kn: 1750 };
    await reportFor({ length: 'ft', mass: 'kg' }, right);
    const table = screen.getByRole('table');
    const cells = within(table).getAllByRole('cell').map(cell => cell.textContent ?? '');
    // 200 t difference reads as 200,000 kg, and 50 m³ of area/volume as ft³.
    expect(cells.some(cell => cell.includes('200,000 kg'))).toBe(true);
    expect(cells.some(cell => cell.includes('ft³'))).toBe(true);
  });

  it('keeps a report local override from touching the stored snapshot', async () => {
    const data = await reportFor({ mass: 't' });
    const original = JSON.stringify(data);
    const snapshot = data.input_snapshot;
    const massSelect = screen.getByLabelText('报告mass显示单位');
    fireEvent.change(massSelect, { target: { value: 'kg' } });
    expect(screen.getAllByText('27,200,000 kg').length).toBeGreaterThan(0);
    // The immutable result object is untouched: exports and fingerprints keep
    // the canonical units they were saved with.
    expect(snapshot.display_preferences).toEqual({ mass: 't' });
    expect(snapshot.weight_groups).toEqual([]);
    expect(JSON.stringify(snapshot)).not.toContain('27200000');
    expect(JSON.stringify(data)).toBe(original);
  });
});

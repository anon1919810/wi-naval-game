import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ConceptDesignEditor } from '../components/ConceptDesignEditor';
import { ConceptComponentReadings } from '../components/ConceptComponentReadings';
import { compareReports } from '../components/reportComparison';
import { reportMetrics } from '../components/reportMetrics';
import { UnitProvider } from '../components/UnitProvider';
import {
  ARMOUR_GEOMETRY_METHOD, armourGeometryEnabled, armourGeometryOf, armourGeometryPlates,
  armourGeometryReferences, armourGeometryRegions, duplicateArmourGeometryPlateIds,
  duplicateArmourGeometryRegions, invalidArmourGeometryReferences, newConcept,
} from '../components/conceptDesign';
import { conceptCopy, type ConceptKey } from '../i18n/concept';
import { workspaceCopy } from '../i18n/workspace';
import { zhCopy } from './locale';
import type { AnalysisResult, ProjectDocument, StageEnvelope } from '../types';
import * as api from '../api';

// The geometric armour panels are one optional declaration of scope, an explicit
// set of regions and plates, and one pair of read-only server readings per
// region. This suite checks that enabling chooses nothing, that a selected region
// is an explicit opt-in whose fixed record is protected while linked, that the
// form invents no density or size, that the readings keep area, volume and mass
// in their right units, and that the comparison gates geometry on a requested and
// completed parent.

vi.mock('../api', async original => ({ ...await original<typeof import('../api')>(),
  listProjects: vi.fn(), createProject: vi.fn() }));

const c = (key: ConceptKey, params?: Record<string, string | number>) =>
  conceptCopy('en', key, params);

const GEOM_METHOD = ARMOUR_GEOMETRY_METHOD;

function fixedRecord(id: string, kind: string, over: Record<string, unknown> = {}) {
  return { id, kind, system_id: null, item_id: null, source: '',
    thickness_mm: null, length_m: null, height_m: null, ...over };
}

function plate(id: string, over: Record<string, unknown> = {}) {
  return { id, source: null, density_source: null, length_m: null, width_m: null,
    thickness_mm: null, density_kg_m3: null, count: null, width_basis: null,
    inclination_deg: null, ...over };
}

function region(fixedId: string, over: Record<string, unknown> = {}) {
  return { fixed_armour_id: fixedId, source: null, plates: [], ...over };
}

function project(over: Record<string, unknown> = {}): ProjectDocument {
  return { schema: 'plimsoll-project-1', id: 'p1', name: 'concept', revision: 1,
    hull: { lwl_m: 152, beam_m: 18.3, draught_normal_m: 5.2, block_coeff: 0.5 },
    geometry: null, loading_conditions: [{ id: 'normal', label: 'Normal' }],
    weight_groups: [], systems: {},
    concept_design: { ...newConcept(), fixed_armour: [], ...over } } as unknown as ProjectDocument;
}

const config = (document: unknown): Record<string, any> =>
  (document as Record<string, any>).concept_design as Record<string, any>;

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

const geometryPanel = () =>
  screen.getByText(c('concept.group.armourGeometry')).closest('div.form-card') as HTMLElement;

const enable = () =>
  fireEvent.click(screen.getByRole('checkbox', { name: c('concept.armourGeometry.use') }));

beforeEach(() => {
  cleanup(); vi.clearAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => { vi.unstubAllGlobals(); });

// --- the declaration form ----------------------------------------------------

describe('the geometric armour panel declaration', () => {
  it('is absent until enabled, then declares no region and invents nothing', () => {
    const { document } = mount(project());
    expect(armourGeometryEnabled(config(document()))).toBe(false);
    expect('armour_geometry' in config(document())).toBe(false);
    enable();
    // Enabled but empty: no region is chosen for the reader and the selection is
    // an explicit empty list, never an unknown one.
    expect(armourGeometryOf(config(document()))).toEqual({ source: null, regions: [] });
    expect(armourGeometryRegions(config(document()))).toEqual([]);
    expect(within(geometryPanel())
      .queryByLabelText(`${c('concept.armourGeometry.regionRecord')} 1`)).toBeNull();
  });

  it('opts a region in explicitly and offers only eligible fixed records', () => {
    const { document } = mount(project({
      fixed_armour: [fixedRecord('belt_main_1', 'belt_main'), fixedRecord('bulge_1', 'bulge')] }));
    enable();
    fireEvent.click(screen.getByRole('button', { name: c('concept.armourGeometry.addRegion') }));
    const section = config(document()).armour_geometry;
    expect(section.regions).toHaveLength(1);
    // A new region references nothing yet and declares no plate.
    expect(section.regions[0]).toEqual({ fixed_armour_id: null, source: null, plates: [] });
    const select = screen.getByLabelText(`${c('concept.armourGeometry.regionRecord')} 1`);
    const options = within(select).getAllByRole('option').map(option => option.textContent);
    expect(options).toContain('belt_main_1');
    // A curved bulge is outside the rectangular model; its old capability stays.
    expect(options).not.toContain('bulge_1');
    fireEvent.change(select, { target: { value: 'belt_main_1' } });
    expect(config(document()).armour_geometry.regions[0].fixed_armour_id).toBe('belt_main_1');
  });

  it('adds, edits and removes plates and regions as explicit declarations', () => {
    const { document } = mount(project({ fixed_armour: [fixedRecord('belt_main_1', 'belt_main')] }));
    enable();
    fireEvent.click(screen.getByRole('button', { name: c('concept.armourGeometry.addRegion') }));
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.regionRecord')} 1`),
      { target: { value: 'belt_main_1' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.regionSource')} 1`),
      { target: { value: 'study plan' } });

    fireEvent.click(screen.getByRole('button', { name: c('concept.armourGeometry.addPlate') }));
    const plateOf = () => armourGeometryPlates(armourGeometryRegions(config(document()))[0])[0];
    // Every dimension, count and basis starts unknown: no plate is invented.
    expect(plateOf()).toEqual(plate(''));
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.plateId')} 1`),
      { target: { value: 'plate_1' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.length')} 1`),
      { target: { value: '10' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.width')} 1`),
      { target: { value: '2' } });
    // The field is shown in the reader’s length unit and stored in millimetres.
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.thickness')} 1`),
      { target: { value: '0.1' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.density')} 1`),
      { target: { value: '7850' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.count')} 1`),
      { target: { value: '2' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.widthBasis')} 1`),
      { target: { value: 'projected' } });
    fireEvent.change(screen.getByLabelText(`${c('concept.armourGeometry.angle')} 1`),
      { target: { value: '60' } });
    expect(plateOf()).toMatchObject({ id: 'plate_1', length_m: 10, width_m: 2, thickness_mm: 100,
      density_kg_m3: 7850, count: 2, width_basis: 'projected', inclination_deg: 60 });
    // The canonical metres/mm persist whatever the display preference is.
    expect(config(document()).armour_geometry.regions[0].source).toBe('study plan');

    fireEvent.click(screen.getByRole('button', { name: c('concept.armourGeometry.removePlate') }));
    expect(armourGeometryPlates(armourGeometryRegions(config(document()))[0])).toEqual([]);
    fireEvent.click(screen.getByRole('button', { name: c('concept.armourGeometry.removeRegion') }));
    expect(armourGeometryRegions(config(document()))).toEqual([]);
  });

  it('protects a referenced fixed region from deletion, rename and kind change', () => {
    const initial = project({
      fixed_armour: [fixedRecord('belt_main_1', 'belt_main')],
      armour_geometry: { source: 'root', regions: [region('belt_main_1', { source: 'r' })] } });
    const { document } = mount(initial);
    // The reader is told, where the record is, that the geometry holds it.
    expect(screen.getByText(c('concept.armourGeometry.linkProtect'))).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: c('concept.fixedArmour.remove') }));
    expect(config(document()).fixed_armour).toHaveLength(1);
    expect(screen.getAllByRole('alert').map(node => node.textContent).join(' '))
      .toContain(c('concept.armourGeometry.linkProtect'));
    fireEvent.change(screen.getByLabelText(c('concept.fixedArmour.id')), { target: { value: 'renamed' } });
    expect(config(document()).fixed_armour[0].id).toBe('belt_main_1');
    fireEvent.change(screen.getByLabelText(c('concept.fixedArmour.kind')), { target: { value: 'bulge' } });
    expect(config(document()).fixed_armour[0].kind).toBe('belt_main');
  });

  it('names an unknown reference and never clears it', () => {
    const initial = project({
      fixed_armour: [fixedRecord('belt_main_1', 'belt_main')],
      armour_geometry: { source: 'root', regions: [region('ghost')] } });
    mount(initial);
    expect(invalidArmourGeometryReferences(config(initial))).toEqual(['ghost']);
    const alert = within(geometryPanel()).getByRole('alert');
    expect(alert).toHaveTextContent(c('concept.armourGeometry.invalidRegion'));
    expect(alert).toHaveTextContent('ghost');
    // The dangling reference is kept exactly as the reader left it.
    expect(armourGeometryReferences(config(initial))).toEqual(['ghost']);
  });

  it('warns when a fixed region or a plate id is declared more than once', () => {
    const initial = project({
      fixed_armour: [fixedRecord('belt_main_1', 'belt_main')],
      armour_geometry: { source: null, regions: [
        region('belt_main_1', { plates: [plate('p1'), plate('p1')] }),
        region('belt_main_1'),
      ] } });
    mount(initial);
    expect(duplicateArmourGeometryRegions(config(initial))).toEqual(['belt_main_1']);
    expect(screen.getByText(`${c('concept.armourGeometry.duplicateRegion')} belt_main_1`)).toBeVisible();
    expect(duplicateArmourGeometryPlateIds(armourGeometryRegions(config(initial))[0])).toEqual(['p1']);
    // Both copies of the repeated plate are flagged, so the warning appears twice.
    expect(screen.getAllByText(c('concept.armourGeometry.duplicatePlate', { id: 'p1' }))).not.toHaveLength(0);
  });
});

// --- the readings ------------------------------------------------------------

const PLATE_A = {
  id: 'plate_1', method_version: GEOM_METHOD, status: 'available', adoptable: true,
  values: { area_m2: 40, volume_m3: 4, mass_t: 31.4 },
  diagnostics: [], provenance: { plate_source: 'plate drawing', density_source: 'material declaration' },
};

const GEOM = {
  id: 'belt_main_1', method_version: GEOM_METHOD, status: 'available', adoptable: true,
  values: { area_m2: 40, volume_m3: 4, mass_t: 31.4, known_mass_subtotal_t: 20 },
  records: [PLATE_A],
  diagnostics: [],
  provenance: { method_version: GEOM_METHOD, source: 'study', region_source: 'region drawing' },
};

function readings(data: Record<string, unknown>, over: Partial<StageEnvelope> = {},
  policy: 'independent' | 'report' = 'independent') {
  const envelope = { status: 'completed', requested: true, ...over } as StageEnvelope;
  return render(<UnitProvider preferences={null}>
    <ConceptComponentReadings data={data} envelope={envelope} policy={policy} /></UnitProvider>);
}

describe('the geometric panel reading', () => {
  it('prints region and plate area, volume and mass with their units', () => {
    readings({ armour_geometry: [GEOM] });
    expect(screen.getByText(c('balance.armourGeometry.title'))).toBeVisible();
    // The region and its single plate read the same box, so each figure appears twice.
    expect(screen.getAllByText('40 m²')).toHaveLength(2);
    expect(screen.getAllByText('4 m³')).toHaveLength(2);
    expect(screen.getAllByText('31.4 t')).toHaveLength(2);
    expect(screen.getByText('20 t')).toBeVisible();
    expect(screen.getByText('belt_main_1')).toBeVisible();
    expect(screen.getByText('plate_1')).toBeVisible();
    expect(screen.getByText(c('balance.armourGeometry.adoptable'))).toBeVisible();
    expect(screen.getByText(c('balance.armourGeometry.method', {
      method: GEOM_METHOD, source: 'study · region drawing' }))).toBeVisible();
    expect(screen.getByText(c('balance.armourGeometry.method', {
      method: GEOM_METHOD, source: 'plate drawing · material declaration' }))).toBeVisible();
  });

  it('keeps a mathematically available but non-adoptable panel visible', () => {
    readings({ armour_geometry: [{ ...GEOM,
      adoptable: false, provenance: { ...GEOM.provenance, declared_source: null } }] });
    // The numbers are still the server's readings; only adoption is withheld.
    expect(screen.getAllByText('40 m²')).toHaveLength(2);
    expect(screen.getByText(c('balance.armourGeometry.notAdoptable'))).toBeVisible();
  });

  it('adds no section when geometry was never declared and hides numbers behind the gate', () => {
    const { rerender } = readings({ other: 1 });
    expect(screen.queryByText(c('balance.armourGeometry.title'))).toBeNull();
    rerender(<UnitProvider preferences={null}>
      <ConceptComponentReadings data={{ armour_geometry: [GEOM] }}
        envelope={{ requested: true, status: 'failed' } as StageEnvelope} policy="report" /></UnitProvider>);
    expect(screen.queryByText('40 m²')).toBeNull();
  });

  it('marks the recovered empirical reading inactive when geometry replaced it', () => {
    readings({ fixed_armour: [{ id: 'belt_main_1', method_version: 'sps-adapted-v1',
      status: 'available', values: { total_long_tons: 10, mass_t: 10 },
      active_mass_model: 'geometry' }] });
    expect(screen.getByText(c('balance.fixedArmour.geometryInactive'))).toBeVisible();
  });
});

// --- the comparison metrics --------------------------------------------------

function stage(status: StageEnvelope['status'], data: StageEnvelope['data']): StageEnvelope {
  return { status, requested: true, reason: null,
    validity: { complete: status === 'completed', converged: null, model_applicable: null, historical_validated: null },
    method_versions: {}, assumptions: [], diagnostics: [], data };
}

function conceptStage(data: Record<string, unknown>, over: Partial<StageEnvelope> = {}): StageEnvelope {
  return { ...stage('completed', data),
    method_versions: { methods: { armour_geometry: GEOM_METHOD } }, ...over };
}

function result(stageEnvelope: StageEnvelope): AnalysisResult {
  return { schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1',
    condition_id: 'normal', project_fingerprint: 'p', input_fingerprint: 'i', request_fingerprint: 'r',
    request: {}, input_snapshot: {}, units: { mass: 't' }, method_versions: {}, sources: {},
    diagnostics: [], validity: { complete: true, converged: null, model_applicable: null,
      historical_validated: null }, stages: { design_balance: stageEnvelope } } as unknown as AnalysisResult;
}

function clone<T>(value: T): T { return structuredClone(value); }

const geometryIds = (metrics: ReturnType<typeof reportMetrics>) =>
  metrics.filter(metric => metric.id.startsWith('armour_geometry:')).map(metric => metric.id).sort();

describe('keyed geometry metrics for the comparison', () => {
  it('keys by stable region and plate ids and states area, volume and mass units', () => {
    const metrics = reportMetrics('design_balance', conceptStage({ armour_geometry: [GEOM] }));
    expect(metrics.find(metric => metric.id === 'armour_geometry:belt_main_1:values.area_m2'))
      .toMatchObject({ key: 'armour_geometry_area_m2', dimension: 'area', blocked: false });
    expect(metrics.find(metric => metric.id === 'armour_geometry:belt_main_1:values.volume_m3'))
      .toMatchObject({ key: 'armour_geometry_volume_m3', dimension: 'volume' });
    expect(metrics.find(metric => metric.id === 'armour_geometry:belt_main_1:values.mass_t'))
      .toMatchObject({ key: 'armour_geometry_mass_t', dimension: 'mass', storedUnit: 't' });
    expect(metrics.find(metric => metric.id === 'armour_geometry:belt_main_1:values.known_mass_subtotal_t'))
      .toMatchObject({ key: 'armour_geometry_known_mass_subtotal_t', dimension: 'mass' });
    expect(metrics.find(metric => metric.id === 'armour_geometry:belt_main_1:plate_1:mass_t'))
      .toMatchObject({ key: 'armour_geometry_plate_mass_t', dimension: 'mass', storedUnit: 't' });
  });

  it('gates geometry metrics on a requested and completed stage', () => {
    expect(geometryIds(reportMetrics('design_balance',
      conceptStage({ armour_geometry: [GEOM] }, { requested: false })))).toEqual([]);
    expect(geometryIds(reportMetrics('design_balance',
      conceptStage({ armour_geometry: [GEOM] }, { status: 'failed' })))).toEqual([]);
    expect(geometryIds(reportMetrics('design_balance',
      conceptStage({ armour_geometry: [GEOM] })))).not.toEqual([]);
  });

  it('blocks a repeated, missing, unavailable or method-mismatched region or plate', () => {
    const cases: Array<[string, Record<string, unknown>]> = [
      ['duplicate', { armour_geometry: [GEOM, { ...GEOM }] }],
      ['missing', { armour_geometry: [{ ...GEOM, id: null }] }],
      ['unavailable', { armour_geometry: [{ ...GEOM, status: 'unavailable' }] }],
      ['mismatch', { armour_geometry: [{ ...GEOM, method_version: 'plimsoll-armour-panels-v2' }] }],
      ['plate-mismatch', { armour_geometry: [{ ...GEOM,
        records: [{ ...PLATE_A, method_version: 'other' }] }] }],
      ['plate-duplicate', { armour_geometry: [{ ...GEOM, records: [PLATE_A, { ...PLATE_A }] }] }],
    ];
    for (const [name, patch] of cases) {
      const metrics = reportMetrics('design_balance', conceptStage(patch));
      expect(geometryIds(metrics).length, name).toBeGreaterThan(0);
      expect(metrics.filter(metric => metric.id.startsWith('armour_geometry:')).every(metric => metric.blocked),
        name).toBe(true);
    }
  });

  it('matches reordered records by id and reports no delta', () => {
    const two = { ...GEOM, records: [PLATE_A, { ...PLATE_A, id: 'plate_2', values: { area_m2: 10, volume_m3: 1, mass_t: 7.85 } }] };
    const before = conceptStage({ armour_geometry: [two] });
    const reordered = clone({ armour_geometry: [two] }) as Record<string, unknown>;
    (reordered.armour_geometry as any[])[0].records.reverse();
    const after = conceptStage(reordered);
    expect(geometryIds(reportMetrics('design_balance', before)))
      .toEqual(geometryIds(reportMetrics('design_balance', after)));
    const cells = compareReports({ result: result(before) }, { result: result(after) },
      (key, params) => zhCopy(key as never, params)).groups.flatMap(group => group.cells);
    expect(cells.filter(cell => cell.path.includes('armour_geometry')).every(cell => cell.delta === 0))
      .toBe(true);
  });

  it('names every new geometry word in both languages', () => {
    const keys: ConceptKey[] = [
      'concept.group.armourGeometry', 'concept.armourGeometry.note',
      'concept.armourGeometry.use', 'concept.armourGeometry.source',
      'concept.armourGeometry.sourceHint', 'concept.armourGeometry.replace',
      'concept.armourGeometry.separate', 'concept.armourGeometry.noRegion',
      'concept.armourGeometry.addRegion', 'concept.armourGeometry.regionMax',
      'concept.armourGeometry.regionRecord', 'concept.armourGeometry.chooseRegion',
      'concept.armourGeometry.regionHint', 'concept.armourGeometry.noEligible',
      'concept.armourGeometry.regionSource', 'concept.armourGeometry.regionSourceHint',
      'concept.armourGeometry.removeRegion', 'concept.armourGeometry.invalidRegion',
      'concept.armourGeometry.duplicateRegion', 'concept.armourGeometry.plates',
      'concept.armourGeometry.platesHint', 'concept.armourGeometry.noPlate',
      'concept.armourGeometry.addPlate', 'concept.armourGeometry.plateMax',
      'concept.armourGeometry.removePlate', 'concept.armourGeometry.plateId',
      'concept.armourGeometry.plateSource', 'concept.armourGeometry.densitySource',
      'concept.armourGeometry.densitySourceHint', 'concept.armourGeometry.length',
      'concept.armourGeometry.lengthHint', 'concept.armourGeometry.width',
      'concept.armourGeometry.thickness', 'concept.armourGeometry.density',
      'concept.armourGeometry.densityHint', 'concept.armourGeometry.count',
      'concept.armourGeometry.countHint', 'concept.armourGeometry.widthBasis',
      'concept.armourGeometry.basisUnknown', 'concept.armourGeometry.basis.developed',
      'concept.armourGeometry.basis.projected', 'concept.armourGeometry.basisRequired',
      'concept.armourGeometry.angle', 'concept.armourGeometry.angleVertical',
      'concept.armourGeometry.angleHorizontal', 'concept.armourGeometry.angleUnknown',
      'concept.armourGeometry.angleUsed', 'concept.armourGeometry.angleUnused',
      'concept.armourGeometry.invalidPlateId', 'concept.armourGeometry.duplicatePlate',
      'concept.armourGeometry.linkProtect',
      'balance.armourGeometry.title', 'balance.armourGeometry.whole',
      'balance.armourGeometry.method', 'balance.armourGeometry.totals',
      'balance.armourGeometry.note', 'balance.armourGeometry.area',
      'balance.armourGeometry.volume', 'balance.armourGeometry.mass',
      'balance.armourGeometry.knownSubtotal', 'balance.armourGeometry.plates',
      'balance.armourGeometry.plate', 'balance.armourGeometry.adoptable',
      'balance.armourGeometry.notAdoptable', 'balance.armourGeometry.unidentified',
      'balance.armourGeometry.unavailable', 'balance.armourGeometry.diagnostics',
      'balance.fixedArmour.geometryInactive',
    ];
    for (const key of keys) {
      expect(c(key).trim(), key).not.toBe('');
      expect(c(key), key).not.toBe(key);
      expect(conceptCopy('zh-CN', key).trim(), key).not.toBe('');
      expect(conceptCopy('zh-CN', key), key).not.toBe(c(key));
    }
    for (const key of ['armour_geometry_area_m2', 'armour_geometry_volume_m3',
      'armour_geometry_mass_t', 'armour_geometry_known_mass_subtotal_t',
      'armour_geometry_plate_area_m2', 'armour_geometry_plate_volume_m3',
      'armour_geometry_plate_mass_t']) {
      expect(workspaceCopy('en', `data.${key}` as never), key).not.toBe(`data.${key}`);
      expect(zhCopy(`data.${key}` as never), key).not.toBe(workspaceCopy('en', `data.${key}` as never));
    }
  });
});

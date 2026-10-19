import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { UnitProvider } from '../components/UnitProvider';
import { HullReadings, NativeFreeboardProfile } from '../components/HullFreeboardReadings';
import { readHullFreeboard } from '../components/hullFreeboardModel';
import { freeboardProfileSvg } from '../components/freeboardProfileSvg';
import { configChangeRows } from '../components/designConfigModel';
import { resolvedUnit } from '../components/sps3b3Model';
import { Sps3b3Readings } from '../components/Sps3b3Readings';
import { hullFreeboardCopy, hullFreeboardDictionary } from '../i18n/hullFreeboard';
import { FEEDBACK_READING_KEYS } from '../components/designFeedbackModel';
import { CANONICAL_PREFERENCES } from '../components/units';
import { inLanguage } from './locale';
import type { Sps3b3Field, StageEnvelope } from '../types';

/**
 * The hull and freeboard readers, their one projection, their serializer and the
 * frozen comparison rows.
 *
 * These pin the boundaries the increment must not cross: the source's normalized
 * feet and long tons are read as saved, the design's own drivers and depth lock
 * are strict true / false / unknown declarations, a missing station input never
 * grows a fabricated outline, coincident endpoints remain separately selectable,
 * a depth lock removes the FD/AD edit affordance, and both downloads contain all
 * eight endpoints whatever is selected.
 */

afterEach(cleanup);

const SCHEMA = 'plimsoll-ship-design-result-1';
const METHOD = 'ship-design-native-v1';
const FT = { ...CANONICAL_PREFERENCES, length: 'ft' as const };

const hull = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  length: 590.55, lengthOA: 620.1, beam: 88.58, beamBulges: 95, draught: 26.25,
  block: 0.55, displacement: 72000,
  ...over,
});

const freeboard = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  fcLength: 0.205, fdLength: 0.3, adLength: 0.34, qdLength: 0.155,
  freeQDAft: 26, freeQDFor: 26, freeADAft: 25, freeADFor: 25,
  freeFDAft: 24, freeFDFor: 24, freeFCAft: 30, freeFCFor: 34,
  lengthBow: 20, lengthStern: 10,
  ...over,
});

const editing = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  length_driver: 'overall', overall_length: 620.1,
  displacement_driver: 'displacement', normal_displacement_lt: 71000,
  depth_locked: false, ...over,
});

const native = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  schema: SCHEMA, method_version: METHOD, status: 'available', basis_condition_id: 'normal',
  hull: hull(), freeboard: freeboard(), design: { editing: editing() },
  balance: { selected_mass_t: 71934, estimated_mass_t: 71924, target_displacement_t: 71924, difference_t: 10 },
  ...over,
});

const read = (over: Record<string, unknown> = {}, baseline?: Record<string, unknown>) =>
  readHullFreeboard(native(over), baseline === undefined ? undefined : native(baseline));
const hullFact = (r: ReturnType<typeof read>, key: string) => r.hull.facts.find(item => item.key === key)!;
const endpoint = (r: ReturnType<typeof read>, key: string) => r.freeboard.endpoints.find(item => item.key === key)!;
const fraction = (r: ReturnType<typeof read>, key: string) => r.freeboard.fractions.find(item => item.key === key)!;

const ready = (node: React.ReactElement) =>
  render(inLanguage(<UnitProvider preferences={FT}>{node}</UnitProvider>, 'en'));
const frozen = (node: React.ReactElement) =>
  render(inLanguage(<UnitProvider preferences={FT}>{node}</UnitProvider>, 'en'));
const zhReady = (node: React.ReactElement) =>
  render(inLanguage(<UnitProvider preferences={FT}>{node}</UnitProvider>, 'zh-CN'));

const textOf = (svg: string): string =>
  [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]).join(' ');

describe('native hull and freeboard gates', () => {
  it('names an absent, foreign or unreadable result and quotes no fact', () => {
    expect(readHullFreeboard(null).problem).toBe('absent');
    expect(readHullFreeboard({ schema: 'other', hull: hull() }).problem).toBe('unsupported_schema');
    expect(readHullFreeboard({ schema: SCHEMA, method_version: 'other', hull: hull() }).problem).toBe('unsupported_method');
    expect(readHullFreeboard({ schema: SCHEMA, method_version: METHOD, status: 'failed', hull: hull() }).problem)
      .toBe('unavailable');
    const unsupported = readHullFreeboard({ schema: 'other', hull: hull(), freeboard: freeboard() });
    expect(unsupported.supported).toBe(false);
    expect(unsupported.hull.facts.every(fact => fact.value === null)).toBe(true);
    expect(unsupported.freeboard.endpoints.every(item => item.value === null)).toBe(true);
  });

  it('reads partial results and refuses a result with neither section', () => {
    expect(read({ status: 'partial' }).supported).toBe(true);
    expect(readHullFreeboard({ schema: SCHEMA, method_version: METHOD, status: 'available' }).problem)
      .toBe('unavailable');
  });

  it('never mutates the result it reads', () => {
    const input = native();
    const snapshot = JSON.stringify(input);
    readHullFreeboard(input, native());
    expect(JSON.stringify(input)).toBe(snapshot);
  });
});

describe('hull facts and declarations', () => {
  it('reads the linked hull values in normalized feet and the source displacement in long tons', () => {
    const reading = read();
    expect(reading.hull.facts.map(fact => fact.key)).toEqual([
      'hull.length', 'hull.lengthOA', 'hull.beam', 'hull.beamBulges', 'hull.draught', 'hull.block', 'hull.displacement',
    ]);
    expect(hullFact(reading, 'hull.length')).toMatchObject({
      value: 590.55, unit: 'length', editField: 'length_waterline',
    });
    expect(hullFact(reading, 'hull.lengthOA')).toMatchObject({ value: 620.1, unit: 'length' });
    expect(hullFact(reading, 'hull.lengthOA').editField).toBeUndefined();
    expect(hullFact(reading, 'hull.beam')).toMatchObject({ value: 88.58, editField: 'beam_moulded' });
    expect(hullFact(reading, 'hull.beamBulges')).toMatchObject({ value: 95, editField: 'beam_at_bulges' });
    expect(hullFact(reading, 'hull.draught')).toMatchObject({ value: 26.25, editField: 'draught_normal' });
    expect(hullFact(reading, 'hull.block')).toMatchObject({ value: 0.55, editField: 'block_coefficient_normal' });
    expect(hullFact(reading, 'hull.displacement')).toMatchObject({ value: 72000, unit: 'lt' });
    expect(hullFact(reading, 'hull.displacement').editField).toBeUndefined();
    // The ledger balance is tonnes, separate from the source long tons above.
    expect(reading.balance).toEqual({ selectedT: 71934, estimateT: 71924, targetT: 71924, differenceT: 10 });
  });

  it('keeps zero, unknown and a changed hull fact distinct against a saved revision', () => {
    const moved = read({ hull: hull({ beam: 90, block: 0, lengthOA: undefined }) }, {});
    expect(hullFact(moved, 'hull.beam')).toMatchObject({ value: 90, changed: true });
    expect(hullFact(moved, 'hull.block')).toMatchObject({ value: 0, changed: true });
    expect(hullFact(moved, 'hull.lengthOA')).toMatchObject({ value: null, changed: true });
    const unknownBoth = read({ hull: hull({ lengthOA: undefined }) }, { hull: hull({ lengthOA: undefined }) });
    expect(hullFact(unknownBoth, 'hull.lengthOA').changed).toBe(false);
    const same = read({}, {});
    expect(same.hull.facts.every(fact => fact.changed === false)).toBe(true);
  });

  it('keeps its own drivers and depth lock strictly declared, never defaulted', () => {
    expect(read().hull.drivers).toMatchObject({
      lengthDriver: 'overall', displacementDriver: 'displacement', depthLocked: false,
    });
    expect(read({ design: { editing: editing({ length_driver: 'waterline' }) } }).hull.drivers.lengthDriver)
      .toBe('waterline');
    expect(read({ design: { editing: editing({ length_driver: 'metric' }) } }).hull.drivers.lengthDriver).toBeNull();
    expect(read({ design: { editing: editing({ displacement_driver: 'block' }) } }).hull.drivers.displacementDriver)
      .toBe('block');
    expect(read({ design: { editing: editing({ displacement_driver: 'volume' }) } }).hull.drivers.displacementDriver)
      .toBeNull();
    // A missing flag is unknown; an explicit false stays false.
    expect(read({ design: { editing: {} } }).hull.drivers.depthLocked).toBeNull();
    expect(read({ design: { editing: editing({ depth_locked: true }) } }).hull.drivers.depthLocked).toBe(true);
    expect(read({ design: { editing: editing({ depth_locked: 'yes' }) } }).hull.drivers.depthLocked).toBeNull();
    // The overall target keeps its saved hull-page unit; the displacement target
    // is the source long-ton figure and a genuine zero is kept.
    expect(read({ design: { editing: editing({ overall_length: 0 }) } }).hull.drivers.overallTarget).toBe(0);
    expect(read({ design: { editing: editing({ normal_displacement_lt: 0 }) } }).hull.drivers.displacementTargetLt)
      .toBe(0);
    expect(read({ design: { editing: {} } }).hull.drivers.overallTarget).toBeNull();
  });
});

describe('hull chapter', () => {
  it('prints the linked facts, the saved drivers and the reveal buttons of the real fields only', () => {
    const onEditField = vi.fn();
    ready(<HullReadings result={native()} state="ready" onEditField={onEditField} />);
    expect(document.querySelector('[data-hull-readings][data-state="ready"]')).not.toBeNull();
    expect(document.querySelector('[data-hull-fact="hull.length"] dd')!.textContent).toContain('590.55 ft');
    expect(document.querySelector('[data-hull-fact="hull.displacement"] dd')!.textContent).toContain('72,000 LT');
    // The page-unit target is not silently converted into feet.
    expect(document.querySelector('[data-hull-driver="length"] dd')!.textContent).toContain('overall');
    expect(document.querySelector('[data-hull-driver-target="overall"] dd')!.textContent).toContain('620.1');
    expect(document.querySelector('[data-hull-driver="displacement"] dd')!.textContent).toContain('displacement');
    expect(document.querySelector('[data-hull-driver-target="displacement"] dd')!.textContent).toContain('71,000 LT');
    expect(document.querySelector('[data-hull-driver="depth"] dd')!.textContent).toContain('not locked');
    // LOA, the source displacement and the balance carry no edit affordance.
    expect(document.querySelector('[data-hull-fact="hull.lengthOA"] [data-hull-reveal]')).toBeNull();
    expect(document.querySelector('[data-hull-fact="hull.displacement"] [data-hull-reveal]')).toBeNull();
    expect(document.querySelector('[data-hull-balance-row="target"] dd')!.textContent).toContain('71,924 t');
    fireEvent.click(document.querySelector('[data-hull-reveal="length_waterline"]')!);
    expect(onEditField).toHaveBeenCalledWith('length_waterline');
    fireEvent.click(document.querySelector('[data-hull-reveal="block_coefficient_normal"]')!);
    expect(onEditField).toHaveBeenCalledWith('block_coefficient_normal');
  });

  it('withholds the hull facts while pending or failed and names an unsupported shape', () => {
    render(<HullReadings result={native()} state="pending" />);
    expect(document.querySelector('[data-hull-readings][data-state="pending"]')).not.toBeNull();
    expect(document.querySelector('[data-hull-fact]')).toBeNull();
    cleanup();
    render(<HullReadings result={native()} state="failed" />);
    expect(document.querySelector('[data-hull-readings][data-state="failed"]')).not.toBeNull();
    cleanup();
    render(<HullReadings result={{ schema: 'other', hull: hull() }} />);
    expect(document.querySelector('[data-hull-facts]')).toBeNull();
    expect(document.body.textContent).toMatch(/supported native result shape/);
  });
});

describe('freeboard endpoints', () => {
  it('reads the eight endpoints in source order with their real edit fields', () => {
    const reading = read();
    expect(reading.freeboard.endpoints.map(item => item.key)).toEqual([
      'freeQDAft', 'freeQDFor', 'freeADAft', 'freeADFor',
      'freeFDAft', 'freeFDFor', 'freeFCAft', 'freeFCFor',
    ]);
    expect(reading.freeboard.endpoints.map(item => item.editField)).toEqual([
      'freeboard_quarterdeck_aft', 'freeboard_quarterdeck_fore',
      'freeboard_afterdeck_aft', 'freeboard_afterdeck_fore',
      'freeboard_flat_deck_aft', 'freeboard_flat_deck_fore',
      'freeboard_forecastle_aft', 'freeboard_forecastle_fore',
    ]);
    expect(endpoint(reading, 'freeFCFor')).toMatchObject({ value: 34, unit: 'length', changed: false });
    expect(fraction(reading, 'fcLength')).toMatchObject({ value: 0.205, percent: 20.5, changed: false });
  });

  it('keeps a saved zero and a negative height while a missing height stays unknown', () => {
    const reading = read({ freeboard: freeboard({ freeFCAft: 0, freeFCFor: -2 }) });
    expect(endpoint(reading, 'freeFCAft').value).toBe(0);
    expect(endpoint(reading, 'freeFCFor').value).toBe(-2);
    expect(reading.freeboard.geometry).not.toBeNull();
    expect(reading.freeboard.geometry!.heights[7]).toBe(-2);
    const missing = read({ freeboard: freeboard({ freeQDAft: undefined }) });
    expect(endpoint(missing, 'freeQDAft').value).toBeNull();
    expect(endpoint(missing, 'freeQDAft').changed).toBe(false);
    expect(missing.freeboard.geometry).toBeNull();
    expect(missing.freeboard.geometryProblem).toBe('heights');
  });

  it('draws only when every station input is real and the declared proportions fit', () => {
    const valid = read();
    expect(valid.freeboard.geometry?.xs).toHaveLength(8);
    expect(valid.freeboard.geometryProblem).toBeNull();
    expect(read({ freeboard: freeboard({ lengthBow: undefined }) }).freeboard.geometryProblem).toBe('bow');
    expect(read({ freeboard: freeboard({ lengthStern: undefined }) }).freeboard.geometryProblem).toBe('stern');
    expect(read({ freeboard: freeboard({ lengthStern: -1 }) }).freeboard.geometryProblem).toBe('stern');
    expect(read({ freeboard: freeboard({ qdLength: -0.1 }) }).freeboard.geometryProblem).toBe('fraction');
    expect(read({ freeboard: freeboard({ fcLength: 0.8, fdLength: 0.8 }) }).freeboard.geometryProblem).toBe('fraction');
    expect(read({ hull: hull({ length: 0 }) }).freeboard.geometryProblem).toBe('length');
    // The independent endpoint facts survive a refused outline.
    const refused = read({ freeboard: freeboard({ lengthBow: undefined }) });
    expect(refused.freeboard.geometry).toBeNull();
    expect(endpoint(refused, 'freeFCFor').value).toBe(34);
  });

  it('marks a known endpoint change, including known to unknown, but not two unknowns', () => {
    const moved = read({ freeboard: freeboard({ freeFCFor: 36 }) }, {});
    expect(endpoint(moved, 'freeFCFor').changed).toBe(true);
    expect(fraction(moved, 'fcLength').changed).toBe(false);
    const knownToUnknown = read({ freeboard: freeboard({ freeFCFor: undefined }) }, {});
    expect(endpoint(knownToUnknown, 'freeFCFor')).toMatchObject({ value: null, changed: true });
    const bothUnknown = read({ freeboard: freeboard({ freeFCFor: undefined }) },
      { freeboard: freeboard({ freeFCFor: undefined }) });
    expect(endpoint(bothUnknown, 'freeFCFor').changed).toBe(false);
    const basis = read({ freeboard: freeboard({ freeFCFor: 36 }) }, { basis_condition_id: 'ballast' });
    expect(basis.comparable).toBe(false);
    expect(basis.freeboard.endpoints.every(item => item.changed === false)).toBe(true);
    const refreshed = read({}, {});
    expect(refreshed.freeboard.endpoints.every(item => item.changed === false)).toBe(true);
  });
});

describe('interactive freeboard profile', () => {
  it('selects coincident endpoints independently through the list without writing the design', () => {
    const onEditField = vi.fn();
    ready(<NativeFreeboardProfile result={native()} state="ready" onEditField={onEditField} />);
    expect(document.querySelectorAll('[data-freeboard-select]')).toHaveLength(8);
    // The two quarterdeck endpoints deliberately share coordinates here.
    fireEvent.click(document.querySelector('[data-freeboard-select="freeQDAft"]')!);
    expect(document.querySelector('[data-freeboard-panel="freeQDAft"]')).not.toBeNull();
    fireEvent.click(document.querySelector('[data-freeboard-select="freeQDFor"]')!);
    expect(document.querySelector('[data-freeboard-panel="freeQDFor"]')).not.toBeNull();
    expect(document.querySelector('[data-freeboard-panel="freeQDAft"]')).toBeNull();
    expect(onEditField).not.toHaveBeenCalled();
  });

  it('selects a point from the drawing by keyboard and keeps the focused node alive', () => {
    ready(<NativeFreeboardProfile result={native()} state="ready" />);
    const group = document.querySelector('[data-freeboard-point="freeFDAft"]') as SVGGElement;
    expect(group).not.toBeNull();
    group.focus();
    fireEvent.keyDown(group, { key: 'Enter' });
    expect(document.querySelector('[data-freeboard-panel="freeFDAft"]')).not.toBeNull();
    expect(document.activeElement).toBe(group);
    fireEvent.keyDown(group, { key: ' ' });
    expect(document.activeElement).toBe(group);
  });

  it('reveals the selected endpoint field and never turns selection into an edit', () => {
    const onEditField = vi.fn();
    const input = native();
    const snapshot = JSON.stringify(input);
    ready(<NativeFreeboardProfile result={input} state="ready" onEditField={onEditField} />);
    fireEvent.click(document.querySelector('[data-freeboard-select="freeFCFor"]')!);
    expect(onEditField).not.toHaveBeenCalled();
    fireEvent.click(document.querySelector('[data-freeboard-edit="freeboard_forecastle_fore"]')!);
    expect(onEditField).toHaveBeenCalledWith('freeboard_forecastle_fore');
    expect(JSON.stringify(input)).toBe(snapshot);
  });

  it('offers no edit for the four FD/AD endpoints under a saved depth lock', () => {
    const locked = native({ design: { editing: editing({ depth_locked: true }) } });
    ready(<NativeFreeboardProfile result={locked} state="ready" onEditField={vi.fn()} />);
    expect(document.querySelector('[data-freeboard-lock]')!.textContent).toMatch(/Pinned by the depth lock/);
    for (const key of ['freeFDAft', 'freeFDFor', 'freeADAft', 'freeADFor']) {
      fireEvent.click(document.querySelector(`[data-freeboard-select="${key}"]`)!);
      expect(document.querySelector(`[data-freeboard-panel="${key}"] [data-freeboard-edit]`)).toBeNull();
      expect(document.querySelector(`[data-freeboard-panel="${key}"]`)!.textContent).toMatch(/Pinned/);
    }
    fireEvent.click(document.querySelector('[data-freeboard-select="freeFCFor"]')!);
    expect(document.querySelector('[data-freeboard-edit="freeboard_forecastle_fore"]')).not.toBeNull();
  });

  it('withholds the drawing, list and downloads while pending or failed, and names an unsupported shape', () => {
    render(<NativeFreeboardProfile result={native()} state="pending" />);
    expect(document.querySelector('[data-freeboard-profile][data-state="pending"]')).not.toBeNull();
    expect(document.querySelector('[data-freeboard-profile] svg')).toBeNull();
    expect(document.querySelector('[data-freeboard-download]')).toBeNull();
    cleanup();
    render(<NativeFreeboardProfile result={native()} state="failed" />);
    expect(document.querySelector('[data-freeboard-profile][data-state="failed"]')).not.toBeNull();
    expect(document.querySelector('[data-freeboard-download]')).toBeNull();
    cleanup();
    render(<NativeFreeboardProfile result={{ schema: 'other', freeboard: freeboard() }} />);
    expect(document.querySelector('[data-freeboard-profile] svg')).toBeNull();
    expect(document.body.textContent).toMatch(/supported native result shape/);
  });

  it('renders a frozen reading read-only with the full list, identity and downloads', () => {
    frozen(<NativeFreeboardProfile result={native()} state="frozen" contextLabel="design-normal · r2" runId="run-7" />);
    const section = document.querySelector('[data-freeboard-profile][data-state="frozen"]')!;
    expect(section.querySelector('svg[role="img"]')).not.toBeNull();
    expect(section.querySelector('[data-freeboard-select]')).toBeNull();
    expect(section.querySelector('[data-freeboard-edit]')).toBeNull();
    expect(section.querySelectorAll('[data-freeboard-endpoint]')).toHaveLength(8);
    expect(section.querySelector('[data-freeboard-download="svg"]')).not.toBeNull();
    expect(section.querySelector('[data-freeboard-download="png"]')).not.toBeNull();
    expect(section.textContent).toContain('design-normal · r2');
    expect(section.textContent).toContain('run-7');
  });
});

describe('freeboard serializer and downloads', () => {
  const renderOptions = {
    language: 'en' as const, prefs: FT, uid: 'f1', interactive: true,
    contextLabel: 'A & B <x>', runId: 'run-7',
  };

  it('writes standalone escaped SVG with all eight endpoints and a white background', () => {
    const svg = freeboardProfileSvg(read(), renderOptions);
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(svg).toContain('fill="#ffffff"');
    expect(svg).toContain('A &amp; B &lt;x&gt;');
    expect(svg).toContain('run-7');
    expect(parseSvg(svg).querySelector('parsererror')).toBeNull();
    for (const key of ['freeQDAft', 'freeQDFor', 'freeADAft', 'freeADFor', 'freeFDAft', 'freeFDFor', 'freeFCAft', 'freeFCFor']) {
      expect(svg).toContain(`data-freeboard-point="${key}"`);
    }
    expect(parseSvg(svg).querySelectorAll('[data-freeboard-point]')).toHaveLength(8);
    // Every endpoint's height appears even when only one would be selected.
    expect(textOf(svg)).toContain('Forecastle fore');
    expect(textOf(svg)).toContain('34 ft');
    expect(textOf(svg)).toContain('20.5%');
    // The accessible quantity follows the same display unit as the visible row.
    const metres = { ...CANONICAL_PREFERENCES, length: 'm' as const };
    const metreSvg = freeboardProfileSvg(read(), { ...renderOptions, prefs: metres });
    expect(metreSvg).toContain('aria-label="Forecastle fore: 10.36 m"');
    const zeroSvg = freeboardProfileSvg(read({ freeboard: freeboard({ freeFCAft: 0 }) }),
      { ...renderOptions, prefs: metres });
    expect(zeroSvg).toContain('aria-label="Forecastle aft: 0 m"');
    const unknownSvg = freeboardProfileSvg(read({ freeboard: freeboard({ freeQDAft: undefined }) }),
      { ...renderOptions, prefs: metres });
    expect(unknownSvg).toContain('aria-label="Quarterdeck aft: —"');
  });

  it('states a refused outline but still lists the independent known endpoints', () => {
    const refused = read({ freeboard: freeboard({ lengthBow: undefined }) });
    const svg = freeboardProfileSvg(refused, renderOptions);
    expect(textOf(svg)).toMatch(/bow angle is missing/);
    expect(svg).not.toContain('<polyline');
    expect(parseSvg(svg).querySelectorAll('[data-freeboard-point]')).toHaveLength(8);
    expect(textOf(svg)).toContain('34 ft');
  });

  it('is a group of focusable points when live and a static image when frozen', () => {
    const live = freeboardProfileSvg(read(), renderOptions);
    expect(live).toContain('role="group"');
    expect(live).toContain('role="button"');
    expect(live).toContain('tabindex="0"');
    const still = freeboardProfileSvg(read(), { ...renderOptions, interactive: false });
    expect(still).toContain('role="img"');
    expect(still).not.toContain('role="button"');
    expect(still).not.toContain('tabindex="0"');
  });

  it('localizes the serialized labels and units', () => {
    const zh = freeboardProfileSvg(read(), { ...renderOptions, language: 'zh-CN' });
    expect(textOf(zh)).toContain('艏楼');
    expect(textOf(zh)).not.toContain('Forecastle fore');
    expect(textOf(zh)).toContain('20.5%');
  });

  it('downloads the same complete SVG and reports a failed export in words', () => {
    const createObjectURL = vi.fn(() => 'blob:freeboard');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    try {
      ready(<NativeFreeboardProfile result={native()} state="ready" />);
      fireEvent.click(document.querySelector('[data-freeboard-download="svg"]')!);
      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(click).toHaveBeenCalledTimes(1);
    } finally {
      click.mockRestore();
      vi.unstubAllGlobals();
    }
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => { throw new Error('Unavailable'); } });
    try {
      cleanup();
      ready(<NativeFreeboardProfile result={native()} state="ready" />);
      fireEvent.click(document.querySelector('[data-freeboard-download="svg"]')!);
      expect(screen.getByRole('alert')).toHaveTextContent(/SVG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('says so in words when the PNG cannot be produced', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:freeboard', revokeObjectURL: () => {} });
    class BrokenImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      width = 960;
      height = 700;
      set src(_value: string) { queueMicrotask(() => this.onerror?.()); }
    }
    vi.stubGlobal('Image', BrokenImage);
    try {
      ready(<NativeFreeboardProfile result={native()} state="ready" />);
      fireEvent.click(document.querySelector('[data-freeboard-download="png"]')!);
      expect(await screen.findByRole('alert')).toHaveTextContent(/PNG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('frozen report integration and comparison rows', () => {
  const envelope = (over: Partial<StageEnvelope> = {}): StageEnvelope => ({
    status: 'completed', requested: true, reason: null, assumptions: [], diagnostics: [],
    method_versions: { kernel: METHOD },
    validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
    data: null as never, ...over,
  });

  it('mounts the read-only native readers only behind the existing envelope gate', () => {
    render(<Sps3b3Readings variant="native" data={native()} envelope={envelope({ requested: false })} />);
    expect(document.querySelector('[data-hull-readings]')).toBeNull();
    expect(document.querySelector('[data-freeboard-profile]')).toBeNull();
    cleanup();
    render(<Sps3b3Readings variant="native" data={native()} envelope={envelope()} runId="run-7" />);
    expect(document.querySelector('[data-hull-readings][data-state="frozen"]')).not.toBeNull();
    expect(document.querySelector('[data-freeboard-profile][data-state="frozen"]')).not.toBeNull();
    cleanup();
    // A non-native compatibility result keeps the original profile and gets no
    // new reader.
    render(<Sps3b3Readings data={{ schema: 'plimsoll-sps3b3-result-1', status: 'available', hull: { length: 590.55 }, freeboard: freeboard() }} />);
    expect(document.querySelector('.sps-profile')).not.toBeNull();
    expect(document.querySelector('[data-freeboard-profile]')).toBeNull();
  });

  it('extends the frozen configuration rows without changing the sixteen readings', () => {
    const current = native();
    const comparison = native({
      hull: hull({ lengthOA: 630, block: 0.6, displacement: 73000 }),
      freeboard: freeboard({ freeFCFor: 36, fcLength: 0.25 }),
      design: { editing: editing({ length_driver: 'waterline', displacement_driver: 'block', depth_locked: true }) },
    });
    const rows = configChangeRows(current as never, comparison as never, 'en');
    const row = (key: string) => rows.find(item => item.key === key)!;
    expect(FEEDBACK_READING_KEYS).toHaveLength(16);
    expect(row('hull.lengthOA')).toMatchObject({ before: 620.1, after: 630, dimension: 'length', storedUnit: 'ft' });
    expect(row('hull.block')).toMatchObject({ before: 0.55, after: 0.6 });
    expect(row('hull.displacement')).toMatchObject({ before: 72000, after: 73000, canonical: 'LT' });
    expect(row('hull.lengthDriver').beforeText).toBe('overall');
    expect(row('hull.lengthDriver').afterText).toBe('waterline');
    expect(row('hull.displacementDriver').beforeText).toBe('displacement');
    expect(row('hull.displacementDriver').afterText).toBe('block coefficient');
    expect(row('hull.depthLock').beforeText).toBe('not locked');
    expect(row('hull.depthLock').afterText).toBe('locked to saved depth snapshot');
    expect(row('freeboard.freeFCFor')).toMatchObject({ group: 'freeboard', before: 34, after: 36, dimension: 'length', storedUnit: 'ft' });
    // Fractions are displayed as percentages, not raw 0–1 values.
    expect(row('freeboard.fcLength')).toMatchObject({ before: 20.5, after: 25, canonical: '%' });
  });

  it('keeps a source unknown unknown in the comparison instead of inventing a delta', () => {
    const rows = configChangeRows(native({ freeboard: freeboard({ freeFCFor: undefined }) }) as never,
      native({ freeboard: freeboard({ freeFCFor: 36 }) }) as never, 'en');
    const row = rows.find(item => item.key === 'freeboard.freeFCFor')!;
    expect(row.before).toBeNull();
    expect(row.after).toBe(36);
  });
});

describe('bow-angle unit and dictionary', () => {
  const bowField = (over: Partial<Sps3b3Field> = {}): Sps3b3Field => ({
    key: 'freeboard_length_bow', name: 'freeboard_length_bow', source_index: 0,
    page: 'freeboard', label: 'Bow angle', kind: 'number',
    unit: 'ft', unit_resolved: 'ft', unit_choices: ['ft', 'm'], scale_ref: 'hull_scale',
    choices: null, allows_unselected: false, min_value: null, max_value: null,
    ...over,
  } as Sps3b3Field);

  it('always resolves the front-end bow angle as degrees under either hull scale', () => {
    expect(resolvedUnit(bowField(), { parameters: { hull_scale: 0 } } as never)).toBe('deg');
    expect(resolvedUnit(bowField(), { parameters: { hull_scale: 1 } } as never)).toBe('deg');
    expect(resolvedUnit(bowField({ unit_choices: null, scale_ref: null }), null)).toBe('deg');
  });

  it('is complete in both languages with equal keys and no empty string', () => {
    const en = hullFreeboardDictionary('en');
    const zh = hullFreeboardDictionary('zh-CN');
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort());
    for (const key of Object.keys(en)) {
      expect(en[key as keyof typeof en]).not.toBe('');
      expect(zh[key as keyof typeof en]).not.toBe('');
    }
    expect(hullFreeboardCopy('zh-CN', 'freeboard.point.freeFCFor')).toBe('艏楼前');
  });

  it('prints the freeboard chapter in Chinese for a Chinese reader', () => {
    zhReady(<NativeFreeboardProfile result={native()} state="ready" />);
    expect(document.querySelector('[data-freeboard-select="freeFCFor"]')!.textContent).toContain('艏楼前');
    expect(document.querySelector('[data-freeboard-profile]')!.textContent).toContain('已声明端点剖面');
  });
});

/** Parse one serialized SVG and return the document, with a parser error if any. */
function parseSvg(svg: string): Document {
  return new DOMParser().parseFromString(svg, 'image/svg+xml');
}

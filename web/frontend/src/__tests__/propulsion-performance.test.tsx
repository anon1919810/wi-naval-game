import { cleanup, fireEvent, render } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PerformanceReadings, PropulsionReadings } from '../components/PropulsionPerformanceReadings';
import { UnitProvider } from '../components/UnitProvider';
import {
  propulsionEnvelopeGate, PROPULSION_LEDGER_ROLES, readPropulsionPerformance,
  type PropulsionPerformance,
} from '../components/propulsionPerformanceModel';
import { propulsionPerformanceDictionary } from '../i18n/propulsionPerformance';
import { inLanguage } from './locale';

/**
 * The propulsion and performance readers, through their one pure projection and
 * their two presentational chapters.
 *
 * These pin the rules the reading depends on: the source's own units are never
 * converted, a genuine zero is a fact while a missing field is unknown, a
 * malformed selector array is unknown rather than none-selected, the declared
 * power lock is strictly true / false / unknown and a missing target is never a
 * zero, only the two whole-ship machinery and fuel ledger roles are read and
 * they stay in tonnes, the eight source flags keep their three states, and a
 * pending, failed, unsupported or frozen reading withholds what it must. The
 * input is never mutated.
 */

afterEach(cleanup);

const SCHEMA = 'plimsoll-ship-design-result-1';
const METHOD = 'ship-design-native-v1';

/** The declared engine block, with overrides. */
const engine = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  speedMax: 30, speedCruise: 14, hpMax: 60000, hpCruise: 20000, range: 12000, screws: 4,
  pctCoal: 0, bunker: 0, engineWeight: 800,
  fuelArray: [true, false, false, false, false],
  engineArray: [false, false, true],
  driveArray: [false, true, false, false],
  ...over,
});

/** The declared performance block, with overrides. */
const performance = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  stability: 1.2, stabilityAdj: 1.1, metacentre: 3.5, rollPeriod: 12,
  strengthCross: 0.8, strengthLong: 0.9, strengthComp: 0.85,
  seaboat: 1, seakeeping: 1, steadiness: 1, steadinessAdj: 1,
  tenderWarn: true, capsizeWarn: false, steady: true, unsteady: false,
  badSea: false, poorSea: false, goodSea: true, fineSea: false,
  ...over,
});

const native = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  schema: SCHEMA,
  method_version: METHOD,
  status: 'available',
  basis_condition_id: 'design-normal',
  engine: engine(),
  performance: performance(),
  design: { editing: { power_locked: true, power_hp: 60000, locked_bunker_lt: 1500 } },
  ledger: { roles: {
    machinery: { mode: 'declared', selected_mass_t: 4000, estimate_t: 3900 },
    fuel: { mode: 'estimated', selected_mass_t: 2000, estimate_t: 2100 },
  } },
  ...over,
});

const read = (over: Record<string, unknown> = {}): PropulsionPerformance => readPropulsionPerformance(native(over));
const fact = (r: PropulsionPerformance, key: string): PropulsionPerformance['engine']['facts'][number] =>
  r.engine.facts.find(item => item.key === key)
  ?? r.performance.groups.flatMap(item => item.readings).find(item => item.key === key)!;
const group = (r: PropulsionPerformance, id: string) => r.performance.groups.find(item => item.id === id)!;
const flag = (r: PropulsionPerformance, key: string) => r.performance.flags.find(item => item.key === key)!;

/* ------------------------------------------------------------- projection */

describe('propulsion native gates', () => {
  it('names an absent, foreign-schema, foreign-method or sectionless result', () => {
    expect(readPropulsionPerformance(null).problem).toBe('absent');
    expect(readPropulsionPerformance({ schema: 'other' }).problem).toBe('unsupported_schema');
    expect(readPropulsionPerformance({ schema: SCHEMA, method_version: 'other' }).problem).toBe('unsupported_method');
    expect(readPropulsionPerformance({ schema: SCHEMA, method_version: METHOD }).problem).toBe('unavailable');
    // A result whose own status is unavailable yields no fact even when a
    // residual engine section is still attached.
    expect(readPropulsionPerformance({ schema: SCHEMA, method_version: METHOD, status: 'unavailable', engine: engine() }).problem)
      .toBe('unavailable');
  });

  it('never quotes a number for an unsupported result', () => {
    const reading = readPropulsionPerformance({ schema: 'other', engine: engine(), performance: performance() });
    expect(reading.supported).toBe(false);
    expect(reading.engine.facts.every(item => item.value === null)).toBe(true);
    expect(reading.performance.flags.every(item => item.value === null)).toBe(true);
    expect(reading.engine.lock.locked).toBeNull();
  });

  it('reports the identity it read and always yields both sections', () => {
    const reading = read();
    expect(reading).toMatchObject({
      supported: true, problem: null, schema: SCHEMA, method: METHOD,
      status: 'available', basisConditionId: 'design-normal',
    });
    const sparse = readPropulsionPerformance({ schema: SCHEMA, method_version: METHOD, status: 'available', engine: {} });
    expect(sparse.supported).toBe(true);
    expect(sparse.engine.facts.every(item => item.value === null)).toBe(true);
    expect(sparse.performance.groups.every(item => item.readings.every(f => f.value === null))).toBe(true);
  });

  it('reads a valid available or partial result and withholds every number for any other status', () => {
    // The native result declares `available` or `partial`; both are readable.
    expect(readPropulsionPerformance(native({ status: 'available' })).supported).toBe(true);
    const partial = readPropulsionPerformance(native({ status: 'partial' }));
    expect(partial.supported).toBe(true);
    expect(fact(partial, 'engine.hpMax').value).toBe(60000);
    // A failed, unavailable or missing status withholds the residual payload.
    for (const status of ['unavailable', 'failed', 'completed', undefined]) {
      const rejected = readPropulsionPerformance(native({ status }));
      expect(rejected.supported).toBe(false);
      expect(rejected.problem).toBe('unavailable');
      expect(rejected.engine.facts.every(item => item.value === null)).toBe(true);
    }
  });
});

describe('propulsion source facts', () => {
  it('reads speed, power, range, coal share and bunker in the source units; a zero is a fact and a missing field is unknown', () => {
    const reading = read();
    expect(fact(reading, 'engine.speedMax')).toMatchObject({ value: 30, unit: 'speed', editField: 'speed_max_kn' });
    expect(fact(reading, 'engine.hpMax')).toMatchObject({ value: 60000, unit: 'source-hp' });
    expect(fact(reading, 'engine.range')).toMatchObject({ value: 12000, unit: 'range-nmi', editField: 'range_nm' });
    expect(fact(reading, 'engine.pctCoal')).toMatchObject({ value: 0, unit: 'percent', editField: 'coal_percentage' });
    expect(fact(reading, 'engine.bunker')).toMatchObject({ value: 0, unit: 'long-ton' });
    // The maximum-load bunker is not saved, so it is unknown and never zero.
    expect(fact(reading, 'engine.bunkerMax')).toMatchObject({ value: null, unit: 'long-ton' });
    // The source machinery mass is the engine page's own long-ton figure, kept
    // apart from the whole-ship ledger masses in tonnes.
    expect(fact(reading, 'engine.engineWeight')).toMatchObject({ value: 800, unit: 'long-ton' });
    expect(reading.engine.ledger[0].selectedT).toBe(4000);
  });

  it('treats a numeric string or a non-finite number as no reading at all', () => {
    const reading = read({ engine: engine({ hpMax: '60000', speedCruise: Infinity, range: NaN }) });
    expect(fact(reading, 'engine.hpMax').value).toBeNull();
    expect(fact(reading, 'engine.speedCruise').value).toBeNull();
    expect(fact(reading, 'engine.range').value).toBeNull();
  });
});

describe('propulsion declarations', () => {
  it('reads the fuel, engine and drive selectors strictly, and keeps a malformed array unknown', () => {
    const reading = read();
    expect(reading.engine.declaration.fuel).toEqual([0]);
    expect(reading.engine.declaration.engine).toEqual([2]);
    expect(reading.engine.declaration.drive).toEqual([1]);
    expect(reading.engine.screws).toBe(4);
    // An exact all-false array is the explicit none-selected list.
    expect(read({ engine: engine({ fuelArray: [false, false, false, false, false] }) }).engine.declaration.fuel).toEqual([]);
    // A short, long or partly non-boolean array cannot assert "none selected".
    expect(read({ engine: engine({ fuelArray: [true] }) }).engine.declaration.fuel).toBeNull();
    expect(read({ engine: engine({ engineArray: [false, true] }) }).engine.declaration.engine).toBeNull();
    expect(read({ engine: engine({ driveArray: [false, 1, false, false] }) }).engine.declaration.drive).toBeNull();
    expect(read({ engine: engine({ fuelArray: undefined }) }).engine.declaration.fuel).toBeNull();
  });
});

describe('declared power lock', () => {
  it('keeps true, false and missing three facts and never turns a missing target into zero', () => {
    const locked = read();
    expect(locked.engine.lock).toEqual({ locked: true, powerHp: 60000, bunkerLt: 1500 });
    // A genuine zero locked bunker is a fact.
    expect(read({ design: { editing: { power_locked: true, power_hp: 60000, locked_bunker_lt: 0 } } }).engine.lock.bunkerLt).toBe(0);
    // An explicit false must never be read as an unknown, or the reverse.
    expect(read({ design: { editing: { power_locked: false } } }).engine.lock)
      .toEqual({ locked: false, powerHp: null, bunkerLt: null });
    // A missing flag is unknown; a non-boolean is unknown too.
    expect(read({ design: { editing: {} } }).engine.lock.locked).toBeNull();
    expect(read({ design: { editing: { power_locked: 'yes' } } }).engine.lock.locked).toBeNull();
    // A declared lock with no saved target is unknown, not zero.
    expect(read({ design: { editing: { power_locked: true } } }).engine.lock)
      .toEqual({ locked: true, powerHp: null, bunkerLt: null });
    // A result with no editing block at all stays unknown, never unlocked.
    expect(read({ design: {} }).engine.lock.locked).toBeNull();
  });
});

describe('whole-ship ledger roles', () => {
  it('reads only the two global roles, in tonnes, with their policy and unbound state', () => {
    const reading = read();
    expect(PROPULSION_LEDGER_ROLES).toEqual(['machinery', 'fuel']);
    expect(reading.engine.ledger.map(row => row.role)).toEqual(['machinery', 'fuel']);
    expect(reading.engine.ledger[0]).toMatchObject({ mode: 'declared', selectedT: 4000, estimateT: 3900, unresolved: false });
    expect(reading.engine.ledger[1]).toMatchObject({ mode: 'estimated', selectedT: 2000, estimateT: 2100, unresolved: false });
    // A role the ledger never bound keeps the masses it has and reports unbound.
    const unbound = readPropulsionPerformance(native({ ledger: { roles: { machinery: { selected_mass_t: 4000, estimate_t: 3900 } } } }));
    expect(unbound.engine.ledger[0]).toMatchObject({ role: 'machinery', mode: null, selectedT: 4000, unresolved: true });
    expect(unbound.engine.ledger[1]).toMatchObject({ role: 'fuel', selectedT: null, estimateT: null, unresolved: true });
  });
});

describe('performance groups', () => {
  it('reads the three source groups and keeps the source foot and second unconverted', () => {
    const reading = read();
    expect(reading.performance.groups.map(item => item.id)).toEqual(['stability', 'strength', 'seakeeping']);
    expect(group(reading, 'stability').readings.map(item => item.key))
      .toEqual(['performance.stability', 'performance.stabilityAdj', 'performance.metacentre', 'performance.rollPeriod']);
    expect(group(reading, 'strength').readings.map(item => item.key))
      .toEqual(['performance.strengthCross', 'performance.strengthLong', 'performance.strengthComp']);
    expect(group(reading, 'seakeeping').readings.map(item => item.key))
      .toEqual(['performance.seaboat', 'performance.seakeeping', 'performance.steadiness', 'performance.steadinessAdj']);
    // The metacentric height and the roll period keep the units the source saved.
    expect(fact(reading, 'performance.metacentre')).toMatchObject({ value: 3.5, unit: 'foot' });
    expect(fact(reading, 'performance.rollPeriod')).toMatchObject({ value: 12, unit: 'second' });
    expect(fact(reading, 'performance.strengthComp')).toMatchObject({ value: 0.85, unit: 'score' });
  });
});

describe('performance source flags', () => {
  it('keeps each flag strictly true, false or unknown', () => {
    const reading = readPropulsionPerformance(native({ performance: {
      tenderWarn: true, capsizeWarn: false, steady: 1, unsteady: null, goodSea: true, fineSea: 0,
    } }));
    expect(flag(reading, 'flag.tenderWarn').value).toBe(true);
    expect(flag(reading, 'flag.capsizeWarn').value).toBe(false);
    expect(flag(reading, 'flag.steady').value).toBeNull();
    expect(flag(reading, 'flag.unsteady').value).toBeNull();
    expect(flag(reading, 'flag.badSea').value).toBeNull();
    expect(flag(reading, 'flag.poorSea').value).toBeNull();
    expect(flag(reading, 'flag.goodSea').value).toBe(true);
    expect(flag(reading, 'flag.fineSea').value).toBeNull();
  });
});

describe('projection immutability', () => {
  it('never mutates the result it reads', () => {
    const input = native();
    const snapshot = JSON.stringify(input);
    readPropulsionPerformance(input);
    propulsionEnvelopeGate({ requested: true, status: 'completed', method_versions: { kernel: METHOD } }, input);
    expect(JSON.stringify(input)).toBe(snapshot);
  });
});

describe('frozen envelope gate', () => {
  it('lets a standalone reader through and only admits a report mount under its own envelope', () => {
    const result = native();
    // No envelope: a standalone frozen reading validates its own schema and method.
    expect(propulsionEnvelopeGate(undefined, result)).toBe(true);
    // The parent must have been requested and finished.
    expect(propulsionEnvelopeGate({ requested: false, status: 'completed', method_versions: {} }, result)).toBe(false);
    expect(propulsionEnvelopeGate({ requested: true, status: 'failed', method_versions: {} }, result)).toBe(false);
    // Completed or partial both reveal the residual fact.
    expect(propulsionEnvelopeGate({ requested: true, status: 'completed', method_versions: {} }, result)).toBe(true);
    expect(propulsionEnvelopeGate({ requested: true, status: 'partial', method_versions: {} }, result)).toBe(true);
    // A declared kernel must agree with the payload's own method version.
    expect(propulsionEnvelopeGate({ requested: true, status: 'completed', method_versions: { kernel: METHOD } }, result)).toBe(true);
    expect(propulsionEnvelopeGate({ requested: true, status: 'completed', method_versions: { kernel: 'other-kernel' } }, result)).toBe(false);
    // A non-string kernel identity asserts nothing and does not block.
    expect(propulsionEnvelopeGate({ requested: true, status: 'completed', method_versions: { kernel: 123 } }, result)).toBe(true);
  });
});

/* -------------------------------------------------------------- chapters */

const ready = (node: ReactElement) => render(inLanguage(<UnitProvider preferences={{}}>{node}</UnitProvider>, 'en'));
const zhReady = (node: ReactElement) => render(inLanguage(<UnitProvider preferences={{}}>{node}</UnitProvider>, 'zh-CN'));

describe('propulsion chapter', () => {
  it('withholds every fact while pending or failed and names an unsupported shape', () => {
    render(<PropulsionReadings result={native()} state="pending" />);
    expect(document.querySelector('[data-propulsion-readings][data-state="pending"]')).not.toBeNull();
    cleanup();
    render(<PropulsionReadings result={native()} state="failed" />);
    expect(document.querySelector('[data-propulsion-readings][data-state="failed"]')).not.toBeNull();
    cleanup();
    render(<PropulsionReadings result={{ schema: 'other', engine: engine() }} />);
    const unsupported = document.querySelector('[data-propulsion-readings][data-state="unavailable"]')!;
    expect(unsupported).not.toBeNull();
    expect(unsupported.textContent).toMatch(/supported native result shape/);
    // No source fact leaks from an unsupported result.
    expect(unsupported.querySelector('[data-propulsion-fact]')).toBeNull();
  });

  it('prints the declared chain, the source facts and the whole-ship roles, and reveals a real field', () => {
    const onEditField = vi.fn();
    ready(<PropulsionReadings result={native()} state="ready" onEditField={onEditField} />);
    // The declared fuel → engine → drive chain and the shaft count.
    expect(document.querySelector('[data-propulsion-chain="fuel"] dd')!.textContent).toBe('Coal fired boilers');
    expect(document.querySelector('[data-propulsion-chain="engine"] dd')!.textContent).toBe('Steam turbine');
    expect(document.querySelector('[data-propulsion-chain="drive"] dd')!.textContent).toBe('Geared');
    expect(document.querySelector('[data-propulsion-chain="screws"] dd')!.textContent).toBe('4');
    // The source's own units and a missing field as the unknown marker.
    expect(document.querySelector('[data-propulsion-fact="engine.hpMax"] dd')!.textContent).toContain('60,000 hp');
    expect(document.querySelector('[data-propulsion-fact="engine.range"] dd')!.textContent).toContain('12,000 nmi');
    expect(document.querySelector('[data-propulsion-fact="engine.bunkerMax"] dd')!.textContent).toContain('—');
    // The source machinery mass is long tons on the fact row and does not become
    // the ledger's tonnes.
    expect(document.querySelector('[data-propulsion-fact="engine.engineWeight"] dd')!.textContent).toContain('800 LT');
    // The two ledger roles are read in tonnes with their policy words.
    const machinery = document.querySelector('[data-propulsion-role="machinery"] dd')!;
    expect(machinery.textContent).toContain('4,000 t');
    expect(machinery.textContent).not.toContain('800 LT');
    expect(document.querySelector('[data-propulsion-role="fuel"] dd')!.textContent).toContain('2,000 t');
    // The reveal hands back the real source field name.
    fireEvent.click(document.querySelector('[data-propulsion-reveal="speed_max_kn"]')!);
    expect(onEditField).toHaveBeenCalledWith('speed_max_kn');
    fireEvent.click(document.querySelector('[data-propulsion-reveal="coal_percentage"]')!);
    expect(onEditField).toHaveBeenCalledWith('coal_percentage');
  });

  it('renders read-only with no reveal control when frozen', () => {
    ready(<PropulsionReadings result={native()} state="frozen" />);
    const section = document.querySelector('[data-propulsion-readings][data-state="frozen"]')!;
    expect(section.querySelector('[data-propulsion-reveal]')).toBeNull();
    // A frozen reading still prints the saved facts.
    expect(section.textContent).toContain('12,000 nmi');
  });
});

describe('performance chapter', () => {
  it('prints the three groups, the unconverted source units and the three flag states', () => {
    ready(<PerformanceReadings result={native()} state="ready" />);
    expect(document.querySelectorAll('[data-performance-group]')).toHaveLength(3);
    expect(document.querySelector('[data-performance-fact="performance.metacentre"] dd')!.textContent).toContain('3.5 ft');
    expect(document.querySelector('[data-performance-fact="performance.rollPeriod"] dd')!.textContent).toContain('12 s');
    expect(document.querySelector('[data-performance-fact="performance.strengthComp"] dd')!.textContent).toContain('0.85');
    expect(document.querySelector('[data-performance-flag="flag.tenderWarn"] dd')!.textContent).toBe('triggered');
    expect(document.querySelector('[data-performance-flag="flag.capsizeWarn"] dd')!.textContent).toBe('not triggered');
  });

  it('names an unknown flag as the unknown marker, never a "no"', () => {
    ready(<PerformanceReadings result={native({ performance: { tenderWarn: true } })} state="ready" />);
    expect(document.querySelector('[data-performance-flag="flag.capsizeWarn"] dd')!.textContent).toBe('—');
  });

  it('points a live reading at the trim field and the related chapters, and the frozen report at nothing', () => {
    const onEditField = vi.fn();
    const onOpenChapter = vi.fn();
    ready(<PerformanceReadings result={native()} state="ready" onEditField={onEditField} onOpenChapter={onOpenChapter} />);
    fireEvent.click(document.querySelector('[data-performance-trim]')!);
    expect(onEditField).toHaveBeenCalledWith('trim');
    fireEvent.click(document.querySelector('[data-performance-open="hull"]')!);
    expect(onOpenChapter).toHaveBeenCalledWith('hull');
    cleanup();

    ready(<PerformanceReadings result={native()} state="frozen" />);
    const frozen = document.querySelector('[data-performance-readings][data-state="frozen"]')!;
    expect(frozen.querySelector('[data-performance-related]')).toBeNull();
    expect(frozen.querySelector('[data-performance-trim]')).toBeNull();
    expect(frozen.querySelector('[data-performance-open]')).toBeNull();
  });

  it('withholds the readings while pending or failed', () => {
    render(<PerformanceReadings result={native()} state="pending" />);
    expect(document.querySelector('[data-performance-readings][data-state="pending"]')).not.toBeNull();
    cleanup();
    render(<PerformanceReadings result={native()} state="failed" />);
    expect(document.querySelector('[data-performance-readings][data-state="failed"]')).not.toBeNull();
  });
});

describe('propulsion and performance dictionary', () => {
  it('is complete in both languages with equal keys and no empty string', () => {
    const en = propulsionPerformanceDictionary('en');
    const zh = propulsionPerformanceDictionary('zh-CN');
    expect(Object.keys(zh).sort()).toEqual(Object.keys(en).sort());
    for (const key of Object.keys(en)) {
      expect(en[key as keyof typeof en]).not.toBe('');
      expect(zh[key as keyof typeof en]).not.toBe('');
    }
  });

  it('says the same readings in Chinese', () => {
    zhReady(<PerformanceReadings result={native()} state="ready" />);
    const section = document.querySelector('[data-performance-readings]')!;
    expect(section.textContent).toContain('初稳性高（来源推算）');
    expect(document.querySelector('[data-performance-fact="performance.metacentre"] dd')!.textContent).toContain('3.5 ft');
    // The source flags are stated in the reader's language.
    expect(document.querySelector('[data-performance-flag="flag.tenderWarn"] dd')!.textContent).toBe('已触发');
  });
});

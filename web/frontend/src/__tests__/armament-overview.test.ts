import { describe, expect, it } from 'vitest';

import { buildArmament, integralCount } from '../components/armamentModel';
import { buildVesselOverview } from '../components/vesselOverviewModel';
import { armamentSvg, wrapWidth } from '../components/armamentExport';
import { configChangeRows } from '../components/designConfigModel';
import { frozenNativeSides } from '../components/designFeedbackModel';
import type { AnalysisResult, ShipDesignResult } from '../types';
import {
  DRIVE_LABELS, ENGINE_LABELS, FUEL_LABELS, GUN_TYPE_LABELS, LAYOUT_LABELS, MOUNT_TYPE_LABELS,
  SELECTOR_LABELS, ledgerPolicyLabel, vesselLabel, vesselOverviewDictionary,
} from '../i18n/vesselOverview';

/**
 * The armament and vessel-overview contracts.
 *
 * These pin the reading rules the interface depends on: bank identity is
 * declared, zero is not unknown, selectors and actual counts stay separate, the
 * source units are untouched, ledger mass is never partitioned, and a change is
 * only a change against a compatible saved revision. The input is never mutated.
 */

const NATIVE = 'plimsoll-ship-design-result-1';
const METHOD = 'ship-design-native-v1';

/** One group of the four-group reference battery shape, with overrides. */
const group = (over: Record<string, unknown> = {}) => ({
  bank: 1, id: 'gun1', barrels: 12, mounts: 5, gunType: 1, mountType: 3, dateGun: 1910, calLength: 45,
  magazine: 150, layoutG1: 0, layoutG2: 0, selectorG1: 4, selectorG2: 6, perMountG1: 2, perMountG2: 3,
  mountsG1: 3, mountsG2: 2, mountSuperG1: 1, mountSubG1: 0, mountSuperG2: 1, mountDeckG1: 2, mountDeckG2: 1,
  mountSubG2: 0, superSuper: false, subSub: false, calibre: 6, calMet: 152.39999999999998,
  armFace: 0, armBack: 0, armBottom: 0, autoShellWeight: 108.92068909286012, shellWeightDeclared: 100,
  shellWeight: 100.0016860961914, gunWeight: 73.5140174405157, mountWeight: 269.32618116578857,
  magazineWeight: 100.00168252470262, broadsideWeight: 1200.0202331542969, armWeight: 0,
  totalWeight: 342.8401986063043, ...over,
});

/** The other four batteries, declared exactly zero. */
const zeroBanks = [2, 3, 4, 5].map(bank => ({
  bank, id: `gun${bank}`, barrels: 0, mounts: 0, gunType: 0, mountType: 0, dateGun: 0, calLength: 0,
  magazine: 0, layoutG1: 0, layoutG2: 0, selectorG1: 0, selectorG2: 0, perMountG1: 0, perMountG2: 0,
  mountsG1: 0, mountsG2: 0, mountSuperG1: 0, mountSubG1: 0, mountSuperG2: 0, mountDeckG1: 0, mountDeckG2: 0,
  mountSubG2: 0, superSuper: false, subSub: false, calibre: 0, calMet: 0, armFace: 0, armBack: 0,
  armBottom: 0, autoShellWeight: 0, shellWeightDeclared: 0, shellWeight: 0, gunWeight: 0,
  mountWeight: 0, magazineWeight: 0, broadsideWeight: 0, armWeight: 0, totalWeight: 0,
}));

const native = (over: Record<string, unknown> = {}) => ({
  schema: NATIVE,
  method_version: METHOD,
  status: 'available',
  basis_condition_id: 'design-normal',
  hull: { length: 590.5511474609375, beam: 82.02099609375, draught: 26.246719360351562 },
  freeboard: { freeboard: 17.04068374633789 },
  armour: { beltMain: 7, deck: 2, deckCoverage: 0, bulkheadType: 0 },
  engine: {
    speedMax: 27, speedCruise: 14, hpMax: 72098.859375, range: 7000,
    fuelArray: [true, true, false, false, false], engineArray: [false, false, true], driveArray: [false, true, false, false],
  },
  guns: { groups: [group(), ...zeroBanks] },
  ledger: { roles: {
    guns: { mode: 'estimated', estimate_t: 74.69369017390527, selected_mass_t: 74.69369017390527 },
    mounts: { mode: 'estimated', estimate_t: 273.64803383240826, selected_mass_t: 273.64803383240826 },
    ammunition: { mode: 'estimated', estimate_t: 101.60640040402306, selected_mass_t: 101.60640040402306 },
    gun_armour: { mode: 'estimated', estimate_t: 0, selected_mass_t: 0 },
  } },
  balance: { selected_mass_t: 21120.53972858855, estimated_mass_t: 21110.53972858855, target_displacement_t: 21110.539583401056, difference_t: 10.000145187492308 },
  ...over,
});

const configRows = (current: Record<string, unknown>, comparison: Record<string, unknown>, language: 'en' | 'zh-CN' = 'en') =>
  configChangeRows(current as unknown as ShipDesignResult, comparison as unknown as ShipDesignResult, language);

const sides = (current: Record<string, unknown>, comparison: Record<string, unknown>,
  identity?: { currentValid?: boolean; comparisonValid?: boolean }) =>
  frozenNativeSides(current as unknown as AnalysisResult, comparison as unknown as AnalysisResult, identity);

describe('armament native gates', () => {
  it('names an absent, foreign-schema, foreign-method or sectionless result', () => {
    expect(buildArmament(null).problem).toBe('absent');
    expect(buildArmament({ schema: 'other' }).problem).toBe('unsupported_schema');
    expect(buildArmament({ schema: NATIVE, method_version: 'other' }).problem).toBe('unsupported_method');
    expect(buildArmament({ schema: NATIVE, method_version: METHOD, guns: null }).problem).toBe('unavailable');
    expect(buildArmament({ schema: NATIVE, method_version: METHOD, status: 'unavailable', guns: { groups: [] } }).problem).toBe('unavailable');
  });

  it('never draws numbers for an unsupported result', () => {
    const reading = buildArmament({ schema: 'other', guns: { groups: [group()] } });
    expect(reading.supported).toBe(false);
    expect(reading.banks.every(bank => bank.state === 'missing')).toBe(true);
    expect(reading.balance).toBeNull();
  });
});

describe('armament bank identity', () => {
  it('reads the five banks by bank and id, never by array order', () => {
    const scrambled = native({ guns: { groups: [...zeroBanks].reverse().concat([group()]) } });
    const reading = buildArmament(scrambled);
    expect(reading.banks.map(bank => bank.bank)).toEqual([1, 2, 3, 4, 5]);
    expect(reading.banks[0].state).toBe('declared');
    expect(reading.banks[0].barrels).toBe(12);
    expect(reading.banks.slice(1).every(bank => bank.state === 'zero')).toBe(true);
  });

  it('keeps a missing bank distinct from a declared zero', () => {
    const noGunThree = native({ guns: { groups: [group(), ...zeroBanks.filter(bank => bank.bank !== 3)] } });
    const reading = buildArmament(noGunThree);
    expect(reading.banks[2].state).toBe('missing');
    expect(reading.banks[2].barrels).toBeNull();
    expect(reading.banks[3].state).toBe('zero');
    expect(reading.banks[3].barrels).toBe(0);
  });

  it('treats a duplicate or mismatched identity as ambiguous, not reassigned', () => {
    const duplicate = native({ guns: { groups: [group(), group({ mounts: 9 }), ...zeroBanks] } });
    expect(buildArmament(duplicate).banks[0].state).toBe('ambiguous');
    const mismatch = native({ guns: { groups: [group({ id: 'gun2' }), ...zeroBanks] } });
    const reading = buildArmament(mismatch);
    // The group claims bank 1 but names gun2: its identity is mismatched, so
    // bank 1 is ambiguous and bank 2 still reads its own declared zero.
    expect(reading.banks[0].state).toBe('ambiguous');
    expect(reading.banks[1].state).toBe('zero');
  });

  it('keeps a negative count as declared, never rounded', () => {
    const negative = native({ guns: { groups: [group({ barrels: -2 }), ...zeroBanks] } });
    expect(buildArmament(negative).banks[0].barrels).toBe(-2);
    expect(buildArmament(negative).banks[0].state).toBe('declared');
    // A negative or fractional count is raw text: it is never drawn as a whole
    // number of mounts.
    expect(integralCount(-2)).toBeNull();
    expect(integralCount(2.5)).toBeNull();
    expect(integralCount(0)).toBe(0);
    expect(integralCount(3)).toBe(3);
  });

  it('keeps an undeclared double-elevation flag unknown, never an explicit false', () => {
    const blank = native({ guns: { groups: [group({ superSuper: undefined, subSub: undefined }), ...zeroBanks] } });
    const bank = buildArmament(blank).banks[0];
    expect(bank.superSuper).toBeNull();
    expect(bank.subSub).toBeNull();
    expect(buildArmament(native()).banks[0].superSuper).toBe(false);
  });
});

describe('armament source facts', () => {
  it('keeps the 15-way selectors distinct even when barrel counts agree', () => {
    const reading = buildArmament(native());
    const [g1, g2] = reading.banks[0].groups;
    expect(g1.selector).toBe(4);
    expect(g2.selector).toBe(6);
    expect(g1.perMount).toBe(2);
    expect(g2.perMount).toBe(3);
    // Twin mount (3) and 2-gun mount (4) both mean two barrels of a mount, but
    // they are different declarations and must stay different labels.
    expect(vesselLabel('en', 'selector', 3)).toBe('Twin mount');
    expect(vesselLabel('en', 'selector', 4)).toBe('2-gun mount');
    expect(vesselLabel('en', 'selector', 3)).not.toBe(vesselLabel('en', 'selector', 4));
  });

  it('reads layout 18 as the explicit None, distinct from an unknown', () => {
    expect(vesselLabel('en', 'layout', 18)).toBe('None');
    expect(vesselLabel('zh-CN', 'layout', 18)).toBe('无（未设置）');
    expect(vesselLabel('en', 'layout', 17)).not.toBe('None');
    expect(vesselLabel('en', 'layout', 19)).toBeNull();
    expect(vesselLabel('en', 'layout', null)).toBeNull();
  });

  it('reads a missing selector or an out-of-range one as unknown', () => {
    const gappy = native({ guns: { groups: [group({ selectorG1: 99 }), ...zeroBanks] } });
    const [g1] = buildArmament(gappy).banks[0].groups;
    expect(g1.selector).toBeNull();
    expect(g1.layout).toBe(0);
  });

  it('reads calibre in inches, armour in inches, shells in pounds and masses in long tons', () => {
    const bank = buildArmament(native()).banks[0];
    expect(bank.calibreIn).toBe(6);
    expect(bank.armFaceIn).toBe(0);
    expect(bank.shellWeightDeclaredLb).toBe(100);
    expect(bank.broadsideWeightLb).toBeCloseTo(1200.0202331542969, 6);
    expect(bank.gunWeightLt).toBeCloseTo(73.5140174405157, 9);
    expect(bank.totalWeightLt).toBeCloseTo(342.8401986063043, 9);
  });
});

describe('armament ledger authority', () => {
  it('reads selected mass only from the global ledger roles, never per battery', () => {
    const reading = buildArmament(native());
    expect(reading.ledger.guns.selectedT).toBeCloseTo(74.69369017390527, 9);
    expect(reading.ledger.mounts.selectedT).toBeCloseTo(273.64803383240826, 9);
    expect(reading.ledger.ammunition.selectedT).toBeCloseTo(101.60640040402306, 9);
    // The source estimate and the ledger selected mass are separate numbers; the
    // source mass never becomes a ledger mass and vice versa.
    expect(reading.banks[0].totalWeightLt).not.toBe(reading.ledger.guns.selectedT);
    for (const bank of reading.banks) {
      expect('selectedT' in bank).toBe(false);
    }
    expect(reading.balance?.selected_mass_t).toBe(21120.53972858855);
  });
});

describe('armament comparison', () => {
  it('highlights only the changed bank against a compatible saved revision', () => {
    const baseline = native();
    const current = native({ guns: { groups: [group({ calibre: 5, selectorG2: 5 }), ...zeroBanks] } });
    const reading = buildArmament(current, baseline);
    expect(reading.comparable).toBe(true);
    expect(reading.banks[0].changed).toBe(true);
    expect(reading.banks[1].changed).toBe(false);
  });

  it('shows a manual ledger policy change even when the batteries are unchanged', () => {
    const baseline = native({ ledger: { roles: { ...native().ledger.roles, guns: { mode: 'declared', estimate_t: 74.69369017390527, selected_mass_t: 90 } } } });
    const reading = buildArmament(native(), baseline);
    expect(reading.banks[0].changed).toBe(false);
    expect(reading.ledger.guns.changed).toBe(true);
    expect(reading.ledger.mounts.changed).toBe(false);
  });

  it('withholds highlights when schema, method or basis differ', () => {
    const foreignBasis = native({ basis_condition_id: 'deep' });
    expect(buildArmament(native(), foreignBasis).comparable).toBe(false);
    expect(buildArmament(native(), { schema: 'other' }).comparable).toBe(false);
    expect(buildArmament(native(), { schema: NATIVE, method_version: 'other' }).comparable).toBe(false);
    expect(buildArmament(native(), null).comparable).toBe(false);
  });
});

describe('armament immutability', () => {
  it('never mutates the result it reads', () => {
    const input = native({ guns: { groups: [group(), ...zeroBanks] } });
    const snapshot = JSON.stringify(input);
    buildArmament(input, input);
    buildVesselOverview(input);
    expect(JSON.stringify(input)).toBe(snapshot);
  });
});

describe('vessel overview sections', () => {
  it('gives six chapter sections with explicit unit identities', () => {
    const overview = buildVesselOverview(native());
    expect(overview.supported).toBe(true);
    expect(overview.sections.map(section => section.id)).toEqual(['hull', 'freeboard', 'armament', 'armour', 'propulsion', 'weight']);
    expect(overview.sections.map(section => section.chapter)).toEqual(['hull', 'freeboard', 'guns', 'armour', 'propulsion', 'weights']);

    const hullLength = overview.sections[0].facts.find(fact => fact.key === 'hull.length');
    expect(hullLength?.kind).toBe('length');
    expect(hullLength?.storedUnit).toBe('ft');
    expect(hullLength?.chapter).toBe('hull');

    const belt = overview.sections[3].facts.find(fact => fact.key === 'armour.beltMain');
    expect(belt?.kind).toBe('inches');
    const coverage = overview.sections[3].facts.find(fact => fact.key === 'armour.deckCoverage');
    expect(coverage?.kind).toBe('enum');
    expect(coverage?.index).toBe(0);

    const speed = overview.sections[4].facts.find(fact => fact.key === 'propulsion.speedMax');
    expect(speed?.kind).toBe('speed');
    expect(speed?.storedUnit).toBe('kn');
    const power = overview.sections[4].facts.find(fact => fact.key === 'propulsion.hpMax');
    expect(power?.kind).toBe('power-hp');
    expect(power?.storedUnit).toBeUndefined();
    const range = overview.sections[4].facts.find(fact => fact.key === 'propulsion.range');
    expect(range?.kind).toBe('range-nmi');
    const fuel = overview.sections[4].facts.find(fact => fact.key === 'propulsion.fuel');
    expect(fuel?.kind).toBe('flags');
    expect(fuel?.flags).toEqual([0, 1]);
  });

  it('states five banks and four ledger rows, with balance in tonnes', () => {
    const overview = buildVesselOverview(native());
    const armament = overview.sections[2];
    expect(armament.facts).toHaveLength(5);
    expect(armament.facts[0].kind).toBe('bank');
    expect(armament.facts[0].bank?.barrels).toBe(12);
    expect(armament.facts[1].bank?.state).toBe('zero');

    const weight = overview.sections[5];
    expect(weight.facts.find(fact => fact.key === 'weight.selected')?.storedUnit).toBe('t');
    for (const role of ['guns', 'mounts', 'ammunition', 'gun_armour']) {
      const fact = weight.facts.find(item => item.key === `weight.ledger.${role}`);
      expect(fact?.kind).toBe('ledger');
      expect(fact?.ledger?.role).toBe(role);
    }
    expect(weight.facts.find(fact => fact.key === 'weight.ledger.guns')?.ledger?.selectedT).toBeCloseTo(74.69369017390527, 9);
  });

  it('separates an undeclared selector array from an explicit none-selected one', () => {
    const absent = buildVesselOverview(native({ engine: { speedMax: 27, speedCruise: 14, hpMax: 1, range: 2 } }));
    expect(absent.sections[4].facts.find(fact => fact.key === 'propulsion.fuel')?.flags).toBeNull();

    const malformed = buildVesselOverview(native({ engine: { fuelArray: [true] } }));
    expect(malformed.sections[4].facts.find(fact => fact.key === 'propulsion.fuel')?.flags).toBeNull();

    const partial = buildVesselOverview(native({ engine: { fuelArray: [false, false, false] } }));
    expect(partial.sections[4].facts.find(fact => fact.key === 'propulsion.fuel')?.flags).toBeNull();

    const none = buildVesselOverview(native({ engine: { fuelArray: [false, false, false, false, false] } }));
    expect(none.sections[4].facts.find(fact => fact.key === 'propulsion.fuel')?.flags).toEqual([]);

    const some = buildVesselOverview(native());
    expect(some.sections[4].facts.find(fact => fact.key === 'propulsion.fuel')?.flags).toEqual([0, 1]);
  });

  it('names an unsupported, absent or sectionless result instead of guessing', () => {
    expect(buildVesselOverview(null).problem).toBe('absent');
    expect(buildVesselOverview({ schema: 'other' }).problem).toBe('unsupported_schema');
    expect(buildVesselOverview({ schema: NATIVE, method_version: 'other' }).problem).toBe('unsupported_method');
    expect(buildVesselOverview({ schema: NATIVE, method_version: METHOD }).problem).toBe('unavailable');
    expect(buildVesselOverview({ schema: 'other' }).sections).toEqual([]);
  });

  it('keeps an undeclared hull value unknown, not zero', () => {
    const sparse = native({ hull: { length: 590.5511474609375 } });
    const overview = buildVesselOverview(sparse);
    expect(overview.sections[0].facts.find(fact => fact.key === 'hull.length')?.value).toBe(590.5511474609375);
    expect(overview.sections[0].facts.find(fact => fact.key === 'hull.beam')?.value).toBeNull();
  });
});

describe('armament export wrapping', () => {
  it('wraps to the pixel width, splitting an unbroken CJK run without losing a glyph', () => {
    const cjk = '舰'.repeat(120);
    const lines = wrapWidth(cjk, 200, 10);
    // 200 px of 10 px glyphs is twenty per line; the run is far longer.
    expect(lines.length).toBe(6);
    expect(lines.every(line => line.length <= 20)).toBe(true);
    expect(lines.join('')).toBe(cjk);
  });

  it('keeps every non-space character of a Latin line, breaking at its spaces', () => {
    const text = 'Gun mass (source) long ton estimate for the five batteries of this design';
    const lines = wrapWidth(text, 120, 10);
    expect(lines.length).toBeGreaterThan(1);
    expect(lines.join(' ').replace(/\s+/g, '')).toBe(text.replace(/\s+/g, ''));
    for (const line of lines) expect(widthOf(line)).toBeLessThanOrEqual(120);
  });

  it('preserves a long context label in the serialized document', () => {
    const label = `${'舰'.repeat(90)} · revision 7`;
    const svg = armamentSvg(buildArmament(native()), {
      language: 'zh-CN', prefs: { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' },
      uid: 'wrap', interactive: false, contextLabel: label,
    });
    const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
    expect(parsed.querySelector('parsererror')).toBeNull();
    // The glyphs and the closing text survive intact, across as many lines as fit.
    expect(parsed.documentElement.textContent).toContain('revision 7');
    expect(parsed.documentElement.textContent).toContain('舰'.repeat(90));
  });

  it('states the ledger policy beside the masses in the drawing', () => {
    const declared = native({ ledger: { roles: { ...native().ledger.roles, guns: { mode: 'declared', estimate_t: 74.69, selected_mass_t: 90 } } } });
    const svg = armamentSvg(buildArmament(declared), {
      language: 'en', prefs: { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' },
      uid: 'policy', interactive: false,
    });
    expect(svg).toContain('declared (manual)');
    expect(svg).not.toContain('policy not set');
  });

  it('keeps the ledger role and its values in two non-overlapping columns', () => {
    const svg = armamentSvg(buildArmament(native()), {
      language: 'en', prefs: { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' },
      uid: 'columns', interactive: false,
    });
    const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
    const roleText = [...parsed.querySelectorAll('text')].find(node => node.textContent === 'Gun armour');
    const valueText = [...parsed.querySelectorAll('text')].find(node => (node.textContent ?? '').includes('selected'));
    expect(roleText).toBeDefined();
    expect(valueText).toBeDefined();
    expect(Number(roleText?.getAttribute('x'))).toBeLessThan(Number(valueText?.getAttribute('x')));
  });
});

/** The width of a line under the serializer's own glyph metric, at size 10. */
function widthOf(line: string): number {
  let total = 0;
  for (const char of line) {
    const code = char.codePointAt(0) ?? 0;
    if (code === 32) total += 3;
    else if ((code >= 0x2e80 && code <= 0xa4cf) || (code >= 0xac00 && code <= 0xd7a3)) total += 10;
    else total += 5.4;
  }
  return total;
}

describe('ledger policy words', () => {
  it('names estimated, declared, another and unset policies distinctly', () => {
    const estimated = ledgerPolicyLabel('en', 'estimated');
    const declared = ledgerPolicyLabel('en', 'declared');
    expect(estimated).not.toBe(declared);
    expect(ledgerPolicyLabel('en', null)).not.toBe(estimated);
    expect(ledgerPolicyLabel('en', 'other')).not.toBe(estimated);
    expect(ledgerPolicyLabel('en', null)).not.toBe(ledgerPolicyLabel('en', 'other'));
    expect(ledgerPolicyLabel('zh-CN', 'declared')).not.toBe(declared);
  });
});

describe('frozen configuration changes', () => {
  it('reads the five batteries, hull, armour and propulsion in current → comparison order', () => {
    const current = native();
    const comparison = native({
      hull: { length: 600, beam: 82.02099609375, draught: 26.246719360351562 },
      armour: { beltMain: 8, deck: 2, deckCoverage: 1 },
      engine: { speedMax: 28, speedCruise: 14, hpMax: 72098.859375, range: 7000, fuelArray: [true, false, false, false, false], engineArray: [false, false, true], driveArray: [false, true, false, false] },
    });
    const rows = configRows(native(), comparison, 'en');
    expect(rows.filter(row => row.group === 'battery')).toHaveLength(5);

    const length = rows.find(row => row.key === 'hull.length');
    expect(length?.kind).toBe('number');
    expect(length?.before).toBeCloseTo(590.5511474609375, 6);
    expect(length?.after).toBe(600);
    expect(length?.dimension).toBe('length');

    const belt = rows.find(row => row.key === 'armour.beltMain');
    expect(belt?.kind).toBe('thickness');
    expect(belt?.beforeText).toBe('7 in (177.8 mm)');
    expect(belt?.afterText).toBe('8 in (203.2 mm)');

    const coverage = rows.find(row => row.key === 'armour.deckCoverage');
    expect(coverage?.kind).toBe('categorical');
    expect(coverage?.before).toBeUndefined();
    expect(coverage?.beforeText).not.toBe(coverage?.afterText);
  });

  it('gives a categorical battery row its two configuration labels and no number', () => {
    const rows = configRows(native(), native({ guns: { groups: [group({ calibre: 8, mountType: 5 }), ...zeroBanks] } }), 'en');
    const battery = rows.find(row => row.key === 'battery.1');
    expect(battery?.kind).toBe('categorical');
    expect(battery?.bank).toBe(1);
    expect(battery?.before).toBeUndefined();
    expect(battery?.after).toBeUndefined();
    expect(battery?.beforeText).toContain('6 in');
    expect(battery?.afterText).toContain('8 in');
    expect(battery?.beforeText).not.toBe(battery?.afterText);
  });

  it('reads an undeclared battery as unavailable instead of borrowing another', () => {
    const rows = configRows(native({ guns: { groups: [group(), ...zeroBanks.filter(bank => bank.bank !== 3)] } }), native(), 'en');
    expect(rows.find(row => row.key === 'battery.3')?.beforeText).toBe('not declared');
  });

  it('keeps an absent or malformed selector array unknown, never none selected', () => {
    const rows = configRows(native({ engine: { speedMax: 27, fuelArray: [true] } }), native(), 'en');
    expect(rows.find(row => row.key === 'propulsion.fuelArray')?.beforeText).toBe('not declared');
    const none = configRows(native({ engine: { fuelArray: [false, false, false, false, false] } }), native(), 'en');
    expect(none.find(row => row.key === 'propulsion.fuelArray')?.beforeText).toBe('none declared');
  });

  it('reports equal declarations as equal text and equal numbers, with no sentinel', () => {
    const rows = configChangeRows(native(), native(), 'en');
    expect(rows.find(row => row.key === 'battery.1')?.beforeText).toBe(rows.find(row => row.key === 'battery.1')?.afterText);
    expect(rows.find(row => row.key === 'hull.length')?.before).toBe(rows.find(row => row.key === 'hull.length')?.after);
    expect(rows.find(row => row.key === 'hull.length')?.kind).toBe('number');
  });
});

describe('frozen native side gates', () => {
  const run = (data: unknown, over: Record<string, unknown> = {}) => ({
    project_id: 'p1',
    input_snapshot: { id: 'p1', revision: 3, ship_design: { condition_id: 'design-normal' } },
    stages: { ship_design: { requested: true, status: 'completed', data } },
    ...over,
  });

  it('quotes nothing until both sides are readable and agree on identity', () => {
    const current = run(native());
    const comparison = run(native({ basis_condition_id: 'deep' }));
    expect(sides(current, comparison).comparable).toBe(false);
    expect(sides(current, comparison).problems).toContain('feedback.incompatible.basis');

    const same = run(native());
    expect(sides(current, same).comparable).toBe(true);
    expect(sides(current, same).requested).toBe(true);

    const unwritable = run({ schema: 'other' });
    expect(sides(current, unwritable).comparable).toBe(false);
    expect(sides(current, unwritable).problems).toContain('feedback.frozen.schema');
  });

  it('treats a run with no requested native stage as not requested at all', () => {
    const none = { project_id: 'p1', input_snapshot: { id: 'p1', revision: 1 }, stages: {} };
    expect(sides(none, none).requested).toBe(false);
    expect(sides(none, none).comparable).toBe(false);
  });

  it('withholds both sides when the identity verdict rejects either run', () => {
    const current = run(native());
    const pair = sides(current, run(native()), { comparisonValid: false });
    expect(pair.comparable).toBe(false);
    expect(pair.problems).toContain('feedback.frozen.identity');
  });
});

describe('vessel overview dictionary', () => {
  it('is complete in both languages with equal keys', () => {
    const en = Object.keys(vesselOverviewDictionary('en')).sort();
    const zh = Object.keys(vesselOverviewDictionary('zh-CN')).sort();
    expect(zh).toEqual(en);
    for (const key of en) {
      expect(vesselOverviewDictionary('en')[key as never]).not.toBe('');
      expect(vesselOverviewDictionary('zh-CN')[key as never]).not.toBe('');
    }
  });

  it('keeps every authority enum table complete and distinct', () => {
    expect(GUN_TYPE_LABELS.en).toHaveLength(7);
    expect(MOUNT_TYPE_LABELS.en).toHaveLength(7);
    expect(LAYOUT_LABELS.en).toHaveLength(19);
    expect(LAYOUT_LABELS.en[18]).toBe('None');
    expect(SELECTOR_LABELS.en).toHaveLength(15);
    expect(FUEL_LABELS.en).toHaveLength(5);
    expect(ENGINE_LABELS.en).toHaveLength(3);
    expect(DRIVE_LABELS.en).toHaveLength(4);
    for (const table of [GUN_TYPE_LABELS, MOUNT_TYPE_LABELS, LAYOUT_LABELS, FUEL_LABELS, ENGINE_LABELS, DRIVE_LABELS]) {
      expect(table['zh-CN']).toHaveLength(table.en.length);
    }
    // All fifteen selectors are distinct labels; index 2 and index 5 both mean a
    // row of quad mounts but are different declarations and must stay different.
    expect(new Set(SELECTOR_LABELS.en).size).toBe(15);
    expect(SELECTOR_LABELS.en[2]).not.toBe(SELECTOR_LABELS.en[5]);
  });
});

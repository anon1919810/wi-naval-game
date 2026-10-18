import { describe, expect, it } from 'vitest';

import {
  ARMOUR_REGION_ORDER, FRACTION_TOLERANCE, buildArmourDiagram,
} from '../components/armourDiagramModel';
import { armourDiagramFileName, armourDiagramSvg, wrapText } from '../components/armourDiagramExport';
import { CANONICAL_PREFERENCES } from '../components/units';

/**
 * The armour reader and its serializer, before either is put on screen.
 *
 * These tests pin the contract the diagram depends on: unknown stays unknown and
 * zero stays zero; an overlong, negative or non-positive-denominator length is
 * reported, never trimmed; the saved single-precision deck fractions are read
 * with the documented tolerance; the ledger alone supplies masses; a change is a
 * known fact differing; and every download carries all seven roles with the
 * ledger's masses and localized policies regardless of what is selected.
 */

/* --------------------------------------------------------------- fixtures */

const realFractions = {
  fcLength: 0.20499999821186066,
  fdLength: 0.30000001192092896,
  adLength: 0.3400000035762787,
  qdLength: 0.1550000011920929,
};

const ledgerRoles = () => ({
  belt_main: { mode: 'estimated', estimate_t: 1114.57, selected_mass_t: 1114.57 },
  belt_ends: { mode: 'estimated', estimate_t: 157.89, selected_mass_t: 157.89 },
  belt_upper: { mode: 'estimated', estimate_t: 402.2, selected_mass_t: 402.2 },
  bulkhead: { mode: 'estimated', estimate_t: 189.47, selected_mass_t: 189.47 },
  bulge: { mode: 'estimated', estimate_t: 56.39, selected_mass_t: 56.39 },
  deck: { mode: 'declared', estimate_t: 1267.13, selected_mass_t: 1277.13 },
  conning: { mode: 'estimated', estimate_t: 449.5, selected_mass_t: 449.5 },
});

const armour = () => ({
  beltMain: 7, beltEnds: 3, beltUpper: 4, bulkhead: 1.5, bulge: 0.5,
  deck: 2, deckFC: 1, deckQD: 1.25, conningFor: 8, conningAft: 4,
  beltMainLength: 280, beltMainHeight: 12, beltEndsLength: 140, beltEndsHeight: 10,
  beltUpperLength: 260, beltUpperHeight: 8, bulkheadLength: 240, bulkheadHeight: 14,
  bulgeLength: 300, bulgeHeight: 10, bulkheadBeam: 88.58267716535433, beltsIncline: 30,
  bulkheadType: 0, deckCoverage: 0,
  // The block's weights are LONG TONS; the model must never read them as masses.
  weightBeltMain: 1096.9, weightDeck: 1247.1, weightConning: 442.4, weight: 3579.7, weightBelts: 1648.2,
  beltCover: 0.7294359389890516, maxBeltHeight: 49.150652592383295, armourWarn: false,
});

const freeboard = (over: Record<string, unknown> = {}) => ({
  ...realFractions,
  freeQDAft: 26, freeQDFor: 26, freeADAft: 25, freeADFor: 25,
  freeFDAft: 24, freeFDFor: 24, freeFCAft: 30, freeFCFor: 34,
  lengthBow: 20, lengthStern: 0, ...over,
});

const native = (over: Record<string, unknown> = {}) => ({
  schema: 'plimsoll-ship-design-result-1',
  method_version: 'ship-design-native-v1',
  status: 'available',
  basis_condition_id: 'design-normal',
  hull: { length: 590.55, beam: 88.58 },
  freeboard: freeboard(),
  armour: armour(),
  ledger: { roles: ledgerRoles(), basis_condition_id: 'design-normal' },
  balance: { selected_mass_t: 71934.15, estimated_mass_t: 71924.15, target_displacement_t: 71924.15, difference_t: 10.0 },
  source_design: { parameters: { ship_name: 'Queen Mary' } },
  ...over,
});

const band = (diagram: ReturnType<typeof buildArmourDiagram>, role: string) =>
  diagram.bands.find(item => item.role === role)!;

/* ---------------------------------------------------------------- gating */

describe('armour reading gate', () => {
  it('names each unavailable shape instead of drawing one', () => {
    expect(buildArmourDiagram(null).problem).toBe('absent');
    expect(buildArmourDiagram({ schema: 'other', method_version: 'ship-design-native-v1' }).problem).toBe('unsupported_schema');
    expect(buildArmourDiagram({ schema: 'plimsoll-ship-design-result-1', method_version: 'later' }).problem).toBe('unsupported_method');
    expect(buildArmourDiagram(native({ armour: undefined })).problem).toBe('unavailable');
    expect(buildArmourDiagram(native({ status: 'unavailable' })).problem).toBe('unavailable');
  });

  it('draws a supported reply and reads the shared freeboard geometry', () => {
    const diagram = buildArmourDiagram(native());
    expect(diagram.supported).toBe(true);
    expect(diagram.problem).toBeNull();
    expect(diagram.freeboard?.length).toBeCloseTo(590.55);
    expect(diagram.context.hullLengthFt).toBeCloseTo(590.55);
    expect(diagram.context.sourceName).toBe('Queen Mary');
  });
});

/* ------------------------------------------------------------------ facts */

describe('armour facts', () => {
  it('keeps lengths and heights in feet, thickness in inches, and a saved zero as zero', () => {
    const diagram = buildArmourDiagram(native({
      armour: { ...armour(), beltMainLength: 0, beltEndsHeight: 0, deck: 0 },
    }));
    expect(band(diagram, 'belt_main').lengthFt).toBe(0);
    expect(band(diagram, 'belt_main').heightFt).toBe(12);
    expect(band(diagram, 'belt_main').thicknessIn).toBe(7);
    expect(band(diagram, 'belt_ends').heightFt).toBe(0);
    expect(band(diagram, 'belt_main').lengthValid).toBe(true);
  });

  it('reads a length through the ledger, never the long-ton block', () => {
    const diagram = buildArmourDiagram(native());
    expect(diagram.ledger.belt_main?.selectedT).toBeCloseTo(1114.57);
    expect(diagram.ledger.deck?.mode).toBe('declared');
    // No raw weight survives on any band as a mass.
    expect(diagram.bands.every(item => !('weightT' in item))).toBe(true);
    expect(diagram.deck && 'weightT' in diagram.deck).toBe(false);
  });

  it('reports a missing length as unknown, never zero', () => {
    const diagram = buildArmourDiagram(native({ armour: { ...armour(), beltMainLength: undefined } }));
    expect(band(diagram, 'belt_main').lengthFt).toBeNull();
    expect(band(diagram, 'belt_main').lengthValid).toBe(false);
    expect(band(diagram, 'belt_main').lengthProblem).toBe('missing');
  });

  it('reports overlong, negative and non-positive-denominator lengths', () => {
    expect(band(buildArmourDiagram(native({ armour: { ...armour(), beltMainLength: 900 } })), 'belt_main').lengthProblem).toBe('overlong');
    expect(band(buildArmourDiagram(native({ armour: { ...armour(), beltMainLength: -5 } })), 'belt_main').lengthProblem).toBe('negative');
    expect(band(buildArmourDiagram(native({ hull: { length: 0 } })), 'belt_main').lengthProblem).toBe('nohull');
    expect(band(buildArmourDiagram(native({ hull: null })), 'belt_main').lengthProblem).toBe('nohull');
  });

  it('carries the declared bulkhead beam and type', () => {
    const diagram = buildArmourDiagram(native());
    expect(band(diagram, 'bulkhead').beamFt).toBeCloseTo(88.58267716535433);
    expect(diagram.context.bulkheadTypeIndex).toBe(0);
  });
});

/* ------------------------------------------------------------------- deck */

describe('deck partition', () => {
  it('accepts the saved single-precision fractions inside the documented tolerance', () => {
    const diagram = buildArmourDiagram(native());
    expect(diagram.deck?.totalFraction).toBeCloseTo(1.0000000149011612);
    expect(diagram.deck?.totalValid).toBe(true);
    expect(diagram.deck?.overlong).toBe(false);
    expect(diagram.deck?.invalid).toBe(false);
    expect(FRACTION_TOLERANCE).toBe(1e-6);
    expect(diagram.deck?.segments.map(segment => segment.key)).toEqual(['quarterdeck', 'afterdeck', 'flatDeck', 'forecastle']);
  });

  it('reports fractions that overflow the hull instead of trimming them', () => {
    const diagram = buildArmourDiagram(native({ freeboard: freeboard({ qdLength: 0.5, adLength: 0.5, fdLength: 0.5, fcLength: 0.5 }) }));
    expect(diagram.deck?.overlong).toBe(true);
    expect(diagram.deck?.totalValid).toBe(false);
  });

  it('reports a negative fraction as invalid', () => {
    const diagram = buildArmourDiagram(native({ freeboard: freeboard({ qdLength: -0.1 }) }));
    expect(diagram.deck?.invalid).toBe(true);
    expect(diagram.deck?.segments[0].valid).toBe(false);
  });

  it('leaves the later segments unplaced when an earlier fraction is unknown', () => {
    const diagram = buildArmourDiagram(native({ freeboard: freeboard({ adLength: undefined }) }));
    expect(diagram.deck?.totalFraction).toBeNull();
    expect(diagram.deck?.segments[1].start).toBeNull();
    expect(diagram.deck?.segments[2].start).toBeNull();
  });
});

/* ---------------------------------------------------------------- changes */

describe('changes against a saved revision', () => {
  it('marks a known dimension that moved', () => {
    const diagram = buildArmourDiagram(native({ armour: { ...armour(), beltMain: 8 } }), native());
    expect(diagram.comparable).toBe(true);
    expect(diagram.changed.belt_main).toBe(true);
    expect(diagram.changed.belt_ends).toBe(false);
  });

  it('does not mark two unchanged unknowns as a change', () => {
    const missing = native({ armour: { ...armour(), beltMain: undefined } });
    const diagram = buildArmourDiagram(missing, structuredClone(missing));
    expect(diagram.changed.belt_main).toBe(false);
    expect(diagram.changed.deck).toBe(false);
  });

  it('marks a policy-only ledger change', () => {
    const saved = native();
    const draft = native();
    (draft.ledger.roles.deck as Record<string, unknown>).mode = 'estimated';
    const diagram = buildArmourDiagram(draft, saved);
    expect(diagram.changed.deck).toBe(true);
  });

  it('marks a bulkhead type-only change and a beam change', () => {
    const saved = native();
    const typeChanged = buildArmourDiagram(native({ armour: { ...armour(), bulkheadType: 1 } }), saved);
    expect(typeChanged.changed.bulkhead).toBe(true);
    const beamChanged = buildArmourDiagram(native({ armour: { ...armour(), bulkheadBeam: 90 } }), saved);
    expect(beamChanged.changed.bulkhead).toBe(true);
  });

  it('withholds the comparison when the basis differs', () => {
    const diagram = buildArmourDiagram(native({ basis_condition_id: 'other' }), native());
    expect(diagram.comparable).toBe(false);
    expect(diagram.changed).toEqual({});
  });

  it('never mutates the reply it reads', () => {
    const reply = native();
    const snapshot = structuredClone(reply);
    buildArmourDiagram(reply, native());
    expect(reply).toEqual(snapshot);
  });
});

/* -------------------------------------------------------------- serializer */

const render = (over: Record<string, unknown> = {}) => ({
  language: 'en' as const,
  prefs: CANONICAL_PREFERENCES,
  uid: 'u1',
  interactive: true,
  selected: null,
  ...over,
});

/** Every `<text>` node's content, joined with single spaces, so a wrapped phrase reads whole again. */
const textOf = (svg: string): string =>
  [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]).join(' ');

describe('the standalone SVG', () => {
  it('parses as standalone SVG XML, including the shared freeboard context', () => {
    const svg = armourDiagramSvg(buildArmourDiagram(native()), render());
    const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
    expect(parsed.querySelector('parsererror')).toBeNull();
    expect(parsed.querySelector('[data-armour-freeboard] polyline')).not.toBeNull();
  });

  it('carries the namespace, a title, its own background and every region', () => {
    const svg = armourDiagramSvg(buildArmourDiagram(native()), render());
    expect(svg).toContain('xmlns="http://www.w3.org/2000/svg"');
    expect(svg).toContain('<title');
    expect(svg).toContain('fill="#ffffff"');
    for (const role of ARMOUR_REGION_ORDER) expect(svg).toContain(`data-armour-region="${role}"`);
  });

  it('is interactive as a group of buttons and static as an image', () => {
    const live = armourDiagramSvg(buildArmourDiagram(native()), render({ interactive: true }));
    expect(live).toContain('role="group"');
    expect(live).toContain('role="button"');
    const frozen = armourDiagramSvg(buildArmourDiagram(native()), render({ interactive: false, selected: 'deck' }));
    expect(frozen).toContain('role="img"');
    expect(frozen).not.toContain('role="button"');
  });

  it('includes every role\'s ledger mass and policy, localized, independent of selection', () => {
    const diagram = buildArmourDiagram(native());
    const en = armourDiagramSvg(diagram, render());
    for (const copy of ['Main belt', 'End belts', 'Upper belt', 'Bulkheads', 'Bulges', 'Deck', 'Conning towers']) {
      expect(en).toContain(copy);
    }
    expect(en).toContain('1,114.57 t');
    expect(en).toContain('declared (manual)');
    expect(en).toContain('estimated');
    const zh = armourDiagramSvg(diagram, render({ language: 'zh-CN' }));
    expect(zh).toContain('估算');
    expect(zh).toContain('声明（手动）');
    expect(zh).not.toContain('declared');
  });

  it('includes the shared freeboard context as a polyline', () => {
    const svg = armourDiagramSvg(buildArmourDiagram(native()), render());
    expect(svg).toContain('data-armour-freeboard');
    expect(svg).toContain('<polyline');
    const missing = armourDiagramSvg(buildArmourDiagram(native({ freeboard: null })), render());
    expect(missing).not.toContain('data-armour-freeboard');
    expect(textOf(missing)).toContain('cannot be plotted');
  });

  it('hatches an overflowing deck instead of painting clipped rectangles', () => {
    const overlong = buildArmourDiagram(native({ freeboard: freeboard({ qdLength: 0.5, adLength: 0.5, fdLength: 0.5, fcLength: 0.5 }) }));
    const svg = armourDiagramSvg(overlong, render());
    expect(textOf(svg)).toContain('total more than the hull');
    expect(svg).toContain('url(#hatch-u1)');
  });

  it('omits the freeboard context when deck fractions would reverse its stations', () => {
    const invalid = buildArmourDiagram(native({ freeboard: freeboard({
      fcLength: 0.6, fdLength: 0.6, qdLength: 0.1, adLength: -0.3,
    }) }));
    expect(armourDiagramSvg(invalid, render())).not.toContain('data-armour-freeboard');
  });

  it('names capacities in both inches and millimetres and states the units', () => {
    const svg = armourDiagramSvg(buildArmourDiagram(native()), render());
    expect(svg).toContain('7 in (177.8 mm)');
    expect(svg).toContain('ft');
  });

  it('never lets a label run past the sheet, even unbroken CJK', () => {
    const svg = armourDiagramSvg(buildArmourDiagram(native()), render({ language: 'zh-CN', runId: 'run-0123456789abcdef0123456789abcdef' }));
    const contents = [...svg.matchAll(/<text[^>]*>([^<]*)<\/text>/g)].map(match => match[1]);
    expect(contents.length).toBeGreaterThan(10);
    for (const content of contents) expect(content.length).toBeLessThanOrEqual(90);
  });

  it('wraps unbroken runs rather than dropping them', () => {
    const lines = wrapText('x'.repeat(200), 82);
    expect(lines.every(line => line.length <= 82)).toBe(true);
    expect(lines.join('')).toBe('x'.repeat(200));
    const cjk = wrapText('装'.repeat(200), 82);
    expect(cjk.every(line => line.length <= 82)).toBe(true);
    expect(cjk.join('')).toBe('装'.repeat(200));
  });

  it('gives two diagrams different defs ids', () => {
    const diagram = buildArmourDiagram(native());
    const a = armourDiagramSvg(diagram, render({ uid: 'a' }));
    const b = armourDiagramSvg(diagram, render({ uid: 'b' }));
    expect(a).toContain('hatch-a');
    expect(b).toContain('hatch-b');
  });

  it('sanitizes a filename', () => {
    expect(armourDiagramFileName('design-normal / r2', 'svg')).toBe('plimsoll-design-normal-r2.svg');
    expect(armourDiagramFileName('', 'png')).toBe('plimsoll-armour-diagram.png');
  });
});

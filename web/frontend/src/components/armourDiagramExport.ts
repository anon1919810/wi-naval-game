import {
  ARMOUR_REGION_ORDER, FRACTION_TOLERANCE, type ArmourBand, type ArmourDiagram, type ArmourLedgerReading,
  type ArmourRegionRole,
} from './armourDiagramModel';
import { profileX, profileY } from './freeboardProfileModel';
import { armourDiagramCopy, bulkheadTypeLabel, deckCoverageLabel, policyLabel, type ArmourDiagramKey } from '../i18n/armourDiagram';
import { formatNumber, toDisplay, unitLabel, type DisplayPreferences } from './units';
import type { SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The one serializer both the interactive diagram and its exports are built from.
 *
 * The component renders the returned markup, and the SVG/PNG downloads write the
 * very same string, so a download can never show a different design from the one
 * on screen and selection can never remove data from a file. The output is
 * self-contained: its namespace, its background, its fonts and every colour are
 * explicit, its text is the reader's own language, its units are stated, and it
 * carries every region, the ledger's per-role masses and policies, the balance,
 * the freeboard context, the known/unknown-placement legend and the reading's
 * identity — all independent of what is selected. Nothing here reads the
 * application stylesheet.
 */

export interface ArmourDiagramRender {
  language: SiteLanguage;
  prefs: DisplayPreferences;
  /** A per-instance id, so two diagrams on one page never share a `defs` id. */
  uid: string;
  /** True for the on-screen diagram: regions become focusable buttons and an image role is not used. */
  interactive: boolean;
  selected: ArmourRegionRole | null;
  /** The run, revision or condition the drawn mass belongs to. */
  contextLabel?: string | null;
  runId?: string | null;
}

const INK = '#1b1f1e';
const MUTED = '#5b6360';
const RULE = '#c8cfcc';
const CHANGED = '#b23b2e';
const UNKNOWN = '#9aa3a0';
const FONT = 'system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif';
const BAND_FILL: Record<string, string> = {
  belt_main: '#3f6f8f', belt_ends: '#5b8aa8', belt_upper: '#7aa6bd', bulkhead: '#8f6f3f', bulge: '#6f8f5b',
};
const SEGMENT_FILL = ['#b9c9d6', '#cdd8e2', '#dfe7ee', '#eef3f7'];

const LEFT = 16;
const TRACK_LEFT = 250;
const TRACK_RIGHT = 930;
const TRACK_WIDTH = TRACK_RIGHT - TRACK_LEFT;
// A conservative character budget for the widest glyph a label can hold at the
// working size, so neither a run UUID nor a Chinese sentence can run off the sheet.
const WRAP_CHARS = 82;

const UNKNOWN_MARK = '—';

function escape(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function round(value: number, places = 3): number {
  const scale = 10 ** places;
  return Math.round(value * scale) / scale;
}

function lengthText(ft: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('length', ft, prefs, 'ft');
  return value === null ? UNKNOWN_MARK : `${formatNumber(round(value))} ${unitLabel('length', prefs.length)}`;
}

function massText(tonnes: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('mass', tonnes, prefs, 't');
  return value === null ? UNKNOWN_MARK : `${formatNumber(round(value))} ${unitLabel('mass', prefs.mass)}`;
}

function angleText(deg: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('angle', deg, prefs, 'deg');
  return value === null ? UNKNOWN_MARK : `${formatNumber(round(value))} ${unitLabel('angle', prefs.angle)}`;
}

/** Thickness is always named in both inches and millimetres; it never takes a hull-length unit. */
function thicknessText(inches: number | null): string {
  if (inches === null) return UNKNOWN_MARK;
  return `${formatNumber(round(inches))} in (${formatNumber(round(inches * 25.4))} mm)`;
}

function fractionText(fraction: number | null): string {
  return fraction === null ? UNKNOWN_MARK : `${formatNumber(round(fraction * 100, 2))}%`;
}

/**
 * Wrap text to a character budget, never dropping a character.
 *
 * Long unbroken runs — a run UUID, or a Chinese clause with no spaces — are
 * hard-split rather than allowed to run past the sheet, so every complete label
 * stays inside the drawing.
 */
export function wrapText(text: string, maxChars: number): string[] {
  const lines: string[] = [];
  let line = '';
  const flush = (): void => { if (line !== '') { lines.push(line); line = ''; } };
  for (const raw of text.split(' ')) {
    if (raw === '') continue;
    let word = raw;
    while (word.length > maxChars) {
      flush();
      lines.push(word.slice(0, maxChars));
      word = word.slice(maxChars);
    }
    if (line === '') line = word;
    else if (line.length + 1 + word.length <= maxChars) line += ` ${word}`;
    else { flush(); line = word; }
  }
  flush();
  return lines.length ? lines : [''];
}

interface TextOptions { size?: number; fill?: string; weight?: string; anchor?: 'start' | 'middle' | 'end' }

class Builder {
  private readonly parts: string[] = [];

  constructor(private readonly uid: string) {}

  text(x: number, y: number, content: string, options: TextOptions = {}): void {
    const { size = 11, fill = INK, weight = 'normal', anchor = 'start' } = options;
    this.parts.push(`<text x="${round(x)}" y="${round(y)}" font-size="${size}" font-weight="${weight}" fill="${fill}"${anchor === 'start' ? '' : ` text-anchor="${anchor}"`}>${escape(content)}</text>`);
  }

  /** Wrapped lines of text; returns the number of lines drawn. */
  wrap(x: number, y: number, content: string, options: TextOptions = {}, maxChars = WRAP_CHARS, lineHeight = 14): number {
    const lines = wrapText(content, maxChars);
    lines.forEach((entry, index) => this.text(x, y + index * lineHeight, entry, { ...options, fill: options.fill ?? MUTED }));
    return lines.length;
  }

  rect(x: number, y: number, width: number, height: number, options: { fill?: string; stroke?: string; dash?: boolean; width?: number } = {}): void {
    const { fill = 'none', stroke, dash = false } = options;
    const strokePart = stroke ? ` stroke="${stroke}" stroke-width="${options.width ?? 1}"` : '';
    const dashPart = dash ? ` stroke-dasharray="5 4"` : '';
    this.parts.push(`<rect x="${round(x)}" y="${round(y)}" width="${round(Math.max(0, width))}" height="${round(height)}" fill="${fill}"${strokePart}${dashPart} />`);
  }

  line(x1: number, y1: number, x2: number, y2: number, options: { stroke?: string; dash?: boolean; width?: number } = {}): void {
    const { stroke = RULE, dash = false, width = 1 } = options;
    this.parts.push(`<line x1="${round(x1)}" y1="${round(y1)}" x2="${round(x2)}" y2="${round(y2)}" stroke="${stroke}" stroke-width="${width}"${dash ? ' stroke-dasharray="5 4"' : ''} />`);
  }

  push(markup: string): void {
    this.parts.push(markup);
  }

  get markup(): string {
    return this.parts.join('');
  }
}

function regionLabel(language: SiteLanguage, role: ArmourRegionRole): string {
  return armourDiagramCopy(language, `armour.region.${role}` as ArmourDiagramKey);
}

function bandFacts(band: ArmourBand, language: SiteLanguage, prefs: DisplayPreferences, bulkheadTypeIndex: number | null): string {
  const w = (key: ArmourDiagramKey): string => armourDiagramCopy(language, key);
  const facts = [
    `${w('armour.fact.length')}: ${lengthText(band.lengthFt, prefs)}`,
    `${w('armour.fact.height')}: ${lengthText(band.heightFt, prefs)}`,
    `${w('armour.fact.thickness')}: ${thicknessText(band.thicknessIn)}`,
  ];
  if (band.role === 'belt_main') facts.push(`${w('armour.fact.inclination')}: ${angleText(band.inclinationDeg, prefs)}`);
  if (band.role === 'bulkhead') {
    facts.push(`${w('armour.bulkhead.beam')}: ${lengthText(band.beamFt, prefs)}`);
    facts.push(`${w('armour.bulkhead.type')}: ${bulkheadTypeLabel(language, bulkheadTypeIndex) ?? UNKNOWN_MARK}`);
  }
  return facts.join('   ·   ');
}

function problemText(language: SiteLanguage, problem: ArmourBand['lengthProblem']): string | null {
  if (!problem) return null;
  return armourDiagramCopy(language, `armour.problem.${problem}` as ArmourDiagramKey);
}

function ledgerLine(reading: ArmourLedgerReading | null, language: SiteLanguage, prefs: DisplayPreferences): string {
  const w = (key: ArmourDiagramKey): string => armourDiagramCopy(language, key);
  if (!reading) return `${w('armour.fact.mode')}: ${policyLabel(language, null)}   ·   ${w('armour.fact.selected')}: ${UNKNOWN_MARK}   ·   ${w('armour.fact.estimate')}: ${UNKNOWN_MARK}`;
  return `${w('armour.fact.mode')}: ${policyLabel(language, reading.mode)}   ·   ${w('armour.fact.selected')}: ${massText(reading.selectedT, prefs)}   ·   ${w('armour.fact.estimate')}: ${massText(reading.estimateT, prefs)}`;
}

/**
 * The complete, standalone SVG for one reading.
 *
 * `interactive` only changes the accessibility shape of the root and the
 * regions; the drawn facts, labels, units, legend and identity are identical in
 * both, so every download carries everything.
 */
export function armourDiagramSvg(diagram: ArmourDiagram, render: ArmourDiagramRender): string {
  const { language, prefs } = render;
  const w = (key: ArmourDiagramKey): string => armourDiagramCopy(language, key);
  const body = new Builder(render.uid);
  const defs = `<defs><pattern id="hatch-${escape(render.uid)}" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#ffffff" /><line x1="0" y1="0" x2="0" y2="8" stroke="${UNKNOWN}" stroke-width="2" /></pattern></defs>`;
  const hatch = `url(#hatch-${escape(render.uid)})`;
  body.push(defs);

  const context = diagram.context;
  const identity = render.contextLabel ?? context.sourceName;
  let y = 22;

  // Header, stacked so a UUID or a long identity never runs off the sheet.
  body.text(LEFT, y, w('armour.kicker'), { size: 10, fill: MUTED });
  y += 22;
  body.text(LEFT, y, w('armour.title'), { size: 19, weight: 'bold' });
  y += 16;
  const headerFacts = [
    `${w('armour.context.hullLength')}: ${lengthText(context.hullLengthFt, prefs)}`,
    `${w('armour.context.beam')}: ${lengthText(context.beamFt, prefs)}`,
    `${w('armour.context.basis')}: ${context.basisConditionId ?? UNKNOWN_MARK}`,
  ];
  if (context.bulkheadTypeIndex !== null) headerFacts.push(`${w('armour.context.bulkheadType')}: ${bulkheadTypeLabel(language, context.bulkheadTypeIndex) ?? UNKNOWN_MARK}`);
  if (identity) headerFacts.push(`${w('armour.mass.context')}: ${identity}`);
  if (render.runId) headerFacts.push(`${w('armour.mass.run')}: ${render.runId}`);
  for (const fact of headerFacts) { y += body.wrap(LEFT, y, fact, { size: 10, fill: MUTED }) * 14; }
  const unitsLine = w('armour.legend.units')
    .replace('{length}', unitLabel('length', prefs.length))
    .replace('{thickness}', `${w('armour.unit.in')} / ${w('armour.unit.mm')}`)
    .replace('{mass}', unitLabel('mass', prefs.mass));
  y += body.wrap(LEFT, y, unitsLine, { size: 10, fill: MUTED }) * 14;
  y += 6;
  if (context.armourWarn) { y += body.wrap(LEFT, y, w('armour.warn'), { size: 10, fill: CHANGED }) * 14; y += 6; }

  // Length-proportion bands.
  body.text(LEFT, y, w('armour.bands.title'), { size: 13, weight: 'bold' });
  y += 18;
  y += body.wrap(LEFT, y, w('armour.bands.note'), { size: 10, fill: MUTED }) * 14;
  y += 6;
  body.line(TRACK_LEFT, y, TRACK_RIGHT, y, { stroke: RULE });
  body.text(TRACK_LEFT, y - 4, '0', { size: 9, fill: MUTED });
  body.text(TRACK_RIGHT, y - 4, w('armour.bands.track'), { size: 9, fill: MUTED, anchor: 'end' });
  y += 10;
  for (const band of diagram.bands) {
    const rowY = y + 11;
    const selected = render.selected === band.role;
    const changed = diagram.comparable && diagram.changed[band.role] === true;
    const groupAttrs = render.interactive
      ? ` role="button" tabindex="0" aria-label="${escape(regionLabel(language, band.role))}" data-armour-region="${band.role}"`
      : ` data-armour-region="${band.role}"`;
    body.push(`<g${groupAttrs}${selected ? ' data-selected="true"' : ''}${changed ? ' data-changed="true"' : ''}>`);
    body.text(TRACK_LEFT - 10, rowY, regionLabel(language, band.role), { size: 12, anchor: 'end', weight: 'bold', fill: changed ? CHANGED : INK });
    body.rect(TRACK_LEFT, y, TRACK_WIDTH, 18, { stroke: RULE });
    if (band.lengthValid && band.lengthFt !== null && context.hullLengthFt !== null && context.hullLengthFt > 0) {
      const width = (band.lengthFt / context.hullLengthFt) * TRACK_WIDTH;
      const drawWidth = band.lengthFt > 0 ? Math.min(TRACK_WIDTH, Math.max(2, width)) : 0;
      body.rect(TRACK_LEFT + (TRACK_WIDTH - drawWidth) / 2, y, drawWidth, 18, { fill: BAND_FILL[band.role] ?? '#607d8b', stroke: selected ? INK : undefined, width: selected ? 2 : 1 });
    } else {
      body.rect(TRACK_LEFT, y, TRACK_WIDTH, 18, { fill: hatch, stroke: selected ? INK : UNKNOWN, dash: !selected, width: selected ? 2 : 1 });
      const message = problemText(language, band.lengthProblem);
      if (message) body.text(TRACK_LEFT + 8, rowY, message, { size: 9, fill: CHANGED });
    }
    // The full numeric facts are always stated under the band, plotted or not.
    y += 34;
    y += body.wrap(LEFT, y, bandFacts(band, language, prefs, context.bulkheadTypeIndex), { size: 10, fill: MUTED }) * 14;
    body.push('</g>');
    y += 12;
  }

  // Freeboard endpoints, read through the one shared geometry the profile uses.
  body.text(LEFT, y, w('armour.freeboard.title'), { size: 13, weight: 'bold' });
  y += 18;
  y += body.wrap(LEFT, y, w('armour.freeboard.note'), { size: 10, fill: MUTED }) * 14;
  y += 4;
  if (diagram.freeboard) {
    const geo = diagram.freeboard;
    const stripHeight = 110;
    const scaleX = TRACK_WIDTH / 1000;
    const scaleY = stripHeight / 180;
    body.push(`<g data-armour-freeboard="true" transform="translate(${round(TRACK_LEFT)},${round(y + 20)}) scale(${round(scaleX, 5)},${round(scaleY, 5)})">`);
    body.line(profileX(geo, 0), profileY(geo, 0), profileX(geo, geo.length), profileY(geo, 0), { stroke: RULE, dash: true });
    const points = geo.xs.map((value, index) => `${round(profileX(geo, value), 2)},${round(profileY(geo, geo.heights[index]), 2)}`).join(' ');
    body.push(`<polyline points="${points}" fill="none" stroke="${INK}" stroke-width="2" />`);
    body.push(`<circle cx="${round(profileX(geo, 0), 2)}" cy="${round(profileY(geo, geo.heights[0]), 2)}" r="3" fill="${INK}" />`);
    body.push('</g>');
    body.text(TRACK_LEFT, y + 20 + stripHeight + 12, w('armour.freeboard.stern'), { size: 10, fill: MUTED });
    body.text(TRACK_RIGHT, y + 20 + stripHeight + 12, w('armour.freeboard.bow'), { size: 10, fill: MUTED, anchor: 'end' });
    y += 20 + stripHeight + 34;
    const endpointFacts = geo.heights.map((height, index) => `${index + 1}: ${lengthText(height, prefs)}`).join('   ·   ');
    y += body.wrap(LEFT, y, endpointFacts, { size: 10, fill: MUTED }) * 14;
  } else {
    y += body.wrap(LEFT, y, w('armour.freeboard.missing'), { size: 10, fill: MUTED }) * 14;
  }
  y += 10;

  // Deck partition, drawn only when every drawn fraction is valid and fits.
  if (diagram.deck) {
    body.text(LEFT, y, w('armour.deck.title'), { size: 13, weight: 'bold' });
    y += 18;
    y += body.wrap(LEFT, y, w('armour.deck.note'), { size: 10, fill: MUTED }) * 14;
    y += 6;
    const deckY = y;
    const selected = render.selected === 'deck';
    const changed = diagram.comparable && diagram.changed.deck === true;
    body.push(`<g${render.interactive ? ` role="button" tabindex="0" aria-label="${escape(regionLabel(language, 'deck'))}"` : ''} data-armour-region="deck"${selected ? ' data-selected="true"' : ''}${changed ? ' data-changed="true"' : ''}>`);
    body.rect(TRACK_LEFT, deckY, TRACK_WIDTH, 22, { stroke: selected ? INK : RULE, width: selected ? 2 : 1 });
    let placedTo = 0;
    let placedAny = false;
    if (!diagram.deck.invalid && !diagram.deck.overlong) {
      for (const segment of diagram.deck.segments) {
        if (segment.start === null || segment.end === null || !segment.valid) break;
        const start = Math.max(0, Math.min(1, segment.start));
        const end = Math.max(start, Math.min(1, segment.end));
        const x = TRACK_LEFT + start * TRACK_WIDTH;
        const width = (end - start) * TRACK_WIDTH;
        body.rect(x, deckY, width, 22, { fill: SEGMENT_FILL[diagram.deck.segments.indexOf(segment) % SEGMENT_FILL.length], stroke: RULE });
        if (width > 60) body.text(x + width / 2, deckY + 15, fractionText(segment.fraction), { size: 9, fill: INK, anchor: 'middle' });
        placedTo = Math.max(placedTo, end);
        placedAny = true;
      }
    }
    if (placedTo < 1 - FRACTION_TOLERANCE) {
      const x = TRACK_LEFT + Math.max(0, placedTo) * TRACK_WIDTH;
      body.rect(x, deckY, TRACK_RIGHT - x, 22, { fill: hatch, stroke: UNKNOWN, dash: true });
      if (!placedAny) body.text(TRACK_LEFT + 8, deckY + 15, UNKNOWN_MARK, { size: 10, fill: MUTED });
    }
    body.push('</g>');
    y = deckY + 40;
    for (const segment of diagram.deck.segments) {
      y += body.wrap(TRACK_LEFT, y, `${w(`armour.segment.${segment.key}` as ArmourDiagramKey)}: ${fractionText(segment.fraction)}`, { size: 10, fill: MUTED }) * 14;
    }
    if (diagram.deck.overlong) { y += body.wrap(TRACK_LEFT, y, w('armour.deck.fractionOverlong'), { size: 10, fill: CHANGED }) * 14; }
    else if (diagram.deck.invalid) { y += body.wrap(TRACK_LEFT, y, w('armour.deck.fractionInvalid'), { size: 10, fill: CHANGED }) * 14; }
    else if (diagram.deck.totalFraction === null) { y += body.wrap(TRACK_LEFT, y, w('armour.deck.fractionIncomplete'), { size: 10, fill: MUTED }) * 14; }
    else if (placedTo < 1 - FRACTION_TOLERANCE) { y += body.wrap(TRACK_LEFT, y, w('armour.deck.unknownRest'), { size: 10, fill: MUTED }) * 14; }
    const coverage = deckCoverageLabel(language, diagram.deck.coverageIndex);
    y += body.wrap(TRACK_LEFT, y, `${w('armour.deck.thickness')}: ${thicknessText(diagram.deck.thicknessIn)}   ·   ${w('armour.deck.forecastle')}: ${thicknessText(diagram.deck.forecastleThicknessIn)}   ·   ${w('armour.deck.quarterdeck')}: ${thicknessText(diagram.deck.quarterdeckThicknessIn)}`, { size: 10, fill: MUTED }) * 14;
    y += body.wrap(TRACK_LEFT, y, `${w('armour.deck.coverage')}: ${coverage ?? UNKNOWN_MARK}`, { size: 10, fill: INK }) * 14;
    y += body.wrap(TRACK_LEFT, y, w('armour.deck.boxes'), { size: 10, fill: MUTED }) * 14;
    y += body.wrap(TRACK_LEFT, y, w('armour.deck.coverageOptions'), { size: 10, fill: MUTED }) * 14;
    for (let index = 0; index < 7; index += 1) {
      const label = deckCoverageLabel(language, index) ?? '';
      const chosen = diagram.deck.coverageIndex === index;
      y += body.wrap(TRACK_LEFT + 12, y, `${chosen ? '◉' : '○'} ${label}`, { size: 10, fill: chosen ? INK : MUTED }) * 14;
    }
    y += 8;
  }

  // Conning towers and the declared bulkhead type.
  body.text(LEFT, y, w('armour.towers.title'), { size: 13, weight: 'bold' });
  y += 18;
  body.push(`<g${render.interactive ? ` role="button" tabindex="0" aria-label="${escape(regionLabel(language, 'conning'))}"` : ''} data-armour-region="conning"${render.selected === 'conning' ? ' data-selected="true"' : ''}${diagram.comparable && diagram.changed.conning ? ' data-changed="true"' : ''}>`);
  y += body.wrap(TRACK_LEFT, y, `${w('armour.tower.forward')}: ${thicknessText(diagram.towers[0]?.thicknessIn ?? null)}`, { size: 11, fill: INK }, WRAP_CHARS, 16) * 16;
  y += body.wrap(TRACK_LEFT, y, `${w('armour.tower.aft')}: ${thicknessText(diagram.towers[1]?.thicknessIn ?? null)}`, { size: 11, fill: INK }, WRAP_CHARS, 16) * 16;
  body.push('</g>');
  y += body.wrap(TRACK_LEFT, y, w('armour.towers.note'), { size: 10, fill: MUTED }) * 14;
  y += 6;

  // Ledger masses for every role, in one place, ordered and never doubled.
  body.text(LEFT, y, w('armour.ledger.title'), { size: 13, weight: 'bold' });
  y += 18;
  y += body.wrap(LEFT, y, w('armour.ledger.note'), { size: 10, fill: MUTED }) * 14;
  for (const role of ARMOUR_REGION_ORDER) {
    const changed = diagram.comparable && diagram.changed[role] === true;
    body.text(LEFT, y, regionLabel(language, role), { size: 10, fill: changed ? CHANGED : INK, weight: 'bold' });
    y += body.wrap(TRACK_LEFT, y, ledgerLine(diagram.ledger[role], language, prefs), { size: 10, fill: MUTED }) * 14 + 8;
  }
  y += 10;

  // Mass context and the unified balance, labelled for what each number is.
  body.text(LEFT, y, w('armour.mass.title'), { size: 13, weight: 'bold' });
  y += 18;
  const contextFacts: string[] = [];
  if (context.beltCover !== null) contextFacts.push(`${w('armour.mass.beltCover')}: ${formatNumber(round(context.beltCover * 100, 2))}%`);
  if (context.maxBeltHeightFt !== null) contextFacts.push(`${w('armour.mass.maxBeltHeight')}: ${lengthText(context.maxBeltHeightFt, prefs)}`);
  if (contextFacts.length) y += body.wrap(TRACK_LEFT, y, contextFacts.join('   ·   '), { size: 10, fill: MUTED }) * 14;
  if (diagram.balance) {
    const b = diagram.balance;
    const balanceLine = [
      `${w('armour.mass.selected')}: ${massText(b.selected_mass_t ?? null, prefs)}`,
      `${w('armour.mass.estimate')}: ${massText(b.estimated_mass_t ?? null, prefs)}`,
      `${w('armour.mass.target')}: ${massText(b.target_displacement_t ?? null, prefs)}`,
      `${w('armour.mass.difference')}: ${massText(b.difference_t ?? null, prefs)}`,
    ].join('   ·   ');
    y += body.wrap(TRACK_LEFT, y, balanceLine, { size: 10, fill: MUTED }) * 14;
  }
  y += 14;

  // Legend.
  body.text(LEFT, y, w('armour.legend.title'), { size: 12, weight: 'bold' });
  y += 16;
  body.rect(TRACK_LEFT, y, 22, 10, { fill: BAND_FILL.belt_main });
  body.text(TRACK_LEFT + 30, y + 9, w('armour.legend.known'), { size: 10, fill: MUTED });
  y += 16;
  body.rect(TRACK_LEFT, y, 22, 10, { fill: hatch, stroke: UNKNOWN, dash: true });
  body.text(TRACK_LEFT + 30, y + 9, w('armour.legend.unknown'), { size: 10, fill: MUTED });
  y += 16;
  body.line(TRACK_LEFT, y + 5, TRACK_LEFT + 22, y + 5, { stroke: CHANGED, width: 3 });
  body.text(TRACK_LEFT + 30, y + 9, w('armour.legend.changed'), { size: 10, fill: MUTED });
  y += 18;

  const height = Math.max(120, y);
  const rootRole = render.interactive ? 'group' : 'img';
  const titleId = `armour-title-${escape(render.uid)}`;
  const descId = `armour-desc-${escape(render.uid)}`;
  const root = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 ${round(height)}" width="960" height="${round(height)}" role="${rootRole}" aria-labelledby="${titleId} ${descId}" font-family="${FONT}">`,
    `<title id="${titleId}">${escape(w('armour.title'))}</title>`,
    `<desc id="${descId}">${escape(w('armour.intro'))}</desc>`,
    `<rect x="0" y="0" width="960" height="${round(height)}" fill="#ffffff" />`,
    body.markup,
    '</svg>',
  ];
  return root.join('');
}

/** A filename that drops any character a file system could disagree about. */
export function armourDiagramFileName(label: string, extension: string): string {
  const slug = (label || 'armour-diagram').normalize('NFKD').replace(/[^\w.-]+/g, '-').replace(/-+/g, '-').replace(/^[-.]+|[-.]+$/g, '').slice(0, 80);
  return `plimsoll-${slug || 'armour-diagram'}.${extension}`;
}

function triggerDownload(href: string, filename: string): void {
  const link = document.createElement('a');
  link.href = href;
  link.download = filename;
  link.click();
}

/** A real SVG download, from an object URL that is always released. */
export function downloadArmourDiagramSvg(svg: string, filename: string): void {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
  try {
    triggerDownload(url, filename);
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
}

/**
 * A PNG of the very same SVG, rasterized by the browser.
 *
 * It rejects when the browser cannot decode or draw the picture, so the caller
 * can say so in words instead of silently doing nothing.
 */
export function downloadArmourDiagramPng(svg: string, filename: string, width = 1600): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }));
    const image = new Image();
    const fail = (): void => { URL.revokeObjectURL(url); reject(new Error('png')); };
    image.onload = () => {
      try {
        const canvas = document.createElement('canvas');
        const ratio = image.height && image.width ? image.height / image.width : 0.7;
        canvas.width = width;
        canvas.height = Math.round(width * ratio) || 1;
        const context = canvas.getContext('2d');
        if (!context) { fail(); return; }
        context.fillStyle = '#ffffff';
        context.fillRect(0, 0, canvas.width, canvas.height);
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        triggerDownload(canvas.toDataURL('image/png'), filename);
        URL.revokeObjectURL(url);
        resolve();
      } catch {
        fail();
      }
    };
    image.onerror = fail;
    image.src = url;
  });
}

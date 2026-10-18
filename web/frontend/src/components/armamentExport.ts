import {
  ARMAMENT_LEDGER_ROLES, integralCount, type Armament, type ArmamentBank, type ArmamentGroup,
} from './armamentModel';
import { armourDiagramFileName, downloadArmourDiagramPng, downloadArmourDiagramSvg } from './armourDiagramExport';
import {
  ledgerPolicyLabel, vesselLabel, vesselOverviewCopy, type VesselLabelTable, type VesselOverviewKey,
} from '../i18n/vesselOverview';
import { formatNumber, toDisplay, unitLabel, type DisplayPreferences } from './units';
import type { SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The one serializer the interactive armament composition and its exports share.
 *
 * The component renders the returned markup and the SVG/PNG downloads write the
 * very same string, so a download can never show a different armament from the
 * one on screen and selection can never remove data from a file. The output is
 * self-contained: its namespace, background, fonts and every colour are explicit,
 * its text is the reader's own language, and every reader meets the same five
 * batteries, their two groups, their source facts, the global ledger roles and
 * the source-mass legend — all independent of what is selected.
 *
 * Text is wrapped to the pixel width of its own column, not to a character count,
 * because a line of wide CJK glyphs is twice as wide as the same count of Latin
 * letters. A single unbroken run — a CJK word, a long identifier — is split
 * across lines rather than clipped, and no source character is ever dropped.
 *
 * Mass follows the reader's chosen mass unit. A source estimate stored in long
 * tons is converted once for display and labelled a source estimate; the ledger
 * roles are stored in tonnes and shown in the same chosen unit, with their
 * declared policy beside them. Nothing here recomputes a ship number or
 * partitions a global ledger mass.
 */

export interface ArmamentRender {
  language: SiteLanguage;
  prefs: DisplayPreferences;
  /** A per-instance id, so two compositions on one page never share a `defs` id. */
  uid: string;
  /** True for the on-screen composition: batteries become focusable buttons. */
  interactive: boolean;
  /** The run, revision or condition the composition belongs to. */
  contextLabel?: string | null;
  runId?: string | null;
}

const INK = '#1b1f1e';
const MUTED = '#5b6360';
const RULE = '#c8cfcc';
const CHANGED = '#b23b2e';
const UNKNOWN = '#9aa3a0';
const ACCENT = '#3f6f8f';
const FONT = 'system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif';

const WIDTH = 960;
const LEFT = 16;
const COL = 210;
const RIGHT = 944;
// The two independent columns of a ledger row and of a labelled fact row.
const ROLE_W = COL - 8 - LEFT;
const VALUE_W = RIGHT - COL;
const FACT_W = RIGHT - (COL + 90);
const LINE = 14;
// Never draw one glyph per source mount: the strip is a bounded schematic.
const GLYPH_CAP = 8;
const GLYPH = 14;
const UNKNOWN_MARK = '—';

function escape(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function round(value: number, places = 3): number {
  const scale = 10 ** places;
  return Math.round(value * scale) / scale;
}

/** The advance width of one code point at a font size, in the drawing's units. */
function charWidth(code: number, size: number): number {
  if (code === 32) return size * 0.3;
  // Hangul, CJK, fullwidth forms and their punctuation are one em wide; the rest
  // is a narrow proportional average.
  if ((code >= 0x1100 && code <= 0x115f) || (code >= 0x2e80 && code <= 0xa4cf)
    || (code >= 0xac00 && code <= 0xd7a3) || (code >= 0xf900 && code <= 0xfaff)
    || (code >= 0xfe30 && code <= 0xfe6f) || (code >= 0xff00 && code <= 0xff60)
    || (code >= 0xffe0 && code <= 0xffe6)) return size;
  return size * 0.54;
}

function textWidth(text: string, size: number): number {
  let width = 0;
  for (const char of text) width += charWidth(char.codePointAt(0) ?? 0, size);
  return width;
}

/**
 * Wrap a string to a pixel width at a font size, never dropping a character.
 *
 * A line breaks at its last space when it has one — a Latin word stays whole — and
 * between characters when it has none, which is what a wide CJK run needs. A
 * single run wider than the whole column is split the same way rather than
 * overflowing the drawing.
 */
export function wrapWidth(text: string, widthPx: number, size: number): string[] {
  const lines: string[] = [];
  let line = '';
  // The index just past the last space in `line`, or -1 when there is none.
  let spaceAt = -1;
  for (const char of text) {
    if (line !== '' && textWidth(line + char, size) > widthPx) {
      if (spaceAt > 0) {
        lines.push(line.slice(0, spaceAt).replace(/ +$/, ''));
        line = line.slice(spaceAt);
      } else {
        lines.push(line);
        line = '';
      }
      spaceAt = -1;
    }
    line += char;
    if (char === ' ') spaceAt = line.length;
  }
  lines.push(line);
  return lines;
}

interface TextOptions { size?: number; fill?: string; weight?: string; anchor?: 'start' | 'middle' | 'end' }

/** A minimal, local SVG builder; the armour serializer's behaviour is untouched. */
class Builder {
  private readonly parts: string[] = [];

  text(x: number, y: number, content: string, options: TextOptions = {}): void {
    const { size = 11, fill = INK, weight = 'normal', anchor = 'start' } = options;
    this.parts.push(`<text x="${round(x)}" y="${round(y)}" font-size="${size}" font-weight="${weight}" fill="${fill}"${anchor === 'start' ? '' : ` text-anchor="${anchor}"`}>${escape(content)}</text>`);
  }

  /** Wrap to a pixel width and draw the lines; returns how many were drawn. */
  wrap(x: number, y: number, content: string, options: TextOptions = {}, widthPx = RIGHT - x, lineHeight = LINE): number {
    const size = options.size ?? 11;
    const lines = wrapWidth(content, widthPx, size);
    lines.forEach((entry, index) => this.text(x, y + index * lineHeight, entry, { ...options, fill: options.fill ?? MUTED }));
    return lines.length;
  }

  rect(x: number, y: number, width: number, height: number, options: { fill?: string; stroke?: string; dash?: boolean; width?: number; rx?: number } = {}): void {
    const { fill = 'none', stroke, dash = false, rx } = options;
    const strokePart = stroke ? ` stroke="${stroke}" stroke-width="${options.width ?? 1}"` : '';
    const dashPart = dash ? ' stroke-dasharray="5 4"' : '';
    const roundPart = rx ? ` rx="${rx}"` : '';
    this.parts.push(`<rect x="${round(x)}" y="${round(y)}" width="${round(Math.max(0, width))}" height="${round(height)}" fill="${fill}"${strokePart}${dashPart}${roundPart} />`);
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

/* -------------------------------------------------------------- text helpers */

/** A source mass stored in long tons, converted once for display. */
function sourceMassText(lt: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('mass', lt, prefs, 'long_ton');
  return value === null ? UNKNOWN_MARK : `${formatNumber(round(value))} ${unitLabel('mass', prefs.mass)}`;
}

/** A ledger or balance mass stored in tonnes, shown in the reader's chosen unit. */
function ledgerMassText(t: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('mass', t, prefs, 't');
  return value === null ? UNKNOWN_MARK : `${formatNumber(round(value))} ${unitLabel('mass', prefs.mass)}`;
}

/** A normalized calibre or armour thickness, always named in both inches and millimetres. */
function thicknessText(inches: number | null): string {
  return inches === null ? UNKNOWN_MARK : `${formatNumber(round(inches))} in (${formatNumber(round(inches * 25.4))} mm)`;
}

function poundsText(lb: number | null): string {
  return lb === null ? UNKNOWN_MARK : `${formatNumber(round(lb))} lb`;
}

/** A count that is only ever drawn as a whole arrangement when it is one. */
function countText(value: number | null, w: (key: VesselOverviewKey, params?: Record<string, string | number>) => string): string {
  if (value === null) return UNKNOWN_MARK;
  if (Number.isInteger(value) && value >= 0) return formatNumber(value);
  return w('armament.count.invalid', { value: formatNumber(round(value)) });
}

function label(language: SiteLanguage, table: VesselLabelTable, index: number | null): string {
  return vesselLabel(language, table, index) ?? UNKNOWN_MARK;
}

/** True when a group declares anything at all. */
function groupDeclared(group: ArmamentGroup): boolean {
  return group.selector !== null || group.layout !== null || group.perMount !== null || group.mounts !== null
    || group.elevated !== null || group.deck !== null || group.depressed !== null;
}

/* ---------------------------------------------------------------- serializer */

/** One group's glyph strip and its declared facts, returning the next y. */
function drawGroup(body: Builder, group: ArmamentGroup, render: ArmamentRender, y: number): number {
  const w = (key: VesselOverviewKey, params?: Record<string, string | number>) => vesselOverviewCopy(render.language, key, params);
  const groupName = w(`armament.group.${group.key}` as VesselOverviewKey);
  const declared = groupDeclared(group);
  body.text(COL, y, groupName, { size: 11, weight: 'bold', fill: declared ? INK : MUTED });
  if (!declared) {
    body.text(COL + 80, y, w('armament.group.none'), { size: 10, fill: MUTED });
    return y + 20;
  }
  const stripY = y + 6;
  const drawable = integralCount(group.mounts);
  if (drawable !== null) {
    const shown = Math.min(drawable, GLYPH_CAP);
    for (let index = 0; index < shown; index += 1) {
      body.rect(COL + index * GLYPH, stripY, GLYPH - 3, 12, { fill: ACCENT, stroke: INK, rx: 2 });
    }
    if (drawable > GLYPH_CAP) body.text(COL + shown * GLYPH + 4, stripY + 11, `+${drawable - GLYPH_CAP}`, { size: 9, fill: MUTED });
    else if (drawable === 0) body.text(COL, stripY + 11, countText(group.mounts, w), { size: 10, fill: MUTED });
  } else {
    body.rect(COL, stripY, GLYPH, 12, { fill: 'none', stroke: UNKNOWN, dash: true, rx: 2 });
    body.text(COL + GLYPH + 6, stripY + 11, countText(group.mounts, w), { size: 10, fill: CHANGED });
  }
  const facts: string[] = [
    `${w('armament.fact.groupMounts')}: ${countText(group.mounts, w)}`,
    `${w('armament.fact.selector')}: ${label(render.language, 'selector', group.selector)}`,
    `${w('armament.fact.layout')}: ${label(render.language, 'layout', group.layout)}`,
    `${w('armament.fact.perMount')}: ${countText(group.perMount, w)}`,
    `${w('armament.fact.elevated')} / ${w('armament.fact.deck')} / ${w('armament.fact.depressed')}: ${countText(group.elevated, w)} / ${countText(group.deck, w)} / ${countText(group.depressed, w)}`,
  ];
  let cursor = stripY + 22;
  for (const fact of facts) cursor += body.wrap(COL + 90, cursor, fact, { size: 10, fill: MUTED }, FACT_W) * LINE;
  return cursor + 6;
}

function drawBank(body: Builder, bank: ArmamentBank, render: ArmamentRender, y: number): number {
  const w = (key: VesselOverviewKey, params?: Record<string, string | number>) => vesselOverviewCopy(render.language, key, params);
  const changed = bank.changed;
  const attrs = render.interactive
    ? ` role="button" tabindex="0" aria-label="${escape(vesselOverviewCopy(render.language, 'armament.bank.label', { bank: bank.bank }))}" data-armament-bank="${bank.bank}"`
    : ` data-armament-bank="${bank.bank}"`;
  body.push(`<g${attrs}${changed ? ' data-changed="true"' : ''}>`);
  body.rect(LEFT, y - 14, RIGHT - LEFT, 26, { fill: '#f4f6f5', stroke: changed ? CHANGED : RULE, width: changed ? 2 : 1, rx: 3 });
  body.text(LEFT + 10, y + 4, w('armament.bank.label', { bank: bank.bank }), { size: 13, weight: 'bold', fill: changed ? CHANGED : INK });
  const stateText = bank.state === 'missing' ? w('armament.bank.missing')
    : bank.state === 'ambiguous' ? w('armament.bank.ambiguous')
      : bank.state === 'zero' ? w('armament.bank.zero') : '';
  if (stateText) body.wrap(LEFT + 150, y + 4, stateText, { size: 10, fill: MUTED }, RIGHT - (LEFT + 150) - 10);
  y += 26;
  if (bank.state === 'declared' || bank.state === 'zero') {
    const summary = [
      `${w('armament.fact.barrels')}: ${countText(bank.barrels, w)}`,
      `${w('armament.fact.mounts')}: ${countText(bank.mounts, w)}`,
      `${w('armament.fact.calibre')}: ${thicknessText(bank.calibreIn)}`,
      `${w('armament.fact.gunType')}: ${label(render.language, 'gunType', bank.gunType)}`,
      `${w('armament.fact.mountType')}: ${label(render.language, 'mountType', bank.mountType)}`,
      `${w('armament.fact.year')}: ${countText(bank.year, w)}`,
      `${w('armament.fact.calLength')}: ${bank.calLength === null ? UNKNOWN_MARK : w('armament.fact.calibreLength', { value: formatNumber(round(bank.calLength)) })}`,
      `${w('armament.fact.magazine')}: ${countText(bank.magazine, w)}`,
    ].join('   ·   ');
    y += body.wrap(COL, y, summary, { size: 10, fill: MUTED }, VALUE_W) * LINE + 4;
    for (const group of bank.groups) y = drawGroup(body, group, render, y);
    const armour = [
      `${w('armament.fact.face')}: ${thicknessText(bank.armFaceIn)}`,
      `${w('armament.fact.side')}: ${thicknessText(bank.armBackIn)}`,
      `${w('armament.fact.barbette')}: ${thicknessText(bank.armBottomIn)}`,
    ].join('   ·   ');
    y += body.wrap(COL, y, armour, { size: 10, fill: MUTED }, VALUE_W) * LINE;
    const shells = [
      `${w('armament.fact.shellDeclared')}: ${poundsText(bank.shellWeightDeclaredLb)}`,
      `${w('armament.fact.shellEffective')}: ${poundsText(bank.shellWeightLb)}`,
      `${w('armament.fact.shellRecovered')}: ${poundsText(bank.autoShellWeightLb)}`,
      `${w('armament.fact.broadside')}: ${poundsText(bank.broadsideWeightLb)}`,
    ].join('   ·   ');
    y += body.wrap(COL, y, shells, { size: 10, fill: MUTED }, VALUE_W) * LINE;
    const masses = [
      `${w('armament.fact.gunWeight')}: ${sourceMassText(bank.gunWeightLt, render.prefs)}`,
      `${w('armament.fact.mountWeight')}: ${sourceMassText(bank.mountWeightLt, render.prefs)}`,
      `${w('armament.fact.magazineWeight')}: ${sourceMassText(bank.magazineWeightLt, render.prefs)}`,
      `${w('armament.fact.armWeight')}: ${sourceMassText(bank.armWeightLt, render.prefs)}`,
      `${w('armament.fact.totalWeight')}: ${sourceMassText(bank.totalWeightLt, render.prefs)}`,
    ].join('   ·   ');
    y += body.wrap(COL, y, masses, { size: 10, fill: MUTED }, VALUE_W) * LINE;
    const flagNotes: string[] = [];
    if (bank.superSuper === true) flagNotes.push(w('armament.fact.flagElevation'));
    if (bank.subSub === true) flagNotes.push(w('armament.fact.flagDepression'));
    if (flagNotes.length) y += body.wrap(COL, y, flagNotes.join('   ·   '), { size: 10, fill: MUTED }, VALUE_W) * LINE;
  }
  body.push('</g>');
  return y + 10;
}

/**
 * The complete, standalone SVG for one armament reading.
 *
 * `interactive` only changes the accessibility shape of the root and the
 * batteries; every fact, unit, label, legend and download is identical in both.
 */
export function armamentSvg(armament: Armament, render: ArmamentRender): string {
  const { language, prefs } = render;
  const w = (key: VesselOverviewKey, params?: Record<string, string | number>) => vesselOverviewCopy(language, key, params);
  const body = new Builder();
  body.push(`<defs><pattern id="hatch-${escape(render.uid)}" width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="8" height="8" fill="#ffffff" /><line x1="0" y1="0" x2="0" y2="8" stroke="${UNKNOWN}" stroke-width="2" /></pattern></defs>`);

  let y = 22;
  body.text(LEFT, y, w('armament.kicker'), { size: 10, fill: MUTED });
  // Four pixels more than the bare row step: the 19px title's ascent otherwise
  // reaches back into the 10px kicker's descender.
  y += 26;
  body.text(LEFT, y, w('armament.title'), { size: 19, weight: 'bold' });
  y += 18;
  if (render.contextLabel) y += body.wrap(LEFT, y, render.contextLabel, { size: 10, fill: MUTED }) * LINE;
  if (render.runId) y += body.wrap(LEFT, y, render.runId, { size: 10, fill: MUTED }) * LINE;
  y += body.wrap(LEFT, y, w('armament.intro'), { size: 10, fill: MUTED }) * LINE + 4;
  y += body.wrap(LEFT, y, w('armament.banks.note'), { size: 10, fill: MUTED }) * LINE + 6;

  for (const bank of armament.banks) y = drawBank(body, bank, render, y);

  // The four global ledger roles, each with its own policy and both masses. The
  // role name and its values are two independent columns: they wrap separately
  // and the row grows to the taller of the two, so they never overlap.
  body.text(LEFT, y, w('armament.ledger.title'), { size: 13, weight: 'bold' });
  y += 18;
  y += body.wrap(LEFT, y, w('armament.ledger.note'), { size: 10, fill: MUTED }) * LINE + 4;
  const ledgerLabels: Record<string, VesselOverviewKey> = {
    guns: 'armament.ledger.role.guns', mounts: 'armament.ledger.role.mounts',
    ammunition: 'armament.ledger.role.ammunition', gun_armour: 'armament.ledger.role.gun_armour',
  };
  for (const role of ARMAMENT_LEDGER_ROLES) {
    const row = armament.ledger[role];
    const roleText = w(ledgerLabels[role]);
    const valueText = w('armament.ledger.mass', {
      selected: ledgerMassText(row.selectedT, prefs),
      estimate: ledgerMassText(row.estimateT, prefs),
      policy: ledgerPolicyLabel(language, row.mode),
    });
    const roleLines = wrapWidth(roleText, ROLE_W, 10);
    const valueLines = wrapWidth(valueText, VALUE_W, 10);
    roleLines.forEach((line, index) => body.text(LEFT, y + index * LINE, line, { size: 10, weight: 'bold', fill: row.changed ? CHANGED : INK }));
    valueLines.forEach((line, index) => body.text(COL, y + index * LINE, line, { size: 10, fill: MUTED }));
    y += Math.max(roleLines.length, valueLines.length) * LINE + 6;
  }
  y += 6;

  // The unified balance, then the source-mass notes.
  if (armament.balance) {
    const balance = armament.balance;
    const line = [
      `${w('vessel.fact.balanceSelected')}: ${ledgerMassText(balance.selected_mass_t ?? null, prefs)}`,
      `${w('vessel.fact.balanceEstimate')}: ${ledgerMassText(balance.estimated_mass_t ?? null, prefs)}`,
      `${w('vessel.fact.balanceTarget')}: ${ledgerMassText(balance.target_displacement_t ?? null, prefs)}`,
      `${w('vessel.fact.balanceDifference')}: ${ledgerMassText(balance.difference_t ?? null, prefs)}`,
    ].join('   ·   ');
    y += body.wrap(LEFT, y, line, { size: 10, fill: MUTED }) * LINE;
  }
  y += body.wrap(LEFT, y, w('armament.fact.estimateNote'), { size: 10, fill: MUTED }) * LINE;
  y += body.wrap(LEFT, y, w('armament.fact.weightUnits'), { size: 10, fill: MUTED }) * LINE + 6;

  // Legend.
  body.text(LEFT, y, w('armament.legend.title'), { size: 12, weight: 'bold' });
  y += 16;
  body.rect(COL, y, 22, 10, { fill: ACCENT, stroke: INK, rx: 2 });
  body.text(COL + 30, y + 9, w('armament.legend.battery'), { size: 10, fill: MUTED });
  y += 16;
  body.rect(COL, y, 22, 10, { fill: 'none', stroke: UNKNOWN, dash: true, rx: 2 });
  body.text(COL + 30, y + 9, w('armament.legend.unknown'), { size: 10, fill: MUTED });
  y += 16;
  body.line(COL, y + 5, COL + 22, y + 5, { stroke: CHANGED, width: 3 });
  body.text(COL + 30, y + 9, w('armament.legend.changed'), { size: 10, fill: MUTED });
  // The marker rows are two short columns; the note below runs the full width, so
  // it takes its own band rather than the next 16px row baseline, which would put
  // it one line step under the changed label and collide with its descender.
  y += 30;
  y += body.wrap(LEFT, y, w('armament.legend.group'), { size: 10, fill: MUTED }) * LINE;
  y += body.wrap(LEFT, y, w('armament.legend.units'), { size: 10, fill: MUTED }) * LINE;
  y += 10;

  const height = Math.max(160, y);
  const rootRole = render.interactive ? 'group' : 'img';
  const titleId = `armament-title-${escape(render.uid)}`;
  const descId = `armament-desc-${escape(render.uid)}`;
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${round(height)}" width="${WIDTH}" height="${round(height)}" role="${rootRole}" aria-labelledby="${titleId} ${descId}" font-family="${FONT}">`,
    `<title id="${titleId}">${escape(w('armament.title'))}</title>`,
    `<desc id="${descId}">${escape(w('armament.intro'))}</desc>`,
    `<rect x="0" y="0" width="${WIDTH}" height="${round(height)}" fill="#ffffff" />`,
    body.markup,
    '</svg>',
  ].join('');
}

/** A filename, from the one existing rule the armour downloads already use. */
export function armamentFileName(label: string, extension: string): string {
  return armourDiagramFileName(label, extension);
}

export { downloadArmourDiagramPng as downloadArmamentPng, downloadArmourDiagramSvg as downloadArmamentSvg };

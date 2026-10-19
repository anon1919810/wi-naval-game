import {
  FREEBOARD_ENDPOINTS, profileX, profileY, type FreeboardGeometry,
} from './freeboardProfileModel';
import { wrapText } from './armourDiagramExport';
import { hullFreeboardCopy, type HullFreeboardKey } from '../i18n/hullFreeboard';
import { formatNumber, toDisplay, unitLabel, type DisplayPreferences } from './units';
import type { FreeboardGeometryProblem, HullFreeboard } from './hullFreeboardModel';
import type { SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * The one serializer behind the on-screen freeboard profile and both exports.
 *
 * The component renders the returned markup and the SVG/PNG downloads write the
 * very same string, so a download can never show a different design from the one
 * on screen and selection can never remove data from a file. The output is
 * self-contained: its namespace, white background, fonts and colours are
 * explicit, its labels follow the reader's language, and its heights follow the
 * reader's chosen length unit.
 *
 * Every call writes all eight endpoints and all four declared fractions,
 * whatever happens to be selected. When the saved station inputs cannot produce
 * an outline, the reader still receives the endpoint list and the named reason;
 * no missing bow angle or stern extension is turned into a zero.
 */

export interface FreeboardProfileRender {
  language: SiteLanguage;
  prefs: DisplayPreferences;
  /** A per-instance id, so two profiles on one page never share a `defs` id. */
  uid: string;
  /** True for the screen: endpoint points become focusable buttons. */
  interactive: boolean;
  contextLabel?: string | null;
  runId?: string | null;
}

const INK = '#1b1f1e';
const MUTED = '#5b6360';
const RULE = '#c8cfcc';
const CHANGED = '#b23b2e';
const WATER = '#3f6f8f';
const FONT = 'system-ui, Segoe UI, Roboto, Helvetica, Arial, sans-serif';
const WIDTH = 960;
const LEFT = 16;
const RIGHT = WIDTH - 16;
// Conservative for CJK as well: 80 characters at size 10 stay inside 928 px.
const WRAP_CHARS = 80;
const LINE = 14;

// The legacy profile maps its drawing into x 30..970 and y 40..150. The new
// serializer places that whole coordinate system into one explicit chart band,
// so the arithmetic stays shared while nothing can reach the header above it.
const LEGACY_X0 = 30;
const LEGACY_X1 = 970;
const LEGACY_Y0 = 40;
const LEGACY_Y1 = 150;
const PLOT_TOP_GAP = 14;
const PLOT_HEIGHT = 132;

function escape(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function round(value: number, places = 2): number {
  const scale = 10 ** places;
  return Math.round(value * scale) / scale;
}

function lengthText(ft: number | null, prefs: DisplayPreferences): string {
  const value = toDisplay('length', ft, prefs, 'ft');
  return value === null ? '—' : `${formatNumber(round(value))} ${unitLabel('length', prefs.length)}`;
}

function fractionText(value: number | null): string {
  return value === null ? '—' : `${formatNumber(round(value * 100, 2))}%`;
}

function problemText(language: SiteLanguage, problem: FreeboardGeometryProblem | null): string | null {
  if (!problem) return null;
  return hullFreeboardCopy(language, `freeboard.problem.${problem}` as HullFreeboardKey);
}

interface TextOptions {
  size?: number;
  fill?: string;
  weight?: string;
  anchor?: 'start' | 'middle' | 'end';
}

function text(x: number, y: number, content: string, options: TextOptions = {}): string {
  const { size = 11, fill = INK, weight = 'normal', anchor = 'start' } = options;
  return `<text x="${round(x)}" y="${round(y)}" font-size="${size}" font-weight="${weight}" fill="${fill}"${anchor === 'start' ? '' : ` text-anchor="${anchor}"`}>${escape(content)}</text>`;
}

/** Append wrapped lines to `parts`; returns the number drawn, never dropping a character. */
function wrap(parts: string[], x: number, y: number, content: string, options: TextOptions = {},
  maxChars = WRAP_CHARS, lineHeight = LINE): number {
  const lines = wrapText(content, maxChars);
  lines.forEach((entry, index) => {
    parts.push(text(x, y + index * lineHeight, entry, { ...options, fill: options.fill ?? MUTED }));
  });
  return lines.length;
}

function line(x1: number, y1: number, x2: number, y2: number,
  options: { stroke?: string; dash?: boolean; width?: number } = {}): string {
  const { stroke = RULE, dash = false, width = 1 } = options;
  return `<line x1="${round(x1)}" y1="${round(y1)}" x2="${round(x2)}" y2="${round(y2)}" stroke="${stroke}" stroke-width="${width}"${dash ? ' stroke-dasharray="7 5"' : ''} />`;
}

function pointGroup(
  item: HullFreeboard['freeboard']['endpoints'][number],
  content: string,
  language: SiteLanguage,
  prefs: DisplayPreferences,
  interactive: boolean,
): string {
  const label = hullFreeboardCopy(language, item.label);
  const attrs = interactive
    ? ` role="button" tabindex="0" aria-label="${escape(`${label}: ${lengthText(item.value, prefs)}`)}"`
    : '';
  return `<g data-freeboard-point="${item.key}"${item.changed ? ' data-changed="true"' : ''}${attrs}><title>${escape(label)}</title>${content}</g>`;
}

/**
 * Draw the declared outline in one explicit chart band below the complete,
 * wrapped header. `profileX`/`profileY` remain the only coordinate arithmetic;
 * the whole legacy box is translated and scaled into the band, while the
 * waterline and its labels are placed back in outer viewport coordinates.
 */
function chart(reading: HullFreeboard, language: SiteLanguage, prefs: DisplayPreferences,
  interactive: boolean, top: number): { markup: string; bottom: number } {
  const geometry: FreeboardGeometry = reading.freeboard.geometry as FreeboardGeometry;
  const parts: string[] = [];
  parts.push(text(LEFT, top, hullFreeboardCopy(language, 'freeboard.geometry.title'), { size: 13, weight: 'bold' }));
  const plotTop = top + PLOT_TOP_GAP;
  const width = RIGHT - LEFT;
  const scaleX = width / (LEGACY_X1 - LEGACY_X0);
  const scaleY = PLOT_HEIGHT / (LEGACY_Y1 - LEGACY_Y0);
  const translateX = LEFT - LEGACY_X0 * scaleX;
  const translateY = plotTop - LEGACY_Y0 * scaleY;
  const projectX = (value: number): number => translateX + profileX(geometry, value) * scaleX;
  const projectY = (value: number): number => translateY + profileY(geometry, value) * scaleY;

  const waterY = projectY(0);
  parts.push(line(projectX(0), waterY, projectX(geometry.length), waterY, {
    stroke: WATER, dash: true, width: 1,
  }));
  parts.push(text(projectX(0), waterY + 16, '0', { size: 9, fill: MUTED }));
  parts.push(text(projectX(geometry.length), waterY + 16, lengthText(geometry.length, prefs), {
    size: 9, fill: MUTED, anchor: 'end',
  }));

  parts.push(`<g transform="translate(${round(translateX, 4)},${round(translateY, 4)}) scale(${round(scaleX, 5)},${round(scaleY, 5)})">`);
  const points = geometry.xs.map((value, index) => `${round(profileX(geometry, value), 2)},${round(profileY(geometry, geometry.heights[index]), 2)}`).join(' ');
  parts.push(`<polyline points="${points}" fill="none" stroke="${INK}" stroke-width="2.5" />`);
  reading.freeboard.endpoints.forEach((item, index) => {
    const cx = profileX(geometry, geometry.xs[index]);
    const cy = profileY(geometry, geometry.heights[index]);
    const marker = item.changed ? CHANGED : INK;
    const circle = `<circle cx="${round(cx, 2)}" cy="${round(cy, 2)}" r="${item.changed ? 5 : 4}" fill="${marker}" stroke="#ffffff" stroke-width="1.5" />`;
    parts.push(pointGroup(item, circle, language, prefs, interactive));
  });
  parts.push('</g>');

  return { markup: parts.join(''), bottom: plotTop + PLOT_HEIGHT + 28 };
}

/**
 * The complete, standalone SVG for one reading.
 *
 * `interactive` changes only the accessibility shape of the root and endpoint
 * points. Labels, values, fractions, identity and every endpoint are identical
 * in both, so every download carries the whole reading.
 */
export function freeboardProfileSvg(reading: HullFreeboard, render: FreeboardProfileRender): string {
  const { language, prefs } = render;
  const w = (key: HullFreeboardKey): string => hullFreeboardCopy(language, key);
  const rendered: string[] = [];
  const titleId = `freeboard-title-${escape(render.uid)}`;
  const descId = `freeboard-desc-${escape(render.uid)}`;

  rendered.push(text(LEFT, 26, w('freeboard.kicker'), { size: 10, fill: MUTED }));
  rendered.push(text(LEFT, 50, w('freeboard.title'), { size: 19, weight: 'bold' }));
  let y = 70;
  const introLines = wrap(rendered, LEFT, y, w('freeboard.intro'), { size: 10, fill: MUTED });
  y += introLines * LINE + 4;

  if (render.contextLabel) {
    const lines = wrap(rendered, LEFT, y, `${w('freeboard.context')}: ${render.contextLabel}`, { size: 10, fill: MUTED });
    y += lines * LINE + 2;
  }
  if (reading.basisConditionId) {
    const lines = wrap(rendered, LEFT, y, `${w('freeboard.basis')}: ${reading.basisConditionId}`, { size: 10, fill: MUTED });
    y += lines * LINE + 2;
  }
  if (render.runId) {
    const lines = wrap(rendered, LEFT, y, `${w('freeboard.run')}: ${render.runId}`, { size: 10, fill: MUTED });
    y += lines * LINE + 2;
  }

  if (reading.freeboard.geometry) {
    const region = chart(reading, language, prefs, render.interactive, y + 18);
    rendered.push(region.markup);
    y = region.bottom;
  } else {
    rendered.push(text(LEFT, y + 18, w('freeboard.geometry.title'), { size: 13, weight: 'bold' }));
    const problem = problemText(language, reading.freeboard.geometryProblem);
    y += 40;
    if (problem) y += wrap(rendered, LEFT, y, problem, { size: 11, fill: CHANGED }) * LINE;
    y += 14;
  }

  const listTop = y + 18;
  rendered.push(text(LEFT, listTop, w('freeboard.endpoints.title'), { size: 13, weight: 'bold' }));
  reading.freeboard.endpoints.forEach((item, index) => {
    const rowY = listTop + 28 + index * 26;
    const label = hullFreeboardCopy(language, item.label);
    const value = lengthText(item.value, prefs);
    const changed = item.changed ? `   ·   ${w('freeboard.changed')}` : '';
    const content = [
      `<rect x="12" y="${rowY - 17}" width="${WIDTH - 24}" height="23" fill="${item.changed ? '#fbf0ee' : 'none'}" stroke="${item.changed ? CHANGED : RULE}" stroke-width="1" />`,
      text(26, rowY, label, { size: 11, fill: item.changed ? CHANGED : INK, weight: 'bold' }),
      text(390, rowY, value, { size: 11, fill: item.changed ? CHANGED : INK }),
      text(620, rowY, changed, { size: 10, fill: MUTED }),
    ].join('');
    // With a chart the endpoint points are the focusable nodes; without one,
    // the endpoint rows themselves remain the eight selectable identities.
    rendered.push(reading.freeboard.geometry
      ? `<g data-freeboard-row="${item.key}">${content}</g>`
      : pointGroup(item, content, language, prefs, render.interactive));
  });

  const fractionTop = listTop + 28 + reading.freeboard.endpoints.length * 26 + 18;
  rendered.push(text(LEFT, fractionTop, w('freeboard.fraction.title'), { size: 13, weight: 'bold' }));
  reading.freeboard.fractions.forEach((item, index) => {
    const rowY = fractionTop + 22 + index * 18;
    const changed = item.changed ? `   ·   ${w('freeboard.changed')}` : '';
    rendered.push(text(26, rowY, `${hullFreeboardCopy(language, item.label)}: ${fractionText(item.value)}${changed}`, {
      size: 11, fill: item.changed ? CHANGED : INK,
    }));
  });
  const lastFractionY = fractionTop + 22 + (reading.freeboard.fractions.length - 1) * 18;
  const noteY = lastFractionY + 28;
  rendered.push(text(LEFT, noteY, w('freeboard.unitNote'), { size: 9, fill: MUTED }));
  const height = Math.max(120, noteY + 18);

  const rootRole = render.interactive ? 'group' : 'img';
  return [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${WIDTH} ${round(height)}" width="${WIDTH}" height="${round(height)}" role="${rootRole}" aria-labelledby="${titleId} ${descId}" font-family="${FONT}">`,
    `<title id="${titleId}">${escape(w('freeboard.profile.aria'))}</title>`,
    `<desc id="${descId}">${escape(w('freeboard.intro'))}</desc>`,
    `<rect x="0" y="0" width="${WIDTH}" height="${round(height)}" fill="#ffffff" />`,
    rendered.join(''),
    '</svg>',
  ].join('');
}

/** The eight endpoint identities in the order every profile and export writes them. */
export const FREEBOARD_PROFILE_ENDPOINTS = FREEBOARD_ENDPOINTS;

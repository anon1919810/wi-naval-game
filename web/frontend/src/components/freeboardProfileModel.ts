import type { Sps3b3Result } from '../types';

/**
 * The one pure reading of a native freeboard result's endpoint geometry.
 *
 * The freeboard profile and the armour diagram's deck-partition schematic are
 * two readings of the same eight saved endpoints and the same four declared deck
 * fractions, so the arithmetic that turns them into a drawing lives here once.
 * Nothing here computes a ship number: `length`, the eight heights and the four
 * fractions are exactly the saved fields, and the two coordinate helpers are the
 * same linear mapping the profile has always drawn with.
 *
 * A result that does not carry a usable length, forecastle fraction, flat-deck
 * fraction, quarterdeck fraction and all eight endpoint heights reads as `null`,
 * which is what keeps the existing profile exactly as it was.
 */

/** The eight saved freeboard endpoint heights, in the order the profile plots them. */
export const FREEBOARD_ENDPOINTS = [
  'freeQDAft', 'freeQDFor', 'freeADAft', 'freeADFor',
  'freeFDAft', 'freeFDFor', 'freeFCAft', 'freeFCFor',
] as const;

export interface FreeboardGeometry {
  /** The normalized waterline length the profile is drawn in, in feet. */
  length: number;
  /** The four declared deck fractions of that length; the afterdeck may be absent. */
  quarterdeck: number;
  afterdeck: number | null;
  flatDeck: number;
  forecastle: number;
  /** The eight endpoint heights, in feet. */
  heights: number[];
  /** The stem offset the profile extends to, and the bow x it raises to. */
  stern: number;
  bowX: number;
  /** The plotted station positions and the mapped drawing bounds. */
  xs: number[];
  low: number;
  span: number;
  top: number;
  bottom: number;
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function value(source: Record<string, unknown> | null, key: string): number | null {
  if (!source) return null;
  const raw = source[key];
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : null;
}

/** The saved freeboard geometry of one result, or `null` when it cannot be plotted. */
export function readFreeboardGeometry(result: Sps3b3Result | null | undefined): FreeboardGeometry | null {
  const hull = record(result?.hull);
  const freeboard = record(result?.freeboard);
  const length = value(hull, 'length');
  const forecastle = value(freeboard, 'fcLength');
  const flatDeck = value(freeboard, 'fdLength');
  const quarterdeck = value(freeboard, 'qdLength');
  const heights = FREEBOARD_ENDPOINTS.map(key => value(freeboard, key));
  if (!length) return null;
  if (forecastle === null || flatDeck === null || quarterdeck === null) return null;
  if (heights.some(height => height === null)) return null;
  const plotted = heights as number[];
  const afterdeck = value(freeboard, 'adLength');
  const bowAngle = value(freeboard, 'lengthBow') ?? 0;
  const stern = Math.max(0, value(freeboard, 'lengthStern') ?? 0);
  const bowX = length + plotted[7] * Math.tan(bowAngle * Math.PI / 180);
  const xs = [
    -stern, length * quarterdeck, length * quarterdeck,
    length * (1 - forecastle - flatDeck), length * (1 - forecastle - flatDeck),
    length * (1 - forecastle), length * (1 - forecastle), bowX,
  ];
  const low = Math.min(0, ...xs);
  const span = Math.max(length, ...xs) - low;
  const top = Math.max(1, ...plotted);
  const bottom = Math.min(0, ...plotted);
  return { length, quarterdeck, afterdeck, flatDeck, forecastle, heights: plotted, stern, bowX, xs, low, span, top, bottom };
}

/** The drawing x of one station position, exactly as the profile maps it. */
export function profileX(geometry: FreeboardGeometry, value: number): number {
  return 30 + (value - geometry.low) / geometry.span * 940;
}

/** The drawing y of one freeboard height, exactly as the profile maps it. */
export function profileY(geometry: FreeboardGeometry, value: number): number {
  return 150 - (value - geometry.bottom) / (geometry.top - geometry.bottom) * 110;
}

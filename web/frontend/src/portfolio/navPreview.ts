/**
 * Geometry and arbitration for the Work/About navigation preview.
 *
 * The rail is the only navigation on the site, so it answers a pointer or the
 * keyboard before it answers a press: pointing at a destination paints that word
 * blue with a full underline, and the page that is actually on screen keeps its
 * own state until something is really committed. Nothing here touches the DOM —
 * these are the numbers the component writes as custom properties, kept apart so
 * they can be reasoned about and tested on their own.
 *
 * Two rules the shape of the answer depends on:
 *
 * - **The circle opens from where the pointer entered the word.** Moving inside
 *   the same word must not move the origin, or the reveal would slide around
 *   under the pointer. A keyboard has no entry point, so the middle of the word
 *   is used instead.
 * - **The circle stops at the far corner.** That is the smallest radius that has
 *   actually covered the whole word, so the reveal ends exactly when the word is
 *   blue and not one frame earlier.
 */

/** One duration for the whole preview exchange, in milliseconds. */
export const NAV_PREVIEW_MS = 300;
/** Damped and monotonic: the two words hand over without a bounce or a jump. */
export const NAV_PREVIEW_EASE = 'cubic-bezier(.2,.8,.2,1)';

/** The two entries the rail owns. Work also stands in for the work detail. */
export type RailView = 'home' | 'about';

export interface NavPoint { readonly x: number; readonly y: number }

export interface NavBox {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));
const round = (value: number) => Math.round(value * 100) / 100;

/**
 * Which rail entry is the truthful current page. Work owns the exhibit *and* its
 * detail, so a public view that is not About is Work.
 */
export function railView(view: string): RailView {
  return view === 'about' ? 'about' : 'home';
}

/**
 * The word the preview is aimed at, in a fixed order of authority:
 *
 * 1. a destination that has been **pressed** and is still travelling,
 * 2. the word under the **pointer**,
 * 3. the word holding **keyboard focus**,
 * 4. the route that is actually committed.
 *
 * The pointer outranks focus because a pointer that is present is a more current
 * statement of intent than a focus ring left behind by an earlier press. A held
 * destination outranks both, because the sheet covering the content needs the
 * word it was asked for to stay blue all the way through.
 */
export function previewTarget(current: RailView, hover: RailView | null, focus: RailView | null, held: RailView | null): RailView {
  return held ?? hover ?? focus ?? current;
}

/** Where the pointer crossed into the word, clamped to the word's own box. */
export function entryPoint(box: NavBox, clientX: number, clientY: number): NavPoint {
  return {
    x: round(clamp(clientX - box.left, 0, Math.max(0, box.width))),
    y: round(clamp(clientY - box.top, 0, Math.max(0, box.height))),
  };
}

/** The keyboard has no entry point, so the middle of the word is the fair one. */
export function wordCentre(box: NavBox): NavPoint {
  return { x: round(Math.max(0, box.width) / 2), y: round(Math.max(0, box.height) / 2) };
}

/** The distance from the origin to the furthest corner of the word. */
export function revealRadius(box: NavBox, origin: NavPoint): number {
  const width = Math.max(0, box.width);
  const height = Math.max(0, box.height);
  const far = Math.max(
    Math.hypot(origin.x, origin.y),
    Math.hypot(width - origin.x, origin.y),
    Math.hypot(origin.x, height - origin.y),
    Math.hypot(width - origin.x, height - origin.y),
  );
  return round(far);
}

/**
 * Geometry and arbitration for the Work/About/Credits navigation preview.
 *
 * The rail is the only navigation on the site, so it answers a pointer or the
 * keyboard before it answers a press: pointing at a destination paints that word
 * blue with a full underline, and the page that is actually on screen keeps its
 * own state until something is really committed. Nothing here touches the DOM —
 * these are the numbers the component writes as custom properties, kept apart so
 * they can be reasoned about and tested on their own.
 *
 * Three rules the shape of the answer depend on:
 *
 * - **The circle opens from where the pointer entered the word.** Moving inside
 *   the same word must not move the origin, or the reveal would slide around
 *   under the pointer. A keyboard has no entry point, so the middle of the word
 *   is used instead.
 * - **The circle stops at the far corner.** That is the smallest radius that has
 *   actually covered the whole word, so the reveal ends exactly when the word is
 *   blue and not one frame earlier.
 * - **A destination nobody pressed has no entry point.** A history entry or a
 *   typed address opens from the middle of the word rather than from wherever a
 *   pointer last happened to be, which is what keeps a stale press out of the
 *   next move.
 */

/** One duration for the whole preview exchange, in milliseconds. */
export const NAV_PREVIEW_MS = 300;
/** Damped and monotonic: the two words hand over without a bounce or a jump. */
export const NAV_PREVIEW_EASE = 'cubic-bezier(.2,.8,.2,1)';

/** The three entries the rail owns. Work also stands in for the work detail. */
export type RailView = 'home' | 'about' | 'credits';

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
 * detail, so a public view that is neither About nor Credits is Work.
 */
export function railView(view: string): RailView {
  if (view === 'about') return 'about';
  if (view === 'credits') return 'credits';
  return 'home';
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

/**
 * A word-local point in page coordinates.
 *
 * The preview's origin is stored relative to the word's own box, because that is
 * what the reveal radius is measured from. The page reveal needs the same place
 * in the coordinate system everything else on screen uses, and the word sits
 * outside the content region it opens: adding the box's own origin is what keeps
 * the circle at the word the visitor pressed instead of at the top-left of the
 * column. Clamped, because a box measured before a resize may be stale.
 */
export function pageOrigin(box: NavBox, local: NavPoint): NavPoint {
  return {
    x: round(box.left + clamp(local.x, 0, Math.max(0, box.width))),
    y: round(box.top + clamp(local.y, 0, Math.max(0, box.height))),
  };
}

/**
 * Where a destination's page circle should open, in page coordinates.
 *
 * A destination that is being pressed continues its own preview origin: the
 * pointer's entry point, or the middle of the word under the keyboard. A
 * destination that nobody pressed — Back, Forward, a typed address, a reload —
 * has no entry point of its own and must not inherit the last press's, so it
 * opens from the middle of the word instead. `null` means the word has no box to
 * read at all, and the caller falls back to the middle of the destination region.
 */
export function destinationOrigin(box: NavBox | null, pressed: boolean, remembered?: NavPoint): NavPoint | null {
  if (!box || !(box.width > 0) || !(box.height > 0)) return null;
  return pageOrigin(box, pressed && remembered ? remembered : wordCentre(box));
}

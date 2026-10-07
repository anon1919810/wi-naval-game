/**
 * The reading controller: which section of a long page the reader is in, and the
 * one quiet tick that says so.
 *
 * Nothing here animates anything and nothing here draws. It answers two
 * questions — *where is the reader* and *may that answer be heard* — and it
 * answers them defensively, because both are easy to get wrong in ways a reader
 * notices immediately:
 *
 * - **A boundary is not a place.** A scroll position that wobbles either side of
 *   a section edge must not re-fire the tick, so every change has to clear the
 *   boundary by a hysteresis band before it counts. See {@link currentSection}.
 * - **A tick is an answer to a gesture, not a report.** Mounting, route
 *   placement, a resize, a late font and a tab coming back from hidden all move
 *   the reading line without the reader having scrolled anything, so none of them
 *   may make a sound. Only a real scrolling gesture — or an explicit press on
 *   the ruler itself — arms the voice for a bounded period. See {@link Reading.arm}.
 *
 * The geometry is injected rather than read here, so the lifecycle can be tested
 * with fake sections and a fake clock while the browser keeps its own geometry.
 */

import type { PreviewSound } from './previewAudio';

/** Where the reader's eye sits, measured down from the top of the viewport. */
export const READ_LINE_PX = 96;
/** How far past a boundary the reading line must travel before the section changes. */
export const SECTION_HYSTERESIS_PX = 24;
/** Quick traversal settles this long before the section it settles on is heard. */
export const SECTION_SETTLE_MS = 140;
/** Minor ticks per gap between two major marks; distance, not identity. */
export const RULER_MINOR_MARKS = 4;
/** How long a real scrolling gesture keeps asking for the voice. */
export const SECTION_ARM_MS = 1500;

/** One section of a page, as the ruler names it. */
export interface ReadingSection {
  readonly id: string;
  readonly label: string;
}

/** `02 / CAPABILITIES` — reading order, and never the section's own numbering. */
export function sectionLabel(index: number, label: string): string {
  return `${String(index + 1).padStart(2, '0')} / ${label.trim().toUpperCase()}`;
}

/**
 * Where the document has to be scrolled for a section to sit at the reading
 * line: its own top edge, less the line's offset, never above the top. This is
 * what a ruler mark scrolls to, so the mark the reader pressed and the section
 * that arrives are the same place, not a heading parked under the chrome.
 */
export function sectionScrollTop(top: number, offset = READ_LINE_PX): number {
  return Math.max(0, Math.ceil(top - offset));
}

/**
 * Which section the reading line is in, given the one it was already in.
 *
 * `tops` are the sections' own top edges in document coordinates, in reading
 * order; `line` is the reading line in the same coordinates. The answer is the
 * last section the line has passed — except while the line is inside the
 * hysteresis band around a boundary the reader is already on one side of, where
 * the answer is simply the section held. Twenty-four pixels is about a third of a
 * line of body type: enough that a scrollbar drag, a momentum tail or a trackpad
 * settling cannot chatter across it, small enough that it is not felt as a lag.
 *
 * `atEnd` says the document cannot be scrolled any further. A short last section
 * would otherwise be unreachable, because the reading line never gets past its
 * top edge however far down the page the reader goes.
 */
export function currentSection(
  tops: readonly number[],
  line: number,
  held: number,
  options: { readonly hysteresis?: number; readonly atEnd?: boolean } = {},
): number {
  const count = tops.length;
  if (!count) return -1;
  if (options.atEnd) return count - 1;
  const hysteresis = options.hysteresis ?? SECTION_HYSTERESIS_PX;
  const at = (index: number) => tops[Math.min(Math.max(index, 0), count - 1)];
  // The section the geometry says we are in, clamped: above the first section is
  // still the first section, because a ruler with no current mark reads as broken.
  let reached = 0;
  for (let index = 0; index < count; index += 1) if (line >= tops[index]) reached = index;
  if (held < 0 || held >= count || reached === held) return reached;
  if (reached > held) return line >= at(held + 1) + hysteresis ? reached : held;
  return line <= at(held) - hysteresis ? reached : held;
}

/** One tick of the ruler: where it sits along the track, and whether it is a section. */
export interface RulerStop {
  /** A fraction of the measured reading distance, always 0…1. */
  readonly at: number;
  readonly major: boolean;
  readonly index: number;
}

/**
 * Minor and major ticks across the track, in reading order.
 *
 * The majors are the measured sections themselves — a mark is at the section, not
 * at a guess of it. The minors divide the gaps, so a long gap between two short
 * sections still reads as distance travelled. A page that cannot be measured at
 * all yields one mark at the top rather than an empty track.
 */
export function rulerStops(tops: readonly number[], span: number, minors = RULER_MINOR_MARKS): RulerStop[] {
  if (!tops.length || !(span > 0)) return tops.length ? [{ at: 0, major: true, index: 0 }] : [];
  const origin = tops[0];
  const clamp01 = (value: number) => Math.min(1, Math.max(0, value));
  const stops: RulerStop[] = [];
  for (let index = 0; index < tops.length; index += 1) {
    // The minors divide the gap that is being crossed, so distance travelled
    // reads as distance travelled even where two short sections are far apart.
    // The first section has no gap before it, so it contributes no minors.
    for (let minor = 1; index > 0 && minor < minors; minor += 1) {
      const from = tops[index - 1];
      stops.push({ at: clamp01((from + (tops[index] - from) * (minor / minors) - origin) / span), major: false, index });
    }
    stops.push({ at: clamp01((tops[index] - origin) / span), major: true, index });
  }
  return stops;
}

/** The sections a page declares, in document order, as `(node, label)` pairs. */
export function sectionNodes(root: ParentNode | null): HTMLElement[] {
  return root ? Array.from(root.querySelectorAll<HTMLElement>('[data-ff-section]')) : [];
}

/**
 * The declared sections of a page, measured in document coordinates.
 *
 * Measured in one pass and read once per settle, never per frame. A section with
 * no box — not laid out, `display: none`, or a browser that will not measure it —
 * contributes its predecessor's edge, which is what keeps the ruler's numbering
 * and its ticks aligned with the sections the reader can actually see.
 */
export function measureSections(nodes: readonly HTMLElement[], scrollY: number): number[] {
  const tops: number[] = [];
  for (const node of nodes) {
    const rect = node.getBoundingClientRect();
    const top = rect.top + scrollY;
    tops.push(tops.length && top <= tops[tops.length - 1] ? tops[tops.length - 1] : top);
  }
  return tops;
}

/** The keys that scroll a document on their own. Only these arm the voice. */
const SCROLL_KEYS = new Set(['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' ']);

export interface ReadingOptions {
  /** The visible page's section tops, in document coordinates, in reading order. */
  measure: () => number[];
  /** The reading line, in document coordinates. */
  line: () => number;
  /** True when the document cannot be scrolled any further. */
  atEnd?: () => boolean;
  /** Fired only when the section identity itself changes. */
  onCurrent: (index: number) => void;
  /** The one voice a settled section may use. Optional: a page may be silent. */
  sound?: Pick<PreviewSound, 'muted' | 'tap'>;
  settle?: number;
  arm?: number;
  reducedMotion?: () => boolean;
  /** Injected by tests; `performance.now` and `window.setTimeout` otherwise. */
  now?: () => number;
  setTimer?: (callback: () => void, ms: number) => number;
  clearTimer?: (id: number) => void;
}

export interface Reading {
  /** The section the reader is in, or -1 before the page has been measured. */
  readonly current: number;
  /** True while a real gesture is still asking for the voice. */
  readonly armed: boolean;
  /** Called by the ruler: a press is a gesture, and it settles a section itself. */
  arm(): void;
  /** Re-measure and re-settle without arming. Used on resize, fonts and return. */
  refresh(): void;
  /** Every listener, timer and pending tick released. Idempotent. */
  dispose(): void;
}

/**
 * The controller itself.
 *
 * Listening is deliberately asymmetric: scroll settles, geometry refreshes, and
 * only real gestures arm. That is the whole of "no sound on mount, on route
 * placement, on resize, on fonts arriving, or when a hidden page comes back".
 *
 * Arming expires on its own, so a single wheel cannot authorise a later
 * programmatic scroll — a route placing this page at a section, a ruler press
 * whose smooth scroll runs for a second — to be heard as if a reader had asked
 * for it. And the debounce is restarted by *every* scroll event, not only by the
 * ones that change section, so the tick belongs to the moment the reader stopped
 * rather than to the first boundary they happened to cross.
 */
export function startReading(options: ReadingOptions): Reading {
  const now = options.now ?? (() => performance.now());
  const setTimer = options.setTimer ?? ((callback: () => void, ms: number) => window.setTimeout(callback, ms));
  const clearTimer = options.clearTimer ?? ((id: number) => window.clearTimeout(id));
  const settle = options.settle ?? SECTION_SETTLE_MS;
  const lifetime = options.arm ?? SECTION_ARM_MS;

  let current = -1;
  let settled = -1;
  let armedUntil = 0;
  let owed = false;
  let seeking = false;
  let pending = 0;
  let disposed = false;

  const armed = () => now() < armedUntil;
  const quiet = () => document.visibilityState === 'hidden' || !!options.reducedMotion?.();
  const cancel = () => { owed = false; if (pending) { clearTimer(pending); pending = 0; } };
  const speak = () => {
    pending = 0;
    const sound = options.sound;
    const shouldSpeak = owed && current !== settled && current >= 0 && !quiet() && !sound?.muted;
    settled = current;
    owed = false;
    armedUntil = 0;
    seeking = false;
    if (shouldSpeak) sound?.tap('section');
  };
  /** Report where the reader is, and queue the tick that belongs to it. */
  const settleSection = (withVoice: boolean) => {
    if (disposed) return;
    if (pending) { clearTimer(pending); pending = 0; }
    const eligible = withVoice && !quiet() && (armed() || owed);
    const next = currentSection(options.measure(), options.line(), current, {
      atEnd: options.atEnd?.(), hysteresis: seeking ? 0 : SECTION_HYSTERESIS_PX,
    });
    if (next !== current) { current = next; options.onCurrent(next); }
    if (!eligible) { settled = current; owed = false; return; }
    owed = current !== settled;
    if (owed) pending = setTimer(speak, settle);
  };
  const gesture = () => { if (!disposed && !quiet()) { armedUntil = now() + lifetime; seeking = false; } };
  const scroll = () => settleSection(true);
  /** Geometry moved under the reader without the reader asking: say nothing. */
  const refresh = () => {
    if (disposed) return;
    cancel(); armedUntil = 0; seeking = false; settleSection(false);
  };
  const key = (event: KeyboardEvent) => {
    const target = event.target;
    if (event.defaultPrevented || event.ctrlKey || event.altKey || event.metaKey
      || target instanceof Element && (target.closest('input, textarea, select, [contenteditable="true"], [role="slider"]')
        || event.key === ' ' && target.closest('button'))) return;
    if (SCROLL_KEYS.has(event.key)) gesture();
  };
  const visibility = () => {
    // A tab that comes back has been somewhere else entirely; it starts unarmed.
    refresh();
  };
  const preference = refresh;

  window.addEventListener('scroll', scroll, { passive: true });
  window.addEventListener('resize', refresh);
  window.addEventListener('wheel', gesture, { passive: true });
  window.addEventListener('touchmove', gesture, { passive: true });
  window.addEventListener('keydown', key, { passive: true });
  document.addEventListener('visibilitychange', visibility);
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  media?.addEventListener?.('change', preference);
  refresh();

  return {
    get current() { return current; },
    get armed() { return armed(); },
    /** A press on a ruler mark is a real gesture, and it asks for the voice. */
    arm: () => { gesture(); seeking = true; },
    refresh,
    dispose() {
      if (disposed) return;
      disposed = true;
      cancel();
      window.removeEventListener('scroll', scroll);
      window.removeEventListener('resize', refresh);
      window.removeEventListener('wheel', gesture);
      window.removeEventListener('touchmove', gesture);
      window.removeEventListener('keydown', key);
      document.removeEventListener('visibilitychange', visibility);
      media?.removeEventListener?.('change', preference);
    },
  };
}

/**
 * One controller for every page-level transition on the public shell.
 *
 * Four different moves share one set of rules, because they share the same
 * failure modes:
 *
 * 1. **theme** — the radial clip of the incoming root snapshot (560 ms).
 * 2. **sheet / sheet-back** — a sharp diagonal wipe of the artwork snapshot
 *    (360 ms), opposite edge for the direction of the reference change.
 * 3. **page / page-back** — content-only (260 ms). The header and footer stay
 *    put, so this must not snapshot the page at all: it sets one attribute and
 *    lets a plain CSS animation move the section that appeared.
 * 4. **detail** — the exhibit's artwork and the work detail's hero are the same
 *    shared drawing, so one named group morphs between them (400 ms) while the
 *    persistent chrome stays still.
 * 5. **tool** — the exhibit frame morphs into the workspace (450 ms).
 * 6. **app-route** — the workspace moves between its own pages (220 ms).
 *
 * What the controller guarantees for all six:
 *
 * - **Feature detection, never assumptions.** `document.startViewTransition` is
 *   checked at call time; reduced motion and an unsupported browser both fall
 *   back to an immediate, un-animated commit.
 * - **Latest wins.** Starting a transition releases the previous one, and the
 *   generation counter moves *before* `skipTransition()` is called: a skipped
 *   transition still runs its update callback, so the bump is what stops that
 *   callback from committing, and a callback arriving after unmount can no
 *   longer match.
 * - **No unhandled rejections.** `ready` and `finished` both get a rejection
 *   handler; skipping and interrupting are normal outcomes here.
 * - **Cleanup on every path.** Interruption, error and unmount drop the
 *   attributes and the timer the controller owns.
 * - **No waiting.** Nothing here waits for a module, an image or a response.
 */

export type TransitionKind = 'theme' | 'sheet' | 'sheet-back' | 'page' | 'page-back' | 'detail' | 'tool' | 'tool-back' | 'app-route';

/** Choreography, in milliseconds. These are the only moving durations in the shell. */
export const TRANSITION_MS = {
  /** Radial theme reveal. */
  theme: 560,
  /** Sharp diagonal reference switch. */
  sheet: 360,
  /** Content-only Work/About move. */
  page: 260,
  /** Exhibit artwork morphing into the work detail's hero. */
  detail: 400,
  /** Exhibit frame expanding into the workspace. */
  tool: 450,
  /** One workspace page to the next: identity holds, content arrives. */
  appRoute: 220,
} as const;

/** The vessel only leaves while the frame expands; it never stretches. */
export const TOOL_SCAN_MS = 180;
/** Public chrome leaving the way out. */
export const TOOL_CHROME_MS = 150;
/** The workspace surface fades in behind the expanded frame. */
export const TOOL_SURFACE_MS = 240;

/**
 * Kinds that set one attribute on the root and let plain CSS move a section.
 *
 * `page`, `page-back` and `app-route` are here for the same reason: these pages
 * can each be thousands of lines — a full report, a tall About — and a named-group
 * morph would have to snapshot the whole of them, which is expensive and would
 * distort the text as it moved. So nothing is captured, and the content changes
 * as the attribute is set. Identity is carried by the header and the rail, which
 * are outside `.ff-main` and hold still, and the arrival is a plain CSS animation
 * with the shared chrome sitting still beside it.
 */
interface AttributeKind {
  readonly attribute: 'ffPage' | 'ffAppRoute';
  /** The value the attribute takes while the move runs. */
  readonly value: string;
  /** How long the attribute is held before it is released. */
  readonly duration: number;
}

const ATTRIBUTE_KINDS: ReadonlyMap<TransitionKind, AttributeKind> = new Map([
  // Work→About: the section that appeared rises into place.
  ['page', { attribute: 'ffPage', value: 'in', duration: TRANSITION_MS.page }],
  // About→Work: the same cut, entering from the other side.
  ['page-back', { attribute: 'ffPage', value: 'out', duration: TRANSITION_MS.page }],
  ['app-route', { attribute: 'ffAppRoute', value: 'in', duration: TRANSITION_MS.appRoute }],
]);
/** Kinds that move the exhibit frame and the workspace surface. */
const TOOL_KINDS: ReadonlySet<TransitionKind> = new Set<TransitionKind>(['tool', 'tool-back']);

/** True while the controller owns a running transition. */
export function transitionsActive(): boolean {
  return active !== null;
}

const EASE = 'cubic-bezier(.22,1,.36,1)';

interface ViewTransitionLike {
  readonly ready: Promise<void>;
  readonly finished: Promise<void>;
  skipTransition?: () => void;
}

type StartViewTransition = (update: () => void | Promise<void>) => ViewTransitionLike;

/** Narrow read of the DOM surface: no `extends Document`, no invented members. */
function startViewTransition(): StartViewTransition | undefined {
  const surface = document as { startViewTransition?: StartViewTransition };
  return typeof surface.startViewTransition === 'function' ? surface.startViewTransition.bind(document) : undefined;
}

/** True when the browser can snapshot and morph named groups. */
export function viewTransitionsAvailable(): boolean {
  return startViewTransition() !== undefined;
}

export function prefersReducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/**
 * The radial theme clip and the tool fades are driven here rather than in CSS so
 * the numbers above stay the single source of truth for the choreography.
 * jsdom has no Web Animations API, so this is a no-op there.
 */
export function animateTheme(origin: { x: number; y: number }, radius: number): void {
  const host = document.documentElement;
  if (typeof host.animate !== 'function') return;
  host.animate(
    { clipPath: [`circle(0px at ${origin.x}px ${origin.y}px)`, `circle(${radius}px at ${origin.x}px ${origin.y}px)`] },
    { duration: TRANSITION_MS.theme, easing: EASE, pseudoElement: '::view-transition-new(root)' },
  );
}

/**
 * The exhibit becomes the workspace, and the same frame morph runs in reverse on
 * the way back. The frame expands or contracts; the vessel that no longer has a
 * frame to sit in leaves quickly, in either direction, at its own size (see
 * portfolio.css) so it is never stretched by the morph. Going back, the outgoing
 * application snapshot is faded rather than scaled: its full-bleed surface has
 * no proportion worth preserving, and scaling it would only expose that.
 */
export function animateTool(returning: boolean): void {
  const host = document.documentElement;
  if (typeof host.animate !== 'function') return;
  const fade = (pseudo: string, from: number, to: number, duration: number, delay = 0, easing = 'linear') =>
    host.animate({ opacity: [from, to] }, { duration, delay, easing, fill: 'both', pseudoElement: `::view-transition-${pseudo}` });
  // Whichever surface is leaving gets the quick departure.
  fade(returning ? 'old(ff-frame)' : 'old(ff-scan)', 1, 0, returning ? TOOL_CHROME_MS : TOOL_SCAN_MS);
  // Whichever surface is arriving gets the slower arrival behind the frame.
  fade(returning ? 'new(ff-scan)' : 'new(ff-frame)', 0, 1, TOOL_SURFACE_MS, TOOL_CHROME_MS - 10, EASE);
  fade('old(root)', 1, 0, TOOL_CHROME_MS);
}

interface ActiveTransition { clean: () => void; cancel: () => void }

let generation = 0;
let active: ActiveTransition | null = null;

/** A transition has ended: finished, interrupted, cancelled or committed at once. */
export interface TransitionEnd {
  /** The generation that owned the move, so a late end can be told from a late start. */
  readonly generation: number;
  readonly kind: TransitionKind;
}

const endings = new Set<(event: TransitionEnd) => void>();

/**
 * Watch for the controller's current move ending.
 *
 * Every move here is announced, including the ones that reach their destination
 * at once: reduced motion, an unsupported browser and the content-only cut all
 * still have a beginning and an end, and a listener that guessed at a duration
 * would be wrong for whichever one it did not expect. Anything that has to hold a
 * state across a whole move — the navigation preview holding the word it was
 * asked for — needs this rather than a guess at a duration.
 */
export function onTransitionEnd(listener: (event: TransitionEnd) => void): () => void {
  endings.add(listener);
  return () => { endings.delete(listener); };
}

/** The generation that owns the next move. Read before a move starts, to tell later ends apart. */
export function transitionGeneration(): number {
  return generation;
}

function announce(mine: number, kind: TransitionKind): void {
  for (const listener of [...endings]) listener({ generation: mine, kind });
}

export interface TransitionOptions {
  /** Milliseconds the controller keeps its own attributes. Defaults per kind. */
  duration?: number;
  /**
   * Runs once the snapshots exist, where the keyframes are driven. Defaults to
   * the choreography of the kind, so callers never repeat a duration.
   */
  animate?: () => void;
}

/**
 * Release the current transition's attributes and timer, and retire its update
 * callback. Safe to call when idle. The generation moves first and the owned
 * attribute is removed in the same synchronous step: a cancelled transition
 * still runs its callback *and* still resolves `ready`/`finished` afterwards,
 * so nothing late may be able to reintroduce state that is already gone.
 */
export function cancelTransitions(): void {
  const current = active;
  active = null;
  generation++;
  current?.clean();
  try { current?.cancel(); } catch { /* already settled: nothing to skip */ }
}

/**
 * Run one state change inside one transition. The returned promise settles when
 * the transition is over, finished, skipped or impossible — it never rejects.
 */
export async function runTransition(kind: TransitionKind, update: () => void, options: TransitionOptions = {}): Promise<void> {
  cancelTransitions();
  const mine = generation;
  const commit = () => { if (mine === generation) update(); };
  const root = document.documentElement;

  const start = startViewTransition();
  if (!start || prefersReducedMotion()) {
    commit();
    // Reduced motion and an unsupported browser both reach the page at once, and
    // that is still a move with an end: anything waiting on this one is released.
    announce(mine, kind);
    return;
  }

  const attribute = ATTRIBUTE_KINDS.get(kind);
  if (attribute) {
    // The live page is always interactive here: there is no snapshot layer at
    // all, only a CSS animation on the section that just appeared, and the
    // content changes in the same synchronous step that sets the attribute.
    root.dataset[attribute.attribute] = attribute.value;
    const timer = window.setTimeout(() => { if (mine === generation) clean(); }, options.duration ?? attribute.duration);
    const clean = () => { window.clearTimeout(timer); delete root.dataset[attribute.attribute]; if (mine === generation) active = null; announce(mine, kind); };
    active = { clean, cancel: () => {} };
    commit();
    return;
  }

  root.dataset.ffTransition = kind;
  let transition: ViewTransitionLike;
  try {
    transition = start(commit);
  } catch {
    delete root.dataset.ffTransition;
    commit();
    announce(mine, kind);
    return;
  }
  // A snapshot layer sits above the live page, and a snapshot of a clickable
  // control is not clickable. The live page keeps receiving pointer events for
  // the whole of each transition, so the buttons underneath stay usable even
  // though their painted counterpart is frozen. portfolio.css drops the pointer
  // blocking while any of these attributes is present.
  // Unconditional, and only reachable while this run still owns `active`: the
  // owner releases the attribute on cancel, while the late cleanup below stays
  // generation-guarded so a finished callback can never clear a newer
  // transition's attribute.
  const clean = () => { delete root.dataset.ffTransition; if (mine === generation) active = null; announce(mine, kind); };
  active = { clean, cancel: () => { transition.skipTransition?.(); } };
  const drive = options.animate ?? (TOOL_KINDS.has(kind) ? () => animateTool(kind === 'tool-back') : undefined);
  await transition.ready.then(
    () => { if (mine === generation) drive?.(); },
    () => { /* Skipped before capture: there is nothing to animate. */ },
  ).catch(() => {});
  await transition.finished.catch(() => {});
  if (mine === generation) clean();
}

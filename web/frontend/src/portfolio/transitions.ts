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
 * 4. **tool** — the exhibit frame morphs into the workspace (450 ms).
 *
 * What the controller guarantees for all four:
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

export type TransitionKind = 'theme' | 'sheet' | 'sheet-back' | 'page' | 'page-back' | 'tool' | 'tool-back';

/** Choreography, in milliseconds. These are the only moving durations in the shell. */
export const TRANSITION_MS = {
  /** Radial theme reveal. */
  theme: 560,
  /** Sharp diagonal reference switch. */
  sheet: 360,
  /** Content-only Work/About move. */
  page: 260,
  /** Exhibit frame expanding into the workspace. */
  tool: 450,
} as const;

/** The vessel only leaves while the frame expands; it never stretches. */
export const TOOL_SCAN_MS = 180;
/** Public chrome leaving the way out. */
export const TOOL_CHROME_MS = 150;
/** The workspace surface fades in behind the expanded frame. */
export const TOOL_SURFACE_MS = 240;

/** Kinds that animate the section itself instead of snapshotting the page. */
const ATTRIBUTE_KINDS: ReadonlySet<TransitionKind> = new Set<TransitionKind>(['page', 'page-back']);
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
  if (!start || prefersReducedMotion()) { commit(); return; }

  if (ATTRIBUTE_KINDS.has(kind)) {
    // The live page is always interactive here: there is no snapshot layer at
    // all, only a CSS animation on the section that just appeared.
    root.dataset.ffPage = kind === 'page-back' ? 'out' : 'in';
    const timer = window.setTimeout(() => { if (mine === generation) clean(); }, options.duration ?? TRANSITION_MS.page);
    const clean = () => { window.clearTimeout(timer); delete root.dataset.ffPage; if (mine === generation) active = null; };
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
  const clean = () => { delete root.dataset.ffTransition; if (mine === generation) active = null; };
  active = { clean, cancel: () => { transition.skipTransition?.(); } };
  const drive = options.animate ?? (TOOL_KINDS.has(kind) ? () => animateTool(kind === 'tool-back') : undefined);
  await transition.ready.then(
    () => { if (mine === generation) drive?.(); },
    () => { /* Skipped before capture: there is nothing to animate. */ },
  ).catch(() => {});
  await transition.finished.catch(() => {});
  if (mine === generation) clean();
}

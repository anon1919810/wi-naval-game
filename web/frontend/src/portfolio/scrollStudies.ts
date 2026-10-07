/**
 * Scroll-linked drawings for the public pages, and the one curve they are
 * allowed to pretend to be.
 *
 * Three things live here, in this order of importance:
 *
 * 1. **The real Cf curve.** `connCf` is Conn's 1953 explicit approximation to the
 *    Kármán–Schoenherr line, exactly as `tools/plimsoll/resistance.py` computes
 *    it, together with the plot box it is drawn in. The friction figure and the
 *    marker that follows the curve share this one definition, so the marker
 *    cannot drift from the line it claims to be on. Nothing here is a measurement
 *    of a ship.
 * 2. **Progress.** One number per drawing: how far the figure has travelled
 *    through the viewport. It is clamped to 0…1 and it is reversible, because a
 *    reader who scrolls back must see the drawing go back, not find it stranded
 *    where they left it. A page shorter than its own viewport, a viewport shorter
 *    than a figure and a figure with no measurable box all clamp to something
 *    drawable rather than to `NaN`.
 * 3. **The painter.** A bounded, event-driven loop: it wakes on a scroll or a
 *    resize, paints, and runs a short damped tail so the drawing catches up
 *    instead of snapping. The tail ends on its own, nothing is animated while the
 *    page is hidden, and reduced motion gets the complete static drawing with no
 *    painted values at all.
 *
 * The figures themselves are never re-rendered while this runs: the painter only
 * writes attributes and custom properties on nodes the figure already contains,
 * so React never commits for a scroll.
 */

/* ---- the friction curve, as the calculation core has it -------------------- */

/** `tools/plimsoll/resistance.py`: Cf = 0.4631 / (log10 Re) ** 2.6. */
export const connCf = (reynolds: number) => 0.4631 / Math.log10(reynolds) ** 2.6;

/** The interval Plimsoll declares valid, and the top of the plotted coefficient. */
export const CF_LO = 6;
export const CF_HI = 9;
export const CF_TOP = 0.005;
/** The plot box inside the friction figure's own viewBox. */
export const PLOT = { x: 46, y: 18, w: 270, h: 146 };

/** A decade of Reynolds number across the plot's width, clamped to the interval. */
export const cfX = (logRe: number) => PLOT.x + ((logRe - CF_LO) / (CF_HI - CF_LO)) * PLOT.w;
/** A coefficient up the plot's height, clamped so a bad input stays on the paper. */
export const cfY = (cf: number) => PLOT.y + PLOT.h - (Math.min(CF_TOP, Math.max(0, cf)) / CF_TOP) * PLOT.h;

/** One point on the real curve, given how far along the interval to sit. */
export function frictionPoint(progress: number): { readonly logRe: number; readonly cf: number; readonly x: number; readonly y: number } {
  const logRe = CF_LO + (CF_HI - CF_LO) * Math.min(1, Math.max(0, progress));
  const cf = connCf(10 ** logRe);
  return { logRe, cf, x: cfX(logRe), y: cfY(cf) };
}

/* ---- the harmonic curve ---------------------------------------------------- */

/** The hero family: x = sin(3t + π/2), y = sin(2t), over one full turn. */
const HARMONIC = { a: 3, b: 2, p: Math.PI / 2, cx: 160, cy: 160, r: 140 };

export interface HarmonicFrame {
  /** Where along the curve the cursor is, in radians. */
  readonly t: number;
  /** A short dark segment of the real curve centred on the cursor. */
  readonly d: string;
  /** The cursor itself, on the same curve. */
  readonly x: number;
  readonly y: number;
}

/** The trace and its cursor at one progress, both on the real curve. */
export function harmonicFrame(progress: number, span = 0.34, samples = 24): HarmonicFrame {
  const p = Math.min(1, Math.max(0, progress));
  const t = p * Math.PI * 2;
  const at = (angle: number) => ({
    x: HARMONIC.cx + HARMONIC.r * Math.sin(HARMONIC.a * angle + HARMONIC.p),
    y: HARMONIC.cy - HARMONIC.r * Math.sin(HARMONIC.b * angle),
  });
  let d = '';
  for (let step = 0; step <= samples; step += 1) {
    const point = at(t - span + (span * 2 * step) / samples);
    d += `${step === 0 ? 'M' : 'L'}${Math.round(point.x * 100) / 100} ${Math.round(point.y * 100) / 100}`;
  }
  const head = at(t);
  return { t, d, x: Math.round(head.x * 100) / 100, y: Math.round(head.y * 100) / 100 };
}

/* ---- Work: the compass ------------------------------------------------------ */

/** Total sweep of the compass ring, in degrees: enough to read, never enough to spin. */
export const COMPASS_DEGREES = 8;
/** Total travel of the same ring, in the field's own composition units. */
export const COMPASS_SHIFT = 18;

export interface CompassFrame {
  /** Rotation about the study's own focal point, so tangent and point stay true. */
  readonly angle: number;
  readonly x: number;
  readonly y: number;
}

/** The compass at one progress: a slow sweep and a slow drift, both reversible. */
export function compassFrame(progress: number): CompassFrame {
  const p = Math.min(1, Math.max(0, progress));
  // Centred, so the drawing is where it started at both ends of the page.
  const swing = p - 0.5;
  return {
    angle: Math.round(swing * COMPASS_DEGREES * 100) / 100,
    x: Math.round(swing * COMPASS_SHIFT * 100) / 100,
    y: Math.round(-swing * COMPASS_SHIFT * 100) / 100,
  };
}

/* ---- progress -------------------------------------------------------------- */

export interface StudyBox { readonly top: number; readonly height: number }

/**
 * How far a figure has travelled through the viewport: 0 as its top edge touches
 * the bottom of the screen, 1 as its bottom edge leaves the top. Reversible, and
 * clamped, so scrolling back undoes it exactly.
 *
 * A figure with no measurable height has not been laid out; it is treated as a
 * single line at its own position, which paints something honest rather than
 * dividing by nothing.
 */
export function studyProgress(box: StudyBox, viewportHeight: number): number {
  const height = Number.isFinite(box.height) ? Math.max(0, box.height) : 0;
  const travel = Math.max(0, viewportHeight) + height;
  if (!(travel > 0)) return 0;
  const top = Number.isFinite(box.top) ? box.top : 0;
  return Math.min(1, Math.max(0, (Math.max(0, viewportHeight) - top) / travel));
}

/**
 * The one figure allowed to move: the one whose centre is nearest the middle of
 * the screen. Everything else stays at its resting state, so a page of drawings
 * never shows four things moving at once. Returns -1 when none of them is near
 * enough to be worth painting.
 */
export function dominantBox(boxes: readonly StudyBox[], viewportHeight: number): number {
  const middle = Math.max(0, viewportHeight) / 2;
  let best = -1;
  let distance = Number.POSITIVE_INFINITY;
  boxes.forEach((box, index) => {
    if (!(box.height > 0) || !Number.isFinite(box.top) || box.top >= viewportHeight || box.top + box.height <= 0) return;
    const offset = Math.abs(box.top + box.height / 2 - middle);
    if (offset < distance) { distance = offset; best = index; }
  });
  return best;
}

/* ---- the painter ----------------------------------------------------------- */

/** The compass study's focal point, in its own viewBox. Shared with pageGeometry. */
const FOCAL = { x: 1180, y: -60 };
/** How long the damped tail may run after the last scroll event, in milliseconds. */
export const STUDIES_SETTLE_MS = 420;
/** First-order catch-up rate: how much of the remaining gap a frame closes. */
const CATCH_UP = 0.24;
/** Below this, the drawing is where it is going and the tail may stop. */
const REST = 0.0015;

export interface StudiesOptions {
  /** The figures of the page that is actually on screen, in document order. */
  find: () => readonly HTMLElement[];
  /** The viewport height the progress is measured against. */
  viewport: () => number;
  /** True while the reader has asked for less motion. Nothing is painted then. */
  reducedMotion: () => boolean;
  settle?: number;
  now?: () => number;
  requestFrame?: (callback: () => void) => number;
  cancelFrame?: (handle: number) => void;
}

export interface Studies {
  /** Wake, measure and paint. Safe to call on every scroll event. */
  update(): void;
  /** Release every listener, frame and painted value. Idempotent. */
  dispose(): void;
}

/** Write one study's resting state, which is also its reduced-motion state. */
function rest(node: HTMLElement): void {
  if (node.dataset.ffStudy === 'compass') {
    node.querySelector('[data-ff-motion]')?.removeAttribute('transform');
    return;
  }
  if (node.dataset.ffStudy === 'harmonic') {
    // The trace's own start is a real point on the curve, so the static figure
    // keeps it: reduced motion loses the travel, not the drawing.
    paint(node, 0);
    return;
  }
  if (node.dataset.ffStudy === 'friction') {
    for (const motion of node.querySelectorAll('[data-ff-motion]')) {
      if (motion instanceof SVGElement && motion.tagName === 'circle') motion.style.opacity = '0';
      else if (motion instanceof SVGElement) motion.setAttribute('d', '');
    }
    return;
  }
  node.style.removeProperty('--ff-study-progress');
}

/** Write one study at one progress. */
function paint(node: HTMLElement, progress: number): void {
  const study = node.dataset.ffStudy;
  if (study === 'compass') {
    const group = node.querySelector('[data-ff-motion]');
    if (!(group instanceof SVGElement)) return;
    const frame = compassFrame(progress);
    group.setAttribute('transform', `rotate(${frame.angle} ${FOCAL.x} ${FOCAL.y}) translate(${frame.x} ${frame.y})`);
    return;
  }
  if (study === 'harmonic') {
    const frame = harmonicFrame(progress);
    const trace = node.querySelector('[data-ff-motion="trace"]');
    const cursor = node.querySelector('[data-ff-motion="cursor"]');
    if (trace instanceof SVGElement) { trace.setAttribute('d', frame.d); trace.style.opacity = '1'; }
    if (cursor instanceof SVGElement) { cursor.setAttribute('cx', String(frame.x)); cursor.setAttribute('cy', String(frame.y)); cursor.style.opacity = '1'; }
    return;
  }
  if (study === 'friction') {
    const point = frictionPoint(progress);
    const marker = node.querySelector('[data-ff-motion="marker"]');
    const across = node.querySelector('[data-ff-motion="across"]');
    const up = node.querySelector('[data-ff-motion="up"]');
    if (marker instanceof SVGElement) {
      marker.setAttribute('cx', String(point.x));
      marker.setAttribute('cy', String(point.y));
      marker.style.opacity = '1';
    }
    // Both projections start on the marker and land on the axes it is read
    // against, so the marker can never be somewhere the projections disagree with.
    if (across instanceof SVGElement) { across.setAttribute('d', `M${point.x} ${point.y}H${PLOT.x}`); across.style.opacity = '1'; }
    if (up instanceof SVGElement) { up.setAttribute('d', `M${point.x} ${point.y}V${PLOT.y + PLOT.h}`); up.style.opacity = '1'; }
    return;
  }
  // Scale and Power are emphasis, not geometry: the figure keeps every term of
  // its formula and only the guides change weight.
  node.style.setProperty('--ff-study-progress', progress.toFixed(3));
}

/** Paint one page's figures and report what each of them was given. */
/**
 * The controller for one visible page.
 *
 * One rAF is outstanding at a time and it is always cancelled on the way out. The
 * tail is a damped first-order catch-up that is given a bounded number of
 * milliseconds after the last input and then stops, so a settled page costs
 * nothing and there is no loop that can outlive the route.
 */
export function startScrollStudies(options: StudiesOptions): Studies {
  const now = options.now ?? (() => performance.now());
  const requestFrame = options.requestFrame ?? ((callback: () => void) => window.requestAnimationFrame(() => callback()));
  const cancelFrame = options.cancelFrame ?? ((handle: number) => window.cancelAnimationFrame(handle));
  const budget = options.settle ?? STUDIES_SETTLE_MS;
  /** A hard frame cap, so a clock that never advances still cannot loop for ever. */
  const maxFrames = 90;

  let nodes: readonly HTMLElement[] = [];
  let targets: number[] = [];
  let painted: number[] = [];
  let pending = 0;
  let frames = 0;
  let quietUntil = 0;
  let disposed = false;
  let dominant = -1;

  const release = () => { if (pending) { cancelFrame(pending); pending = 0; } };

  /** One measurement of the page: which figure is in focus, and how far along it is. */
  const measure = () => {
    nodes = options.find();
    const viewportHeight = options.viewport();
    const boxes = nodes.map(node => { const rect = node.getBoundingClientRect(); return { top: rect.top, height: rect.height }; });
    dominant = dominantBox(boxes, viewportHeight);
    // A figure that is not the one in focus is not moving at all, so it keeps the
    // progress it already has rather than being walked back to its rest state.
    targets = nodes.map((_, index) => (index === dominant ? studyProgress(boxes[index], viewportHeight) : (painted[index] ?? 0)));
  };

  const write = (values: readonly number[]) => {
    nodes.forEach((node, index) => {
      if (index === dominant && painted[index] !== values[index]) paint(node, values[index] ?? 0);
    });
    painted = [...values];
  };

  const frame = () => {
    pending = 0;
    if (disposed || document.visibilityState === 'hidden') return;
    if (options.reducedMotion()) { settle(); return; }
    frames += 1;
    measure();
    const next = nodes.map((_, index) => {
      const from = painted[index] ?? targets[index] ?? 0;
      return from + ((targets[index] ?? 0) - from) * CATCH_UP;
    });
    write(next);
    const settled = next.every((value, index) => Math.abs(value - (targets[index] ?? 0)) < REST);
    if (settled || frames >= maxFrames || now() >= quietUntil) { write(targets); return; }
    pending = requestFrame(frame);
  };

  const wake = () => {
    if (disposed) return;
    if (document.visibilityState === 'hidden') { release(); return; }
    if (options.reducedMotion()) { settle(); return; }
    quietUntil = now() + budget;
    frames = 0;
    release();
    pending = requestFrame(frame);
  };
  /** Reduced motion and a hidden page both land here: the complete static drawing. */
  const settle = () => {
    release();
    for (const node of options.find()) rest(node);
    nodes = [];
    painted = [];
  };

  const scroll = () => wake();
  const preference = () => { if (options.reducedMotion() || document.visibilityState === 'hidden') settle(); else wake(); };
  window.addEventListener('scroll', scroll, { passive: true });
  window.addEventListener('resize', scroll);
  document.addEventListener('visibilitychange', preference);
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
  media?.addEventListener?.('change', preference);
  // Install static geometry once; offscreen figures receive no frame writes.
  if (document.visibilityState !== 'hidden') for (const node of options.find()) rest(node);
  wake();

  return {
    update: wake,
    dispose() {
      if (disposed) return;
      disposed = true;
      release();
      window.removeEventListener('scroll', scroll);
      window.removeEventListener('resize', scroll);
      document.removeEventListener('visibilitychange', preference);
      media?.removeEventListener?.('change', preference);
      for (const node of nodes) rest(node);
      nodes = [];
    },
  };
}

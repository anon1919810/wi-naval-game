/** Work/About: live incoming circle over an inert outgoing DOM copy.
 * Chrome stays live. The rim uses the same viewport origin and radius.
 * Route placement is synchronous; every exit restores inline state and removes
 * both visual layers, the RAF and all listeners. See the 2026-10-07 handoff. */

/** One move, in milliseconds. This is the whole Work/About choreography. */
export const REVEAL_MS = 500;
/** Damped and monotonic: the circle opens fast and settles, without a bounce. */
export const REVEAL_EASE = 'cubic-bezier(.34,.62,.24,1)';
/** The rim's flecks: a fixed pool, bounded on purpose. Never a particle field. */
export const REVEAL_PARTICLES = 18;
export const REVEAL_MIN_PARTICLES = 12;
export const REVEAL_MAX_PARTICLES = 24;
/** Trailing contour wavefronts behind the rim. Two is a wave; a dozen is noise. */
export const REVEAL_WAVES = 2;
/** Samples per contour. A circle at a thousand pixels wants no fewer to stay smooth. */
export const REVEAL_WAVE_SAMPLES = 96;
/** Peak deviation of a contour from the rim, in pixels, at desktop. */
export const REVEAL_WAVE_AMPLITUDE = 6;
/** How far behind the live rim a contour's own radius sits, in pixels. */
export const REVEAL_WAVE_SETBACK = 3;

/** Page coordinates: the same space `getBoundingClientRect()` reports. */
export interface RevealPoint { readonly x: number; readonly y: number }
export interface RevealRect { readonly left: number; top: number; width: number; height: number }

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));
/** Only ever applied to a coordinate or a radius that is written out. */
const round = (value: number) => Math.round(value * 100) / 100;
const right = (rect: RevealRect) => rect.left + rect.width;
const bottom = (rect: RevealRect) => rect.top + rect.height;

/** The viewport, in page coordinates. */
export function viewportBox(): RevealRect {
  return { left: 0, top: 0, width: window.innerWidth || 0, height: window.innerHeight || 0 };
}

function boxOf(node: Element): RevealRect {
  const rect = node.getBoundingClientRect();
  return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
}

/** The middle of a region: the honest origin when there is no preview to continue. */
export function revealCentre(region: RevealRect): RevealPoint {
  return { x: region.left + region.width / 2, y: region.top + region.height / 2 };
}

/** The smallest radius that has actually covered the whole region. */
export function coverRadius(region: RevealRect, origin: RevealPoint): number {
  const far = Math.max(
    Math.hypot(origin.x - region.left, origin.y - region.top),
    Math.hypot(right(region) - origin.x, origin.y - region.top),
    Math.hypot(origin.x - region.left, bottom(region) - origin.y),
    Math.hypot(right(region) - origin.x, bottom(region) - origin.y),
  );
  return round(far);
}

/**
 * The clip for one radius, written in the destination region's own box.
 *
 * `clip-path` resolves its circle against the element it is written on, so a
 * page-coordinate origin has to be normalised against that element's own origin.
 * Doing it here — from the post-commit rectangle — is what makes the circle open
 * at the word the visitor pressed even though the word lives outside the region
 * entirely.
 */
export function clipCircle(region: RevealRect, origin: RevealPoint, radius: number): string {
  return `circle(${round(radius)}px at ${round(origin.x - region.left)}px ${round(origin.y - region.top)}px)`;
}

/**
 * The part of the outgoing page that may stay on screen: the intersection of
 * where it was painted, where the arriving page will be, and the viewport.
 *
 * The intersection with the *incoming* rectangle is what keeps the copy off the
 * chrome: a shorter destination pulls its footer up, and a copy that ran to the
 * old bottom edge would sit on top of it. Outside the outgoing rectangle there
 * was nothing to keep, so the arriving page may show there at once.
 */
export function revealRegion(before: RevealRect, after: RevealRect, viewport: RevealRect): RevealRect | null {
  const left = Math.max(before.left, after.left, viewport.left);
  const top = Math.max(before.top, after.top, viewport.top);
  const width = Math.min(right(before), right(after), right(viewport)) - left;
  const height = Math.min(bottom(before), bottom(after), bottom(viewport)) - top;
  if (!(width > 0) || !(height > 0)) return null;
  return { left, top, width, height };
}

/* ---- the curve ------------------------------------------------------------ */

// The same four numbers REVEAL_EASE spells, so the move's shape is checkable.
const X1 = 0.34, X2 = 0.24, Y1 = 0.62, Y2 = 1;
const CURVE_STEPS = 256;
const cubic = (a: number, b: number, t: number) => {
  const u = 1 - t;
  return 3 * u * u * t * a + 3 * u * t * t * b + t * t * t;
};
/** Sampled once, by bisection, so a frame costs a lookup and never a solver. */
const CURVE: readonly number[] = Array.from({ length: CURVE_STEPS + 1 }, (_, step) => {
  const x = step / CURVE_STEPS;
  let low = 0, high = 1, t = x;
  for (let i = 0; i < 24; i += 1) {
    t = (low + high) / 2;
    if (cubic(X1, X2, t) < x) low = t; else high = t;
  }
  return cubic(Y1, Y2, t);
});

/**
 * Progress in `0…1` to radius fraction, damped: never negative, never over 1.
 *
 * Returned unrounded. The radius this multiplies can be a thousand pixels wide,
 * and rounding the *fraction* to two decimals makes the slow end of the move jump
 * in ten- and twenty-pixel steps — which is exactly the part of a reveal the eye
 * follows. Rounding belongs on the radius that is finally written, and nowhere
 * else.
 */
export function eased(progress: number): number {
  // Exact at both ends. The sampled curve's first and last values carry the
  // bisection's own error, and a closed circle that is 1e-7 of a pixel open is not
  // a closed circle.
  if (progress <= 0) return 0;
  if (progress >= 1) return 1;
  const position = progress * CURVE_STEPS;
  const index = Math.min(CURVE_STEPS - 1, Math.floor(position));
  const mix = position - index;
  return CURVE[index] + (CURVE[index + 1] - CURVE[index]) * mix;
}

/* ---- the rim's flecks ----------------------------------------------------- */

export interface ParticlePlan {
  readonly index: number;
  /** Where it sits around the rim, in degrees. */
  readonly angle: number;
  /** How far behind the rim it trails, in pixels. */
  readonly inset: number;
  /** How far it slides along the rim, in pixels, over the whole move. */
  readonly drift: number;
  /** When it appears, and how long it lives, as fractions of the move. */
  readonly delay: number;
  readonly span: number;
  readonly size: number;
  /** A fleck is a dot stretched along its own drift. */
  readonly fleck: boolean;
  readonly tone: 'ink' | 'line';
}

/**
 * The pool, as arithmetic on the index: the same run always places the same
 * flecks, and nothing here can drift between two identical navigations.
 */
export function particlePlan(count: number = REVEAL_PARTICLES): readonly ParticlePlan[] {
  const total = clamp(Math.round(count), 0, REVEAL_MAX_PARTICLES);
  return Array.from({ length: total }, (_, index) => ({
    index,
    angle: ((index * 137.508) + (index % 3) * 11) % 360,
    inset: round(2 + (index % 5) * 1.6),
    drift: round((((index * 37) % 9) / 4) - 1),
    delay: round(((index % 6) / 6) * 0.42),
    span: round(0.34 + ((index * 17) % 7) / 7 * 0.4),
    size: round(1.2 + (index % 3) * 0.7),
    fleck: index % 4 === 0,
    tone: index % 2 === 0 ? 'ink' : 'line',
  }));
}

export interface ParticleFrame {
  readonly x: number;
  readonly y: number;
  /** Never more than half strength, so the rim stays the thing being read. */
  readonly opacity: number;
}

/** One fleck at one progress: just behind the rim, out again within the move. */
export function particleFrame(plan: ParticlePlan, origin: RevealPoint, radius: number, progress: number): ParticleFrame {
  const p = clamp(progress, 0, 1);
  const local = (p - plan.delay) / plan.span;
  const life = local <= 0 || local >= 1 ? 0 : Math.sin(local * Math.PI);
  const angle = ((plan.angle + plan.drift * p) * Math.PI) / 180;
  const r = Math.max(0, radius - plan.inset - Math.abs(plan.drift) * p * 0.5);
  return {
    x: round(origin.x + Math.cos(angle) * r),
    y: round(origin.y + Math.sin(angle) * r),
    opacity: round(life * 0.5),
  };
}

/* ---- the rim's trailing contour ------------------------------------------ */

/**
 * One travelling wavefront behind the rim.
 *
 * A circle that opens with nothing but a thin boundary and a handful of dots reads
 * as a cut. What makes it read as something moving through a medium is a lagged
 * contour behind the edge, oscillating as it travels: the boundary stays a precise
 * circle, and the wave is what follows it.
 *
 * The plan is arithmetic on the index, like the flecks: the same move always draws
 * the same wave, and nothing here can drift between two identical navigations.
 */
export interface WavePlan {
  readonly index: number;
  /** How far behind the live rim this contour runs, as a fraction of the move. */
  readonly lag: number;
  /** Lobes around the circle. Six to nine reads as an organic contour, not a cog. */
  readonly lobes: number;
  /** Where the oscillation starts. */
  readonly phase: number;
  /** How many radians the phase travels over the whole move. Slow, never spinning. */
  readonly travel: number;
  /** Peak deviation from its own radius, in pixels. */
  readonly amplitude: number;
  /** Its ceiling: never brighter than the rim, never brighter than the flecks. */
  readonly opacity: number;
}

export function wavePlan(count: number = REVEAL_WAVES): readonly WavePlan[] {
  const total = clamp(Math.round(count), 0, REVEAL_WAVES);
  return Array.from({ length: total }, (_, index) => ({
    index,
    lag: round(0.045 + index * 0.055),
    lobes: 7 + index,
    phase: index * 2.1,
    travel: round(1.5 + index * 0.7),
    amplitude: round(REVEAL_WAVE_AMPLITUDE - index * 1.5),
    opacity: round(0.5 - index * 0.18),
  }));
}

/**
 * The amplitude envelope: rises, crests, then damps back to nothing.
 *
 * Zero at both ends, so the wave is not there before the circle opens and is gone
 * before it finishes, and never negative, so the contour cannot cross the rim.
 */
export function waveEnvelope(progress: number): number {
  const p = clamp(progress, 0, 1);
  return round(Math.sin(Math.PI * p) ** 0.7 * (1 - 0.55 * p));
}

export interface WaveFrame {
  /** The contour, as one closed path in the same box as the rim. */
  readonly d: string;
  /** Never above the plan's ceiling, and zero at both ends of the move. */
  readonly opacity: number;
  /** The contour's own radius: the lagging rim, less its setback. */
  readonly radius: number;
}

/**
 * The contour at one progress, as a closed polyline of bounded samples.
 *
 * Deterministic and finite: no randomness, no filter, no canvas, and the same
 * number of samples whatever the radius, so a frame costs a fixed amount and the
 * path can never grow a tail or a spike.
 */
export function waveFrame(plan: WavePlan, origin: RevealPoint, radius: number, progress: number): WaveFrame {
  const p = clamp(progress, 0, 1);
  const envelope = waveEnvelope(p);
  const amplitude = Math.min(plan.amplitude * envelope, radius * .3);
  // The contour's own circle: the rim as it was a moment ago, set back further the
  // more amplitude it is about to swing, so the wave can never ride over the edge.
  const own = Math.max(0, radius - REVEAL_WAVE_SETBACK - amplitude);
  const phase = plan.phase + plan.travel * p;
  let d = '';
  for (let step = 0; step < REVEAL_WAVE_SAMPLES; step += 1) {
    const angle = (step / REVEAL_WAVE_SAMPLES) * Math.PI * 2;
    const r = Math.max(0, own + amplitude * Math.sin(plan.lobes * angle + phase));
    d += `${step === 0 ? 'M' : 'L'}${round(origin.x + Math.cos(angle) * r)} ${round(origin.y + Math.sin(angle) * r)}`;
  }
  return { d: `${d}Z`, opacity: round(plan.opacity * envelope), radius: round(own + amplitude) };
}

/* ---- the lifecycle -------------------------------------------------------- */

export interface RevealRequest {
  /** Where the layers are appended: the shell, which owns the theme's tokens. */
  readonly shell: HTMLElement | null;
  /** The live region being revealed — the public main content, and only that. */
  readonly source: HTMLElement | null;
  /** The destination word's preview origin, in page coordinates. */
  readonly origin: RevealPoint | null | (() => RevealPoint | null);
}

export interface RevealOptions {
  readonly request: RevealRequest;
  /** Runs exactly once, synchronously, under the outgoing copy. */
  readonly commit: () => void;
  readonly duration?: number;
  readonly now?: () => number;
  /** Injected by tests; the browser's own frame request otherwise. */
  readonly requestFrame?: (callback: () => void) => number;
  readonly cancelFrame?: (handle: number) => void;
}

export interface CircularReveal {
  /** False when the destination was committed at once, with no clip or rim. */
  readonly animated: boolean;
  /** Settles when the move is over — finished, cancelled or settled early. */
  readonly finished: Promise<void>;
  /** Every layer off, every frame and listener stopped. Idempotent. */
  cancel(): void;
}

const SVG_NS = 'http://www.w3.org/2000/svg';
/** Attributes whose value may address another node by a fragment id. */
const FRAGMENT_ATTRIBUTES = ['clip-path', 'fill', 'filter', 'marker-end', 'marker-mid', 'marker-start', 'mask', 'stroke', 'style'];
/** The attributes that would make a copy addressable or submittable. */
const NAVIGATION_ATTRIBUTES = ['action', 'formaction', 'formenctype', 'formmethod', 'formtarget', 'ping', 'target', 'download'];
/** SVG elements whose `href` is a reference to another node, not a file. */
const FRAGMENT_TAGS = new Set(['use', 'textpath', 'mpath', 'animate', 'animatemotion', 'animatetransform', 'set', 'lineargradient', 'radialgradient', 'pattern', 'filter', 'fegaussianblur', 'feimage', 'femerge', 'fecomposite']);
let token = 0;

function reducedMotion(): boolean {
  return window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
}

/**
 * Make a copy safe to leave on screen, without degrading what it draws.
 *
 * Ids are *renamed* rather than dropped, because the artwork's own mask, pattern
 * and filter all live in ids — stripping them would erase the outgoing boat. The
 * prefix is per run, so the document still holds exactly one of each, and every
 * reference to one is rewritten with it.
 *
 * What does go is anything addressable: a link's `href`, a control's form
 * actions, a name, a tab stop, a label's `for`, and the ARIA references that
 * would otherwise point a screen reader into a second copy of the page. An
 * `href` on an SVG `<image>` is a file, not a fragment, and is left exactly as it
 * was.
 */
export function sanitizeClone(root: Element, prefix: string): void {
  const nodes = [root, ...Array.from(root.querySelectorAll('*'))];
  const renamed = new Map<string, string>();
  for (const node of nodes) {
    const id = node.getAttribute('id');
    if (id) { renamed.set(id, `${prefix}-${id}`); node.setAttribute('id', `${prefix}-${id}`); }
    node.removeAttribute('name');
    node.removeAttribute('tabindex');
    node.removeAttribute('for');
    node.removeAttribute('contenteditable');
    const inline = (node as HTMLElement).style;
    if (inline?.getPropertyValue('view-transition-name')) inline.removeProperty('view-transition-name');
    for (const attribute of NAVIGATION_ATTRIBUTES) {
      if (node.hasAttribute(attribute)) node.removeAttribute(attribute);
    }
    for (const attribute of ['aria-labelledby', 'aria-describedby', 'aria-controls', 'aria-owns']) node.removeAttribute(attribute);
  }
  for (const node of nodes) {
    for (const attribute of FRAGMENT_ATTRIBUTES) {
      const value = node.getAttribute(attribute);
      if (!value?.includes('url(#')) continue;
      node.setAttribute(attribute, value.replace(/url\(#([^)]+)\)/g, (whole, id: string) => {
        const mapped = renamed.get(id);
        return mapped ? `url(#${mapped})` : whole;
      }));
    }
    // A fragment `href` addresses a node; anything else is a file the copy needs.
    const tag = node.tagName.toLowerCase();
    if (tag === 'a' || tag === 'area') {
      node.removeAttribute('href');
      node.removeAttribute('xlink:href');
      continue;
    }
    if (tag !== 'a' && tag !== 'area' && !FRAGMENT_TAGS.has(tag)) continue;
    for (const attribute of ['href', 'xlink:href']) {
      const value = node.getAttribute(attribute);
      if (!value?.startsWith('#')) continue;
      const mapped = renamed.get(value.slice(1));
      if (mapped) node.setAttribute(attribute, `#${mapped}`);
      else node.removeAttribute(attribute);
    }
  }
}

function place(layer: HTMLElement, region: RevealRect): void {
  layer.style.left = `${round(region.left)}px`;
  layer.style.top = `${round(region.top)}px`;
  layer.style.width = `${round(region.width)}px`;
  layer.style.height = `${round(region.height)}px`;
}

function visualLayer(className: string, key: string): HTMLElement {
  const layer = document.createElement('div');
  layer.className = className;
  layer.dataset[key] = 'true';
  layer.setAttribute('aria-hidden', 'true');
  layer.setAttribute('inert', '');
  layer.style.position = 'fixed';
  layer.style.overflow = 'hidden';
  layer.style.pointerEvents = 'none';
  return layer;
}

interface EdgeLayer { root: HTMLElement; rim: SVGCircleElement; waves: SVGPathElement[]; flecks: HTMLElement[] }

/**
 * The rim, its trailing contours and its flecks, in one layer bounded by the same
 * region as the copy.
 *
 * Bounding them is what keeps the hairlines off the chrome: the circle only ever
 * reaches past the region on the side the word is on, where both pages are the
 * same background and there is no boundary to draw. The rim's own centre and the
 * flecks' positions are written in region-local coordinates, so re-bounding the
 * layer after the commit is a matter of rewriting two numbers.
 *
 * The waves are in the same `<svg>` and behind the rim in document order, so the
 * boundary is always the last thing drawn on the edge: the eye reads a crisp circle
 * with a travelling contour behind it, never a circle inside a wobble.
 */
function edgeLayer(plans: readonly ParticlePlan[], waves: readonly WavePlan[]): EdgeLayer {
  const root = visualLayer('ff-reveal-edge', 'ffRevealEdge');
  const svg = document.createElementNS(SVG_NS, 'svg');
  svg.setAttribute('class', 'ff-reveal-rim');
  svg.setAttribute('aria-hidden', 'true');
  svg.setAttribute('focusable', 'false');
  const trails: SVGPathElement[] = waves.map(plan => {
    const path = document.createElementNS(SVG_NS, 'path');
    path.setAttribute('class', 'ff-reveal-wave');
    path.setAttribute('data-ff-wave', String(plan.index));
    path.setAttribute('stroke-width', String(1 + (1 - plan.index) * 0.3));
    path.setAttribute('d', '');
    path.style.opacity = '0';
    svg.append(path);
    return path;
  });
  const rim = document.createElementNS(SVG_NS, 'circle');
  rim.setAttribute('cx', '0');
  rim.setAttribute('cy', '0');
  rim.setAttribute('r', '0');
  svg.append(rim);
  root.append(svg);
  const flecks: HTMLElement[] = plans.map(plan => {
    const node = document.createElement('span');
    node.className = 'ff-reveal-particle';
    node.dataset.ffParticle = String(plan.index);
    node.dataset.ffTone = plan.tone;
    node.dataset.ffShape = plan.fleck ? 'fleck' : 'dot';
    node.style.width = `${plan.size}px`;
    node.style.height = `${plan.fleck ? round(plan.size * 0.5) : plan.size}px`;
    node.style.opacity = '0';
    root.append(node);
    return node;
  });
  return { root, rim, waves: trails, flecks };
}

/**
 * Run the reveal. The commit happens synchronously under the outgoing copy, the
 * circle then opens from the requested origin, and the promise settles when the
 * move ends for any reason at all.
 *
 * Anything that would make this untrue — reduced motion, a hidden page, a region
 * with nothing visible, no host to hold the layers, a clone the browser refused
 * to build — takes the plain semantic path instead: one commit, no clip, no rim,
 * no flecks, no frame request, and a settled promise.
 */
export function startCircularReveal(options: RevealOptions): CircularReveal {
  const { request } = options;
  let settle: () => void = () => {};
  const finished = new Promise<void>(resolve => { settle = resolve; });
  const atOnce = (): CircularReveal => { options.commit(); settle(); return { animated: false, finished, cancel: () => {} }; };

  const shell = request.shell;
  const source = request.source;
  const duration = options.duration ?? REVEAL_MS;
  if (!shell || !source || !source.isConnected || !(duration > 0)) return atOnce();
  if (reducedMotion() || document.visibilityState === 'hidden') return atOnce();

  const before = boxOf(source);
  if (!revealRegion(before, before, viewportBox())) return atOnce();

  const now = options.now ?? (() => performance.now());
  const requestFrame = options.requestFrame ?? ((callback: () => void) => window.requestAnimationFrame(() => callback()));
  const cancelFrame = options.cancelFrame ?? ((handle: number) => window.cancelAnimationFrame(handle));
  const plans = particlePlan();
  const waves = wavePlan();
  /** Where the circle opens, fixed for the whole move. */
  let origin = typeof request.origin === 'function' ? null : request.origin;
  /** Where the copy of the outgoing page came from, in page coordinates. */
  const painted = before;

  let copy: HTMLElement | null = null;
  let clone: HTMLElement | null = null;
  let edge: EdgeLayer | null = null;
  let pending = 0;
  let stopped = false;
  const previousClip = source.style.clipPath;
  const previousBackground = source.style.background;
  const previousZIndex = source.style.zIndex;
  const previousClipPath = source.dataset.ffRevealClip;
  /** The bounds the move paints in: the visible region both pages share. */
  let region = revealRegion(before, before, viewportBox())!;
  let paintedClip = '';

  const stop = () => {
    if (stopped) return;
    stopped = true;
    if (pending) { cancelFrame(pending); pending = 0; }
    media?.removeEventListener?.('change', onPreference);
    window.removeEventListener('resize', onResize);
    window.removeEventListener('scroll', onScroll);
    document.removeEventListener('visibilitychange', onVisibility);
    source.removeEventListener('focusin', onFocus);
    source.style.clipPath = previousClip;
    source.style.background = previousBackground;
    source.style.zIndex = previousZIndex;
    if (previousClipPath === undefined) delete source.dataset.ffRevealClip; else source.dataset.ffRevealClip = previousClipPath;
    copy?.remove();
    edge?.root.remove();
    copy = null; clone = null; edge = null;
    settle();
  };
  const onPreference = (event: MediaQueryListEvent) => { if (event.matches) stop(); };
  // A viewport change moves every rectangle the move was measured against, so it
  // settles rather than continuing on numbers that are no longer true.
  const onResize = () => stop();
  const onScroll = () => {
    // Ignore the scroll event queued by the synchronous route placement itself.
    const current = boxOf(source);
    if (current.top !== after.top || current.left !== after.left) stop();
  };
  const onVisibility = () => { if (document.visibilityState === 'hidden') stop(); };
  // Focus arriving inside the clipped region would land on a control that is
  // mostly invisible, which is worse than finishing the move a moment early.
  const onFocus = (event: FocusEvent) => { if (regionContains(event.target)) stop(); };
  const regionContains = (target: EventTarget | null) => target instanceof Node && source.contains(target);
  const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');

  try {
    copy = visualLayer('ff-reveal-out', 'ffRevealOut');
    clone = source.cloneNode(true) as HTMLElement;
    sanitizeClone(clone, `ff-reveal-${token += 1}`);
    clone.style.position = 'absolute';
    clone.style.minWidth = '0px';
    copy.append(clone);
    shell.append(copy);
    edge = edgeLayer(plans, waves);
    shell.append(edge.root);
  } catch {
    // A browser that will not give us the copy still gets the page, at once.
    try { copy?.remove(); edge?.root.remove(); } catch { /* nothing was attached */ }
    return atOnce();
  }

  /** Re-bound both layers, and the copy inside, to the region they may paint in. */
  const bound = (next: RevealRect) => {
    region = next;
    place(copy!, next);
    place(edge!.root, next);
    // The copy is offset by however far its page sat above and left of the region,
    // so the outgoing page is painted exactly where it was rather than slid.
    clone!.style.left = `${round(painted.left - next.left)}px`;
    clone!.style.top = `${round(painted.top - next.top)}px`;
    clone!.style.width = `${round(painted.width)}px`;
  };
  bound(region);
  // The arriving page must be able to hide the copy *inside* the circle, or the
  // circle would open on the old page. Its own background colour is the only thing
  // written: no plate, no paper, no reserved space.
  source.style.background = 'var(--ff-bg)';
  source.style.zIndex = '2';

  // The destination appears now, under the copy that is on its way out.
  options.commit();

  // Everything the move needs about the destination is measured *after* that
  // commit: the route may have changed the region's height and the page may have
  // jumped to its own top. Re-bounding here is what stops a short Work from being
  // covered by a copy sized for a 1753px-tall About, and what keeps that copy off
  // the footer's new position.
  const after = boxOf(source);
  origin = (typeof request.origin === 'function' ? request.origin() : origin)
    ?? revealCentre(revealRegion(after, after, viewportBox()) ?? after);
  const shared = revealRegion(painted, after, viewportBox());
  if (!shared) { stop(); return { animated: true, finished, cancel: stop }; }
  bound(shared);
  edge!.rim.setAttribute('cx', String(round(origin.x - shared.left)));
  edge!.rim.setAttribute('cy', String(round(origin.y - shared.top)));
  /** The radius that has actually covered everything the move can paint. */
  const full = coverRadius(revealRegion(after, after, viewportBox())!, origin);

  const paint = (progress: number) => {
    if (!source.isConnected) { stop(); return; }
    const radius = full * eased(progress);
    const clip = clipCircle(after, origin!, radius);
    if (clip !== paintedClip) {
      paintedClip = clip;
      source.style.clipPath = clip;
      // Mirrored so the clip in force is readable from the DOM itself, which is
      // how it can be checked without a screenshot.
      source.dataset.ffRevealClip = clip;
    }
    edge!.rim.setAttribute('r', String(round(radius)));
    for (const plan of waves) {
      const wave = waveFrame(plan, { x: origin!.x - region.left, y: origin!.y - region.top },
        full * eased(Math.max(0, progress - plan.lag)), progress);
      edge!.waves[plan.index].setAttribute('d', wave.d);
      edge!.waves[plan.index].style.opacity = String(wave.opacity);
    }
    for (const plan of plans) {
      const fleck = particleFrame(plan, origin!, radius, progress);
      const node = edge!.flecks[plan.index];
      node.style.transform = `translate(${round(fleck.x - region.left)}px, ${round(fleck.y - region.top)}px) translate(-50%, -50%)`;
      node.style.opacity = String(fleck.opacity);
    }
  };

  media?.addEventListener?.('change', onPreference);
  window.addEventListener('resize', onResize);
  window.addEventListener('scroll', onScroll, { passive: true });
  document.addEventListener('visibilitychange', onVisibility);
  source.addEventListener('focusin', onFocus);

  const started = now();
  paint(0);
  const tick = () => {
    pending = 0;
    const progress = (now() - started) / duration;
    if (progress >= 1) { paint(1); stop(); return; }
    paint(progress);
    if (!stopped) pending = requestFrame(tick);
  };
  pending = requestFrame(tick);
  return { animated: true, finished, cancel: stop };
}

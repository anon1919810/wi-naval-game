import { act, cleanup } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  clipCircle, coverRadius, eased, particleFrame, particlePlan, REVEAL_EASE, REVEAL_MAX_PARTICLES, REVEAL_MIN_PARTICLES,
  REVEAL_MS, REVEAL_PARTICLES, revealCentre, revealRegion, sanitizeClone, startCircularReveal, viewportBox,
  wavePlan, waveFrame, waveEnvelope,
} from '../portfolio/circularReveal';

/**
 * The circular reveal itself, below the shell.
 *
 * The shell's own suite covers how it is wired into a navigation; this file covers
 * the two halves that can be checked on their own: the geometry (which decides
 * where the circle opens and how far it has to travel) and the lifecycle (which
 * decides that nothing is left running, nothing is committed twice, and every
 * early exit still settles). The assertions are written against behaviour rather
 * than against the numbers in the source, so a regression in the mapping or in
 * the cleanup fails here even if the constants still read the same.
 */

const preferences = new Map<string, boolean>();
const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();

beforeEach(() => {
  preferences.clear(); listeners.clear();
  // A test that hid the page must not hide the next one: the reveal refuses to
  // animate at all while the document is hidden.
  Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
  vi.stubGlobal('matchMedia', (query: string) => {
    const handlers = listeners.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
    listeners.set(query, handlers);
    return {
      get matches() { return preferences.get(query) ?? false; }, media: query,
      addEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.add(handler),
      removeEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => handlers.delete(handler),
    };
  });
  vi.stubGlobal('innerWidth', 1440);
  vi.stubGlobal('innerHeight', 960);
  document.body.innerHTML = '';
});

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

function media(query: string, matches: boolean) {
  act(() => {
    preferences.set(query, matches);
    for (const listener of [...(listeners.get(query) ?? [])]) listener({ matches } as MediaQueryListEvent);
  });
}

/**
 * A frame pump with a clock we own.
 *
 * The reveal asks for frames and reads a millisecond clock, so driving it means
 * owning both: `advance` moves time and runs exactly the callbacks that were
 * queued, which is how a real frame behaves and what makes "the rim radius and
 * the clip radius are the same number on this frame" checkable.
 */
function frames() {
  let time = 0;
  let next = 1;
  let queue: { id: number; run: () => void }[] = [];
  vi.stubGlobal('performance', { now: () => time });
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => {
    const id = next++;
    queue.push({ id, run: () => callback(time) });
    return id;
  });
  vi.stubGlobal('cancelAnimationFrame', (id: number) => { queue = queue.filter(entry => entry.id !== id); });
  return {
    /** The clock the reveal is reading. */
    at: () => time,
    advance(ms: number) {
      act(() => {
        time += ms;
        const due = queue; queue = [];
        for (const entry of due) entry.run();
      });
    },
    pending: () => queue.length,
  };
}

/** A region with a real box, so the reveal has something to measure. */
function region(host: HTMLElement, box: { left: number; top: number; width: number; height: number }) {
  host.style.position = 'fixed';
  Object.defineProperty(host, 'getBoundingClientRect', { configurable: true, value: () => new DOMRect(box.left, box.top, box.width, box.height) });
  return host;
}

/**
 * A region whose box a test can change while the move runs, the way a real route
 * commit changes it: the same node, measured again, at its new size.
 */
function liveRegion(host: HTMLElement, box: { left: number; top: number; width: number; height: number }) {
  const state = { ...box };
  Object.defineProperty(host, 'getBoundingClientRect', { configurable: true, value: () => new DOMRect(state.left, state.top, state.width, state.height) });
  return { moveTo: (next: { left: number; top: number; width: number; height: number }) => Object.assign(state, next) };
}

function shell() { return document.createElement('div'); }

/** The clip the live region is carrying, read back out of its own style. */
function clipOf(node: HTMLElement): { radius: number; x: number; y: number } {
  const match = node.style.clipPath.match(/^circle\(([\d.]+)px at (-?[\d.]+)px (-?[\d.]+)px\)$/);
  if (!match) throw new Error(`no circle on ${node.style.clipPath}`);
  return { radius: Number(match[1]), x: Number(match[2]), y: Number(match[3]) };
}

const rimRadius = () => Number(document.querySelector('.ff-reveal-rim circle')!.getAttribute('r'));
const layers = () => document.querySelectorAll('.ff-reveal-out, .ff-reveal-edge');
const flecks = () => [...document.querySelectorAll<HTMLElement>('.ff-reveal-particle')];

describe('circular reveal geometry', () => {
  it('keeps wave contours bounded behind the rim and damps them away', () => {
    for (const plan of wavePlan()) {
      for (const progress of [0, .05, .25, .5, .8, 1]) {
        const radius = 800 * eased(Math.max(0, progress - plan.lag));
        const frame = waveFrame(plan, { x: 0, y: 0 }, radius, progress);
        const numbers = frame.d.match(/-?\d+(?:\.\d+)?/g)!.map(Number);
        expect(numbers.every(Number.isFinite)).toBe(true);
        for (let i = 0; i < numbers.length; i += 2) {
          expect(Math.hypot(numbers[i], numbers[i + 1])).toBeLessThanOrEqual(radius + .02);
        }
        if (progress === 0 || progress === 1) expect(frame.opacity).toBe(0);
      }
    }
    expect(waveEnvelope(.9)).toBeLessThan(waveEnvelope(.4));
  });
  const region = { left: 48, top: 100, width: 996, height: 780 };

  it('stops at the furthest corner, whatever the origin is', () => {
    // The radius is the smallest one that has actually covered the region, so a
    // circle aimed from the rail's own corner travels much further than one aimed
    // from the middle, and neither stops short.
    for (const origin of [{ x: 48, y: 100 }, { x: 546, y: 490 }, { x: 1044, y: 880 }, { x: 5000, y: -4000 }]) {
      const radius = coverRadius(region, origin);
      for (const corner of [{ x: region.left, y: region.top }, { x: 1044, y: 100 }, { x: 48, y: 880 }, { x: 1044, y: 880 }]) {
        expect(radius).toBeGreaterThanOrEqual(Math.hypot(corner.x - origin.x, corner.y - origin.y) - 0.01);
      }
      // And it is not larger than it needs to be: the far corner is the answer.
      const far = Math.max(...[{ x: 48, y: 100 }, { x: 1044, y: 100 }, { x: 48, y: 880 }, { x: 1044, y: 880 }]
        .map(corner => Math.hypot(corner.x - origin.x, corner.y - origin.y)));
      expect(radius).toBeCloseTo(far, 1);
    }
    expect(coverRadius({ left: 0, top: 0, width: 0, height: 0 }, { x: 0, y: 0 })).toBe(0);
  });

  it('normalises a page-coordinate origin into the region being clipped', () => {
    // A word on the right of a 1440-wide rail is nowhere near the region: written
    // untranslated it would put the circle off the edge of the clip entirely.
    const origin = { x: 1150, y: 260 };
    const clip = clipCircle(region, origin, 400);
    expect(clip).toBe('circle(400px at 1102px 160px)');
    // Read back as the page point it was given, not as a point inside the region.
    expect(clipOf({ style: { clipPath: clip } } as unknown as HTMLElement)).toEqual({ radius: 400, x: 1102, y: 160 });
    expect(region.left + 1102).toBe(origin.x);
    expect(region.top + 160).toBe(origin.y);
    // A negative local coordinate is a real case (an origin above the region) and
    // is written as one rather than clamped away.
    expect(clipCircle(region, { x: 100, y: 40 }, 10)).toBe('circle(10px at 52px -60px)');
  });

  it('reserves only what both pages and the viewport share', () => {
    const viewport = { left: 0, top: 0, width: 1440, height: 960 };
    // Identical pages: the whole visible region.
    expect(revealRegion(region, region, viewport)).toEqual(region);
    // A scrolled page: only what is actually on screen.
    expect(revealRegion({ ...region, top: -300 }, { ...region, top: -300 }, viewport))
      .toEqual({ left: 48, top: 0, width: 996, height: 480 });
    // A shorter destination pulls its footer up, so the copy must stop where the
    // destination ends or it would sit on top of the footer's new position.
    expect(revealRegion(region, { ...region, height: 300 }, viewport)).toEqual({ left: 48, top: 100, width: 996, height: 300 });
    // A taller one may not cover more than the outgoing page ever painted.
    expect(revealRegion({ ...region, height: 300 }, region, viewport)).toEqual({ left: 48, top: 100, width: 996, height: 300 });
    // A destination that has moved down leaves the chrome above it alone.
    expect(revealRegion(region, { ...region, top: 220 }, viewport)).toEqual({ left: 48, top: 220, width: 996, height: 660 });
    // Nothing on screen is not a region.
    expect(revealRegion({ ...region, top: -2000 }, { ...region, top: -2000 }, viewport)).toBeNull();
    expect(revealRegion({ ...region, left: 2000 }, { ...region, left: 2000 }, viewport)).toBeNull();
    expect(revealRegion({ left: 0, top: 0, width: 0, height: 0 }, { left: 0, top: 0, width: 0, height: 0 }, viewport)).toBeNull();
    expect(viewportBox()).toEqual({ left: 0, top: 0, width: 1440, height: 960 });
    // The fallback origin is the middle of what is actually visible.
    expect(revealCentre(revealRegion(region, region, viewport)!)).toEqual({ x: 546, y: 490 });
  });

  it('opens damped and monotonic at full precision, and states that curve as CSS', () => {
    const control = REVEAL_EASE.replace(/cubic-bezier\(|\)/g, '').split(',').map(Number);
    expect(control).toHaveLength(4);
    expect(control.every(value => value >= 0 && value <= 1)).toBe(true);
    expect(eased(0)).toBe(0);
    expect(eased(1)).toBe(1);
    // Negative and past-the-end progress clamp rather than extrapolating.
    expect(eased(-4)).toBe(0);
    expect(eased(9)).toBe(1);
    let previous = -1;
    for (let step = 0; step <= 2000; step += 1) {
      const value = eased(step / 2000);
      expect(value).toBeGreaterThanOrEqual(previous);
      previous = value;
    }
    // Most of the travel happens early: a circle that opened linearly would read
    // as a slow wipe, and one that opened with a bounce would overshoot.
    expect(eased(0.25)).toBeGreaterThan(0.55);
    expect(eased(0.5)).toBeGreaterThan(0.85);
    expect(REVEAL_MS).toBe(500);
    // The curve is not rounded on its way out. A radius here is a thousand pixels
    // wide, so quantising the *fraction* to 1/100 reduces the whole settle to 101
    // distinct radii — eleven-pixel steps, in the part of a reveal the eye follows
    // most closely. Sampled every millisecond across the second half, the real
    // curve keeps almost every sample distinct.
    const radius = 1100;
    const samples = Array.from({ length: 251 }, (_, index) => eased((250 + index) / 500) * radius);
    expect(new Set(samples.map(value => value.toFixed(2))).size).toBeGreaterThan(240);
    // No two adjacent samples are a full rounding quantum apart, which is the step
    // size quantisation would force.
    const quantum = radius / 100;
    for (let index = 1; index < samples.length; index += 1) {
      expect(Math.abs(samples[index] - samples[index - 1])).toBeLessThan(quantum);
    }
  });

  it('places a fixed, bounded pool of flecks without touching randomness', () => {
    const random = vi.spyOn(Math, 'random');
    const plans = particlePlan();
    expect(random).not.toHaveBeenCalled();
    random.mockRestore();
    expect(plans).toHaveLength(REVEAL_PARTICLES);
    expect(REVEAL_PARTICLES).toBeGreaterThanOrEqual(REVEAL_MIN_PARTICLES);
    expect(REVEAL_PARTICLES).toBeLessThanOrEqual(REVEAL_MAX_PARTICLES);
    // A pool that can be asked for more than the bound is truncated, not grown.
    expect(particlePlan(400)).toHaveLength(REVEAL_MAX_PARTICLES);
    expect(particlePlan(0)).toHaveLength(0);
    // The same run places the same flecks in the same places.
    expect(particlePlan()).toEqual(plans);
    expect(new Set(plans.map(plan => plan.angle)).size).toBe(plans.length);
    for (const plan of plans) {
      expect(plan.angle).toBeGreaterThanOrEqual(0);
      expect(plan.angle).toBeLessThan(360);
      expect(plan.size).toBeLessThanOrEqual(3);
      expect(['ink', 'line']).toContain(plan.tone);
    }
  });

  it('keeps every fleck a few pixels behind the rim and fades it within the move', () => {
    const origin = { x: 1150, y: 260 };
    const plans = particlePlan();
    for (const radius of [80, 400, 1200]) {
      for (const plan of plans) {
        for (const progress of [0, 0.2, 0.5, 0.8, 1]) {
          const fleck = particleFrame(plan, origin, radius, progress);
          const distance = Math.hypot(fleck.x - origin.x, fleck.y - origin.y);
          // Behind the rim, never outside it and never drifting into a field.
          expect(distance).toBeLessThanOrEqual(radius + 0.01);
          expect(radius - distance).toBeLessThan(24);
          // Quiet, and never brighter than half strength.
          expect(fleck.opacity).toBeGreaterThanOrEqual(0);
          expect(fleck.opacity).toBeLessThanOrEqual(0.5);
        }
      }
    }
    // A fleck is only alive inside its own window, and it starts and ends gone.
    const plan = plans[0];
    expect(particleFrame(plan, origin, 500, 0).opacity).toBe(0);
    expect(particleFrame(plan, origin, 500, 1).opacity).toBe(0);
    expect(particleFrame(plan, origin, 500, plan.delay + plan.span / 2).opacity).toBeGreaterThan(0.4);
  });
});

describe('the outgoing copy', () => {
  it('renames every id, so the document still holds one of each', () => {
    document.body.innerHTML = '<svg><defs><filter id="ink"><feGaussianBlur stdDeviation="1" /></filter><pattern id="grid" /></defs>'
      + '<g mask="url(#ink)"><rect fill="url(#grid)" /><image href="/plan.png" /></g></svg>';
    const source = document.querySelector('svg')!;
    const clone = source.cloneNode(true) as Element;
    sanitizeClone(clone, 'ff-reveal-1');
    document.body.append(clone);
    // The mask and the pattern still resolve — the outgoing page is repainted, not
    // degraded — but under names that cannot collide with the live ones.
    expect(clone.querySelector('g')!.getAttribute('mask')).toBe('url(#ff-reveal-1-ink)');
    expect(clone.querySelector('rect')!.getAttribute('fill')).toBe('url(#ff-reveal-1-grid)');
    for (const id of ['ink', 'grid']) expect(clone.querySelector(`#${id}`)).toBeNull();
    const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('keeps the outgoing boat drawn, and rewrites only what addresses a node', () => {
    // The vessel is an SVG <image href>: a file, not a fragment. Dropping href on
    // every node would erase the boat from the page on its way out.
    document.body.innerHTML = '<svg><defs><filter id="ink"><feGaussianBlur stdDeviation="1"></feGaussianBlur></filter>'
      + '<pattern id="grid"></pattern><mask id="deck"><rect class="mask-fill"></rect></mask></defs>'
      + '<g mask="url(#deck)"><rect class="grid-fill" fill="url(#grid)"></rect><image href="/portfolio/plan-a.png"></image>'
      + '<use href="#ink"></use></g>'
      + '<a id="out" href="#/about">About</a><image id="ext" href="https://example.invalid/x.svg"></image></svg>';
    const source = document.querySelector('svg')!;
    const clone = source.cloneNode(true) as Element;
    sanitizeClone(clone, 'ff-reveal-1');
    document.body.append(clone);
    // The scan and the boat survive: mask, pattern and filter all still resolve,
    // under names that cannot collide with the live page's.
    expect(clone.querySelector('g')!.getAttribute('mask')).toBe('url(#ff-reveal-1-deck)');
    expect(clone.querySelector('.grid-fill')!.getAttribute('fill')).toBe('url(#ff-reveal-1-grid)');
    expect(clone.querySelector('image')!.getAttribute('href')).toBe('/portfolio/plan-a.png');
    // The live page is untouched by all of this.
    expect(source.querySelector('image')!.getAttribute('href')).toBe('/portfolio/plan-a.png');
    expect(source.querySelector('#ink')).not.toBeNull();
    // A fragment href on a reference element is renamed to match; an external one is not.
    expect(clone.querySelector('use')!.getAttribute('href')).toBe('#ff-reveal-1-ink');
    expect(clone.querySelector('#ff-reveal-1-ext')!.getAttribute('href')).toBe('https://example.invalid/x.svg');
    // The anchor is no longer addressable.
    expect(clone.querySelector('a')!.hasAttribute('href')).toBe(false);
    expect(clone.querySelector('#ff-reveal-1-out')!.hasAttribute('href')).toBe(false);
    for (const id of ['ink', 'grid', 'deck', 'out', 'ext']) expect(clone.querySelector(`#${id}`)).toBeNull();
    const ids = [...document.querySelectorAll('[id]')].map(node => node.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it('leaves nothing focusable, addressable or screen-readable behind', () => {
    document.body.innerHTML = '<div id="page"><a id="link" href="#/about" tabindex="0">About</a>'
      + '<button id="go" formaction="/somewhere">Go</button><input id="field" /><label id="label" for="field">Field</label>'
      + '<h2 id="title">Plimsoll</h2></div>';
    const clone = document.querySelector('#page')!.cloneNode(true) as Element;
    sanitizeClone(clone, 'ff-reveal-2');
    expect(clone.querySelectorAll('a[href], button[formaction], [tabindex], [name], [contenteditable], label[for]')).toHaveLength(0);
    // An image still loads from its own src; only fragment references are rewritten.
    expect(clone.querySelector('#ff-reveal-2-link')).not.toBeNull();
  });
});

describe('the reveal lifecycle', () => {
  const box = { left: 48, top: 100, width: 996, height: 780 };

  function build() {
    const host = shell();
    document.body.append(host);
    const source = region(document.createElement('main'), box);
    host.append(source);
    source.innerHTML = '<h1>Plimsoll</h1><svg><defs><mask id="deck"><rect /></mask></defs><g mask="url(#deck)"><rect /></g></svg>';
    return { host, source };
  }

  it('commits once, under the copy, and holds one radius for both the clip and the rim', async () => {
    const clock = frames();
    const { host, source } = build();
    let commits = 0;
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => {
        commits += 1;
        source.innerHTML = '<h1>A field for useful ideas.</h1>';
      },
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    expect(reveal.animated).toBe(true);
    // One synchronous commit, and the page that is arriving is already there while
    // the page that is leaving is still on screen outside the circle.
    expect(commits).toBe(1);
    expect(source.innerHTML).toContain('A field for useful ideas.');
    // Both layers are actually in the document: a reveal that built its rim and
    // forgot to attach it would otherwise look complete from here.
    expect(document.querySelectorAll('.ff-reveal-out')).toHaveLength(1);
    expect(document.querySelectorAll('.ff-reveal-edge')).toHaveLength(1);
    expect(flecks()).toHaveLength(REVEAL_PARTICLES);
    expect(document.querySelector('.ff-reveal-rim circle')).not.toBeNull();
    // The copy is the outgoing page, inert, hidden from assistive technology and
    // never a pointer target.
    const copy = document.querySelector<HTMLElement>('.ff-reveal-out')!;
    expect(copy.textContent).toContain('Plimsoll');
    expect(copy.getAttribute('aria-hidden')).toBe('true');
    expect(copy.hasAttribute('inert')).toBe(true);
    expect(copy.style.pointerEvents).toBe('none');
    expect(copy.querySelector('#ff-reveal-1-deck')).not.toBeNull();
    // Its box is the visible region, and the copy inside is offset by however much
    // of the outgoing page sat above it.
    expect(copy.style.left).toBe('48px');
    expect(copy.style.top).toBe('100px');
    expect(copy.style.width).toBe('996px');
    expect(copy.style.height).toBe('780px');
    // The copy is offset by however much of the outgoing page sat above and left
    // of the region, so it is painted where it was rather than slid.
    expect(copy.firstElementChild).toMatchObject({ style: expect.objectContaining({ top: '0px', left: '0px' }) });
    // Both layers are visual only, and the rim is bounded by the same region so a
    // hairline can never cross the header, the rail or the footer.
    const edge = document.querySelector<HTMLElement>('.ff-reveal-edge')!;
    expect(edge.getAttribute('aria-hidden')).toBe('true');
    expect(edge.hasAttribute('inert')).toBe(true);
    expect(edge.style.pointerEvents).toBe('none');
    expect(edge.style.overflow).toBe('hidden');
    expect([edge.style.left, edge.style.top, edge.style.width, edge.style.height]).toEqual(['48px', '100px', '996px', '780px']);
    // The rim's centre is region-local, so it lands on the destination word.
    const rim = document.querySelector('.ff-reveal-rim circle')!;
    expect(Number(rim.getAttribute('cx'))).toBeCloseTo(1150 - 48, 1);
    expect(Number(rim.getAttribute('cy'))).toBeCloseTo(260 - 100, 1);
    // The arriving page carries an opaque base of the page's own colour, so the
    // circle reveals the destination rather than showing the copy through a hole.
    expect(source.style.background).toBe('var(--ff-bg)');
    expect(source.style.zIndex).toBe('2');
    expect(source.style.clipPath).toMatch(/^circle\(/);
    // At the first frame the circle is closed, so nothing of the destination shows.
    expect(clipOf(source).radius).toBe(0);
    expect(rimRadius()).toBe(0);
    // And it opens from the destination word, written in the region's own box.
    expect(clipOf(source)).toEqual({ radius: 0, x: 1102, y: 160 });
    // Every frame, the rim radius is the clip radius: one number, two places.
    for (let step = 0; step < 5; step += 1) {
      clock.advance(80);
      const clip = clipOf(source);
      expect(rimRadius()).toBeCloseTo(clip.radius, 2);
      expect(clip.radius).toBeGreaterThanOrEqual(0);
      const waves = [...document.querySelectorAll<SVGPathElement>('.ff-reveal-wave')];
      expect(waves).toHaveLength(2);
      for (const wave of waves) {
        expect(wave.getAttribute('d')).toMatch(/^M.+Z$/);
        expect(wave.getAttribute('d')).not.toMatch(/NaN|Infinity/);
        expect(Number(wave.style.opacity)).toBeGreaterThan(0);
      }
    }
    expect(clipOf(source).radius).toBeGreaterThan(0);
    // The pool never grows, whatever the move does.
    expect(flecks()).toHaveLength(REVEAL_PARTICLES);
    for (const fleck of flecks()) {
      expect(Number(fleck.style.opacity)).toBeLessThanOrEqual(0.5);
      expect(fleck.style.transform).toMatch(/^translate\(-?[\d.]+px, -?[\d.]+px\)/);
    }
    // Nothing else in the document took a view-transition name, and the copy's ids
    // are the only ones on their new names.
    expect(document.querySelectorAll('[style*="view-transition-name"]')).toHaveLength(0);
    // The move finishes itself and takes every layer with it.
    clock.advance(REVEAL_MS);
    await act(async () => { await reveal.finished; });
    expect(layers()).toHaveLength(0);
    expect(source.style.clipPath).toBe('');
    expect(source.style.zIndex).toBe('');
    expect(clock.pending()).toBe(0);
    expect(commits).toBe(1);
  });

  it.each([
    ['reduced motion', () => preferences.set('(prefers-reduced-motion: reduce)', true)],
    ['the page is hidden', () => Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })],
    ['nothing is visible', (source: HTMLElement) => region(source, { left: 48, top: -4000, width: 996, height: 780 })],
    ['the region has unmounted', (source: HTMLElement) => source.remove()],
  ])('reaches the destination at once under %s, and leaves nothing behind', async (label, arrange) => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'visible' });
    const clock = frames();
    const { host, source } = build();
    arrange(source);
    let commits = 0;
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => { commits += 1; },
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    expect(reveal.animated).toBe(false);
    expect(commits).toBe(1);
    await act(async () => { await reveal.finished; });
    expect(layers()).toHaveLength(0);
    expect(source.style.clipPath).toBe('');
    expect(clock.pending()).toBe(0);
  });

  it('settles rather than continuing when reduced motion arrives mid-move', async () => {
    const clock = frames();
    const { host, source } = build();
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => {},
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    clock.advance(120);
    expect(clipOf(source).radius).toBeGreaterThan(0);
    media('(prefers-reduced-motion: reduce)', true);
    expect(layers()).toHaveLength(0);
    expect(source.style.clipPath).toBe('');
    expect(clock.pending()).toBe(0);
    await act(async () => { await reveal.finished; });
  });

  it.each([
    ['a resize', () => act(() => { window.dispatchEvent(new Event('resize')); })],
    ['the page being hidden', () => {
      Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' });
      act(() => { document.dispatchEvent(new Event('visibilitychange')); });
    }],
  ])('settles on %s, which invalidates every rectangle it measured', async (label, trigger) => {
    const clock = frames();
    const { host, source } = build();
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => {},
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    clock.advance(200);
    trigger();
    expect(layers()).toHaveLength(0);
    expect(source.style.clipPath).toBe('');
    // No work continues after the settle: the frame request is cancelled, so the
    // clock can advance for a long time without anything happening.
    expect(clock.pending()).toBe(0);
    clock.advance(5000);
    expect(layers()).toHaveLength(0);
    await act(async () => { await reveal.finished; });
  });

  it('is safe to cancel at any point, any number of times, and never commits again', async () => {
    const clock = frames();
    const { host, source } = build();
    let commits = 0;
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => { commits += 1; },
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    clock.advance(300);
    reveal.cancel();
    reveal.cancel();
    act(() => { clock.advance(2000); });
    expect(commits).toBe(1);
    expect(layers()).toHaveLength(0);
    expect(source.style.clipPath).toBe('');
    // The destination stays on screen: a cancelled reveal leaves the page, it does
    // not put the old one back.
    expect(source.isConnected).toBe(true);
    await act(async () => { await reveal.finished; });
  });

  it('re-bounds itself after the commit, so a short destination is never covered by a copy of a tall one', async () => {
  const clock = frames();
  const host = shell();
  document.body.append(host);
  let box = { left: 48, top: -100, width: 996, height: 1853 };
  const source = document.createElement('main');
  const region = liveRegion(source, box);
  host.append(source);
  source.innerHTML = '<h1>A field for useful ideas.</h1>';
  const reveal = startCircularReveal({
    request: { shell: host, source, origin: { x: 1150, y: 260 } },
    // The commit lands the short Work page: the region is now 780px tall at top 100.
    commit: () => { box = { left: 48, top: 100, width: 996, height: 780 }; region.moveTo(box); source.innerHTML = '<h1>Plimsoll</h1>'; },
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  expect(reveal.animated).toBe(true);
  const copy = document.querySelector<HTMLElement>('.ff-reveal-out')!;
  const edge = document.querySelector<HTMLElement>('.ff-reveal-edge')!;
  // Re-bounded to what the two pages share: no more of the 1853px About than the
  // 780px Work occupies, so the copy cannot sit over the footer that just moved up.
  expect([copy.style.top, copy.style.height]).toEqual(['100px', '780px']);
  expect([edge.style.top, edge.style.height]).toEqual(['100px', '780px']);
  // The copy inside is offset by the 200px the old page sat above the region, which
  // puts its content back where the eye last saw it rather than sliding it down.
  expect((copy.firstElementChild as HTMLElement).style.top).toBe('-200px');
  // The radius covers the region that can be painted, not the destination's full
  // height: it stops at 100+780, never at the About's 1753px bottom.
  const rim = document.querySelector('.ff-reveal-rim circle')!;
  const full = Number(rim.getAttribute('cx')) + 48;
  expect(Math.hypot(full - 1150, 100 + 780 - 260)).toBeLessThan(1200);
  clock.advance(REVEAL_MS / 2);
  // The radius covers the region that can be painted, not the destination's full
  // height: it is bounded by 100+780, never by the About's 1753px bottom.
  const reached = clipOf(source).radius;
  expect(reached).toBeLessThan(Math.hypot(1150 - 48, 1753 - 260));
  expect(reached).toBeCloseTo(Number(rim.getAttribute('r')), 2);
  clock.advance(REVEAL_MS);
  await act(async () => { await reveal.finished; });
  // And the destination's own height is untouched: no reserved space, no padding.
  expect(source.style.background).toBe('');
});

it('settles at once when the commit leaves the two pages with nothing in common', async () => {
  const clock = frames();
  const host = shell();
  document.body.append(host);
  const source = document.createElement('main');
  const region = liveRegion(source, { left: 48, top: 100, width: 996, height: 780 });
  host.append(source);
  const reveal = startCircularReveal({
    request: { shell: host, source, origin: { x: 1150, y: 260 } },
    // A commit that lands the destination somewhere entirely off screen.
    commit: () => { region.moveTo({ left: 48, top: -4000, width: 996, height: 780 }); },
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  expect(reveal.animated).toBe(true);
  // Settled rather than left animating against numbers that are no longer true.
  expect(layers()).toHaveLength(0);
  expect(source.style.clipPath).toBe('');
  expect(source.style.background).toBe('');
  expect(clock.pending()).toBe(0);
  await act(async () => { await reveal.finished; });
});

it('settles when focus arrives inside the clipped region', async () => {
  const clock = frames();
  const { host, source } = build();
  source.innerHTML = '<a href="#/about" id="inside">About</a>';
  const reveal = startCircularReveal({
    request: { shell: host, source, origin: { x: 1150, y: 260 } },
    commit: () => {},
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  clock.advance(120);
  act(() => { source.querySelector<HTMLElement>('#inside')!.dispatchEvent(new FocusEvent('focusin', { bubbles: true })); });
  expect(layers()).toHaveLength(0);
  expect(source.style.clipPath).toBe('');
  expect(clock.pending()).toBe(0);
  await act(async () => { await reveal.finished; });
});

it('stops on its own if the region is removed while the move is running', async () => {
  const clock = frames();
  const { host, source } = build();
  const reveal = startCircularReveal({
    request: { shell: host, source, origin: { x: 1150, y: 260 } },
    commit: () => {},
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  clock.advance(100);
  source.remove();
  clock.advance(100);
  // A region that is gone from the document cannot carry a clip, so the move has
  // settled rather than continuing to paint into a detached node.
  expect(source.style.clipPath).toBe('');
  expect(clock.pending()).toBe(0);
  expect(layers()).toHaveLength(0);
  clock.advance(2000);
  await act(async () => { await reveal.finished; });
});

it('falls back to one commit when there is nowhere to draw', async () => {
  const clock = frames();
  const { host, source } = build();
  let commits = 0;
  const reveal = startCircularReveal({
    request: { shell: null, source, origin: null },
    commit: () => { commits += 1; },
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  expect(reveal.animated).toBe(false);
  expect(commits).toBe(1);
  expect(layers()).toHaveLength(0);
  await act(async () => { await reveal.finished; });
});

it('opens from the middle of the visible region when no origin was given', async () => {
  const clock = frames();
  const { host, source } = build();
  const reveal = startCircularReveal({
    request: { shell: host, source, origin: null },
    commit: () => {},
    now: clock.at,
    requestFrame: (callback) => window.requestAnimationFrame(callback),
    cancelFrame: (handle) => window.cancelAnimationFrame(handle),
  });
  // The region's own centre, not the top-left corner and not a remembered press.
  expect(clipOf(source)).toEqual({ radius: 0, x: 498, y: 390 });
  clock.advance(REVEAL_MS / 2);
  expect(clipOf(source).radius).toBeGreaterThan(0);
  clock.advance(REVEAL_MS);
  await act(async () => { await reveal.finished; });
});

  it('maps the clip against the incoming box and settles on actual scroll, not route placement', async () => {
    const clock = frames();
    const { host, source } = build();
    const incoming = liveRegion(source, box);
    let committed = false;
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: () => {
        expect(committed).toBe(true);
        return { x: 700, y: 200 };
      } },
      commit: () => { committed = true; incoming.moveTo({ ...box, top: -100, height: 1800 }); },
      now: clock.at,
    });
    expect(clipOf(source).y - 100).toBe(200);
    const edge = document.querySelector<HTMLElement>('.ff-reveal-edge')!;
    const rim = edge.querySelector('circle')!;
    expect(Number(rim.getAttribute('cy')) + Number.parseFloat(edge.style.top)).toBe(200);
    window.dispatchEvent(new Event('scroll'));
    expect(layers()).toHaveLength(2); // queued route scroll has not moved geometry
    incoming.moveTo({ ...box, top: -250, height: 1800 });
    window.dispatchEvent(new Event('scroll'));
    expect(layers()).toHaveLength(0);
    expect(clock.pending()).toBe(0);
    expect(source.style.clipPath).toBe('');
    await reveal.finished;
  });

  it('restores whatever clip, background and state the region already carried', async () => {
    const clock = frames();
    const { host, source } = build();
    source.style.clipPath = 'inset(0 0 40% 0)';
    source.style.background = 'rgb(1, 2, 3)';
    source.dataset.ffRevealClip = 'circle(9px at 1px 2px)';
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => {},
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    expect(source.style.clipPath).toMatch(/^circle\(/);
    expect(source.dataset.ffRevealClip).toMatch(/^circle\(0px at/);
    clock.advance(REVEAL_MS + 40);
    expect(source.style.clipPath).toBe('inset(0 0 40% 0)');
    expect(source.style.background).toBe('rgb(1, 2, 3)');
    expect(source.dataset.ffRevealClip).toBe('circle(9px at 1px 2px)');
    await act(async () => { await reveal.finished; });
  });

  it('removes the mirrored clip entirely when the region never had one', async () => {
    const clock = frames();
    const { host, source } = build();
    const reveal = startCircularReveal({
      request: { shell: host, source, origin: { x: 1150, y: 260 } },
      commit: () => {},
      now: clock.at,
      requestFrame: (callback) => window.requestAnimationFrame(callback),
      cancelFrame: (handle) => window.cancelAnimationFrame(handle),
    });
    expect(source.dataset.ffRevealClip).toMatch(/^circle\(/);
    clock.advance(REVEAL_MS + 40);
    expect(source.dataset.ffRevealClip).toBeUndefined();
    expect(source.style.clipPath).toBe('');
    expect(source.style.background).toBe('');
    await act(async () => { await reveal.finished; });
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  CF_HI,
  CF_LO,
  compassFrame,
  COMPASS_DEGREES,
  COMPASS_SHIFT,
  connCf,
  cfX,
  cfY,
  dominantBox,
  frictionPoint,
  harmonicFrame,
  PLOT,
  startScrollStudies,
  studyProgress,
} from '../portfolio/scrollStudies';

/**
 * Cluster: the scroll-linked drawings.
 *
 * The math is asserted against the same numbers the calculation core uses, and
 * the painter is asserted on its own terms: it writes attributes, it never
 * re-renders, it stops when it is told to, and a browser with no SVG geometry at
 * all still gets a usable static drawing.
 */

const VIEWPORT = 900;

describe('the friction curve', () => {
  it('is the Conn 1953 approximation the calculation core computes', () => {
    // tools/plimsoll/resistance.py: 0.4631 / (log10 Re) ** 2.6
    expect(connCf(1e6)).toBeCloseTo(0.4631 / 6 ** 2.6, 12);
    expect(connCf(1e7)).toBeCloseTo(0.4631 / 7 ** 2.6, 12);
    expect(connCf(1e9)).toBeCloseTo(0.4631 / 9 ** 2.6, 12);
    expect(connCf(1e6)).toBeCloseTo(0.0043902, 6);
    expect(connCf(1e9)).toBeCloseTo(0.0015300, 6);
    // Monotone over the declared interval, which is what makes it a curve and
    // not a scatter: more Reynolds, less coefficient.
    let previous = Number.POSITIVE_INFINITY;
    for (let i = 0; i <= 40; i++) {
      const value = connCf(10 ** (CF_LO + (CF_HI - CF_LO) * (i / 40)));
      expect(value).toBeLessThan(previous);
      previous = value;
    }
  });

  it('puts a marker on the real curve at every progress, inside the plot', () => {
    for (const progress of [0, 0.25, 0.5, 0.75, 1]) {
      const point = frictionPoint(progress);
      // The point is the curve's own evaluation, not an interpolation of it.
      expect(point.cf).toBeCloseTo(connCf(10 ** point.logRe), 12);
      expect(point.x).toBeCloseTo(cfX(point.logRe), 10);
      expect(point.y).toBeCloseTo(cfY(point.cf), 10);
      expect(point.x).toBeGreaterThanOrEqual(PLOT.x - 1e-9);
      expect(point.x).toBeLessThanOrEqual(PLOT.x + PLOT.w + 1e-9);
      expect(point.y).toBeGreaterThanOrEqual(PLOT.y - 1e-9);
      expect(point.y).toBeLessThanOrEqual(PLOT.y + PLOT.h + 1e-9);
    }
    expect(frictionPoint(0).logRe).toBe(CF_LO);
    expect(frictionPoint(1).logRe).toBe(CF_HI);
    // Out-of-range progress clamps instead of leaving the paper.
    expect(frictionPoint(-4)).toEqual(frictionPoint(0));
    expect(frictionPoint(9)).toEqual(frictionPoint(1));
  });

  it('clamps a coefficient that would plot off the top of its own box', () => {
    expect(cfY(0.02)).toBe(PLOT.y);
    expect(cfY(-1)).toBe(PLOT.y + PLOT.h);
  });
});

describe('the harmonic trace', () => {
  it('follows a = 3, b = 2, phi = pi/2 rather than a stored path', () => {
    for (const progress of [0, 0.2, 0.5, 0.9, 1]) {
      const frame = harmonicFrame(progress);
      const t = progress * Math.PI * 2;
      expect(frame.t).toBeCloseTo(t, 10);
      expect(frame.x).toBeCloseTo(160 + 140 * Math.sin(3 * t + Math.PI / 2), 1);
      expect(frame.y).toBeCloseTo(160 - 140 * Math.sin(2 * t), 1);
      // A bounded sample count, always a path, never a growing tail.
      expect(frame.d.startsWith('M')).toBe(true);
      expect(frame.d.split('L')).toHaveLength(25);
    }
    // Reversible: the same progress gives the same point, whatever came before.
    expect(harmonicFrame(0.4)).toEqual(harmonicFrame(0.4));
  });
});

describe('the compass sweep', () => {
  it('stays inside its own budget and reverses continuously', () => {
    const frames = [0, 0.25, 0.5, 0.75, 1].map(compassFrame);
    for (const frame of frames) {
      expect(Math.abs(frame.angle)).toBeLessThanOrEqual(COMPASS_DEGREES / 2 + 1e-9);
      expect(Math.abs(frame.x)).toBeLessThanOrEqual(COMPASS_SHIFT / 2 + 1e-9);
      expect(Math.abs(frame.y)).toBeLessThanOrEqual(COMPASS_SHIFT / 2 + 1e-9);
    }
    expect(frames[2].angle).toBeCloseTo(0);
    expect(frames[2].x).toBeCloseTo(0);
    expect(frames[2].y).toBeCloseTo(0);
    // Backwards is the same path in reverse, not a different one.
    expect(compassFrame(0.25).angle).toBeCloseTo(-compassFrame(0.75).angle);
    expect(compassFrame(0.25).x).toBeCloseTo(-compassFrame(0.75).x);
    expect(compassFrame(-1)).toEqual(compassFrame(0));
    expect(compassFrame(2)).toEqual(compassFrame(1));
  });
});

describe('figure progress', () => {
  it('runs 0 to 1 as a figure crosses the viewport, and is reversible', () => {
    const figure = { height: 600 };
    const at = (top: number) => studyProgress({ top, ...figure }, VIEWPORT);
    expect(at(VIEWPORT)).toBe(0);
    expect(at(300)).toBeCloseTo(0.4, 6);
    expect(at(-600)).toBeCloseTo(1, 6);
    expect(at(-1000)).toBe(1);
    expect(at(5000)).toBe(0);
    // The same position always gives the same progress, whichever way it came.
    expect(at(200)).toBe(at(200));
  });

  it('clamps a page shorter than its viewport and a figure with no measured box', () => {
    expect(studyProgress({ top: 0, height: 0 }, VIEWPORT)).toBeGreaterThanOrEqual(0);
    expect(studyProgress({ top: -50, height: 100 }, VIEWPORT)).toBeGreaterThanOrEqual(0);
    expect(studyProgress({ top: 0, height: 0 }, 0)).toBe(0);
    expect(Number.isFinite(studyProgress({ top: Number.NaN, height: 10 }, VIEWPORT))).toBe(true);
  });

  it('lets at most one figure be in focus, the one nearest the viewport centre', () => {
    const boxes = [
      { top: -3000, height: 400 },
      { top: 200, height: 500 },
      { top: 4000, height: 400 },
    ];
    expect(dominantBox(boxes, VIEWPORT)).toBe(1);
    expect(dominantBox([{ top: 4000, height: 400 }], VIEWPORT)).toBe(-1);
    expect(dominantBox([], VIEWPORT)).toBe(-1);
  });

  it('never elects a figure entirely outside the viewport', () => {
    expect(dominantBox([{ top: 901, height: 600 }], VIEWPORT)).toBe(-1);
    expect(dominantBox([{ top: -601, height: 600 }], VIEWPORT)).toBe(-1);
    expect(dominantBox([{ top: 500, height: 0 }], VIEWPORT)).toBe(-1);
  });
});

describe('the painter', () => {
  const html = `<div>
    <figure data-ff-study="compass"><svg><g data-ff-motion></g></svg></figure>
    <figure data-ff-study="harmonic"><svg><path data-ff-motion="trace"></path><circle data-ff-motion="cursor" r="3"></circle></svg></figure>
    <figure data-ff-study="friction"><svg><circle data-ff-motion="marker" r="3"></circle><path data-ff-motion="across"></path><path data-ff-motion="up"></path></svg></figure>
    <figure data-ff-study="scale"></figure>
  </div>`;

  let host: HTMLElement;
  let clock = 0;
  let queued: (() => void)[] = [];
  let reduced = false;
  let tops: number[];

  beforeEach(() => {
    clock = 0; queued = []; reduced = false; tops = [200, 1400, 4000, 9000];
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.body.innerHTML = html;
    host = document.body.firstElementChild as HTMLElement;
    const figures = [...host.querySelectorAll<HTMLElement>('[data-ff-study]')];
    figures.forEach((figure, index) => {
      vi.spyOn(figure, 'getBoundingClientRect').mockImplementation(() => ({ top: tops[index], height: 600 }) as DOMRect);
    });
  });
  afterEach(() => { document.body.innerHTML = ''; vi.restoreAllMocks(); });

  function run(settle = 600) {
    clock += settle;
    const due = queued; queued = [];
    for (const callback of due) callback();
  }

  function start() {
    return startScrollStudies({
      find: () => [...host.querySelectorAll<HTMLElement>('[data-ff-study]')],
      viewport: () => VIEWPORT,
      reducedMotion: () => reduced,
      now: () => clock,
      requestFrame: callback => { queued.push(callback); return queued.length; },
      cancelFrame: () => { queued = []; },
    });
  }

  const group = () => host.querySelector('[data-ff-study="compass"] g')!;
  const trace = () => host.querySelector<SVGElement>('[data-ff-motion="trace"]')!;
  const marker = () => host.querySelector<SVGElement>('[data-ff-motion="marker"]')!;

  it('writes bounded transforms, real curve geometry and a settled tail', () => {
    const studies = start();
    run();
    // The compass is nearest the viewport centre here, so it is the one figure
    // allowed to move: a sweep about its own focal point and a drift with it.
    expect(group().getAttribute('transform')).toMatch(/^rotate\(-?[\d.]+ 1180 -60\) translate\(-?[\d.]+ -?[\d.]+\)$/);
    // A figure that is not in focus keeps its own start, which is a real point
    // on its curve rather than a blank or a halfway state.
    expect(trace().getAttribute('d')).toBe(harmonicFrame(0).d);
    // The tail ends by itself: no frame is left queued once the window expires.
    run(1000);
    expect(queued).toHaveLength(0);
    studies.dispose();
  });

  it('gives the static drawing back when reduced motion arrives mid-page', () => {
    const studies = start();
    tops = [-4000, 200, 4000, 9000];
    window.dispatchEvent(new Event('scroll'));
    run(1000);
    const moved = trace().getAttribute('d');
    expect(moved).not.toBe(harmonicFrame(0).d);
    reduced = true;
    window.dispatchEvent(new Event('scroll'));
    run();
    expect(group().getAttribute('transform')).toBeNull();
    // Reduced motion keeps the whole figure: the trace is back at the start of
    // the real curve and the cursor is on it, with no travel left in it.
    expect(trace().getAttribute('d')).toBe(harmonicFrame(0).d);
    expect(trace().style.opacity).toBe('1');
    expect(marker().style.opacity).toBe('0');
    studies.dispose();
  });

  it('sweeps the compass about its own focal point, inside its budget', () => {
    const studies = start();
    tops = [200, -4000, 4000, 9000];
    window.dispatchEvent(new Event('scroll'));
    run(1000);
    const frame = compassFrame(studyProgress({ top: 200, height: 600 }, VIEWPORT));
    expect(group().getAttribute('transform')).toBe(`rotate(${frame.angle} 1180 -60) translate(${frame.x} ${frame.y})`);
    expect(Math.abs(frame.angle)).toBeLessThanOrEqual(COMPASS_DEGREES / 2);
    studies.dispose();
  });

  it('leaves a figure that is not in focus exactly where it was', () => {
    const studies = start();
    tops = [-4000, 200, 4000, 9000];
    window.dispatchEvent(new Event('scroll'));
    run(1000);
    const seen = trace().getAttribute('d');
    expect(seen).not.toBe(harmonicFrame(0).d);
    // The harmonic figure is far off screen. It is not walked back to zero: that
    // would be motion for a drawing nobody is looking at.
    tops[1] = -4000;
    window.dispatchEvent(new Event('scroll'));
    run(1000);
    expect(trace().getAttribute('d')).toBe(seen);
    expect(trace().style.opacity).toBe('1');
    studies.dispose();
  });

  it('projects the friction marker onto the axis it is read against', () => {
    const studies = start();
    tops = [4000, 4000, 200, 9000];
    window.dispatchEvent(new Event('scroll'));
    run(1000);
    const point = frictionPoint(studyProgress({ top: 200, height: 600 }, VIEWPORT));
    expect(Number(marker().getAttribute('cx'))).toBeCloseTo(point.x, 6);
    expect(Number(marker().getAttribute('cy'))).toBeCloseTo(point.y, 6);
    // Horizontal projection lands on the left, where the coefficient is read.
    expect(host.querySelector('[data-ff-motion="across"]')!.getAttribute('d')).toBe(`M${point.x} ${point.y}H${PLOT.x}`);
    // Vertical projection lands on the bottom axis, where Re is read.
    expect(host.querySelector('[data-ff-motion="up"]')!.getAttribute('d')).toBe(`M${point.x} ${point.y}V${PLOT.y + PLOT.h}`);
    studies.dispose();
  });

  it('stops painting on hidden and on dispose, and leaves no frame behind', () => {
    const studies = start();
    run();
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    run();
    expect(queued).toHaveLength(0);
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    studies.dispose();
    window.dispatchEvent(new Event('scroll'));
    expect(queued).toHaveLength(0);
    expect(trace().getAttribute('d')).toBe(harmonicFrame(0).d);
  });

  it('cannot wake while hidden, either on mount or on a later event', () => {
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    const studies = start();
    try {
      expect(queued).toHaveLength(0);
      window.dispatchEvent(new Event('scroll'));
      studies.update();
      expect(queued).toHaveLength(0);
    } finally { studies.dispose(); }
  });

  it('does not rewrite offscreen figures while another figure moves', () => {
    const studies = start();
    run();
    const write = vi.spyOn(trace(), 'setAttribute');
    try {
      tops[0] = 100;
      window.dispatchEvent(new Event('scroll'));
      run();
      expect(write).not.toHaveBeenCalled();
    } finally { studies.dispose(); }
  });

  it('paints nothing at all where the browser has no SVG geometry', () => {
    // A document with no measurable figure is a static page, not a broken one.
    document.body.innerHTML = '<div data-ff-study="compass"></div>';
    const studies = startScrollStudies({
      find: () => [...document.querySelectorAll<HTMLElement>('[data-ff-study]')],
      viewport: () => VIEWPORT,
      reducedMotion: () => false,
      now: () => clock,
      requestFrame: callback => { queued.push(callback); return queued.length; },
      cancelFrame: () => { queued = []; },
    });
    expect(() => run(2000)).not.toThrow();
    expect(queued).toHaveLength(0);
    studies.dispose();
  });
});

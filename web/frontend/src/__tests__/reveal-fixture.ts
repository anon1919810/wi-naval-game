import { vi } from 'vitest';

/**
 * JSDOM has no layout, so the geometry the reveal measures has to be stated.
 *
 * These boxes are a 1440-wide desktop viewport with the shell's own rail: `main`
 * spans the full content width because the Work compass field is allowed to run
 * out past the reading column, while the rail keeps its own width on top. The
 * numbers below are the desktop composition at that width — nothing is arbitrary,
 * and the tests that use them assert behaviour against this geometry rather than
 * against the source numbers.
 */
const VIEWPORT = { width: 1440, height: 960 };
/** 1440 minus the shell's own horizontal padding (37.44px each side). */
export const MAIN = { left: 37.44, width: 1365.12 };
/** `--ff-rail` and `--ff-gap` at 1440: 288 and 57.6. */
export const RAIL = { width: 288, gap: 57.6, left: MAIN.left + MAIN.width - 288 };

/**
 * `railWords` gives the rail's own words a box. Off by default: a suite that
 * measures the words itself must not also have them measured for it, or the rail
 * remembers an origin from a box that suite never meant to exist.
 */
export function revealGeometry({ railWords = false }: { railWords?: boolean } = {}) {
  const original = Element.prototype.getBoundingClientRect;
  vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
    if (this.matches('.ff-main')) {
      return new DOMRect(MAIN.left, 100, MAIN.width, this.querySelector('.ff-about') ? 1800 : 650);
    }
    if (railWords && this.matches('.ff-rail-word')) {
      return new DOMRect(RAIL.left, 130, RAIL.width, 220);
    }
    return original.call(this);
  });
}

/** Fake timers drive the same RAF lifecycle, including the terminal frame. */
export function revealClock() {
  vi.spyOn(performance, 'now').mockImplementation(() => Date.now());
  vi.stubGlobal('requestAnimationFrame', (callback: FrameRequestCallback) => window.setTimeout(() => callback(performance.now()), 1));
  vi.stubGlobal('cancelAnimationFrame', (id: number) => window.clearTimeout(id));
}

export const revealing = () => document.querySelector<HTMLElement>('.ff-main')?.dataset.ffRevealClip;
export { VIEWPORT };
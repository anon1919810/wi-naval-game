import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import {
  currentSection,
  measureSections,
  READ_LINE_PX,
  RULER_MINOR_MARKS,
  rulerStops,
  SECTION_ARM_MS,
  SECTION_HYSTERESIS_PX,
  SECTION_SETTLE_MS,
  sectionLabel,
  sectionScrollTop,
  startReading as createReading,
  type ReadingOptions,
} from '../portfolio/readingScroll';

/**
 * Cluster: the reading controller.
 *
 * Two things have to be true at once and they pull in opposite directions — the
 * controller must follow a reader who scrolls quickly, and it must stay silent
 * when nothing was scrolled. So the geometry and the clock are fakes here, and
 * every assertion is about whether a tick was owed, was spent, or was correctly
 * never armed.
 */

const TOPS = [0, 600, 1200, 1800];

let clock = 0;
let timers: { id: number; at: number; run: () => void }[] = [];
let nextTimer = 1;
const activeReadings: ReturnType<typeof createReading>[] = [];
function startReading(options: ReadingOptions) {
  const reading = createReading(options);
  activeReadings.push(reading);
  return reading;
}

function options(patch: Omit<Partial<ReadingOptions>, 'onCurrent'> = {}): ReadingOptions & { onCurrent: ReturnType<typeof vi.fn>; tap: ReturnType<typeof vi.fn> } {
  const onCurrent = vi.fn();
  const tap = vi.fn(() => true);
  return {
    measure: () => [...TOPS],
    line: () => READ_LINE_PX,
    onCurrent,
    sound: { muted: false, tap },
    now: () => clock,
    setTimer: (callback, ms) => { const id = nextTimer++; timers.push({ id, at: clock + ms, run: callback }); return id; },
    clearTimer: id => { timers = timers.filter(timer => timer.id !== id); },
    tap,
    ...patch,
  };
}

function advance(ms: number) {
  clock += ms;
  const due = timers.filter(timer => timer.at <= clock).sort((a, b) => a.at - b.at);
  timers = timers.filter(timer => timer.at > clock);
  for (const timer of due) timer.run();
}

beforeEach(() => {
  clock = 0; timers = []; nextTimer = 1;
  Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
});
afterEach(() => { activeReadings.splice(0).forEach(reading => reading.dispose()); vi.restoreAllMocks(); });

describe('reading regression boundaries', () => {
  it('never carries a silent mount or refresh into a later same-section gesture', () => {
    let line = READ_LINE_PX;
    const seen = options({ line: () => line });
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    line += 10;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    line = 740;
    reading.refresh();
    window.dispatchEvent(new Event('wheel'));
    line += 10;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
  });

  it('uses the documented reading-line coordinates without a second offset', () => {
    let line = 0;
    const seen = options({ line: () => line });
    const reading = startReading(seen);
    line = 624;
    window.dispatchEvent(new Event('scroll'));
    expect(reading.current).toBe(1);
  });

  it('does not play before scrolling settles when gesture arming expires mid-tail', () => {
    let line = READ_LINE_PX;
    const seen = options({ line: () => line });
    startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    advance(SECTION_ARM_MS - 10);
    line = 740;
    window.dispatchEvent(new Event('scroll'));
    advance(20);
    line += 10;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS - 20);
    expect(seen.tap).not.toHaveBeenCalled();
    advance(20);
    expect(seen.tap).toHaveBeenCalledTimes(1);
  });

  it('keeps reduced-motion and hidden-page scrolling silent', () => {
    let line = READ_LINE_PX;
    const seen = options({ line: () => line, reducedMotion: () => true });
    startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    line = 740;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    window.dispatchEvent(new Event('wheel'));
    line = 1340;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
  });

  it('does not sound a brief section excursion that settles back at the starting section', () => {
    let line = READ_LINE_PX;
    const seen = options({ line: () => line });
    startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    line = 740;
    window.dispatchEvent(new Event('scroll'));
    advance(50);
    line = READ_LINE_PX;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
  });

  it('allows an explicit ruler arrival at the exact section edge', () => {
    let line = READ_LINE_PX;
    const seen = options({ line: () => line });
    const reading = startReading(seen);
    reading.arm();
    line = 600;
    window.dispatchEvent(new Event('scroll'));
    expect(reading.current).toBe(1);
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).toHaveBeenCalledTimes(1);
  });

  it('lands beyond a fractional section edge instead of rounding before it', () => {
    const top = 600.2;
    expect(sectionScrollTop(top) + READ_LINE_PX).toBeGreaterThanOrEqual(top);
  });

  it('arms PageDown on a focused link but ignores editing and button activation', () => {
    const seen = options();
    const reading = startReading(seen);
    const link = document.createElement('a');
    const button = document.createElement('button');
    const input = document.createElement('input');
    document.body.append(link, button, input);
    try {
      input.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
      button.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }));
      expect(reading.armed).toBe(false);
      link.dispatchEvent(new KeyboardEvent('keydown', { key: 'PageDown', bubbles: true }));
      expect(reading.armed).toBe(true);
    } finally { link.remove(); button.remove(); input.remove(); }
  });
});

describe('section projection', () => {
  it('clamps to the page and treats above the first section as the first section', () => {
    expect(currentSection(TOPS, -400, -1)).toBe(0);
    expect(currentSection(TOPS, 0, -1)).toBe(0);
    expect(currentSection(TOPS, 1500, 0)).toBe(2);
    expect(currentSection(TOPS, 99999, 0)).toBe(3);
    expect(currentSection([], 500, 0)).toBe(-1);
  });

  it('needs the reading line clear of the boundary, in both directions', () => {
    const boundary = TOPS[1];
    const band = { hysteresis: SECTION_HYSTERESIS_PX };
    // Just short of section 2: still section 1, even though the geometry says 2.
    expect(currentSection(TOPS, boundary + 1, 0, band)).toBe(0);
    expect(currentSection(TOPS, boundary + SECTION_HYSTERESIS_PX - 1, 0, band)).toBe(0);
    // Clear of the band: it changes, and only then.
    expect(currentSection(TOPS, boundary + SECTION_HYSTERESIS_PX, 0, band)).toBe(1);
    // Coming back, the same band holds section 2.
    expect(currentSection(TOPS, boundary - SECTION_HYSTERESIS_PX + 1, 1, band)).toBe(1);
    expect(currentSection(TOPS, boundary - SECTION_HYSTERESIS_PX, 1, band)).toBe(0);
  });

  it('does not chatter when the line jitters either side of a boundary', () => {
    let held = 0;
    // Every one of these is inside the 24 px band around the boundary at 600.
    for (const line of [600, 620, 610, 623, 577, 578, 599]) held = currentSection(TOPS, line, held);
    expect(held).toBe(0);
  });

  it('makes the last section reachable however short it is', () => {
    // A 40px final section can never be scrolled past its own top edge.
    const short = [0, 500, 540];
    expect(currentSection(short, 400, 1, { atEnd: true })).toBe(2);
    expect(currentSection(short, 400, 1)).toBe(0);
  });

  it('scrolls a mark to the reading line, never above the top of the page', () => {
    expect(sectionScrollTop(1200)).toBe(1200 - READ_LINE_PX);
    expect(sectionScrollTop(20)).toBe(0);
    expect(sectionScrollTop(-400)).toBe(0);
  });

  it('names sections in reading order, not by their own numbering', () => {
    expect(sectionLabel(0, 'Overview')).toBe('01 / OVERVIEW');
    expect(sectionLabel(4, 'Methods & Limits')).toBe('05 / METHODS & LIMITS');
  });
});

describe('the ruler track', () => {
  it('puts a major mark at the cumulative distance of every measured section', () => {
    const tops = [100, 300, 700];
    const majors = rulerStops(tops, 600).filter(stop => stop.major);
    expect(majors.map(stop => stop.index)).toEqual([0, 1, 2]);
    expect(majors.map(stop => stop.at)).toEqual([0, 1 / 3, 1]);
  });

  it('puts a major mark at every measured section and minors in the gaps', () => {
    const span = TOPS[TOPS.length - 1] - TOPS[0];
    const stops = rulerStops(TOPS, span);
    const majors = stops.filter(stop => stop.major);
    expect(majors.map(stop => stop.index)).toEqual([0, 1, 2, 3]);
    for (const [index, stop] of majors.entries()) expect(stop.at).toBeCloseTo(index / 3, 6);
    // Three gaps, each divided into RULER_MINOR_MARKS - 1 interior ticks.
    expect(stops.filter(stop => !stop.major)).toHaveLength(3 * (RULER_MINOR_MARKS - 1));
    for (const stop of stops) { expect(stop.at).toBeGreaterThanOrEqual(0); expect(stop.at).toBeLessThanOrEqual(1); }
  });

  it('clamps a section past the measured span rather than drawing outside the track', () => {
    const stops = rulerStops([0, 200, 900], 500);
    expect(Math.max(...stops.map(stop => stop.at))).toBeLessThanOrEqual(1);
  });

  it('leaves one usable mark when the page cannot be measured', () => {
    expect(rulerStops([0, 400], 0)).toEqual([{ at: 0, major: true, index: 0 }]);
    expect(rulerStops([], 100)).toEqual([]);
  });

  it('measures sections in document order and never returns an unordered edge', () => {
    const nodes = [
      { getBoundingClientRect: () => ({ top: 100 }) },
      { getBoundingClientRect: () => ({ top: 40 }) },
      { getBoundingClientRect: () => ({ top: 700 }) },
    ] as unknown as HTMLElement[];
    expect(measureSections(nodes, 20)).toEqual([120, 120, 720]);
  });
});

describe('the section voice', () => {
  it('says nothing on mount, on a route placement or on a resize', () => {
    const seen = options();
    const reading = startReading(seen);
    expect(seen.onCurrent).toHaveBeenCalledTimes(1);
    expect(reading.armed).toBe(false);
    // A page that arrives already scrolled is a placement, not a gesture.
    reading.refresh();
    window.dispatchEvent(new Event('resize'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    reading.dispose();
  });

  it('arms only on a real scrolling gesture, and ticks once it settles', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();

    window.dispatchEvent(new Event('wheel'));
    expect(reading.armed).toBe(true);
    reading.dispose();
  });

  it('debounces a fast traversal to the section the reader came to rest on', () => {
    const seen = options({ line: () => READ_LINE_PX });
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    // Cross three boundaries in three frames, none of them allowed to sound.
    seen.line = () => READ_LINE_PX + TOPS[3];
    window.dispatchEvent(new Event('scroll'));
    seen.line = () => READ_LINE_PX + TOPS[2];
    window.dispatchEvent(new Event('scroll'));
    seen.line = () => READ_LINE_PX + TOPS[1];
    window.dispatchEvent(new Event('scroll'));
    expect(seen.onCurrent).toHaveBeenLastCalledWith(1);
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).toHaveBeenCalledTimes(1);
    reading.dispose();
  });

  it('uses the quietest voice in the set and spends one tick per real change', () => {
    const tap = vi.fn(() => true);
    const seen = options({ sound: { muted: false, tap } });
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(tap).toHaveBeenCalledTimes(1);
    expect(tap).toHaveBeenCalledWith('section');
    // Jitter inside the band changes nothing, so nothing is owed.
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX - 8;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(tap).toHaveBeenCalledTimes(1);
    reading.dispose();
  });

  it('drops a pending tick when the visitor mutes before it is due', () => {
    const tap = vi.fn(() => true);
    const sound = { muted: false, tap };
    const seen = options({ sound });
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    sound.muted = true;
    advance(SECTION_SETTLE_MS);
    expect(tap).not.toHaveBeenCalled();
    reading.dispose();
  });

  it('takes the pending tick with it when the page is hidden, and stays unarmed', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    expect(reading.armed).toBe(false);
    // Restoring the tab reports where the reader is, and still says nothing.
    Object.defineProperty(document, 'visibilityState', { value: 'visible', configurable: true });
    document.dispatchEvent(new Event('visibilitychange'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    reading.dispose();
  });

  it('arms from a scroll key, and from nothing else', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'a' }));
    expect(reading.armed).toBe(false);
    window.dispatchEvent(new KeyboardEvent('keydown', { key: 'PageDown' }));
    expect(reading.armed).toBe(true);
    reading.dispose();
  });

  it('arms from an explicit ruler activation', () => {
    const seen = options();
    const reading = startReading(seen);
    reading.arm();
    expect(reading.armed).toBe(true);
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).toHaveBeenCalledTimes(1);
    reading.dispose();
  });

  it('keeps debouncing while the reader is still moving, even between boundaries', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    // Still scrolling inside the same section: the tick is pushed back, because
    // 140 ms has to mean "the reader stopped", not "a boundary was crossed".
    advance(SECTION_SETTLE_MS - 40);
    window.dispatchEvent(new Event('scroll'));
    advance(30);
    expect(seen.tap).not.toHaveBeenCalled();
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).toHaveBeenCalledTimes(1);
    reading.dispose();
  });

  it('takes a queued tick back when the page is re-measured or restored', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    // A resize, a late font or a returning tab all land on refresh, and all of
    // them mean the tick that was queued is about an older page.
    reading.refresh();
    advance(SECTION_SETTLE_MS * 2);
    expect(seen.tap).not.toHaveBeenCalled();
    window.dispatchEvent(new Event('resize'));
    advance(SECTION_SETTLE_MS * 2);
    expect(seen.tap).not.toHaveBeenCalled();
    reading.dispose();
  });

  it('does not let one wheel authorise a later programmatic scroll', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    // The arming expires on its own: a route that places the page at a section a
    // second later is not a reader's gesture and is not heard as one.
    advance(SECTION_ARM_MS + 1);
    expect(reading.armed).toBe(false);
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    advance(SECTION_SETTLE_MS);
    expect(seen.tap).not.toHaveBeenCalled();
    reading.dispose();
  });

  it('releases every listener and timer, and answers nothing afterwards', () => {
    const seen = options();
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    reading.dispose();
    reading.dispose();
    const owed = seen.onCurrent.mock.calls.length;
    window.dispatchEvent(new Event('scroll'));
    window.dispatchEvent(new Event('wheel'));
    advance(SECTION_SETTLE_MS * 4);
    expect(seen.onCurrent).toHaveBeenCalledTimes(owed);
    expect(seen.tap).not.toHaveBeenCalled();
    expect(timers).toHaveLength(0);
  });

  it('is a page without a voice when no sound is offered', () => {
    const seen = options({ sound: undefined });
    const reading = startReading(seen);
    window.dispatchEvent(new Event('wheel'));
    seen.line = () => READ_LINE_PX + TOPS[1] + SECTION_HYSTERESIS_PX;
    window.dispatchEvent(new Event('scroll'));
    expect(() => advance(SECTION_SETTLE_MS)).not.toThrow();
    expect(seen.onCurrent).toHaveBeenLastCalledWith(1);
    reading.dispose();
  });
});

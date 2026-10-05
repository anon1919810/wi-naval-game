import { ARTWORK_FRAME } from './Artwork';

/**
 * Bounded desktop inspection lens.
 *
 * The lens is not a second renderer: it reuses the same `Artwork` composition
 * and only narrows the SVG viewBox onto the sampled point. Magnification comes
 * from the ratio of the two scales, so the lens always shows the *same* rendered
 * artwork — same bitmap crop, same pan, same rest angle, same theme tone, same
 * construction plate — at exactly `LENS_MAGNIFICATION`, and it can never reveal
 * detail the source does not contain.
 *
 * The exhibit fits the composition frame with `preserveAspectRatio="xMidYMid
 * meet"`, so whenever its rectangle is not 16:7 the SVG letterboxes. The two
 * mappings below are kept apart on purpose:
 *
 * - `samplePoint` answers "which composition unit is under the pointer", in
 *   composition units, letterbox offsets included. That is what the lens
 *   viewBox must centre on.
 * - `cssSample` answers "where in the exhibit rectangle is that pointer", in CSS
 *   pixels. That is what the lens circle is clamped with, and it is also what
 *   the pan cursor and the keyboard focus read.
 */

/** Nominal lens diameter in CSS pixels; clamped down to the exhibit if it is smaller. */
export const LENS_DIAMETER = 200;

/** The lens shows the rendered exhibit twice as large. No more. */
export const LENS_MAGNIFICATION = 2;

export interface ExhibitRect {
  readonly left: number;
  readonly top: number;
  readonly width: number;
  readonly height: number;
}

export interface LensFrame {
  /** Square viewBox, in composition units, centred on the sampled point. */
  readonly viewBox: string;
  /** Composition units visible across the lens. */
  readonly span: number;
  /** Lens circle centre inside the exhibit, in CSS pixels. */
  readonly cx: number;
  readonly cy: number;
  /** Lens edge in CSS pixels; shrinks only when the exhibit is smaller than the lens. */
  readonly size: number;
  /** Sampled point relative to the lens centre, in CSS pixels. */
  readonly ox: number;
  readonly oy: number;
}

/** Resting viewBox before the exhibit has been measured: the middle of the frame. */
export const RESTING_VIEW_BOX = `${ARTWORK_FRAME.width / 2 - 400} ${ARTWORK_FRAME.height / 2 - 400} 800 800`;

const clamp = (value: number, low: number, high: number) => Math.max(low, Math.min(high, value));
const round = (value: number) => Math.round(value * 100) / 100;

/** CSS pixels per composition unit under `meet`, i.e. the exhibit's scale. */
export function exhibitScale(rect: ExhibitRect): number {
  return Math.min(rect.width / ARTWORK_FRAME.width, rect.height / ARTWORK_FRAME.height);
}

/** Composition unit sampled at a fraction of the exhibit rectangle, letterboxing included. */
export function samplePoint(rect: ExhibitRect, fx: number, fy: number) {
  const scale = exhibitScale(rect);
  const offsetX = (rect.width - ARTWORK_FRAME.width * scale) / 2;
  const offsetY = (rect.height - ARTWORK_FRAME.height * scale) / 2;
  return {
    x: (clamp(fx, 0, 1) * rect.width - offsetX) / scale,
    y: (clamp(fy, 0, 1) * rect.height - offsetY) / scale,
    scale,
  };
}

/** The same sample as a plain position inside the exhibit rectangle, in CSS pixels. */
export function cssSample(fx: number, fy: number, rect: ExhibitRect) {
  return { x: clamp(fx, 0, 1) * rect.width, y: clamp(fy, 0, 1) * rect.height };
}

/**
 * Lens placement for one sample. The lens stays fully inside the exhibit by
 * shifting the *circle*, while the viewBox — and therefore the sampled detail —
 * stays locked to the sampled point, reported back as the in-lens offset.
 */
export function lensFrame(rect: ExhibitRect, fx: number, fy: number, diameter = LENS_DIAMETER): LensFrame {
  const size = Math.max(0, Math.min(diameter, rect.width, rect.height));
  const sample = cssSample(fx, fy, rect);
  if (!rect.width || !rect.height || !size) {
    return { viewBox: RESTING_VIEW_BOX, span: 800, cx: sample.x, cy: sample.y, size: 0, ox: 0, oy: 0 };
  }
  const { x, y, scale } = samplePoint(rect, fx, fy);
  const span = size / (LENS_MAGNIFICATION * scale);
  const half = span / 2;
  const cx = clamp(sample.x, size / 2, Math.max(size / 2, rect.width - size / 2));
  const cy = clamp(sample.y, size / 2, Math.max(size / 2, rect.height - size / 2));
  return {
    viewBox: `${round(x - half)} ${round(y - half)} ${round(span)} ${round(span)}`,
    span,
    cx,
    cy,
    size,
    ox: sample.x - cx,
    oy: sample.y - cy,
  };
}

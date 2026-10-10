/**
 * Reference line sheets behind the public Plimsoll exhibit.
 *
 * The public artwork *is* the original scan: VesselDrawing.tsx crops each sheet
 * in place with an <image> at its intrinsic size, so the crop metadata below is
 * load-bearing source geometry rather than reference notes. Nothing is redrawn,
 * traced or simplified, and the scan is shown at its own resolution. The bow
 * points right in all three studies.
 *
 * `href` names a **lossless WebP derivative** of each PNG, not the PNG itself.
 * Lossless here means exactly that: the decoded pixels are byte-for-byte
 * identical to the PNG's, which was verified for all three sheets when they were
 * generated. The PNGs remain in `public/portfolio/` as the archival originals
 * and are unchanged; the derivatives are ~58% smaller, which matters because
 * each sheet is a ~200 KB scan the browser has to fetch. Nothing about the
 * geometry, the crop or the tonal treatment changes — only the container.
 *
 * Provenance and usage limits: see `public/portfolio/PROVENANCE.md`. The three
 * sheets are reference alternatives inside the single
 * Plimsoll work — not three projects, and not interchangeable verified
 * specifications of one vessel.
 */

export interface PlanCrop {
  readonly x: number;
  readonly y: number;
  readonly width: number;
  readonly height: number;
}

/**
 * Per-sheet, per-theme tone control. The scan's own pixels decide everything:
 * `gamma` bends the density around the midtones before the linear term lifts or
 * firms the ink, and `opacity` scales the finished group. Nothing here reads,
 * writes or resamples the source, and every curve stays monotone, so no detail
 * is invented — but, as with any tonal threshold, marks fainter than the
 * cleaned threshold can attenuate. A denser sheet is only made calmer.
 */
export interface TonalProfile {
  /** Density curve: ink = clamp(slope · (1 − luminance) ^ gamma + intercept). */
  readonly slope: number;
  readonly intercept: number;
  /** > 1 pulls mid ink down while leaving the deepest marks strongest. */
  readonly gamma: number;
  /** Multiplier on the theme's base group opacity (1 = unchanged). */
  readonly opacity: number;
}

export interface PlanSheet {
  readonly id: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly href: string;
  readonly sourceWidth: number;
  readonly sourceHeight: number;
  /** Lower top-view band of the archived reference, used verbatim as the viewBox. */
  readonly crop: PlanCrop;
  /**
   * Tonal profiles shared by the splash, the exhibit and the inspection lens, so
   * a sheet never changes weight between those three surfaces.
   *
   * Measured on the archived bands (`docs/formfield/inspect-lens-2026-10-05.md`):
   * 01 is a line drawing on white paper (77% of its band is bare paper) and is
   * left exactly as before. 02 carries a dense dark deck hatch covering the whole
   * hull, which inverse luminance turned into one solid field of ink, so its
   * midtones are pulled down hardest while its line cores keep the darkest ink.
   * 03's flat gray fills are eased a little further to sit in the same
   * hierarchy as 02.
   */
  readonly tone: { readonly light: TonalProfile; readonly dark: TonalProfile };
}

export const PLAN_SHEETS: readonly PlanSheet[] = [
  {
    id: '01',
    label: 'Reference sheet 01',
    shortLabel: '01',
    href: '/portfolio/ship-plan-01.webp',
    sourceWidth: 1000,
    sourceHeight: 451,
    crop: { x: 0, y: 290, width: 1000, height: 161 },
    tone: {
      light: { slope: 1.2, intercept: -0.05, gamma: 1, opacity: 1 },
      dark: { slope: 1.08, intercept: -0.035, gamma: 1, opacity: 1 },
    },
  },
  {
    id: '02',
    label: 'Reference sheet 02',
    shortLabel: '02',
    href: '/portfolio/ship-plan-02.webp',
    sourceWidth: 1018,
    sourceHeight: 451,
    crop: { x: 0, y: 290, width: 1018, height: 161 },
    tone: {
      light: { slope: 0.72, intercept: -0.02, gamma: 1.35, opacity: 0.9 },
      dark: { slope: 0.95, intercept: -0.02, gamma: 1.8, opacity: 0.95 },
    },
  },
  {
    id: '03',
    label: 'Reference sheet 03',
    shortLabel: '03',
    href: '/portfolio/ship-plan-03.webp',
    sourceWidth: 1063,
    sourceHeight: 542,
    crop: { x: 0, y: 360, width: 1063, height: 182 },
    tone: {
      light: { slope: 0.92, intercept: -0.02, gamma: 1.15, opacity: 0.92 },
      dark: { slope: 0.92, intercept: -0.03, gamma: 1.2, opacity: 0.9 },
    },
  },
];

export const DEFAULT_SHEET_INDEX = 0;

/** Composition length of the vessel crop, in composition units. */
export const VESSEL_LENGTH = 1000;

export function sheetBeam(sheet: PlanSheet): number {
  return VESSEL_LENGTH * (sheet.crop.height / sheet.crop.width);
}

export function sheetByIndex(index: number): PlanSheet {
  const safe = Number.isFinite(index) ? Math.trunc(index) : DEFAULT_SHEET_INDEX;
  return PLAN_SHEETS[Math.min(Math.max(safe, 0), PLAN_SHEETS.length - 1)];
}

/** The one tonal profile for a sheet in the given theme; splash, exhibit and lens all use it. */
export function sheetTone(sheet: PlanSheet, dark: boolean): TonalProfile {
  return dark ? sheet.tone.dark : sheet.tone.light;
}

export function sheetViewBox(sheet: PlanSheet): string {
  const { x, y, width, height } = sheet.crop;
  return `${x} ${y} ${width} ${height}`;
}

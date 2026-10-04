/**
 * Reference line sheets behind the public Plimsoll exhibit.
 *
 * The public artwork *is* the original PNG: VesselDrawing.tsx crops each sheet
 * in place with an <image> at its intrinsic size, so the crop metadata below is
 * load-bearing source geometry rather than reference notes. Nothing is redrawn,
 * traced or simplified, and the scan is shown at its own resolution. The bow
 * points right in all three studies.
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

export interface PlanSheet {
  readonly id: string;
  readonly label: string;
  readonly shortLabel: string;
  readonly href: string;
  readonly sourceWidth: number;
  readonly sourceHeight: number;
  /** Lower top-view band of the archived reference, used verbatim as the viewBox. */
  readonly crop: PlanCrop;
}

export const PLAN_SHEETS: readonly PlanSheet[] = [
  {
    id: '01',
    label: 'Reference sheet 01',
    shortLabel: '01',
    href: '/portfolio/ship-plan-01.png',
    sourceWidth: 1000,
    sourceHeight: 451,
    crop: { x: 0, y: 290, width: 1000, height: 161 },
  },
  {
    id: '02',
    label: 'Reference sheet 02',
    shortLabel: '02',
    href: '/portfolio/ship-plan-02.png',
    sourceWidth: 1018,
    sourceHeight: 451,
    crop: { x: 0, y: 290, width: 1018, height: 161 },
  },
  {
    id: '03',
    label: 'Reference sheet 03',
    shortLabel: '03',
    href: '/portfolio/ship-plan-03.png',
    sourceWidth: 1063,
    sourceHeight: 542,
    crop: { x: 0, y: 360, width: 1063, height: 182 },
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

export function sheetViewBox(sheet: PlanSheet): string {
  const { x, y, width, height } = sheet.crop;
  return `${x} ${y} ${width} ${height}`;
}

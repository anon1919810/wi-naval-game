import { useId } from 'react';
import { sheetViewBox, type PlanSheet, type TonalProfile } from './plans';

/**
 * The studies are the archived reference PNGs themselves, cropped in place.
 * Nothing here redraws, traces or simplifies the source artwork: the nested
 * <svg> viewBox is exactly `sheet.crop` and the <image> carries the whole
 * original sheet at its intrinsic pixel size, so every original detail —
 * hatching, fittings, shading, plate seams and fine marks — survives at the
 * source's own resolution.
 */
const COMPOSITION = { x: 145, y: 232, width: 1310, height: 236, viewWidth: 1000, viewHeight: 180 };

/**
 * Decoration-mask hulls, used only by the `silhouette` branch so Artwork's
 * construction lines do not cross the deck. These are broad, smooth
 * approximations with no claim to the source outline; they are never the
 * displayed artwork and carry none of the original detail.
 */
const MASK_HULLS: Record<string, string> = {
  '01': 'M18 82 68 57 175 34 325 22 575 22 725 33 850 52 985 90 850 128 725 147 575 158 325 158 175 146 68 123 18 98Z',
  '02': 'M18 85 83 52 205 27 396 19 673 19 825 37 923 64 989 90 923 116 825 143 673 161 396 161 205 153 83 128 18 95Z',
  '03': 'M17 83 73 57 173 38 320 24H648L789 36 903 57 989 90 903 123 789 144 648 156H320L173 142 73 123 17 97Z',
};

/**
 * The only treatment applied to the scan is a restrained tonal one, so the
 * theme ink drives the rendering while the paper drops out:
 *
 * 1. `feColorMatrix` inverts luminance into alpha — white paper becomes fully
 *    transparent, solid black ink becomes opaque, and every intermediate gray
 *    is retained as its own ink density. The source's own gray fills therefore
 *    survive as proportionally lighter ink.
 * 2. `feComponentTransfer` applies the sheet's own profile as a single gamma
 *    function, `amplitude · density ^ exponent + offset` (sheet 01 keeps gamma 1
 *    and the original per-theme values, slope 1.2 / intercept -0.05 in light and
 *    1.08 / -0.035 in dark). One function per channel, because a second
 *    `feFuncA` in the same transfer would silently replace it rather than
 *    follow it. It reconstructs no geometry; as any tonal threshold does, it
 *    can attenuate marks fainter than the cleaned threshold.
 * 3. `feFlood` + `feComposite operator="in"` paint that density in the theme
 *    ink color.
 *
 * There is deliberately no blur, morphological filter, convolution or edge
 * detection, and no enhancement of the source's intrinsic resolution. The
 * rendered result stays at the source's own resolution: the curve decides how
 * much ink a sampled pixel carries, never how many source pixels exist.
 */
function InkFilter({ id, ink, tone }: { id: string; ink: string; tone: TonalProfile }) {
  return <filter id={id} colorInterpolationFilters="sRGB">
    <feColorMatrix type="matrix" result="density" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  -0.3333 -0.3333 -0.3333 0 1" />
    {/* One function per channel: amplitude and offset are the linear term,
        exponent is the midtone bend that a dense sheet needs. */}
    <feComponentTransfer in="density" result="clean-density">
      <feFuncA type="gamma" amplitude={tone.slope} exponent={tone.gamma} offset={tone.intercept} />
    </feComponentTransfer>
    {/* SourceAlpha bounds the result: without it the inverse-luminance matrix
      resolves fully transparent, out-of-image pixels to alpha 1 and floods the
      composition rectangle with ink. */}
    <feComposite in="clean-density" in2="SourceAlpha" operator="in" result="bounded-density" />
    <feFlood floodColor={ink} result="ink-color" />
    <feComposite in="ink-color" in2="bounded-density" operator="in" />
  </filter>;
}

/** Shared placement registers silhouette masking, exhibit, lens and both scan layers. */
export function VesselDrawing({ sheet, ink = 'currentColor', silhouette = false, opacity = 1, tone }: { sheet: PlanSheet; ink?: string; silhouette?: boolean; opacity?: number; tone?: TonalProfile }) {
  const id = useId().replace(/:/g, '');
  const hull = MASK_HULLS[sheet.id] ?? MASK_HULLS['01'];
  const profile = tone ?? sheet.tone.light;
  return <svg className="ff-vessel-drawing" x={COMPOSITION.x} y={COMPOSITION.y} width={COMPOSITION.width} height={COMPOSITION.height} viewBox={`0 0 ${COMPOSITION.viewWidth} ${COMPOSITION.viewHeight}`} aria-hidden="true" focusable="false">
    {silhouette ? <path d={hull} fill="black" stroke="black" strokeWidth="14" /> : <>
      <defs><InkFilter id={`${id}-ink`} ink={ink} tone={profile} /></defs>
      <g className="ff-vessel" data-study={sheet.id} opacity={opacity} filter={`url(#${id}-ink)`}>
        <svg className="ff-vessel-sheet" x="0" y="0" width={COMPOSITION.viewWidth} height={COMPOSITION.viewHeight} viewBox={sheetViewBox(sheet)} preserveAspectRatio="xMidYMid meet" overflow="hidden">
          {/* Clip in source-sheet coordinates: `overflow` bounds the viewport,
            not the requested crop, so the letterboxed band above the top view
            would otherwise leak into the composition. */}
          <defs>
            <clipPath id={`${id}-crop`} clipPathUnits="userSpaceOnUse">
              <rect x={sheet.crop.x} y={sheet.crop.y} width={sheet.crop.width} height={sheet.crop.height} />
            </clipPath>
          </defs>
          <image href={sheet.href} x="0" y="0" width={sheet.sourceWidth} height={sheet.sourceHeight} clipPath={`url(#${id}-crop)`} />
        </svg>
      </g>
    </>}
  </svg>;
}

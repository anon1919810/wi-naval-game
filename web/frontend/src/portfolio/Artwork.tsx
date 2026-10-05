import { useId, type Ref } from 'react';
import { sheetTone, type PlanSheet } from './plans';
import { VesselDrawing } from './VesselDrawing';

export interface ArtworkProps {
  sheet: PlanSheet;
  angle?: number;
  scale?: number;
  pan?: { x: number; y: number };
  dark?: boolean;
  details?: boolean;
  /** Give the root <svg> the frame's own pixel box, so 1 unit = 1 CSS pixel. */
  pixelFrame?: boolean;
  compositionRef?: Ref<SVGGElement>;
  geometryRef?: Ref<SVGGElement>;
  maskRef?: Ref<SVGGElement>;
}

/** The panoramic composition frame every surface shares, in composition units. */
export const ARTWORK_FRAME = { width: 1600, height: 700 } as const;

/** Composition pivot: the centre of the 1600×700 panoramic frame. */
export function artworkTransform(angle = -12, scale = 1, pan = { x: 0, y: 0 }) {
  return `translate(${ARTWORK_FRAME.width / 2 + pan.x} ${ARTWORK_FRAME.height / 2 + pan.y}) rotate(${angle}) scale(${scale}) translate(-800 -350)`;
}

/** The construction layer floats at this fraction of the vessel layer's pan. */
export const GEOMETRY_PARALLAX = 0.45;

/**
 * The deck-clearing mask belongs to the geometry layer's coordinate space but
 * must cut where the vessel actually is. With parallax the vessel appears in
 * geometry-local coordinates translated by R⁻¹(pan × (1 − GEOMETRY_PARALLAX)),
 * where R⁻¹ undoes the -12° rest rotation.
 */
export function maskTrackTransform(pan = { x: 0, y: 0 }) {
  const dx = pan.x * (1 - GEOMETRY_PARALLAX), dy = pan.y * (1 - GEOMETRY_PARALLAX);
  const r = (12 * Math.PI) / 180, c = Math.cos(r), s = Math.sin(r);
  const f = (n: number) => Math.round(n * 100) / 100;
  return `translate(${f(dx * c - dy * s)} ${f(dx * s + dy * c)})`;
}

/** Hull-station verticals crossing the vessel band; the deck mask leaves only the stubs above and below the hull. */
const STATION_XS = [330, 450, 570, 690, 930, 1050, 1170, 1290];
const STATIONS = STATION_XS.map(x => `M${x} 210V490`).join(' ');
/** Bottom scale bar: decorative ticks every 50 units, longer each 100. No real measurements are expressed. */
const RULER = 'M180 645H1420 ' + Array.from({ length: 25 }, (_, i) => `M${180 + i * 50} 645v${i % 2 === 0 ? 10 : 5}`).join(' ');
/** Scale-bar numbers sit above the line where the -12° rest angle keeps them inside the frame. */
const RULER_NUMBERS = Array.from({ length: 9 }, (_, i) => ({ x: 580 + i * 100, label: String((i + 1) * 10) }));
/** Protractor rose around the lower-right registration mark. */
const ROSE_TICKS = Array.from({ length: 12 }, (_, k) => {
  const t = (k * Math.PI) / 6, c = Math.cos(t), s = Math.sin(t);
  return `M${(1338 + 38 * c).toFixed(1)} ${(503 + 38 * s).toFixed(1)}L${(1338 + 48 * c).toFixed(1)} ${(503 + 48 * s).toFixed(1)}`;
}).join(' ');

/**
 * Composition shared by the exhibit and its two scan layers. The vessel study
 * is the original reference bitmap cropped by VesselDrawing.tsx; only the
 * construction lines, grid and labels around it are drawn here, and the mask
 * uses a broad approximate hull so those lines never cross the deck.
 *
 * The frame is a panoramic 1600×700: the vessel band fills about a third of
 * the frame height so the study reads as the exhibit's mass, with the
 * construction geometry compressed around the centre axis.
 *
 * Two layers share the frame: `ff-layer-vessel` carries the study itself,
 * `ff-layer-geometry` the construction plate. The exhibit pans them at
 * GEOMETRY_PARALLAX so the plate floats gently against the drawing; during
 * the intro both layers are painted with the same angle and scale.
 *
 * `pixelFrame` is for the inspection lens, which narrows an enclosing viewBox:
 * without the frame's own pixel box the nested <svg> would be fitted to the
 * lens square a second time and the lens would zoom out instead of in.
 *
 * Light mode needs both a firmer ink curve on the scan and slightly stronger
 * construction lines: on paper, dark ink and thin strokes read weaker than
 * their light-on-dark equivalents at equal opacity.
 */
export function Artwork({ sheet, angle = -12, scale = 1, pan = { x: 0, y: 0 }, dark = false, details = true, pixelFrame = false, compositionRef, geometryRef, maskRef }: ArtworkProps) {
  const id = useId().replace(/:/g, '');
  const ink = dark ? '#f2f2ee' : '#171817';
  const tone = sheetTone(sheet, dark);
  const geometryPan = { x: pan.x * GEOMETRY_PARALLAX, y: pan.y * GEOMETRY_PARALLAX };
  return <svg className="ff-artwork" viewBox={`0 0 ${ARTWORK_FRAME.width} ${ARTWORK_FRAME.height}`} {...(pixelFrame ? { x: 0, y: 0, width: ARTWORK_FRAME.width, height: ARTWORK_FRAME.height } : {})} aria-hidden="true" focusable="false">
    <defs>
      <mask id={`${id}-clear-deck`} maskUnits="userSpaceOnUse" x="-200" y="-200" width="2000" height="1400">
        <rect x="-200" y="-200" width="2000" height="1400" fill="white" />
        {/* The hull cutout tracks the vessel layer's actual pan, so parallax never exposes hull-shaped gaps in the plate. */}
        <g className="ff-mask-track" ref={maskRef} transform={maskTrackTransform(pan)}>
          <VesselDrawing sheet={sheet} silhouette />
        </g>
      </mask>
      <pattern id={`${id}-grid`} width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke={ink} strokeWidth=".7" /></pattern>
    </defs>
    <g className="ff-layer-geometry" ref={geometryRef} transform={artworkTransform(angle, scale, geometryPan)}>
      <g fill="none" stroke={ink} opacity={details ? (dark ? .2 : .27) : 0} mask={`url(#${id}-clear-deck)`}>
        <g strokeWidth="1.4"><path d="M-80 350H1690 M810 -100V780" strokeDasharray="10 12" /></g>
        <g strokeWidth="1.1">
          <path d="M-150 540L1640 89 M105 578L1550 292 M170 503L1490 503" />
          <path d="M175 426A547 547 0 0 0 1142 551 M525 650A330 330 0 0 0 1003 307 M1190 54A282 282 0 0 1 1338 559" />
          <path d="M158 225V529H1338 M260 250H1410V441 M1090 100H1380V272" />
          <circle cx="1338" cy="503" r="48" />
          {[{ x: 310, y: 503 }, { x: 810, y: 350 }, { x: 1170, y: 214 }, { x: 1338, y: 503 }].map(p => <g key={`${p.x}-${p.y}`}><path d={`M${p.x - 11} ${p.y}h22 M${p.x} ${p.y - 11}v22`} /><circle cx={p.x} cy={p.y} r="20" /></g>)}
        </g>
        <g strokeWidth=".75">
          <path d={STATIONS} />
          <circle cx="810" cy="350" r="195" strokeDasharray="4 8" />
          <path d={RULER} />
          <path d={ROSE_TICKS} />
        </g>
        <circle cx="810" cy="503" r="3.5" fill={ink} stroke="none" />
        <circle cx="810" cy="298" r="3.5" fill={ink} stroke="none" />
        <rect x="180" y="441" width="372" height="115" fill={`url(#${id}-grid)`} stroke="none" opacity={dark ? .55 : .7} />
        <rect x="1150" y="142" width="210" height="98" fill={`url(#${id}-grid)`} stroke="none" opacity={dark ? .55 : .7} />
      </g>
      <g fill={ink} opacity={details ? .48 : 0} fontFamily="Archivo, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif" fontWeight="600" fontSize="11" letterSpacing="2" style={{ fontVariantNumeric: 'tabular-nums' }}>
        <text x="180" y="560">TOP VIEW / REFERENCE {sheet.id}</text>
        <text x="1110" y="117">FORM / FIELD</text>
        <text x="826" y="150">SEC A—A</text>
        <text x="1150" y="132">GRID 42</text>
        <g fontSize="9" letterSpacing="1" textAnchor="middle">
          {STATION_XS.map((x, i) => <text key={x} x={x} y="202">S{i + 1}</text>)}
          {RULER_NUMBERS.map(n => <text key={n.x} x={n.x} y="633">{n.label}</text>)}
        </g>
      </g>
    </g>
    <g className="ff-layer-vessel" ref={compositionRef} transform={artworkTransform(angle, scale, pan)}>
      {/* One tonal profile per sheet and theme, shared with the splash and the lens. */}
      <VesselDrawing sheet={sheet} ink={ink} opacity={(dark ? .85 : 1) * tone.opacity} tone={tone} />
    </g>
  </svg>;
}

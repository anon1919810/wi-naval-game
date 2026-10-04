import { useId, type Ref } from 'react';
import type { PlanSheet } from './plans';
import { VesselDrawing } from './VesselDrawing';

export interface ArtworkProps {
  sheet: PlanSheet;
  angle?: number;
  scale?: number;
  pan?: { x: number; y: number };
  dark?: boolean;
  details?: boolean;
  compositionRef?: Ref<SVGGElement>;
}

export function artworkTransform(angle = -12, scale = 1, pan = { x: 0, y: 0 }) {
  return `translate(${800 + pan.x} ${450 + pan.y}) rotate(${angle}) scale(${scale}) translate(-800 -450)`;
}

/**
 * Composition shared by the exhibit and its two scan layers. The vessel study
 * is the original reference bitmap cropped by VesselDrawing.tsx; only the
 * construction lines, grid and labels around it are drawn here, and the mask
 * uses a broad approximate hull so those lines never cross the deck.
 */
export function Artwork({ sheet, angle = -12, scale = 1, pan = { x: 0, y: 0 }, dark = false, details = true, compositionRef }: ArtworkProps) {
  const id = useId().replace(/:/g, '');
  const ink = dark ? '#f2f2ee' : '#171817';
  return <svg className="ff-artwork" viewBox="0 0 1600 900" aria-hidden="true" focusable="false">
    <defs>
      <mask id={`${id}-clear-deck`} maskUnits="userSpaceOnUse" x="-200" y="-200" width="2000" height="1400">
        <rect x="-200" y="-200" width="2000" height="1400" fill="white" />
        <VesselDrawing sheet={sheet} silhouette />
      </mask>
      <pattern id={`${id}-grid`} width="42" height="42" patternUnits="userSpaceOnUse"><path d="M42 0H0V42" fill="none" stroke={ink} strokeWidth=".7" /></pattern>
    </defs>
    <g ref={compositionRef} transform={artworkTransform(angle, scale, pan)}>
      <g fill="none" stroke={ink} strokeWidth="1.1" opacity={details ? .2 : 0} mask={`url(#${id}-clear-deck)`}>
        <path d="M-80 450H1690 M810 -150V1030" strokeDasharray="10 12" />
        <path d="M-150 694L1640 116 M105 742L1550 375 M170 646L1490 646" />
        <path d="M175 548A550 550 0 0 0 1142 708 M525 835A365 365 0 0 0 1003 395 M1190 70A355 355 0 0 1 1338 718" />
        <path d="M158 290V680H1338 M260 322H1410V567 M1090 130H1380V350" />
        <rect x="180" y="566" width="372" height="168" fill={`url(#${id}-grid)`} stroke="none" opacity=".55" />
        <rect x="1150" y="183" width="210" height="126" fill={`url(#${id}-grid)`} stroke="none" opacity=".55" />
        {[{ x: 310, y: 646 }, { x: 810, y: 450 }, { x: 1170, y: 275 }, { x: 1338, y: 646 }].map(p => <g key={`${p.x}-${p.y}`}><path d={`M${p.x - 11} ${p.y}h22 M${p.x} ${p.y - 11}v22`} /><circle cx={p.x} cy={p.y} r="20" /></g>)}
      </g>
      <VesselDrawing sheet={sheet} ink={ink} opacity={dark ? .85 : 1} />
      <g fill={ink} opacity={details ? .48 : 0} fontFamily="'SFMono-Regular',Consolas,monospace" fontSize="11" letterSpacing="2">
        <text x="180" y="770">TOP VIEW / REFERENCE {sheet.id}</text>
        <text x="1110" y="151">FORM / FIELD</text>
      </g>
    </g>
  </svg>;
}

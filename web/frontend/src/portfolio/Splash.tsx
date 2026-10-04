import { useLayoutEffect, useRef, type RefObject } from 'react';
import { Artwork, artworkTransform } from './Artwork';
import { diagonalClip, introFrame, INTRO_DURATION } from './motion';
import type { PlanSheet } from './plans';

interface Props { sheet: PlanSheet; target: RefObject<HTMLDivElement | null>; dark: boolean; details: boolean; onDone: () => void; onSettle: () => void }
export function Splash({ sheet, target, dark, details, onDone, onSettle }: Props) {
  const root = useRef<HTMLDivElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  const reveal = useRef<HTMLDivElement>(null);
  const reverse = useRef<HTMLDivElement>(null);
  const firstArt = useRef<SVGGElement>(null);
  const secondArt = useRef<SVGGElement>(null);
  const firstGeo = useRef<SVGGElement>(null);
  const secondGeo = useRef<SVGGElement>(null);
  const skip = useRef<HTMLButtonElement>(null);
  useLayoutEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { onDone(); return; }
    let active = true, frame = 0, settling = false;
    let width = 0, height = 0;
    let rect = { left: 0, top: 0, width: 0, height: 0 };
    const measure = () => {
      width = document.documentElement.clientWidth || window.innerWidth;
      height = document.documentElement.clientHeight || window.innerHeight;
      const r = target.current?.getBoundingClientRect();
      rect = r ? { left: r.left, top: r.top, width: r.width, height: r.height } : { left: 0, top: 0, width, height };
    };
    const paint = (elapsed: number) => {
      const f = introFrame(elapsed), u = f.settle;
      root.current!.dataset.phase = f.phase;
      root.current!.classList.toggle('ff-splash-settle', u > 0);
      Object.assign(panel.current!.style, { left: `${rect.left * u}px`, top: `${rect.top * u}px`, width: `${width + (rect.width - width) * u}px`, height: `${height + (rect.height - height) * u}px` });
      reveal.current!.style.clipPath = diagonalClip(f.reveal);
      reverse.current!.style.clipPath = diagonalClip(f.reverse, true);
      const transform = artworkTransform(f.angle, f.scale);
      firstArt.current!.setAttribute('transform', transform);
      secondArt.current!.setAttribute('transform', transform);
      firstGeo.current!.setAttribute('transform', transform);
      secondGeo.current!.setAttribute('transform', transform);
      skip.current!.hidden = elapsed <= 100 || u > 0;
    };
    measure(); paint(0);
    const origin = performance.now();
    const tick = (now: number) => {
      if (!active) return;
      const elapsed = now - origin;
      if (elapsed >= INTRO_DURATION) { onDone(); return; }
      paint(elapsed);
      if (elapsed >= 1800 && !settling) { settling = true; onSettle(); }
      frame = requestAnimationFrame(tick);
    };
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') onDone(); };
    frame = requestAnimationFrame(tick);
    window.addEventListener('resize', measure);
    window.addEventListener('scroll', measure, { passive: true });
    window.addEventListener('keydown', key);
    return () => { active = false; cancelAnimationFrame(frame); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure); window.removeEventListener('keydown', key); };
  }, [sheet, target, onDone, onSettle]);
  return <div ref={root} className="ff-splash" data-phase="black" role="status" aria-label="Opening Y’s Formfield">
    <div ref={panel} className="ff-splash-panel">
      <div ref={reveal} className="ff-scan-layer ff-scan-dark"><Artwork compositionRef={firstArt} geometryRef={firstGeo} sheet={sheet} dark details={details} angle={-28} scale={1.85} /></div>
      <div ref={reverse} className={`ff-scan-layer ${dark ? 'ff-scan-dark' : 'ff-scan-light'}`}><Artwork compositionRef={secondArt} geometryRef={secondGeo} sheet={sheet} dark={dark} details={details} angle={-28} scale={1.85} /></div>
    </div>
    <button ref={skip} hidden className="ff-skip" onClick={onDone}>SKIP INTRO <span>↗</span></button>
  </div>;
}

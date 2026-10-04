import { useEffect, useState, type RefObject } from 'react';
import { Artwork } from './Artwork';
import { diagonalClip, introFrame, INTRO_DURATION } from './motion';
import type { PlanSheet } from './plans';

interface Props { sheet: PlanSheet; target: RefObject<HTMLDivElement | null>; dark: boolean; details: boolean; onDone: () => void; onSettle: () => void }
export function Splash({ sheet, target, dark, details, onDone, onSettle }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [rect, setRect] = useState({ left: 0, top: 0, width: window.innerWidth, height: window.innerHeight });
  useEffect(() => {
    let active = true, frame = 0, started = false, settling = false;
    const finish = () => { if (active) onDone(); };
    const measure = () => {
      const r = target.current?.getBoundingClientRect();
      if (r) setRect({ left: r.left, top: r.top, width: r.width, height: r.height });
    };
    const start = () => {
      if (!active || started) return;
      started = true;
      if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { finish(); return; }
      measure();
      const origin = performance.now();
      const tick = (now: number) => {
        if (!active) return;
        const next = now - origin;
        if (next >= INTRO_DURATION) { finish(); return; }
        if (next >= 1800 && !settling) { settling = true; onSettle(); }
        setElapsed(next); frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };
    start();
    window.addEventListener('resize', measure);
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') finish(); };
    window.addEventListener('keydown', key);
    return () => { active = false; cancelAnimationFrame(frame); window.removeEventListener('resize', measure); window.removeEventListener('keydown', key); };
  }, [sheet, target, onDone, onSettle]);
  const f = introFrame(elapsed);
  const u = f.settle;
  const panel = { left: rect.left * u, top: rect.top * u, width: window.innerWidth + (rect.width - window.innerWidth) * u, height: window.innerHeight + (rect.height - window.innerHeight) * u };
  return <div className={`ff-splash${u > 0 ? ' ff-splash-settle' : ''}`} data-phase={f.phase} role="status" aria-label="Opening Y’s Formfield">
    <div className="ff-splash-panel" style={panel}>
      <div className="ff-scan-layer ff-scan-dark" style={{ clipPath: diagonalClip(f.reveal) }}><Artwork sheet={sheet} dark details={details} angle={f.angle} scale={f.scale} /></div>
      <div className={`ff-scan-layer ${dark ? 'ff-scan-dark' : 'ff-scan-light'}`} style={{ clipPath: diagonalClip(f.reverse, true) }}><Artwork sheet={sheet} dark={dark} details={details} angle={f.angle} scale={f.scale} /></div>
    </div>
    {elapsed > 100 && u === 0 && <button className="ff-skip" onClick={onDone}>SKIP INTRO <span>↗</span></button>}
  </div>;
}

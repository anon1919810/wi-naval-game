import { lazy, Suspense, useCallback, useEffect, useRef, useState, type PointerEvent, type KeyboardEvent } from 'react';
import { Artwork } from './Artwork';
import { Splash } from './Splash';
import { PLAN_SHEETS, sheetByIndex } from './plans';
import { APP_ENTRY_LINK, classifyHash, publicHref } from './routes';
import { resolveTheme, storedTheme, THEME_KEY, type PortfolioTheme } from './theme';
import './portfolio.css';

const Plimsoll = lazy(() => import('../App'));
const zero = { x: 0, y: 0 };
const limit = (value: number) => Math.max(-70, Math.min(70, value));

export default function Portfolio({ introEnabled = true }: { introEnabled?: boolean }) {
  const [route, setRoute] = useState(() => classifyHash(window.location.hash));
  const [theme, setTheme] = useState<PortfolioTheme>(storedTheme);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  const dark = resolveTheme(theme, systemDark) === 'dark';
  const [opening, setOpening] = useState(() => {
    const initial = classifyHash(window.location.hash);
    return introEnabled && initial.kind === 'public' && initial.view === 'home';
  });
  const [settling, setSettling] = useState(false);
  const [sheetIndex, setSheetIndex] = useState(0);
  const [pan, setPan] = useState(zero);
  const [details, setDetails] = useState(true);
  const [inspect, setInspect] = useState(false);
  const [focus, setFocus] = useState({ x: 50, y: 50 });
  const exhibit = useRef<HTMLDivElement>(null);
  const finish = useCallback(() => { setOpening(false); setSettling(false); }, []);
  const beginSettle = useCallback(() => setSettling(true), []);
  const sheet = sheetByIndex(sheetIndex);

  useEffect(() => {
    const update = () => {
      const next = classifyHash(window.location.hash);
      setRoute(next);
      if (next.kind === 'app' || next.view !== 'home') finish();
    };
    window.addEventListener('hashchange', update);
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const change = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    media?.addEventListener?.('change', change);
    return () => { window.removeEventListener('hashchange', update); media?.removeEventListener?.('change', change); };
  }, [finish]);
  useEffect(() => {
    document.title = route.kind === 'app' ? 'Plimsoll · 舰船计算工作台' : 'Y’s Formfield — Tools & Experiments';
    document.documentElement.lang = route.kind === 'app' ? 'zh-CN' : 'en';
    document.documentElement.dataset.formfieldSurface = route.kind;
    if (route.kind === 'public') document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }, [dark, route.kind]);
  useEffect(() => {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* Local preference remains usable without storage. */ }
  }, [theme]);

  const explore = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' && e.buttons === 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    const y = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height));
    setPan({ x: (x - .5) * -90, y: (y - .5) * -60 });
    setFocus({ x: x * 100, y: y * 100 });
  };
  const keyboard = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, [number, number]> = { ArrowLeft: [-15, 0], ArrowRight: [15, 0], ArrowUp: [0, -15], ArrowDown: [0, 15] };
    const move = moves[e.key];
    if (move) { e.preventDefault(); setPan(p => ({ x: limit(p.x + move[0]), y: limit(p.y + move[1]) })); }
    if (e.key === 'Home' || e.key === 'Escape') { setPan(zero); setFocus({ x: 50, y: 50 }); }
  };
  const replay = () => {
    window.location.hash = publicHref('home').slice(1);
    setRoute({ kind: 'public', view: 'home' });
    window.scrollTo({ top: 0, behavior: 'auto' });
    setPan(zero); setFocus({ x: 50, y: 50 }); setSettling(false); setOpening(true);
  };
  const publicActive = route.kind === 'public';
  const about = publicActive && route.view === 'about';

  return <>
    <div className="ff-shell" data-ff-theme={dark ? 'dark' : 'light'} data-opening={opening} data-settling={settling} hidden={!publicActive}>
      <header className="ff-header" inert={opening}>
        <a className="ff-wordmark" href={publicHref('home')} aria-label="Y’s Formfield home">Y’s <span>Formfield</span><i aria-hidden="true">↗</i></a>
        <nav aria-label="Main navigation"><a href={publicHref('home')} aria-current={!about ? 'page' : undefined}>Work <span>01</span></a><a href={publicHref('about')} aria-current={about ? 'page' : undefined}>About</a></nav>
        <label className="ff-theme"><span className="ff-theme-symbol" aria-hidden="true">◐</span><select aria-label="Color theme" value={theme} onChange={e => setTheme(e.target.value as PortfolioTheme)}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></label>
      </header>

      <main className="ff-main" inert={opening}>
        <section className="ff-home" hidden={about} aria-label="Selected work">
          <div className="ff-exhibit-label"><span><i className="ff-live-dot" />SELECTED WORK</span><span>TOOLS & EXPERIMENTS / VOL. 01</span></div>
          <div className="ff-exhibit" ref={exhibit} role="group" tabIndex={0} aria-label="Interactive top-view drawing. Use arrow keys to explore, Home to reset." onKeyDown={keyboard} onPointerMove={explore} onPointerDown={e => { if (e.pointerType !== 'mouse') e.currentTarget.setPointerCapture(e.pointerId); explore(e); }}>
            <div className="ff-art-scene"><Artwork sheet={sheet} dark={dark} pan={pan} details={details} /></div>
            {inspect && <div className="ff-inspection" style={{ left: `${focus.x}%`, top: `${focus.y}%` }} aria-hidden="true"><span>REFERENCE {sheet.id}</span></div>}
            <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
            <div className="ff-exhibit-note"><span>PLIMSOLL / DRAWING {sheet.id}</span><span>{inspect ? 'INSPECTION ON' : 'MOVE TO EXPLORE'}</span></div>
          </div>

          <div className="ff-work-info">
            <div className="ff-work-heading"><span className="ff-work-index">01 /</span><div><h1>Plimsoll</h1><p>Naval design, made explorable.</p></div></div>
            <a className="ff-explore-link" href={APP_ENTRY_LINK}>EXPLORE PROJECT <span aria-hidden="true">↗</span></a>
          </div>
          <div className="ff-work-controls">
            <div className="ff-sheet-picker" role="group" aria-label="Reference drawing"><span>REFERENCE</span>{PLAN_SHEETS.map((s, i) => <button key={s.id} onClick={() => { setSheetIndex(i); setPan(zero); }} aria-label={s.label} aria-pressed={i === sheetIndex}>{s.shortLabel}</button>)}</div>
            <div className="ff-exhibit-tools"><button onClick={() => setDetails(v => !v)} aria-pressed={details}>Geometry {details ? 'On' : 'Off'}</button><button onClick={() => setInspect(v => !v)} aria-pressed={inspect}>Inspect {inspect ? 'On' : 'Off'}</button><button onClick={() => { setPan(zero); setFocus({ x: 50, y: 50 }); }}>Reset view <span aria-hidden="true">↺</span></button></div>
          </div>
        </section>

        <section className="ff-about" hidden={!about}>
          <span className="ff-eyebrow">ABOUT THE COLLECTION</span><h1>A field for<br />useful ideas.</h1>
          <p>Y’s Formfield is Yang Duanming’s collection of tools and experiments. A place to build, explore, and keep making things better.</p>
          <div className="ff-about-work"><span>FIRST WORK / 01</span><h2>Plimsoll</h2><p>A naval design and analysis tool for studying ship projects, loading conditions, stability, resistance, and simplified damage.</p><a href={publicHref('home')}>BACK TO THE WORK <span aria-hidden="true">↗</span></a></div>
        </section>
      </main>

      <footer className="ff-footer" inert={opening}><span>BUILT BY YANG DUANMING</span><span>PRECISE. MODERN. INTERACTIVE.</span><button onClick={replay}>REPLAY INTRO <span aria-hidden="true">↗</span></button></footer>
      {opening && publicActive && <Splash sheet={sheet} target={exhibit} dark={dark} details={details} onDone={finish} onSettle={beginSettle} />}
    </div>
    {route.kind === 'app' && <div className="ff-tool-shell"><a className="ff-tool-return" href={publicHref('home')}>↖ Y’s Formfield</a><Suspense fallback={<div className="app-loading">Opening Plimsoll…</div>}><Plimsoll /></Suspense></div>}
  </>;
}

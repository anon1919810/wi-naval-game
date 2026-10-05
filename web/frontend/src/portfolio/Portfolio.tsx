import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import { Artwork, artworkTransform, GEOMETRY_PARALLAX, maskTrackTransform } from './Artwork';
import { readyImage, type ImageCache } from './images';
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
    return introEnabled && initial.kind === 'public' && initial.view === 'home' && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
  });
  const [settling, setSettling] = useState(false);
  const [sheetIndex, setSheetIndex] = useState(0);
  const [details, setDetails] = useState(true);
  const [inspect, setInspect] = useState(false);
  const pan = useRef(zero);
  const focus = useRef({ x: 50, y: 50 });
  const composition = useRef<SVGGElement>(null);
  const geometry = useRef<SVGGElement>(null);
  const maskTrack = useRef<SVGGElement>(null);
  const inspection = useRef<HTMLDivElement>(null);
  const cursor = useRef<HTMLDivElement>(null);
  const cursorOn = useRef(false);
  const panFrame = useRef(0);
  const imageCache = useRef<ImageCache>(new Map());
  const [readyHref, setReadyHref] = useState<string | null>(null);
  const [imageError, setImageError] = useState(false);
  const [loadAttempt, setLoadAttempt] = useState(0);
  const exhibit = useRef<HTMLDivElement>(null);
  const finish = useCallback(() => { setOpening(false); setSettling(false); }, []);
  const beginSettle = useCallback(() => setSettling(true), []);
  const sheet = sheetByIndex(sheetIndex);
  const publicActive = route.kind === 'public';
  const about = publicActive && route.view === 'about';

  useEffect(() => {
    if (!publicActive || about) return;
    let active = true;
    setReadyHref(null); setImageError(false);
    readyImage(sheet.href, imageCache.current).then(() => {
      if (active) setReadyHref(sheet.href);
    }, () => { if (active) { setImageError(true); finish(); } });
    return () => { active = false; };
  }, [sheet.href, publicActive, about, loadAttempt, finish]);

  useEffect(() => {
    if (!publicActive || about || readyHref !== sheet.href) return;
    const prefetch = () => {
      for (const other of PLAN_SHEETS) if (other.href !== sheet.href) void readyImage(other.href, imageCache.current).catch(() => {});
    };
    if (window.requestIdleCallback) {
      const id = window.requestIdleCallback(prefetch);
      return () => window.cancelIdleCallback(id);
    }
    const timer = window.setTimeout(prefetch, 1500);
    return () => window.clearTimeout(timer);
  }, [readyHref, sheet.href, publicActive, about]);

  useLayoutEffect(() => {
    if (!opening || !publicActive) return;
    const nodes = [document.documentElement, document.body];
    const prior = nodes.map(node => [node.style.getPropertyValue('overflow'), node.style.getPropertyPriority('overflow')]);
    nodes.forEach(node => node.style.setProperty('overflow', 'hidden'));
    const key = (e: globalThis.KeyboardEvent) => { if (e.key === 'Escape') finish(); };
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const change = (e: MediaQueryListEvent) => { if (e.matches) finish(); };
    window.addEventListener('keydown', key);
    media?.addEventListener?.('change', change);
    return () => {
      nodes.forEach((node, i) => { if (prior[i][0]) node.style.setProperty('overflow', prior[i][0], prior[i][1]); else node.style.removeProperty('overflow'); });
      window.removeEventListener('keydown', key); media?.removeEventListener?.('change', change);
    };
  }, [opening, publicActive, finish]);

  const paintPan = useCallback(() => {
    composition.current?.setAttribute('transform', artworkTransform(-12, 1, pan.current));
    geometry.current?.setAttribute('transform', artworkTransform(-12, 1, { x: pan.current.x * GEOMETRY_PARALLAX, y: pan.current.y * GEOMETRY_PARALLAX }));
    maskTrack.current?.setAttribute('transform', maskTrackTransform(pan.current));
    if (inspection.current) { inspection.current.style.left = `${focus.current.x}%`; inspection.current.style.top = `${focus.current.y}%`; }
    if (cursor.current) { cursor.current.hidden = !cursorOn.current; cursor.current.style.left = `${focus.current.x}%`; cursor.current.style.top = `${focus.current.y}%`; }
  }, []);
  const resetPan = useCallback(() => {
    cancelAnimationFrame(panFrame.current); panFrame.current = 0;
    pan.current = zero; focus.current = { x: 50, y: 50 }; paintPan();
  }, [paintPan]);
  useLayoutEffect(() => { resetPan(); return () => cancelAnimationFrame(panFrame.current); }, [sheetIndex, publicActive, about, resetPan]);
  useLayoutEffect(paintPan, [inspect, paintPan]);

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
    if (!publicActive) return;
    const root = document.documentElement;
    const meta = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
    const previous = meta?.content;
    const scheme = root.style.colorScheme;
    root.style.colorScheme = dark ? 'dark' : 'light';
    if (meta) meta.content = dark ? '#101110' : '#f6f6f3';
    return () => { root.style.colorScheme = scheme; if (meta && previous !== undefined) meta.content = previous; };
  }, [dark, publicActive]);
  useEffect(() => {
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* Local preference remains usable without storage. */ }
  }, [theme]);

  const explore = (e: PointerEvent<HTMLDivElement>) => {
    if (e.pointerType !== 'mouse' && e.buttons === 0) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    const y = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height));
    pan.current = { x: (x - .5) * -90, y: (y - .5) * -60 };
    focus.current = { x: x * 100, y: y * 100 };
    if (!panFrame.current) panFrame.current = requestAnimationFrame(() => { panFrame.current = 0; paintPan(); });
  };
  const keyboard = (e: KeyboardEvent<HTMLDivElement>) => {
    const moves: Record<string, [number, number]> = { ArrowLeft: [-15, 0], ArrowRight: [15, 0], ArrowUp: [0, -15], ArrowDown: [0, 15] };
    const move = moves[e.key];
    if (move) { e.preventDefault(); cancelAnimationFrame(panFrame.current); panFrame.current = 0; pan.current = { x: limit(pan.current.x + move[0]), y: limit(pan.current.y + move[1]) }; paintPan(); }
    if (e.key === 'Home' || e.key === 'Escape') resetPan();
  };
  const replay = () => {
    window.location.hash = publicHref('home').slice(1);
    setRoute({ kind: 'public', view: 'home' });
    window.scrollTo({ top: 0, behavior: 'auto' });
    resetPan(); setSettling(false); setLoadAttempt(v => v + 1);
    setOpening(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  };

  const toggleTheme = useCallback((e: MouseEvent<HTMLButtonElement>) => {
    const next = dark ? 'light' : 'dark';
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduce || typeof document.startViewTransition !== 'function') { setTheme(next); return; }
    // Keyboard-triggered clicks report 0,0 — fall back to the button's own center.
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX || rect.left + rect.width / 2;
    const y = e.clientY || rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    const transition = document.startViewTransition(() => { flushSync(() => setTheme(next)); });
    transition.ready.then(() => {
      document.documentElement.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`] },
        { duration: 560, easing: 'cubic-bezier(.22,1,.36,1)', pseudoElement: '::view-transition-new(root)' },
      );
    }, () => {});
  }, [dark]);

  return <>
    <div className="ff-shell" data-ff-theme={dark ? 'dark' : 'light'} data-opening={opening} data-settling={settling} hidden={!publicActive}>
      <header className="ff-header" inert={opening}>
        <a className="ff-wordmark" href={publicHref('home')} aria-label="Y’s Formfield home">Y’s <span>Formfield</span><i aria-hidden="true">↗</i></a>
        <nav aria-label="Main navigation"><a href={publicHref('home')} aria-current={!about ? 'page' : undefined}>Work <span>01</span></a><a href={publicHref('about')} aria-current={about ? 'page' : undefined}>About</a></nav>
        <button className="ff-theme" onClick={toggleTheme} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}><span className="ff-theme-symbol" aria-hidden="true">◐</span><span className="ff-theme-mode">{dark ? 'DARK' : 'LIGHT'}</span></button>
      </header>

      <main className="ff-main" inert={opening}>
        <section className="ff-home" hidden={about} aria-label="Selected work">
          <div className="ff-exhibit-label"><span><i className="ff-live-dot" />SELECTED WORK</span><span>TOOLS & EXPERIMENTS / VOL. 01</span></div>
          <div className="ff-exhibit" ref={exhibit} role="group" tabIndex={0} aria-label="Interactive top-view drawing. Use arrow keys to explore, Home to reset." onKeyDown={keyboard} onPointerMove={explore} onPointerEnter={e => { if (e.pointerType === 'mouse') { cursorOn.current = true; paintPan(); } }} onPointerLeave={() => { cursorOn.current = false; paintPan(); }} onPointerDown={e => { if (e.pointerType !== 'mouse') e.currentTarget.setPointerCapture(e.pointerId); explore(e); }}>
            <div className="ff-art-scene"><Artwork compositionRef={composition} geometryRef={geometry} maskRef={maskTrack} sheet={sheet} dark={dark} details={details} /></div>
            {inspect && <div ref={inspection} className="ff-inspection" aria-hidden="true"><span>REFERENCE {sheet.id}</span></div>}
            {!inspect && <div ref={cursor} className="ff-cursor" aria-hidden="true" hidden><span className="ff-cursor-breath" /><i /></div>}
            <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
            <div className="ff-exhibit-note"><span>PLIMSOLL / DRAWING {sheet.id}</span><span>{inspect ? 'INSPECTION ON' : 'MOVE TO EXPLORE'}</span></div>
          </div>

          <div className="ff-work-info">
            <div className="ff-work-heading"><span className="ff-work-index">01 /</span><div><h1>Plimsoll</h1><p>Naval design, made explorable.</p></div></div>
            <a className="ff-explore-link" href={APP_ENTRY_LINK}>EXPLORE PROJECT <span aria-hidden="true">↗</span></a>
          </div>
          <div className="ff-work-controls">
            <div className="ff-sheet-picker" role="group" aria-label="Reference drawing"><span>REFERENCE</span>{PLAN_SHEETS.map((s, i) => <button key={s.id} onClick={() => { setSheetIndex(i); resetPan(); }} aria-label={s.label} aria-pressed={i === sheetIndex}>{s.shortLabel}</button>)}</div>
            <div className="ff-exhibit-tools"><button onClick={() => setDetails(v => !v)} aria-pressed={details}>Geometry {details ? 'On' : 'Off'}</button><button onClick={() => setInspect(v => !v)} aria-pressed={inspect}>Inspect {inspect ? 'On' : 'Off'}</button><button onClick={resetPan}>Reset view <span aria-hidden="true">↺</span></button></div>
          </div>
          {imageError && <p className="ff-image-error" role="alert">The reference could not be loaded. Choose another reference or use Replay Intro to retry.</p>}
        </section>

        <section className="ff-about" hidden={!about}>
          <span className="ff-eyebrow">ABOUT THE COLLECTION</span><h1>A field for<br />useful ideas.</h1>
          <p>Y’s Formfield is Yang Duanming’s collection of tools and experiments. A place to build, explore, and keep making things better.</p>
          <div className="ff-about-work"><span>FIRST WORK / 01</span><h2>Plimsoll</h2><p>A naval design and analysis tool for studying ship projects, loading conditions, stability, resistance, and simplified damage.</p><a href={publicHref('home')}>BACK TO THE WORK <span aria-hidden="true">↗</span></a></div>
        </section>
      </main>

      <footer className="ff-footer" inert={opening}><span>BUILT BY YANG DUANMING</span><span>PRECISE. MODERN. INTERACTIVE.</span><button onClick={replay}>REPLAY INTRO <span aria-hidden="true">↗</span></button></footer>
      {opening && publicActive && (readyHref === sheet.href
        ? <Splash sheet={sheet} target={exhibit} dark={dark} details={details} onDone={finish} onSettle={beginSettle} />
        : <div className="ff-splash ff-image-wait" role="status" aria-label="Loading reference"><span>PREPARING THE DRAWING</span><button className="ff-skip" onClick={finish}>SKIP INTRO <span>↗</span></button></div>)}
    </div>
    {route.kind === 'app' && <div className="ff-tool-shell"><a className="ff-tool-return" href={publicHref('home')}>↖ Y’s Formfield</a><Suspense fallback={<div className="app-loading">Opening Plimsoll…</div>}><Plimsoll /></Suspense></div>}
  </>;
}

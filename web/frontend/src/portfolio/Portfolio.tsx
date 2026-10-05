import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import { Artwork, artworkTransform, GEOMETRY_PARALLAX, maskTrackTransform } from './Artwork';
import { readyImage, type ImageCache } from './images';
import { lensFrame, RESTING_VIEW_BOX, type ExhibitRect } from './lens';
import { Splash } from './Splash';
import { PLAN_SHEETS, sheetByIndex } from './plans';
import { APP_ENTRY_LINK, classifyHash, publicHref } from './routes';
import { resolveTheme, storedTheme, THEME_KEY, type PortfolioTheme } from './theme';
import './portfolio.css';

const Plimsoll = lazy(() => import('../App'));
const zero = { x: 0, y: 0 };
const limit = (value: number) => Math.max(-70, Math.min(70, value));
const inside = (value: number) => Math.max(0, Math.min(100, value));
/** Pan step, in composition units, for the explore keys. */
const PAN_MOVES: Record<string, [number, number]> = { ArrowLeft: [-15, 0], ArrowRight: [15, 0], ArrowUp: [0, -15], ArrowDown: [0, 15] };
/** Sample step, in per cent of the exhibit, for the inspect keys. */
const SAMPLE_MOVES: Record<string, [number, number]> = { ArrowLeft: [-4, 0], ArrowRight: [4, 0], ArrowUp: [0, -4], ArrowDown: [0, 4] };

export default function Portfolio({ introEnabled = true }: { introEnabled?: boolean }) {
  const [route, setRoute] = useState(() => classifyHash(window.location.hash));
  const [theme, setTheme] = useState<PortfolioTheme>(storedTheme);
  const [systemDark, setSystemDark] = useState(() => window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false);
  const resolved = resolveTheme(theme, systemDark);
  const dark = resolved === 'dark';
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
  const lens = useRef<HTMLDivElement>(null);
  const lensView = useRef<SVGSVGElement>(null);
  const lensComposition = useRef<SVGGElement>(null);
  const lensGeometry = useRef<SVGGElement>(null);
  const lensMask = useRef<SVGGElement>(null);
  const cursor = useRef<HTMLDivElement>(null);
  const hovered = useRef(false);
  const keysOn = useRef(false);
  const inspectOn = useRef(false);
  const still = useRef(window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false);
  const exhibitBox = useRef<ExhibitRect>({ left: 0, top: 0, width: 0, height: 0 });
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

  /**
   * One frame of direct-DOM painting, shared by the exhibit and the lens. Reads
   * the exhibit rectangle at most once per frame (never during render), then
   * writes the layer transforms, the lens viewBox and the cursor straight to the
   * DOM: React never commits for pointer, keyboard or resize work.
   */
  const paint = useCallback(() => {
    const box = exhibit.current?.getBoundingClientRect();
    if (box) exhibitBox.current = { left: box.left, top: box.top, width: box.width, height: box.height };
    const vesselTransform = artworkTransform(-12, 1, pan.current);
    const plateTransform = artworkTransform(-12, 1, { x: pan.current.x * GEOMETRY_PARALLAX, y: pan.current.y * GEOMETRY_PARALLAX });
    const trackTransform = maskTrackTransform(pan.current);
    for (const node of [composition.current, lensComposition.current]) node?.setAttribute('transform', vesselTransform);
    for (const node of [geometry.current, lensGeometry.current]) node?.setAttribute('transform', plateTransform);
    for (const node of [maskTrack.current, lensMask.current]) node?.setAttribute('transform', trackTransform);
    const rect = exhibitBox.current;
    if (cursor.current) {
      // Mouse only, and never beside the lens: the lens is the inspect cursor.
      cursor.current.hidden = !hovered.current || inspectOn.current;
      cursor.current.style.left = `${focus.current.x}%`;
      cursor.current.style.top = `${focus.current.y}%`;
    }
    const lensNode = lens.current;
    if (!lensNode) return;
    const frame = lensFrame(rect, focus.current.x / 100, focus.current.y / 100);
    // The lens follows the pointer or the keyboard and is gone when neither is
    // asking for it, so nothing is ever left floating offstage. Its geometry is
    // still written while hidden, so it is correct the instant it appears.
    lensNode.hidden = !(hovered.current || keysOn.current);
    lensNode.style.width = lensNode.style.height = `${frame.size}px`;
    lensNode.style.transform = `translate(${frame.cx - frame.size / 2}px, ${frame.cy - frame.size / 2}px)`;
    lensView.current?.setAttribute('viewBox', frame.viewBox);
    // The viewBox centres the sampled detail even when the lens itself is
    // clamped, so its reticle must stay at the centre of the magnified image.
  }, []);
  const schedule = useCallback(() => {
    if (!panFrame.current) panFrame.current = requestAnimationFrame(() => { panFrame.current = 0; paint(); });
  }, [paint]);
  const reset = useCallback(() => {
    cancelAnimationFrame(panFrame.current); panFrame.current = 0;
    pan.current = zero; focus.current = { x: 50, y: 50 };
    paint();
  }, [paint]);
  useLayoutEffect(() => { reset(); return () => cancelAnimationFrame(panFrame.current); }, [sheetIndex, publicActive, about, reset]);
  // Re-register the lens and cursor nodes and restate their visibility whenever
  // anything that changes the rendered surface changes.
  useLayoutEffect(() => { inspectOn.current = inspect; paint(); }, [inspect, sheet, dark, details, paint]);
  useEffect(() => {
    if (!publicActive) return;
    const node = exhibit.current;
    if (!node) return;
    const update = () => schedule();
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(update) : null;
    observer?.observe(node);
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, { passive: true });
    return () => { observer?.disconnect(); window.removeEventListener('resize', update); window.removeEventListener('scroll', update); };
  }, [publicActive, schedule]);

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
    keysOn.current = false;
    const r = e.currentTarget.getBoundingClientRect();
    if (!r.width || !r.height) return;
    const x = Math.max(0, Math.min(1, (e.clientX - r.left) / r.width));
    const y = Math.max(0, Math.min(1, (e.clientY - r.top) / r.height));
    // Reduced motion keeps hover-pan still; the sample still follows the pointer.
    if (!still.current) pan.current = { x: (x - .5) * -90, y: (y - .5) * -60 };
    focus.current = { x: x * 100, y: y * 100 };
    schedule();
  };
  const keyboard = (e: KeyboardEvent<HTMLDivElement>) => {
    keysOn.current = true;
    // Inspect mode hands the arrows to the sample; explore mode keeps panning.
    const move = (inspectOn.current ? SAMPLE_MOVES : PAN_MOVES)[e.key];
    if (move) {
      e.preventDefault();
      cancelAnimationFrame(panFrame.current); panFrame.current = 0;
      if (inspectOn.current) focus.current = { x: inside(focus.current.x + move[0]), y: inside(focus.current.y + move[1]) };
      else pan.current = { x: limit(pan.current.x + move[0]), y: limit(pan.current.y + move[1]) };
      paint();
    }
    if (e.key === 'Home') {
      e.preventDefault();
      if (inspectOn.current) { focus.current = { x: 50, y: 50 }; paint(); } else reset();
    }
    // Escape leaves inspection, or resets the view when nothing is inspected.
    if (e.key === 'Escape') { e.preventDefault(); if (inspectOn.current) setInspect(false); else reset(); }
  };
  const replay = () => {
    window.location.hash = publicHref('home').slice(1);
    setRoute({ kind: 'public', view: 'home' });
    window.scrollTo({ top: 0, behavior: 'auto' });
    reset(); setSettling(false); setLoadAttempt(v => v + 1);
    setOpening(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  };

  /** Compact companion to the primary toggle: follow the OS, or pin what it resolves to now. */
  const followSystem = useCallback(() => setTheme(previous => (previous === 'system' ? resolved : 'system')), [resolved]);

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
        <div className="ff-theme-group">
          <button className="ff-theme" onClick={toggleTheme} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}><span className="ff-theme-symbol" aria-hidden="true">◐</span><span className="ff-theme-mode">{dark ? 'DARK' : 'LIGHT'}</span></button>
          <button className="ff-theme-system" onClick={followSystem} aria-pressed={theme === 'system'} title="Follow system theme">SYSTEM</button>
        </div>
      </header>

      <main className="ff-main" inert={opening}>
        <section className="ff-home" hidden={about} aria-label="Selected work">
          <div className="ff-exhibit-label"><span><i className="ff-live-dot" />SELECTED WORK</span><span>TOOLS & EXPERIMENTS / VOL. 01</span></div>
          <div className="ff-exhibit" ref={exhibit} role="group" tabIndex={0} aria-label={inspect ? 'Interactive top-view drawing. Inspection on: arrow keys move the 2× lens over the same rendered scan, Home resets the lens, Escape leaves inspection.' : 'Interactive top-view drawing. Use arrow keys to explore, Home to reset.'} onKeyDown={keyboard} onBlur={() => { keysOn.current = false; paint(); }} onPointerMove={explore} onPointerEnter={e => { if (e.pointerType === 'mouse') { hovered.current = true; paint(); } }} onPointerLeave={() => { hovered.current = false; paint(); }} onPointerDown={e => { if (e.pointerType !== 'mouse') e.currentTarget.setPointerCapture(e.pointerId); explore(e); }}>
            <div className="ff-art-scene"><Artwork compositionRef={composition} geometryRef={geometry} maskRef={maskTrack} sheet={sheet} dark={dark} details={details} /></div>
            {inspect && <div ref={lens} className="ff-lens" aria-hidden="true">
              <span className="ff-lens-port">
                {/* The same Artwork composition, narrowed by viewBox: no second renderer, no second tone. */}
                <svg ref={lensView} className="ff-lens-view" viewBox={RESTING_VIEW_BOX} preserveAspectRatio="xMidYMid meet"><Artwork pixelFrame compositionRef={lensComposition} geometryRef={lensGeometry} maskRef={lensMask} sheet={sheet} dark={dark} details={details} /></svg>
                <span className="ff-lens-mark" />
              </span>
              <span className="ff-lens-label">2×<i>REF {sheet.id}</i></span>
            </div>}
            {!inspect && <div ref={cursor} className="ff-cursor" aria-hidden="true" hidden><span className="ff-cursor-cross" /><i /></div>}
            <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
            <div className="ff-exhibit-note"><span>PLIMSOLL / DRAWING {sheet.id}</span><span>{inspect ? `INSPECT 2× / REF ${sheet.id}` : 'MOVE TO EXPLORE'}</span></div>
          </div>

          <div className="ff-work-info">
            <div className="ff-work-heading"><span className="ff-work-index">01 /</span><div><h1>Plimsoll</h1><p>Naval design, made explorable.</p></div></div>
            <a className="ff-explore-link" href={APP_ENTRY_LINK}>EXPLORE PROJECT <span aria-hidden="true">↗</span></a>
          </div>
          <div className="ff-work-controls">
            <div className="ff-sheet-picker" role="group" aria-label="Reference drawing"><span>REFERENCE</span>{PLAN_SHEETS.map((s, i) => <button key={s.id} onClick={() => { setSheetIndex(i); reset(); }} aria-label={s.label} aria-pressed={i === sheetIndex}>{s.shortLabel}</button>)}</div>
            <div className="ff-exhibit-tools"><button onClick={() => setDetails(v => !v)} aria-pressed={details}>Geometry {details ? 'On' : 'Off'}</button><button onClick={() => setInspect(v => !v)} aria-pressed={inspect}>Inspect {inspect ? 'On' : 'Off'}</button><button onClick={reset}>Reset view <span aria-hidden="true">↺</span></button></div>
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

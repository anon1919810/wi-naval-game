import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import { Artwork, artworkTransform, GEOMETRY_PARALLAX, maskTrackTransform } from './Artwork';
import { readyImage, type ImageCache } from './images';
import { lensFrame, RESTING_VIEW_BOX, type ExhibitRect } from './lens';
import { Splash } from './Splash';
import { PLAN_SHEETS, sheetByIndex } from './plans';
import { APP_ENTRY_LINK, classifyHash, publicHref, type PortfolioRoute } from './routes';
import { resolveTheme, storedTheme, THEME_KEY, type PortfolioTheme } from './theme';
import { animateTheme, cancelTransitions, runTransition, TRANSITION_MS, transitionsActive, type TransitionKind, type TransitionOptions } from './transitions';
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
  /**
   * `sheetIndex` is what the exhibit is actually showing. `requested` is what the
   * visitor has already pressed: the button answers at once, the bitmap only
   * follows once it has decoded. The two are deliberately separate so a slow or
   * failed sheet can never blank or replace the drawing on screen.
   */
  const [requested, setRequested] = useState<number | null>(null);
  const [switchError, setSwitchError] = useState<number | null>(null);
  const [switching, setSwitching] = useState(false);
  const sheetRequest = useRef(0);
  const busy = useRef(false);
  const sheetIndexRef = useRef(0);
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
  const cta = useRef<HTMLAnchorElement>(null);
  const homeHeading = useRef<HTMLHeadingElement>(null);
  const aboutHeading = useRef<HTMLHeadingElement>(null);
  const cut = useRef(0);
  /** The route React has actually committed, which the async listener compares against. */
  const committed = useRef(route);
  const finish = useCallback(() => { setOpening(false); setSettling(false); }, []);

  /**
   * Every page-level state change goes through here. A native cut also owns the
   * exhibit for its duration: exploration, the lens and the blueprint cursor are
   * withdrawn, because all three sample a surface that is being cut away. The
   * token means a superseded cut can never leave the exhibit frozen afterwards.
   */
  const change = useCallback(async (kind: TransitionKind, update: () => void, options?: TransitionOptions) => {
    if (kind !== 'sheet' && kind !== 'sheet-back') {
      sheetRequest.current++;
      setRequested(null);
    }
    const mine = ++cut.current;
    const native = kind !== 'page' && kind !== 'page-back';
    if (native) { busy.current = true; setSwitching(true); }
    try { await runTransition(kind, update, options); }
    finally { if (native && cut.current === mine) { busy.current = false; setSwitching(false); } }
  }, []);

  /** Drop whatever is in flight — a cut, a pending request, the busy flag. */
  const retire = useCallback(() => {
    sheetRequest.current++;
    setRequested(null);
    cut.current++;
    cancelTransitions();
    busy.current = false;
    setSwitching(false);
  }, []);
  const beginSettle = useCallback(() => setSettling(true), []);
  const sheet = sheetByIndex(sheetIndex);
  const marked = requested ?? sheetIndex;
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
  useLayoutEffect(() => { sheetIndexRef.current = sheetIndex; }, [sheetIndex]);
  useLayoutEffect(() => { reset(); return () => cancelAnimationFrame(panFrame.current); }, [sheetIndex, reset]);
  // Leaving for About or for the application is not a new reference and not an
  // explicit reset, so the view is only repainted on the way back — never
  // recentred behind the visitor's back.
  useLayoutEffect(() => { if (publicActive && !about) paint(); }, [publicActive, about, paint]);

  /**
   * Focus only ever moves when the browser would otherwise have stranded it: the
   * element that held it just unmounted, or is hidden by the page that replaced
   * it. The persistent header keeps the focus through a normal nav click, so the
   * heading is only claimed when nothing visible still holds it. Coming back
   * from the workspace returns focus to the way out of the exhibit.
   */
  const restoreFocus = useCallback((next: PortfolioRoute, returningFromTool: boolean) => {
    if (next.kind === 'app') return;
    const active = document.activeElement as HTMLElement | null;
    const stranded = !active || active === document.body || !active.isConnected || !!active.closest('[hidden]');
    if (!stranded) return;
    const target = returningFromTool ? cta.current : (next.view === 'about' ? aboutHeading.current : homeHeading.current);
    target?.focus({ preventScroll: true });
  }, []);

  /**
   * The hash is the single route trigger: an anchor's own navigation is left
   * alone, so Back, Forward, a typed URL and a modified click all arrive here
   * through the same `hashchange`. `applyRoute` therefore never writes the hash
   * itself, which is what keeps one navigation to one transition.
   */
  const applyRoute = useCallback((next: PortfolioRoute) => {
    const current = committed.current;
    const same = current.kind === next.kind
      && (current.kind === 'app' || next.kind === 'app' || current.view === next.view);
    if (same) {
      // Already there, but a transition may still be in flight toward here. It
      // is now redundant, so it is retired rather than left to finish.
      if (transitionsActive()) retire();
      return;
    }
    // Retire the previous route's work *before* starting this one: the pending
    // reference request, the busy flag and any animation still running.
    sheetRequest.current++;
    setRequested(null);
    setSwitchError(null);
    retire();
    const returningFromTool = current.kind === 'app' && next.kind === 'public';
    if (next.kind === 'app' || next.view !== 'home') finish();
    // Leaving and re-entering the workspace are the same geometric move, only
    // in opposite directions.
    const kind: TransitionKind = next.kind === 'app' ? 'tool'
      : returningFromTool ? 'tool-back'
      : (next.view === 'about' ? 'page' : 'page-back');
    void change(kind, () => {
      committed.current = next;
      flushSync(() => setRoute(next));
      restoreFocus(next, returningFromTool);
    });
  }, [change, finish, restoreFocus, retire]);

  /**
   * Decode-gated reference selection. Pressing a reference marks it immediately;
   * the drawing is only replaced once its bitmap has actually decoded, and only
   * then does the 360 ms diagonal cut run. There is no queue: a newer press
   * retires the pending decode, a route change or unmount retires it too, and a
   * sheet that fails to load leaves the current drawing on the exhibit.
   */
  const chooseReference = useCallback((index: number) => {
    // A press always retires whatever came before, including a press on the
    // sheet that is already displayed: that cancels a pending request instead of
    // letting a stale decode swap the artwork afterwards.
    sheetRequest.current++;
    retire();
    if (index === sheetIndexRef.current) {
      setRequested(null);
      setSwitchError(null);
      return;
    }
    setRequested(index);
    setSwitchError(null);
    const token = sheetRequest.current;
    void readyImage(PLAN_SHEETS[index].href, imageCache.current).then(() => {
      if (token !== sheetRequest.current) return;
      const kind: TransitionKind = index > sheetIndexRef.current ? 'sheet' : 'sheet-back';
      return change(kind, () => {
        if (token !== sheetRequest.current) return;
        flushSync(() => { setSheetIndex(index); setRequested(null); });
      });
    }, () => {
      if (token !== sheetRequest.current) return;
      setRequested(null);
      setSwitchError(index);
    });
  }, [change, retire]);
  // Re-register the lens and cursor nodes and restate their visibility whenever
  // anything that changes the rendered surface changes.
  useLayoutEffect(() => { inspectOn.current = inspect; paint(); }, [inspect, sheet, dark, details, paint]);
  // The reduced-motion preference is read live: turning it on mid-session stops
  // the hover-pan without a reload, and retires whatever animation is running,
  // because motion the visitor has just opted out of should not continue.
  useEffect(() => {
    const media = window.matchMedia?.('(prefers-reduced-motion: reduce)');
    const change = (e: MediaQueryListEvent) => {
      still.current = e.matches;
      if (e.matches) retire();
    };
    media?.addEventListener?.('change', change);
    return () => { media?.removeEventListener?.('change', change); };
  }, [retire]);

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

  // Retirement happens in `applyRoute` and `replay`, *before* a route change is
  // initiated — never as a reaction to the commit, which would cancel the
  // transition that commit just started.

  useEffect(() => () => {
    sheetRequest.current++;
    retire();
  }, [retire]);

  useEffect(() => {
    const update = () => {
      const next = classifyHash(window.location.hash);
      applyRoute(next);
    };
    window.addEventListener('hashchange', update);
    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const change = (e: MediaQueryListEvent) => {
      if (theme === 'system') retire();
      setSystemDark(e.matches);
    };
    media?.addEventListener?.('change', change);
    return () => { window.removeEventListener('hashchange', update); media?.removeEventListener?.('change', change); };
  }, [applyRoute, retire, theme]);
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
    if (busy.current) return;
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
    // A reference cut owns the exhibit while it runs.
    if (busy.current) return;
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
    // Replay is an explicit restart: it retires every in-flight transition and
    // pending decode before it sets up the intro again.
    sheetRequest.current++;
    retire();
    window.location.hash = publicHref('home').slice(1);
    committed.current = { kind: 'public', view: 'home' };
    flushSync(() => setRoute({ kind: 'public', view: 'home' }));
    window.scrollTo({ top: 0, behavior: 'auto' });
    reset(); setSettling(false); setLoadAttempt(v => v + 1);
    setRequested(null); setSwitchError(null);
    if (busy.current) { busy.current = false; setSwitching(false); }
    setOpening(!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);
  };

  /** Compact companion to the primary toggle: follow the OS, or pin what it resolves to now. */
  const followSystem = useCallback(() => {
    // Following the OS re-resolves the theme from scratch, so any cut in flight
    // is retired rather than left to overwrite the value it just changed.
    retire();
    setTheme(previous => (previous === 'system' ? resolved : 'system'));
  }, [resolved, retire]);

  const toggleTheme = useCallback((e: MouseEvent<HTMLButtonElement>) => {
    const next = dark ? 'light' : 'dark';
    // Keyboard-triggered clicks report 0,0 — fall back to the button's own center.
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX || rect.left + rect.width / 2;
    const y = e.clientY || rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    void change('theme', () => { flushSync(() => setTheme(next)); }, { animate: () => animateTheme({ x, y }, radius) });
  }, [change, dark]);

  /**
   * The workspace module is fetched, never mounted: the lazy factory is the
   * same one React.lazy will call on the app route, so the chunk is already
   * warm and nothing here can reach the API or render the application.
   */
  const prefetchApp = useCallback(() => {
    void import('../App').catch(() => { /* The route retries the same import on its own. */ });
  }, []);

  /**
   * Modified clicks, middle clicks and new tabs keep the browser's own
   * behaviour. Everything else is left to the anchor too: its navigation is the
   * single route trigger, and `applyRoute` runs the transition from the
   * `hashchange` it raises. Interrupting the current route first means a press
   * during another cut is retires rather than queued.
   */
  const enterTool = useCallback((e: MouseEvent<HTMLAnchorElement>) => {
    prefetchApp();
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    finish();
    sheetRequest.current++;
    setRequested(null);
    setSwitchError(null);
    retire();
  }, [finish, prefetchApp, retire]);

  return <>
    <div className="ff-shell" data-ff-theme={dark ? 'dark' : 'light'} data-opening={opening} data-settling={settling} data-switching={switching} hidden={!publicActive}>
      <header className="ff-header" inert={opening}>
        <a className="ff-wordmark" href={publicHref('home')} aria-label="Y’s Formfield home">Y’s <span>Formfield</span><i aria-hidden="true">↗</i></a>
        <div className="ff-theme-group">
          <button className="ff-theme" onClick={toggleTheme} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}><span className="ff-theme-symbol" aria-hidden="true">◐</span><span className="ff-theme-mode">{dark ? 'DARK' : 'LIGHT'}</span></button>
          <button className="ff-theme-system" onClick={followSystem} aria-pressed={theme === 'system'} title="Follow system theme">SYSTEM</button>
        </div>
      </header>

      {/* The rail is a sibling of `main`, not a child of it: the Work/About cut is
          scoped to `.ff-main`, so this navigation is never named, never moves and
          keeps focus across the page change. It stays mounted on both views. */}
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
            <div className="ff-work-heading"><span className="ff-work-index">01 /</span><div><h1 ref={homeHeading} tabIndex={-1}>Plimsoll</h1><p>Naval design, made explorable.</p></div></div>
            <a className="ff-explore-link" ref={cta} href={APP_ENTRY_LINK} onClick={enterTool} onPointerEnter={prefetchApp} onFocus={prefetchApp}>OPEN PLIMSOLL <span aria-hidden="true">↗</span></a>
          </div>
          <div className="ff-work-controls">
            <div className="ff-sheet-picker" role="group" aria-label="Reference drawing"><span>REFERENCE {sheet.shortLabel} / {String(PLAN_SHEETS.length).padStart(2, '0')}</span>{PLAN_SHEETS.map((s, i) => <button key={s.id} onClick={() => chooseReference(i)} aria-label={s.label} aria-pressed={i === marked}>{s.shortLabel}</button>)}</div>
            <div className="ff-exhibit-tools"><button onClick={() => setDetails(v => !v)} aria-pressed={details}>Geometry {details ? 'On' : 'Off'}</button><button onClick={() => setInspect(v => !v)} aria-pressed={inspect}>Inspect {inspect ? 'On' : 'Off'}</button><button onClick={reset}>Reset view <span aria-hidden="true">↺</span></button></div>
          </div>
          {switchError !== null && <p className="ff-image-error" role="alert">Reference {PLAN_SHEETS[switchError].shortLabel} could not be loaded, so {sheet.shortLabel} stays on the exhibit. <button onClick={() => chooseReference(switchError)}>RETRY {PLAN_SHEETS[switchError].shortLabel}</button> or choose another reference.</p>}
          {imageError && <p className="ff-image-error" role="alert">The reference could not be loaded. Choose another reference or use Replay Intro to retry.</p>}
        </section>

        <section className="ff-about" hidden={!about}>
          <span className="ff-eyebrow">ABOUT THE COLLECTION</span><h1 ref={aboutHeading} tabIndex={-1}>A field for<br />useful ideas.</h1>
          <p>Y’s Formfield is Yang Duanming’s collection of tools and experiments. A place to build, explore, and keep making things better.</p>
          <div className="ff-about-work"><span>FIRST WORK / 01</span><h2>Plimsoll</h2><p>A naval design and analysis tool for studying ship projects, loading conditions, stability, resistance, and simplified damage.</p><a href={publicHref('home')}>BACK TO THE WORK <span aria-hidden="true">↗</span></a></div>
        </section>
      </main>

      <nav className="ff-rail" aria-label="Main navigation" inert={opening}>
        <a href={publicHref('home')} aria-current={!about ? 'page' : undefined}>Work <span>01</span></a>
        <a href={publicHref('about')} aria-current={about ? 'page' : undefined}>About</a>
      </nav>

      <footer className="ff-footer" inert={opening}><span>BUILT BY YANG DUANMING</span><span>PRECISE. MODERN. INTERACTIVE.</span><button onClick={replay}>REPLAY INTRO <span aria-hidden="true">↗</span></button></footer>
      {opening && publicActive && (readyHref === sheet.href
        ? <Splash sheet={sheet} target={exhibit} dark={dark} details={details} onDone={finish} onSettle={beginSettle} />
        : <div className="ff-splash ff-image-wait" role="status" aria-label="Loading reference"><span>PREPARING THE DRAWING</span><button className="ff-skip" onClick={finish}>SKIP INTRO <span>↗</span></button></div>)}
    </div>
    {/* The fallback is the workspace's own shell, so the frame morph lands on a
        surface that looks like the destination instead of a bare message. The
        application is still lazy: it mounts only on the committed app route. */}
    {route.kind === 'app' && <div className="ff-tool-shell"><a className="ff-tool-return" href={publicHref('home')}>↖ Y’s Formfield</a><div className="ff-workspace"><Suspense fallback={<div className="app-loading"><span className="brand-mark" />Plimsoll <small>正在加载工作空间</small></div>}><Plimsoll /></Suspense></div></div>}
  </>;
}

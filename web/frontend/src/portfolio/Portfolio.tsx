import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import { AboutContent } from './AboutContent';
import { CONTACT_EMAIL } from './Contact';
import { Artwork, artworkTransform, GEOMETRY_PARALLAX, maskTrackTransform } from './Artwork';
import { readyImage, type ImageCache } from './images';
import { lensFrame, RESTING_VIEW_BOX, type ExhibitRect } from './lens';
import { ProjectDetail } from './ProjectDetail';
import { Splash } from './Splash';
import { SiteGeometry } from './SiteGeometry';
import { PLAN_SHEETS, sheetByIndex } from './plans';
import { APP_ENTRY_LINK, classifyHash, publicHref, WORK_DETAIL_LINK, type PortfolioRoute, type PublicView } from './routes';
import { resolveTheme, storedTheme, THEME_KEY, type PortfolioTheme } from './theme';
import { animateTheme, cancelTransitions, runTransition, TRANSITION_MS, transitionsActive, type TransitionKind, type TransitionOptions } from './transitions';
import './portfolio.css';
import './content.css';
import './exhibit.css';

const Plimsoll = lazy(() => import('../App'));
const zero = { x: 0, y: 0 };
const limit = (value: number) => Math.max(-70, Math.min(70, value));
const inside = (value: number) => Math.max(0, Math.min(100, value));
const isExhibitControl = (target: EventTarget | null) => target instanceof Element && !!target.closest('[data-exhibit-ui]');
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
  const details = true;
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
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const detailCta = useRef<HTMLAnchorElement>(null);
  const cut = useRef(0);
  /**
   * Where the visitor was when they left for the workspace, and how far down the
   * exhibit they had scrolled. A long page replacing a short one must not strand
   * the reader halfway down the new page, so the position is recorded on the way
   * out and re-applied on the way back.
   */
  const publicOrigin = useRef<PublicView>('home');
  const homeScroll = useRef(0);
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
  const detail = publicActive && route.view === 'project';
  /** Work owns the exhibit and its detail; both of them need the reference bitmap. */
  const onWork = publicActive && !about;

  useEffect(() => {
    if (!onWork) return;
    let active = true;
    setReadyHref(null); setImageError(false);
    readyImage(sheet.href, imageCache.current).then(() => {
      if (active) setReadyHref(sheet.href);
    }, () => { if (active) { setImageError(true); finish(); } });
    return () => { active = false; };
  }, [sheet.href, onWork, loadAttempt, finish]);

  useEffect(() => {
    if (!onWork || readyHref !== sheet.href) return;
    const prefetch = () => {
      for (const other of PLAN_SHEETS) if (other.href !== sheet.href) void readyImage(other.href, imageCache.current).catch(() => {});
    };
    if (window.requestIdleCallback) {
      const id = window.requestIdleCallback(prefetch);
      return () => window.cancelIdleCallback(id);
    }
    const timer = window.setTimeout(prefetch, 1500);
    return () => window.clearTimeout(timer);
  }, [readyHref, sheet.href, onWork]);

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
  // recentred behind the visitor's back. The detail keeps the exhibit's state
  // untouched for the same reason.
  useLayoutEffect(() => { if (onWork && !detail) paint(); }, [onWork, detail, paint]);

  /**
   * Focus only ever moves when the browser would otherwise have stranded it: the
   * element that held it just unmounted, or is hidden by the page that replaced
   * it. The persistent header and rail keep the focus through a normal nav click,
   * so the heading is only claimed when nothing visible still holds it. Coming
   * back from the workspace returns focus to the way out of the view it left.
   */
  const restoreFocus = useCallback((next: PortfolioRoute, returningFromTool: boolean) => {
    if (next.kind === 'app') return;
    const active = document.activeElement as HTMLElement | null;
    const stranded = !active || active === document.body || !active.isConnected || !!active.closest('[hidden]');
    if (!stranded) return;
    const fromDetail = next.view === 'project';
    const target = returningFromTool
      ? (fromDetail ? detailCta.current : cta.current)
      : (next.view === 'about' ? aboutHeading.current : fromDetail ? detailHeading.current : homeHeading.current);
    target?.focus({ preventScroll: true });
  }, []);

  /**
   * Every public page is entered at its own top, except the exhibit, which gets
   * back the position it was left at — whether the visitor left it for the
   * detail, for About or for the workspace. The position is read before the
   * transition starts, so the outgoing snapshot still shows the page they were
   * reading. The workspace is a different surface, so it always starts at its top.
   */
  const place = useCallback((next: PortfolioRoute) => {
    const backToExhibit = next.kind === 'public' && next.view === 'home';
    window.scrollTo({ top: backToExhibit ? homeScroll.current : 0, behavior: 'auto' });
  }, []);

  /**
   * The hash is the single route trigger: an anchor's own navigation is left
   * alone, so Back, Forward, a typed URL and a modified click all arrive here
   * through the same `hashchange`. `applyRoute` therefore never writes the hash
   * itself, which is what keeps one navigation to one transition.
   */
  const applyRoute = useCallback((next: PortfolioRoute, immediate = false) => {
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
    // Leaving the exhibit records its scroll position, so every way back lands
    // where the visitor was; leaving for the workspace also records the page, so
    // the return goes there rather than to a fixed one.
    if (current.kind === 'public' && current.view === 'home') homeScroll.current = window.scrollY;
    if (next.kind === 'app' && current.kind === 'public') publicOrigin.current = current.view;
    if (next.kind === 'app' || next.view !== 'home') finish();
    // The artwork morph is the move between the exhibit and its own detail, in
    // either direction. Work/About stays the cheap content-only cut.
    const fromView = current.kind === 'public' ? current.view : null;
    const kind: TransitionKind = next.kind === 'app' ? 'tool'
      : returningFromTool ? 'tool-back'
      : (next.view === 'project' || fromView === 'project') ? 'detail'
      : (next.view === 'about' ? 'page' : 'page-back');
    const commit = () => {
      committed.current = next;
      flushSync(() => setRoute(next));
      place(next);
      restoreFocus(next, returningFromTool);
    };
    if (immediate) commit();
    else void change(kind, commit);
  }, [change, finish, place, restoreFocus, retire]);

  // A preference change can cancel a native capture before its route callback
  // runs. Keep the requested URL authoritative, then apply the preference.
  // Route supersession and unmount still use retire() to discard obsolete work.
  const settleRequestedRoute = useCallback(() => {
    retire();
    applyRoute(classifyHash(window.location.hash), true);
  }, [applyRoute, retire]);

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
    settleRequestedRoute();
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
  }, [change, settleRequestedRoute]);
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
      if (e.matches) settleRequestedRoute();
    };
    media?.addEventListener?.('change', change);
    return () => { media?.removeEventListener?.('change', change); };
  }, [settleRequestedRoute]);

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
      if (theme === 'system') settleRequestedRoute();
      setSystemDark(e.matches);
    };
    media?.addEventListener?.('change', change);
    return () => { window.removeEventListener('hashchange', update); media?.removeEventListener?.('change', change); };
  }, [applyRoute, settleRequestedRoute, theme]);
  useEffect(() => {
    document.title = route.kind === 'app' ? 'Plimsoll · 舰船计算工作台'
      : route.view === 'project' ? 'Plimsoll — Y’s Formfield'
      : 'Y’s Formfield — Tools & Experiments';
    document.documentElement.lang = route.kind === 'app' ? 'zh-CN' : 'en';
    document.documentElement.dataset.formfieldSurface = route.kind;
    if (route.kind === 'public') document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  }, [dark, route]);
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
    if (isExhibitControl(e.target)) { hovered.current = false; keysOn.current = false; paint(); return; }
    if (busy.current) return;
    if (e.pointerType !== 'mouse' && e.buttons === 0) return;
    hovered.current = e.pointerType === 'mouse';
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
    if (e.target !== e.currentTarget) return;
    // A reference cut owns the exhibit while it runs.
    if (busy.current) return;
    // Inspect mode hands the arrows to the sample; explore mode keeps panning.
    const move = (inspectOn.current ? SAMPLE_MOVES : PAN_MOVES)[e.key];
    if (!move && e.key !== 'Home' && e.key !== 'Escape') return;
    keysOn.current = true;
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
    settleRequestedRoute();
    setTheme(previous => (previous === 'system' ? resolved : 'system'));
  }, [resolved, settleRequestedRoute]);

  const toggleTheme = useCallback((e: MouseEvent<HTMLButtonElement>) => {
    settleRequestedRoute();
    const next = dark ? 'light' : 'dark';
    // Keyboard-triggered clicks report 0,0 — fall back to the button's own center.
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX || rect.left + rect.width / 2;
    const y = e.clientY || rect.top + rect.height / 2;
    const radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
    void change('theme', () => { flushSync(() => setTheme(next)); }, { animate: () => animateTheme({ x, y }, radius) });
  }, [change, dark, settleRequestedRoute]);

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
   * `hashchange` it raises. Retirement belongs to that route change: a repeated
   * click on the same hash must not cancel a pending entry with no new trigger.
   */
  const enterTool = useCallback((e: MouseEvent<HTMLAnchorElement>) => {
    prefetchApp();
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    finish();
  }, [finish, prefetchApp]);

  const withdrawDrawingCursor = () => { hovered.current = false; keysOn.current = false; paint(); };

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
          keeps focus across the page change. It stays mounted on every view. */}
      <main className="ff-main" inert={opening}>
        <section className="ff-home" hidden={!onWork || detail} aria-label="Selected work">
          <div className="ff-exhibit-label"><span><i className="ff-live-dot" />SELECTED WORK</span><span>TOOLS & EXPERIMENTS / VOL. 01</span></div>
          <div className="ff-exhibit" ref={exhibit} role="group" tabIndex={0} aria-label={inspect ? 'Interactive top-view drawing. Inspection on: arrow keys move the 2× lens over the same rendered scan, Home resets the lens, Escape leaves inspection.' : 'Interactive top-view drawing. Use arrow keys to explore, Home to reset.'} onKeyDown={keyboard} onBlur={() => { keysOn.current = false; paint(); }} onPointerMove={explore} onPointerEnter={e => { if (isExhibitControl(e.target)) withdrawDrawingCursor(); else if (e.pointerType === 'mouse') { hovered.current = true; paint(); } }} onPointerLeave={() => { hovered.current = false; paint(); }} onPointerDown={e => { if (isExhibitControl(e.target)) return; if (e.pointerType !== 'mouse') e.currentTarget.setPointerCapture(e.pointerId); explore(e); }}>
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
            <button className="ff-board-icon ff-board-inspect" data-exhibit-ui onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor} onClick={() => setInspect(v => !v)} aria-label={`Inspect ${inspect ? 'On' : 'Off'}`} aria-pressed={inspect} title={inspect ? 'Leave inspection' : 'Inspect drawing · 2×'}>
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5 M7.5 10.5h6 M10.5 7.5v6" /></svg>
            </button>
            <span className="ff-board-caption">DRAWING {sheet.id} / 03</span>
            <div className="ff-board-picker" data-exhibit-ui role="group" aria-label="Reference drawing" onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor}>
              {PLAN_SHEETS.map((s, i) => <button key={s.id} onClick={() => chooseReference(i)} aria-label={s.label} aria-pressed={i === marked} title={`View drawing ${s.shortLabel}`}>{s.shortLabel}</button>)}
            </div>
            <button className="ff-board-icon ff-board-reset" data-exhibit-ui onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor} onClick={reset} aria-label="Reset view" title="Reset view">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 9a8 8 0 1 1-.5 6 M5 3v6h6" /></svg>
            </button>
            {switchError !== null && <p className="ff-image-error ff-board-error" data-exhibit-ui role="alert" onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor}>Reference {PLAN_SHEETS[switchError].shortLabel} could not be loaded, so {sheet.shortLabel} stays on the exhibit. <button onClick={() => chooseReference(switchError)}>RETRY {PLAN_SHEETS[switchError].shortLabel}</button> or choose another reference.</p>}
            {imageError && <p className="ff-image-error ff-board-error" data-exhibit-ui role="alert">The reference could not be loaded. Choose another reference or use Replay Intro to retry.</p>}
          </div>

          <div className="ff-work-info">
            <div className="ff-work-heading"><span className="ff-work-index">01 /</span><div><h1 ref={homeHeading} tabIndex={-1}>Plimsoll</h1><p>Naval design, made explorable.</p></div></div>
            {/* Two ways out, and they stay visibly different: the framed block opens
                the tool, the ruled text reads the project first. */}
            <div className="ff-work-entries">
              <a className="ff-explore-link" ref={cta} href={APP_ENTRY_LINK} onClick={enterTool} onPointerEnter={prefetchApp} onFocus={prefetchApp}>OPEN PLIMSOLL <span aria-hidden="true">↗</span></a>
              <a className="ff-project-link" href={WORK_DETAIL_LINK}>VIEW PROJECT <span aria-hidden="true">↗</span></a>
            </div>
          </div>
        </section>

        {/* The detail and About mount only when they are the visible view. Keeping
            a hidden copy of the detail alive would put a second full copy of the
            artwork in the document — a third `view-transition-name` candidate, a
            third filter id and a second `img` that no test or reader ever wanted.
            All the exhibit's own state lives in refs and state above, so it is
            already intact when this view comes back. */}
        {detail && <section className="ff-detail-slot">
          <ProjectDetail sheet={sheet} dark={dark} details={details} headingRef={detailHeading} ctaRef={detailCta} prefetchApp={prefetchApp} onEnterTool={enterTool} />
        </section>}

        {about && <section className="ff-about-slot">
          <AboutContent headingRef={aboutHeading} />
        </section>}
      </main>

      <nav className="ff-rail" aria-label="Main navigation" inert={opening}>
        {/* Work owns the exhibit and the work detail, so it stays the current page
            on both; the detail is reached from the exhibit, not from the rail. */}
        <a href={publicHref('home')} aria-current={!about ? 'page' : undefined}>Work <span>01</span></a>
        <a href={publicHref('about')} aria-current={about ? 'page' : undefined}>About</a>
      </nav>

      <footer className="ff-footer" inert={opening}><span>BUILT BY YANG DUANMING</span><span>PRECISE. MODERN. INTERACTIVE.</span><a href={`mailto:${CONTACT_EMAIL}`}>CONTACT ↗</a><button onClick={replay}>REPLAY INTRO <span aria-hidden="true">↗</span></button><SiteGeometry variant="rule" /></footer>
      {opening && publicActive && (readyHref === sheet.href
        ? <Splash sheet={sheet} target={exhibit} dark={dark} details={details} onDone={finish} onSettle={beginSettle} />
        : <div className="ff-splash ff-image-wait" role="status" aria-label="Loading reference"><span>PREPARING THE DRAWING</span><button className="ff-skip" onClick={finish}>SKIP INTRO <span>↗</span></button></div>)}
    </div>

    {/* The fallback is the workspace's own shell, so the frame morph lands on a
        surface that looks like the destination instead of a bare message. The
        application is still lazy: it mounts only on the committed app route. The
        way out is the real public view the visitor left, and it is rendered by
        the application header itself — there is no second return bar here. */}
    {route.kind === 'app' && <div className="ff-tool-shell"><div className="ff-workspace">
      {/* The application chunk is still loading: its header cannot be on screen
          yet, so the same real return href is rendered here. When the app mounts,
          it owns the anchor and this fallback leaves with it. */}
      <Suspense fallback={<><a className="ff-tool-return" href={publicHref(publicOrigin.current)}>↖ Y’s Formfield</a><div className="app-loading"><span className="brand-mark" />Plimsoll <small>正在加载工作空间</small></div></>}>
        <Plimsoll returnHref={publicHref(publicOrigin.current)} />
      </Suspense>
    </div></div>}
  </>;
}

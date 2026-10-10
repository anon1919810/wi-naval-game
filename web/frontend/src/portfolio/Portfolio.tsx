import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type KeyboardEvent } from 'react';
import { flushSync } from 'react-dom';
import { AboutContent } from './AboutContent';
import { CreditsContent } from './CreditsContent';
import { Artwork, artworkTransform, GEOMETRY_PARALLAX, maskTrackTransform } from './Artwork';
import { readyImage, type ImageCache } from './images';
import { introPlayed, markIntroPlayed } from './intro';
import { lensFrame, RESTING_VIEW_BOX, type ExhibitRect } from './lens';
import { createPreviewSound } from './previewAudio';
import { installInteractionFeedback, outcome } from '../audio/feedback';
import { interactionAudio } from '../audio/interactionAudio';
import { SoundToggle } from '../audio/SoundToggle';
import { ProjectDetail } from './ProjectDetail';
import { RailNav, type DestinationOrigin } from './RailNav';
import { ReadingRuler } from './ReadingRuler';
import { measureSections, READ_LINE_PX, sectionNodes, startReading, type Reading } from './readingScroll';
import { Splash } from './Splash';
import { PageField, ShellField } from './pageGeometry';
import { PLAN_SHEETS, sheetByIndex } from './plans';
import { APP_ENTRY_LINK, classifyHash, publicHref, WORK_DETAIL_LINK, type PortfolioRoute, type PublicView } from './routes';
import { railView } from './navPreview';
import { startScrollStudies } from './scrollStudies';
import { storedTheme, THEME_KEY, type PortfolioTheme } from './theme';
import { TitleEntry } from './TitleEntry';
import { ToolModuleBoundary } from './ToolModule';
import { animateTheme, cancelTransitions, runTransition, TRANSITION_MS, transitionsActive, type TransitionKind, type TransitionOptions } from './transitions';
import { ReadPending } from '../components/ReadPending';
// The leave guard attaches at import time: before this component mounts, and
// before the lazily fetched application chunk could have added any listener of
// its own. It therefore always hears a navigation first.
import '../leaveGuard';
import './portfolio.css';
import './content.css';
import './exhibit.css';
import './pageGeometry.css';

/**
 * The workspace chunk, fetched once and mounted only on the committed app route.
 *
 * A failed import is remembered by the browser's module map for the lifetime of
 * the document, so this factory is deliberately created once and never replaced:
 * re-running it would look like a retry while resolving the same rejection. The
 * boundary's own recovery is a page reload, which is the only thing that gets a
 * fresh module map. `toolFailed` records the failure so a later entry into the
 * workspace does not wait on the same dead promise before it can show that.
 */
const Tool = lazy(() => import('../App'));
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
  const dark = theme === 'dark';
  /**
   * The opening plays once per browser session, and only on request after that:
   * a reload or a Back does not replay it, and a new tab may. A refused
   * `sessionStorage` simply falls back to the previous behaviour.
   */
  const [opening, setOpening] = useState(() => {
    const initial = classifyHash(window.location.hash);
    return introEnabled && initial.kind === 'public' && initial.view === 'home'
      && !introPlayed() && !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
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
  const creditsHeading = useRef<HTMLHeadingElement>(null);
  const detailHeading = useRef<HTMLHeadingElement>(null);
  const detailCta = useRef<HTMLAnchorElement>(null);
  /** The page the ruler measures: the visible document, never the shell around it. */
  const page = useRef<HTMLElement>(null);
  /** The reading controller for that page, and the studies painter beside it. */
  const reading = useRef<Reading | null>(null);
  const studies = useRef<{ dispose(): void } | null>(null);
  /** Only section identity crosses into React; drawing progress stays in the DOM. */
  const [readingCurrent, setReadingCurrent] = useState(-1);
  const cut = useRef(0);
  /** The shell, which owns the theme tokens the reveal's layers are drawn in. */
  const shellRef = useRef<HTMLDivElement>(null);
  /** The public content region, and the only thing the reveal ever clips. */
  const mainRef = useRef<HTMLElement>(null);
  /** Where the rail says each destination's circle should open. */
  const railOrigins = useRef<DestinationOrigin | null>(null);
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
  /** Whether the chunk has failed, so a later entry can say so immediately. */
  const toolFailed = useRef(false);
  /**
   * The navigation preview's tap. Created once per shell, and only ever given a
   * context by a real gesture, so the first hover is silent. Disposing it is not
   * a one-way door: a later gesture can unlock a fresh context, which is what
   * keeps it correct under StrictMode's mount/unmount/mount rehearsal.
   */
  const soundRef = useRef<ReturnType<typeof createPreviewSound> | null>(null);
  if (soundRef.current === null) soundRef.current = createPreviewSound();
  const sound = soundRef.current;
  const finish = useCallback(() => { setOpening(false); setSettling(false); }, []);

  useEffect(installInteractionFeedback, []);

  // Marked as soon as the opening starts, not when it ends: an interrupted intro
  // has still been shown once in this session. Deliberately an effect rather than
  // part of the initial state, because a state initialiser runs during render and
  // this is a write to another context.
  useEffect(() => { if (opening) markIntroPlayed(); }, [opening]);

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
    // Cancel the pending tick even when this press keeps the current route.
    // Effect cleanup owns controller disposal when the route actually changes.
    reading.current?.refresh();
  }, []);
  const beginSettle = useCallback(() => setSettling(true), []);
  const sheet = sheetByIndex(sheetIndex);
  const marked = requested ?? sheetIndex;
  const publicActive = route.kind === 'public';
  const about = publicActive && route.view === 'about';
  const credits = publicActive && route.view === 'credits';
  const detail = publicActive && route.view === 'project';
  /**
   * Work owns the exhibit and its detail, and nothing else.
   *
   * Stated as the two views that really are Work rather than as "anything that is
   * not About": a fourth public view added later would otherwise inherit the
   * exhibit, and with it the reference decode, the sheet prefetch and the compass
   * field, none of which that page needs or asked for.
   */
  const onWork = publicActive && (route.view === 'home' || route.view === 'project');
  /** The rail only exists on a public route, so anything else reads as Work. */
  const railCurrent = route.kind === 'app' ? 'home' : route.view;
  /** Every view long enough to measure: three ruler sections on Credits. */
  const ruler = publicActive && (about || detail || credits);

  /** A reading controller for long pages; a separate painter also serves Work. */
  useEffect(() => {
    if (!ruler) return;
    const root = page.current;
    if (!root) return;
    const measure = () => measureSections(sectionNodes(root), window.scrollY);
    reading.current = startReading({
      measure,
      line: () => window.scrollY + READ_LINE_PX,
      atEnd: () => window.scrollY + window.innerHeight >= (document.documentElement.scrollHeight || 0) - 1,
      sound,
      onCurrent: setReadingCurrent,
      reducedMotion: () => still.current,
    });
    return () => { reading.current?.dispose(); reading.current = null; };
  }, [ruler, route, sound]);

  useEffect(() => {
    if (!publicActive || opening) return;
    studies.current = startScrollStudies({
      find: () => Array.from(mainRef.current?.querySelectorAll<HTMLElement>('[data-ff-study]') ?? []).filter(node => !node.closest('[hidden]')),
      viewport: () => window.innerHeight,
      reducedMotion: () => still.current,
    });
    return () => {
      studies.current?.dispose(); studies.current = null;
    };
  }, [publicActive, route, opening, sheet.href]);

  useEffect(() => {
    if (!onWork) return;
    let active = true;
    setReadyHref(null); setImageError(false);
    readyImage(sheet.href, imageCache.current).then(() => {
      if (active) setReadyHref(sheet.href);
    }, () => { if (active) { setImageError(true); finish(); } });
    return () => { active = false; };
  }, [sheet.href, onWork, loadAttempt, finish]);

  // There is deliberately no idle prefetch of the other reference sheets.
  // Each sheet is a ~200 KB archival scan and a visitor normally looks at one,
  // so loading all three while the page is idle spends their data and
  // connection on drawings they may never open. A sheet is requested when it is
  // selected (chooseReference), which is the intent that justifies the fetch;
  // the decode gate below still keeps the drawing on screen until the target
  // bitmap has actually decoded.

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
    // The circle's centre is the sampled point itself, at the rim as much as in
    // the middle, so the reticle at the centre of the magnified image and the
    // crosshair under the pointer are the same place. Near an edge the lens
    // hangs over the board and the board clips it — the sample is never moved.
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
      : (next.view === 'about' ? aboutHeading.current
        : next.view === 'credits' ? creditsHeading.current
        : fromDetail ? detailHeading.current : homeHeading.current);
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
      // is now redundant, so it is retired rather than left to finish. Only the
      // public shell's own moves are retired this way: an address change between
      // two application pages is the application's own business, and it manages
      // its transition with the same controller.
      if (transitionsActive() && next.kind === 'public') retire();
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
    // The artwork morph is the existing move between the exhibit and its own
    // detail. Work/About uses the bounded circular reveal. Credits uses that same
    // reveal from and to every public page — the detail included — because the
    // drawing lives on Work and there is nothing on Credits for it to morph with.
    // The morph rule is otherwise untouched: a move Credits is not part of behaves
    // exactly as it did before this page existed.
    const fromView = current.kind === 'public' ? current.view : null;
    const toView = next.kind === 'public' ? next.view : null;
    const creditsMove = toView === 'credits' || fromView === 'credits';
    const kind: TransitionKind = next.kind === 'app' ? 'tool'
      : returningFromTool ? 'tool-back'
      : creditsMove ? (toView === 'credits' ? 'page' : 'page-back')
      : (toView === 'project' || fromView === 'project') ? 'detail'
      : (toView === 'about' ? 'page' : 'page-back');
    const commit = () => {
      committed.current = next;
      flushSync(() => setRoute(next));
      place(next);
      restoreFocus(next, returningFromTool);
    };
    if (immediate) commit();
    // Preserve a real press's entry point before route placement changes scroll.
    // History has no press: measure its destination word after the commit instead.
    else if (kind === 'page' || kind === 'page-back') {
      const destination = next.kind === 'public' ? railView(next.view) : null;
      const pressedOrigin = destination ? railOrigins.current?.(destination) : null;
      void change(kind, commit, {
        reveal: {
          shell: shellRef.current,
          source: mainRef.current,
          origin: pressedOrigin ?? (() => destination ? railOrigins.current?.(destination, true) ?? null : null),
        },
      });
    } else void change(kind, commit);
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
      outcome('hold');
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
    return () => { window.removeEventListener('hashchange', update); };
  }, [applyRoute]);
  useEffect(() => {
    document.title = route.kind === 'app' ? 'Plimsoll · 舰船计算工作台'
      : route.view === 'project' ? 'Plimsoll — Y’s Formfield'
      : route.view === 'credits' ? 'Credits — Y’s Formfield'
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
      interactionAudio.play('detent');
      if (inspectOn.current) { focus.current = { x: 50, y: 50 }; paint(); } else reset();
    }
    // Escape leaves inspection, or resets the view when nothing is inspected.
    if (e.key === 'Escape') { e.preventDefault(); interactionAudio.play('detent'); if (inspectOn.current) setInspect(false); else reset(); }
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

  /** Compact companion to the primary toggle: nothing. The theme is chosen here
   *  and kept, so there is no mode that follows the OS behind the visitor's back. */
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
    <div className="ff-shell" ref={shellRef} data-ff-theme={dark ? 'dark' : 'light'} data-opening={opening} data-settling={settling} data-switching={switching} hidden={!publicActive}>
      <ShellField />
      <header className="ff-header" inert={opening}>
        <a className="ff-wordmark" href={publicHref('home')} aria-label="Y’s Formfield home">Y’s <span>Formfield</span><i aria-hidden="true">↗</i></a>
        <div className="ff-theme-group">
          {/* Three geometric marks, no words. The sound is a speaker with one
              wave and a diagonal slash through it when muted; the theme is a ring
              half filled; the replay is an incomplete circle that turns under the
              pointer or the key and stands still otherwise. Each keeps its
              accessible name, its pressed state where it has one, and its English
              title, so nothing here is only a picture. */}
          <SoundToggle />
          <button className="ff-theme" data-audio="manual" onClick={toggleTheme} aria-label={dark ? 'Switch to light theme' : 'Switch to dark theme'} title={dark ? 'Switch to light theme' : 'Switch to dark theme'}>
            <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><circle cx="10" cy="10" r="6.4" /><path className="ff-theme-fill" d="M10 3.6a6.4 6.4 0 0 1 0 12.8z" /></svg>
          </button>
          <button className="ff-replay" onClick={replay} aria-label="Replay intro" title="Replay intro">
            <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false"><path d="M15.2 12.6A6.4 6.4 0 1 1 10 3.6a6.4 6.4 0 0 1 5.2 9" /><path className="ff-replay-head" d="M15.6 6.2v3.6h-3.6" /></svg>
          </button>
        </div>
      </header>

      {/* The rail is a sibling of `main`, not a child of it: the circular reveal is
          scoped to `.ff-main`, so this navigation is never copied, never clipped
          and keeps focus across the page change. It stays mounted on every view. */}
      <main className="ff-main" ref={mainRef} inert={opening}>
        {/* The compass study is a child of `main`, not of the Work section: it needs
            the whole width `main` spans — rail included — so the arc can run out
            past the content column. Absolutely positioned, it adds no height, and
            the reveal's clip covers it exactly as it covers everything else here.
            It is the exhibit's own background, however: its own box is filled by
            `main`, so on the much longer detail it would stretch the drawing down
            the whole page and across its reading columns. The detail reads under
            the shell's faint field instead, and clears the paper under each of its
            own blocks. */}
        {onWork && !detail && <PageField page="work" />}
        <section className="ff-home" hidden={!onWork || detail} aria-label="Selected work">
          {/* The shared pale field surrounds the exhibit. */}
          <div className="ff-exhibit-label"><span><i className="ff-live-dot" />SELECTED WORK</span><span>TOOLS & EXPERIMENTS / VOL. 01</span></div>
          <div className="ff-exhibit" ref={exhibit} role="group" tabIndex={0} aria-label={inspect ? 'Interactive top-view drawing. Inspection on: arrow keys move the 2× lens over the same rendered scan, Home resets the lens, Escape leaves inspection.' : 'Interactive top-view drawing. Use arrow keys to explore, Home to reset.'} onKeyDown={keyboard} onBlur={() => { keysOn.current = false; paint(); }} onPointerMove={explore} onPointerEnter={e => { if (isExhibitControl(e.target)) withdrawDrawingCursor(); else if (e.pointerType === 'mouse') { hovered.current = true; paint(); } }} onPointerLeave={() => { hovered.current = false; paint(); }} onPointerDown={e => { if (isExhibitControl(e.target)) return; if (e.pointerType !== 'mouse') e.currentTarget.setPointerCapture(e.pointerId); explore(e); }}>
            {/* Hidden SVG images still fetch. Keep the exhibit frame and state,
                but mount its bitmap only while this drawing is displayed. */}
            <div className="ff-art-scene">{onWork && !detail && <Artwork compositionRef={composition} geometryRef={geometry} maskRef={maskTrack} sheet={sheet} dark={dark} details={details} />}</div>
            {onWork && !detail && inspect && <div ref={lens} className="ff-lens" aria-hidden="true">
              <span className="ff-lens-port">
                {/* The same Artwork composition, narrowed by viewBox: no second renderer, no second tone. */}
                <svg ref={lensView} className="ff-lens-view" viewBox={RESTING_VIEW_BOX} preserveAspectRatio="xMidYMid meet"><Artwork pixelFrame compositionRef={lensComposition} geometryRef={lensGeometry} maskRef={lensMask} sheet={sheet} dark={dark} details={details} /></svg>
                <span className="ff-lens-mark" />
              </span>
              <svg className="ff-lens-dial" viewBox="0 0 200 200" focusable="false">
                {Array.from({ length: 12 }, (_, index) => {
                  const angle = index * Math.PI / 6;
                  const major = index % 3 === 0;
                  const start = major ? 84 : 90;
                  return <line key={index} className={major ? 'ff-lens-tick-major' : undefined}
                    x1={100 + Math.cos(angle) * start} y1={100 + Math.sin(angle) * start}
                    x2={100 + Math.cos(angle) * 96} y2={100 + Math.sin(angle) * 96} />;
                })}
              </svg>
              <span className="ff-lens-label">2×<i>REF {sheet.id}</i></span>
            </div>}
            {!inspect && <div ref={cursor} className="ff-cursor" aria-hidden="true" hidden><span className="ff-cursor-cross" /><i /></div>}
            <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
            <button className="ff-board-icon ff-board-inspect" data-exhibit-ui onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor} onClick={() => setInspect(v => !v)} aria-label={`Inspect ${inspect ? 'On' : 'Off'}`} aria-pressed={inspect} title={inspect ? 'Leave inspection' : 'Inspect drawing · 2×'}>
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.5" cy="10.5" r="6.5" /><path d="m15.5 15.5 5 5 M7.5 10.5h6 M10.5 7.5v6" /></svg>
            </button>
            <span className="ff-board-caption">DRAWING {sheet.id} / 03</span>
            <div className="ff-board-picker" data-exhibit-ui role="group" aria-label="Reference drawing" onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor}>
              {PLAN_SHEETS.map((s, i) => <button key={s.id} data-audio="manual" onClick={() => chooseReference(i)} aria-label={s.label} aria-pressed={i === marked} title={`View drawing ${s.shortLabel}`}>{s.shortLabel}</button>)}
            </div>
            <button className="ff-board-icon ff-board-reset" data-audio="detent" data-exhibit-ui onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor} onClick={reset} aria-label="Reset view" title="Reset view">
              <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 9a8 8 0 1 1-.5 6 M5 3v6h6" /></svg>
            </button>
            {switchError !== null && <p className="ff-image-error ff-board-error" data-exhibit-ui role="alert" onPointerEnter={withdrawDrawingCursor} onFocus={withdrawDrawingCursor}>Reference {PLAN_SHEETS[switchError].shortLabel} could not be loaded, so {sheet.shortLabel} stays on the exhibit. <button onClick={() => chooseReference(switchError)}>RETRY {PLAN_SHEETS[switchError].shortLabel}</button> or choose another reference.</p>}
            {imageError && <p className="ff-image-error ff-board-error" data-exhibit-ui role="alert">The reference could not be loaded. Choose another reference or use Replay Intro to retry.</p>}
          </div>

          <div className="ff-work-info">
            {/* The title is the way into the tool, and the detail sits on its
                baseline rather than under it, so there is one entry line here
                instead of two competing ones. */}
            <div className="ff-work-heading">
              <span className="ff-work-index">01 /</span>
              <div>
                <TitleEntry headingRef={homeHeading} linkRef={cta} parts={['Pl', 'i', 'msoll']} dot={1} name="Open Plimsoll" href={APP_ENTRY_LINK}
                  secondary={{ href: WORK_DETAIL_LINK, label: 'VIEW PROJECT' }} prefetch={prefetchApp} onEnter={enterTool} />
                <p>Naval design, made explorable.</p>
              </div>
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
          <ProjectDetail sheet={sheet} dark={dark} details={details} pageRef={page} headingRef={detailHeading} ctaRef={detailCta} prefetchApp={prefetchApp} onEnterTool={enterTool} />
        </section>}

        {about && <section className="ff-about-slot">
          <AboutContent headingRef={aboutHeading} pageRef={page} />
        </section>}

        {/* Credits mounts only on its own route, for the same reason the detail
            does: a hidden second long page in the document is a second thing the
            ruler could measure and a second one a reader would have to skip past. */}
        {credits && <section className="ff-credits-slot">
          <CreditsContent headingRef={creditsHeading} pageRef={page} />
        </section>}
      </main>

      {/* The rail dock owns the whole navigation column: the two entries, and
          below them the reading ruler for the views long enough to need one. The
          ruler is its own labelled landmark, a sibling of the main navigation
          rather than a child of it, so a landmark list never reads them as one.
          Work owns the exhibit and the work detail, so it stays the current page
          on both; the detail is reached from the exhibit, not from the rail. A
          press on the page already on screen raises no address and therefore no
          route, so it is answered here instead: it drops whatever is still
          travelling away from it. */}
      <div className="ff-rail-dock">
        <RailNav current={railCurrent} sound={sound} onCurrentPagePress={retire} revealOrigins={railOrigins} inert={opening} />
        {ruler && <ReadingRuler key={railCurrent} pageRef={page} reading={reading} current={readingCurrent} />}
      </div>

      {/* Footer contact is gone: About ends with the real contact section, and a
          second address at the bottom of every page said the same thing twice.
          Replay is in the header for the same reason — one control, not two. */}
      <footer className="ff-footer" inert={opening}><span>BUILT BY YANG DUANMING</span><span>PRECISE. MODERN. INTERACTIVE.</span></footer>
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
      {/* The chunk is still arriving: the application's own header cannot be on
          screen yet, so the same real return href is rendered here, and the
          shared read placeholder says what is being read. When the app mounts it
          owns the anchor and this fallback leaves with it. */}
      <ToolModuleBoundary returnHref={publicHref(publicOrigin.current)}
        onFailure={() => { toolFailed.current = true; }}>
        <Suspense fallback={<><a className="ff-tool-return" href={publicHref(publicOrigin.current)}>↖ Y’s Formfield</a>
          <div className="workspace-connect"><ReadPending scope="workspace" object="工作空间" /></div></>}>
          <Tool returnHref={publicHref(publicOrigin.current)} />
        </Suspense>
      </ToolModuleBoundary>
    </div></div>}
  </>;
}

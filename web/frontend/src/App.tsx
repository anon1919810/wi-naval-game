import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';

import * as api from './api';
import { ReadFailure, ReadPending } from './components/ReadPending';
import { clearLeaveGuard, pushHash, setLeaveGuard } from './leaveGuard';
import { Library } from './pages/Library';
import { Login } from './pages/Login';
import { ReportPage } from './pages/Report';
import { Run } from './pages/Run';
import { Workbench } from './pages/Workbench';
import { isAppHash } from './portfolio/routes';
import { runTransition } from './portfolio/transitions';
import { useLanguage } from './portfolio/LanguageProvider';
import { SoundToggle } from './audio/SoundToggle';
import { outcome } from './audio/feedback';
import { useShellCopy } from './i18n/shell';
import { useWorkspaceCopy } from './i18n/workspace';
import type { AuthMode, Theme, UserSession } from './types';
// The workspace material is loaded by the eager shell entry, so a chunk that
// fails to arrive still finds these styles present.

const DamageLabPage = lazy(() => import('./damageLab/Page'));
type Route = { kind: 'library' } | { kind: 'project'; id: string } | { kind: 'run'; id: string } | { kind: 'report'; id: string } | { kind: 'lab'; id: string };

/** Where the reader is, in the shell's own words. Read from the route alone. */
const PLACES = { project: 'shell.place.project', run: 'shell.place.run', report: 'shell.place.report', lab: 'shell.place.lab' } as const;
type PlaceKey = typeof PLACES[keyof typeof PLACES];

function routeFrom(hash: string): Route {
  const path = hash.replace(/^#\/?/, '').split('/');
  if (path[0] === 'projects' && path[1]) return { kind: 'project', id: path[1] };
  if (path[0] === 'runs' && path[1]) return { kind: 'run', id: path[1] };
  if (path[0] === 'reports' && path[1]) return { kind: 'report', id: path[1] };
  if (path[0] === 'damage-lab' && path[1]) return { kind: 'lab', id: path[1] };
  return { kind: 'library' };
}

function currentRoute(): Route {
  return routeFrom(window.location.hash);
}

/** The library has no identity of its own, so it compares as one bucket. */
function identityOf(route: Route): string {
  return route.kind === 'library' ? '' : route.id;
}

/** A stage anchor adds a tail to the address but is still the same page. */
function sameRoute(left: Route, right: Route): boolean {
  return left.kind === right.kind && identityOf(left) === identityOf(right);
}

/**
 * The address a route owns. Derived from the route itself rather than read back
 * from the browser, so the guard is always told what this page is even if the
 * address has already started moving toward somewhere else.
 *
 * The segments are spelled out rather than interpolated from the route kind,
 * because the route kinds are singular and the addresses are plural: a mismatch
 * here would hand the guard an address that names no page, and a refused leave
 * would restore the reader to nothing.
 */
const SEGMENTS = { library: 'projects', project: 'projects', run: 'runs', report: 'reports', lab: 'damage-lab' } as const;

function addressOf(route: Route): string {
  return route.kind === 'library' ? '#/projects' : `#/${SEGMENTS[route.kind]}/${route.id}`;
}

/**
 * `returnHref` is the public page the visitor actually came from. Portfolio owns
 * that origin and passes it in; the application never guesses a destination, and
 * the return anchor renders in the application header instead of a second bar.
 */
export default function App({ returnHref }: { returnHref?: string }) {
  // One language for the whole application, owned by the shell that mounted
  // this route. Reading it here changes words and nothing else: the session, the
  // route, the draft, the scroll position and any queued run all live in state
  // above this component and none of them is touched by a dictionary changing.
  const { language, t, setLanguage } = useLanguage();
  // `c` is the shared chrome the eager shell also owns; `w` is this route's own
  // dictionary, reached only through the workspace chunk.
  const c = useShellCopy();
  const w = useWorkspaceCopy();
  const [user, setUser] = useState<UserSession | null>(null);
  const [mode, setMode] = useState<AuthMode | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [failed, setFailed] = useState(false);
  const [route, setRoute] = useState<Route>(currentRoute);
  const [reason, setReason] = useState<Reason>(null);

  // The public shell owns the document root once the route leaves the
  // application. A request still in flight at that moment must not mint another
  // identity or repaint the root theme behind the portfolio's back.
  const mounted = useRef(true);
  /** Every attempt retires the one before it, including an abandoned one. */
  const attempt = useRef(0);
  /** The route React has actually committed, which the address listener compares. */
  const committed = useRef<Route>(route);
  /**
   * The address this page is actually showing. Derived from the committed route
   * and never read back out of the browser: during a traversal the browser's
   * address is already the destination, and the guard has to be told what the
   * reader would lose, not where they were refused.
   */
  const shownHash = useRef(addressOf(route));
  /** Whether the open project holds unsaved edits; read by the leave guard. */
  const dirty = useRef(false);

  /** Why a message is on screen, resolved to words where it is printed. */
type Reason = 'connect' | 'theme' | 'signOut' | null;

  const apply = useCallback((session: UserSession) => {
    setUser(session);
    document.documentElement.dataset.theme = session.theme;
  }, []);

  /**
   * Enter the workspace. A failed attempt surfaces and waits: it is never repeated
   * on its own, so no identities are minted in a loop. The reader's own retry
   * asks `/me` first — an existing browser session is adopted again rather than
   * replaced — and only a genuine 401 goes on to create one, and `bootstrap`
   * stays single-flight, so a second press cannot start a second creation.
   *
   * Nothing here reads a dictionary. This callback is the mount effect's only
   * dependency, so a localized lookup in its body would rebuild it on every
   * language change; the effect would then unmount, re-enter and set
   * `connecting` again, taking the whole page — an edited draft, a running
   * calculation, a laboratory camera — with it. What it records instead is a
   * *reason*, not a sentence, and the sentence is resolved where it is printed.
   */
  const enter = useCallback(async (explicit = false) => {
    const mine = ++attempt.current;
    setConnecting(true);
    setFailed(false);
    setReason(null);
    const live = () => mounted.current && mine === attempt.current;
    try {
      const config = await api.authConfig();
      if (!live()) return;
      setMode(config.mode);
      if (config.mode !== 'anonymous') {
        try { const session = await api.me(); if (live()) apply(session); }
        catch (cause) { if (!(cause instanceof api.ApiError && cause.status === 401)) throw cause; }
        return;
      }
      try {
        const session = await api.me();
        if (live()) apply(session);
      } catch (cause) {
        if (!(cause instanceof api.ApiError && cause.status === 401)) throw cause;
        // A 401 can arrive after the route has already left the application, so
        // the follow-on bootstrap is gated: returning to the portfolio must stop
        // the workspace calls instead of continuing into a second one.
        if (!live()) return;
        // The creation itself is gated the same way, and its answer is gated
        // again: an attempt that has been retired or unmounted while the
        // request was out must not repaint the root or resurrect a session.
        const created = await api.bootstrapAnonymous();
        if (!live()) return;
        apply(created);
      }
    } catch {
      if (live()) { setFailed(true); setReason('connect'); if (explicit) outcome('hold'); }
    } finally { if (live()) setConnecting(false); }
  }, [apply]);

  /**
   * One workspace page to the next. The shared controller owns the timing, the
   * latest-wins rule and the reduced-motion fallback; it waits for nothing, so a
   * slow read never holds the page back. An unsupported browser, a refused visit
   * and a changed motion preference all commit immediately.
   */
  const applyRoute = useCallback((next: Route) => {
    if (sameRoute(next, committed.current)) { shownHash.current = addressOf(next); return; }
    void runTransition('app-route', () => {
      committed.current = next;
      shownHash.current = addressOf(next);
      // Only an open project can hold an unsaved draft; nothing else may leave
      // the guard armed for the reader's next Back.
      if (next.kind !== 'project') dirty.current = false;
      setRoute(next);
    });
    // A CSS animation restarts only when its name changes, so one name would let
    // a second switch inside the first 220 ms do nothing at all. The token
    // alternates for exactly the reason the local reveals do, and the first
    // arrival is not animated: it is the page simply being there.
    setRouteMotion(previous => (previous === 'a' ? 'b' : 'a'));
  }, []);

  /** `null` until the first switch, so arriving at a page is not an animation. */
  const [routeMotion, setRouteMotion] = useState<'a' | 'b' | null>(null);

  const navigate = useCallback((path: string) => {
    const hash = `#${path}`;
    // The guard answers before the address moves, so a refused press leaves the
    // draft, the chapter and the address exactly as they were.
    if (!pushHash(hash)) return;
    applyRoute(routeFrom(hash));
  }, [applyRoute]);

  const reportDirty = useCallback((edited: boolean) => { dirty.current = edited; }, []);

  useEffect(() => {
    mounted.current = true;
    void enter();
    return () => { mounted.current = false; attempt.current += 1; };
  }, [enter]);

  useEffect(() => {
    const update = () => {
      if (!isAppHash(window.location.hash)) return;
      applyRoute(currentRoute());
    };
    window.addEventListener('hashchange', update);
    return () => window.removeEventListener('hashchange', update);
  }, [applyRoute]);

  useEffect(() => {
    setLeaveGuard(() => dirty.current ? { message: w('shell.unsaved'), current: shownHash.current } : null);
    return () => clearLeaveGuard();
    // `w` is stable while the language is, so a switch re-arms the guard with the
    // new wording and nothing else; the guard's own state is the ref above.
  }, [w]);

  async function changeTheme() {
    if (!user) return;
    const theme: Theme = user.theme === 'light' ? 'dark' : 'light';
    try {
      await api.setTheme(theme);
      if (!mounted.current) return;
      setUser({ ...user, theme });
      document.documentElement.dataset.theme = theme;
    } catch { if (mounted.current) { setReason('theme'); outcome('hold'); } }
  }

  async function signOut() {
    try {
      await api.logout();
      if (!mounted.current) return;
      setUser(null);
      navigate('/projects');
    } catch { if (mounted.current) { setReason('signOut'); outcome('hold'); } }
  }

  /**
 * The anonymous session's own label.
 *
 * The backend names a browser workspace for the reader; that name is an
 * application-authored default rather than something the visitor chose, so it
 * follows the language like every other application-owned word. A real
 * account's `label`, and any email, is the user's own text and is printed
 * exactly as stored. The backend's default is matched as a known value rather
 * than assumed, so a backend that changes it falls through to the raw string.
 */
const ANONYMOUS_DEFAULT_LABELS: ReadonlySet<string> = new Set([
  '本浏览器工作区', 'This browser’s workspace', 'This browser\'s workspace',
]);

  const anonymous = mode === 'anonymous';
  const stored = user?.label ?? '';
  const identity = stored && ANONYMOUS_DEFAULT_LABELS.has(stored) && anonymous
    ? w('library.anonymous.title')
    : user?.label ?? user?.email ?? '';
  // The one place a reason becomes words. Nothing above this reads a dictionary
  // for it, so a language switch re-renders this sentence and no lifecycle.
  const message = reason === 'connect' ? w('shell.connect.failed')
    : reason === 'theme' ? w('shell.theme.failed')
    : reason === 'signOut' ? w('shell.signOut.failed')
    : '';
  // The header states where the reader is before the page's own identity has
  // finished loading, so the 220 ms between two workspace pages is never a blank.
  const place = route.kind === 'library' ? w('shell.place.library') : `${w(PLACES[route.kind] as PlaceKey)} · ${route.id.slice(0, 8).toUpperCase()}`;

  // The public return belongs to the application head and stays available in every
  // state below, including a workspace that never reaches its API. Someone who
  // cannot sign in must still be able to go back to the public pages.
  //
  // The language pair is the same pair the public shell offers, in the same
  // position beside the theme and the sound: two ordinary buttons in one
  // labelled group, each carrying its own `lang` so a screen reader pronounces
  // 中文 as Chinese and EN as English. It writes the shell's single stored
  // preference, so the tool and the public pages can never disagree about which
  // language this visitor chose.
  const head = <header className="site-header">
    {returnHref && <a className="ff-tool-return" href={returnHref}>{c('shell.toolReturn')}</a>}
    <button className="brand brand-button" data-audio="manual" onClick={() => navigate('/projects')}><span className="brand-mark" aria-hidden="true" />Plimsoll<span className="brand-suffix">{w('shell.brandSuffix')}</span></button>
    <span className="header-context" data-ff-context={route.kind} title={w('shell.contextTitle')}>{place}</span>
    <div className="header-actions"><span className="header-edition">DESIGN DESK · 1.0</span>
      <SoundToggle workspace />
      <div className="workspace-lang" role="group" aria-label={t('header.languageGroup')}>
        <button type="button" className="text-button workspace-lang-option" lang="zh-CN" aria-pressed={language === 'zh-CN'}
          aria-label={t('header.languageZh')} title={t('header.languageZhTitle')} onClick={() => setLanguage('zh-CN')}>中文</button>
        <button type="button" className="text-button workspace-lang-option" lang="en" aria-pressed={language === 'en'}
          aria-label={t('header.languageEn')} title={t('header.languageEnTitle')} onClick={() => setLanguage('en')}>EN</button>
      </div>
      {user && <><button className="icon-button" data-audio="detent"
        aria-label={user.theme === 'light' ? w('shell.theme.toDark') : w('shell.theme.toLight')}
        title={user.theme === 'light' ? w('shell.theme.toDark') : w('shell.theme.toLight')}
        onClick={changeTheme}>{user.theme === 'light' ? '◐' : '◑'}</button><span className="user-email" title={identity}>{identity}</span>{!anonymous && <button className="text-button" onClick={signOut}>{w('shell.signOut')}</button>}</>}
    </div>
  </header>;

  if (connecting) return <div className="app-shell">{head}
    <div className="page-pad workspace-connect"><ReadPending scope="workspace" object={c('shell.connect.object')} /></div></div>;
  // A workspace that never reached its API says so, and offers exactly one way
  // back in —together with the real public way out.
  if (!user && mode !== 'email') return <div className="app-shell">{head}
    <div className="page-pad workspace-connect">
      {failed
        ? <ReadFailure title={w('shell.connect.failedTitle')} detail={message} retryLabel={w('shell.connect.retry')}
            onRetry={() => { void enter(true); }}
            onBack={returnHref ? () => { window.location.hash = returnHref.replace(/^#/, ''); } : undefined}
            backLabel={w('shell.connect.back')} />
        : <ReadPending scope="workspace" object={c('shell.connect.object')} />}
    </div></div>;
  if (!user) return <div className="app-shell">{head}<Login onAuthenticated={() => {
    // Gated before the request, not only after it: a stale callback from a form
    // that was already replaced must not start another identity lookup.
    if (!mounted.current) return;
    void api.me().then(session => { if (!mounted.current) return; setUser(session); document.documentElement.dataset.theme = session.theme; });
  }} />{message && <div className="connection-note" role="alert">{message}</div>}</div>;

  // The header and the page identity stay put; only the arriving page is marked,
  // so the animation never captures or distorts the report body.
  return <div className="app-shell">
    {head}
    {message && <div className="connection-note" role="alert">{message}<button onClick={() => setReason(null)} aria-label={w('shell.dismiss')}>×</button></div>}
    <div className="app-route" data-motion={routeMotion ?? undefined}>
      {route.kind === 'library' && <Library onOpen={id => navigate(`/projects/${id}`)} onLab={id => navigate(`/damage-lab/${id}`)} anonymous={anonymous} />}
      {route.kind === 'project' && <Workbench key={route.id} projectId={route.id} onDirtyChange={reportDirty}
        onBack={() => navigate('/projects')} onRun={id => navigate(`/runs/${id}`)} onLab={() => navigate(`/damage-lab/${route.id}`)} />}
      {route.kind === 'run' && <Run key={route.id} runId={route.id} onBack={id => navigate(`/projects/${id}`)} onReport={() => navigate(`/reports/${route.id}`)} />}
      {route.kind === 'report' && <ReportPage key={route.id} runId={route.id} onBack={() => navigate(`/runs/${route.id}`)} />}
      {route.kind === 'lab' && <Suspense fallback={<div className="page-pad"><ReadPending scope="workspace" object={w('shell.place.lab')} /></div>}><DamageLabPage key={route.id} projectId={route.id} onBack={() => navigate('/projects')} onProject={id => navigate(`/damage-lab/${id}`)} /></Suspense>}
    </div>
  </div>;
}

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
import { SoundToggle } from './audio/SoundToggle';
import { outcome } from './audio/feedback';
import type { AuthMode, Theme, UserSession } from './types';
// The workspace material is loaded by the eager shell entry, so a chunk that
// fails to arrive still finds these styles present.

const DamageLabPage = lazy(() => import('./damageLab/Page'));
type Route = { kind: 'library' } | { kind: 'project'; id: string } | { kind: 'run'; id: string } | { kind: 'report'; id: string } | { kind: 'lab'; id: string };

/** What the reader gives up by leaving an edited project. */
const UNSAVED = '当前舰船有未保存的修改，离开会丢失这些修改。是否离开？';

/** Where the reader is, in the shell's own words. Read from the route alone. */
const PLACES = { project: '项目', run: '运行', report: '报告', lab: '损伤实验室' } as const;

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
  const [user, setUser] = useState<UserSession | null>(null);
  const [mode, setMode] = useState<AuthMode | null>(null);
  const [connecting, setConnecting] = useState(true);
  const [failed, setFailed] = useState(false);
  const [route, setRoute] = useState<Route>(currentRoute);
  const [message, setMessage] = useState('');

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

  const apply = useCallback((session: UserSession) => {
    setUser(session);
    document.documentElement.dataset.theme = session.theme;
  }, []);

  /**
   * Enter the workspace. A failed attempt surfaces and waits: it is never repeated
   * on its own, so no identities are minted in a loop. The reader's own retry
   * asks `/me` first — an existing browser session is adopted again rather than
   * replaced — and only a genuine 401 goes on to create one, and `bootstrap` stays
   * single-flight, so a second press cannot start a second creation.
   */
  const enter = useCallback(async (explicit = false) => {
    const mine = ++attempt.current;
    setConnecting(true);
    setFailed(false);
    setMessage('');
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
      if (live()) { setFailed(true); setMessage('暂时无法连接工作空间，请稍后刷新页面重试。'); if (explicit) outcome('hold'); }
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
    setLeaveGuard(() => dirty.current ? { message: UNSAVED, current: shownHash.current } : null);
    return () => clearLeaveGuard();
  }, []);

  async function changeTheme() {
    if (!user) return;
    const theme: Theme = user.theme === 'light' ? 'dark' : 'light';
    try {
      await api.setTheme(theme);
      if (!mounted.current) return;
      setUser({ ...user, theme });
      document.documentElement.dataset.theme = theme;
    } catch { if (mounted.current) { setMessage('主题设置未保存。'); outcome('hold'); } }
  }

  async function signOut() {
    try {
      await api.logout();
      if (!mounted.current) return;
      setUser(null);
      navigate('/projects');
    } catch { if (mounted.current) { setMessage('退出登录失败，请重试。'); outcome('hold'); } }
  }

  const anonymous = mode === 'anonymous';
  const identity = user?.label ?? user?.email ?? '';
  // The header states where the reader is before the page's own identity has
  // finished loading, so the 220 ms between two workspace pages is never a blank.
  const place = route.kind === 'library' ? '项目库' : `${PLACES[route.kind]} · ${route.id.slice(0, 8).toUpperCase()}`;

  // The public return belongs to the application head and stays available in every
  // state below, including a workspace that never reaches its API. Someone who
  // cannot sign in must still be able to go back to the public pages.
  const head = <header className="site-header">
    {returnHref && <a className="ff-tool-return" href={returnHref}>↖ Y’s Formfield</a>}
    <button className="brand brand-button" data-audio="manual" onClick={() => navigate('/projects')}><span className="brand-mark" aria-hidden="true" />Plimsoll<span className="brand-suffix">/ WORKSPACE</span></button>
    <span className="header-context" data-ff-context={route.kind} title="当前位置">{place}</span>
    <div className="header-actions"><span className="header-edition">DESIGN DESK · 1.0</span>
      <SoundToggle workspace />
      {user && <><button className="icon-button" data-audio="detent" aria-label={user.theme === 'light' ? '切换到深色主题' : '切换到浅色主题'} onClick={changeTheme}>{user.theme === 'light' ? '◐' : '◑'}</button><span className="user-email" title={identity}>{identity}</span>{!anonymous && <button className="text-button" onClick={signOut}>退出</button>}</>}
    </div>
  </header>;

  if (connecting) return <div className="app-shell">{head}
    <div className="page-pad workspace-connect"><ReadPending scope="workspace" object="工作空间" /></div></div>;
  // A workspace that never reached its API says so, and offers exactly one way
  // back in — together with the real public way out.
  if (!user && mode !== 'email') return <div className="app-shell">{head}
    <div className="page-pad workspace-connect">
      {failed
        ? <ReadFailure title="工作空间尚未连接" detail={message} retryLabel="重新连接"
            onRetry={() => { void enter(true); }}
            onBack={returnHref ? () => { window.location.hash = returnHref.replace(/^#/, ''); } : undefined}
            backLabel="返回总站" />
        : <ReadPending scope="workspace" object="工作空间" />}
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
    {message && <div className="connection-note" role="alert">{message}<button onClick={() => setMessage('')} aria-label="关闭提示">×</button></div>}
    <div className="app-route" data-motion={routeMotion ?? undefined}>
      {route.kind === 'library' && <Library onOpen={id => navigate(`/projects/${id}`)} onLab={id => navigate(`/damage-lab/${id}`)} anonymous={anonymous} />}
      {route.kind === 'project' && <Workbench key={route.id} projectId={route.id} onDirtyChange={reportDirty}
        onBack={() => navigate('/projects')} onRun={id => navigate(`/runs/${id}`)} onLab={() => navigate(`/damage-lab/${route.id}`)} />}
      {route.kind === 'run' && <Run key={route.id} runId={route.id} onBack={id => navigate(`/projects/${id}`)} onReport={() => navigate(`/reports/${route.id}`)} />}
      {route.kind === 'report' && <ReportPage key={route.id} runId={route.id} onBack={() => navigate(`/runs/${route.id}`)} />}
      {route.kind === 'lab' && <Suspense fallback={<div className="page-pad"><ReadPending scope="workspace" object="损伤实验室" /></div>}><DamageLabPage key={route.id} projectId={route.id} onBack={() => navigate('/projects')} onProject={id => navigate(`/damage-lab/${id}`)} /></Suspense>}
    </div>
  </div>;
}

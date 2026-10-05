import { useEffect, useRef, useState } from 'react';

import * as api from './api';
import { Library } from './pages/Library';
import { Login } from './pages/Login';
import { ReportPage } from './pages/Report';
import { Run } from './pages/Run';
import { Workbench } from './pages/Workbench';
import { isAppHash } from './portfolio/routes';
import type { AuthMode, Theme, UserSession } from './types';
import './styles/workspace.css';

type Route = { kind: 'library' } | { kind: 'project'; id: string } | { kind: 'run'; id: string } | { kind: 'report'; id: string };

function currentRoute(): Route {
  const path = window.location.hash.replace(/^#\/?/, '').split('/');
  if (path[0] === 'projects' && path[1]) return { kind: 'project', id: path[1] };
  if (path[0] === 'runs' && path[1]) return { kind: 'run', id: path[1] };
  if (path[0] === 'reports' && path[1]) return { kind: 'report', id: path[1] };
  return { kind: 'library' };
}

function navigate(path: string) { window.location.hash = path; }

export default function App() {
  const [user, setUser] = useState<UserSession | null>(null);
  const [mode, setMode] = useState<AuthMode | null>(null);
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState<Route>(currentRoute);
  const [message, setMessage] = useState('');

  // The public shell owns the document root once the route leaves the
  // application. A request still in flight at that moment must not mint another
  // identity or repaint the root theme behind the portfolio's back.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    let active = true;
    const update = () => { if (isAppHash(window.location.hash)) setRoute(currentRoute()); };
    window.addEventListener('hashchange', update);

    function apply(session: UserSession) {
      if (!active) return;
      setUser(session);
      document.documentElement.dataset.theme = session.theme;
    }

    // Browser workspaces bootstrap at most once per page load; a failed attempt
    // surfaces a message instead of retrying, so no identities are minted in a loop.
    async function enter() {
      const config = await api.authConfig();
      if (!active) return;
      setMode(config.mode);
      if (config.mode !== 'anonymous') {
        try { apply(await api.me()); }
        catch (cause) { if (!(cause instanceof api.ApiError && cause.status === 401)) throw cause; }
        return;
      }
      try {
        apply(await api.me());
      } catch (cause) {
        if (!(cause instanceof api.ApiError && cause.status === 401)) throw cause;
        // A 401 can arrive after the route has already left the application, so
        // the follow-on bootstrap is gated: returning to the portfolio must stop
        // the workspace calls instead of continuing into a second one.
        if (!active) return;
        apply(await api.bootstrapAnonymous());
      }
    }

    enter().catch(() => { if (active) setMessage('暂时无法连接工作空间，请稍后刷新页面重试。'); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; window.removeEventListener('hashchange', update); };
  }, []);

  async function changeTheme() {
    if (!user) return;
    const theme: Theme = user.theme === 'light' ? 'dark' : 'light';
    try {
      await api.setTheme(theme);
      if (!mounted.current) return;
      setUser({ ...user, theme });
      document.documentElement.dataset.theme = theme;
    } catch { if (mounted.current) setMessage('主题设置未保存。'); }
  }

  async function signOut() {
    try { await api.logout(); if (!mounted.current) return; setUser(null); navigate('/projects'); }
    catch { if (mounted.current) setMessage('退出登录失败，请重试。'); }
  }

  const anonymous = mode === 'anonymous';
  const identity = user?.label ?? user?.email ?? '';

  if (loading) return <div className="app-loading"><span className="brand-mark" />Plimsoll <small>正在连接工作空间</small></div>;
  if (!user && mode !== 'email') return <div className="app-loading"><span className="brand-mark" />Plimsoll <small>{message || '正在建立本浏览器工作区'}</small></div>;
  if (!user) return <><Login onAuthenticated={() => {
    // Gated before the request, not only after it: a stale callback from a form
    // that was already replaced must not start another identity lookup.
    if (!mounted.current) return;
    void api.me().then(session => { if (!mounted.current) return; setUser(session); document.documentElement.dataset.theme = session.theme; });
  }} />{message && <div className="connection-note" role="alert">{message}</div>}</>;

  return <div className="app-shell">
    <header className="site-header"><button className="brand brand-button" onClick={() => navigate('/projects')}><span className="brand-mark" aria-hidden="true" />Plimsoll<span className="brand-suffix">/ WORKSPACE</span></button>
      <div className="header-actions"><span className="header-edition">DESIGN DESK · 1.0</span><button className="icon-button" aria-label={user.theme === 'light' ? '切换到深色主题' : '切换到浅色主题'} onClick={changeTheme}>{user.theme === 'light' ? '◐' : '◑'}</button><span className="user-email" title={identity}>{identity}</span>{!anonymous && <button className="text-button" onClick={signOut}>退出</button>}</div>
    </header>
    {message && <div className="connection-note" role="alert">{message}<button onClick={() => setMessage('')} aria-label="关闭提示">×</button></div>}
    {route.kind === 'library' && <Library onOpen={id => navigate(`/projects/${id}`)} anonymous={anonymous} />}
    {route.kind === 'project' && <Workbench key={route.id} projectId={route.id} onBack={() => navigate('/projects')} onRun={id => navigate(`/runs/${id}`)} />}
    {route.kind === 'run' && <Run key={route.id} runId={route.id} onBack={id => navigate(`/projects/${id}`)} onReport={() => navigate(`/reports/${route.id}`)} />}
    {route.kind === 'report' && <ReportPage key={route.id} runId={route.id} onBack={() => navigate(`/runs/${route.id}`)} />}
  </div>;
}

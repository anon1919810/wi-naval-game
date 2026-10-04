import { useEffect, useState } from 'react';

import * as api from './api';
import { Library } from './pages/Library';
import { Login } from './pages/Login';
import { ReportPage } from './pages/Report';
import { Run } from './pages/Run';
import { Workbench } from './pages/Workbench';
import type { AuthMode, Theme, UserSession } from './types';

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

  useEffect(() => {
    let active = true;
    const update = () => setRoute(currentRoute());
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
      setUser({ ...user, theme });
      document.documentElement.dataset.theme = theme;
    } catch { setMessage('主题设置未保存。'); }
  }

  async function signOut() {
    try { await api.logout(); setUser(null); navigate('/projects'); }
    catch { setMessage('退出登录失败，请重试。'); }
  }

  const anonymous = mode === 'anonymous';
  const identity = user?.label ?? user?.email ?? '';

  if (loading) return <div className="app-loading"><span className="brand-mark" />Plimsoll <small>正在连接工作空间</small></div>;
  if (!user && mode !== 'email') return <div className="app-loading"><span className="brand-mark" />Plimsoll <small>{message || '正在建立本浏览器工作区'}</small></div>;
  if (!user) return <><Login onAuthenticated={() => { void api.me().then(session => { setUser(session); document.documentElement.dataset.theme = session.theme; }); }} />{message && <div className="connection-note" role="alert">{message}</div>}</>;

  return <div className="app-shell">
    <header className="site-header"><button className="brand brand-button" onClick={() => navigate('/projects')}><span className="brand-mark" aria-hidden="true" />Plimsoll<span className="brand-suffix">/ 工作空间</span></button>
      <div className="header-actions"><span className="header-edition">DESIGN DESK · 1.0</span><button className="icon-button" aria-label={user.theme === 'light' ? '切换到深色主题' : '切换到浅色主题'} onClick={changeTheme}>{user.theme === 'light' ? '◐' : '◑'}</button><span className="user-email" title={identity}>{identity}</span>{!anonymous && <button className="text-button" onClick={signOut}>退出</button>}</div>
    </header>
    {message && <div className="connection-note" role="alert">{message}<button onClick={() => setMessage('')} aria-label="关闭提示">×</button></div>}
    {route.kind === 'library' && <Library onOpen={id => navigate(`/projects/${id}`)} anonymous={anonymous} />}
    {route.kind === 'project' && <Workbench key={route.id} projectId={route.id} onBack={() => navigate('/projects')} onRun={id => navigate(`/runs/${id}`)} />}
    {route.kind === 'run' && <Run key={route.id} runId={route.id} onBack={id => navigate(`/projects/${id}`)} onReport={() => navigate(`/reports/${route.id}`)} />}
    {route.kind === 'report' && <ReportPage key={route.id} runId={route.id} onBack={() => navigate(`/runs/${route.id}`)} />}
  </div>;
}

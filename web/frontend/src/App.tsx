import { useEffect, useState } from 'react';

import * as api from './api';
import { Library } from './pages/Library';
import { Login } from './pages/Login';
import { Workbench } from './pages/Workbench';
import type { Theme, UserSession } from './types';

type Route = { kind: 'library' } | { kind: 'project'; id: string } | { kind: 'run'; id: string };

function currentRoute(): Route {
  const path = window.location.hash.replace(/^#\/?/, '').split('/');
  if (path[0] === 'projects' && path[1]) return { kind: 'project', id: path[1] };
  if (path[0] === 'runs' && path[1]) return { kind: 'run', id: path[1] };
  return { kind: 'library' };
}

function navigate(path: string) { window.location.hash = path; }

export default function App() {
  const [user, setUser] = useState<UserSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [route, setRoute] = useState<Route>(currentRoute);
  const [message, setMessage] = useState('');

  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener('hashchange', update);
    api.me().then(session => { setUser(session); document.documentElement.dataset.theme = session.theme; })
      .catch(cause => { if (!(cause instanceof api.ApiError && cause.status === 401)) setMessage('暂时无法连接工作空间，请稍后刷新。'); })
      .finally(() => setLoading(false));
    return () => window.removeEventListener('hashchange', update);
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

  if (loading) return <div className="app-loading"><span className="brand-mark" />Plimsoll <small>正在连接工作空间</small></div>;
  if (!user) return <><Login onAuthenticated={() => { void api.me().then(session => { setUser(session); document.documentElement.dataset.theme = session.theme; }); }} />{message && <div className="connection-note" role="alert">{message}</div>}</>;

  return <div className="app-shell">
    <header className="site-header"><button className="brand brand-button" onClick={() => navigate('/projects')}><span className="brand-mark" aria-hidden="true" />Plimsoll<span className="brand-suffix">/ 工作空间</span></button>
      <div className="header-actions"><span className="header-edition">DESIGN DESK · 1.0</span><button className="icon-button" aria-label={user.theme === 'light' ? '切换到深色主题' : '切换到浅色主题'} onClick={changeTheme}>{user.theme === 'light' ? '◐' : '◑'}</button><span className="user-email" title={user.email}>{user.email}</span><button className="text-button" onClick={signOut}>退出</button></div>
    </header>
    {message && <div className="connection-note" role="alert">{message}<button onClick={() => setMessage('')} aria-label="关闭提示">×</button></div>}
    {route.kind === 'library' && <Library onOpen={id => navigate(`/projects/${id}`)} />}
    {route.kind === 'project' && <Workbench key={route.id} projectId={route.id} onBack={() => navigate('/projects')} onRun={id => navigate(`/runs/${id}`)} />}
    {route.kind === 'run' && <div className="page-pad"><span className="section-kicker">RUN / {route.id.slice(0, 8)}</span><h1>计算运行</h1><p>结果与报告视图正在接入。</p><button className="button button--secondary" onClick={() => navigate('/projects')}>返回项目库</button></div>}
  </div>;
}

import { useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { ReadFailure, ReadPending } from '../components/ReadPending';
import type { ProjectSummary } from '../types';
import { SiteGeometry } from '../portfolio/SiteGeometry';
import { outcome } from '../audio/feedback';

const templates = [
  { key: 'analytic_box', name: '解析方箱', tag: '解析基准', text: '有明确几何与解析解，适合熟悉项目和验证流程。' },
  { key: 'generic_steamer', name: '通用试验船', tag: '示范案例', text: '带完整型线与载荷，用于探索多工况计算。' },
  { key: 'queen_mary_1913', name: 'HMS Queen Mary', tag: '史实未认证代理', text: '一战战列巡洋舰工程代理。所有估算和史料缺口均保留标记。' },
] as const;

/**
 * Reading the library and creating a project are two different failures.
 *
 * A failed read ends the skeleton and the reading count together — a page that
 * still claims to be counting something it cannot read is lying — and it leaves
 * every creation entry usable, because nothing about a new project depends on
 * being able to list the old ones. A failed creation says only that the creation
 * failed, next to the entries that can be tried again.
 */
type Read = { status: 'loading' | 'failed' | 'ready'; projects: ProjectSummary[] };

/**
 * How long a creation has been refused for, in words. Nothing here is invented:
 * the answer is either the server's own or the generic fallback.
 */
function creationReason(cause: unknown): string {
  return cause instanceof Error && cause.message ? cause.message : '请检查名称与模板后重试';
}

export function Library({ onOpen, anonymous = false }: { onOpen: (id: string) => void; anonymous?: boolean }) {
  const [read, setRead] = useState<Read>({ status: 'loading', projects: [] });
  const [readError, setReadError] = useState('');
  const [createError, setCreateError] = useState('');
  const [creating, setCreating] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [attempt, setAttempt] = useState(0);
  /**
   * The page's own lifetime, and one ticket per request. A creation that is still
   * in flight when the reader leaves must not navigate a page that no longer
   * exists, and a failed one must not speak into an unmounted tree.
   */
  const alive = useRef(true);
  const readTicket = useRef(0);
  const createTicket = useRef(0);

  useEffect(() => {
    alive.current = true;
    return () => { alive.current = false; readTicket.current += 1; createTicket.current += 1; };
  }, []);

  useEffect(() => {
    const ticket = ++readTicket.current;
    setRead(previous => ({ ...previous, status: 'loading' }));
    setReadError('');
    api.listProjects().then(items => {
      if (!alive.current || readTicket.current !== ticket) return;
      setRead({ status: 'ready', projects: items });
    }).catch(cause => {
      if (!alive.current || readTicket.current !== ticket) return;
      setRead({ status: 'failed', projects: [] });
      setReadError(cause instanceof Error ? cause.message : '无法读取项目库');
    });
  }, [attempt]);

  async function create(template: string | null, initialName: string) {
    const ticket = ++createTicket.current;
    setCreateError('');
    setCreating(template ?? 'blank');
    try {
      const saved = await api.createProject(template, initialName.trim());
      // The answer belongs to the page that asked, and only while it exists.
      if (!alive.current || createTicket.current !== ticket) return;
      outcome('resolve');
      onOpen(saved.project_id);
    } catch (cause) {
      if (!alive.current || createTicket.current !== ticket) return;
      outcome('hold');
      setCreateError(creationReason(cause));
    } finally {
      if (alive.current && createTicket.current === ticket) setCreating(null);
    }
  }

  const count = read.status === 'loading' ? '读取中' : read.status === 'failed' ? '读取失败' : `${read.projects.length} 个项目`;

  return <main className="library-page page-pad">
    <aside className="library-context" aria-label="工作区说明">
      <header className="library-title"><span className="section-kicker">DESIGN WORKSPACE / 01</span><h1>Projects<span className="visually-hidden"> · 项目库</span></h1><p>从已保存的舰船继续，<br />或建立新的计算基线。</p></header>
      <div className="library-context-rule" aria-hidden="true"><SiteGeometry variant="rule" /></div>
      {anonymous && <div className="workspace-notice" role="note">
      <strong>本浏览器工作区</strong>
      <p className="workspace-summary">仅当前浏览器可见。请下载项目 JSON 备份；清除身份 Cookie 后无法自动找回。</p>
      <details><summary>保存与恢复说明</summary>
      <p>项目保存在这台设备的浏览器 Cookie 身份下，只有这个浏览器能看到它们。清除 Cookie、使用无痕窗口或换一台设备，都无法自动找回原来的工作区。需要留存时，请在项目页用「下载项目 JSON」保存完整文档。手工恢复时，先创建新项目，将备份的顶层 id 改为新项目的 id，再粘入「完整项目数据」并保存。运行页导出的 JSON/CSV 是计算报告，不是项目备份。</p>
      </details>
      </div>}
      <p className="library-context-foot">INPUT / REVISION / RESULT<br /><span>输入、修订与结果分别保存</span></p>
    </aside>
    <div className="library-body">
    {createError && <div className="notice notice--error library-create-error" role="alert">创建失败：{createError}</div>}
    <section className="library-section" aria-labelledby="my-projects-title">
      <div className="section-heading library-section-heading"><div><span className="section-kicker">01 / SAVED PROJECTS</span><h2 id="my-projects-title">我的舰船</h2></div><span data-read-state={read.status}>{count}</span><SiteGeometry /></div>
      {read.status === 'loading' ? <ReadPending scope="library" object="项目库" className="library-read" />
        : read.status === 'failed' ? <ReadFailure title="无法读取项目库" detail={readError} retryLabel="重新读取项目库"
            onRetry={() => setAttempt(current => current + 1)} onBack={undefined} />
          : read.projects.length === 0
        ? <div className="empty-state"><span className="empty-glyph" aria-hidden="true">⌁</span><h3>还没有舰船项目</h3><p>选择下方的案例开始。每次计算都会固定输入修订，方便复核。</p></div>
        : <div className="project-list">{read.projects.map(project => <button key={project.project_id} className="project-row" data-audio="manual" onClick={() => onOpen(project.project_id)}>
            <span className="project-row-mark" aria-hidden="true" /><span className="project-row-main"><strong>{project.name}</strong><small>修订 {project.revision} · {new Date(project.updated_at).toLocaleDateString('zh-CN')}</small></span><span aria-hidden="true">↗</span>
          </button>)}</div>}
    </section>
    <section className="library-section" aria-labelledby="template-title">
      <div className="section-heading library-section-heading"><div><span className="section-kicker">02 / NEW PROJECT</span><h2 id="template-title">从基线开始</h2></div><span>模板只作为起点</span><SiteGeometry /></div>
      <div className="template-grid">{templates.map((template, index) => <button className="template-card" key={template.key} onClick={() => create(template.key, template.name)} disabled={creating !== null}>
        <span className="template-number">0{index + 1}</span><span className="template-identity"><strong>{template.name}</strong><span className="template-tag">{template.tag}</span></span><p>{template.text}</p><span className="template-action">{creating === template.key ? '建立中…' : '建立项目 ↗'}</span>
      </button>)}</div>
      <form className="blank-project" onSubmit={event => { event.preventDefault(); if (name.trim()) void create(null, name); }}>
        <div><strong>空白项目</strong><p>从自己的数据开始，未知输入会继续保持未知。</p></div>
        <label className="visually-hidden" htmlFor="blank-name">新项目名称</label><input id="blank-name" required value={name} onChange={event => setName(event.target.value)} placeholder="新项目名称" />
        <button className="button button--secondary" disabled={creating !== null || !name.trim()} type="submit">{creating === 'blank' ? '建立中…' : '创建空白项目'}</button>
      </form>
    </section>
    </div>
  </main>;
}

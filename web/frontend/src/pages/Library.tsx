import { useEffect, useState } from 'react';

import * as api from '../api';
import type { ProjectSummary } from '../types';

const templates = [
  { key: 'analytic_box', name: '解析方箱', tag: '解析基准', text: '有明确几何与解析解，适合熟悉项目和验证流程。' },
  { key: 'generic_steamer', name: '通用试验船', tag: '示范案例', text: '带完整型线与载荷，用于探索多工况计算。' },
  { key: 'queen_mary_1913', name: 'HMS Queen Mary', tag: '史实未认证代理', text: '一战战列巡洋舰工程代理。所有估算和史料缺口均保留标记。' },
] as const;

export function Library({ onOpen }: { onOpen: (id: string) => void }) {
  const [projects, setProjects] = useState<ProjectSummary[] | null>(null);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState<string | null>(null);
  const [name, setName] = useState('');

  useEffect(() => {
    let active = true;
    api.listProjects().then(items => { if (active) setProjects(items); })
      .catch(cause => { if (active) setError(cause instanceof Error ? cause.message : '无法读取项目库'); });
    return () => { active = false; };
  }, []);

  async function create(template: string | null, initialName: string) {
    setError('');
    setCreating(template ?? 'blank');
    try {
      const saved = await api.createProject(template, initialName.trim());
      onOpen(saved.project_id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法创建项目');
    } finally {
      setCreating(null);
    }
  }

  return <div className="library-page page-pad">
    <div className="page-heading">
      <div><span className="section-kicker">WORKSPACE / 001</span><h1>项目库</h1><p>从已保存的舰船继续，或建立新的计算基线。</p></div>
      <span className="heading-rule" aria-hidden="true" />
    </div>
    {error && <div className="notice notice--error" role="alert">{error}</div>}
    <section className="library-section" aria-labelledby="my-projects-title">
      <div className="section-heading"><h2 id="my-projects-title">我的舰船</h2><span>{projects === null ? '读取中' : `${projects.length} 个项目`}</span></div>
      {projects === null ? <div className="loading-skeleton" aria-label="正在读取项目" /> : projects.length === 0
        ? <div className="empty-state"><span className="empty-glyph" aria-hidden="true">⌁</span><h3>还没有舰船项目</h3><p>选择下方的案例开始。每次计算都会固定输入修订，方便复核。</p></div>
        : <div className="project-list">{projects.map(project => <button key={project.project_id} className="project-row" onClick={() => onOpen(project.project_id)}>
            <span className="project-row-mark" aria-hidden="true" /><span className="project-row-main"><strong>{project.name}</strong><small>修订 {project.revision} · {new Date(project.updated_at).toLocaleDateString('zh-CN')}</small></span><span aria-hidden="true">↗</span>
          </button>)}</div>}
    </section>
    <section className="library-section" aria-labelledby="template-title">
      <div className="section-heading"><h2 id="template-title">从基线开始</h2><span>模板只作为起点</span></div>
      <div className="template-grid">{templates.map((template, index) => <button className="template-card" key={template.key} onClick={() => create(template.key, template.name)} disabled={creating !== null}>
        <span className="template-number">0{index + 1}</span><span className="template-mark" aria-hidden="true" /><strong>{template.name}</strong><span className="template-tag">{template.tag}</span><p>{template.text}</p><span className="template-action">{creating === template.key ? '建立中…' : '建立项目 ↗'}</span>
      </button>)}</div>
      <form className="blank-project" onSubmit={event => { event.preventDefault(); if (name.trim()) void create(null, name); }}>
        <div><strong>空白项目</strong><p>从自己的数据开始，未知输入会继续保持未知。</p></div>
        <label className="visually-hidden" htmlFor="blank-name">新项目名称</label><input id="blank-name" required value={name} onChange={event => setName(event.target.value)} placeholder="新项目名称" />
        <button className="button button--secondary" disabled={creating !== null || !name.trim()} type="submit">创建空白项目</button>
      </form>
    </section>
  </div>;
}

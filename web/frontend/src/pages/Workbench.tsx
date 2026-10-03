import { useCallback, useEffect, useRef, useState } from 'react';

import * as api from '../api';
import { DeckFreeboardEditor } from '../components/DeckFreeboardEditor';
import { GunsEditor } from '../components/GunsEditor';
import { WeaponsEditor } from '../components/WeaponsEditor';
import { ArmourEditor } from '../components/ArmourEditor';
import { EnginesEditor } from '../components/EnginesEditor';
import { HullSupplementEditor } from '../components/HullSupplementEditor';
import { PerformanceEditor, EMPTY_REQUEST, buildOptions, type RequestDraft } from '../components/PerformanceEditor';
import { currentRun, eligibleResultRun, ledgerItems, RESULT_STATUSES } from '../components/formModel';
import { getDeck, type DeckInput } from '../components/deckModel';
import { FactField } from '../components/FactField';
import { ProjectNav, type Chapter } from '../components/ProjectNav';
import { StatusBadge } from '../components/StatusBadge';
import type { ProjectDocument, ProjectView, RunView } from '../types';

const HULL_FIELDS = [
  { key: 'loa_m', alternate: 'length_m', label: '船长 · m', hint: '全长（LOA），保留输入口径' },
  { key: 'lwl_m', label: '水线长 · m', hint: '计算水线长度' },
  { key: 'beam_m', label: '型宽 · m', hint: '最大型宽' },
  { key: 'draught_normal_m', alternate: 'draft_m', label: '设计吃水 · m', hint: '正常工况参考值' },
  { key: 'block_coeff', label: '方形系数', hint: '无量纲' },
  { key: 'waterplane_coeff', label: '水线面系数', hint: '无量纲' },
] as const;

const CHAPTER_DATA: Partial<Record<Chapter, { key: string; title: string; intro: string }>> = {
  armour: { key: 'systems', title: '装甲与武备', intro: '这里编辑系统事实；质量仍须在所选载荷账本中明确绑定，不能重复计重。' },
  guns: { key: 'systems', title: '火炮武备', intro: '声明炮数与每炮携弹数；单发弹重优先取自账本弹药模型，没有模型时可声明仅用于报告的弹丸质量。全舰携带量仍取自账本。' },
  weapons: { key: 'systems', title: '鱼雷与水雷武备', intro: '声明鱼雷、水雷、深弹及五个杂项位置分区；系统质量取自所选载荷账本，位置分区声明质量仅用于报告，不另加排水量。' },
  stability: { key: 'deck', title: '甲板与稳性输入', intro: '端点、干舷与参考长度需要独立来源。未知值请保持空缺。' },
  propulsion: { key: 'systems', title: '动力系统', intro: '锅炉、燃料和传动事实来自项目输入；计算结果只出现在运行记录里。' },
  damage: { key: 'compartments', title: '舱室与破损', intro: '舱室与开口定义决定破损场景的适用范围。' },
};

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function errorMessage(cause: unknown): string {
  if (cause instanceof api.ApiError && Array.isArray(cause.detail)) {
    return cause.detail.map((item: { path?: string; message?: string }) => `${item.path ?? '输入'}：${item.message ?? '无效'}`).slice(0, 4).join('；');
  }
  return cause instanceof Error ? cause.message : '操作未完成，请检查输入';
}

function validationDetails(cause: unknown): Array<{ path: string; message: string }> {
  if (!(cause instanceof api.ApiError) || !Array.isArray(cause.detail)) return [];
  return cause.detail.map(item => {
    const path = typeof item.path === 'string' ? item.path : Array.isArray(item.loc) ? item.loc.join('.') : '项目';
    return { path, message: String(item.message ?? item.msg ?? '输入无效') };
  });
}

// A stored result may only be presented as "current" when it describes exactly
// this project, this saved revision, this condition, and it carries a payload.
// A condition switch, an edit or a foreign response fails this synchronously.
function matchesRun(run: RunView | null | undefined, projectId: string, revision: number, conditionId: string): boolean {
  return !!run && run.project_id === projectId && run.revision === revision
    && run.condition_id === conditionId && RESULT_STATUSES.includes(run.status) && !!run.result;
}

function projectRenderError(value: unknown, projectId: string): string | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return '项目 JSON 根节点无效';
  const row = value as Record<string, unknown>;
  if (row.id !== projectId) return '项目 ID 必须与当前项目一致';
  if (row.schema !== 'plimsoll-project-1') return '项目 schema 无效';
  if (typeof row.name !== 'string' || !row.name.trim()) return '项目缺少有效舰名';
  if (!row.hull || typeof row.hull !== 'object' || Array.isArray(row.hull)) return '项目缺少船型 hull';
  if (!Array.isArray(row.loading_conditions) || !row.loading_conditions.every(
    item => item && typeof item === 'object' && typeof item.id === 'string'
      && (item.label === undefined || item.label === null || typeof item.label === 'string'),
  )) return '项目缺少有效工况 loading_conditions';
  if (!Array.isArray(row.weight_groups) || !row.weight_groups.every(
    group => group && typeof group === 'object' && typeof group.id === 'string'
      && (group.label === undefined || group.label === null || typeof group.label === 'string')
      && Array.isArray(group.items) && group.items.every((item: unknown) => item && typeof item === 'object' && !Array.isArray(item)),
  )) return '项目缺少有效重量分组 weight_groups';
  return null;
}

export function Workbench({ projectId, onBack, onRun }: { projectId: string; onBack: () => void; onRun: (runId: string) => void }) {
  const [view, setView] = useState<ProjectView | null>(null);
  const [draft, setDraft] = useState<ProjectDocument | null>(null);
  const [chapter, setChapter] = useState<Chapter>('overview');
  const [conditionId, setConditionId] = useState('');
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [conflict, setConflict] = useState<number | null>(null);
  const [jsonText, setJsonText] = useState('');
  const [jsonError, setJsonError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Array<{ path: string; message: string }>>([]);
  const [inspected, setInspected] = useState<{ label: string; source: string; estimate: boolean } | null>(null);
  const [runs, setRuns] = useState<RunView[]>([]);
  const [runResult, setRunResult] = useState<RunView | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);
  const [performanceRequest, setPerformanceRequest] = useState<RequestDraft>(EMPTY_REQUEST);
  const runRequest = buildOptions(performanceRequest);
  const draftGeneration = useRef(0);

  useEffect(() => {
    let active = true;
    api.getProject(projectId).then(saved => {
      if (!active) return;
      setView(saved);
      setDraft(structuredClone(saved.project));
      setPerformanceRequest(EMPTY_REQUEST);
      setConditionId(saved.project.loading_conditions[0]?.id ?? '');
      setDirty(false);
      setError('');
    }).catch(cause => { if (active) setError(errorMessage(cause)); });
    return () => { active = false; };
  }, [projectId]);

  useEffect(() => {
    let active = true;
    api.listRuns(projectId).then(items => { if (active) setRuns(items); }).catch(() => { /* Project editing remains usable if history is unavailable. */ });
    return () => { active = false; };
  }, [projectId]);

  // The list endpoint never carries result payloads (the backend builds run
  // summaries with `include_result=False`), so retrieve exactly one run: the
  // newest completed/partial run of the saved revision and selected condition.
  //
  // Identity is re-checked synchronously at render time by `currentRun`, so a
  // condition switch or an unsaved draft hides the previous result immediately
  // rather than after the in-flight request resolves. The response is accepted
  // only when it still matches the candidate that requested it.
  useEffect(() => {
    const revision = view?.revision ?? -1;
    const candidate = eligibleResultRun(runs, revision, conditionId);
    // A run list entry may already carry its payload; use it directly and make
    // no request. Only a payload-less entry needs the single bounded retrieval.
    setPendingRunId(candidate && !candidate.result ? candidate.id : null);
    if (!candidate || dirty) { setRunResult(null); return; }
    if (candidate.result) { setRunResult(matchesRun(candidate, projectId, revision, conditionId) ? candidate : null); return; }
    let active = true;
    api.getRun(candidate.id).then(full => {
      if (!active) return;
      setRunResult(matchesRun(full, projectId, revision, conditionId) ? full : null);
    }).catch(() => { if (active) setRunResult(null); });
    return () => { active = false; };
  }, [runs, view?.revision, conditionId, dirty, projectId]);

  useEffect(() => {
    if (!draft) return;
    const section = CHAPTER_DATA[chapter];
    const value = chapter === 'json' ? draft : section ? draft[section.key] : null;
    setJsonText(JSON.stringify(value ?? (chapter === 'damage' ? [] : {}), null, 2));
    setJsonError('');
  }, [chapter, draft]);

  function updateDraft(next: ProjectDocument) {
    draftGeneration.current += 1;
    setDraft(next);
    if (!next.loading_conditions.some(c => c.id === conditionId)) setConditionId(next.loading_conditions[0]?.id ?? '');
    setDirty(true);
    setConflict(null);
    setError('');
    setFieldErrors([]);
  }

  function updateHull(key: string, value: string) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.hull[key] = value.trim() === '' ? null : Number(value);
    updateDraft(next);
  }

  function updateMass(groupIndex: number, itemIndex: number, key: string, value: string) {
    if (!draft) return;
    const next = structuredClone(draft);
    next.weight_groups[groupIndex].items[itemIndex][key] = key === 'source' ? value : value.trim() === '' ? null : Number(value);
    updateDraft(next);
  }

  function patchDeck(next: DeckInput) {
    if (!draft) return;
    const prev = (draft as Record<string, unknown>).deck;
    const prevTop = prev && typeof prev === 'object' ? { ...(prev as Record<string, unknown>) } : {};
    const newDeck = {
      ...prevTop,
      estimate: next.estimate,
      source: next.source,
      points: next.points,
      segments: next.segments,
      reference_length_m: next.reference_length_m,
    };
    const clone = structuredClone(draft) as Record<string, unknown>;
    clone.deck = newDeck;
    updateDraft(clone as ProjectDocument);
  }

  function getWeapons(): Record<string, unknown> {
    const systems = (draft as Record<string, unknown>).systems;
    if (!systems || typeof systems !== 'object' || Array.isArray(systems)) return {};
    const weapons = (systems as Record<string, unknown>).weapons;
    return weapons && typeof weapons === 'object' && !Array.isArray(weapons) ? (weapons as Record<string, unknown>) : {};
  }

  function patchBattery(batteryId: string, next: Record<string, unknown>) {
    if (!draft) return;
    const clone = structuredClone(draft) as Record<string, unknown>;
    const systems = (clone.systems ?? {}) as Record<string, unknown>;
    const weapons = (systems.weapons ?? {}) as Record<string, unknown>;
    weapons[batteryId] = next;
    systems.weapons = weapons;
    clone.systems = systems;
    updateDraft(clone as ProjectDocument);
  }

  function patchWeapons(leafId: string, next: Record<string, unknown>) {
    if (!draft) return;
    const clone = structuredClone(draft) as Record<string, unknown>;
    const systems = (clone.systems ?? {}) as Record<string, unknown>;
    const weapons = (systems.weapons ?? {}) as Record<string, unknown>;
    weapons[leafId] = next;
    systems.weapons = weapons;
    clone.systems = systems;
    updateDraft(clone as ProjectDocument);
  }

  async function save() {
    if (!view || !draft || !dirty) return;
    const submittedGeneration = draftGeneration.current;
    setBusy(true);
    setError('');
    try {
      const saved = await api.saveProject(projectId, { base_revision: view.revision, project: draft });
      setView(saved);
      if (draftGeneration.current === submittedGeneration) {
        setDraft(structuredClone(saved.project));
        setDirty(false);
      } else {
        setDirty(true);
      }
      setConflict(null);
      setFieldErrors([]);
    } catch (cause) {
      if (cause instanceof api.ApiError && cause.status === 409) {
        const detail = cause.detail as { current_revision?: number };
        setConflict(detail.current_revision ?? -1);
      } else {
        setError(errorMessage(cause));
        setFieldErrors(validationDetails(cause));
      }
    } finally { setBusy(false); }
  }

  async function reload() {
    setBusy(true);
    try {
      const saved = await api.getProject(projectId);
      setView(saved);
      setDraft(structuredClone(saved.project));
      setDirty(false);
      setConflict(null);
      setError('');
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  async function run() {
    if (!view || !conditionId || dirty || runRequest.error) return;
    setBusy(true);
    try {
      const queued = await api.enqueueRun(projectId, { revision: view.revision, condition_id: conditionId, options: runRequest.options });
      onRun(queued.id);
    } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }

  function applyJson() {
    if (!draft) return;
    try {
      const parsed: unknown = JSON.parse(jsonText);
      if (chapter === 'json') {
        const problem = projectRenderError(parsed, projectId);
        if (problem) throw new Error(problem);
        updateDraft(parsed as ProjectDocument);
      } else {
        const section = CHAPTER_DATA[chapter];
        if (!section) return;
        const next = structuredClone(draft);
        next[section.key] = parsed;
        updateDraft(next);
      }
      setJsonError('');
    } catch (cause) { setJsonError(cause instanceof Error ? cause.message : 'JSON 格式无效'); }
  }

  if (!draft || !view) return <div className="page-pad"><p className="section-kicker">WORKSPACE / LOADING</p>{error ? <div className="notice notice--error" role="alert">{error}</div> : <div className="loading-skeleton" aria-label="正在读取舰船" />}</div>;

  const hull = draft.hull ?? {};
  // Validate identity here, in render, rather than relying on the effect having
  // run: a stale or in-flight result must never be displayed for the current
  // revision/condition.
  const selectedRun = currentRun(runResult, projectId, view.revision, conditionId, dirty);
  const ledger = ledgerItems(draft);
  const visibleRuns = selectedRun ? [selectedRun] : [];
  return <div className="workbench-layout">
    <ProjectNav name={draft.name} active={chapter} onSelect={setChapter} onBack={onBack} />
    <main className="workbench-main">
      <div className="workbench-toolbar"><div className="breadcrumbs"><button onClick={onBack}>项目库</button><span>/</span><strong>{draft.name}</strong></div>
        <div className="toolbar-actions"><span className={`save-state ${dirty ? 'save-state--dirty' : ''}`}><i aria-hidden="true" />{dirty ? '未保存修改' : `已保存 · 修订 ${view.revision}`}</span>
          <button className="button button--secondary" onClick={save} disabled={!dirty || busy}>保存修订</button>
          <button className="button button--primary" onClick={run} disabled={dirty || !conditionId || busy || !!runRequest.error} title={dirty ? '先保存当前修改再运行计算' : undefined}>{busy ? '请稍候…' : '运行计算 ↗'}</button></div>
      </div>
      <div className="workbench-content">
        <header className="vessel-header"><span className="section-kicker">VESSEL / {draft.id.slice(0, 8).toUpperCase()}</span><div className="vessel-title-row"><h1>{draft.name}</h1><span className="proxy-label">{draft.name.toLowerCase().includes('queen mary') ? '工程代理 · 非史实认证' : '项目输入'}</span></div><p>选择工况并保存输入后运行。计算状态与历史适用性分别呈现。</p></header>
        <div className="condition-strip"><label htmlFor="condition">当前工况</label><select id="condition" value={conditionId} onChange={event => setConditionId(event.target.value)}>{draft.loading_conditions.length === 0 ? <option value="">尚无工况</option> : draft.loading_conditions.map(item => <option key={item.id} value={item.id}>{item.label || item.id}</option>)}</select><span>已选修订 {view.revision} · 计算不会读取未保存的修改</span></div>
        {error && <div className="notice notice--error" role="alert">{error}</div>}
        {conflict !== null && <div className="notice notice--conflict" role="alert"><strong>服务器已有修订 {conflict}</strong><p>你的修改仍留在此页。复制后再载入最新版本，避免覆盖他人的或另一标签页的工作。</p><div className="notice-actions"><button className="button button--secondary" onClick={() => { void navigator.clipboard?.writeText(JSON.stringify(draft, null, 2)); }}>复制我的修改</button><button className="button button--primary" onClick={() => { void reload(); }}>重新载入</button></div></div>}
        {chapter === 'overview' && <section className="overview-grid"><div className="metric-grid">
          <FactField label="船长" value={numeric(hull.loa_m ?? hull.length_m)} unit="m" status="known" source="项目输入" />
          <FactField label="型宽" value={numeric(hull.beam_m)} unit="m" status="known" source="项目输入" />
          <FactField label="设计吃水" value={numeric(hull.draught_normal_m ?? hull.draft_m)} unit="m" status="known" source="项目输入" />
          <FactField label="重量条目" value={draft.weight_groups.reduce((sum, group) => sum + group.items.length, 0)} unit="项" status="known" source="当前修订" />
        </div><div className="overview-panel"><div className="section-heading"><h2>纵向概览</h2><span>结构示意 · 不按比例</span></div><svg viewBox="0 0 780 180" role="img" aria-label="舰船轮廓示意，不按比例"><path className="ship-outline" d="M40 96 L72 74 L166 67 L255 64 L365 67 L470 65 L592 70 L705 78 L741 96 L726 118 Q450 143 101 118 Z"/><path className="ship-waterline" d="M28 105 H752"/><path className="ship-mast" d="M290 67 L314 13 L339 67 M311 65 L313 14 M510 67 L525 32 L541 68"/><rect className="ship-detail" x="353" y="35" width="22" height="31"/><rect className="ship-detail" x="402" y="25" width="24" height="40"/><rect className="ship-detail" x="466" y="34" width="22" height="31"/></svg><p className="diagram-caption">仅表达船体与水线阅读关系；真实型线以项目数据和计算结果为准。</p></div><div className="overview-callout"><span className="section-kicker">NEXT STEP / 下一步</span><h2>先确认输入，再看结果</h2><p>从左侧章节检查主尺度、载荷与来源。运行后可查看各阶段的结果、限制与报告。</p><button className="text-button" onClick={() => setChapter('hull')}>编辑船型数据 ↗</button></div>{runs.length > 0 && <div className="overview-panel"><div className="section-heading"><h2>最近运行</h2><span>保存的输入快照</span></div><div className="run-history">{runs.slice(0, 6).map(item => <button key={item.id} onClick={() => onRun(item.id)}><span>{item.condition_id} · 修订 {item.revision}</span><strong><StatusBadge status={item.status} /></strong><small>{new Date(item.created_at).toLocaleString('zh-CN')}</small><span aria-hidden="true">↗</span></button>)}</div></div>}</section>}
        {chapter === 'hull' && <section className="editor-section"><div className="section-heading"><h2>船型与几何</h2><span>单位以项目契约为准</span></div><p className="section-intro">主尺度只记录已知输入。留空表示未知，不自动补零。复杂型线可在“项目数据”中编辑。</p><div className="field-grid">{HULL_FIELDS.map(field => { const alternate = 'alternate' in field ? field.alternate : undefined; const key = alternate && !(field.key in hull) ? alternate : field.key; const value = hull[key]; const issue = fieldErrors.find(item => item.path.includes(`hull.${key}`) || item.path.includes(`hull['${key}']`)); return <label className="field-label" key={field.key}>{field.label}<input type="number" step="any" aria-invalid={Boolean(issue)} value={typeof value === 'number' ? value : ''} onChange={event => updateHull(key, event.target.value)} placeholder="未知" onFocus={() => setInspected({ label: field.label, source: '当前项目输入；具体史料来源请在项目数据中声明', estimate: false })} /><small>{field.hint}</small>{issue && <span className="field-error" role="alert">{issue.message}</span>}</label>; })}</div></section>}
        {chapter === 'hull' && <section className="editor-section"><HullSupplementEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'performance' && <section className="editor-section"><div className="section-heading"><h2>性能与工况研究</h2></div><PerformanceEditor project={draft} run={selectedRun} request={performanceRequest} onChange={updateDraft} onRequestChange={setPerformanceRequest} /></section>}
        {chapter === 'weights' && <section className="editor-section"><div className="section-heading"><h2>重量与载荷</h2><span>{draft.weight_groups.length} 个分组</span></div><p className="section-intro">这里只修改已有条目。质量、重心和来源随项目修订保存；新增分组可通过“项目数据”编辑。</p>{draft.weight_groups.length === 0 ? <div className="empty-state compact"><h3>还没有重量分组</h3><p>空白项目可先从项目数据中添加账本结构。</p></div> : draft.weight_groups.map((group, groupIndex) => <div className="weight-group" key={group.id}><div className="weight-group-title"><h3>{group.label || group.id}</h3><span>{group.items.length} 项</span></div><div className="weight-list">{group.items.map((item, itemIndex) => <div className="weight-row" key={String(item.id ?? itemIndex)}><strong>{String(item.id ?? `条目 ${itemIndex + 1}`)}</strong><label>质量 · t<input type="number" step="any" value={typeof item.mass_t === 'number' ? item.mass_t : ''} onChange={event => updateMass(groupIndex, itemIndex, 'mass_t', event.target.value)} /></label><label>纵向位置 · m<input type="number" step="any" value={typeof item.x_m === 'number' ? item.x_m : ''} onChange={event => updateMass(groupIndex, itemIndex, 'x_m', event.target.value)} /></label><label>来源<input value={typeof item.source === 'string' ? item.source : ''} onChange={event => updateMass(groupIndex, itemIndex, 'source', event.target.value)} /></label></div>)}</div></div>)}</section>}
        {chapter === 'stability' && <section className="editor-section"><div className="section-heading"><h2>{CHAPTER_DATA[chapter]?.title}</h2><span>端点、干舷与参考长度</span></div><p className="section-intro">{CHAPTER_DATA[chapter]?.intro}</p><DeckFreeboardEditor deck={getDeck(draft)} runs={visibleRuns} onPatchDeck={patchDeck} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">用于编辑表单未覆盖的字段（如 y_m / z_m）。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => setJsonText(event.target.value)} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button><span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'guns' && <section className="editor-section"><div className="section-heading"><h2>{CHAPTER_DATA[chapter]?.title}</h2><span>每个炮组声明输入 · 未知留空</span></div><p className="section-intro">{CHAPTER_DATA[chapter]?.intro}</p><GunsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchBattery={patchBattery} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">表单未覆盖的字段（如 mounts / armour 边界）可在此编辑 systems 原始 JSON。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => setJsonText(event.target.value)} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button><span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'weapons' && <section className="editor-section"><div className="section-heading"><h2>{CHAPTER_DATA[chapter]?.title}</h2><span>鱼雷 / 水雷 / 深弹 / 杂项分区 · 未知留空</span></div><p className="section-intro">{CHAPTER_DATA[chapter]?.intro}</p><WeaponsEditor weapons={getWeapons()} runs={visibleRuns} ledger={ledger} onPatchLeaf={patchWeapons} /><details className="advanced-json"><summary>高级：原始契约字段</summary><p className="section-intro">表单未覆盖的字段（如 torpedo 的 weight_item_ids 绑定）可在此编辑 systems 原始 JSON。应用后仍需点击“保存修订”。</p><label className="field-label" htmlFor="chapter-json">章节数据</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => setJsonText(event.target.value)} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button><span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</details></section>}
        {chapter === 'armour' && <section className="editor-section"><div className="section-heading"><h2>装甲输入与研究</h2></div><ArmourEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {chapter === 'propulsion' && <section className="editor-section"><div className="section-heading"><h2>动力输入与研究</h2></div><EnginesEditor project={draft} run={selectedRun} onChange={updateDraft} /></section>}
        {(chapter === 'damage' || chapter === 'json') && <section className="editor-section"><div className="section-heading"><h2>{chapter === 'json' ? '完整项目数据' : CHAPTER_DATA[chapter]?.title}</h2><span>结构化 JSON</span></div><p className="section-intro">{chapter === 'json' ? '这里可编辑所有符合 plimsoll-project-1 契约的字段。应用后请保存修订；服务端会验证并返回具体字段路径。' : CHAPTER_DATA[chapter]?.intro}</p><label className="field-label" htmlFor="chapter-json">{chapter === 'json' ? '项目 JSON' : '章节数据'}</label><textarea id="chapter-json" className="json-editor" spellCheck={false} value={jsonText} onChange={event => setJsonText(event.target.value)} /><div className="json-actions"><button className="button button--secondary" type="button" onClick={applyJson}>应用到草稿</button><span>应用后仍须点击“保存修订”</span></div>{jsonError && <p className="form-error" role="alert">{jsonError}</p>}</section>}
      </div>
    </main>
    <aside className="inspector" aria-label="来源与诊断"><span className="section-kicker">TRACE / 来源与诊断</span><h2>{inspected?.label || '当前输入'}</h2><p>点击字段查看输入语义。计算完成后，结果来源与方法边界会在报告中逐项展开。</p><div className="inspector-rule" /><dl><dt>数据状态</dt><dd>{inspected?.estimate ? '工程估算' : '项目输入'}</dd><dt>来源</dt><dd>{inspected?.source || '请在项目中保留原始来源；未提供的事实保持未知'}</dd><dt>请求身份</dt><dd>运行后生成并固定指纹</dd></dl><div className="inspector-bottom">水线 / 来源 / 适用范围</div></aside>
  </div>;
}

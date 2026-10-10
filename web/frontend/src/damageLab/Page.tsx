import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import * as accountApi from '../api';
import type { ProjectView } from '../types';
import * as api from './api';
import { active, draftIdentity, frameAt, numeric, STATUS, visibleResult } from './model';
import type { Experiment, LabRun, Room, Setup, Vec3 } from './types';
import Inspector, { CoreEvidence } from './Inspector';
import './lab.css';

const Scene = lazy(()=>import('./Scene'));
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
function message(cause: unknown): string {
  if (cause instanceof accountApi.ApiError && Array.isArray(cause.detail)) return cause.detail.map(d=>d.message ?? d.msg ?? JSON.stringify(d)).join(' · ');
  return cause instanceof Error ? cause.message : '读取失败，请重试';
}
function download(name: string, data: unknown) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a'); link.href=url; link.download=name; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export default function DamageLabPage({ projectId, onBack, onProject }: {
  projectId: string; onBack: () => void; onProject: (id: string) => void;
}) {
  const [view,setView]=useState<ProjectView|null>(null), [setup,setSetup]=useState<Setup|null>(null);
  const [draft,setDraft]=useState<Experiment|null>(null), [condition,setCondition]=useState('');
  const [run,setRun]=useState<LabRun|null>(null), [history,setHistory]=useState<LabRun[]>([]);
  const [loading,setLoading]=useState(projectId!=='demo'), [busy,setBusy]=useState(false), [error,setError]=useState('');
  const [attempt,setAttempt]=useState(0), [selected,setSelected]=useState(''), [target,setTarget]=useState('');
  const [frame,setFrame]=useState(0), [playing,setPlaying]=useState(false), [speed,setSpeed]=useState(1);
  const [json,setJson]=useState(''), [pollAttempt,setPollAttempt]=useState(0);
  const alive=useRef(true), busyNow=useRef(false), operation=useRef(0), draftTicket=useRef(0);
  const result=view ? visibleResult(run,view.project_id,view.revision,condition,draft) : null;
  const state=frameAt(result,frame);
  const snapshotProject=result?.input_snapshot ?? view?.project;
  const rooms=(snapshotProject?.compartments ?? []) as Room[];

  useEffect(()=>{ alive.current=true; return ()=>{alive.current=false;operation.current++;}; },[]);
  useEffect(()=>{
    const controller=new AbortController(); const token=++operation.current;
    setError(''); setRun(null); setPlaying(false); setView(null); setDraft(null); setSetup(null); setHistory([]);
    if(projectId==='demo') { setLoading(false); return ()=>controller.abort(); }
    setLoading(true);
    Promise.all([api.readProject(projectId,controller.signal),api.readSetup(projectId,controller.signal),api.listRuns(projectId,controller.signal)])
      .then(async ([project,prepared,jobs])=>{
        if(controller.signal.aborted || token!==operation.current) return;
        if(project.revision!==prepared.revision) throw new Error('保存修订已变化，请重新读取');
        let experiment=prepared.experiment;
        try { const stored=JSON.parse(sessionStorage.getItem('plimsoll:lab-draft:'+projectId) ?? 'null');
          if(stored?.revision===project.revision && stored.experiment) {
            const checked=await api.preview(projectId,project.revision,project.project.loading_conditions[0]?.id ?? '',stored.experiment,controller.signal);
            experiment=checked.experiment;
          }
        } catch { /* Draft storage is optional; the server defaults remain usable. */ }
        if(controller.signal.aborted || token!==operation.current)return;
        setView(project);setSetup(prepared);setDraft(experiment);setHistory(jobs);
        setCondition(project.project.loading_conditions[0]?.id ?? '');
        setSelected(experiment?.modules[0]?.id ?? '');setTarget(experiment?.modules[0]?.id ?? '');
        setRun(jobs.find(job=>active(job)) ?? null);
      }).catch(cause=>{if(!controller.signal.aborted && token===operation.current)setError(message(cause));})
      .finally(()=>{if(!controller.signal.aborted && token===operation.current)setLoading(false);});
    return ()=>controller.abort();
  },[projectId,attempt]);

  useEffect(()=>{setPlaying(false);setFrame(0);setJson(draft ? JSON.stringify(draft,null,2) : '');},[draft,condition,run?.id]);
  useEffect(()=>{
    if(!run || !active(run))return;
    const controller=new AbortController();let timer: ReturnType<typeof setTimeout>;
    const id=run.id,fingerprint=run.request_fingerprint;
    async function poll(){
      try {
        const next=await api.readRun(id,controller.signal);
        if(controller.signal.aborted)return;
        if(next.request_fingerprint!==fingerprint || next.project_id!==projectId)throw new Error('返回试验身份不一致');
        setRun(previous=>previous?.id===id ? next : previous);
        setHistory(previous=>[next,...previous.filter(job=>job.id!==id)].slice(0,50));
        if(active(next))timer=setTimeout(poll,900);
      }catch(cause){if(!controller.signal.aborted)setError('状态读取中断：'+message(cause));}
    }
    void poll();return()=>{controller.abort();clearTimeout(timer);};
  },[run?.id,run?.status,projectId,pollAttempt]);
  useEffect(()=>{
    if(!playing || !result)return;
    const timer=setInterval(()=>setFrame(current=>{
      if(current>=result.snapshots.length-1){setPlaying(false);return current;}
      return current+1;
    }),600/speed);
    return()=>clearInterval(timer);
  },[playing,result,speed]);

  function edit(change:(next:Experiment)=>void){
    if(!draft)return;draftTicket.current++;const next=clone(draft);change(next);setDraft(next);setError('');
  }
  async function start(){
    if(!view || !draft || busyNow.current || active(run))return;
    busyNow.current=true;setBusy(true);setError('');setRun(null);setPlaying(false);
    const token=operation.current;
    try {const next=await api.enqueue(view.project_id,view.revision,condition,clone(draft));
      if(!alive.current || token!==operation.current)return;
      setRun(next);setHistory(previous=>[next,...previous]);
    }catch(cause){if(alive.current && token===operation.current)setError(message(cause));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function cancel(){
    if(!run || busyNow.current)return;busyNow.current=true;setBusy(true);setError('');
    const id=run.id,token=operation.current;
    try {const next=await api.cancel(id);if(alive.current && token===operation.current){setRun(previous=>previous?.id===id ? next : previous);setHistory(previous=>[next,...previous.filter(job=>job.id!==id)]);setPollAttempt(v=>v+1);}}
    catch(cause){if(alive.current && token===operation.current)setError(message(cause));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function createDemo(){
    if(busyNow.current)return;busyNow.current=true;setBusy(true);setError('');const token=operation.current;
    try {const demo=await api.readDemo();if(!alive.current || token!==operation.current)return;
      const saved=await accountApi.importProject(demo.project);
      if(!alive.current || token!==operation.current)return;
      try {sessionStorage.setItem('plimsoll:lab-draft:'+saved.project_id,JSON.stringify({revision:saved.revision,experiment:demo.experiment}));}catch{/* optional */}
      onProject(saved.project_id);
    }catch(cause){if(alive.current && token===operation.current)setError(message(cause));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function restore(job:LabRun){
    if(busyNow.current || active(run))return;busyNow.current=true;setBusy(true);setError('');const token=operation.current,ticket=++draftTicket.current;
    try{const saved=await api.readRun(job.id);if(!alive.current || token!==operation.current || ticket!==draftTicket.current)return;
      setDraft(clone(saved.request.experiment));setCondition(saved.condition_id);setRun(saved);
      setSelected(saved.request.experiment.modules[0]?.id ?? '');setTarget(saved.request.experiment.modules[0]?.id ?? '');
    }catch(cause){if(alive.current && token===operation.current && ticket===draftTicket.current)setError(message(cause));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function applyJson(){
    if(!view || busyNow.current)return;
    busyNow.current=true;setBusy(true);const token=operation.current,ticket=++draftTicket.current;
    try{
      const checked=await api.preview(view.project_id,view.revision,condition,JSON.parse(json));
      if(!alive.current || token!==operation.current || ticket!==draftTicket.current)return;
      const parsed=checked.experiment;
      setDraft(parsed);setTarget(parsed.modules[0].id);setSelected(parsed.modules[0].id);setError('');
    }catch(cause){if(alive.current && token===operation.current && ticket===draftTicket.current)setError(message(cause));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  const targetModule=draft?.modules.find(m=>m.id===target) ?? draft?.modules[0];
  const room=rooms.find(r=>r.id===targetModule?.compartment_id);
  function breach(enabled:boolean){edit(next=>{
    if(!room)return;
    next.breaches=enabled ? [{id:'declared-side-breach',from_id:'sea',to_id:room.id,
      position_m:[room.x_m,room.y_m+(room.y_m<0 ? -1:1)*room.beam_m/2,room.keel_to_bottom_m+.2],
      area_m2:.5,discharge_coefficient:.6,source:'User-declared boundary sea-link gameplay proxy; not surveyed hull skin',estimate:true}] : [];
  });}
  const mismatch=run && view && (run.revision!==view.revision || run.condition_id!==condition || draftIdentity(run.request.experiment)!==draftIdentity(draft));

  return <main className="damage-lab">
    <header className="lab-head"><div><span className="lab-kicker">PLIMSOLL / KNOWN HIT STUDIES</span><h1>Damage laboratory<span className="lab-red-dot" aria-hidden="true">.</span></h1></div>
      <button className="lab-link" onClick={onBack}>← 返回项目库</button></header>
    {error && <div role="alert" className="lab-error">{error}<button onClick={()=>{setAttempt(v=>v+1);setPollAttempt(v=>v+1);}} disabled={busy}>重新读取</button></div>}
    {loading ? <p role="status">正在读取舰船与试验配置…</p> : !view || !draft ? <section className="lab-welcome">
      <span className="lab-kicker">01 / EXPLICIT SYNTHETIC DEMO</span><h2>{view ? '当前舰船尚无可用试验布局' : '从一个明确的试验开始'}</h2>
      {setup?.diagnostics.map((d,i)=><p key={i}>{d.message}</p>)}
      <p>用单次已知命中，检查模块、舱室乘员与真实进水计算。36 米合成船体包含三处舱室和明确人数，外壳与核心共用型线，会另存为你的新项目。</p>
      <button className="lab-primary" onClick={createDemo} disabled={busy}>{busy ? '建立中…' : '建立合成试验场'}</button>
      <p className="lab-note">损伤与乘员规则是游戏估算；进水、平衡与剩余 GZ 来自 Plimsoll 核心。</p>
    </section> : <>
      <div className="lab-identity"><strong>{view.project.name}</strong><span>修订 {view.revision} / {condition}</span><span className="lab-note">KNOWN HIT → EQUIPMENT → CREW → SHIP</span></div>
      <div className="lab-grid">
        <form className="lab-setup" onSubmit={e=>{e.preventDefault();void start();}}>
          <span className="lab-kicker">01 / EXPERIMENT</span><h2>命中条件</h2>
          <label>载荷工况<select value={condition} onChange={e=>{draftTicket.current++;setCondition(e.target.value);}}>{view.project.loading_conditions.map(c=><option key={c.id} value={c.id}>{c.label || c.id}</option>)}</select></label>
          <label>命中目标<select value={target} onChange={e=>{setTarget(e.target.value);edit(next=>{const m=next.modules.find(v=>v.id===e.target.value);if(m)next.impact.position_m=clone(m.box.center_m);});}}>{draft.modules.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>
          <div className="lab-coordinates">{(['X','Y','Z'] as const).map((axis,i)=><label key={axis}>{axis} / m<input aria-label={`命中 ${axis}`} type="number" step=".1" value={draft.impact.position_m[i]} onChange={e=>{if(e.target.value!=='')edit(next=>{next.impact.position_m[i]=Number(e.target.value);});}} /></label>)}</div>
          <label>命中强度 <span>{numeric(draft.impact.severity,2)}</span><input aria-label="命中强度" type="range" min="0" max="1" step=".05" value={draft.impact.severity} onChange={e=>edit(next=>{next.impact.severity=Number(e.target.value);})} /></label>
          <label>影响半径 / m<input type="number" min="0" max="1000" step=".1" value={draft.impact.radius_m} onChange={e=>edit(next=>{next.impact.radius_m=Number(e.target.value);})} /></label>
          <div className="lab-pair"><label>时长 / s<input type="number" min="0" max="60" step="any" value={draft.duration_s} onChange={e=>edit(next=>{next.duration_s=Number(e.target.value);})} /></label><label>步长 / s<input type="number" min=".000001" max="60" step="any" value={draft.time_step_s} onChange={e=>edit(next=>{next.time_step_s=Number(e.target.value);})} /></label></div>
          <label className="lab-check"><input type="checkbox" checked={draft.breaches.length>0} onChange={e=>breach(e.target.checked)} />目标舱海水破口（替换）</label>
          {draft.breaches[0] && <label>首个破口面积 / m²<input type="number" min="0" step=".1" value={draft.breaches[0].area_m2} onChange={e=>edit(next=>{next.breaches[0].area_m2=Number(e.target.value);})} /></label>}
          {draft.breaches.map(b=><p className="lab-note" key={b.id}>{b.from_id} → {b.to_id} / {b.area_m2} m² / Cd {b.discharge_coefficient}</p>)}
          <p className="lab-note">无破口就不新增进水路径。强度与影响范围由你指定。</p>
          <button className="lab-primary" disabled={busy || active(run) || !condition}>{busy ? '提交中…' : '运行命中试验'}</button>
          {active(run) && <button type="button" onClick={()=>void cancel()} disabled={busy || run?.cancel_requested}>{run?.cancel_requested ? '正在取消…' : '取消试验'}</button>}
          <details><summary>乘员与规则</summary>
            {draft.crew_groups.map((group,i)=><label key={group.id}>{group.label} / 人<input type="number" min="0" max="100000" value={group.personnel ?? ''} placeholder="未知" onChange={e=>edit(next=>{next.crew_groups[i].personnel=e.target.value==='' ? null : Number(e.target.value);})} /></label>)}
            <p className="lab-note">空值保留未知。完整阈值、模块布局、来源和权属可在 JSON 配置中编辑。</p>
          </details>
        </form>
        <div className="lab-middle">
          <div className="lab-scene-head"><span className="lab-kicker">SPATIAL INSPECTOR / METRES</span><span>{run ? STATUS[run.status] : '待试验'}</span></div>
          <Suspense fallback={<div className="lab-scene-loading" role="status">正在加载三维检查视图…</div>}><Scene project={snapshotProject!} experiment={draft} state={state} selected={selected} onSelect={setSelected} /></Suspense>
          {run?.error && <p role="alert" className="lab-error">{run.error.message}</p>}
          {mismatch && <p className="lab-note lab-mismatch">配置已改变，原结果不显示在当前配置下。{run?.revision!==view.revision ? '原结果属于另一修订，可导出留存或重新运行。' : '可恢复保存的配置，或运行新试验。'}</p>}
          {result && <section aria-label="回放结果" className="lab-replay">
            <div className="lab-replay-head"><span className="lab-kicker">03 / ACCEPTED EVENTS</span><strong>{numeric(state?.time_s,2)} s</strong><span>{state?.event_index===-1 ? '命中前 / 尚无平衡解' : `事件 ${(state?.event_index ?? 0)+1}`}</span></div>
            <input aria-label="回放事件" type="range" min="0" max={Math.max(0,result.snapshots.length-1)} step="1" value={frame} onChange={e=>{setPlaying(false);setFrame(Number(e.target.value));}} />
            <div className="lab-replay-actions"><button onClick={()=>{setPlaying(false);setFrame(0);}}>回到命中前</button><button onClick={()=>{if(frame>=result.snapshots.length-1)setFrame(0);setPlaying(v=>!v);}}>{playing ? '暂停' : '播放'}</button><button onClick={()=>{setPlaying(false);setFrame(v=>Math.min(result.snapshots.length-1,v+1));}}>下一事件 →</button><button onClick={()=>{setPlaying(false);setFrame(result.snapshots.length-1);}}>最终接受状态</button><label>回放速度<select aria-label="回放速度" value={speed} onChange={e=>setSpeed(Number(e.target.value))}><option value=".5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select></label></div>
            <p className="lab-note">{state?.event_index===-1 ? '保留已声明的初始状态；物理量待核心求解。' : result.events[state?.event_index ?? 0]?.message}</p>
          </section>}
          <div className="lab-ship-metrics"><div><span>新增水量</span><strong>{numeric(state?.ship?.total_onboard_water_mass_t)} <small>t</small></strong></div><div><span>横倾</span><strong>{numeric(state?.ship?.equilibrium.heel_deg,2)} <small>°</small></strong></div><div><span>纵倾</span><strong>{numeric(state?.ship?.equilibrium.trim_deg,2)} <small>°</small></strong></div><div><span>质量残差</span><strong>{state?.ship ? state.ship.mass_conservation_error_t.toExponential(1) : '未知'} <small>t</small></strong></div></div>
        </div>
        <Inspector experiment={draft} state={state} selected={selected} onSelect={setSelected} />
      </div>
      {result && <CoreEvidence result={result} />}
      <section className="lab-records"><div><span className="lab-kicker">CONFIGURATION / REPRODUCE</span><h2>配置与复核</h2><p className="lab-note">配置可下载；结果包含冻结的舰船、工况、规则、事件和核心计算。CLI 能从这些输入复跑。</p>
        <button onClick={()=>download('damage-lab.experiment.json',draft)}>下载当前配置 JSON</button>
        <details><summary>编辑完整配置 JSON</summary><label>选择配置文件<input type="file" accept="application/json,.json" onChange={e=>{const file=e.target.files?.[0];if(!file)return;const token=operation.current,ticket=++draftTicket.current;if(file.size>1024*1024){setError('配置文件不能超过 1 MiB');return;}void file.text().then(text=>{if(alive.current && token===operation.current && ticket===draftTicket.current)setJson(text);}).catch(cause=>{if(alive.current && token===operation.current && ticket===draftTicket.current)setError(message(cause));});}} /></label><textarea aria-label="完整配置 JSON" spellCheck={false} value={json} onChange={e=>{draftTicket.current++;setJson(e.target.value);}} /><button disabled={busy} onClick={()=>void applyJson()}>应用配置</button></details>
      </div><div><span className="lab-kicker">FROZEN RUNS / LATEST 50</span><h2>试验记录</h2>
        {history.length ? history.map(job=><div className="lab-record" key={job.id}><button disabled={busy || active(run)} onClick={()=>void restore(job)}>{job.id.slice(0,8)} · R{job.revision} · {STATUS[job.status]}</button>{(job.has_result || job.result) && <span><a href={api.exportUrl(job.id,'json')} download={`damage-lab-${job.id}.json`}>JSON ↗</a><a href={api.exportUrl(job.id,'csv')} download={`damage-lab-${job.id}.csv`}>CSV ↗</a></span>}</div>) : <p className="lab-note">还没有保存的试验</p>}
        {run && <p className="lab-fingerprint">REQUEST / {run.request_fingerprint}</p>}
      </div></section>
    </>}
  </main>;
}

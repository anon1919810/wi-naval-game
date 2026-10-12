import { lazy, Suspense, useEffect, useMemo, useRef, useState } from 'react';
import * as accountApi from '../api';
import type { ProjectView, ProjectDocument } from '../types';
import * as api from './api';
import { active, draftIdentity, frameAt, visibleResult } from './model';
import type { Experiment, LabRun, Room, Setup, Vec3 } from './types';
import Inspector, { CoreEvidence, ShipMetrics } from './Inspector';
import Replay from './Replay';
import { DetonationControls, FragmentEvidence } from './Detonation';
import ComparisonPanel from './ComparisonPanel';
import { validTrialIdentity } from './comparison';
import { comparisonBaseline, replayEntries, type InspectionTarget } from './narrative';
import { buildPreset, PRESET_NAMES, type PresetAssumption, type PresetName, type PresetProblem } from './presets';
import { useLabCopy, useLabMessage, type LabKey } from '../i18n/lab';
import { useLabFormat } from '../i18n/labFormat';
import { useLanguage } from '../portfolio/LanguageProvider';
import './lab.css';

const Scene = lazy(()=>import('./Scene'));
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value));
class LabMessageError extends Error { constructor(readonly key: LabKey) { super(key); } }
function message(cause: unknown, l: ReturnType<typeof useLabCopy>): string {
  if (cause instanceof LabMessageError) return l(cause.key);
  if (cause instanceof accountApi.ApiError && Array.isArray(cause.detail)) return cause.detail.map(d=>d.message ?? d.msg ?? JSON.stringify(d)).join(' · ');
  return cause instanceof Error ? cause.message : l('page.readFailed');
}
function download(name: string, data: unknown) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
  const link=document.createElement('a'); link.href=url; link.download=name; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export default function DamageLabPage({ projectId, onBack, onProject }: {
  projectId: string; onBack: () => void; onProject: (id: string) => void;
}) {
  const [view,setView]=useState<ProjectView|null>(null), [setup,setSetup]=useState<Setup|null>(null);
  // The laboratory reads the shell's one language state. A switch changes the
  // words in place: the draft, the selected module, the replay frame, the camera
  // and any running trial all live in the state below and none is touched by it.
  const l=useLabCopy(),f=useLabFormat(),{language}=useLanguage();
  const [draft,setDraft]=useState<Experiment|null>(null), [condition,setCondition]=useState('');
  const [preset,setPreset]=useState<PresetProblem|null>(null), [assumptions,setAssumptions]=useState<PresetAssumption[]>([]);
  // The comparison reads its own two records and holds them separately: it never
  // becomes the active run and never touches the draft, the replay or the camera.
  const [compareRuns,setCompareRuns]=useState<{a:LabRun|null;b:LabRun|null}>({a:null,b:null});
  const [compareLoading,setCompareLoading]=useState<{a:boolean;b:boolean}>({a:false,b:false});
  const compareRead=useRef<{a:AbortController|null;b:AbortController|null}>({a:null,b:null});
  // A new project means different records: drop the pair rather than compare
  // across projects.
  useEffect(()=>{setCompareRuns({a:null,b:null});setCompareLoading({a:false,b:false});compareRead.current.a?.abort();compareRead.current.b?.abort();},[projectId]);
  useEffect(()=>()=>{compareRead.current.a?.abort();compareRead.current.b?.abort();},[]);
  const [run,setRun]=useState<LabRun|null>(null), [history,setHistory]=useState<LabRun[]>([]);
  const [loading,setLoading]=useState(projectId!=='demo'), [busy,setBusy]=useState(false), [error,setError]=useLabMessage();
  const [attempt,setAttempt]=useState(0), [selected,setSelected]=useState(''), [target,setTarget]=useState('');
  const [inspection,setInspection]=useState<InspectionTarget|null>(null);
  const [frame,setFrame]=useState(0), [playing,setPlaying]=useState(false), [speed,setSpeed]=useState(1);
  const [trace,setTrace]=useState<number|null>(null);
  const [json,setJson]=useState(''), [pollAttempt,setPollAttempt]=useState(0);
  const manualJson=useRef(false);
  const alive=useRef(true), busyNow=useRef(false), operation=useRef(0), draftTicket=useRef(0);
  const result=view ? visibleResult(run,view.project_id,view.revision,condition,draft) : null;
  const state=frameAt(result,frame);
  const snapshotProject=result?.input_snapshot ?? view?.project;
  const rooms=(snapshotProject?.compartments ?? []) as Room[];
  // Re-derived when the language changes; the frames, their order and the frozen
  // numbers behind them are identical either way.
  const entries=useMemo(()=>replayEntries(result,language),[result,language]);
  const baseline=useMemo(()=>comparisonBaseline(result),[result]);
  const currentEntry=entries[frame];
  function inspect(next:InspectionTarget){
    setInspection(next);
    const module=next.kind==='module' ? next.id : next.kind==='crew'
      ? draft?.crew_groups.find(c=>c.id===next.id)?.module_id
      : draft?.modules.find(m=>m.compartment_id===next.id)?.id;
    setSelected(module ?? '');
  }
  useEffect(()=>{if(currentEntry?.targets[0])inspect(currentEntry.targets[0]);},[frame,result?.request_fingerprint]);

  useEffect(()=>{ alive.current=true; return ()=>{alive.current=false;operation.current++;}; },[]);
  useEffect(()=>{
    const controller=new AbortController(); const token=++operation.current;
    manualJson.current=false;setError(''); setRun(null); setPlaying(false); setView(null); setDraft(null); setSetup(null); setHistory([]);
    if(projectId==='demo') { setLoading(false); return ()=>controller.abort(); }
    setLoading(true);
    Promise.all([api.readProject(projectId,controller.signal),api.readSetup(projectId,controller.signal),api.listRuns(projectId,controller.signal)])
      .then(async ([project,prepared,jobs])=>{
        if(controller.signal.aborted || token!==operation.current) return;
        if(project.revision!==prepared.revision) throw new LabMessageError('error.revisionChanged');
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
      }).catch(cause=>{if(!controller.signal.aborted && token===operation.current)setError(l => message(cause,l));})
      .finally(()=>{if(!controller.signal.aborted && token===operation.current)setLoading(false);});
    return ()=>controller.abort();
  },[projectId,attempt]);

  useEffect(()=>{setPlaying(false);setFrame(0);setTrace(null);setInspection(null);if(!manualJson.current)setJson(draft ? JSON.stringify(draft,null,2) : '');},[draft,condition,run?.id]);
  useEffect(()=>{
    if(!run || !active(run))return;
    const controller=new AbortController();let timer: ReturnType<typeof setTimeout>;
    const id=run.id,fingerprint=run.request_fingerprint;
    async function poll(){
      try {
        const next=await api.readRun(id,controller.signal);
        if(controller.signal.aborted)return;
        if(next.request_fingerprint!==fingerprint || next.project_id!==projectId)throw new LabMessageError('error.identityMismatch');
        setRun(previous=>previous?.id===id ? next : previous);
        setHistory(previous=>[next,...previous.filter(job=>job.id!==id)].slice(0,50));
        if(active(next))timer=setTimeout(poll,900);
      }catch(cause){if(!controller.signal.aborted)setError(l => l('error.readInterrupted',{reason:message(cause,l)}));}
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
    if(!draft)return;draftTicket.current++;manualJson.current=false;const next=clone(draft);change(next);setDraft(next);setError('');
  }
  /**
   * Prepare one synthetic preset.
   *
   * This prepares a draft and states its assumptions; it runs nothing. The reader
   * still has to accept the draft through the form's own submit, which is the only
   * path that enqueues, so choosing a preset can never start a calculation. A
   * vessel the preset cannot describe gets the reason instead of a guessed draft.
   */
  async function applyPreset(name:PresetName){
    if(!view || !draft || busyNow.current || active(run))return;
    busyNow.current=true;setBusy(true);setError('');
    const token=operation.current,ticket=++draftTicket.current;
    try {
      const demo=await api.readDemo();
      if(!alive.current || token!==operation.current || ticket!==draftTicket.current)return;
      const shape=(project:ProjectDocument)=>JSON.stringify((project.compartments as unknown as Room[] ?? [])
        .map(room=>[room.id,room.x_m,room.y_m,room.keel_to_bottom_m,room.length_m,room.beam_m,room.height_m,room.permeability]).sort());
      if(shape(view.project)!==shape(demo.project)){setPreset('unsupported');setAssumptions([]);return;}
      const built=buildPreset(view.project,demo.experiment,name);
      if('problem' in built){setPreset(built.problem);setAssumptions([]);return;}
      const checked=await api.preview(view.project_id,view.revision,condition,built.experiment);
      if(!alive.current || token!==operation.current || ticket!==draftTicket.current)return;
      manualJson.current=false;setPreset(null);setAssumptions(built.assumptions);setDraft(checked.experiment);setError('');
    }catch(cause){if(alive.current && token===operation.current && ticket===draftTicket.current)setError(copy=>message(cause,copy));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  function selectCompare(side:'a'|'b',id:string){
    compareRead.current[side]?.abort();
    setCompareRuns(previous=>({...previous,[side]:null}));
    setCompareLoading(previous=>({...previous,[side]:Boolean(id)}));
    if(!id)return;
    const controller=new AbortController();compareRead.current[side]=controller;
    void api.readRun(id,controller.signal).then(next=>{
      if(controller.signal.aborted)return;
      if(next.id!==id || next.project_id!==view?.project_id || !validTrialIdentity(next)){setError(copy=>copy('error.identityMismatch'));return;}
      setCompareRuns(previous=>({...previous,[side]:next}));
    }).catch(cause=>{if(!controller.signal.aborted)setError(copy=>message(cause,copy));})
      .finally(()=>{if(!controller.signal.aborted)setCompareLoading(previous=>({...previous,[side]:false}));});
  }
  async function start(){
    if(!view || !draft || busyNow.current || active(run))return;
    busyNow.current=true;setBusy(true);setError('');setRun(null);setPlaying(false);
    const token=operation.current;
    try {const next=await api.enqueue(view.project_id,view.revision,condition,clone(draft));
      if(!alive.current || token!==operation.current)return;
      setRun(next);setHistory(previous=>[next,...previous]);
      try{sessionStorage.setItem('plimsoll:lab-draft:'+view.project_id,JSON.stringify({revision:view.revision,experiment:next.request.experiment}));}catch{/* Draft storage is optional. */}
    }catch(cause){if(alive.current && token===operation.current)setError(l => message(cause,l));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function cancel(){
    if(!run || busyNow.current)return;busyNow.current=true;setBusy(true);setError('');
    const id=run.id,token=operation.current;
    try {const next=await api.cancel(id);if(alive.current && token===operation.current){setRun(previous=>previous?.id===id ? next : previous);setHistory(previous=>[next,...previous.filter(job=>job.id!==id)]);setPollAttempt(v=>v+1);}}
    catch(cause){if(alive.current && token===operation.current)setError(l => message(cause,l));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function createDemo(){
    if(busyNow.current)return;busyNow.current=true;setBusy(true);setError('');const token=operation.current;
    try {const demo=await api.readDemo();if(!alive.current || token!==operation.current)return;
      const saved=await accountApi.importProject(demo.project);
      if(!alive.current || token!==operation.current)return;
      try {sessionStorage.setItem('plimsoll:lab-draft:'+saved.project_id,JSON.stringify({revision:saved.revision,experiment:demo.experiment}));}catch{/* optional */}
      onProject(saved.project_id);
    }catch(cause){if(alive.current && token===operation.current)setError(l => message(cause,l));}
    finally{if(alive.current && token===operation.current){busyNow.current=false;setBusy(false);}}
  }
  async function restore(job:LabRun){
    if(busyNow.current || active(run))return;busyNow.current=true;setBusy(true);setError('');const token=operation.current,ticket=++draftTicket.current;
    try{const saved=await api.readRun(job.id);if(!alive.current || token!==operation.current || ticket!==draftTicket.current)return;
      if(saved.id!==job.id || saved.project_id!==view?.project_id){throw new LabMessageError('error.identityMismatch');}
      if(saved.revision!==view.revision){throw new LabMessageError('error.restoreRevision');}
      if(saved.result && !validTrialIdentity(saved)){throw new LabMessageError('error.identityMismatch');}
      if(!view.project.loading_conditions.some(c=>c.id===saved.condition_id)){throw new LabMessageError('error.identityMismatch');}
      manualJson.current=false;setDraft(clone(saved.request.experiment));setCondition(saved.condition_id);setRun(saved);
      setSelected(saved.request.experiment.modules[0]?.id ?? '');setTarget(saved.request.experiment.modules[0]?.id ?? '');
    }catch(cause){if(alive.current && token===operation.current && ticket===draftTicket.current)setError(l => message(cause,l));}
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
    }catch(cause){if(alive.current && token===operation.current && ticket===draftTicket.current)setError(l => message(cause,l));}
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
    <header className="lab-head"><div><span className="lab-kicker">{l('page.kicker')}</span><h1>{l('page.title')}<span className="lab-red-dot" aria-hidden="true">.</span></h1></div>
      <button className="lab-link" onClick={onBack}>{l('page.back')}</button></header>
    {error && <div role="alert" className="lab-error">{error}<button onClick={()=>{setAttempt(v=>v+1);setPollAttempt(v=>v+1);}} disabled={busy}>{l('page.readAgain')}</button></div>}
    {loading ? <p role="status">{l('page.loading')}</p> : !view || !draft ? <section className="lab-welcome">
      <span className="lab-kicker">{l('welcome.kicker')}</span><h2>{view ? l('welcome.title.ready') : l('welcome.title')}</h2>
      {setup?.diagnostics.map((d,i)=><p key={i}>{d.message}</p>)}
      <p>{l('welcome.body')}</p>
      <button className="lab-primary" onClick={createDemo} disabled={busy}>{busy ? l('welcome.creating') : l('welcome.create')}</button>
      <p className="lab-note">{l('welcome.note')}</p>
    </section> : <>
      <div className="lab-identity"><strong>{view.project.name}</strong><span>{l('identity.revision',{revision:view.revision,condition})}</span><span className="lab-note">{l('identity.note')}</span></div>
      <div className="lab-grid">
        <form className="lab-setup" onSubmit={e=>{e.preventDefault();void start();}}>
          <span className="lab-kicker">{l('setup.kicker')}</span><h2>{l('setup.title')}</h2>
          <label>{l('setup.condition')}<select value={condition} onChange={e=>{draftTicket.current++;setCondition(e.target.value);}}>{view.project.loading_conditions.map(c=><option key={c.id} value={c.id}>{c.label || c.id}</option>)}</select></label>
          <DetonationControls draft={draft} rooms={rooms} edit={edit} />
          <fieldset className="lab-boundary"><legend>{l('preset.legend')}</legend>
            <div className="lab-pair">{PRESET_NAMES.map(name=><button type="button" key={name} onClick={()=>void applyPreset(name)} disabled={busy || active(run)}>{l(`preset.${name}` as LabKey)}</button>)}</div>
            {preset && <p role="status" className="lab-note">{l(`preset.problem.${preset}` as LabKey)}</p>}
            {assumptions.map(entry=><p className="lab-note" key={entry.key}>{l(entry.key as LabKey,entry.params)}</p>)}
          </fieldset>
          <label>{draft.detonation ? l('setup.moveDetonation') : l('setup.hitTarget')}<select value={target} onChange={e=>{setTarget(e.target.value);edit(next=>{const m=next.modules.find(v=>v.id===e.target.value);if(m){next.impact.position_m=clone(m.box.center_m);if(next.detonation)next.detonation.position_m=clone(m.box.center_m);}});}}>{draft.modules.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></label>
          <div className="lab-coordinates">{(['X','Y','Z'] as const).map((axis,i)=><label key={axis}>{axis} / m<input aria-label={l('setup.axis',{kind:draft.detonation ? l('setup.detonationAxis') : l('setup.hitAxis')}) + ' ' + axis} type="number" step=".1" value={(draft.detonation?.position_m ?? draft.impact.position_m)[i]} onChange={e=>{if(e.target.value!=='')edit(next=>{(next.detonation?.position_m ?? next.impact.position_m)[i]=Number(e.target.value);});}} /></label>)}</div>
          <label>{l('setup.severity')} <span>{f.numeric(draft.impact.severity,2)}</span><input aria-label={l('setup.severity')} type="range" min="0" max="1" step=".05" value={draft.impact.severity} onChange={e=>edit(next=>{next.impact.severity=Number(e.target.value);})} /></label>
          <label>{draft.detonation ? l('setup.radiusDetonation') : l('setup.radius')}<input type="number" min="0" max="1000" step=".1" value={draft.impact.radius_m} onChange={e=>edit(next=>{next.impact.radius_m=Number(e.target.value);})} /></label>
          <div className="lab-pair"><label>{l('setup.duration')}<input type="number" min="0" max="60" step="any" value={draft.duration_s} onChange={e=>edit(next=>{next.duration_s=Number(e.target.value);})} /></label><label>{l('setup.step')}<input type="number" min=".000001" max="60" step="any" value={draft.time_step_s} onChange={e=>edit(next=>{next.time_step_s=Number(e.target.value);})} /></label></div>
          <label className="lab-check"><input type="checkbox" checked={draft.breaches.length>0} onChange={e=>breach(e.target.checked)} />{l('setup.breach')}</label>
          {draft.breaches[0] && <label>{l('setup.breachArea')}<input type="number" min="0" step=".1" value={draft.breaches[0].area_m2} onChange={e=>edit(next=>{next.breaches[0].area_m2=Number(e.target.value);})} /></label>}
          {draft.breaches.map(b=><p className="lab-note" key={b.id}>{b.from_id} → {b.to_id} / {b.area_m2} m² / Cd {b.discharge_coefficient}</p>)}
          <p className="lab-note">{draft.detonation ? l('setup.breachNote.detonation') : l('setup.breachNote.plain')}</p>
          <button className="lab-primary" disabled={busy || active(run) || !condition}>{busy ? l('setup.submitting') : l('setup.submit')}</button>
          {active(run) && <button type="button" onClick={()=>void cancel()} disabled={busy || run?.cancel_requested}>{run?.cancel_requested ? l('setup.cancelling') : l('setup.cancel')}</button>}
          <details><summary>{l('setup.crewSummary')}</summary>
            {draft.crew_groups.map((group,i)=><label key={group.id}>{l('setup.crewUnit',{label:group.label})}<input type="number" min="0" max="100000" value={group.personnel ?? ''} placeholder={l('value.unknown')} onChange={e=>edit(next=>{next.crew_groups[i].personnel=e.target.value==='' ? null : Number(e.target.value);})} /></label>)}
            <p className="lab-note">{l('setup.crewNote')}</p>
          </details>
        </form>
        <div className="lab-middle">
          <div className="lab-scene-head"><span className="lab-kicker">{l('inspector.kicker')}</span><span>{run ? f.status(run.status) : l('inspector.pending')}</span></div>
          <Suspense fallback={<div className="lab-scene-loading" role="status">{l('inspector.loading')}</div>}><Scene project={snapshotProject!} experiment={draft} state={state} selected={selected} inspection={inspection} eventTargets={currentEntry?.targets} fragments={result?.fragmentation ?? null} selectedTrace={trace} onSelect={id=>inspect({kind:'module',id})} /></Suspense>
          {run?.error && <p role="alert" className="lab-error">{run.error.message}</p>}
          {mismatch && <p className="lab-note lab-mismatch">{l('inspector.mismatch')}{run?.revision!==view.revision ? l('inspector.mismatchRevision') : l('inspector.mismatchDraft')}</p>}
          <ShipMetrics state={state} baseline={baseline.ship} />
          {result?.fragmentation && <FragmentEvidence report={result.fragmentation} state={state} experiment={draft} selected={trace} onTrace={setTrace} onInspect={inspect} />}
          {result && <Replay entries={entries} frame={frame} playing={playing} speed={speed} onFrame={setFrame} onPlaying={setPlaying} onSpeed={setSpeed} onInspect={inspect} />}
        </div>
        <Inspector experiment={draft} state={state} baseline={baseline.initial} rooms={rooms} selected={selected} inspection={inspection} result={result} frame={frame} onSelect={id=>inspect({kind:'module',id})} onInspect={inspect} />
      </div>
      {result && <CoreEvidence result={result} />}
      <section className="lab-records"><div><span className="lab-kicker">{l('records.kicker')}</span><h2>{l('records.title')}</h2><p className="lab-note">{l('records.note')}</p>
        <button onClick={()=>download('damage-lab.experiment.json',draft)}>{l('records.download')}</button>
        <details><summary>{l('records.editSummary')}</summary><label>{l('records.chooseFile')}<input type="file" accept="application/json,.json" onChange={e=>{const file=e.target.files?.[0];if(!file)return;const token=operation.current,ticket=++draftTicket.current;if(file.size>1024*1024){setError(l => l('records.fileTooLarge'));return;}manualJson.current=true;void file.text().then(text=>{if(alive.current && token===operation.current && ticket===draftTicket.current)setJson(text);}).catch(cause=>{if(alive.current && token===operation.current && ticket===draftTicket.current)setError(l => message(cause,l));});}} /></label><textarea aria-label={l('records.jsonLabel')} spellCheck={false} value={json} onChange={e=>{draftTicket.current++;manualJson.current=true;setJson(e.target.value);}} /><button disabled={busy} onClick={()=>void applyJson()}>{l('records.apply')}</button></details>
      </div><div><span className="lab-kicker">{l('records.historyKicker')}</span><h2>{l('records.historyTitle')}</h2>
        {history.length ? history.map(job=><div className="lab-record" key={job.id}><button disabled={busy || active(run)} onClick={()=>void restore(job)}>{job.id.slice(0,8)} · R{job.revision} · {f.status(job.status)}</button>{(job.has_result || job.result) && <span><a href={api.exportUrl(job.id,'json')} download={`damage-lab-${job.id}.json`}>JSON ↗</a><a href={api.exportUrl(job.id,'csv')} download={`damage-lab-${job.id}.csv`}>CSV ↗</a></span>}</div>) : <p className="lab-note">{l('records.historyEmpty')}</p>}
        {run && <p className="lab-fingerprint">REQUEST / {run.request_fingerprint}</p>}
      </div></section>
      <ComparisonPanel records={history.filter(job=>job.has_result || job.result || job.status==='completed')}
        a={compareRuns.a} b={compareRuns.b} currentRevision={view.revision} loading={compareLoading.a && compareLoading.b ? 'both' : compareLoading.a ? 'a' : compareLoading.b ? 'b' : null} viewDisabled={busy || active(run)}
        onSelect={selectCompare} onView={job=>void restore(job)} />
    </>}
  </main>;
}

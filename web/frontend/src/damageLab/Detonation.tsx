import { useState } from 'react';
import type { Boundary, Experiment, Fragmentation, LabState, Room, Vec3 } from './types';
import type { InspectionTarget } from './narrative';
import { useLabCopy, type LabKey } from '../i18n/lab';
import { useLabFormat } from '../i18n/labFormat';

/**
 * What this boundary response is, stated once and stored in the experiment.
 *
 * It is a declaration the reader makes, not a surveyed armour or explosive
 * property, and it is written into the document as English because it is project
 * data rather than interface copy — exactly like a source string or an id. It
 * travels with the saved experiment in both languages.
 */
export const META = {source:'User-declared normalized game boundary response; not surveyed armor or explosive calibration',estimate:true};
export const bounds = (r:Room) => ({c:[r.x_m,r.y_m,r.keel_to_bottom_m+r.height_m/2],s:[r.length_m,r.beam_m,r.height_m]});

/** Candidates are rectangular hydraulic proxies; sea remains an explicit user choice. */
export function boundaryCandidates(rooms:Room[]):Boundary[] {
  const candidates:Boundary[]=[];
  rooms.forEach((room,i)=>{
    const a=bounds(room);
    for(let axis=0;axis<3;axis++)for(const sign of [-1,1]){
      const face=a.c[axis]+sign*a.s[axis]/2;
      const adjacent=rooms.filter(other=>{
        if(other.id===room.id)return false;
        const b=bounds(other);
        return Math.abs(face-(b.c[axis]-sign*b.s[axis]/2))<1e-6 && a.s.every((_,j)=>j===axis ||
          Math.min(a.c[j]+a.s[j]/2,b.c[j]+b.s[j]/2)-Math.max(a.c[j]-a.s[j]/2,b.c[j]-b.s[j]/2)>1e-6);
      });
      for(const other of adjacent){
        if(rooms.indexOf(other)<=i)continue;
        const b=bounds(other),position=a.c.map((_,j)=>j===axis ? face :
          (Math.min(a.c[j]+a.s[j]/2,b.c[j]+b.s[j]/2)+Math.max(a.c[j]-a.s[j]/2,b.c[j]-b.s[j]/2))/2) as Vec3;
        candidates.push({id:`wall:${room.id}:${other.id}`,from_id:room.id,to_id:other.id,position_m:position,
          transmission:0,breach_threshold:1,max_breach_area_m2:0,discharge_coefficient:.6,...META});
      }
      if(!adjacent.length){
        const position=[...a.c] as Vec3;position[axis]=face;
        candidates.push({id:`face:${room.id}:${axis}:${sign}`,from_id:room.id,to_id:'sea',position_m:position,
          transmission:0,breach_threshold:.02,max_breach_area_m2:Math.min(.5,a.s.reduce((area,s,j)=>j===axis ? area : area*s,1)),discharge_coefficient:.6,...META});
      }
    }
  });
  return candidates.sort((a,b)=>Number(a.to_id==='sea')-Number(b.to_id==='sea'));
}

export function DetonationControls({draft,rooms,edit}:{draft:Experiment;rooms:Room[];edit:(fn:(next:Experiment)=>void)=>void}) {
  const l=useLabCopy(),f=useLabFormat();
  const candidates=boundaryCandidates(rooms),[choice,setChoice]=useState('');
  const available=candidates.filter(c=>!draft.detonation?.boundaries.some(b=>b.id===c.id));
  const selected=available.find(c=>c.id===choice) ?? available[0];
  const label=(b:Boundary)=>{
    const room=rooms.find(r=>r.id===b.from_id),center=room ? bounds(room).c : b.position_m;
    const axis=b.position_m.findIndex((p,j)=>Math.abs(p-center[j])>1e-6);
    return `${room?.label ?? b.from_id} → ${b.to_id==='sea' ? l('detonation.sea') : rooms.find(r=>r.id===b.to_id)?.label ?? b.to_id}${b.to_id==='sea'&&axis>=0 ? ` · ${['X','Y','Z'][axis]} ${f.numeric(b.position_m[axis],2)} m` : ''}`;
  };
  return <section className="lab-detonation-controls">
    <label className="lab-check"><input type="checkbox" checked={!!draft.detonation} onChange={e=>edit(next=>{
      if(e.target.checked)next.detonation={position_m:[...next.impact.position_m],fragment_count:128,seed:42,boundaries:[],...META};
      else delete next.detonation;
    })} />{l('detonation.checkbox')}</label>
    {draft.detonation && <>
      <p className="lab-note">{l('detonation.note')}</p>
      <div className="lab-pair"><label>{l('detonation.fragments')}<input type="number" min="32" max="512" step="1" value={draft.detonation.fragment_count} onChange={e=>edit(n=>{n.detonation!.fragment_count=Number(e.target.value);})} /></label>
        <label>{l('detonation.seed')}<input type="number" min="0" max="4294967295" step="1" value={draft.detonation.seed} onChange={e=>edit(n=>{n.detonation!.seed=Number(e.target.value);})} /></label></div>
      <details><summary>{l('detonation.wallSummary')}</summary>
        <p className="lab-note">{l('detonation.wallNote')}</p>
        {available.length>0 && <><label>{l('detonation.addLabel')}<select value={selected?.id ?? ''} onChange={e=>setChoice(e.target.value)}>{available.map(c=><option key={c.id} value={c.id}>{label(c)}</option>)}</select></label>
          <button type="button" onClick={()=>{if(selected)edit(n=>{n.detonation!.boundaries.push({...selected,position_m:[...selected.position_m]});});}}>{l('detonation.add')}</button></>}
        {draft.detonation.boundaries.map((wall,i)=><fieldset className="lab-boundary" key={wall.id}><legend>{label(wall)}</legend>
          <label>{l('detonation.transmission')}<input type="number" min="0" max="1" step=".05" value={wall.transmission} onChange={e=>edit(n=>{n.detonation!.boundaries[i].transmission=Number(e.target.value);})} /></label>
          <div className="lab-pair"><label>{l('detonation.threshold')}<input type="number" min="0" max="1" step=".01" value={wall.breach_threshold} onChange={e=>edit(n=>{n.detonation!.boundaries[i].breach_threshold=Number(e.target.value);})} /></label>
            <label>{l('detonation.maxArea')}<input type="number" min="0" max="1000" step=".1" value={wall.max_breach_area_m2} onChange={e=>edit(n=>{n.detonation!.boundaries[i].max_breach_area_m2=Number(e.target.value);})} /></label></div>
          <p className="lab-note">{l('detonation.position',{point:wall.position_m.map(v=>f.numeric(v,2)).join(' / ')})}</p>
          <button type="button" onClick={()=>edit(n=>{n.detonation!.boundaries.splice(i,1);})}>{l('detonation.remove')}</button>
        </fieldset>)}
      </details>
    </>}
  </section>;
}

/** A known termination gets a name; an unknown one stays the core's own token. */
function terminationLabel(l:(key:LabKey)=>string, token:string):string {
  return l(`detonation.end.${token}` as LabKey);
}

export function FragmentEvidence({report,state,experiment,selected,onTrace,onInspect}:{
  report:Fragmentation;state:LabState|null;experiment:Experiment;selected:number|null;
  onTrace:(index:number|null)=>void;onInspect:(target:InspectionTarget)=>void;
}) {
  const l=useLabCopy(),f=useLabFormat();
  const trace=selected==null ? null : report.traces.find(t=>t.index===selected);
  return <section className="lab-fragment-evidence" aria-label={l('fragments.label')}><span className="lab-kicker">{l('fragments.kicker')}</span><h2>{l('fragments.title')}</h2>
    {!state?.detonation_occurred ? <p className="lab-note">{l('fragments.pre')}</p> : <>
      <p>{report.compartment_id} · {report.position_m.map(v=>f.numeric(v,2)).join(' / ')} m</p>
      <p className="lab-note">{l('fragments.summary',{seed:report.seed,count:report.traces.length,blocked:report.traces.filter(t=>t.termination==='sealed_boundary').length})}</p>
      <div className="lab-trace-controls"><label>{l('fragments.inspectPath')}<input aria-label={l('fragments.pathAria')} type="number" min="0" max={Math.max(0,report.traces.length-1)} placeholder={l('fragments.overview')} value={selected ?? ''} onChange={e=>onTrace(e.target.value==='' || !report.traces.length ? null : Math.max(0,Math.min(report.traces.length-1,Math.floor(Number(e.target.value)))))} /></label><button type="button" onClick={()=>onTrace(null)}>{l('fragments.overview')}</button></div>
      {trace && <div className="lab-trace-detail"><strong>{l('fragments.pathTitle',{index:String(trace.index).padStart(3,'0'),termination:terminationLabel(l,trace.termination)})}</strong>
        <p className="lab-note">{trace.segments.map(s=>`${s.compartment_id} (${f.percent(s.transmission)})`).join(' → ')}{trace.blocked_by ? ` · ${trace.blocked_by.startsWith('undeclared:') ? l('fragments.defaultWall') : trace.blocked_by}` : ''}</p>
        {trace.segments.at(-1)?.to_m&&<p className="lab-note">{l('fragments.endpoint',{point:trace.segments.at(-1)!.to_m.map(v=>f.numeric(v,2)).join(' / ')})}</p>}
        {trace.hits.length ? trace.hits.map((hit,i)=><button type="button" key={i} onClick={()=>onInspect({kind:hit.kind,id:hit.id})}>{(hit.kind==='module' ? experiment.modules : experiment.crew_groups).find(t=>t.id===hit.id)?.label ?? hit.id} · {l('fragments.contribution',{value:f.numeric(hit.exposure,5)})} ↗</button>) : <p className="lab-note">{l('fragments.noHit')}</p>}
      </div>}
      <span className="lab-kicker">{l('fragments.exposureKicker')}</span>
      {Object.entries(report.module_exposure).map(([id,value])=><div className="lab-fragment-target" key={id}><span>{experiment.modules.find(m=>m.id===id)?.label ?? id}</span><strong>{l('fragments.exposure',{value:f.percent(value)})}</strong><button type="button" disabled={value===0} onClick={()=>{onTrace(report.traces.find(t=>t.hits.some(h=>h.kind==='module'&&h.id===id))?.index ?? null);onInspect({kind:'module',id});}}>{l('fragments.inspect')}</button></div>)}
      <details><summary>{l('fragments.boundariesSummary')}</summary>{report.boundaries.length ? report.boundaries.map(w=><p className="lab-note" key={w.id}>{w.id} · {l('fragments.absorbed',{absorbed:f.numeric(w.absorbed_exposure,4),threshold:f.numeric(w.breach_threshold,4)})} · {w.generated_area_m2===0 ? l('fragments.noBreach') : state.generated_breaches?.some(b=>b.id==='fragment:'+w.id) ? l('fragments.breachGenerated',{area:f.numeric(w.generated_area_m2,4)}) : l('fragments.breachLater')}</p>) : <p className="lab-note">{l('fragments.allClosed')}</p>}</details>
      <p className="lab-note">{l('fragments.footnote')}</p>
    </>}
  </section>;
}

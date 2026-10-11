import { useState } from 'react';
import type { Boundary, Experiment, Fragmentation, LabState, Room, Vec3 } from './types';
import type { InspectionTarget } from './narrative';
import { numeric, percent } from './model';

const META = {source:'User-declared normalized game boundary response; not surveyed armor or explosive calibration',estimate:true};
const bounds = (r:Room) => ({c:[r.x_m,r.y_m,r.keel_to_bottom_m+r.height_m/2],s:[r.length_m,r.beam_m,r.height_m]});

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
  const candidates=boundaryCandidates(rooms),[choice,setChoice]=useState('');
  const available=candidates.filter(c=>!draft.detonation?.boundaries.some(b=>b.id===c.id));
  const selected=available.find(c=>c.id===choice) ?? available[0];
  const label=(b:Boundary)=>{
    const room=rooms.find(r=>r.id===b.from_id),center=room ? bounds(room).c : b.position_m;
    const axis=b.position_m.findIndex((p,j)=>Math.abs(p-center[j])>1e-6);
    return `${room?.label ?? b.from_id} → ${b.to_id==='sea' ? 'Sea proxy / 外部海水界面' : rooms.find(r=>r.id===b.to_id)?.label ?? b.to_id}${b.to_id==='sea'&&axis>=0 ? ` · ${['X','Y','Z'][axis]} ${numeric(b.position_m[axis],2)} m` : ''}`;
  };
  return <section className="lab-detonation-controls">
    <label className="lab-check"><input type="checkbox" checked={!!draft.detonation} onChange={e=>edit(next=>{
      if(e.target.checked)next.detonation={position_m:[...next.impact.position_m],fragment_count:128,seed:42,boundaries:[],...META};
      else delete next.detonation;
    })} />起爆与破片路径模型</label>
    {draft.detonation && <>
      <p className="lab-note">位置是已知起爆点，不求解引信。全部舱壁默认阻挡；界面参数是游戏估算。</p>
      <div className="lab-pair"><label>代表性破片 / 条<input type="number" min="32" max="512" step="1" value={draft.detonation.fragment_count} onChange={e=>edit(n=>{n.detonation!.fragment_count=Number(e.target.value);})} /></label>
        <label>随机种子<input type="number" min="0" max="4294967295" step="1" value={draft.detonation.seed} onChange={e=>edit(n=>{n.detonation!.seed=Number(e.target.value);})} /></label></div>
      <details><summary>舱壁响应 / 自动破口</summary>
        <p className="lab-note">未配置的边界完全遮挡且不生成破口。添加海水界面意味着明确声明这个舱室外表面与海水相连。</p>
        {available.length>0 && <><label>添加界面<select value={selected?.id ?? ''} onChange={e=>setChoice(e.target.value)}>{available.map(c=><option key={c.id} value={c.id}>{label(c)}</option>)}</select></label>
          <button type="button" onClick={()=>{if(selected)edit(n=>{n.detonation!.boundaries.push({...selected,position_m:[...selected.position_m]});});}}>添加所选界面</button></>}
        {draft.detonation.boundaries.map((wall,i)=><fieldset className="lab-boundary" key={wall.id}><legend>{label(wall)}</legend>
          <label>破片透过比例<input type="number" min="0" max="1" step=".05" value={wall.transmission} onChange={e=>edit(n=>{n.detonation!.boundaries[i].transmission=Number(e.target.value);})} /></label>
          <div className="lab-pair"><label>开孔阈值 / 0–1<input type="number" min="0" max="1" step=".01" value={wall.breach_threshold} onChange={e=>edit(n=>{n.detonation!.boundaries[i].breach_threshold=Number(e.target.value);})} /></label>
            <label>最大开孔 / m²<input type="number" min="0" max="1000" step=".1" value={wall.max_breach_area_m2} onChange={e=>edit(n=>{n.detonation!.boundaries[i].max_breach_area_m2=Number(e.target.value);})} /></label></div>
          <p className="lab-note">水力接口位于 {wall.position_m.map(v=>numeric(v,2)).join(' / ')} m。完整位置和 Cd 可在 JSON 中修改。</p>
          <button type="button" onClick={()=>edit(n=>{n.detonation!.boundaries.splice(i,1);})}>移除此响应</button>
        </fieldset>)}
      </details>
    </>}
  </section>;
}

const END:Record<string,string>={sealed_boundary:'舱壁阻挡',range:'达到路径范围',declared_sea_exit:'离开声明的海水界面'};
export function FragmentEvidence({report,state,experiment,selected,onTrace,onInspect}:{
  report:Fragmentation;state:LabState|null;experiment:Experiment;selected:number|null;
  onTrace:(index:number|null)=>void;onInspect:(target:InspectionTarget)=>void;
}) {
  const trace=selected==null ? null : report.traces.find(t=>t.index===selected);
  return <section className="lab-fragment-evidence" aria-label="起爆与破片依据"><span className="lab-kicker">DETONATION / REPRESENTATIVE RAYS</span><h2>起爆与遮挡</h2>
    {!state?.detonation_occurred ? <p className="lab-note">当前是起爆前状态，路径和生成破口尚未发生。</p> : <>
      <p>{report.compartment_id} · {report.position_m.map(v=>numeric(v,2)).join(' / ')} m</p>
      <p className="lab-note">种子 {report.seed} · {report.traces.length} 条代表性路径 · {report.traces.filter(t=>t.termination==='sealed_boundary').length} 条被舱壁阻挡。颜色与线条用于解释，不代表实际碎片数量。</p>
      <div className="lab-trace-controls"><label>检查路径<input aria-label="检查破片路径" type="number" min="0" max={Math.max(0,report.traces.length-1)} placeholder="全部概览" value={selected ?? ''} onChange={e=>onTrace(e.target.value==='' || !report.traces.length ? null : Math.max(0,Math.min(report.traces.length-1,Math.floor(Number(e.target.value)))))} /></label><button type="button" onClick={()=>onTrace(null)}>全部概览</button></div>
      {trace && <div className="lab-trace-detail"><strong>PATH {String(trace.index).padStart(3,'0')} / {END[trace.termination] ?? trace.termination}</strong>
        <p className="lab-note">{trace.segments.map(s=>`${s.compartment_id} (${percent(s.transmission)})`).join(' → ')}{trace.blocked_by ? ` · ${trace.blocked_by.startsWith('undeclared:') ? '默认封闭舱壁' : trace.blocked_by}` : ''}</p>
        {trace.segments.at(-1)?.to_m&&<p className="lab-note">终点 {trace.segments.at(-1)!.to_m.map(v=>numeric(v,2)).join(' / ')} m</p>}
        {trace.hits.length ? trace.hits.map((hit,i)=><button type="button" key={i} onClick={()=>onInspect({kind:hit.kind,id:hit.id})}>{(hit.kind==='module' ? experiment.modules : experiment.crew_groups).find(t=>t.id===hit.id)?.label ?? hit.id} · 贡献 {numeric(hit.exposure,5)} ↗</button>) : <p className="lab-note">这条路径未交到已声明的模块或岗位。</p>}
      </div>}
      <span className="lab-kicker">MODULE EXPOSURE / GAME ESTIMATE</span>
      {Object.entries(report.module_exposure).map(([id,value])=><div className="lab-fragment-target" key={id}><span>{experiment.modules.find(m=>m.id===id)?.label ?? id}</span><strong>暴露 {numeric(value*100,2)}%</strong><button type="button" disabled={value===0} onClick={()=>{onTrace(report.traces.find(t=>t.hits.some(h=>h.kind==='module'&&h.id===id))?.index ?? null);onInspect({kind:'module',id});}}>检查路径 ↗</button></div>)}
      <details><summary>边界负荷与生成破口</summary>{report.boundaries.length ? report.boundaries.map(w=><p className="lab-note" key={w.id}>{w.id} · 吸收 {numeric(w.absorbed_exposure,4)} / 阈值 {numeric(w.breach_threshold,4)} · {w.generated_area_m2===0 ? '未生成破口' : state.generated_breaches?.some(b=>b.id==='fragment:'+w.id) ? `生成 ${numeric(w.generated_area_m2,4)} m²` : '当前帧尚无生成破口'}</p>) : <p className="lab-note">全部边界默认封闭；没有声明可生成的海水或舱间接口。</p>}</details>
      <p className="lab-note">这是有舱壁遮挡的游戏破片估算，不包含爆压、真实穿甲或船壳断裂。新破口只影响后续进水，不反向改变本次破片路径。</p>
    </>}
  </section>;
}

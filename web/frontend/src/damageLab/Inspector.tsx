import { useState } from 'react';
import type { Experiment, LabResult, LabState, Room, ShipState } from './types';
import type { InspectionTarget } from './narrative';
import { numeric, percent } from './model';

function Comparison({ before, after, format = percent }: {
  before: number | null | undefined; after: number | null | undefined; format?: (n: number | null | undefined) => string;
}) {
  return <><span className="lab-before">{format(before)} <span aria-hidden="true">→</span></span><strong>{format(after)}</strong></>;
}

export default function Inspector({ experiment, state, baseline = null, rooms = [], selected, inspection, onSelect, onInspect }: {
  experiment: Experiment; state: LabState | null; baseline?: LabState | null; rooms?: Room[];
  selected: string; inspection?: InspectionTarget | null; onSelect: (id: string) => void; onInspect?: (target: InspectionTarget) => void;
}) {
  const [allCrew, setAllCrew] = useState(false);
  const format=experiment.detonation ? (value:number|null|undefined)=>value==null ? '未知' : `${numeric(value*100,2)}%` : percent;
  const crewDefinition=inspection?.kind==='crew' ? experiment.crew_groups.find(c=>c.id===inspection.id) : null;
  const roomId=inspection?.kind==='compartment' ? inspection.id : crewDefinition?.compartment_id;
  const definition = crewDefinition ? experiment.modules.find(m=>m.id===crewDefinition.module_id)
    : roomId ? experiment.modules.find(m=>m.id===selected && m.compartment_id===roomId)
    ?? experiment.modules.find(m=>m.compartment_id===roomId) : experiment.modules.find(m=>m.id===selected) ?? experiment.modules[0];
  const selectedRoom=roomId ?? definition?.compartment_id;
  const room=rooms.find(r=>r.id===selectedRoom), roomState=state?.compartments.find(r=>r.id===selectedRoom);
  const module = state?.modules.find(m=>m.id===definition?.id);
  const initial = baseline?.modules.find(m=>m.id===definition?.id);
  const groups=experiment.crew_groups.filter(g=>allCrew || !selectedRoom || g.compartment_id===selectedRoom);
  return <aside className="lab-inspector" aria-label="损伤说明">
    <span className="lab-kicker">02 / CONSEQUENCES</span><h2>影响与依据</h2>
    <div className="lab-module-list">{experiment.modules.map(m=>{
      const result=state?.modules.find(row=>row.id===m.id);
      return <button key={m.id} aria-pressed={selected===m.id} onClick={()=>onSelect(m.id)}>
        <span>{m.label}</span><strong>{result ? format(result.effective_availability) : '待试验'}</strong></button>;
    })}</div>
    {selectedRoom && <section className="lab-room-summary"><span className="lab-kicker">SELECTED COMPARTMENT / CORE STATE</span>
      <h3>{room?.label ?? selectedRoom}</h3><p className="lab-note">舱内水量 {numeric(roomState?.volume_m3,2)} m³ · 有效容量占比 {percent(roomState?.fill_fraction)}</p>
    </section>}
    {definition && <section><span className="lab-kicker">{definition.role.toUpperCase()} / GAME ESTIMATE</span><h3>{definition.label}</h3>
      <p className="lab-note">初始 → 当前接受状态</p>
      <dl><div><dt>机械完整度</dt><dd><Comparison before={initial?.mechanical_integrity} after={module?.mechanical_integrity} format={format} /></dd></div>
        <div><dt>进水可用度</dt><dd><Comparison before={initial?.flooding_availability} after={module?.flooding_availability} format={format} /></dd></div>
        <div><dt>值勤可用度</dt><dd><Comparison before={initial?.staffing_availability} after={module?.staffing_availability} format={format} /></dd></div>
        <div className="lab-total"><dt>综合可用度</dt><dd><Comparison before={initial?.effective_availability} after={module?.effective_availability} format={format} /></dd></div></dl>
      {module && <p className="lab-factor-equation">{format(module.mechanical_integrity)} × {format(module.flooding_availability)} × {format(module.staffing_availability)} = {format(module.effective_availability)}</p>}
      <p className="lab-note">{module?.causes.length ? module.causes.map(c=>({ localized_game_impact: '局部命中', estimated_fragment_exposure:'破片暴露估算', flood_disable: '进水停机' }[c] ?? c)).join(' / ') : state ? '未记录直接损伤原因' : '运行试验后显示事件依据'}{module?.staffing_availability===0 ? ' · 当前无可值勤人员' : ''}</p>
    </section>}
    <section><span className="lab-kicker">DUTY GROUPS / GAME ESTIMATE</span><h3>舱室乘员</h3>
      <label className="lab-check"><input type="checkbox" checked={allCrew} onChange={e=>setAllCrew(e.target.checked)} />全部乘员组</label>
      {!groups.length && <p className="lab-note">此舱室没有已声明的乘员组。</p>}
      {groups.map(group=>{
        const crew = state?.crew_groups.find(c=>c.id===group.id);
        const before = baseline?.crew_groups.find(c=>c.id===group.id);
        return <div className="lab-crew" key={group.id} data-selected={inspection?.kind==='crew' && inspection.id===group.id ? 'true' : undefined}>
          <button className="lab-crew-select" aria-pressed={inspection?.kind==='crew' && inspection.id===group.id} onClick={()=>onInspect?.({kind:'crew',id:group.id})}>{group.label} <span aria-hidden="true">↗</span></button>
          <dl>{([['available','可值勤'],['incapacitated','失能'],['dead','死亡'],['evacuated','撤离']] as const).map(([key,label])=>
            <div key={key}><dt>{label}</dt><dd><Comparison before={before?.[key]} after={crew?.[key]} format={n=>numeric(n,0)} /></dd></div>)}</dl>
          <p className="lab-note">{crew?.evacuation_triggered ? '值勤人员撤至抽象集合点；伤亡留在原舱。' : `${group.compartment_id} · 输入 ${numeric(group.personnel,0)} 人`}</p></div>;
      })}
    </section>
    <section><span className="lab-kicker">PROPULSION / ESTIMATE</span><h3>可用轴功率</h3>
      <p className="lab-power">{numeric(state?.capabilities.shaft_power_kw,0)} <small>kW</small></p>
      {baseline && <p className="lab-note">初始 {numeric(baseline.capabilities.shaft_power_kw,0)} kW → 当前 {numeric(state?.capabilities.shaft_power_kw,0)} kW</p>}
      {state?.capabilities.shaft_power_kw == null && <p className="lab-note">总量含未知输入；已知小计 {numeric(state?.capabilities.known_shaft_power_subtotal_kw,0)} kW。</p>}
    </section>
  </aside>;
}

export function ShipMetrics({ state, baseline }: { state: LabState | null; baseline: ShipState | null }) {
  const ship=state?.ship;
  const reference=ship ? baseline : null;
  return <div className="lab-ship-metrics" aria-label="船体状态对照">
    <div><span>新增水量</span><strong>{numeric(ship?.total_onboard_water_mass_t)} <small>t</small></strong>
      <p className="lab-note">首解 {numeric(reference?.total_onboard_water_mass_t)} t</p></div>
    <div><span>横倾</span><strong>{numeric(ship?.equilibrium.heel_deg,2)} <small>°</small></strong>
      <p className="lab-note">首解 {numeric(reference?.equilibrium.heel_deg,2)}°</p></div>
    <div><span>纵倾</span><strong>{numeric(ship?.equilibrium.trim_deg,2)} <small>°</small></strong>
      <p className="lab-note">首解 {numeric(reference?.equilibrium.trim_deg,2)}°</p></div>
    <div><span>质量残差</span><strong>{ship ? ship.mass_conservation_error_t.toExponential(1) : '未知'} <small>t</small></strong>
      <p className="lab-note">核心接受状态</p></div>
  </div>;
}

export function CoreEvidence({ result }: { result: LabResult }) {
  const stage=result.core_analysis.stages.flooding;
  const native=stage.data;
  const remaining=native?.remaining_gz as { rows?: Array<{ angle_deg: number; gz_m: number | null }>; converged?: boolean } | null;
  const rows=remaining?.rows ?? [], segments:Array<Array<{angle_deg:number;gz_m:number}>>=[];
  let segment:Array<{angle_deg:number;gz_m:number}>=[];
  for(const row of rows){
    if(Number.isFinite(row.angle_deg) && row.gz_m!=null && Number.isFinite(row.gz_m)){
      if(!segment.length)segments.push(segment);segment.push({angle_deg:row.angle_deg,gz_m:row.gz_m});
    }else segment=[];
  }
  const points=segments.flat(), angles=rows.map(p=>p.angle_deg).filter(Number.isFinite);
  const xMin=angles.length ? Math.min(...angles) : 0, xMax=angles.length ? Math.max(...angles) : 0;
  const yMin=Math.min(0,...points.map(p=>p.gz_m)), yMax=Math.max(.1,...points.map(p=>p.gz_m));
  const x=(angle:number)=>xMax===xMin ? 180 : 20+(angle-xMin)/(xMax-xMin)*320;
  const y=(gz:number)=>100-(gz-yMin)/(yMax-yMin)*80;
  const xy=(p:{angle_deg:number;gz_m:number})=>`${x(p.angle_deg)},${y(p.gz_m)}`;
  return <section className="lab-evidence" aria-label="计算依据">
    <div><span className="lab-kicker">PLIMSOLL CORE / ACCEPTED STATE</span><h2>原始计算依据</h2>
      <p>停止：<strong>{String(native?.stop_reason ?? stage.reason ?? stage.status)}</strong> · 接受终点 {numeric(result.simulated_duration_s,2)} s</p>
      <p className="lab-note">数值完成与适用性分别保留。游戏损伤估算没有史实或医学认证。</p>
      <details><summary>方法、来源与诊断</summary>
        <p>{result.assumptions.join(' · ')}</p>
        <pre>{JSON.stringify({ method_versions: result.method_versions, validity: result.validity, diagnostics: result.diagnostics }, null, 2)}</pre>
      </details></div>
    <div><span className="lab-kicker">FINAL ACCEPTED STATE / REMAINING GZ</span>
      {points.length ? <><svg viewBox="0 0 360 125" role="img" aria-label="最终接受状态的剩余稳性曲线">
        <path d={`M20 15V100H340 M20 ${y(0)}H340`} fill="none" stroke="currentColor" opacity=".3" />
        {xMin<=0 && xMax>=0 && <path d={`M${x(0)} 15V100`} fill="none" stroke="currentColor" opacity=".3" />}
        {segments.map((part,i)=><polyline key={i} points={part.map(xy).join(' ')} fill="none" stroke="var(--accent)" strokeWidth="2" />)}
        {points.map(p=><circle key={p.angle_deg} cx={x(p.angle_deg)} cy={y(p.gz_m)} r="3" fill="var(--accent)" />)}
        <text x="20" y="120">{xMin}°</text><text x="340" y="120" textAnchor="end">{xMax}°</text><text x="25" y="15">GZ / m</text></svg>
        <p className="lab-note">仅最终接受状态的原始采样；不推断沉没或安全。</p></> : <p>剩余 GZ 暂不可用</p>}
    </div>
  </section>;
}

import type { Experiment, LabResult, LabState } from './types';
import { numeric, percent } from './model';

export default function Inspector({ experiment, state, selected, onSelect }: {
  experiment: Experiment; state: LabState | null; selected: string; onSelect: (id: string) => void;
}) {
  const definition = experiment.modules.find(m=>m.id===selected) ?? experiment.modules[0];
  const module = state?.modules.find(m=>m.id===definition?.id);
  return <aside className="lab-inspector" aria-label="损伤说明">
    <span className="lab-kicker">02 / CONSEQUENCES</span><h2>影响与依据</h2>
    <div className="lab-module-list">{experiment.modules.map(m=>{
      const result=state?.modules.find(row=>row.id===m.id);
      return <button key={m.id} aria-pressed={selected===m.id} onClick={()=>onSelect(m.id)}>
        <span>{m.label}</span><strong>{result ? percent(result.effective_availability) : '待试验'}</strong></button>;
    })}</div>
    {definition && <section><span className="lab-kicker">{definition.role.toUpperCase()}</span><h3>{definition.label}</h3>
      <p className="lab-note">{definition.compartment_id}</p>
      <dl><div><dt>机械完整度</dt><dd>{percent(module?.mechanical_integrity)}</dd></div>
        <div><dt>进水可用度</dt><dd>{percent(module?.flooding_availability)}</dd></div>
        <div><dt>值勤可用度</dt><dd>{percent(module?.staffing_availability)}</dd></div>
        <div className="lab-total"><dt>综合可用度</dt><dd>{percent(module?.effective_availability)}</dd></div></dl>
      <p className="lab-note">{module?.causes.length ? module.causes.map(c=>({ localized_game_impact: '局部命中', flood_disable: '进水停机' }[c] ?? c)).join(' / ') : state ? '未记录损伤原因' : '运行试验后显示事件依据'}</p>
    </section>}
    <section><span className="lab-kicker">DUTY GROUPS / GAME ESTIMATE</span><h3>舱室乘员</h3>
      {experiment.crew_groups.map(group=>{
        const crew = state?.crew_groups.find(c=>c.id===group.id);
        return <div className="lab-crew" key={group.id}><strong>{group.label}</strong>
          <dl>{([['available','可值勤'],['incapacitated','失能'],['dead','死亡'],['evacuated','撤离']] as const).map(([key,label])=>
            <div key={key}><dt>{label}</dt><dd>{numeric(crew?.[key],0)}</dd></div>)}</dl>
          <p className="lab-note">{crew?.evacuation_triggered ? '值勤人员撤至抽象集合点；伤亡留在原舱。' : `${group.compartment_id} · 输入 ${numeric(group.personnel,0)} 人`}</p></div>;
      })}
    </section>
    <section><span className="lab-kicker">PROPULSION / ESTIMATE</span><h3>可用轴功率</h3>
      <p className="lab-power">{numeric(state?.capabilities.shaft_power_kw,0)} <small>kW</small></p>
      {state?.capabilities.shaft_power_kw == null && <p className="lab-note">总量含未知输入；已知小计 {numeric(state?.capabilities.known_shaft_power_subtotal_kw,0)} kW。</p>}
    </section>
  </aside>;
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

import type { LabResult, Room } from './types';
import { numeric, percent } from './model';

export type InspectionTarget = { kind: 'module' | 'crew' | 'compartment'; id: string };
export type LabChange = { target: InspectionTarget | null; title: string; detail: string; source: 'game' | 'core' | 'mixed' };
export type ReplayEntry = {
  frame: number; eventIndex: number; time: number; title: string;
  changes: LabChange[]; targets: InspectionTarget[]; significant: boolean;
};
export const SOURCE = { game: '游戏规则估算', core: '核心接受状态', mixed: '核心状态 / 游戏规则' };
const changed = (a: number | null | undefined, b: number | null | undefined) => a !== b &&
  (a == null || b == null || Math.abs(a - b) > 1e-10);

export function comparisonBaseline(result: LabResult | null) {
  return { initial: result?.snapshots[0] ?? null,
    ship: result?.snapshots.find(s => s.ship && Number.isFinite(s.ship.equilibrium.heel_deg)
      && Number.isFinite(s.ship.equilibrium.trim_deg))?.ship ?? null };
}

/** Derive explanations only from frozen adjacent states, never from message prose. */
export function replayEntries(result: LabResult | null): ReplayEntry[] {
  if (!result) return [];
  const integrity=result.request?.experiment?.detonation ? (v:number)=>`${numeric(v*100,2)}%` : percent;
  const rooms = (result.input_snapshot?.compartments ?? []) as Room[];
  return result.snapshots.map((state, frame) => {
    const previous = result.snapshots[frame - 1];
    const changes: LabChange[] = [];
    const event = result.events.find(e => e.index === state.event_index);
    let significant = !previous;
    if(event?.kind==='detonation')changes.push({target:event.target_id ? {kind:'compartment',id:event.target_id} : null,
      title:'起爆与破片路径',source:'game',detail:`已知起爆点 ${event.data?.position_m?.map(v=>numeric(v,2)).join(' / ')} m；${event.data?.fragment_count} 条代表性路径，种子 ${event.data?.seed}。路径考虑声明的舱壁遮挡。`});
    if(event?.kind==='generated_breaches')for(const breach of event.data?.breaches ?? [])changes.push({
      target:{kind:'compartment',id:breach.from_id==='sea' ? breach.to_id : breach.from_id},title:'生成水力破口',source:'game',
      detail:`${breach.from_id} → ${breach.to_id} · ${numeric(breach.area_m2,4)} m² · Cd ${numeric(breach.discharge_coefficient,2)}。游戏规则估算开孔，交由原有核心求解进水。`});
    for (const module of state.modules) {
      const before = previous?.modules.find(m => m.id === module.id);
      if (!before) continue;
      const target: InspectionTarget = { kind: 'module', id: module.id };
      if (changed(before.mechanical_integrity, module.mechanical_integrity)) changes.push({ target,
        title: '机械损伤', detail: `${module.label} · 完整度 ${integrity(before.mechanical_integrity)} → ${integrity(module.mechanical_integrity)}。设备质量保留。`, source: 'game' });
      if (changed(before.staffing_availability, module.staffing_availability)) changes.push({ target,
        title: '值勤可用度变化', detail: `${module.label} · 值勤可用度 ${percent(before.staffing_availability)} → ${percent(module.staffing_availability)}；影响该模块的综合可用度。`, source: 'game' });
      if (changed(before.flooding_availability, module.flooding_availability)) changes.push({ target,
        title: module.flooding_availability === 0 ? '进水停机' : '进水可用度变化',
        detail: `${module.label} · 进水可用度 ${percent(before.flooding_availability)} → ${percent(module.flooding_availability)}。本次接受状态首次记录阈值变化。`, source: 'mixed' });
    }
    for (const crew of state.crew_groups) {
      const before = previous?.crew_groups.find(c => c.id === crew.id);
      if (!before) continue;
      const target: InspectionTarget = { kind: 'crew', id: crew.id };
      if (changed(before.incapacitated, crew.incapacitated) || changed(before.dead, crew.dead)) changes.push({ target,
        title: '乘员影响', detail: `${crew.label} · 失能 ${numeric(before.incapacitated, 0)} → ${numeric(crew.incapacitated, 0)} 人；死亡 ${numeric(before.dead, 0)} → ${numeric(crew.dead, 0)} 人。`, source: 'game' });
      if (changed(before.evacuated, crew.evacuated) || before.evacuation_triggered !== crew.evacuation_triggered) changes.push({ target,
        title: '乘员撤离', detail: `${crew.label} · 撤离 ${numeric(before.evacuated, 0)} → ${numeric(crew.evacuated, 0)} 人，可值勤 ${numeric(before.available, 0)} → ${numeric(crew.available, 0)} 人。集合点为抽象位置；伤亡仍关联原舱。`, source: 'mixed' });
      if (event?.kind === 'crew_impact' && event.target_id === crew.id && crew.initial_personnel == null) changes.push({ target,
        title: '乘员人数未知', detail: `${crew.label} · 人数未知，失能与死亡数量保持未知。`, source: 'game' });
    }
    significant ||= changes.length > 0;
    if (state.ship && !previous?.ship) {
      changes.push({ target: null, title: '首个有效平衡解', source: 'core',
        detail: `横倾 ${numeric(state.ship.equilibrium.heel_deg, 2)}°，纵倾 ${numeric(state.ship.equilibrium.trim_deg, 2)}°。后续姿态对照以此为基准。` });
      significant = true;
    }
    for (const room of state.compartments) {
      const before = previous?.compartments.find(c => c.id === room.id);
      if (!changed(before?.volume_m3, room.volume_m3) || (!before && room.volume_m3 === 0)) continue;
      const label = rooms.find(r => r.id === room.id)?.label ?? room.id;
      changes.push({ target: { kind: 'compartment', id: room.id }, title: '舱室进水状态', source: 'core',
        detail: `${label} · 水量 ${numeric(before?.volume_m3, 2)} → ${numeric(room.volume_m3, 2)} m³，占有效容量 ${percent(room.fill_fraction)}。` });
    }
    const last = frame === result.snapshots.length - 1;
    significant ||= last;
    const targets = changes.flatMap(c => c.target ? [c.target] : []);
    return { frame, eventIndex: state.event_index, time: state.time_s, changes,
      targets: targets.filter((target, i) => targets.findIndex(t => t.kind === target.kind && t.id === target.id) === i), significant,
      title: !previous ? '命中前 / 声明状态' : changes[0]?.title ?? (last ? '最终接受状态' : '状态记录 / 无新增变化') };
  });
}

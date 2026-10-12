import type { LabResult, Room } from './types';
import { labFormat } from '../i18n/labFormat';
import { labCopy, type LabKey } from '../i18n/lab';

export type InspectionTarget = { kind: 'module' | 'crew' | 'compartment'; id: string };
export type LabChange = { target: InspectionTarget | null; title: string; detail: string; source: 'game' | 'core' | 'mixed' };
export type ReplayEntry = {
  frame: number; eventIndex: number; time: number; title: string;
  changes: LabChange[]; targets: InspectionTarget[]; significant: boolean;
};

/**
 * Where an explanation's numbers came from.
 *
 * This is the one distinction the replay panel must never blur: a gameplay rule
 * estimated something, the core accepted something, or both are involved. It is
 * stored as a closed enum and labelled from the laboratory dictionary, so the
 * reader can see which is which in either language.
 */
export type LabSource = LabChange['source'];

const changed = (a: number | null | undefined, b: number | null | undefined) => a !== b &&
  (a == null || b == null || Math.abs(a - b) > 1e-10);

export function comparisonBaseline(result: LabResult | null) {
  return { initial: result?.snapshots[0] ?? null,
    ship: result?.snapshots.find(s => s.ship && Number.isFinite(s.ship.equilibrium.heel_deg)
      && Number.isFinite(s.ship.equilibrium.trim_deg))?.ship ?? null };
}

/**
 * Derive explanations only from frozen adjacent states, never from message prose.
 *
 * The language is a parameter rather than a hidden global so this stays a pure
 * function: the same saved result yields the same frames in either language, and
 * a change of language re-derives the wording without touching the data, the
 * frame order or anything a reader has selected.
 */
export function replayEntries(result: LabResult | null, language: Parameters<typeof labFormat>[0]): ReplayEntry[] {
  if (!result) return [];
  const f = labFormat(language);
  const t = (key: LabKey, params?: Record<string, string | number>) => labCopy(language, key, params);
  const percent = f.percent;
  const integrity = result.request?.experiment?.detonation ? (v: number) => `${f.numeric(v * 100, 2)}%` : percent;
  const rooms = (result.input_snapshot?.compartments ?? []) as Room[];
  return result.snapshots.map((state, frame) => {
    const previous = result.snapshots[frame - 1];
    const changes: LabChange[] = [];
    const event = result.events.find(e => e.index === state.event_index);
    let significant = !previous;
    if (event?.kind === 'detonation') changes.push({ target: event.target_id ? { kind: 'compartment', id: event.target_id } : null,
      title: t('entry.detonation'), source: 'game',
      detail: t('entry.detonation.detail', {
        point: event.data?.position_m?.map(v => f.numeric(v, 2)).join(' / ') ?? '',
        count: String(event.data?.fragment_count ?? 0),
        seed: String(event.data?.seed ?? 0),
      }) });
    if (event?.kind === 'generated_breaches') for (const breach of event.data?.breaches ?? []) changes.push({
      target: { kind: 'compartment', id: breach.from_id === 'sea' ? breach.to_id : breach.from_id },
      title: t('entry.generatedBreach'), source: 'game',
      detail: t('entry.generatedBreach.detail', {
        from: breach.from_id, to: breach.to_id, area: f.numeric(breach.area_m2, 4), discharge: f.numeric(breach.discharge_coefficient, 2),
      }) });
    for (const module of state.modules) {
      const before = previous?.modules.find(m => m.id === module.id);
      if (!before) continue;
      const target: InspectionTarget = { kind: 'module', id: module.id };
      if (changed(before.mechanical_integrity, module.mechanical_integrity)) changes.push({ target,
        title: t('entry.mechanical'), source: 'game',
        detail: t('entry.mechanical.detail', { label: module.label, before: integrity(before.mechanical_integrity), after: integrity(module.mechanical_integrity) }) });
      if (changed(before.staffing_availability, module.staffing_availability)) changes.push({ target,
        title: t('entry.staffing'), source: 'game',
        detail: t('entry.staffing.detail', { label: module.label, before: percent(before.staffing_availability), after: percent(module.staffing_availability) }) });
      if (changed(before.flooding_availability, module.flooding_availability)) changes.push({ target,
        title: module.flooding_availability === 0 ? t('entry.floodShutdown') : t('entry.flooding'),
        source: 'mixed',
        detail: t('entry.flooding.detail', { label: module.label, before: percent(before.flooding_availability), after: percent(module.flooding_availability) }) });
    }
    for (const crew of state.crew_groups) {
      const before = previous?.crew_groups.find(c => c.id === crew.id);
      if (!before) continue;
      const target: InspectionTarget = { kind: 'crew', id: crew.id };
      if (changed(before.incapacitated, crew.incapacitated) || changed(before.dead, crew.dead)) changes.push({ target,
        title: t('entry.crewImpact'), source: 'game',
        detail: t('entry.crewImpact.detail', {
          label: crew.label,
          before: f.numeric(before.incapacitated, 0), after: f.numeric(crew.incapacitated, 0),
          beforeDead: f.numeric(before.dead, 0), afterDead: f.numeric(crew.dead, 0),
        }) });
      if (changed(before.evacuated, crew.evacuated) || before.evacuation_triggered !== crew.evacuation_triggered) changes.push({ target,
        title: t('entry.evacuation'), source: 'mixed',
        detail: t('entry.evacuation.detail', {
          label: crew.label,
          before: f.numeric(before.evacuated, 0), after: f.numeric(crew.evacuated, 0),
          beforeDuty: f.numeric(before.available, 0), afterDuty: f.numeric(crew.available, 0),
        }) });
      if (event?.kind === 'crew_impact' && event.target_id === crew.id && crew.initial_personnel == null) changes.push({ target,
        title: t('entry.crewUnknown'), source: 'game', detail: t('entry.crewUnknown.detail', { label: crew.label }) });
    }
    significant ||= changes.length > 0;
    if (state.ship && !previous?.ship) {
      changes.push({ target: null, title: t('entry.firstEquilibrium'), source: 'core',
        detail: t('entry.firstEquilibrium.detail', { heel: f.numeric(state.ship.equilibrium.heel_deg, 2), trim: f.numeric(state.ship.equilibrium.trim_deg, 2) }) });
      significant = true;
    }
    for (const room of state.compartments) {
      const before = previous?.compartments.find(c => c.id === room.id);
      if (!changed(before?.volume_m3, room.volume_m3) || (!before && room.volume_m3 === 0)) continue;
      const label = rooms.find(r => r.id === room.id)?.label ?? room.id;
      changes.push({ target: { kind: 'compartment', id: room.id }, title: t('entry.compartment'), source: 'core',
        detail: t('entry.compartment.detail', {
          label, before: f.numeric(before?.volume_m3, 2), after: f.numeric(room.volume_m3, 2), fill: percent(room.fill_fraction),
        }) });
    }
    const last = frame === result.snapshots.length - 1;
    significant ||= last;
    const targets = changes.flatMap(c => c.target ? [c.target] : []);
    return { frame, eventIndex: state.event_index, time: state.time_s, changes,
      targets: targets.filter((target, i) => targets.findIndex(o => o.kind === target.kind && o.id === target.id) === i), significant,
      title: !previous ? t('entry.beforeHit') : changes[0]?.title ?? (last ? t('entry.final') : t('entry.plain')) };
  });
}
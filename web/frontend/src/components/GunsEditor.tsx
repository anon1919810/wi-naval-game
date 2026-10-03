import { useState } from 'react';

import type { RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { ResultSection, StudyResult } from './FormResults';
import { object, rows, stringList, uniqueId, type Raw } from './formModel';
import { isWeaponsPageLeaf } from './weaponsModel';

// Declared gun-battery inputs and the broadside shell-weight aggregate.
// `null` always means "unknown" — it must never be coerced to 0 when saved.
//
// A battery is any `systems.weapons` leaf that is not the weapons page's torpedo
// or miscellaneous-zone leaf, so a battery with declared counts and page rows is
// editable even when it declares no ammunition mass model. Without a
// `counted_ammunition_mass` model, an optional sourced projectile fact is used
// only for reporting; it never invents ammunition ledger mass.

export type GunBattery = Raw;
export type Weapons = Record<string, unknown>;

interface ShellMass {
  value: number | null; source: string | null; estimate: boolean | null;
  status?: string; origin?: string | null; mass_authority?: string | null;
}
interface GunsAggregate {
  installed_guns?: number | null; broadside_guns?: number | null; rounds_per_gun?: number | null;
  shell_mass_kg?: ShellMass;
  broadside_mass_kg?: number | null; broadside_mass_lb?: number | null; per_gun_shell_kg?: number | null;
  ship_wide_ammunition_t?: number | null; ledger_mass_t?: number | null;
  status?: string; formula?: string; shell_mass_boundary?: string;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}
interface BatteryView { guns?: GunsAggregate; rotating_armour_component?: Raw; rows?: Raw[] }

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function pickBatteryView(runs: RunView[], batteryId: string): BatteryView | null {
  const key = `weapons.${batteryId}`;
  const withData = runs.filter(run => !!object(object(run.result?.stages?.systems?.data as Raw | undefined).page_rows)[key]);
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems!.data as Raw;
  return object(object(data.page_rows)[key]) as BatteryView;
}

function findAmmoModel(battery: GunBattery | null): { index: number; model: GunBattery } | null {
  if (!battery || !Array.isArray(battery.mass_models)) return null;
  const models = battery.mass_models as GunBattery[];
  const index = models.findIndex(m => !!m && typeof m === 'object' && m.method === 'counted_ammunition_mass');
  return index < 0 ? null : { index, model: models[index] };
}

function readProjectile(battery: GunBattery | null): { value: number | null; source: string | null; estimate: boolean | null } {
  const found = findAmmoModel(battery);
  if (!found) return { value: null, source: null, estimate: null };
  const inputs = object(found.model.inputs);
  const provenance = object(object(found.model.input_provenance).projectile_mass_kg);
  return {
    value: numeric(inputs.projectile_mass_kg),
    source: typeof provenance.source === 'string' ? provenance.source : null,
    estimate: provenance.estimate === true ? true : provenance.estimate === false ? false : null,
  };
}

// The core reads an installed count with `_count`, which rejects null outright;
// an unknown count is therefore expressed by omitting the key, never by null or 0.
function countProblem(raw: string): string | null {
  if (raw.trim() === '') return null;
  const value = Number(raw);
  if (!Number.isFinite(value)) return '必须是有限数值';
  return Number.isInteger(value) && value >= 0 ? null : '必须是非负整数；未知请留空';
}

export function GunsEditor({ weapons, runs, ledger, onPatchBattery }: {
  weapons: Weapons;
  runs: RunView[];
  ledger: Array<{ id: string; label?: string }>;
  onPatchBattery: (id: string, next: GunBattery) => void;
}) {
  const batteryIds = Object.keys(weapons).filter(id => !isWeaponsPageLeaf(id)
    && !!weapons[id] && typeof weapons[id] === 'object' && !Array.isArray(weapons[id]));
  const [choice, setChoice] = useState<string | null>(null);
  const batteryId = (choice && batteryIds.includes(choice) ? choice : batteryIds[0]) ?? '';
  const battery = batteryId ? object(weapons[batteryId]) : {};
  const view = pickBatteryView(runs, batteryId);
  const agg = view?.guns ?? null;
  const hasAmmo = findAmmoModel(battery) !== null;
  const projectile = readProjectile(battery);
  // Reporting-only declaration, used by page_rows.guns_view only when the
  // battery declares no ammunition mass model. See page_rows.guns_rows.
  const facts = object(battery.facts);
  const declaredFact = object(facts.projectile_mass_kg);
  const [problems, setProblems] = useState<Record<string, string>>({});
  const [newId, setNewId] = useState('battery_1');
  const run = runs[0] ?? null;

  function emit(next: GunBattery) { onPatchBattery(batteryId, next); }
  function setCount(key: 'installed_guns' | 'broadside_guns' | 'rounds_per_gun', raw: string) {
    const problem = countProblem(raw);
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    if (problem) return;
    const next = { ...battery };
    if (raw.trim() === '') delete next[key];
    else next[key] = Number(raw);
    emit(next);
  }
  function updateProjectile(value: number | null, patch: { source?: string | null; estimate?: boolean | null }) {
    const found = findAmmoModel(battery);
    if (!found) return;
    const models = (battery.mass_models as GunBattery[]).map(m => ({ ...m }));
    const model = { ...models[found.index] };
    model.inputs = { ...object(model.inputs), projectile_mass_kg: value };
    const provenance = { ...object(model.input_provenance) };
    const entry = { ...object(provenance.projectile_mass_kg) };
    if (patch.source !== undefined) entry.source = patch.source;
    if (patch.estimate !== undefined) entry.estimate = patch.estimate;
    provenance.projectile_mass_kg = entry;
    model.input_provenance = provenance;
    models[found.index] = model;
    emit({ ...battery, mass_models: models });
  }
  function patchFact(fact: Raw) {
    const next = { ...battery };
    // Remove only this declaration; any other declared fact on the battery stays.
    const rest = { ...facts };
    if (fact.value == null && fact.source == null && fact.estimate == null) delete rest.projectile_mass_kg;
    else rest.projectile_mass_kg = fact;
    if (Object.keys(rest).length === 0) delete next.facts; else next.facts = rest;
    emit(next);
  }
  function createBattery() {
    const id = uniqueId(newId.trim() || 'battery_1', batteryIds);
    setChoice(id);
    setProblems({});
    onPatchBattery(id, { weight_item_ids: [], source: null, estimate: null });
  }

  return <div className="guns-editor form-stack">
    <div className="form-card"><h3>炮组</h3>
      <p>声明装舰/单舷炮数与每炮携弹数。单发弹重优先取自弹药质量模型，无模型时可声明仅用于报告的弹重；全舰弹药携带量仍取自账本。鱼雷与杂项分区在“鱼雷与水雷武备”页编辑。</p>
      {batteryIds.length === 0 && <p className="form-hint">项目尚未声明任何炮组。可在此建立炮组，再逐项声明数量与来源；炮数未知请留空，不要填 0。</p>}
      <div className="form-grid">
        <label className="field-label">当前炮组<select aria-label="选择炮组" value={batteryId}
          onChange={e => setChoice(e.target.value)}>
          {batteryIds.length === 0 && <option value="">（尚无炮组）</option>}
          {batteryIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select></label>
        <label className="field-label">新炮组 id<input aria-label="新炮组 id" value={newId}
          onChange={e => setNewId(e.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={createBattery}>添加炮组</button>
      </div>
    </div>

    {batteryId && <>
      <div className="form-card"><h3>声明输入 · {batteryId}</h3>
        <div className="form-grid">
          {([['installed_guns', '装舰炮数'], ['broadside_guns', '单舷炮数'], ['rounds_per_gun', '每炮携弹数']] as const).map(([key, label]) => {
            const problem = problems[key];
            return <label className="field-label" key={key}>{label}
              <input type="number" step="1" min="0" placeholder="未知" aria-label={`${batteryId} ${label}`}
                aria-invalid={Boolean(problem)} value={numeric(battery[key]) ?? ''}
                onChange={e => setCount(key, e.target.value)} />
              {problem && <span className="field-error" role="alert">{problem}</span>}</label>;
          })}
        </div>
        <p className="form-hint">炮数未知请留空：核心把留空读作“未声明”，而 0 表示已知的零门配置。</p>
        {hasAmmo && <p className="form-hint">该炮组声明了弹药质量模型，因此装舰炮数与每炮携弹数为必填；清空其中一项会使系统阶段无法计算。</p>}
      </div>

      <div className="form-card"><h3>单发弹丸质量</h3>
        {hasAmmo ? <div className="form-grid">
          <label className="field-label">单发弹重 · kg<input type="number" step="any" placeholder="未知"
            aria-label={`${batteryId} 单发弹重`} value={projectile.value ?? ''}
            onChange={e => updateProjectile(e.target.value.trim() === '' ? null : Number(e.target.value), {})} /></label>
          <label className="field-label">来源<input aria-label={`${batteryId} 单发弹重来源`} placeholder="待补充来源"
            value={projectile.source ?? ''}
            onChange={e => updateProjectile(projectile.value, { source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
          <EstimateInput label={`${batteryId} 单发弹重估算状态`} value={projectile.estimate}
            onChange={estimate => updateProjectile(projectile.value, { estimate })} />
        </div> : <div className="form-card-body">
          <p className="section-intro">该炮组没有 counted_ammunition_mass 模型。可在此声明单发弹重，仅用于齐射/每炮弹重报告；它不会生成账本弹药质量，装药与全舰携带量保持未知，也不从账本质量倒算。</p>
          <FactInput label={`${batteryId} 单发弹重（仅报告）`} value={declaredFact}
            onChange={f => patchFact({ value: f.value, source: f.source, estimate: f.estimate })} />
        </div>}
      </div>

      <div className="form-card"><h3>炮组账本绑定</h3>
        <p>炮组质量只来自所选载荷账本。请为 guns / mounts / ammunition 各行绑定对应条目，绑定可在“项目数据”或下方选择。</p>
        <IdPicker label={`${batteryId} 炮组账本条目`} selected={battery.weight_item_ids} options={ledger}
          onChange={ids => emit({ ...battery, weight_item_ids: ids })} />
        <p className="form-hint">
          {stringList(battery.weight_item_ids).length === 0
            ? '尚未绑定账本条目：运行时会报告 systems.present_without_weight_items。'
            : `已绑定 ${stringList(battery.weight_item_ids).length} 项。`}
        </p>
      </div>
    </>}

    <ResultSection available={true}>
      {agg
        ? <>
          <div className="metric-grid">
            <ResultFact label="单发弹重" value={numeric(agg.shell_mass_kg?.value)} unit="kg"
              note={numeric(agg.shell_mass_kg?.value) === null ? '未知：缺少有来源的弹丸质量'
                : agg.shell_mass_kg?.origin === 'declared_projectile_mass_kg_fact' ? '声明事实，仅用于报告' : '来自弹药质量模型'}
              status={numeric(agg.shell_mass_kg?.value) === null ? 'unknown' : agg.shell_mass_kg?.estimate ? 'estimate' : 'known'} />
            {/* Derived weights inherit the shell's estimate state: an estimated
                projectile mass yields estimated broadside/per-gun weights. */}
            <ResultFact label="单舷齐射弹重" value={numeric(agg.broadside_mass_kg)} unit="kg"
              note={numeric(agg.broadside_mass_kg) === null ? '未知：缺少弹丸质量或单舷炮数' : '不含装药与全舰弹药'}
              estimate={agg.shell_mass_kg?.estimate} />
            <ResultFact label="每炮携弹壳重" value={numeric(agg.per_gun_shell_kg)} unit="kg"
              note={numeric(agg.per_gun_shell_kg) === null ? '未知：缺少弹丸质量或每炮携弹数' : '不含装药'}
              estimate={agg.shell_mass_kg?.estimate} />
            <ResultFact label="全舰弹药携带" value={numeric(agg.ship_wide_ammunition_t)} unit="t" note="账本携带量，与齐射弹重分开" />
            <ResultFact label="炮组账本质量" value={numeric(agg.ledger_mass_t)} unit="t" note="所选载荷账本" />
          </div>
          <p className="form-hint">齐射弹重 = 单发弹重 × 单舷炮数；仅弹丸，不含装药，也不含全舰携带弹药。{String(agg.shell_mass_boundary ?? '')}</p>
          <Diagnostics value={agg.diagnostics} />
        </>
        : <p className="section-intro">保存并运行后显示聚合值</p>}
      <StudyResult label={`${batteryId || '炮组'} 炮座内旋转装甲拆分`} data={view?.rotating_armour_component}
        metrics={[['rotating_armour_mass_t', '旋转装甲', 't'], ['other_mount_mass_t', '炮座其余部分', 't']]} />
    </ResultSection>
  </div>;
}

function ResultFact({ label, value, unit, note, status, estimate }: {
  label: string; value: number | null; unit: string; note: string;
  status?: 'known' | 'estimate' | 'unknown'; estimate?: boolean | null;
}) {
  const resolved = value === null ? 'unknown' : status ?? (estimate === true ? 'estimate' : 'known');
  return <div className={`fact-field fact-field--${resolved}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{value === null ? '未知' : `${value} ${unit}`}</strong>
    <span className="fact-meta">{resolved === 'estimate' ? '估算 · ' : ''}{note}</span>
  </div>;
}

function Diagnostics({ value }: { value: unknown }) {
  const items = rows(value);
  if (items.length === 0) return null;
  return <ul className="diagnostics-list">
    {items.map((item, index) => <li key={index}><code>{String(item.code ?? '诊断')}</code>{item.message ? `：${String(item.message)}` : ''}</li>)}
  </ul>;
}

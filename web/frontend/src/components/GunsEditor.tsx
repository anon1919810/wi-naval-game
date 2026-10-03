import { useState } from 'react';

import type { RunView } from '../types';
import { FactField } from './FactField';

// Declared gun-battery inputs and the broadside shell-weight aggregate.
// `null` always means "unknown" — it must never be coerced to 0 when saved.

type Raw = Record<string, unknown>;
export type GunBattery = Raw;
export type Weapons = Record<string, unknown>;

interface ShellMass {
  value: number | null;
  source: string | null;
  estimate: boolean | null;
  status?: string;
}

interface GunsAggregate {
  shell_mass_kg?: ShellMass;
  broadside_mass_kg?: number | null;
  broadside_mass_lb?: number | null;
  per_gun_shell_kg?: number | null;
  ship_wide_ammunition_t?: number | null;
  status?: string;
  formula?: string;
  diagnostics?: Array<{ code?: string; message?: string; [key: string]: unknown }>;
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// Most recent run carrying a weapons guns projection for the selected battery.
// The aggregate values come from the backend computation — never recomputed here.
function pickGunsAggregate(runs: RunView[], batteryId: string): GunsAggregate | null {
  const key = `weapons.${batteryId}`;
  const withData = runs
    .filter(run => {
      const data = run.result?.stages?.systems?.data;
      if (!data || typeof data !== 'object') return false;
      const pageRows = (data as Raw).page_rows;
      if (!pageRows || typeof pageRows !== 'object') return false;
      const view = (pageRows as Raw)[key];
      return !!view && typeof view === 'object' && !!(view as Raw).guns;
    })
    .sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')));
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.systems.data as Raw;
  const view = (data.page_rows as Raw)[key] as Raw;
  return (view.guns as GunsAggregate) ?? null;
}

// Tri-state estimate: unchecked = false, checked = true, indeterminate = undeclared.
function EstimateCheckbox({ value, onChange }: { value: boolean | null; onChange: (next: boolean | null) => void }) {
  return <>
    <input
      type="checkbox"
      aria-label="估算"
      ref={el => { if (el) el.indeterminate = value === null; }}
      checked={value === true}
      onChange={() => onChange(value === null ? true : value === true ? false : null)}
    />
    {value === null && <small>未声明</small>}
  </>;
}

function findAmmoModel(battery: GunBattery | null): { index: number; model: GunBattery } | null {
  if (!battery || !Array.isArray(battery.mass_models)) return null;
  const models = battery.mass_models as GunBattery[];
  const index = models.findIndex(m => !!m && m.method === 'counted_ammunition_mass');
  if (index < 0) return null;
  return { index, model: models[index] };
}

function readProjectile(battery: GunBattery | null): { value: number | null; source: string | null; estimate: boolean | null } {
  const found = findAmmoModel(battery);
  if (!found) return { value: null, source: null, estimate: null };
  const inputs = (found.model.inputs as Raw) ?? {};
  const prov = ((found.model.input_provenance as Raw) ?? {}).projectile_mass_kg as Raw | undefined;
  const estimate = prov?.estimate === true ? true : prov?.estimate === false ? false : null;
  const source = typeof prov?.source === 'string' ? prov!.source : null;
  const value = numeric(inputs.projectile_mass_kg);
  return { value, source, estimate };
}

export function GunsEditor({ weapons, runs, onPatchBattery }: {
  weapons: Weapons;
  runs: RunView[];
  onPatchBattery: (id: string, next: GunBattery) => void;
}) {
  // Only the gun batteries declare a counted-ammunition/shell mass model; the
  // torpedo and misc_weight leaves are edited on the Weapons page, not here.
  const batteryIds = Object.keys(weapons).filter(id => {
    if (!id) return false;
    const leaf = weapons[id];
    if (!leaf || typeof leaf !== 'object') return false;
    const models = (leaf as Raw).mass_models;
    return Array.isArray(models) && models.some(
      m => !!m && typeof m === 'object' && (m as Raw).method === 'counted_ammunition_mass');
  });
  const [selected, setSelected] = useState<string>(batteryIds[0] ?? '');
  const batteryId = batteryIds.includes(selected) ? selected : (batteryIds[0] ?? '');
  const battery = batteryIds.length > 0 ? (weapons[batteryId] as GunBattery | null) : null;
  const agg = pickGunsAggregate(runs, batteryId);
  const hasAmmo = findAmmoModel(battery) !== null;
  const projectile = readProjectile(battery);

  function emit(next: GunBattery) {
    onPatchBattery(batteryId, next);
  }
  function setTopCount(key: string, raw: string) {
    if (!battery) return;
    const value = raw.trim() === '' ? null : Number(raw);
    emit({ ...battery, [key]: Number.isFinite(value) ? value : null });
  }
  function updateProjectile(value: number | null, patch: { source?: string | null; estimate?: boolean | null }) {
    const found = findAmmoModel(battery);
    if (!found || !battery) return;
    const models = (battery.mass_models as GunBattery[]).map(m => ({ ...m }));
    const model = { ...models[found.index] };
    model.inputs = { ...(model.inputs as Raw ?? {}), projectile_mass_kg: value };
    const prov = { ...(model.input_provenance as Raw ?? {}) };
    const pm = { ...(prov.projectile_mass_kg as Raw ?? {}) };
    if (patch.source !== undefined) pm.source = patch.source;
    if (patch.estimate !== undefined) pm.estimate = patch.estimate;
    prov.projectile_mass_kg = pm;
    model.input_provenance = prov;
    models[found.index] = model;
    emit({ ...battery, mass_models: models });
  }

  if (batteryIds.length === 0) {
    return <div className="deck-empty"><p>项目尚未声明任何武器炮组（systems.weapons 为空）。可在“高级：原始契约字段”中粘贴。</p></div>;
  }

  return <div className="guns-editor">
    <div className="deck-group">
      <div className="deck-group-title"><h3>炮组</h3>
        <label>选择炮组<select aria-label="选择炮组" value={batteryId} onChange={e => setSelected(e.target.value)}>
          {batteryIds.map(id => <option key={id} value={id}>{id}</option>)}
        </select></label>
      </div>
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>声明输入</h3></div>
      <div className="deck-row">
        <label>装舰炮数<input type="number" step="1" min="0" aria-label={`${batteryId} 装舰炮数`} value={numeric(battery?.installed_guns) ?? ''} onChange={e => setTopCount('installed_guns', e.target.value)} placeholder="未知" /></label>
        <label>单舷炮数<input type="number" step="1" min="0" aria-label={`${batteryId} 单舷炮数`} value={numeric(battery?.broadside_guns) ?? ''} onChange={e => setTopCount('broadside_guns', e.target.value)} placeholder="未知" /></label>
        <label>每炮携弹数<input type="number" step="1" min="0" aria-label={`${batteryId} 每炮携弹数`} value={numeric(battery?.rounds_per_gun) ?? ''} onChange={e => setTopCount('rounds_per_gun', e.target.value)} placeholder="未知" /></label>
      </div>
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>单发弹丸质量</h3></div>
      {hasAmmo ? (
        <div className="deck-row">
          <label>单发弹重 · kg<input type="number" step="any" aria-label={`${batteryId} 单发弹重`} value={projectile.value ?? ''} onChange={e => updateProjectile(e.target.value.trim() === '' ? null : Number(e.target.value), {})} placeholder="未知" /></label>
          <label>来源<input type="text" aria-label={`${batteryId} 单发弹重来源`} value={projectile.source ?? ''} onChange={e => updateProjectile(projectile.value, { source: e.target.value })} placeholder="来源" /></label>
          <label>估算<EstimateCheckbox value={projectile.estimate} onChange={next => updateProjectile(projectile.value, { estimate: next })} /></label>
        </div>
      ) : (
        <p className="section-intro">该炮组没有 counted_ammunition_mass 模型，因此没有单发弹丸质量字段；单舷齐射弹重保持未知（不在此反推）。</p>
      )}
    </div>

    <div className="section-heading"><h2>聚合结果</h2><span>取自最近一次运行（不在此处复算）</span></div>
    {agg ? (
      <>
        <div className="metric-grid">
          <FactField
            label="单发弹重"
            value={numeric(agg.shell_mass_kg?.value)}
            unit="kg"
            status={agg.shell_mass_kg?.value == null ? 'unknown' : agg.shell_mass_kg?.estimate ? 'estimate' : 'known'}
            source={typeof agg.shell_mass_kg?.source === 'string' ? agg.shell_mass_kg!.source : null}
          />
          <FactField
            label="单舷齐射弹重"
            value={numeric(agg.broadside_mass_kg)}
            unit="kg"
            status={agg.broadside_mass_kg == null ? 'unknown' : 'known'}
          />
          <FactField
            label="每炮携弹壳重"
            value={numeric(agg.per_gun_shell_kg)}
            unit="kg"
            status={agg.per_gun_shell_kg == null ? 'unknown' : 'known'}
          />
          <FactField
            label="全舰弹药携带"
            value={numeric(agg.ship_wide_ammunition_t)}
            unit="t"
            status={agg.ship_wide_ammunition_t == null ? 'unknown' : 'known'}
          />
        </div>
        {Array.isArray(agg.diagnostics) && agg.diagnostics.length > 0 && (
          <ul className="diagnostics-list">
            {agg.diagnostics.map((d, i) => <li key={i}><code>{d.code ?? '诊断'}</code>{d.message ? `：${d.message}` : ''}</li>)}
          </ul>
        )}
      </>
    ) : (
      <p className="section-intro">保存并运行后显示聚合值</p>
    )}
  </div>;
}

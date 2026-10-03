import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { Metric, ResultSection, RowResults, StudyResult } from './FormResults';
import { inputNumber, ledgerItems, number, object, rows, sourceText, stageData, stringList, unassignedIds, type Raw } from './formModel';

export function ArmourEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
  const systems = object(project.systems); const armour = object(systems.armour); const fixed = object(armour.fixed);
  const declared = rows(fixed.page_rows); const ledger = ledgerItems(project);
  const data = stageData(run, 'systems'); const view = object(object(data.page_rows)['armour.fixed']);
  function emit(next: Raw) { onChange({ ...project, systems: { ...systems, armour: { ...armour, fixed: { weight_item_ids: [], ...next } } } }); }
  function patchRow(index: number, patch: Raw) {
    const nextRows = declared.map((r, i) => i === index ? { ...r, ...patch } : r);
    // The leaf binding is the union of the declared rows; unbound ids stay so a
    // pre-existing binding is never silently dropped by an unrelated edit.
    const bound = new Set(nextRows.flatMap(r => stringList(r.weight_item_ids)));
    const ids = [...new Set([...bound, ...unassignedIds(stringList(fixed.weight_item_ids), [...bound])])];
    emit({ ...fixed, weight_item_ids: ids, page_rows: nextRows });
  }
  const coverage = object(fixed.deck_coverage); const belt = object(fixed.minimum_main_belt);
  function patchBelt(patch: Raw) { emit({ ...fixed, minimum_main_belt: { protected_compartment_ids: [], aft_margin_m: 0, fore_margin_m: 0,
    inventory_complete: false, source: null, estimate: true, ...belt, ...patch } }); }
  const weapons = object(systems.weapons);
  return <div className="form-stack"><p className="section-intro">厚度、跨度和类型是声明输入；质量取自账本。修改这些声明后，请在重量页核对对应质量和质量模型。</p>
    {declared.length === 0 && <p>尚无装甲行。可添加声明行并绑定已有账本条目。</p>}
    {declared.map((row, index) => <details className="form-card" open key={String(row.row ?? index)}><summary>{String(row.label ?? row.row)}</summary><div className="form-card-body">
      <div className="form-grid"><label className="field-label">厚度 · mm<input aria-label={`${row.row} 厚度 · mm`} type="number" placeholder="未知" step="any" value={number(row.thickness_mm) ?? ''} onChange={e => patchRow(index, { thickness_mm: inputNumber(e.target.value) })} /></label>
        {(['aft_m', 'fore_m'] as const).map((key, i) => <label className="field-label" key={key}>{i ? '艏端' : '艉端'} · m<input aria-label={`${row.row} ${i ? '艏端' : '艉端'} · m`} type="number" step="any" placeholder="未知" value={number(object(row.extents_m)[key]) ?? ''}
          onChange={e => patchRow(index, { extents_m: { ...object(row.extents_m), [key]: inputNumber(e.target.value) } })} /></label>)}
        <label className="field-label">高度 · m<input aria-label={`${row.row} 高度 · m`} type="number" step="any" placeholder="未知" value={number(object(row.typed).height_m) ?? ''} onChange={e => patchRow(index, { typed: { ...object(row.typed), height_m: inputNumber(e.target.value) } })} /></label>
        <label className="field-label">类型<input aria-label={`${row.row} 类型`} placeholder="未知" value={String(object(row.typed).construction_type ?? '')} onChange={e => patchRow(index, { typed: { ...object(row.typed), construction_type: e.target.value.trim() ? e.target.value : null } })} /></label>
        <label className="field-label">分组<input aria-label={`${row.row} 分组`} value={String(row.group ?? '')} onChange={e => patchRow(index, { group: e.target.value || 'unclassified' })} /></label>
        <label className="field-label">来源<input aria-label={`${row.row} 来源`} value={sourceText(row.source)} onChange={e => patchRow(index, { source: e.target.value || null })} /></label>
        <EstimateInput label={`${row.row} 估算状态`} value={row.estimate} onChange={estimate => patchRow(index, { estimate })} />
      </div><IdPicker label={`${row.row} 账本绑定`} selected={row.weight_item_ids} options={ledger} onChange={ids => patchRow(index, { weight_item_ids: ids })} />
      <button className="text-button" type="button" onClick={() => { const kept = declared.filter((_, i) => i !== index);
        // Drop the removed row's bindings from the leaf too: an id no row
        // declares would otherwise linger and be reported as uncovered mass.
        const dropped = new Set(stringList(declared[index].weight_item_ids));
        const ids = [...new Set([...kept.flatMap(r => stringList(r.weight_item_ids)),
          ...stringList(fixed.weight_item_ids).filter(id => !dropped.has(id))])];
        // `page_rows` must be a nonempty array (project_extensions._page_rows),
        // so an empty declaration omits the key instead of writing [].
        const next: Raw = { ...fixed, weight_item_ids: ids };
        if (kept.length === 0) delete next.page_rows; else next.page_rows = kept;
        emit(next); }}>移除声明行</button>
    </div></details>)}
    <button className="button button--secondary" type="button" onClick={() => { let n = 1; while (declared.some(r => r.row === `armour_${n}`)) n++;
      emit({ ...fixed, page_rows: [...declared, { row: `armour_${n}`, label: `Armour ${n}`, group: 'unclassified', weight_item_ids: [], source: null, estimate: null }] }); }}>添加装甲行</button>
    <IdPicker label="固定装甲系统账本条目" selected={fixed.weight_item_ids} options={ledger} onChange={ids => emit({ ...fixed, weight_item_ids: ids })} />
    <div className="form-card"><h3>装甲甲板平面覆盖率</h3><p>受保护平面面积与参考平面面积需要各自来源；它们与装甲展开面积分开记录。</p>
      {(['covered_plan_area_m2', 'reference_plan_area_m2'] as const).map((key, i) => <FactInput key={key} label={i ? '参考平面面积 · m²' : '受保护平面面积 · m²'} value={coverage[key]} onChange={v => emit({ ...fixed, deck_coverage: { ...coverage, [key]: v } })} />)}
    </div><details className="form-card"><summary>主装甲带连续覆盖长度 · 工程估算</summary><div className="form-card-body"><p>使用已声明舱室的几何范围及端部余量。勾选完整清单表示你已核对全部关键舱段；结果保留工程估算标记。</p>
      <IdPicker label="主带保护舱室" selected={belt.protected_compartment_ids} options={rows(project.compartments).map(c => ({ id: String(c.id), label: String(c.label ?? c.id) }))} onChange={ids => patchBelt({ protected_compartment_ids: ids })} />
      <div className="form-grid">{(['aft_margin_m', 'fore_margin_m'] as const).map((key, i) => <label className="field-label" key={key}>{i ? '艏' : '艉'}端余量 · m<input aria-label={`主带 ${key}`} type="number" step="any" value={number(belt[key]) ?? ''} onChange={e => patchBelt({ [key]: inputNumber(e.target.value) })} /></label>)}
      <label className="field-label">研究来源<input aria-label="主带研究来源" value={sourceText(belt.source)} onChange={e => patchBelt({ source: e.target.value || null })} /></label></div>
      <label><input type="checkbox" checked={belt.inventory_complete === true} onChange={e => patchBelt({ inventory_complete: e.target.checked })} />关键舱段清单已完整核对</label>
      {fixed.minimum_main_belt != null && <button className="text-button" onClick={() => { const next = { ...fixed }; delete next.minimum_main_belt; emit(next); }}>取消主带研究</button>}
    </div></details>
    {Object.entries(weapons).filter(([, v]) => rows(object(v).page_rows).some(r => r.row === 'mounts')).map(([id, v]) => {
      const leaf = object(v); const component = object(leaf.rotating_armour_component);
      const mounts = rows(leaf.page_rows).filter(r => r.row === 'mounts').flatMap(r => Array.isArray(r.weight_item_ids) ? r.weight_item_ids as string[] : []);
      function patch(p: Raw) { onChange({ ...project, systems: { ...systems, weapons: { ...weapons, [id]: { ...leaf, rotating_armour_component: { ...component, ...p } } } } }); }
      return <details className="form-card" key={id}><summary>{id} 炮座内旋转装甲拆分</summary><div className="form-card-body"><p>仅拆分已有炮座质量，不再加入全舰重量。</p>
        <label className="field-label">炮座条目<select aria-label={`${id} 旋转装甲炮座条目`} value={String(component.mount_weight_item_id ?? '')} onChange={e => patch({ mount_weight_item_id: e.target.value || null })}><option value="">选择已绑定炮座</option>{mounts.map(m => <option key={m}>{m}</option>)}</select></label>
        <FactInput label={`${id} 旋转装甲质量 · t`} value={{ value: component.mass_t ?? null, source: component.source ?? null, estimate: component.estimate ?? null }}
          onChange={f => patch({ mass_t: f.value, source: f.source, estimate: f.estimate })} />
        {leaf.rotating_armour_component != null && <button className="text-button" onClick={() => { const next = { ...leaf }; delete next.rotating_armour_component;
          onChange({ ...project, systems: { ...systems, weapons: { ...weapons, [id]: next } } }); }}>取消拆分研究</button>}
      </div></details>;
    })}
    <ResultSection available={!!run}><div className="metric-grid"><Metric label="装甲行质量合计" value={object(view.values).declared_rows_total_t} unit="t" /></div><RowResults view={view} />
      <StudyResult label="甲板覆盖率" data={data.deck_coverage} metrics={[["coverage_pct", "平面覆盖率", "%"]]} />
      <StudyResult label="主装甲带工程估算" data={object(data.minimum_main_belt)}
        metrics={[["length_m", "连续覆盖长度", "m"]]} />
      {Object.keys(weapons).map(id => <StudyResult key={id} label={`${id} 旋转装甲拆分`} data={object(object(data.page_rows)[`weapons.${id}`]).rotating_armour_component}
        metrics={[["rotating_armour_mass_t", "旋转装甲", "t"], ["other_mount_mass_t", "炮座其余部分", "t"]]} />)}
    </ResultSection>
  </div>;
}

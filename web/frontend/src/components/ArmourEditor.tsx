import type { ProjectDocument, RunView } from '../types';
import { EstimateInput, FactInput, IdPicker } from './FactInput';
import { QuantityField } from './QuantityField';
import { Metric, ResultSection, RowResults, StudyResult } from './FormResults';
import { inputNumber, ledgerItems, number, object, rows, sourceText, stageData, stringList, unassignedIds, type Raw } from './formModel';
import { useWorkspaceCopy } from '../i18n/workspace';

export function ArmourEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
  const w = useWorkspaceCopy();
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
  return <div className="form-stack"><p className="section-intro">{w('armour.intro')}</p>
    {declared.length === 0 && <p>{w('armour.empty')}</p>}
    {declared.map((row, index) => <details className="form-card" open key={String(row.row ?? index)}><summary>{String(row.label ?? row.row)}</summary><div className="form-card-body">
      {/* Plate thickness is stored in millimetres: the reader sees the preferred
          length unit and typing converts back to the stored millimetres. */}
      <div className="form-grid"><QuantityField label={w('armour.thickness')} aria-label={w('armour.thicknessAria', { row: String(row.row) })} value={number(row.thickness_mm)} dimension="length" storedUnit="mm" kind="nonnegative"
          onChange={value => patchRow(index, { thickness_mm: value })} />
        {(['aft_m', 'fore_m'] as const).map((key, i) => <QuantityField key={key} label={i ? w('armour.fore') : w('armour.aft')} aria-label={w('armour.endAria', { row: String(row.row), end: i ? w('armour.fore') : w('armour.aft') })}
          value={number(object(row.extents_m)[key])} dimension="length" storedUnit="m"
          onChange={value => patchRow(index, { extents_m: { ...object(row.extents_m), [key]: value } })} />)}
        <QuantityField label={w('armour.height')} aria-label={w('armour.heightAria', { row: String(row.row) })} value={number(object(row.typed).height_m)} dimension="length" storedUnit="m" kind="positive"
          onChange={value => patchRow(index, { typed: { ...object(row.typed), height_m: value } })} />
        <label className="field-label">{w('armour.type')}<input aria-label={w('armour.typeAria', { row: String(row.row) })} placeholder={w('units.unknown')} value={String(object(row.typed).construction_type ?? '')} onChange={e => patchRow(index, { typed: { ...object(row.typed), construction_type: e.target.value.trim() ? e.target.value : null } })} /></label>
        <label className="field-label">{w('armour.group')}<input aria-label={w('armour.groupAria', { row: String(row.row) })} value={String(row.group ?? '')} onChange={e => patchRow(index, { group: e.target.value || 'unclassified' })} /></label>
        <label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label: String(row.row) })} value={sourceText(row.source)} onChange={e => patchRow(index, { source: e.target.value || null })} /></label>
        <EstimateInput label={w('fact.estimateAria', { label: String(row.row) })} value={row.estimate} onChange={estimate => patchRow(index, { estimate })} />
      </div><IdPicker label={w('fact.bindingAria', { label: String(row.row) })} selected={row.weight_item_ids} options={ledger} onChange={ids => patchRow(index, { weight_item_ids: ids })} />
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
        emit(next); }}>{w('armour.removeRow')}</button>
    </div></details>)}
    <button className="button button--secondary" type="button" onClick={() => { let n = 1; while (declared.some(r => r.row === `armour_${n}`)) n++;
      // `Armour ${n}` is the label written *into the project document*, so it is
      // a stored row name rather than a translatable string on this page.
      emit({ ...fixed, page_rows: [...declared, { row: `armour_${n}`, label: `Armour ${n}`, group: 'unclassified', weight_item_ids: [], source: null, estimate: null }] }); }}>{w('armour.addRow')}</button>
    <IdPicker label={w('armour.leafBinding')} selected={fixed.weight_item_ids} options={ledger} onChange={ids => emit({ ...fixed, weight_item_ids: ids })} />
    <div className="form-card"><h3>{w('armour.coverage.title')}</h3><p>{w('armour.coverage.note')}</p>
      {(['covered_plan_area_m2', 'reference_plan_area_m2'] as const).map((key, i) => <FactInput key={key} label={i ? w('armour.coverage.reference') : w('armour.coverage.protected')} dimension="area" storedUnit="m"
          value={coverage[key]} onChange={v => emit({ ...fixed, deck_coverage: { ...coverage, [key]: v } })} />)}
    </div><details className="form-card"><summary>{w('armour.belt.title')}</summary><div className="form-card-body"><p>{w('armour.belt.note')}</p>
      <IdPicker label={w('armour.belt.protected')} selected={belt.protected_compartment_ids} options={rows(project.compartments).map(c => ({ id: String(c.id), label: String(c.label ?? c.id) }))} onChange={ids => patchBelt({ protected_compartment_ids: ids })} />
      <div className="form-grid">{(['aft_margin_m', 'fore_margin_m'] as const).map((key, i) => <QuantityField key={key} label={w('armour.belt.margin', { end: w(i ? 'armour.belt.fore' : 'armour.belt.aft') })}
          aria-label={w('armour.belt.marginAria', { field: key })} value={number(belt[key])} dimension="length" storedUnit="m" kind="nonnegative"
          onChange={value => patchBelt({ [key]: value })} />)}
      <label className="field-label">{w('armour.belt.source')}<input aria-label={w('armour.belt.sourceAria')} value={sourceText(belt.source)} onChange={e => patchBelt({ source: e.target.value || null })} /></label></div>
      <label><input type="checkbox" checked={belt.inventory_complete === true} onChange={e => patchBelt({ inventory_complete: e.target.checked })} />{w('armour.belt.inventory')}</label>
      {fixed.minimum_main_belt != null && <button className="text-button" onClick={() => { const next = { ...fixed }; delete next.minimum_main_belt; emit(next); }}>{w('armour.belt.cancel')}</button>}
    </div></details>
    {Object.entries(weapons).filter(([, v]) => rows(object(v).page_rows).some(r => r.row === 'mounts')).map(([id, v]) => {
      const leaf = object(v); const component = object(leaf.rotating_armour_component);
      const mounts = rows(leaf.page_rows).filter(r => r.row === 'mounts').flatMap(r => Array.isArray(r.weight_item_ids) ? r.weight_item_ids as string[] : []);
      function patch(p: Raw) { onChange({ ...project, systems: { ...systems, weapons: { ...weapons, [id]: { ...leaf, rotating_armour_component: { ...component, ...p } } } } }); }
      return <details className="form-card" key={id}><summary>{w('armour.rotating.title', { id })}</summary><div className="form-card-body"><p>{w('armour.rotating.note')}</p>
        <label className="field-label">{w('armour.rotating.entry')}<select aria-label={w('armour.rotating.entryAria', { id })} value={String(component.mount_weight_item_id ?? '')} onChange={e => patch({ mount_weight_item_id: e.target.value || null })}><option value="">{w('armour.rotating.pick')}</option>{mounts.map(m => <option key={m}>{m}</option>)}</select></label>
        <FactInput label={w('armour.rotating.mass', { id })} dimension="mass" storedUnit="t" value={{ value: component.mass_t ?? null, source: component.source ?? null, estimate: component.estimate ?? null }}
          onChange={f => patch({ mass_t: f.value, source: f.source, estimate: f.estimate })} />
        {leaf.rotating_armour_component != null && <button className="text-button" onClick={() => { const next = { ...leaf }; delete next.rotating_armour_component;
          onChange({ ...project, systems: { ...systems, weapons: { ...weapons, [id]: next } } }); }}>{w('armour.rotating.cancel')}</button>}
      </div></details>;
    })}
    <ResultSection available={!!run}><div className="metric-grid"><Metric label={w('armour.result.rowsTotal')} value={object(view.values).declared_rows_total_t} unit="t" /></div><RowResults view={view} />
      <StudyResult label={w('armour.result.coverage')} data={data.deck_coverage} metrics={[["coverage_pct", w('armour.result.coveragePct'), "%"]]} />
      <StudyResult label={w('armour.result.belt')} data={object(data.minimum_main_belt)}
        metrics={[["length_m", w('armour.result.beltLength'), "m", "length"]]} />
      {Object.keys(weapons).map(id => <StudyResult key={id} label={w('armour.rotating.short', { id })} data={object(object(data.page_rows)[`weapons.${id}`]).rotating_armour_component}
        metrics={[["rotating_armour_mass_t", w('armour.result.rotating'), "t", "mass"], ["other_mount_mass_t", w('armour.result.otherMount'), "t", "mass"]]} />)}
    </ResultSection>
  </div>;
}
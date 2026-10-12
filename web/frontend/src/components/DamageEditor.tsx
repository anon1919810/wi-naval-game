import { useCopyMessage } from '../i18n/useCopyMessage';
import { useState } from 'react';

import type { ProjectDocument, RunView } from '../types';
import { EstimateInput } from './FactInput';
import { Diagnostics, ResultSection } from './FormResults';
import { number, numericProblemCode, type NumericProblemCode, numericValue, object, rows, stageData, uniqueId, type Raw } from './formModel';
import {
  APERTURE_HEIGHT, CONNECTION_FIELDS, connections, environmentDensity, EQUILIBRIUM_RHO_T_M3, newConnection, newOpening,
  newScenario, newTank, sea, TANK_FIELDS, tanks, tankFromCompartment, withApertureHeight,
  type FieldSpec, type FloodingRequest,
} from './floodingModel';
import { QuantityField, QuantityListField } from './QuantityField';
import { FloodingResults } from './FloodingResults';
import { useWorkspaceCopy } from '../i18n/workspace';

// Saved flooding scenario drafts plus the project's own compartment geometry.
//
// A scenario is research input, not a second weight ledger: it holds tank
// geometry, declared initial liquid, connections and openings for one damage
// case. Nothing here solves anything, copies no water into the ledger, and
// borrows no geometry that the project or the user did not declare.

type TriState = 'unknown' | 'yes' | 'no';

function tri(value: unknown): TriState { return typeof value === 'boolean' ? (value ? 'yes' : 'no') : 'unknown'; }
function triValue(state: TriState): boolean | null { return state === 'unknown' ? null : state === 'yes'; }

function metadataFields(w: ReturnType<typeof useWorkspaceCopy>, prefix: string, entry: Raw, onPatch: (patch: Raw) => void) {
  return <div className="form-grid">
    <label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label: prefix })} placeholder={w('fact.sourcePlaceholder')}
      value={typeof entry.source === 'string' ? entry.source : ''}
      onChange={event => onPatch({ source: event.target.value.trim() === '' ? null : event.target.value })} /></label>
    <EstimateInput label={w('fact.estimateAria', { label: prefix })} value={entry.estimate} onChange={estimate => onPatch({ estimate })} />
  </div>;
}

// A convertible quantity is typed in the reader's unit and stored canonically;
// a dimensionless or density entry keeps the plain canonical number input.
function numericField(w: ReturnType<typeof useWorkspaceCopy>, spec: FieldSpec, prefix: string, value: unknown, onChange: (raw: string) => void, problem: NumericProblemCode | null) {
  const label = w(spec.label);
  if (spec.dimension) return <QuantityField key={spec.key} label={label} ariaLabel={`${prefix} ${label}`}
    value={number(value)} dimension={spec.dimension} storedUnit={spec.storedUnit} kind={spec.kind} invalid={Boolean(problem)}
    onChange={next => onChange(next === null ? '' : String(next))} />;
  return <label className="field-label" key={spec.key}>{label}
    <input type="number" step="any" placeholder={w('units.unknown')} aria-label={`${prefix} ${label}`}
      aria-invalid={Boolean(problem)} value={number(value) ?? ''} onChange={event => onChange(event.target.value)} />
    {problem && <span className="field-error" role="alert">{w(problem)}</span>}
  </label>;
}

export function DamageEditor({ project, run, request, onChange, onRequestChange, requestError }: {
  project: ProjectDocument; run: RunView | null; request: FloodingRequest;
  onChange: (project: ProjectDocument) => void; onRequestChange: (request: FloodingRequest) => void;
  requestError: string;
}) {
  const w = useWorkspaceCopy();
  const scenarios = rows(project.flooding_scenarios);
  const compartments = rows(project.compartments);
  const [choice, setChoice] = useState<string | null>(null);
  const [newId, setNewId] = useState('flooding_1');
  const [newTankId, setNewTankId] = useState('tank_1');
  const [newConnectionId, setNewConnectionId] = useState('opening_1');
  const [newOpeningId, setNewOpeningId] = useState('opening_1');
  const [newCompartmentId, setNewCompartmentId] = useState('compartment_1');
  const [problems, setProblems] = useState<Record<string, NumericProblemCode>>({});
  const [copyNote, setCopyNote] = useCopyMessage();
  const selected = scenarios.find(row => String(row.id) === choice) ?? scenarios[0] ?? null;
  const id = selected ? String(selected.id) : '';
  const data = stageData(run, 'flooding');

  function emit(list: Raw[]) { onChange({ ...project, flooding_scenarios: list }); }
  function patch(value: Raw) { if (selected) emit(scenarios.map(row => row === selected ? { ...row, ...value } : row)); }
  function emitCompartments(list: Raw[]) { onChange({ ...project, compartments: list }); }
  function create() {
    const next = uniqueId(newId.trim() || 'flooding_1', scenarios.map(row => row.id));
    setChoice(next);
    setProblems({});
    setCopyNote('');
    emit([...scenarios, newScenario(next)]);
  }

  const scenario = selected ?? {};
  const water = sea(scenario);
  const tankRows = tanks(scenario);
  const connectionRows = connections(scenario);
  const openingRows = rows(scenario.openings);
  const nodeIds = [String(water.id ?? ''), ...tankRows.map(tank => String(tank.id))]
    .filter(value => value.trim() !== '');
  const openingState: TriState = !('openings' in scenario) ? 'unknown'
    : scenario.openings === null ? 'unknown' : openingRows.length === 0 ? 'yes' : 'no';
  const environment = request.rho.trim() === '' ? EQUILIBRIUM_RHO_T_M3 : environmentDensity(request) ?? w('flooding.damage.invalid');
  function compartmentReferences(compartmentId: unknown): string[] {
    const protectedIds = object(object(object(project.systems).armour).fixed).minimum_main_belt;
    const references = Array.isArray(object(protectedIds).protected_compartment_ids)
      && (object(protectedIds).protected_compartment_ids as unknown[]).includes(compartmentId) ? [w('flooding.reference.belt')] : [];
    for (const preset of rows(project.damage_presets)) {
      if (String(compartmentId) in object(preset.initial_water_volumes_m3)) references.push(w('flooding.reference.preset', { id: String(preset.id) }));
    }
    return references;
  }

  function refuse(key: string, kind: FieldSpec['kind'], raw: string): boolean {
    const problem = numericProblemCode(kind, raw);
    setProblems(previous => {
      const next = { ...previous };
      if (problem) next[key] = problem; else delete next[key];
      return next;
    });
    return problem !== null;
  }
  function patchTank(index: number, patchValue: Raw) {
    patch({ tanks: tankRows.map((tank, i) => i === index ? { ...tank, ...patchValue } : tank) });
  }
  // A row replacement, not a merge: removing an optional key (the requested
  // aperture height) must really drop it instead of keeping the previous value.
  function replaceConnection(index: number, row: Raw) {
    patch({ connections: connectionRows.map((edge, i) => i === index ? row : edge) });
  }
  function patchConnection(index: number, patchValue: Raw) {
    replaceConnection(index, { ...connectionRows[index], ...patchValue });
  }
  function tankField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`${id}/tank${index}/${spec.key}`, spec.kind, raw)) return;
    patchTank(index, { [spec.key]: numericValue(raw) });
  }
  function connectionField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`${id}/conn${index}/${spec.key}`, spec.kind, raw)) return;
    patchConnection(index, { [spec.key]: numericValue(raw) });
  }
  function patchOpening(index: number, patchValue: Raw) {
    patch({ openings: openingRows.map((row, i) => i === index ? { ...row, ...patchValue } : row) });
  }
  function replaceOpening(index: number, row: Raw) {
    patch({ openings: openingRows.map((entry, i) => i === index ? row : entry) });
  }
  function compartmentField(index: number, spec: FieldSpec, raw: string) {
    if (refuse(`compartment${index}/${spec.key}`, spec.kind, raw)) return;
    emitCompartments(compartments.map((row, i) => i === index ? { ...row, [spec.key]: numericValue(raw) } : row));
  }
  // Removing a referenced tank would leave a dangling edge, so the removal states
  // the connections it takes with it instead of leaving a broken reference.
  function removeTank(index: number) {
    const victim = String(tankRows[index].id);
    const referencing = connectionRows.filter(edge => edge.from === victim || edge.to === victim).map(edge => String(edge.id));
    patch({ tanks: tankRows.filter((_, i) => i !== index),
      connections: referencing.length ? connectionRows.filter(edge => !referencing.includes(String(edge.id))) : connectionRows });
    setCopyNote(w => referencing.length ? w('flooding.tank.removed', { id: victim, connections: referencing.join(w('form.listSeparator')) }) : '');
  }
  function copyCompartments() {
    const seaDensity = number(water.fluid_density_t_m3);
    const taken = new Set(nodeIds);
    const copies: Raw[] = [];
    const skipped: Array<{key:'flooding.copy.missingGeometry'|'flooding.copy.nameClash'; id:string}> = [];
    for (const compartment of compartments) {
      const copy = tankFromCompartment(compartment, seaDensity);
      if (!copy) { skipped.push({key:'flooding.copy.missingGeometry', id:String(compartment.id)}); continue; }
      if (taken.has(String(copy.id))) { skipped.push({key:'flooding.copy.nameClash', id:String(copy.id)}); continue; }
      taken.add(String(copy.id));
      copies.push(copy);
    }
    if (copies.length === 0) {
      setCopyNote(w => w('flooding.copy.none', { reasons: skipped.map(item => w(item.key, {id:item.id})).join(w('form.listSeparator')) || w('flooding.copy.noCompartments') }));
      return;
    }
    patch({ tanks: [...tankRows, ...copies] });
    setCopyNote(w => w('flooding.copy.done', {
      list: copies.map(tank => String(tank.id)).join(w('form.listSeparator')),
      skipped: skipped.length ? w('flooding.copy.skipped', { list: skipped.map(item => w(item.key, {id:item.id})).join(w('form.listSeparator')) }) : '',
    }));
  }

  return <div className="damage-editor form-stack">
    <div className="form-card"><h3>{w('editor.group.damage')}</h3>
      <p>{w('flooding.damage.intro')}</p>
      {scenarios.length === 0 && <p className="form-hint">{w('flooding.damage.empty')}</p>}
      <div className="form-grid">
        <label className="field-label">{w('flooding.damage.current')}<select aria-label={w('flooding.damage.currentAria')} value={id} onChange={event => setChoice(event.target.value)}>
          {scenarios.length === 0 && <option value="">{w('flooding.damage.none')}</option>}
          {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)}</option>)}
        </select></label>
        <label className="field-label">{w('flooding.damage.newId')}<input aria-label={w('flooding.damage.newIdAria')} value={newId} onChange={event => setNewId(event.target.value)} /></label>
        <button className="button button--secondary" type="button" onClick={create}>{w('flooding.damage.add')}</button>
      </div>
    </div>

    {selected && <>
      <div className="form-card"><h3>{w('flooding.damage.durationTitle', { id })}</h3>
        <div className="form-grid">
          <label className="field-label">{w('flooding.damage.scenarioName')}<input aria-label={w('flooding.damage.scenarioNameAria', { id })} value={typeof scenario.label === 'string' ? scenario.label : ''}
            onChange={event => patch({ label: event.target.value })} /></label>
          {numericField(w, { key: 'duration_s', label: 'flooding.damage.duration', kind: 'nonnegative' }, id, scenario.duration_s,
          raw => { if (!refuse(`${id}/duration_s`, 'nonnegative', raw)) patch({ duration_s: numericValue(raw) }); },
          problems[`${id}/duration_s`] ?? null)}
          {numericField(w, { key: 'time_step_s', label: 'flooding.damage.timeStep', kind: 'positive' }, id, scenario.time_step_s,
          raw => { if (!refuse(`${id}/time_step_s`, 'positive', raw)) patch({ time_step_s: numericValue(raw) }); },
          problems[`${id}/time_step_s`] ?? null)}
        </div>
        {metadataFields(w, `${id} ${w('flooding.damage.scenarioName')}`, scenario, patch)}
        <p className="form-hint">{w('flooding.damage.durationHint')}</p>
      </div>

      <div className="form-card"><h3>{w('flooding.sea.title')}</h3>
        <div className="form-grid">
          <label className="field-label">{w('flooding.sea.id')}<input aria-label={w('flooding.sea.idAria', { id })} value={water.id == null ? '' : String(water.id)}
            onChange={event => patch({ sea: { ...water, id: event.target.value } })} /></label>
          <label className="field-label">{w('flooding.sea.density')}<input type="number" step="any" placeholder={w('units.unknown')} aria-label={w('flooding.sea.densityAria', { id })}
            value={number(water.fluid_density_t_m3) ?? ''}
            onChange={event => patch({ sea: { ...water, fluid_density_t_m3: numericValue(event.target.value) } })} /></label>
        </div>
        {metadataFields(w, `${id} ${w('flooding.sea.title')}`, water, patchValue => patch({ sea: { ...water, ...patchValue } }))}
        <p className="form-hint">{w('flooding.sea.note', { value: environment })}</p>
      </div>

      <div className="form-card"><h3>{w('flooding.tanks.title')}</h3>
        <p>{w('flooding.tanks.intro')}</p>
        {tankRows.length === 0 && <p className="form-hint">{w('flooding.tanks.empty')}</p>}
        <div className="form-grid">
          <label className="field-label">{w('flooding.tanks.newId')}<input aria-label={w('flooding.tanks.newIdAria')} value={newTankId} onChange={event => setNewTankId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => patch({ tanks: [...tankRows, newTank(uniqueId(newTankId.trim() || 'tank_1', nodeIds))] })}>{w('flooding.tanks.add')}</button>
          <button className="button button--secondary" type="button" onClick={copyCompartments}>{w('flooding.tanks.copy')}</button>
        </div>
        {copyNote && <p className="form-hint" role="status">{copyNote}</p>}
        {tankRows.map((tank, index) => {
          const references = connectionRows.filter(edge => edge.from === tank.id || edge.to === tank.id).map(edge => String(edge.id));
          return <details className="form-card" open key={String(tank.id ?? index)}>
            <summary>{w('flooding.problem.tankLabel', { id: String(tank.id) })}</summary><div className="form-card-body">
              <div className="form-grid">
                {TANK_FIELDS.map(spec => numericField(w, spec, `${id} ${w('flooding.problem.tankLabel', { id: String(tank.id) })}`, tank[spec.key],
                  raw => tankField(index, spec, raw), problems[`${id}/tank${index}/${spec.key}`] ?? null))}
                <label className="field-label">{w('flooding.freeSurface.label')}<select aria-label={w('flooding.freeSurface.aria', { id, tank: String(tank.id) })} value={tri(tank.free_surface)}
                  onChange={event => patchTank(index, { free_surface: triValue(event.target.value as TriState) })}>
                  <option value="unknown">{w('form.triUnknown')}</option><option value="yes">{w('flooding.freeSurface.yes')}</option><option value="no">{w('flooding.freeSurface.no')}</option>
                </select></label>
                <label className="field-label">{w('flooding.tankDensity')}<input type="number" step="any" placeholder={w('units.unknown')}
                  aria-label={w('flooding.tankDensityAria', { id, tank: String(tank.id) })} value={number(tank.fluid_density_t_m3) ?? ''}
                  onChange={event => patchTank(index, { fluid_density_t_m3: numericValue(event.target.value) })} /></label>
              </div>
              {metadataFields(w, `${id} ${w('flooding.problem.tankLabel', { id: String(tank.id) })}`, tank, patchValue => patchTank(index, patchValue))}
              {references.length > 0 && <p className="form-hint">{w('flooding.tank.referenced', { connections: references.join(w('form.listSeparator')) })}</p>}
              <button className="text-button" type="button" onClick={() => removeTank(index)}>
                {w('flooding.tank.remove', { id: String(tank.id), note: references.length ? w('flooding.tank.removeNote', { count: references.length }) : '' })}</button>
            </div></details>;
        })}
        <p className="form-hint">{w('flooding.tanks.doubleCountNote')}</p>
      </div>

      <div className="form-card"><h3>{w('flooding.connections.title')}</h3>
        <p>{w('flooding.connections.intro')}</p>
        <div className="form-grid">
          <label className="field-label">{w('flooding.connections.newId')}<input aria-label={w('flooding.connections.newIdAria')} value={newConnectionId} onChange={event => setNewConnectionId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => {
              const nextId = uniqueId(newConnectionId.trim() || 'opening_1', connectionRows.map(edge => edge.id));
              setNewConnectionId('opening_1');
              patch({ connections: [...connectionRows, { ...newConnection(nextId), from: nodeIds[0] ?? '', to: nodeIds[1] ?? '' }] });
            }}>{w('flooding.connections.add')}</button>
        </div>
        {connectionRows.map((edge, index) => <details className="form-card" open key={String(edge.id ?? index)}>
          <summary>{w('flooding.problem.connectionLabel', { id: String(edge.id) })}</summary><div className="form-card-body">
            <div className="form-grid">
              {(['from', 'to'] as const).map((side, position) => {
                const sideLabel = w(position ? 'flooding.connections.to' : 'flooding.connections.from');
                return <label className="field-label" key={side}>{sideLabel}
                <select aria-label={w('flooding.connections.sideAria', { id, edge: String(edge.id), side: sideLabel })} value={String(edge[side] ?? '')}
                  onChange={event => patchConnection(index, { [side]: event.target.value })}>
                  <option value="">{w('flooding.connections.unselected')}</option>
                  {nodeIds.map(node => <option key={node} value={node}>{node === String(water.id) ? w('flooding.connections.seaNode', { node }) : node}</option>)}
                </select></label>; })}
              {CONNECTION_FIELDS.filter(spec => spec.key !== 'aperture_height_m').map(spec => numericField(w, spec, `${id} ${w('flooding.problem.connectionLabel', { id: String(edge.id) })}`, edge[spec.key],
                raw => connectionField(index, spec, raw), problems[`${id}/conn${index}/${spec.key}`] ?? null))}
              <label className="field-label">{w('flooding.tankDensity')}<input type="number" step="any" placeholder={w('units.unknown')}
                aria-label={w('flooding.connectionDensityAria', { id, edge: String(edge.id) })} value={number(edge.fluid_density_t_m3) ?? ''}
                onChange={event => patchConnection(index, { fluid_density_t_m3: numericValue(event.target.value) })} /></label>
              <label className="field-label">{w('flooding.connections.openState')}<select aria-label={w('flooding.connections.openStateAria', { id, edge: String(edge.id) })} value={tri(edge.open)}
                onChange={event => patchConnection(index, { open: triValue(event.target.value as TriState) })}>
                <option value="unknown">{w('form.triUnknown')}</option><option value="yes">{w('flooding.open.yes')}</option><option value="no">{w('flooding.open.no')}</option>
              </select></label>
            </div>
            {/* The finite-aperture check is optional: the key exists only when it
                is requested, so a default null can never block a complete edge. */}
            <label><input type="checkbox" aria-label={w('flooding.connections.apertureAria', { id, edge: String(edge.id) })}
              checked={'aperture_height_m' in edge}
              onChange={event => replaceConnection(index, withApertureHeight(edge, event.target.checked))} />{w('flooding.connections.aperture')}</label>
            {'aperture_height_m' in edge && numericField(w, APERTURE_HEIGHT, `${id} ${w('flooding.problem.connectionLabel', { id: String(edge.id) })}`, edge.aperture_height_m,
              raw => connectionField(index, APERTURE_HEIGHT, raw), problems[`${id}/conn${index}/aperture_height_m`] ?? null)}
            {metadataFields(w, `${id} ${w('flooding.problem.connectionLabel', { id: String(edge.id) })}`, edge, patchValue => patchConnection(index, patchValue))}
            <button className="text-button" type="button"
              onClick={() => { patch({ connections: connectionRows.filter((_, i) => i !== index) }); setCopyNote(''); }}>{w('flooding.connections.remove', { id: String(edge.id) })}</button>
          </div></details>)}
      </div>

      <div className="form-card"><h3>{w('flooding.openings.title')}</h3>
        <p>{w('flooding.openings.intro')}</p>
        <label className="field-label">{w('flooding.openings.state')}<select aria-label={w('flooding.openings.stateAria', { id })} value={openingState}
          onChange={event => {
            const state = event.target.value as TriState;
            if (state === 'unknown') { const next: Raw = { ...scenario }; delete next.openings; emit(scenarios.map(row => row === selected ? next : row)); }
            else if (state === 'yes') patch({ openings: [] });
            else patch({ openings: [newOpening('opening_1')] });
          }}>
          <option value="unknown">{w('flooding.openings.inherit')}</option>
          <option value="yes">{w('flooding.openings.none')}</option>
          <option value="no">{w('flooding.openings.pointwise')}</option>
        </select></label>
        {openingState === 'no' && <div className="form-grid">
          <label className="field-label">{w('flooding.openings.newId')}<input aria-label={w('flooding.openings.newIdAria')} value={newOpeningId} onChange={event => setNewOpeningId(event.target.value)} /></label>
          <button className="button button--secondary" type="button"
            onClick={() => {
              const nextId = uniqueId(newOpeningId.trim() || 'opening_1', openingRows.map(item => item.id));
              setNewOpeningId('opening_1');
              patch({ openings: [...openingRows, newOpening(nextId)] });
            }}>{w('flooding.openings.add')}</button>
        </div>}
        {openingRows.map((opening, index) => <div className="form-card" key={String(opening.id ?? index)}>
          <div className="form-card-body"><div className="form-grid">
            <label className="field-label">{w('flooding.openings.id')}<input aria-label={w('flooding.openings.idAria', { id, opening: String(opening.id) })} value={String(opening.id ?? '')}
              onChange={event => patchOpening(index, { id: event.target.value })} /></label>
            <label className="field-label">{w('flooding.openings.kind')}<input aria-label={w('flooding.openings.kindAria', { id, opening: String(opening.id) })} placeholder={w('flooding.openings.kindPlaceholder')}
              value={typeof opening.kind === 'string' ? opening.kind : ''}
              onChange={event => {
              const kind = event.target.value.trim();
              const next: Raw = { ...opening };
              if (kind) next.kind = kind; else delete next.kind;
              replaceOpening(index, next);
            }} /></label>
            {(['x_m', 'y_m', 'z_m'] as const).map(field => <QuantityField key={field} label={w(field === 'x_m' ? 'flooding.openings.longitudinal' : field === 'y_m' ? 'flooding.openings.transverse' : 'flooding.openings.height')}
              ariaLabel={w('flooding.openings.coordAria', { id, opening: String(opening.id), field })} value={number(opening[field])} dimension="length" storedUnit="m"
              onChange={next => patchOpening(index, { [field]: next })} />)}
            <label className="field-label">{w('flooding.openings.open')}<select aria-label={w('flooding.openings.openAria', { id, opening: String(opening.id) })} value={tri(opening.open)}
              onChange={event => patchOpening(index, { open: triValue(event.target.value as TriState) })}>
              <option value="unknown">{w('fact.estimateUnknown')}</option><option value="yes">{w('flooding.open.yes')}</option><option value="no">{w('flooding.open.no')}</option></select></label>
            {metadataFields(w, `${id} ${w('flooding.openings.id')} ${String(opening.id)}`, opening, patchValue => patchOpening(index, patchValue))}
            <button className="text-button" type="button" onClick={() => patch({ openings: openingRows.filter((_, i) => i !== index) })}>{w('flooding.openings.remove', { id: String(opening.id) })}</button>
          </div></div>
        </div>)}
      </div>

      <div className="form-card"><h3>{w('flooding.damage.removeTitle')}</h3>
        <p>{w('flooding.damage.removeNote')}</p>
        <button className="text-button" type="button"
          onClick={() => { emit(scenarios.filter(row => row !== selected)); setChoice(null); setCopyNote(''); }}>{w('flooding.damage.removeAction', { id })}</button>
      </div>
    </>}

    <div className="form-card"><h3>{w('flooding.compartments.title')}</h3>
      <p>{w('flooding.compartments.intro')}</p>
      {compartments.length === 0 && <p className="form-hint">{w('flooding.compartments.empty')}</p>}
      <div className="form-grid">
        <label className="field-label">{w('flooding.compartments.newId')}<input aria-label={w('flooding.compartments.newIdAria')} value={newCompartmentId}
          onChange={event => setNewCompartmentId(event.target.value)} /></label>
        <button className="button button--secondary" type="button"
          onClick={() => {
            const nextId = uniqueId(newCompartmentId.trim() || 'compartment_1', compartments.map(row => row.id));
            setNewCompartmentId('compartment_1');
            emitCompartments([...compartments, { id: nextId, label: nextId, ...Object.fromEntries(
              TANK_FIELDS.filter(field => field.key !== 'initial_volume_m3').map(field => [field.key, null])), free_surface: null, source: null, estimate: null }]);
          }}>{w('flooding.compartments.add')}</button>
      </div>
      {compartments.map((compartment, index) => <details className="form-card" open key={String(compartment.id ?? index)}>
        <summary>{w('flooding.compartments.summary', { label: String(compartment.label ?? compartment.id) })}</summary><div className="form-card-body">
          <div className="form-grid">
            <label className="field-label">{w('flooding.compartments.id')}<input aria-label={w('flooding.compartments.idAria', { id: String(compartment.id) })} value={String(compartment.id ?? '')} readOnly />
              <small>{w('flooding.compartments.idNote')}</small></label>
            <label className="field-label">{w('flooding.compartments.name')}<input aria-label={w('flooding.compartments.nameAria', { id: String(compartment.id) })} value={String(compartment.label ?? '')}
              onChange={event => emitCompartments(compartments.map((row, i) => i === index ? { ...row, label: event.target.value } : row))} /></label>
            {TANK_FIELDS.filter(field => field.key !== 'initial_volume_m3').map(spec => numericField(w, spec,
              `${w('flooding.compartments.summary', { label: String(compartment.id) })}`, compartment[spec.key], raw => compartmentField(index, spec, raw),
              problems[`compartment${index}/${spec.key}`] ?? null))}
            <label className="field-label">{w('flooding.freeSurface.label')}<select aria-label={w('flooding.compartments.freeSurfaceAria', { id: String(compartment.id) })} value={tri(compartment.free_surface)}
              onChange={event => emitCompartments(compartments.map((row, i) => i === index ? { ...row, free_surface: triValue(event.target.value as TriState) } : row))}>
              <option value="unknown">{w('form.triUnknown')}</option><option value="yes">{w('flooding.freeSurface.yes')}</option><option value="no">{w('flooding.freeSurface.no')}</option>
            </select></label>
          </div>
          {metadataFields(w, w('flooding.compartments.summary', { label: String(compartment.id) }), compartment,
            patchValue => emitCompartments(compartments.map((row, i) => i === index ? { ...row, ...patchValue } : row)))}
          {compartmentReferences(compartment.id).length > 0 && <p className="form-hint">{w('flooding.compartments.referenced', { references: compartmentReferences(compartment.id).join(w('form.listSeparator')) })}</p>}
          <button className="text-button" type="button" disabled={compartmentReferences(compartment.id).length > 0}
            onClick={() => emitCompartments(compartments.filter((_, i) => i !== index))}>{w('flooding.compartments.remove', { id: String(compartment.id) })}</button>
        </div></details>)}
    </div>

    {selected && <>
      <div className="form-card"><h3>{w('flooding.damage.requestTitle')}</h3>
        <p>{w('flooding.damage.requestNote')}</p>
        <div className="form-grid">
          <label className="field-label">{w('flooding.request.scenario')}<select aria-label={w('flooding.request.scenarioAria')} value={request.scenario}
            onChange={event => onRequestChange({ ...request, scenario: event.target.value })}>
            <option value="">{w('flooding.request.noScenario')}</option>
            {scenarios.map(row => <option key={String(row.id)} value={String(row.id)}>{String(row.id)}</option>)}
          </select></label>
          {/* Density is canonical: it is never scaled by a display preference. */}
          <label className="field-label">{w('flooding.form.rho')}<input type="number" step="any" placeholder={w('flooding.form.rhoPlaceholder', { value: EQUILIBRIUM_RHO_T_M3 })}
            aria-label={w('flooding.form.rhoAria')} value={request.rho}
            onChange={event => onRequestChange({ ...request, rho: event.target.value })} /></label>
          <label className="field-label">{w('flooding.form.steps')}<input type="number" step="1" placeholder={w('flooding.form.stepsPlaceholder')} aria-label={w('flooding.form.stepsAria')}
            value={request.steps} onChange={event => onRequestChange({ ...request, steps: event.target.value })} /></label>
          <label className="field-label">{w('flooding.form.halvings')}<input type="number" step="1" placeholder={w('flooding.form.halvingsPlaceholder')} aria-label={w('flooding.form.halvingsAria')}
            value={request.halvings} onChange={event => onRequestChange({ ...request, halvings: event.target.value })} /></label>
          <label className="field-label">{w('flooding.form.gravity')}<input type="number" step="any" placeholder={w('flooding.form.gravityPlaceholder')} aria-label={w('flooding.form.gravityAria')}
            value={request.gravity} onChange={event => onRequestChange({ ...request, gravity: event.target.value })} /></label>
          <QuantityListField label={w('flooding.form.gzAngles')} value={request.gzAngles} dimension="angle" placeholder={w('flooding.form.gzAnglesPlaceholder')}
            onChange={values => onRequestChange({ ...request, gzAngles: values })} />
          <label className="field-label">{w('flooding.form.gzSnapshot')}<select aria-label={w('flooding.form.gzSnapshotAria')} value={request.gzSnapshot}
            onChange={event => onRequestChange({ ...request, gzSnapshot: event.target.value as FloodingRequest['gzSnapshot'] })}>
            <option value="final">{w('flooding.form.gzFinal')}</option><option value="each_state">{w('flooding.form.gzEach')}</option>
          </select></label>
        </div>
        {/* The operation bar announces the request failure as the one alert;
            this copy keeps it next to the controls that caused it. */}
        {requestError && <p className="form-error">{requestError}</p>}
        <p className="form-hint">{w('flooding.form.note', { value: EQUILIBRIUM_RHO_T_M3 })}</p>
      </div>

    </>}

    <ResultSection available={!!run}>
      {!!run && data.status != null && <p className="result-context">{w('flooding.result.context', { id: run.id, scenario: String(object(data.scenario).id ?? w('units.unknown')), fingerprint: run.request_fingerprint })}</p>}
      {data.status == null
        ? <p className="section-intro">{w('flooding.result.empty')}</p>
        : <FloodingResults data={data} />}
      <Diagnostics value={data.diagnostics} />
    </ResultSection>
  </div>;
}
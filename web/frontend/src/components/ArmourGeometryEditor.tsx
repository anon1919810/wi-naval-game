import { useRef } from 'react';

import { useConceptCopy } from '../i18n/concept';
import { QuantityField } from './QuantityField';
import { number, object, sourceText, type Raw } from './formModel';
import { DeclaredNumber, ItemSelect } from './declaredInputs';
import {
  armourGeometryAngleBasis, armourGeometryEligibleKind, armourGeometryEnabled,
  armourGeometryIdValid, armourGeometryOf, armourGeometryPlates, armourGeometryRegions,
  ARMOUR_GEOMETRY_WIDTH_BASES, ARMOUR_GEOMETRY_WIDTH_BASIS_LABELS,
  duplicateArmourGeometryPlateIds, duplicateArmourGeometryRegions, fixedArmour, fixedArmourKind,
  newArmourGeometry, newArmourGeometryPlate, newArmourGeometryRegion, patchArmourGeometry,
  patchArmourGeometryPlate, patchArmourGeometryRegion, removeArmourGeometry,
  removeArmourGeometryPlate, removeArmourGeometryRegion, MAX_ARMOUR_GEOMETRY_PLATES,
  MAX_ARMOUR_GEOMETRY_REGIONS, type ArmourWidthBasis,
} from './conceptDesign';

/**
 * The optional geometric armour panels, declared as ordinary inputs.
 *
 * This is a *declaration* and nothing else. Selecting a fixed region for the
 * rectangular model opts that region into geometry — replacing the entire
 * empirical region's suggestion and every layer it already carried — and every
 * plate is one explicit flat panel with its own length, width, thickness, count
 * and material. Nothing here computes an area, a volume or a mass: the server
 * owns the geometry and its readings, and this screen invents no density, no
 * size, no angle and no number of sides.
 *
 * Enabling the section selects no region. A region entry is the reader's own
 * explicit opt-in, and it stays a legal, unfinished draft until it is completed;
 * a missing or empty plate list is incomplete, never a declared zero panel.
 */

interface ArmourGeometryEditorProps {
  config: Raw;
  commit: (next: Raw) => void;
}

export function ArmourGeometryEditor({ config, commit }: ArmourGeometryEditorProps) {
  const c = useConceptCopy();
  const section = armourGeometryOf(config);
  const enabled = armourGeometryEnabled(config);
  const regions = armourGeometryRegions(config);
  const atLimit = regions.length >= MAX_ARMOUR_GEOMETRY_REGIONS;
  const records = fixedArmour(config);
  const used = new Set<string>();
  for (const region of regions) {
    const id = region.fixed_armour_id;
    if (typeof id === 'string' && id !== '') used.add(id);
  }
  const duplicates = duplicateArmourGeometryRegions(config);
  const rowKeys = useRef<number[]>([]);
  const nextRowKey = useRef(0);
  while (rowKeys.current.length < regions.length) rowKeys.current.push(nextRowKey.current++);
  rowKeys.current.length = regions.length;

  function patch(next: Raw) { commit(patchArmourGeometry(config, next)); }

  return <div className="form-card">
    <h3>{c('concept.group.armourGeometry')}</h3>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.armourGeometry.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? { ...config, armour_geometry: newArmourGeometry() }
          : removeArmourGeometry(config))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.armourGeometry.note')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <label className="field-label">{c('concept.armourGeometry.source')}
          <input aria-label={c('concept.armourGeometry.source')}
            value={typeof object(section).source === 'string' ? String(object(section).source) : ''}
            placeholder={c('concept.source.placeholder')}
            onChange={event => patch({
              source: event.target.value.trim() === '' ? null : event.target.value })} />
          <small>{c('concept.armourGeometry.sourceHint')}</small>
        </label>
      </div>
      {/* The whole declaration is one model choice per region: geometry replaces
          the empirical suggestion for a region, and every declared layer counts
          separately because the reader said so. */}
      <p className="form-hint">{c('concept.armourGeometry.replace')}</p>
      <p className="form-hint">{c('concept.armourGeometry.separate')}</p>
      {duplicates.length > 0 ? <p className="form-error" role="alert">
        {c('concept.armourGeometry.duplicateRegion')} {duplicates.join(', ')}</p> : null}
      {regions.length === 0 ? <p className="form-hint">{c('concept.armourGeometry.noRegion')}</p> : null}
      {regions.map((region, index) => <ArmourGeometryRegion key={rowKeys.current[index]}
        config={config} index={index} commit={commit} records={records} used={used} />)}
      <button className="button button--secondary" type="button" disabled={atLimit}
        onClick={() => commit(patchArmourGeometry(config,
          { regions: [...regions, newArmourGeometryRegion()] }))}>
        {c('concept.armourGeometry.addRegion')}
      </button>
      {atLimit && <p className="form-hint">
        {c('concept.armourGeometry.regionMax', { count: MAX_ARMOUR_GEOMETRY_REGIONS })}</p>}
    </>}
  </div>;
}

/**
 * One declared region: the fixed record it names and the plates it declares.
 *
 * The angle convention is stated from the region kind and the chosen width basis
 * — from the vertical for belts and bulkheads, from the horizontal for a deck —
 * because an angle whose reference line is not stated is not a declaration.
 */
function ArmourGeometryRegion({ config, index, commit, records, used }: {
  config: Raw; index: number; commit: (next: Raw) => void; records: Raw[]; used: Set<string>;
}) {
  const c = useConceptCopy();
  const plateKeys = useRef<number[]>([]);
  const nextPlateKey = useRef(0);
  const region = armourGeometryRegions(config)[index];
  if (!region) return null;
  const fixedId = typeof region.fixed_armour_id === 'string' && region.fixed_armour_id !== ''
    ? region.fixed_armour_id : '';
  const eligible = records.filter(record =>
    typeof record.id === 'string' && record.id !== '' && armourGeometryEligibleKind(record.kind));
  const options = eligible
    .filter(record => record.id === fixedId || !used.has(record.id as string))
    .map(record => ({ id: record.id as string, label: record.id as string }));
  const referenced = eligible.find(record => record.id === fixedId);
  const kind = referenced ? fixedArmourKind(referenced.kind) : null;
  const plates = armourGeometryPlates(region);
  const duplicatePlates = new Set(duplicateArmourGeometryPlateIds(region));
  const dangling = fixedId !== '' && referenced === undefined;
  while (plateKeys.current.length < plates.length) plateKeys.current.push(nextPlateKey.current++);
  plateKeys.current.length = plates.length;

  function patch(next: Raw) { commit(patchArmourGeometryRegion(config, index, next)); }

  return <div className="form-card">
    <div className="form-grid">
      <ItemSelect label={c('concept.armourGeometry.regionRecord')}
        ariaLabel={`${c('concept.armourGeometry.regionRecord')} ${index + 1}`} value={region.fixed_armour_id}
        options={options} emptyLabel={c('concept.armourGeometry.chooseRegion')}
        hint={c('concept.armourGeometry.regionHint')}
        onChange={next => patch({ fixed_armour_id: next })} />
      <label className="field-label">{c('concept.armourGeometry.regionSource')}
        <input aria-label={`${c('concept.armourGeometry.regionSource')} ${index + 1}`}
          value={sourceText(region.source)} placeholder={c('concept.source.placeholder')}
          onChange={event => patch({
            source: event.target.value.trim() === '' ? null : event.target.value })} />
        <small>{c('concept.armourGeometry.regionSourceHint')}</small>
      </label>
    </div>
    {eligible.length === 0 ? <p className="form-hint">{c('concept.armourGeometry.noEligible')}</p> : null}
    {dangling ? <p className="form-error" role="alert">
      {c('concept.armourGeometry.invalidRegion')} {fixedId}</p> : null}
    <h4>{c('concept.armourGeometry.plates')}</h4>
    <p className="form-hint">{c('concept.armourGeometry.platesHint', {
      convention: kind === null ? c('concept.armourGeometry.angleUnknown')
        : armourGeometryAngleBasis(kind) === 'horizontal'
          ? c('concept.armourGeometry.angleHorizontal')
          : c('concept.armourGeometry.angleVertical') })}</p>
    {plates.length === 0 ? <p className="form-hint">{c('concept.armourGeometry.noPlate')}</p> : null}
    {plates.map((plate, plateIndex) => <ArmourGeometryPlate key={plateKeys.current[plateIndex]}
      config={config} regionIndex={index} plateIndex={plateIndex} commit={commit} kind={kind}
      duplicate={String(plate.id ?? '') !== '' && duplicatePlates.has(String(plate.id ?? ''))} />)}
    <button className="text-button" type="button"
      disabled={plates.length >= MAX_ARMOUR_GEOMETRY_PLATES}
      onClick={() => patch({ plates: [...plates, newArmourGeometryPlate()] })}>
      {c('concept.armourGeometry.addPlate')}
    </button>
    {plates.length >= MAX_ARMOUR_GEOMETRY_PLATES ? <p className="form-hint">
      {c('concept.armourGeometry.plateMax', { count: MAX_ARMOUR_GEOMETRY_PLATES })}</p> : null}
    <button className="text-button" type="button"
      onClick={() => commit(removeArmourGeometryRegion(config, index))}>
      {c('concept.armourGeometry.removeRegion')}
    </button>
  </div>;
}

/** One plate: identity, provenance, the declared box and how its width develops. */
function ArmourGeometryPlate({ config, regionIndex, plateIndex, commit, kind, duplicate }: {
  config: Raw; regionIndex: number; plateIndex: number; commit: (next: Raw) => void;
  kind: unknown; duplicate: boolean;
}) {
  const c = useConceptCopy();
  const plate = armourGeometryPlates(armourGeometryRegions(config)[regionIndex])[plateIndex];
  if (!plate) return null;
  const basis = typeof plate.width_basis === 'string'
    && (ARMOUR_GEOMETRY_WIDTH_BASES as readonly string[]).includes(plate.width_basis)
    ? plate.width_basis as ArmourWidthBasis : '';
  const id = typeof plate.id === 'string' ? plate.id : '';
  const angleBasis = armourGeometryAngleBasis(kind);

  function patch(next: Raw) { commit(patchArmourGeometryPlate(config, regionIndex, plateIndex, next)); }

  return <div className="form-card">
    <div className="form-grid">
      <label className="field-label">{c('concept.armourGeometry.plateId')}
        <input aria-label={`${c('concept.armourGeometry.plateId')} ${plateIndex + 1}`} value={id}
          onChange={event => patch({ id: event.target.value })} />
      </label>
      <label className="field-label">{c('concept.armourGeometry.plateSource')}
        <input aria-label={`${c('concept.armourGeometry.plateSource')} ${plateIndex + 1}`}
          value={sourceText(plate.source)} placeholder={c('concept.source.placeholder')}
          onChange={event => patch({ source: event.target.value.trim() === '' ? null : event.target.value })} />
      </label>
      <label className="field-label">{c('concept.armourGeometry.densitySource')}
        <input aria-label={`${c('concept.armourGeometry.densitySource')} ${plateIndex + 1}`}
          value={sourceText(plate.density_source)} placeholder={c('concept.source.placeholder')}
          onChange={event => patch({
            density_source: event.target.value.trim() === '' ? null : event.target.value })} />
        <small>{c('concept.armourGeometry.densitySourceHint')}</small>
      </label>
      <QuantityField label={c('concept.armourGeometry.length')}
        ariaLabel={`${c('concept.armourGeometry.length')} ${plateIndex + 1}`}
        dimension="length" storedUnit="m" kind="nonnegative" value={number(plate.length_m)}
        hint={c('concept.armourGeometry.lengthHint')} onChange={next => patch({ length_m: next })} />
      <QuantityField label={c('concept.armourGeometry.width')}
        ariaLabel={`${c('concept.armourGeometry.width')} ${plateIndex + 1}`}
        dimension="length" storedUnit="m" kind="nonnegative" value={number(plate.width_m)}
        onChange={next => patch({ width_m: next })} />
      <QuantityField label={c('concept.armourGeometry.thickness')}
        ariaLabel={`${c('concept.armourGeometry.thickness')} ${plateIndex + 1}`}
        dimension="length" storedUnit="mm" kind="nonnegative" value={number(plate.thickness_mm)}
        onChange={next => patch({ thickness_mm: next })} />
      <DeclaredNumber label={c('concept.armourGeometry.density')}
        ariaLabel={`${c('concept.armourGeometry.density')} ${plateIndex + 1}`}
        kind="positive" min={0} max={30000} unit="kg/m³" value={plate.density_kg_m3}
        hint={c('concept.armourGeometry.densityHint')} onChange={next => patch({ density_kg_m3: next })} />
      <DeclaredNumber label={c('concept.armourGeometry.count')}
        ariaLabel={`${c('concept.armourGeometry.count')} ${plateIndex + 1}`}
        kind="integer" min={0} max={1000000} value={plate.count}
        hint={c('concept.armourGeometry.countHint')} onChange={next => patch({ count: next })} />
      <label className="field-label">{c('concept.armourGeometry.widthBasis')}
        <select aria-label={`${c('concept.armourGeometry.widthBasis')} ${plateIndex + 1}`} value={basis}
          onChange={event => patch({ width_basis: event.target.value === '' ? null : event.target.value })}>
          <option value="">{c('concept.armourGeometry.basisUnknown')}</option>
          {ARMOUR_GEOMETRY_WIDTH_BASES.map(name =>
            <option key={name} value={name}>{c(ARMOUR_GEOMETRY_WIDTH_BASIS_LABELS[name])}</option>)}
        </select>
      </label>
      <DeclaredNumber label={c('concept.armourGeometry.angle')}
        ariaLabel={`${c('concept.armourGeometry.angle')} ${plateIndex + 1}`}
        kind="signed" min={-89} max={89} unit="°" value={plate.inclination_deg}
        hint={angleBasis === 'horizontal' ? c('concept.armourGeometry.angleHorizontal')
          : angleBasis === 'vertical' ? c('concept.armourGeometry.angleVertical')
            : c('concept.armourGeometry.angleUnknown')}
        onChange={next => patch({ inclination_deg: next })} />
    </div>
    <p className="form-hint">{basis === 'projected' ? c('concept.armourGeometry.angleUsed')
      : basis === 'developed' ? c('concept.armourGeometry.angleUnused')
        : c('concept.armourGeometry.basisRequired')}</p>
    {!armourGeometryIdValid(plate.id) ? <p className="form-error" role="alert">
      {c('concept.armourGeometry.invalidPlateId')}</p> : null}
    {duplicate ? <p className="form-error" role="alert">
      {c('concept.armourGeometry.duplicatePlate', { id })}</p> : null}
    <button className="text-button" type="button"
      onClick={() => commit(removeArmourGeometryPlate(config, regionIndex, plateIndex))}>
      {c('concept.armourGeometry.removePlate')}
    </button>
  </div>;
}

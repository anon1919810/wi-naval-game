import { useState } from 'react';

import { useConceptCopy } from '../i18n/concept';
import { DeclaredNumber } from './declaredInputs';
import { useUnits } from './UnitProvider';
import { object, type Raw } from './formModel';
import { FIXED_ARMOUR_KIND_LABELS, fixedArmour } from './conceptDesign';
import {
  ARMOUR_DEFAULT_FIELDS, ARMOUR_DEFAULT_LABELS, ARMOUR_DEFAULT_VALUE_KEYS,
  ARMOUR_DEFAULTS_METHOD, armourDefaultCandidate, armourDefaultsOf, armourDefaultsReading,
  isArmourDefaultKind, newArmourDefaults, patchArmourDefaults, planArmourDefaults,
  removeArmourDefaults, type ArmourDefaultField, type ArmourDefaultSelection,
} from './armourDefaults';
import type { RunView } from '../types';

/**
 * The recovered default armour sizes, previewed and explicitly copied.
 *
 * This is an ordinary declaration and an ordinary draft edit: the reader turns it
 * on, writes a source and two optional fractions, reads the current saved run's
 * eight suggested sizes, and then *chooses* which existing fixed-armour records
 * and which of their two dimensions to fill. Nothing is selected for them, no
 * record is created, and no mass is adopted — the copy writes the two declared
 * dimensions and one plain source annotation and touches nothing else.
 *
 * The selection is bound to one saved result's identity. A changed revision,
 * condition, request option or unsaved edit retires it, and the copy is offered
 * only from the current saved run: a stale suggestion is never written over a
 * newer edit, and the reader is never asked to approve a run they cannot see.
 */

interface ArmourDefaultsPanelProps {
  config: Raw;
  commit: (next: Raw) => void;
  /** The current saved run, or null while the request no longer matches the draft. */
  run: RunView | null;
  /** The saved identity the selection belongs to; a new one retires the selection. */
  identity: string;
  /** Whether the draft has unsaved edits the saved run cannot see. */
  dirty: boolean;
  /** Whether the run's request options still match the options on screen. */
  requestCurrent: boolean;
}

export function ArmourDefaultsPanel({ config, commit, run, identity, dirty, requestCurrent }:
ArmourDefaultsPanelProps) {
  const c = useConceptCopy();
  const units = useUnits();
  const summary = armourDefaultsOf(config);
  const enabled = summary !== null;
  const preview = armourDefaultsReading(run);
  const ownerKey = `${identity}|${run?.id ?? ''}|${run?.request_fingerprint ?? ''}|${dirty}|${requestCurrent}`;
  const [owned, setOwned] = useState<{ key: string; fields: Record<string, ArmourDefaultField[]> }>(
    () => ({ key: ownerKey, fields: {} }));
  const selection = owned.key === ownerKey ? owned.fields : {};
  // Retire the old approval permanently before this render commits. Masking it
  // alone would restore an old choice after switching A → B → A.
  if (owned.key !== ownerKey) setOwned({key:ownerKey,fields:{}});
  const stageMethod = object(object(run?.result?.stages?.design_balance?.method_versions).methods).armour_defaults;
  const methodCurrent = stageMethod === ARMOUR_DEFAULTS_METHOD
    && preview?.method_version === ARMOUR_DEFAULTS_METHOD && preview?.id === 'armour_defaults'
    && (preview?.status === 'available' || preview?.status === 'partial');
  const inputs = object(object(preview?.provenance).inputs);

  const records = fixedArmour(config).filter(record =>
    typeof record.id === 'string' && record.id !== '' && isArmourDefaultKind(record.kind));
  const duplicated = new Set<string>();
  const counts = new Map<string, number>();
  for (const record of records) {
    const id = String(record.id);
    counts.set(id, (counts.get(id) ?? 0) + 1);
  }
  for (const [id, count] of counts) if (count > 1) duplicated.add(id);

  // Only the records still present and still chosen contribute; a record the
  // reader removed simply drops out of the selection rather than blocking it.
  const selections: ArmourDefaultSelection[] = records
    .filter(record => (selection[String(record.id)] ?? []).length > 0)
    .map(record => ({ record_id: String(record.id), fields: [...selection[String(record.id)]!] }));

  const copyReady = run !== null && requestCurrent && !dirty && methodCurrent;
  const sourceRunId = copyReady && run !== null ? String(run.id ?? '') : null;
  const plan = planArmourDefaults(config, copyReady ? preview : null, selections,
    copyReady ? sourceRunId : null);

  function toggle(recordId: string, field: ArmourDefaultField) {
    setOwned(current => {
      const fields = current.key === ownerKey ? current.fields : {};
      const chosen = fields[recordId] ?? [];
      const next = chosen.includes(field)
        ? chosen.filter(item => item !== field) : [...chosen, field];
      return { key: ownerKey, fields: { ...fields, [recordId]: next } };
    });
  }

  function copy() {
    if (!copyReady || owned.key !== ownerKey || !plan.ok) return;
    setOwned({ key: ownerKey, fields: {} });
    commit(plan.config);
  }

  return <div className="form-card">
    <h3>{c('concept.group.armourDefaults')}</h3>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.armourDefaults.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? { ...config, armour_defaults: newArmourDefaults() } : removeArmourDefaults(config))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.armourDefaults.note')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <label className="field-label">{c('concept.armourDefaults.source')}
          <input aria-label={c('concept.armourDefaults.source')}
            value={typeof object(summary).source === 'string' ? String(object(summary).source) : ''}
            placeholder={c('concept.source.placeholder')}
            onChange={event => commit(patchArmourDefaults(config,
              { source: event.target.value.trim() === '' ? null : event.target.value }))} />
          <small>{c('concept.armourDefaults.sourceHint')}</small>
        </label>
        <DeclaredNumber label={c('concept.armourDefaults.forecastle')} kind="nonnegative" min={0} max={1}
          value={object(summary).forecastle_fraction}
          onChange={next => commit(patchArmourDefaults(config, { forecastle_fraction: next }))} />
        <DeclaredNumber label={c('concept.armourDefaults.quarterdeck')} kind="nonnegative" min={0} max={1}
          value={object(summary).quarterdeck_fraction}
          onChange={next => commit(patchArmourDefaults(config, { quarterdeck_fraction: next }))} />
      </div>
      <p className="form-hint">{c('concept.armourDefaults.fractionHint')}</p>

      <h4>{c('concept.armourDefaults.previewTitle')}</h4>
      <p className="form-hint">{c('concept.armourDefaults.previewNote')}</p>
      {preview === null ? <p className="form-hint">{c('concept.armourDefaults.noPreview')}</p>
        : <div className="metric-grid">
          {ARMOUR_DEFAULT_VALUE_KEYS.map(([kind, field, key]) => {
            const candidate = armourDefaultCandidate(preview, kind, field);
            return <div className="fact-field" key={key}>
              <span className="fact-label">{c(ARMOUR_DEFAULT_LABELS[kind][field])}</span>
              <span className="fact-value">{units.text(candidate.value, 'length', 'm')}</span>
              {candidate.value !== null && <small className="fact-meta">
                {c('concept.armourDefaults.canonical')} <code>{String(candidate.value)} m</code>
              </small>}
              <span className="fact-meta">{candidate.selectable
                ? c('concept.armourDefaults.state.available')
                : c('concept.armourDefaults.state.unavailable')}
                {candidate.reason === null ? '' : ` · ${candidate.reason}`}</span>
            </div>;
          })}
        </div>}
      <p className="form-hint">{c('concept.armourDefaults.method', {
        method: String(preview?.method_version ?? ARMOUR_DEFAULTS_METHOD) })}</p>
      {preview !== null && <>
        <p className="form-hint">{c('concept.armourDefaults.run')} <code>{run?.id ?? '—'}</code></p>
        <details open>
          <summary>{c('concept.armourDefaults.inputs')}</summary>
          <dl className="metric-grid">
            {([
              ['length_m', 'concept.armourDefaults.inputLength', 'm'],
              ['beam_m', 'concept.armourDefaults.inputBeam', 'm'],
              ['draught_m', 'concept.armourDefaults.inputDraught', 'm'],
              ['block_coeff', 'concept.armourDefaults.inputBlock', ''],
              ['freeboard_m', 'concept.armourDefaults.inputFreeboard', 'm'],
              ['forecastle_fraction', 'concept.armourDefaults.forecastle', ''],
              ['quarterdeck_fraction', 'concept.armourDefaults.quarterdeck', ''],
            ] as const).map(([key, label, unit]) => <div className="fact-field" key={key}>
              <dt className="fact-label">{c(label)}</dt>
              <dd className="fact-value">{typeof inputs[key] === 'number' && Number.isFinite(inputs[key])
                ? `${String(inputs[key])}${unit ? ` ${unit}` : ''}` : '—'}</dd>
            </div>)}
          </dl>
        </details>
        {!methodCurrent && <p className="form-error" role="status">{c('concept.armourDefaults.methodConflict')}</p>}
      </>}

      <h4>{c('concept.armourDefaults.selectTitle')}</h4>
      <p className="form-hint">{c('concept.armourDefaults.selectNote')}</p>
      {records.length === 0 ? <p className="form-hint">{c('concept.armourDefaults.noRecords')}</p>
        : records.map(record => {
          const id = String(record.id);
          const kind = record.kind;
          if (!isArmourDefaultKind(kind)) return null;
          return <section className="concept-balance-group" key={id} aria-label={id}>
            <h5>{id}{` · ${c(FIXED_ARMOUR_KIND_LABELS[kind])}`}</h5>
            {duplicated.has(id) ? <p className="form-error" role="alert">
              {c('concept.armourDefaults.duplicateRecord')}</p> : null}
            <div className="metric-grid">
              {ARMOUR_DEFAULT_FIELDS.map(field => {
                const candidate = armourDefaultCandidate(preview, kind, field);
                const chosen = (selection[id] ?? []).includes(field);
                const selectable = candidate.selectable;
                return <div className="fact-field" key={field}>
                  <span className="fact-label">{c(ARMOUR_DEFAULT_LABELS[kind][field])}</span>
                  <span className="fact-value">{units.text(object(record)[field], 'length', 'm')}</span>
                  <label className="field-label field-label--inline">
                    <input type="checkbox" aria-label={c('concept.armourDefaults.fill', {
                      record: id, field: c(ARMOUR_DEFAULT_LABELS[kind][field]) })}
                      checked={chosen} disabled={!selectable || duplicated.has(id)}
                      onChange={() => toggle(id, field)} />
                    {c(ARMOUR_DEFAULT_LABELS[kind][field])}
                  </label>
                  {candidate.selectable ? null
                    : <span className="fact-meta">{candidate.reason
                      ?? c('concept.armourDefaults.state.unavailable')}</span>}
                </div>;
              })}
            </div>
          </section>;
        })}

      <button className="button" type="button" disabled={!plan.ok} onClick={copy}>
        {c('concept.armourDefaults.copy')}
      </button>
      <p className="form-hint">{!copyReady ? c('concept.armourDefaults.stale')
        : plan.ok ? c('concept.armourDefaults.ready')
          : plan.reason === 'no-selection' ? c('concept.armourDefaults.choose')
            : c('concept.armourDefaults.refuse')}</p>
      <p className="form-hint">{c('concept.armourDefaults.annotation')}</p>
    </>}
  </div>;
}

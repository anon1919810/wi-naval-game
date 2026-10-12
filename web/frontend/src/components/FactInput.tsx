import { QuantityField } from './QuantityField';
import { number, object, type Raw } from './formModel';
import { declaredSource, TracedField, type TraceFact } from './InputTrace';
import { useWorkspaceCopy } from '../i18n/workspace';
import type { Dimension } from './units';

export function EstimateInput({ label, value, onChange }: { label: string; value: unknown; onChange: (value: boolean | null) => void }) {
  const w = useWorkspaceCopy();
  return <label className="field-label">{w('fact.estimateLabel')}<select aria-label={label} value={value === true ? 'estimate' : value === false ? 'confirmed' : 'unknown'}
    onChange={e => onChange(e.target.value === 'estimate' ? true : e.target.value === 'confirmed' ? false : null)}>
    <option value="unknown">{w('fact.estimateUnknown')}</option><option value="estimate">{w('fact.estimate')}</option><option value="confirmed">{w('fact.confirmed')}</option>
  </select></label>;
}

export interface FactInputProps {
  label: string;
  value: unknown;
  onChange: (value: Raw) => void;
  kind?: 'number' | 'integer' | 'text';
  /** Reading dimension; the fact value is stored in `storedUnit`. */
  dimension?: Dimension;
  storedUnit?: string;
  hint?: string;
  /** Where the fact lives in the document, shown by the Trace panel. */
  path?: string;
}

/**
 * A sourced fact: value, source and three-state estimate. With a convertible
 * dimension the value speaks the reader's unit while `{value}` stays canonical;
 * `storedUnit` declares the unit the fact is actually stored in.
 */
export function FactInput({ label, value, kind = 'number', dimension, storedUnit, onChange, hint, path }: FactInputProps) {
  const w = useWorkspaceCopy();
  const entry = object(value);
  // Only the fact's own stored fields: no default source, no implied estimate.
  const fact: TraceFact = {
    key: path ?? label, label, value: typeof entry.value === 'number' || typeof entry.value === 'string' ? entry.value : null,
    dimension, storedUnit,
    source: declaredSource(entry.source),
    estimate: entry.estimate === true ? true : entry.estimate === false ? false : null,
    path,
  };
  return <fieldset className="fact-input"><legend>{label}</legend>
    <TracedField fact={fact}>
    <div className="form-grid">
    {dimension && kind !== 'text'
      ? <QuantityField label={label} ariaLabel={w('fact.valueAria', { label })} dimension={dimension} storedUnit={storedUnit}
        value={number(entry.value)} kind={kind === 'integer' ? 'integer' : 'signed'} hint={hint}
        onChange={next => onChange({ ...entry, value: next })} />
      : <label className="field-label">{w('fact.value')}<input aria-label={w('fact.valueAria', { label })} type={kind === 'text' ? 'text' : 'number'} step={kind === 'integer' ? 1 : 'any'}
        placeholder={w('units.unknown')} value={typeof entry.value === 'number' || typeof entry.value === 'string' ? entry.value : ''}
        onChange={e => onChange({ ...entry, value: kind === 'text' ? e.target.value.trim() === '' ? null : e.target.value : number(e.target.value.trim() === '' ? null : Number(e.target.value)) })} />
        {hint && <small>{hint}</small>}</label>}
    <label className="field-label">{w('fact.source')}<input aria-label={w('fact.sourceAria', { label })} value={declaredSource(entry.source) ?? ''} placeholder={w('fact.sourcePlaceholder')}
      onChange={e => onChange({ ...entry, source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
    <EstimateInput label={w('fact.estimateAria', { label })} value={entry.estimate} onChange={estimate => onChange({ ...entry, estimate })} />
  </div>
    </TracedField>
  </fieldset>;
}

export function IdPicker({ label, selected, options, onChange }: { label: string; selected: unknown; options: Array<{ id: string; label?: string }>; onChange: (ids: string[]) => void }) {
  const w = useWorkspaceCopy();
  const ids = Array.isArray(selected) ? selected.filter((id): id is string => typeof id === 'string') : [];
  const choices = [...options, ...ids.filter(id => !options.some(o => o.id === id)).map(id => ({ id, label: w('fact.bindingPending', { id }) }))];
  return <fieldset className="id-picker"><legend>{label}</legend><div className="id-options">{choices.length === 0 ? <p>{w('fact.bindingEmpty')}</p> : choices.map(o =>
    <label key={o.id}><input type="checkbox" aria-label={w('fact.bindingOption', { label, id: o.id })} checked={ids.includes(o.id)}
      onChange={e => onChange(e.target.checked ? [...ids, o.id] : ids.filter(id => id !== o.id))} />{o.label || o.id}</label>)}</div></fieldset>;
}

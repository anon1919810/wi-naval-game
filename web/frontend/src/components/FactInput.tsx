import { QuantityField } from './QuantityField';
import { number, object, type Raw } from './formModel';
import { declaredSource, TracedField, type TraceFact } from './InputTrace';
import type { Dimension } from './units';

export function EstimateInput({ label, value, onChange }: { label: string; value: unknown; onChange: (value: boolean | null) => void }) {
  return <label className="field-label">估算状态<select aria-label={label} value={value === true ? 'estimate' : value === false ? 'confirmed' : 'unknown'}
    onChange={e => onChange(e.target.value === 'estimate' ? true : e.target.value === 'confirmed' ? false : null)}>
    <option value="unknown">未知</option><option value="estimate">工程估算</option><option value="confirmed">非估算（已声明）</option>
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
      ? <QuantityField label={label} ariaLabel={`${label} 值`} dimension={dimension} storedUnit={storedUnit}
        value={number(entry.value)} kind={kind === 'integer' ? 'integer' : 'signed'} hint={hint}
        onChange={next => onChange({ ...entry, value: next })} />
      : <label className="field-label">值<input aria-label={`${label} 值`} type={kind === 'text' ? 'text' : 'number'} step={kind === 'integer' ? 1 : 'any'}
        placeholder="未知" value={typeof entry.value === 'number' || typeof entry.value === 'string' ? entry.value : ''}
        onChange={e => onChange({ ...entry, value: kind === 'text' ? e.target.value.trim() === '' ? null : e.target.value : number(e.target.value.trim() === '' ? null : Number(e.target.value)) })} />
        {hint && <small>{hint}</small>}</label>}
    <label className="field-label">来源<input aria-label={`${label} 来源`} value={declaredSource(entry.source) ?? ''} placeholder="待补充来源"
      onChange={e => onChange({ ...entry, source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
    <EstimateInput label={`${label} 估算状态`} value={entry.estimate} onChange={estimate => onChange({ ...entry, estimate })} />
  </div>
    </TracedField>
  </fieldset>;
}

export function IdPicker({ label, selected, options, onChange }: { label: string; selected: unknown; options: Array<{ id: string; label?: string }>; onChange: (ids: string[]) => void }) {
  const ids = Array.isArray(selected) ? selected.filter((id): id is string => typeof id === 'string') : [];
  const choices = [...options, ...ids.filter(id => !options.some(o => o.id === id)).map(id => ({ id, label: `${id}（待核对绑定）` }))];
  return <fieldset className="id-picker"><legend>{label}</legend><div className="id-options">{choices.length === 0 ? <p>暂无可绑定条目</p> : choices.map(o =>
    <label key={o.id}><input type="checkbox" aria-label={`${label} ${o.id}`} checked={ids.includes(o.id)}
      onChange={e => onChange(e.target.checked ? [...ids, o.id] : ids.filter(id => id !== o.id))} />{o.label || o.id}</label>)}</div></fieldset>;
}

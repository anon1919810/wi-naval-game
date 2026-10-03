import { fact, inputNumber, sourceText, type Raw } from './formModel';

export function EstimateInput({ label, value, onChange }: { label: string; value: unknown; onChange: (value: boolean | null) => void }) {
  return <label className="field-label">估算状态<select aria-label={label} value={value === true ? 'estimate' : value === false ? 'confirmed' : 'unknown'}
    onChange={e => onChange(e.target.value === 'estimate' ? true : e.target.value === 'confirmed' ? false : null)}>
    <option value="unknown">未知</option><option value="estimate">工程估算</option><option value="confirmed">有据非估算</option>
  </select></label>;
}

export function FactInput({ label, value, kind = 'number', onChange }: {
  label: string; value: unknown; kind?: 'number' | 'integer' | 'text'; onChange: (value: Raw) => void;
}) {
  const entry = fact(value);
  return <fieldset className="fact-input"><legend>{label}</legend><div className="form-grid">
    <label className="field-label">值<input aria-label={`${label} 值`} type={kind === 'text' ? 'text' : 'number'} step={kind === 'integer' ? 1 : 'any'}
      placeholder="未知" value={typeof entry.value === 'number' || typeof entry.value === 'string' ? entry.value : ''}
      onChange={e => onChange({ ...entry, value: kind === 'text' ? e.target.value.trim() === '' ? null : e.target.value : inputNumber(e.target.value) })} /></label>
    <label className="field-label">来源<input aria-label={`${label} 来源`} value={sourceText(entry.source)} placeholder="待补充来源"
      onChange={e => onChange({ ...entry, source: e.target.value.trim() === '' ? null : e.target.value })} /></label>
    <EstimateInput label={`${label} 估算状态`} value={entry.estimate} onChange={estimate => onChange({ ...entry, estimate })} />
  </div></fieldset>;
}

export function IdPicker({ label, selected, options, onChange }: { label: string; selected: unknown; options: Array<{ id: string; label?: string }>; onChange: (ids: string[]) => void }) {
  const ids = Array.isArray(selected) ? selected.filter((id): id is string => typeof id === 'string') : [];
  const choices = [...options, ...ids.filter(id => !options.some(o => o.id === id)).map(id => ({ id, label: `${id}（待核对绑定）` }))];
  return <fieldset className="id-picker"><legend>{label}</legend><div className="id-options">{choices.length === 0 ? <p>暂无可绑定条目</p> : choices.map(o =>
    <label key={o.id}><input type="checkbox" aria-label={`${label} ${o.id}`} checked={ids.includes(o.id)}
      onChange={e => onChange(e.target.checked ? [...ids, o.id] : ids.filter(id => id !== o.id))} />{o.label || o.id}</label>)}</div></fieldset>;
}

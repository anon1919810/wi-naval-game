import { useEffect, useState } from 'react';

import { useWorkspaceCopy } from '../i18n/workspace';
import { useConceptCopy } from '../i18n/concept';
import { number, numericProblem, type NumericDomain } from './formModel';

/**
 * The two declared inputs more than one editor of the same draft needs.
 *
 * They live here rather than inside `ConceptDesignEditor` because the concept
 * screen has a second, later editor — the two-group mount layouts — that must
 * write the same kind of declaration with exactly the same discipline: a typed
 * value is stored as typed, an empty input is stored as unknown rather than as a
 * zero or a plausible default, and a binding may only name what the project
 * already declares. One implementation of that rule is the point of this file.
 */

/**
 * A declared number, stored exactly as typed.
 *
 * Nothing is rounded, truncated or clamped on the way in. A fractional count or
 * a wrong-signed year is *kept* and marked, so the reader can see and correct
 * what they typed and so the server sees the same value the reader did; a silent
 * `Math.trunc` here would store a number nobody entered.
 */
export function DeclaredNumber({ label, value, onChange, hint, kind = 'signed', min, max, unit, ariaLabel }: {
  label: string; value: unknown; onChange: (next: number | null) => void; hint?: string;
  kind?: NumericDomain; min?: number; max?: number; unit?: string; ariaLabel?: string;
}) {
  const w = useWorkspaceCopy();
  const stored = number(value);
  const [text, setText] = useState(() => (stored === null ? '' : String(stored)));
  // Re-derive only when the stored value changed underneath this control (a
  // save, a reload, another row), never while the reader is mid-type.
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setText(stored === null ? '' : String(stored));
  }, [stored, editing]);
  const problem = numericProblem(kind, text, w);
  return <label className="field-label">{label}
    <input type="number" step="any" min={min} max={max} placeholder={w('units.unknown')}
      aria-label={ariaLabel ?? label} aria-invalid={Boolean(problem)}
      value={text}
      onFocus={() => setEditing(true)}
      onBlur={() => setEditing(false)}
      onChange={event => {
        const raw = event.target.value;
        setText(raw);
        if (raw.trim() === '') { onChange(null); return; }
        const typed = Number(raw);
        // Kept verbatim: a wrong value is refused with a message, not rewritten.
        onChange(Number.isFinite(typed) ? typed : null);
      }} />
    {unit && <span className="field-unit">{unit}</span>}
    {hint && <small>{hint}</small>}
    {problem && <span className="field-error" role="alert">{problem}</span>}
  </label>;
}

/** One existing, owned ledger item, chosen by the reader. Never invented. */
export function ItemSelect({ label, value, options, onChange, hint, emptyLabel, ariaLabel }: {
  label: string; value: unknown; options: Array<{ id: string; label: string }>;
  onChange: (next: string | null) => void; hint?: string; emptyLabel?: string; ariaLabel?: string;
}) {
  const c = useConceptCopy();
  const current = typeof value === 'string' ? value : '';
  const listed = options.some(option => option.id === current);
  return <label className="field-label">{label}
    <select aria-label={ariaLabel ?? label} value={current}
      onChange={event => onChange(event.target.value === '' ? null : event.target.value)}>
      <option value="">{emptyLabel ?? c('concept.roles.unallocated')}</option>
      {/* A binding that no longer resolves is still shown, as unresolved, so the
          reader sees what is there rather than watching it vanish. */}
      {current !== '' && !listed && <option value={current}>{current}</option>}
      {options.map(option => <option key={option.id} value={option.id}>{option.label}</option>)}
    </select>
    {hint && <small>{hint}</small>}
  </label>;
}

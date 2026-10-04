import { useEffect, useId, useRef, useState } from 'react';

import { numericProblem, type NumericDomain } from './formModel';
import { useUnits } from './UnitProvider';
import type { Dimension } from './units';

// A controlled numeric input for one declared quantity.
//
// The field is *stored* in its own canonical unit (`thickness_mm` in mm,
// `projectile_mass_kg` in kg, a length in m) and is *shown* in the reader's
// preferred unit. A typed value is converted back into the stored unit before it
// is written, so the project keeps canonical units; unknown stays null, an exact
// zero stays zero, provenance is untouched, and in-progress text such as "12." or
// "-" survives until blur.

export interface QuantityFieldProps {
  /** Visible label; the unit is rendered separately, never embedded in it. */
  label: string;
  /** aria-label of the control; defaults to `label`. */
  ariaLabel?: string;
  /** Accepted alias so call sites can keep the project's `aria-label` style. */
  'aria-label'?: string;
  /** Stored value in `storedUnit`: a finite number, or null/undefined = unknown. */
  value: number | null | undefined;
  dimension: Dimension;
  /** The unit this field is stored in; omit for the dimension's canonical unit. */
  storedUnit?: string;
  kind?: NumericDomain;
  onChange: (storedValue: number | null) => void;
  hint?: string;
  placeholder?: string;
  invalid?: boolean;
  readOnly?: boolean;
  small?: boolean;
  /** Fixed denominator for a declared daily rate; numeric conversion is mass. */
  unitSuffix?: '/day';
}

export function QuantityField(props: QuantityFieldProps) {
  const { label, value, dimension, storedUnit, kind = 'signed', onChange, hint, placeholder, invalid, readOnly, small } = props;
  const ariaLabel = props.ariaLabel ?? props['aria-label'];
  const unitId = useId();
  const visibleLabel = label.replace(/\s*·\s*(mm|cm|m|kg|t|kW|shp|kn|deg|rad)$/, '');
  const units = useUnits();
  const stored = typeof value === 'number' && Number.isFinite(value) ? value : null;
  const [text, setText] = useState(() => units.typed(stored, dimension, storedUnit));
  const [editing, setEditing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // The display unit the current text was produced in. While it is unchanged the
  // text is kept exactly as typed; if the reader's preference switches mid-edit
  // the text is rebased so it can never be read as the previous unit.
  const textUnit = useRef(units.unit(dimension));

  // Re-derive the text whenever the stored value, the field unit or the reader's
  // preference changes outside this control (save, reopen, preference switch).
  useEffect(() => {
    const currentUnit = units.unit(dimension);
    if (editing && currentUnit === textUnit.current) return;
    textUnit.current = currentUnit;
    setText(units.typed(stored, dimension, storedUnit));
  }, [stored, dimension, storedUnit, editing, units]);

  function commit(raw: string) {
    setText(raw);
    textUnit.current = units.unit(dimension);
    if (raw.trim() === '') {
      setProblem(null);
      setEditing(false);
      onChange(null);
      return;
    }
    const typedValue = Number(raw);
    if (!Number.isFinite(typedValue)) {
      setProblem('必须是有限数值');
      return;
    }
    const converted = units.stored(typedValue, dimension, storedUnit) as number;
    // The numeric domain is checked on the stored value, so a field in another
    // unit still refuses out-of-domain input.
    const domain = numericProblem(kind, String(converted));
    if (domain) {
      setProblem(domain);
      return;
    }
    setProblem(null);
    onChange(converted);
  }

  const control = <input type="number" step="any" placeholder={placeholder ?? '未知'}
    aria-label={ariaLabel ?? label} aria-describedby={unitId} aria-invalid={Boolean(invalid || problem)} readOnly={readOnly}
    value={text} onChange={event => commit(event.target.value)} onFocus={() => { setEditing(true); textUnit.current = units.unit(dimension); }}
    onBlur={() => { setEditing(false); textUnit.current = units.unit(dimension); setText(units.typed(stored, dimension, storedUnit)); }} />;
  const suffix = <span id={unitId} className="field-unit">{units.unit(dimension)}{props.unitSuffix}</span>;
  const message = problem ? <span className="field-error" role="alert">{problem}</span> : null;
  if (small) return <label className="field-label field-label--inline">{visibleLabel}{control}{suffix}{message}</label>;
  return <label className="field-label">{visibleLabel}{control}{suffix}{hint && <small>{hint}</small>}{message}</label>;
}

export interface QuantityListProps {
  label: string;
  /** Canonical stored samples; an empty array means "not requested". */
  value: number[];
  dimension: Dimension;
  storedUnit?: string;
  onChange: (values: number[]) => void;
  hint?: string;
  placeholder?: string;
}

/**
 * A list of samples (speeds, remaining-GZ angles) typed in the reader's unit and
 * stored canonically. Order and count are preserved exactly; an unparsable entry
 * invalid tokens mark the transient request invalid, preventing submission of
 * stale samples. The marker is rejected by request builders, never persisted.
 */
export function QuantityListField({ label, value, dimension, storedUnit, onChange, hint, placeholder }: QuantityListProps) {
  const units = useUnits();
  const unitId = useId();
  const shown = value.map(sample => units.value(sample, dimension, storedUnit));
  const [text, setText] = useState(() => shown.filter(item => item !== null).join(', '));
  const [editing, setEditing] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const textUnit = useRef(units.unit(dimension));
  const signature = `${shown.join(',')}|${units.unit(dimension)}`;

  useEffect(() => {
    if (editing && textUnit.current === units.unit(dimension)) return;
    textUnit.current = units.unit(dimension);
    setText(shown.filter(item => item !== null).join(', '));
  }, [signature, editing, units, dimension]);

  function commit(raw: string) {
    setText(raw);
    textUnit.current = units.unit(dimension);
    const tokens = raw.split(/[\s,，]+/).filter(Boolean);
    const converted: number[] = [];
    for (const token of tokens) {
      const typed = Number(token);
      if (!Number.isFinite(typed)) { setProblem('采样必须是有限数值'); onChange([Number.NaN]); return; }
      converted.push(units.stored(typed, dimension, storedUnit) as number);
    }
    setProblem(null);
    onChange(converted);
  }

  return <label className="field-label">{label}
    <input type="text" placeholder={placeholder} aria-label={label} aria-describedby={unitId} aria-invalid={Boolean(problem)}
      value={text} onChange={event => commit(event.target.value)} onFocus={() => { setEditing(true); textUnit.current = units.unit(dimension); }}
      onBlur={() => { setEditing(false); textUnit.current = units.unit(dimension); setText(shown.filter(item => item !== null).join(', ')); }} />
    <span id={unitId} className="field-unit">{units.unit(dimension)}</span>
    {hint && <small>{hint}</small>}
    {problem && <span className="field-error" role="alert">{problem}</span>}
  </label>;
}

/** Read-only displayed quantity for dense rows. */
export function QuantityReadout({ label, value, dimension, storedUnit }: {
  label: string; value: unknown; dimension: Dimension; storedUnit?: string;
}) {
  const units = useUnits();
  return <label className="field-label field-label--inline">{label}
    <input type="text" readOnly value={units.text(value, dimension, storedUnit)} />
  </label>;
}

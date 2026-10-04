import { useUnits } from './UnitProvider';
import type { Dimension } from './units';

interface FactFieldProps {
  label: string;
  value: number | string | null | undefined;
  /** Canonical unit label, used when no convertible dimension is declared. */
  unit?: string;
  /** Reading dimension; when present the stored value follows the preference. */
  dimension?: Dimension;
  /** The unit this value is stored in; omit for the dimension's canonical unit. */
  storedUnit?: string;
  status?: 'known' | 'estimate' | 'unknown' | 'unavailable';
  source?: string | null;
}

export function FactField({ label, value, unit = '', dimension, storedUnit, status = 'known', source }: FactFieldProps) {
  const units = useUnits();
  const missing = value === null || value === undefined || status === 'unknown';
  const shown = missing
    ? '未知'
    : dimension
      ? units.text(value, dimension, storedUnit)
      : `${value}${unit ? ` ${unit}` : ''}`;
  return <div className={`fact-field fact-field--${status}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{shown}</strong>
    <span className="fact-meta">{status === 'estimate' ? '估算 · ' : ''}{source || (missing ? '缺少输入或来源' : '查看来源')}</span>
  </div>;
}
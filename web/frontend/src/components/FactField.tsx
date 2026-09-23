interface FactFieldProps {
  label: string;
  value: number | string | null | undefined;
  unit?: string;
  status?: 'known' | 'estimate' | 'unknown' | 'unavailable';
  source?: string | null;
}

export function FactField({ label, value, unit = '', status = 'known', source }: FactFieldProps) {
  const missing = value === null || value === undefined || status === 'unknown';
  return <div className={`fact-field fact-field--${status}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{missing ? '未知' : `${value}${unit ? ` ${unit}` : ''}`}</strong>
    <span className="fact-meta">{status === 'estimate' ? '估算 · ' : ''}{source || (missing ? '缺少输入或来源' : '查看来源')}</span>
  </div>;
}

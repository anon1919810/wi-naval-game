import { reportReadings, type ReportReading } from './resultReading';
import { useUnits } from './UnitProvider';
import { formatNumber } from './units';
import type { AnalysisResult } from '../types';

/**
 * The report's first screen: what this saved run actually says.
 *
 * The six readings are projections of six saved paths, so a value is here only
 * because the run stored it: no number is recomputed, averaged or interpolated,
 * and a stage that did not deliver one keeps its reason instead of a zero or a
 * borrowed figure. A true zero is shown as a value, an unknown field as 未知.
 *
 * Dimensions follow the reader's unit choice on this page only. A range has no
 * convertible reader unit and stays in nmi; the stored snapshot, the
 * fingerprints and the exports are untouched by any of it.
 */
export function ReportReadings({ result }: { result: AnalysisResult }) {
  const units = useUnits();
  return <div className="report-readings">{reportReadings(result).map(reading =>
    <Reading key={reading.key} reading={reading} units={units} />)}</div>;
}

/**
 * The projection states a missing reading in field terms, which belongs in a test
 * rather than in front of the reader. Only those two generated messages are said
 * in reader terms here: a saved stage reason is the run's own wording about why a
 * stage produced nothing, and it is passed through untouched.
 */
function readerReason(reading: ReportReading): string | null {
  const reason = reading.reason;
  if (!reason || reading.state !== 'unknown') return reason;
  if (/^保存结果中 .+ 为 null$/.test(reason)) return '本次保存结果将此读数标为未知。';
  if (/^保存结果中 .+ 不是有限数字$/.test(reason)) return '本次保存结果未给出有效数字。';
  return reason;
}

function Reading({ reading, units }: { reading: ReportReading; units: ReturnType<typeof useUnits> }) {
  const shown = reading.state !== 'known' || reading.value === null
    ? '未知'
    : reading.dimension
      ? units.text(reading.value, reading.dimension, reading.storedUnit)
      : `${formatNumber(reading.value)}${reading.canonicalUnit ? ` ${reading.canonicalUnit}` : ''}`;
  const reason = readerReason(reading);
  return <div className={`report-reading report-reading--${reading.state}`}>
    <span className="report-reading-label">{reading.label}</span>
    <strong className="report-reading-value">{shown}</strong>
    {reading.context && <span className="report-reading-context">{reading.context}</span>}
    {/* A missing reading always carries why; a long reason wraps rather than
        being cut off, because it is the only thing the reader gets. */}
    {reason && <span className="report-reading-reason">{reason}</span>}
    {reading.source && <span className="report-reading-source" title={reading.source}>来源 {reading.source}</span>}
    {reading.estimate === true && <span className="report-reading-estimate">工程估算</span>}
    {reading.estimate === false && <span className="report-reading-estimate">非估算</span>}
  </div>;
}
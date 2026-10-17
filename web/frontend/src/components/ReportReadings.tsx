import { reportReadings, type ReportReading } from './resultReading';
import { nativePrimaryReadings } from './nativeReportReadings';
import { useUnits } from './UnitProvider';
import { formatNumber } from './units';
import { useWorkspaceCopy } from '../i18n/workspace';
import { useLanguage } from '../portfolio/LanguageProvider';
import type { AnalysisResult } from '../types';

/**
 * The report's first screen: what this saved run actually says.
 *
 * When the run requested the native ship design, the summary is that frozen
 * result — its balance and its engine and performance readings — and the physical
 * cards of stages the run never asked for are not printed at all. The physical
 * readings of stages the run *did* ask for are still appended after them. Any
 * other run keeps exactly the eight physical readings it always had.
 *
 * Every reading is a projection of a saved path, so a value is here only because
 * the run stored it: no number is recomputed, averaged or interpolated, and a
 * stage that did not deliver one keeps its reason instead of a zero or a borrowed
 * figure. A true zero is shown as a value, an unknown field as unknown.
 *
 * Dimensions follow the reader's unit choice on this page only. A range, a source
 * horsepower and the empirical stability score have no convertible reader unit
 * and keep the unit the source saved; the stored snapshot, the fingerprints and
 * the exports are untouched by any of it.
 */
export function ReportReadings({ result }: { result: AnalysisResult }) {
  const { language } = useLanguage();
  const units = useUnits();
  const readings = nativePrimaryReadings(result, language) ?? reportReadings(result, language);
  return <div className="report-readings">{readings.map(reading =>
    <Reading key={reading.key} reading={reading} units={units} />)}</div>;
}

/**
 * The projection states a missing reading in field terms, which belongs in a test
 * rather than in front of the reader. Only those two generated messages are said
 * in reader terms here: a saved stage reason is the run's own wording about why a
 * stage produced nothing, and it is passed through untouched.
 */
function readerReason(w: (key: any, params?: any) => string, reading: ReportReading): string | null {
  const reason = reading.reason;
  if (!reason || reading.state !== 'unknown') return reason;
  if (/^保存结果中 .+ 为 null$/.test(reason)) return w('reading.reason.null');
  if (/^保存结果中 .+ 不是有限数字$/.test(reason)) return w('reading.reason.notFinite');
  return reason;
}

function Reading({ reading, units }: { reading: ReportReading; units: ReturnType<typeof useUnits> }) {
  const w = useWorkspaceCopy();
  const shown = reading.state !== 'known' || reading.value === null
    ? w('reading.unknown')
    : reading.dimension
      ? units.text(reading.value, reading.dimension, reading.storedUnit)
      : `${formatNumber(reading.value)}${reading.canonicalUnit ? ` ${reading.canonicalUnit}` : ''}`;
  const reason = readerReason(w, reading);
  return <div className={`report-reading report-reading--${reading.state}`}>
    <span className="report-reading-label">{reading.label}</span>
    <strong className="report-reading-value">{shown}</strong>
    {reading.context && <span className="report-reading-context">{reading.context}</span>}
    {/* A missing reading always carries why; a long reason wraps rather than
        being cut off, because it is the only thing the reader gets. */}
    {reason && <span className="report-reading-reason">{reason}</span>}
    {reading.source && <span className="report-reading-source" title={reading.source}>{w('reading.source', { source: reading.source })}</span>}
    {reading.estimate === true && <span className="report-reading-estimate">{w('reading.estimate')}</span>}
    {reading.estimate === false && <span className="report-reading-estimate">{w('reading.notEstimate')}</span>}
  </div>;
}
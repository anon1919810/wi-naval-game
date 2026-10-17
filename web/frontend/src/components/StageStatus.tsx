import { useState } from 'react';
import type { StageEnvelope, StageStatus as StageStatusCode } from '../types';
import { DiagnosticAction, type GuidanceContext } from './DiagnosticAction';
import { ConceptComponentReadings } from './ConceptComponentReadings';
import { Sps3b3Readings } from './Sps3b3Readings';
import { FloodingResults } from './FloodingResults';
import { StabilityPlot } from './StabilityPlot';
import { useUnits } from './UnitProvider';
import { classifyKey, type Dimension, type QuantityKey } from './units';
import { DATA_LABEL_ORDER, useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';
import { numberLocale as numberLocaleFor, useNumberLocale } from '../i18n/format';
import { useLanguage } from '../portfolio/LanguageProvider';

/**
 * The canonical stage order, and the only stage names that may be sorted by it.
 *
 * These are API keys, not words: a stage name is whatever the coordinator wrote
 * into the result, so the order and the key set are data and never change with
 * the language. The display name is looked up separately, below.
 */
export const STAGE_ORDER = [
  'loading', 'systems', 'l0', 'geometry', 'equilibrium', 'hydrostatics', 'gz', 'deck',
  'hydrostatic_curve', 'bonjean', 'resistance', 'propulsion', 'endurance', 'historical', 'flooding', 'design_balance', 'ship_design', 'sps_compat',
];

/** A stage name in one language. An unknown key keeps its own name. */
export function stageLabel(w: (key: WorkspaceKey) => string, name: string): string {
  if (name==='sps_compat') return 'SpringSharp 3b3';
  return w(`stage.${name}` as WorkspaceKey);
}

/** A stage status in one language. */
export function stageStatusLabel(w: (key: WorkspaceKey) => string, status: StageStatusCode): string {
  return w(`status.${status}` as WorkspaceKey);
}

/**
 * A result datum's display name, when this interface knows the key.
 *
 * An unrecognised key falls through to the key itself, exactly as it always did:
 * the raw payload stays readable rather than being hidden behind a guess.
 */
export function dataLabel(w: (key: WorkspaceKey) => string, key: string): string {
  const label = w(`data.${key}` as WorkspaceKey);
  return label === `data.${key}` ? key : label;
}

// A severe diagnostic is a finding, not a footnote: it is shown in place. A
// warning that blocks the stage counts as severe even though its severity says
// "warning", because it decides whether the number may be shown at all.
const SEVERE = new Set(['error', 'critical', 'severe', 'fatal']);

function isBlocking(item: StageEnvelope['diagnostics'][number]): boolean {
  return (item as { blocking?: unknown }).blocking === true;
}

// Units are only inferred from reliable, unambiguous key names: a force in kN,
// a time in s, a density in kg/m³ and every other canonical-only quantity keeps
// its stored label and value instead of borrowing a convertible suffix.
function inferredUnit(key: string): { label: string; dimension?: Dimension; storedUnit?: string } | null {
  const kind: QuantityKey | null = classifyKey(key);
  if (kind) return { label: '', dimension: kind.dimension, storedUnit: kind.storedUnit };
  if (key === 'power_design_shp' || key === 'power_trial_shp') return { label: 'shp' };
  // Densities, viscosities and rates keep their canonical compound unit.
  if (key === 'rho_t_m3') return { label: 't/m³' };
  if (key.endsWith('_kg_m3')) return { label: 'kg/m³' };
  if (key.endsWith('_t_m3')) return { label: 't/m³' };
  if (key.endsWith('_m2_s')) return { label: 'm²/s' };
  if (key.endsWith('_t_per_day')) return { label: 't/day' };
  if (key.endsWith('_m3_s') || key.endsWith('_m3_per_s')) return { label: 'm³/s' };
  if (key.endsWith('_kg')) return { label: 'kg' };
  if (key.endsWith('_kn')) return { label: 'kN' };
  if (key.endsWith('_s')) return { label: 's' };
  if (key.startsWith('pct_')) return { label: '%' };
  if (key.endsWith('_nm')) return { label: 'nmi' };
  if (key.endsWith('_pa')) return { label: 'Pa' };
  return null;
}

function display(w: (key: WorkspaceKey) => string, value: unknown, locale: string): string {
  if (value === null || value === undefined) return w('units.unknown');
  if (typeof value === 'number') {
    if (value !== 0 && Math.abs(value) < 0.0000005) return w('units.approxZero');
    return new Intl.NumberFormat(locale, { maximumFractionDigits: 6 }).format(Object.is(value, -0) ? 0 : value);
  }
  if (typeof value === 'boolean') return value ? w('units.yes') : w('units.no');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

interface Datum { key: string; value: unknown; unit?: string; dimension?: Dimension; storedUnit?: string; source?: string; estimate?: boolean }

function datumFor(key: string, value: unknown): Datum {
  const unit = inferredUnit(key);
  return { key, value, unit: unit?.dimension ? undefined : unit?.label, dimension: unit?.dimension, storedUnit: unit?.storedUnit };
}

/**
 * Every numeric datum a stage reported, in the order the payload declares.
 *
 * This used to stop at eight, which silently hid whichever metrics happened to
 * come after the eighth in payload order — the reader could not tell a stage
 * with eight metrics from one with twenty. The card is a per-stage group
 * already, and `dataLabel` names what the registry knows while anything else
 * keeps its raw key, so showing them all is both honest and bounded by the
 * payload itself.
 *
 * `quotable` narrows that one exception: a key that only repeats a nested
 * result's own scalar is quoted only when that nested result declared itself
 * completed. The card already applies the parent stage's gate before it calls
 * this, so this is the second half of the same rule, not a new one.
 */
function extract(data: Record<string, unknown> | null, quotable: (subkey: string) => boolean = () => true): Datum[] {
  if (!data) return [];
  const found: Datum[] = [];
  for (const [key, value] of Object.entries(data)) {
    if (key === 'diagnostics' || key === 'assumptions' || key === 'method_version') continue;
    if (typeof value === 'number' || value === null) {
      found.push(datumFor(key, value));
    } else if (value && typeof value === 'object' && !Array.isArray(value)) {
      const row = value as Record<string, unknown>;
      if ('value' in row && (typeof row.value === 'number' || row.value === null)) {
        const declared = typeof row.unit === 'string' ? { label: row.unit } : inferredUnit(key);
        found.push({ key, value: row.value, unit: declared?.dimension ? undefined : declared?.label,
          dimension: declared?.dimension, storedUnit: declared?.storedUnit,
          source: typeof row.source === 'string' ? row.source : undefined, estimate: row.estimate === true });
      } else if (key === 'values') {
        for (const [subkey, subvalue] of Object.entries(row)) {
          if (!quotable(subkey)) continue;
          if (typeof subvalue === 'number' || subvalue === null) found.push(datumFor(subkey, subvalue));
        }
      }
    }
  }
  // Known metrics in the registry's fixed order, so the same stage of two runs
  // lines up; anything the registry does not know keeps payload order behind it.
  const rank = (key: string) => {
    const index = DATA_LABEL_ORDER.indexOf(key);
    return index === -1 ? DATA_LABEL_ORDER.length : index;
  };
  return found
    .map((datum, index) => ({ datum, index }))
    .sort((left, right) => rank(left.datum.key) - rank(right.datum.key) || left.index - right.index)
    .map(entry => entry.datum);
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

// A table cell that follows the reader's units when the key is a reliable
// quantity name, and keeps the canonical unit otherwise (for example kN).
function tableValue(w: (key: WorkspaceKey) => string, locale: string, units: ReturnType<typeof useUnits>, key: string, value: unknown, canonicalUnit?: string): string {
  if (value === null || value === undefined) return w('units.unknown');
  const kind = classifyKey(key);
  if (kind) return units.keyed(key, value);
  return `${display(w, value, locale)}${canonicalUnit ? ` ${canonicalUnit}` : ''}`;
}

function ResistanceTables({ data }: { data: Record<string, unknown> }) {
  const w = useWorkspaceCopy();
  const { language } = useLanguage();
  const locale = numberLocaleFor(language);
  const units = useUnits();
  const rows = Array.isArray(data.rows) ? data.rows.map(record) : [];
  const powerRows = Array.isArray(data.power_rows) ? data.power_rows.map(record) : [];
  const validity = record(data.validity);
  const scenario = record(data.scenario);
  if (rows.length === 0 && powerRows.length === 0) return null;
  const powerUnit = units.unit('power');
  const meaning = (row: Record<string, unknown>, withRange: boolean): string =>
    (row.complete === false ? w('resistance.cell.incomplete')
      : withRange && row.model_applicable === false ? w('resistance.cell.outOfRange')
      : row.primary_result === false ? w('resistance.cell.nonPrimary')
      : w('resistance.cell.value')) + (row.estimate === true ? ` · ${w('resistance.estimated')}` : '');
  return <div className="resistance-results">
    <p className="result-context">{w('resistance.method', { method: display(w, data.method, locale) })} · {data.estimate === true ? w('resistance.estimated') : w('resistance.sourceInInputs')}
      {validity.model_applicable === false && ` · ${w('resistance.outOfRange')}`}
      {data.primary_result === false && ` · ${w('resistance.nonPrimary')}`}</p>
    {typeof scenario.source === 'string' && <p className="result-source">{w('resistance.source', { source: scenario.source })}</p>}
    {rows.length > 0 && <div className="stage-table-scroll"><table className="stage-table"><caption>{w('resistance.caption.main')}</caption><thead><tr><th>{w('resistance.th.speed')}</th><th>{w('resistance.th.total')}</th><th>{w('resistance.th.effective')}</th><th>{w('resistance.th.meaning')}</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.speed_kn ?? 'unknown'}-${index}`}>
      <td>{tableValue(w, locale, units, 'speed_kn', row.speed_kn)}</td><td>{tableValue(w, locale, units, 'total_resistance_kn', row.total_resistance_kn, 'kN')}</td>
      <td>{tableValue(w, locale, units, 'effective_power_kw', row.effective_power_kw)}</td>
      <td>{meaning(row, true)}</td>
    </tr>)}</tbody></table></div>}
    {powerRows.length > 0 && <div className="stage-table-scroll"><table className="stage-table"><caption>{w('resistance.caption.power')}</caption><thead><tr><th>{w('resistance.th.speed')}</th><th>{w('resistance.th.qpc')}</th><th>{w('resistance.th.shaft')}</th><th>{w('resistance.th.meaning')}</th></tr></thead><tbody>{powerRows.map((row, index) => {
      const qpc = record(row.qpc);
      return <tr key={`${row.speed_kn ?? 'unknown'}-${index}`}>
        <td>{tableValue(w, locale, units, 'speed_kn', row.speed_kn)}</td><td>{tableValue(w, locale, units, 'qpc', qpc.value)}{typeof qpc.source === 'string' && <small>{qpc.source}</small>}</td>
        {/* One shaft-power column in the reader's unit; the stored kW and shp
            values are the same quantity and must not be shown side by side. */}
        <td>{tableValue(w, locale, units, 'shaft_power_kw', row.shaft_power_kw)}<small>{powerUnit}</small></td>
        <td>{meaning(row, false)}</td>
      </tr>;
    })}</tbody></table></div>}
  </div>;
}

/**
 * One finding line. The message reads once and every piece of evidence the saved
 * result attached to it stays on the line: the code, the path, the source path
 * and, when the page knows which project and run it is showing, a way to follow
 * the path into that project. The action is additive — it never replaces or
 * summarises the finding, and it is absent when the path leads nowhere
 * editable, so a fabricated link can never appear.
 */
function DiagnosticLine({ item, guidance, repeat }: {
  item: StageEnvelope['diagnostics'][number]; guidance: GuidanceContext | null; repeat?: boolean;
}) {
  const w = useWorkspaceCopy();
  return <p className={repeat ? 'stage-diagnostics-repeat' : undefined}>
    <strong>{repeat
      ? (item.code
        ? w('stage.diagnostics.repeat', { code: item.code })
        : w('stage.diagnostics.repeatFallback'))
      : (item.message ?? item.code)}</strong>
    {!repeat && item.code && item.message && <small>{item.code}</small>}
    {item.path && <code>{item.path}</code>}
    {item.source_path && item.source_path !== item.path && <small>{w('stage.diagnostics.source', { path: item.source_path })}</small>}
    <DiagnosticAction diagnostic={item} context={guidance} project={guidance?.snapshot ?? null} />
  </p>;
}

export function StageStatus({ name, stage, guidance }: {
  name: string; stage: StageEnvelope; guidance?: GuidanceContext | null;
}) {
  const w = useWorkspaceCopy();
  const locale = useNumberLocale();
  const [rawOpen, setRawOpen] = useState(false);
  const units = useUnits();
  // Only a requested stage that actually finished may show plain numbers. A
  // blocked or unrequested envelope may still hold partial values, and those
  // are not results: they stay reachable in the raw data, never in the reading
  // area.
  const delivered = stage.requested === true && stage.status === 'completed';
  // `values.equilibrium_gm_t_m` is a saved alias of
  // `small_angle_stability.equilibrium_gm_m`, so it is quoted only when that
  // nested result declared itself completed. A residual scalar beside an
  // unavailable nested result stays in the raw data, never in the readings.
  const smallAngle = record(record(stage.data).small_angle_stability);
  const quotable = (subkey: string) =>
    subkey !== 'equilibrium_gm_t_m' || (smallAngle.status === 'completed'
      && typeof smallAngle.equilibrium_gm_m === 'number'
      && Number.isFinite(smallAngle.equilibrium_gm_m));
  const values = delivered ? extract(stage.data, quotable) : [];
  const diagnostics = stage.diagnostics ?? [];
  const serious = (item: StageEnvelope['diagnostics'][number]) => SEVERE.has(String(item.severity ?? '')) || isBlocking(item);
  const severe = diagnostics.filter(serious);
  // A diagnostic that repeats the stage reason is the reason, not a second
  // finding. Its message is not printed twice, but its code, path and source
  // path stay in the list, so no evidence is lost before it can be printed.
  const repeats = diagnostics.filter(item => !serious(item) && item.message === stage.reason);
  const ordinary = diagnostics.filter(item => !serious(item) && item.message !== stage.reason);
  const detailCount = ordinary.length + repeats.length;
  const reasonAlreadyVisible = severe.some(item => item.message === stage.reason);
  return <article id={`stage-${name}`} className={`stage-card stage-card--${stage.status}`}>
    <div className="stage-card-header"><div><span className="section-kicker">{name.toUpperCase()}</span><h3 tabIndex={-1}>{stageLabel(w, name)}</h3></div><span className={`stage-pill stage-pill--${stage.status}`}>{stageStatusLabel(w, stage.status)}</span></div>
    {/* The stage's own reason is the core's saved text and stays verbatim: a
        localized summary of the message a reader is here to check would be a
        claim about the message rather than the message. */}
    {stage.reason && stage.status !== 'not_requested' && !reasonAlreadyVisible && <p className="stage-reason">{stage.reason}</p>}
    {stage.status === 'not_requested' && <p className="stage-reason">{w('stage.card.reasonNotRequested')}</p>}
    {severe.length > 0 && <div className="stage-diagnostics-open" role="alert">
      <strong>{w('stage.card.severe', { count: severe.length })}</strong>
      {severe.map((item, index) => <DiagnosticLine key={`${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} />)}
    </div>}
    {values.length > 0 && <div className="stage-values">{values.map(item => {
      const shown = item.dimension ? units.text(item.value, item.dimension, item.storedUnit) : display(w, item.value, locale);
      return <div className="stage-value" key={item.key}><span title={item.key}>{dataLabel(w, item.key)}</span>
        <strong>{shown}{!item.dimension && item.value !== null && item.unit ? ` ${item.unit}` : ''}</strong>
        {item.source && <small>{item.source}</small>}{item.estimate && <em>{w('stage.card.estimate')}</em>}</div>;
    })}</div>}
    {name === 'resistance' && stage.requested && stage.data && (delivered || stage.status === 'model_limit') && <>
      {stage.status === 'model_limit' && <p className="stage-reason">{w('stage.card.modelLimitNote')}</p>}
      <ResistanceTables data={stage.data} />
    </>}
    {/* The GZ curve belongs to its own stage, and only a finished one carries a
        curve worth drawing. */}
    {name === 'gz' && delivered && <StabilityPlot stage={stage} />}
    {name === 'flooding' && stage.requested && stage.data && typeof record(stage.data).status === 'string' && <FloodingResults data={record(stage.data)} />}
    {/* The concept screen's own optional component readings — fixed armour
        regions, two-group layouts and the empirical cost — are nested results
        that would otherwise exist only in the raw payload. They use the same
        projection as the workbench, under this card's own gate: only a requested
        envelope that completed may show them, so a failed or canceled parent
        stage keeps its diagnostics and evidence instead of residual numbers. */}
    {name === 'design_balance' && <ConceptComponentReadings data={stage.data} envelope={stage} policy="report" />}
    {name === 'sps_compat' && stage.requested && delivered && <Sps3b3Readings data={stage.data} runId={guidance?.runId} />}
    {/* A native ship-design run may legitimately finish partial while the ledger
        still reports roles that need binding. The source report and its downloads
        are immutable and complete in either case, so they are shown for a partial
        envelope too — the binding work is a ledger note, never a missing report.
        The ledger state is still shown as partial. */}
    {name === 'ship_design' && stage.requested && (delivered || stage.status === 'partial') && <Sps3b3Readings data={stage.data} runId={guidance?.runId} variant="native" />}
    {detailCount > 0 && <details className="stage-diagnostics"><summary>{w('stage.diagnostics.summary', { count: detailCount })}</summary><div>{ordinary.map((item, index) => <DiagnosticLine key={`${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} />)}</div>
      {repeats.map((item, index) => <DiagnosticLine key={`repeat-${item.code ?? ''}-${index}`} item={item} guidance={guidance ?? null} repeat />)}</details>}
    {Object.keys(stage.method_versions).length > 0 && <p className="stage-method">{w('stage.card.method', { value: Object.entries(stage.method_versions).map(([key, value]) => `${key}: ${display(w, value, locale)}`).join(' / ') })}</p>}
    {stage.assumptions.length > 0 && <details className="stage-assumptions"><summary>{w('stage.card.assumptions')}</summary><pre>{JSON.stringify(stage.assumptions, null, 2)}</pre></details>}
    {/* The raw payload stays reachable on screen and stays off paper: a saved
        stage can carry megabytes of iteration and geometry arrays. */}
    {stage.data && <details className="stage-assumptions stage-raw-data no-print" onToggle={event => setRawOpen(event.currentTarget.open)}><summary>{w('stage.card.raw')}</summary>{rawOpen && <pre>{JSON.stringify(stage.data, null, 2)}</pre>}</details>}
  </article>;
}

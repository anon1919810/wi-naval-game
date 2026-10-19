import { Fragment, useMemo, useState } from 'react';

import { chapterOf, type Chapter } from './ProjectNav';
import { useUnits } from './UnitProvider';
import { compareDraft, compareFrozen, frozenNativeSides, requestsNativeDesign, type ChangedInput, type ChangedRole, type DesignFeedback as Feedback, type DraftSide, type FeedbackLabels } from './designFeedbackModel';
import { configChangeRows, configGroupLabel, type ConfigGroup, type ConfigRow } from './designConfigModel';
import { resolvedUnit, shipDesignOf, sourceViewOfShipDesign, type Sps3b3Catalogue } from './sps3b3Model';
import { useDesignCatalogue } from './useDesignCatalogue';
import { formatNumber } from './units';
import { useDesignFeedbackCopy } from '../i18n/designFeedback';
import { useShipDesignRoleLabel } from '../i18n/shipDesign';
import { sps3b3FieldLabel, useSps3b3Copy } from '../i18n/sps3b3';
import { useVesselOverviewCopy } from '../i18n/vesselOverview';
import { useWorkspaceCopy } from '../i18n/workspace';
import { useLanguage } from '../portfolio/LanguageProvider';
import '../styles/designFeedback.css';
import type { AnalysisResult, ProjectDocument } from '../types';

/**
 * The draft feedback panel, and the report's frozen native summary.
 *
 * Both surfaces print the same body: a direction stated in words, the sixteen
 * readings with their own units, the changed declared inputs and the changed
 * ledger roles. The workbench variant names its two sides Saved and Draft and
 * offers a retry when the saved revision could not be read; the report variant
 * names them Current and Comparison and never reads a live preview.
 *
 * Every label comes from the same two existing sources the native editor uses:
 * `sps3b3FieldLabel` for the recovered register name and `resolvedUnit` for the
 * unit each side's own declaration resolves. An imperial → metric change is
 * therefore printed as the two raw values with their two units and an explicit
 * unit change, never as one unit imposed on both and never as a converted delta.
 *
 * Nothing here converts a reading that has no reader dimension: mass and speed
 * follow the reader's display preference, while source horsepower, range,
 * empirical stability and relative hull strength keep the unit the source saved.
 * A value that is missing is the unknown marker, never a zero.
 */

export interface DesignFeedbackProps {
  before: DraftSide;
  after: DraftSide;
  /**
   * The workbench's already-loaded catalogue. The report has none and reads its
   * own read-only copy; a missing catalogue leaves the recovered names as keys.
   */
  catalogue?: Sps3b3Catalogue | null;
  onRetry?: () => void;
  onOpenChapter?: (chapter: string) => void;
}

/** The reader-facing labels both surfaces share, resolved per side. */
function useFieldLabels(catalogue: Sps3b3Catalogue | null, before: ProjectDocument | null,
  after: ProjectDocument | null): FeedbackLabels {
  const sps = useSps3b3Copy();
  const role = useShipDesignRoleLabel();
  return useMemo(() => {
    const beforeDesign = shipDesignOf(before);
    const afterDesign = shipDesignOf(after);
    const resolve = (key: string, side: 'before' | 'after') => {
      const field = catalogue?.byName[key];
      if (!field) return null;
      const design = side === 'before' ? beforeDesign : afterDesign;
      return {
        label: sps3b3FieldLabel(sps, field.name, field.label),
        unit: resolvedUnit(field, design ? sourceViewOfShipDesign(design) : null),
        page: field.page ?? null,
      };
    };
    return { field: resolve, role: (name: string) => role(name) };
  }, [catalogue, before, after, sps, role]);
}

/** The workbench reading: the draft against the saved revision. */
export function DesignFeedback({ before, after, catalogue = null, onRetry, onOpenChapter }: DesignFeedbackProps) {
  const language = useLanguage().language;
  const labels = useFieldLabels(catalogue, before.project, after.project);
  const feedback = useMemo(() => compareDraft(before, after, language, labels), [before, after, language, labels]);
  return <FeedbackBody feedback={feedback} variant="draft"
    onRetry={before.state === 'failed' ? onRetry : undefined} onOpenChapter={onOpenChapter} />;
}

export interface FrozenDesignSummaryProps {
  current: AnalysisResult;
  comparison: AnalysisResult;
  currentLabel: string;
  comparisonLabel: string;
  /** The report's own identity verdict for each run, already applied to the table. */
  currentValid?: boolean;
  comparisonValid?: boolean;
  /**
   * A catalogue the caller already holds. `undefined` reads the cached read-only
   * copy; `null` declares that none is available, so no read is attempted.
   */
  catalogue?: Sps3b3Catalogue | null;
  onOpenChapter?: (chapter: string) => void;
}

/**
 * The report reading: the comparison run against the current run, both frozen.
 *
 * Renders nothing when neither run carries a native design stage, so a report
 * with no native design keeps exactly the comparison it always had. The only
 * network read is the read-only field catalogue, and only when a native stage is
 * present; no preview of either run is fetched.
 */
export function FrozenDesignSummary({ current, comparison, currentLabel, comparisonLabel,
  currentValid, comparisonValid, catalogue: supplied, onOpenChapter }: FrozenDesignSummaryProps) {
  const language = useLanguage().language;
  const wanted = requestsNativeDesign(current) || requestsNativeDesign(comparison);
  const fetched = useDesignCatalogue(wanted && supplied === undefined);
  const catalogue = supplied === undefined ? fetched : supplied;
  const labels = useFieldLabels(catalogue, current.input_snapshot ?? null, comparison.input_snapshot ?? null);
  const feedback = useMemo(() => compareFrozen(current, comparison, language, labels, { currentValid, comparisonValid }),
    [current, comparison, language, labels, currentValid, comparisonValid]);
  // The configuration rows reuse the very same gate: they only exist when both
  // sides are readable native results that the summary itself will quote.
  const pair = useMemo(() => frozenNativeSides(current, comparison, { currentValid, comparisonValid }),
    [current, comparison, currentValid, comparisonValid]);
  const configRows = useMemo(() => pair.comparable && pair.current.result && pair.comparison.result
    ? configChangeRows(pair.current.result, pair.comparison.result, language) : null,
    [pair, language]);
  if (!feedback) return null;
  return <FeedbackBody feedback={feedback} variant="frozen" configRows={configRows}
    currentLabel={currentLabel} comparisonLabel={comparisonLabel} />;
}

/** Every visible value a reading cell can hold, in one reader's units. */
function readingText(value: number | null, reading: Feedback['readings'][number], units: ReturnType<typeof useUnits>, unknown: string): string {
  if (value === null) return unknown;
  if (reading.dimension) return units.text(value, reading.dimension, reading.storedUnit);
  return `${formatNumber(value)}${reading.canonicalUnit ? ` ${reading.canonicalUnit}` : ''}`;
}

function signedText(value: number, reading: Feedback['readings'][number], units: ReturnType<typeof useUnits>): string {
  const sign = value > 0 ? '+' : value < 0 ? '−' : '';
  const magnitude = Math.abs(value);
  if (reading.dimension) return `${sign}${units.text(magnitude, reading.dimension, reading.storedUnit)}`;
  return `${sign}${formatNumber(magnitude)}${reading.canonicalUnit ? ` ${reading.canonicalUnit}` : ''}`;
}

/**
 * A changed input's raw value. A number keeps the unit its own side resolves for
 * the field; an object stays text. No conversion is applied across a scale change.
 */
function inputText(w: ReturnType<typeof useWorkspaceCopy>, value: unknown, unit: string | null): string {
  if (value === null || value === undefined) return w('units.unknown');
  if (typeof value === 'number') return `${formatNumber(value)}${unit ? ` ${unit}` : ''}`;
  if (typeof value === 'boolean') return w(value ? 'units.yes' : 'units.no');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/** How many changed rows stand before the disclosure is needed. */
const VISIBLE_INPUTS = 6;
const VISIBLE_ROLES = 5;

interface BodyProps {
  feedback: Feedback;
  variant: 'draft' | 'frozen';
  /** The frozen configuration rows, or null when the pair may not be quoted. */
  configRows?: ConfigRow[] | null;
  currentLabel?: string;
  comparisonLabel?: string;
  onRetry?: () => void;
  onOpenChapter?: (chapter: string) => void;
}

function FeedbackBody({ feedback, variant, configRows, currentLabel, comparisonLabel, onRetry, onOpenChapter }: BodyProps) {
  const d = useDesignFeedbackCopy();
  const w = useWorkspaceCopy();
  const units = useUnits();
  const [allInputs, setAllInputs] = useState(false);
  const [allRoles, setAllRoles] = useState(false);
  const draft = variant === 'draft';

  // Both panels state their direction in words: the workbench compares the draft
  // against the saved revision, the report the comparison run against the current
  // one, and the two signs must never be read as each other.
  const direction = draft ? d('feedback.direction.draft') : d('feedback.direction.frozen');
  const beforeHead = draft ? d('feedback.reading.before') : (currentLabel ?? d('feedback.reading.beforeFrozen'));
  const afterHead = draft ? d('feedback.reading.after') : (comparisonLabel ?? d('feedback.reading.afterFrozen'));

  const visibleInputs = allInputs ? feedback.inputs : feedback.inputs.slice(0, VISIBLE_INPUTS);
  const visibleRoles = allRoles ? feedback.roles : feedback.roles.slice(0, VISIBLE_ROLES);

  return <section className={`design-feedback design-feedback--${variant}`} aria-label={draft ? d('feedback.title') : d('feedback.frozen.title')}>
    <div className="design-feedback-head">
      <span className="section-kicker">{d('feedback.kicker')}</span>
      <h2>{draft ? d('feedback.title') : d('feedback.frozen.title')}</h2>
      <span className="design-feedback-direction">{direction}</span>
    </div>
    <p className="design-feedback-intro">{draft ? d('feedback.intro') : d('feedback.frozen.intro')}</p>

    {/* Every stop is stated before a single reading: a refusal that does not say
        why leaves the reader hunting for the reason it differs. */}
    {feedback.warnings.map(warning => <p className="design-feedback-warning" role="status" key={warning}>{warning}</p>)}
    {onRetry && <button type="button" className="button button--secondary design-feedback-retry" data-audio="manual" onClick={onRetry}>{d('feedback.baseline.retry')}</button>}
    {feedback.scopeNote && <p className="design-feedback-note">{feedback.scopeNote}</p>}

    {feedback.comparable && feedback.readings.length > 0 && <table className="design-feedback-table" tabIndex={0} aria-label={direction}>
      <thead><tr>
        <th scope="col">{d('feedback.reading.metric')}</th>
        <th scope="col">{beforeHead}</th>
        <th scope="col">{afterHead}</th>
        <th scope="col">{d('feedback.reading.delta')}</th>
      </tr></thead>
      <tbody>{feedback.readings.map(reading => <tr key={reading.key}>
        <th scope="row" title={[reading.beforeField, reading.afterField].filter(Boolean).join(' · ')}>{reading.label}</th>
        <td>{readingText(reading.before, reading, units, w('units.unknown'))}</td>
        <td>{readingText(reading.after, reading, units, w('units.unknown'))}</td>
        <td>{reading.delta === null
          ? <span className="design-feedback-unknown">{w('units.unknown')}{reading.reason && <small>{reading.reason}</small>}</span>
          : <span className="design-feedback-delta">{signedText(reading.delta, reading, units)}
            {reading.percent !== null
              ? <small>{d('feedback.percentOf', { value: formatNumber(Math.abs(reading.percent)) })}</small>
              : reading.before === 0 ? <small>{d('feedback.zeroBaseline')}</small> : null}
          </span>}</td>
      </tr>)}</tbody>
    </table>}

    {!draft && configRows && configRows.length > 0 ? <ConfigChangesTable rows={configRows}
      currentLabel={beforeHead} comparisonLabel={afterHead} /> : null}

    <div className="design-feedback-block">
      {feedback.inputs.length === 0
        ? <p className="design-feedback-empty">{d('feedback.inputs.none')}</p>
        : <details open={feedback.inputs.length <= VISIBLE_INPUTS}>
          <summary>{d('feedback.inputs.count', { count: feedback.inputs.length })}</summary>
          <ul className="design-feedback-inputs">{visibleInputs.map(input => <ChangedInputRow key={input.key} input={input} onOpenChapter={onOpenChapter} />)}</ul>
          {feedback.inputs.length > VISIBLE_INPUTS && <button type="button" className="text-button" data-audio="manual" onClick={() => setAllInputs(value => !value)}>
            {allInputs ? d('feedback.inputs.less') : d('feedback.inputs.more', { count: feedback.inputs.length - VISIBLE_INPUTS })}
          </button>}
        </details>}
    </div>

    <div className="design-feedback-block">
      {feedback.roles.length === 0
        ? <p className="design-feedback-empty">{d('feedback.roles.none')}</p>
        : <details open={feedback.roles.length <= VISIBLE_ROLES}>
          <summary>{d('feedback.roles.count', { count: feedback.roles.length })}</summary>
          <p className="design-feedback-note">{d('feedback.roles.observed')}</p>
          <ul className="design-feedback-roles">{visibleRoles.map(role => <ChangedRoleRow key={role.role} role={role} />)}</ul>
          {feedback.roles.length > VISIBLE_ROLES && <button type="button" className="text-button" data-audio="manual" onClick={() => setAllRoles(value => !value)}>
            {allRoles ? d('feedback.roles.less') : d('feedback.roles.more', { count: feedback.roles.length - VISIBLE_ROLES })}
          </button>}
        </details>}
    </div>
  </section>;
}

/**
 * The frozen configuration comparison: the five batteries and the key hull,
 * armour and propulsion facts, current → comparison.
 *
 * A physical quantity carries a real numeric difference; a categorical
 * declaration carries its two labels and is explicitly marked as having no
 * numeric difference, so the two kinds of row can never be read as one. The rows
 * exist only when the very same gate the reading table uses has accepted both
 * runs, so this table can never quote a value the table beside it withheld.
 */
function ConfigChangesTable({ rows, currentLabel, comparisonLabel }: {
  rows: ConfigRow[]; currentLabel: string; comparisonLabel: string;
}) {
  const c = useVesselOverviewCopy();
  const units = useUnits();
  const groups: ConfigGroup[] = ['battery', 'hull', 'freeboard', 'armour', 'propulsion'];
  const text = (row: ConfigRow, side: 'before' | 'after'): string => {
    if (row.kind === 'number') {
      const value = side === 'before' ? row.before : row.after;
      if (value === null || value === undefined) return c('vessel.unknown');
      // A canonical row keeps the source's own unit and is never converted; an
      // empty canonical is a plain count with no unit at all.
      if (row.canonical !== undefined) return row.canonical ? `${formatNumber(value)} ${row.canonical}` : formatNumber(value);
      return units.text(value, row.dimension ?? 'length', row.storedUnit);
    }
    const literal = side === 'before' ? row.beforeText : row.afterText;
    return literal === '' ? c('vessel.unknown') : literal;
  };
  const delta = (row: ConfigRow): string | null => {
    if (row.kind !== 'number' || row.before == null || row.after == null) return null;
    const value = row.after - row.before;
    const sign = value > 0 ? '+' : value < 0 ? '−' : '';
    if (row.canonical !== undefined) {
      const magnitude = row.canonical ? `${formatNumber(Math.abs(value))} ${row.canonical}` : formatNumber(Math.abs(value));
      return `${sign}${magnitude}`;
    }
    return `${sign}${units.text(Math.abs(value), row.dimension ?? 'length', row.storedUnit)}`;
  };
  const unchanged = (row: ConfigRow): boolean => row.kind === 'number'
    ? row.before === row.after
    : row.beforeText === row.afterText;
  return <details className="design-feedback-config" data-config-changes open>
    <summary>{c('vessel.config.title')}</summary>
    <p className="design-feedback-note">{c('vessel.config.intro')}</p>
    <table className="design-feedback-table" tabIndex={0} aria-label={c('vessel.config.title')}>
      <thead><tr>
        <th scope="col">{c('vessel.config.metric')}</th>
        <th scope="col">{currentLabel}</th>
        <th scope="col">{comparisonLabel}</th>
        <th scope="col">{c('vessel.config.difference')}</th>
      </tr></thead>
      <tbody>
        {groups.map(group => <Fragment key={group}>
          <tr className="design-feedback-config-group"><th scope="colgroup" colSpan={4}>{c(configGroupLabel(group))}</th></tr>
          {rows.filter(row => row.group === group).map(row => <tr key={row.key} data-config-row={row.key}>
            <th scope="row">{typeof row.bank === 'number' ? c('vessel.config.battery', { bank: row.bank }) : c(row.label)}</th>
            <td>{text(row, 'before')}</td>
            <td>{text(row, 'after')}</td>
            <td>{unchanged(row) ? c('vessel.config.unchanged')
              : row.kind === 'number' ? delta(row) ?? c('vessel.unknown')
                : c('vessel.config.categorical')}</td>
          </tr>)}
        </Fragment>)}
      </tbody>
    </table>
    <p className="design-feedback-note">{c('vessel.config.note')}</p>
  </details>;
}

function ChangedInputRow({ input, onOpenChapter }: { input: ChangedInput; onOpenChapter?: (chapter: string) => void }) {  const d = useDesignFeedbackCopy();
  const w = useWorkspaceCopy();
  const chapter = input.chapter as Chapter | null;
  return <li>
    <span className="design-feedback-input-name">{input.label}</span>
    <span className="design-feedback-input-values">{inputText(w, input.before, input.beforeUnit)} <span aria-hidden="true">→</span> {inputText(w, input.after, input.afterUnit)}</span>
    {input.unitChanged
      ? <small>{d('feedback.inputs.unitChanged', {
        before: input.beforeUnit ?? w('units.unknown'),
        after: input.afterUnit ?? w('units.unknown'),
      })}</small>
      : input.afterUnit && <small>{d('feedback.inputs.unit', { unit: input.afterUnit })}</small>}
    {/* A link exists only where the one source-page mapping names the chapter. */}
    {chapter && onOpenChapter && <button type="button" className="text-button" data-audio="manual" onClick={() => onOpenChapter(chapter)}>
      {d('feedback.inputs.open', { chapter: chapterOf(chapter, w).label })}
    </button>}
  </li>;
}

function ChangedRoleRow({ role }: { role: ChangedRole }) {
  const d = useDesignFeedbackCopy();
  const w = useWorkspaceCopy();
  const units = useUnits();
  const policy = (mode: string | null) => mode === 'estimated' ? d('feedback.policy.estimated')
    : mode === 'declared' ? d('feedback.policy.declared')
      : mode ? d('feedback.policy.other') : d('feedback.policy.unknown');
  const mode = role.beforeMode !== role.afterMode
    ? `${policy(role.beforeMode)} → ${policy(role.afterMode)}`
    : policy(role.beforeMode);
  const mass = (value: number | null) => value === null ? w('units.unknown') : units.text(value, 'mass', 't');
  return <li>
    <span className="design-feedback-role-name">{role.label}</span>
    <span className="design-feedback-role-mode">{mode}</span>
    <span className="design-feedback-role-mass">
      {d('feedback.roles.selected')}: {mass(role.beforeSelected)}
      {' '}<span aria-hidden="true">→</span>{' '}
      {mass(role.afterSelected)}
      {role.delta !== null && role.delta !== 0 && <small>{role.delta > 0 ? '+' : '−'}{units.text(Math.abs(role.delta), 'mass', 't')}</small>}
      {role.beforeEstimate !== null && role.afterEstimate !== null && role.beforeEstimate !== role.afterEstimate
        && <small>{d('feedback.roles.estimate')}: {mass(role.beforeEstimate)} → {mass(role.afterEstimate)}</small>}
    </span>
  </li>;
}

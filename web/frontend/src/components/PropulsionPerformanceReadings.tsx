import { chapterOf, type Chapter } from './ProjectNav';
import { useUnits } from './UnitProvider';
import { ledgerPolicyLabel, useVesselOverviewCopy, vesselLabel } from '../i18n/vesselOverview';
import { usePropulsionPerformanceCopy, type PropulsionPerformanceKey } from '../i18n/propulsionPerformance';
import { useWorkspaceCopy } from '../i18n/workspace';
import { useLanguage } from '../portfolio/LanguageProvider';
import { formatNumber } from './units';
import {
  PROPULSION_LEDGER_ROLES, readPropulsionPerformance,
  type PerformanceFlag, type PropulsionFact, type PropulsionLedgerRole, type PropulsionPerformance, type ReadingUnit,
} from './propulsionPerformanceModel';
import '../styles/propulsionPerformance.css';

/**
 * The propulsion and performance readers.
 *
 * Two presentational chapters read one pure projection of the saved native
 * result. Neither computes a ship number: the engine chapter prints the declared
 * fuel → engine → drive → shaft chain, the source speed, power, range, coal share
 * and bunker facts, the result's own declared power lock and the two whole-ship
 * machinery and fuel ledger roles; the performance chapter prints the source
 * empirical stability, hull strength and seakeeping readings and the source's own
 * eight warning and rating flags.
 *
 * A pending or failed reading withholds every fact and names the reason, exactly
 * as the other reading sheets do. Every undeclared value is the unknown marker,
 * never a zero, and a false source flag is only that flag. The live workbench
 * hands a real field back so a reading can reveal and focus it, or opens a
 * related chapter; the frozen report passes neither callback, so it renders
 * read-only with no control that does nothing.
 */

export type PropulsionState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface PropulsionReadingsProps {
  /** The native result or the raw saved stage data; gated inside. */
  result: unknown;
  state?: PropulsionState;
  contextLabel?: string | null;
  runId?: string | null;
  /** Reveal and focus one real engine source field. */
  onEditField?: (field: string) => void;
  className?: string;
}

export interface PerformanceReadingsProps extends PropulsionReadingsProps {
  /** Open a related chapter; the reader never changes a declaration itself. */
  onOpenChapter?: (chapter: string) => void;
}

function problemKey(problem: PropulsionPerformance['problem']): PropulsionPerformanceKey {
  switch (problem) {
    case 'unsupported_schema': return 'propulsion.state.schema';
    case 'unsupported_method': return 'propulsion.state.method';
    case 'absent': return 'propulsion.state.absent';
    default: return 'propulsion.state.unavailable';
  }
}

function performanceProblemKey(problem: PropulsionPerformance['problem']): PropulsionPerformanceKey {
  switch (problem) {
    case 'unsupported_schema': return 'performance.state.schema';
    case 'unsupported_method': return 'performance.state.method';
    case 'absent': return 'performance.state.absent';
    default: return 'performance.state.unavailable';
  }
}

/** One reading in the source's own unit; an undeclared value is the unknown marker. */
function readingText(value: number | null, unit: ReadingUnit, units: ReturnType<typeof useUnits>, unknown: string): string {
  if (value === null) return unknown;
  switch (unit) {
    case 'speed': return units.text(value, 'speed', 'kn');
    case 'source-hp': return `${formatNumber(value)} hp`;
    case 'range-nmi': return `${formatNumber(value)} nmi`;
    case 'count': return formatNumber(value);
    case 'percent': return `${formatNumber(value)} %`;
    case 'long-ton': return `${formatNumber(value)} LT`;
    case 'foot': return `${formatNumber(value)} ft`;
    case 'second': return `${formatNumber(value)} s`;
    default: return formatNumber(value);
  }
}

export function PropulsionReadings({
  result, state = 'ready', contextLabel, runId, onEditField, className,
}: PropulsionReadingsProps) {
  const p = usePropulsionPerformanceCopy();
  const v = useVesselOverviewCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const reading = readPropulsionPerformance(result);
  const sectionClass = `propulsion-readings ${className ?? ''}`.trim();

  // Pending and failed readings withhold every fact and name the reason.
  if (state === 'pending' || state === 'failed') {
    const key: PropulsionPerformanceKey = state === 'pending' ? 'propulsion.state.pending' : 'propulsion.state.failed';
    return <section className={sectionClass} data-propulsion-readings data-state={state} aria-label={p('propulsion.title')}>
      <p className="vessel-state" role="status">{p(key)}</p>
    </section>;
  }
  if (!reading.supported) {
    return <section className={sectionClass} data-propulsion-readings data-state="unavailable" aria-label={p('propulsion.title')}>
      <p className="vessel-state" role="status">{p(problemKey(reading.problem))}</p>
    </section>;
  }

  const canEdit = state === 'ready' && Boolean(onEditField);
  const unknown = v('vessel.unknown');
  const chains: Array<{ key: 'fuel' | 'engine' | 'drive'; label: PropulsionPerformanceKey; indices: readonly number[] | null }> = [
    { key: 'fuel', label: 'propulsion.declaration.fuel', indices: reading.engine.declaration.fuel },
    { key: 'engine', label: 'propulsion.declaration.engine', indices: reading.engine.declaration.engine },
    { key: 'drive', label: 'propulsion.declaration.drive', indices: reading.engine.declaration.drive },
  ];
  const chainText = (indices: readonly number[] | null, table: 'fuel' | 'engine' | 'drive'): string => {
    if (indices === null) return v('armament.flags.unknown');
    if (indices.length === 0) return v('armament.flags.none');
    return indices.map(index => vesselLabel(language, table, index) ?? unknown).join(' · ');
  };

  return <section className={sectionClass} data-propulsion-readings data-state={state} aria-label={p('propulsion.title')}>
    <header className="propulsion-head">
      <p className="propulsion-kicker">{p('propulsion.kicker')}</p>
      <h3>{p('propulsion.title')}</h3>
      <p className="propulsion-intro">{state === 'frozen' ? p('propulsion.state.frozen') : p('propulsion.intro')}</p>
      {contextLabel ? <p className="propulsion-hint" data-propulsion-context>{contextLabel}</p> : null}
      {runId ? <p className="propulsion-hint" data-propulsion-run>{runId}</p> : null}
    </header>

    <article className="propulsion-block" data-propulsion-declaration>
      <h4>{p('propulsion.declaration.title')}</h4>
      <dl className="propulsion-facts">
        {chains.map(({ key, label, indices }) => <div className="propulsion-fact" key={key} data-propulsion-chain={key}>
          <dt>{p(label)}</dt>
          <dd>{chainText(indices, key)}</dd>
        </div>)}
        <div className="propulsion-fact" data-propulsion-chain="screws">
          <dt>{p('propulsion.declaration.screws')}</dt>
          <dd>{reading.engine.screws === null ? unknown : formatNumber(reading.engine.screws)}</dd>
        </div>
      </dl>
      <p className="propulsion-hint">{p('propulsion.declaration.note')}</p>
    </article>

    <article className="propulsion-block" data-propulsion-facts>
      <dl className="propulsion-facts">
        {reading.engine.facts.map(fact => <FactRow key={fact.key} fact={fact} units={units} unknown={unknown}
          canEdit={canEdit} onEditField={onEditField} />)}
      </dl>
      <p className="propulsion-hint">{p('propulsion.fact.units')}</p>
    </article>

    <article className="propulsion-block" data-propulsion-lock>
      <h4>{p('propulsion.lock.title')}</h4>
      <p className="propulsion-hint" role="status">
        {reading.engine.lock.locked === null ? p('propulsion.lock.undeclared')
          : reading.engine.lock.locked ? p('propulsion.lock.locked') : p('propulsion.lock.unlocked')}
      </p>
      {reading.engine.lock.locked === true ? <dl className="propulsion-facts">
        <div className="propulsion-fact" data-propulsion-lock-target="power"><dt>{p('propulsion.lock.powerHp')}</dt>
          <dd>{reading.engine.lock.powerHp === null ? unknown : `${formatNumber(reading.engine.lock.powerHp)} hp`}</dd></div>
        <div className="propulsion-fact" data-propulsion-lock-target="bunker"><dt>{p('propulsion.lock.bunkerLt')}</dt>
          <dd>{reading.engine.lock.bunkerLt === null ? unknown : `${formatNumber(reading.engine.lock.bunkerLt)} LT`}</dd></div>
      </dl> : null}
      <p className="propulsion-hint">{p('propulsion.lock.note')}</p>
    </article>

    <article className="propulsion-block" data-propulsion-ledger>
      <h4>{p('propulsion.ledger.title')}</h4>
      <dl className="propulsion-facts">
        {PROPULSION_LEDGER_ROLES.map(role => <PropulsionLedgerLine key={role} role={role} reading={reading} />)}
      </dl>
      <p className="propulsion-hint">{p('propulsion.ledger.note')}</p>
    </article>
  </section>;
}

/** One engine fact, with its reveal button when the live workbench supplied one. */
function FactRow({ fact, units, unknown, canEdit, onEditField }: {
  fact: PropulsionFact; units: ReturnType<typeof useUnits>; unknown: string;
  canEdit: boolean; onEditField?: (field: string) => void;
}) {
  const p = usePropulsionPerformanceCopy();
  return <div className="propulsion-fact" data-propulsion-fact={fact.key}>
    <dt>{p(fact.label)}</dt>
    <dd>{readingText(fact.value, fact.unit, units, unknown)}
      {canEdit && fact.editField
        ? <button type="button" className="text-button propulsion-edit" data-propulsion-reveal={fact.editField}
          onClick={() => onEditField?.(fact.editField!)}>{p(fact.editLabel ?? 'propulsion.edit.speed')}</button>
        : null}
    </dd>
  </div>;
}

function PropulsionLedgerLine({ role, reading }: { role: PropulsionLedgerRole; reading: PropulsionPerformance }) {
  const p = usePropulsionPerformanceCopy();
  const v = useVesselOverviewCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const row = reading.engine.ledger.find(item => item.role === role)!;
  const mass = (value: number | null) => value === null ? v('vessel.unknown') : units.text(value, 'mass', 't');
  return <div className="propulsion-fact" data-propulsion-role={role}>
    <dt>{p(`propulsion.ledger.role.${role}` as PropulsionPerformanceKey)}</dt>
    <dd>
      {p('propulsion.ledger.mass', {
        selected: mass(row.selectedT), estimate: mass(row.estimateT), policy: ledgerPolicyLabel(language, row.mode),
      })}
      {row.unresolved ? <small className="propulsion-unbound">{p('propulsion.ledger.unbound')}</small> : null}
    </dd>
  </div>;
}

const RELATED_CHAPTERS: readonly Chapter[] = ['hull', 'freeboard', 'armour', 'guns', 'weights'];

export function PerformanceReadings({
  result, state = 'ready', contextLabel, runId, onEditField, onOpenChapter, className,
}: PerformanceReadingsProps) {
  const p = usePropulsionPerformanceCopy();
  const v = useVesselOverviewCopy();
  const w = useWorkspaceCopy();
  const units = useUnits();
  const reading = readPropulsionPerformance(result);
  const sectionClass = `performance-readings ${className ?? ''}`.trim();

  if (state === 'pending' || state === 'failed') {
    const key: PropulsionPerformanceKey = state === 'pending' ? 'performance.state.pending' : 'performance.state.failed';
    return <section className={sectionClass} data-performance-readings data-state={state} aria-label={p('performance.title')}>
      <p className="vessel-state" role="status">{p(key)}</p>
    </section>;
  }
  if (!reading.supported) {
    return <section className={sectionClass} data-performance-readings data-state="unavailable" aria-label={p('performance.title')}>
      <p className="vessel-state" role="status">{p(performanceProblemKey(reading.problem))}</p>
    </section>;
  }

  const unknown = v('vessel.unknown');
  const live = state === 'ready';
  const flagText = (flag: PerformanceFlag): string => flag.value === null ? unknown
    : flag.value ? p('performance.flag.true') : p('performance.flag.false');

  return <section className={sectionClass} data-performance-readings data-state={state} aria-label={p('performance.title')}>
    <header className="propulsion-head">
      <p className="propulsion-kicker">{p('performance.kicker')}</p>
      <h3>{p('performance.title')}</h3>
      <p className="propulsion-intro">{state === 'frozen' ? p('performance.state.frozen') : p('performance.intro')}</p>
      {contextLabel ? <p className="propulsion-hint" data-performance-context>{contextLabel}</p> : null}
      {runId ? <p className="propulsion-hint" data-performance-run>{runId}</p> : null}
    </header>

    {reading.performance.groups.map(group => <article className="propulsion-block" data-performance-group={group.id} key={group.id}>
      <h4>{p(group.label)}</h4>
      <dl className="propulsion-facts">
        {group.readings.map(fact => <div className="propulsion-fact" data-performance-fact={fact.key} key={fact.key}>
          <dt>{p(fact.label)}</dt>
          <dd>{readingText(fact.value, fact.unit, units, unknown)}</dd>
        </div>)}
      </dl>
    </article>)}
    <p className="propulsion-hint">{p('performance.fact.units')}</p>

    <article className="propulsion-block" data-performance-flags>
      <h4>{p('performance.flags.title')}</h4>
      <dl className="propulsion-facts">
        {reading.performance.flags.map(flag => <div className="propulsion-fact" data-performance-flag={flag.key} key={flag.key}>
          <dt>{p(flag.label)}</dt>
          <dd>{flagText(flag)}</dd>
        </div>)}
      </dl>
      <p className="propulsion-hint">{p('performance.flags.intro')}</p>
    </article>

    {/* A live reading points at the inputs that bear on it: the trim field is
        revealed in place, the other related inputs open their own chapter. The
        frozen report passes neither callback, so it carries no control here. */}
    {live && (onOpenChapter || onEditField) ? <article className="propulsion-block" data-performance-related>
      <h4>{p('performance.related.title')}</h4>
      <div className="propulsion-related">
        {onEditField ? <button type="button" className="sps-button" data-performance-trim
          onClick={() => onEditField('trim')}>{p('performance.related.trim')}</button> : null}
        {onOpenChapter ? RELATED_CHAPTERS.map(chapter => <button type="button" className="sps-button" key={chapter}
          data-performance-open={chapter} onClick={() => onOpenChapter(chapter)}>
          {p('performance.related.open', { chapter: chapterOf(chapter, w).label })}
        </button>) : null}
      </div>
      <p className="propulsion-hint">{p('performance.note')}</p>
      <p className="propulsion-hint">{p('performance.related.note')}</p>
    </article> : null}

    {!live || (!onOpenChapter && !onEditField) ? <p className="propulsion-hint">{p('performance.note')}</p> : null}
  </section>;
}

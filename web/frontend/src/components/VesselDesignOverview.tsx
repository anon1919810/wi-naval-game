import { useLanguage } from '../portfolio/LanguageProvider';
import { useUnits } from './UnitProvider';
import { ledgerPolicyLabel, useVesselOverviewCopy, vesselLabel, type VesselLabelTable, type VesselOverviewKey } from '../i18n/vesselOverview';
import { formatNumber } from './units';
import { buildVesselOverview, type VesselFact, type VesselOverview } from './vesselOverviewModel';
import '../styles/vesselOverview.css';

/**
 * The vessel design overview.
 *
 * One compact specification sheet of the confirmed draft: six sections of
 * independent known facts, each with a real navigation button to its chapter.
 * Every undeclared value is the unknown marker, never a zero; the overview makes
 * no aggregate completeness claim, computes no ship number and reads no formula.
 *
 * The live workbench renders it from the settled host preview, so a pending or
 * failed edit withholds every number and names the reason, and each section can
 * open its own chapter. The frozen report renders the same sheet read-only: it
 * says so in its own words and offers no navigation, because there is no draft
 * to navigate. A navigation button exists only where the sheet is a live draft
 * *and* the host actually supplied a chapter callback, so a frozen or standalone
 * reading never shows a button that does nothing.
 */

export type VesselOverviewState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface VesselDesignOverviewProps {
  /** The native result or the raw saved stage data; gated inside. */
  result: unknown;
  state?: VesselOverviewState;
  contextLabel?: string | null;
  runId?: string | null;
  /** Open a chapter; the section button hands its chapter id back. */
  onOpenChapter?: (chapter: string) => void;
  className?: string;
}

function problemKey(problem: VesselOverview['problem']): VesselOverviewKey {
  switch (problem) {
    case 'unsupported_schema': return 'vessel.state.schema';
    case 'unsupported_method': return 'vessel.state.method';
    case 'absent': return 'vessel.state.absent';
    default: return 'vessel.state.unavailable';
  }
}

export function VesselDesignOverview({
  result, state = 'ready', contextLabel, runId, onOpenChapter, className,
}: VesselDesignOverviewProps) {
  const w = useVesselOverviewCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const overview = buildVesselOverview(result);
  const sectionClass = `vessel-overview ${className ?? ''}`.trim();
  const text = (fact: VesselFact): string => factText(fact, language, units, w);
  // Navigation belongs to a live draft with a real destination, never to a frozen
  // reading and never to a button whose callback is absent.
  const canNavigate = state === 'ready' && Boolean(onOpenChapter);

  if (state === 'pending' || state === 'failed') {
    const key: VesselOverviewKey = state === 'pending' ? 'vessel.state.pending' : 'vessel.state.failed';
    return <section className={sectionClass} data-vessel-overview data-state={state} aria-label={w('vessel.title')}>
      <p className="vessel-state" role="status">{w(key)}</p>
    </section>;
  }
  if (!overview.supported) {
    return <section className={sectionClass} data-vessel-overview data-state="unavailable" aria-label={w('vessel.title')}>
      <p className="vessel-state" role="status">{w(problemKey(overview.problem))}</p>
    </section>;
  }

  return <section className={sectionClass} data-vessel-overview data-state={state} aria-label={w('vessel.title')}>
    <header className="vessel-head">
      <p className="vessel-kicker">{w('vessel.kicker')}</p>
      <h3>{w('vessel.title')}</h3>
      <p className="vessel-intro">{state === 'frozen' ? w('vessel.state.frozen') : w('vessel.intro')}</p>
      {contextLabel ? <p className="vessel-hint" data-vessel-context>{contextLabel}</p> : null}
      {runId ? <p className="vessel-hint" data-vessel-run>{runId}</p> : null}
    </header>
    {overview.sections.map(section => <article className="vessel-section" data-vessel-section={section.id} key={section.id}>
      <div className="vessel-section-head">
        <h4>{w(section.label)}</h4>
        {canNavigate ? <button type="button" className="sps-button vessel-open"
          data-vessel-open={section.chapter}
          onClick={() => onOpenChapter?.(section.chapter)}>
          {w('vessel.open', { chapter: w(section.label) })}
        </button> : null}
      </div>
      <dl className="vessel-facts">
        {section.facts.map(fact => <div className="vessel-fact" key={fact.key} data-vessel-fact={fact.key}>
          <dt>{w(fact.label, fact.labelParams)}</dt>
          <dd>{text(fact)}</dd>
        </div>)}
      </dl>
      {section.note ? <p className="vessel-hint">{w(section.note)}</p> : null}
    </article>)}
  </section>;
}

/**
 * One fact, in the reader's own units; an undeclared value is the unknown marker.
 *
 * A pure helper, not a component: it takes the reader's already-resolved
 * language, units and copy, so the sheet calls it inside its one render without
 * any hook of its own.
 */
function factText(fact: VesselFact, language: ReturnType<typeof useLanguage>['language'], units: ReturnType<typeof useUnits>, w: ReturnType<typeof useVesselOverviewCopy>): string {
  const unknown = w('vessel.unknown');
  const enumLabel = (table: VesselLabelTable | undefined, index: number | null): string => table ? vesselLabel(language, table, index) ?? unknown : unknown;

  switch (fact.kind) {
    case 'length': return fact.value === null ? unknown : units.text(fact.value, 'length', fact.storedUnit);
    case 'mass': return fact.value === null ? unknown : units.text(fact.value, 'mass', fact.storedUnit);
    case 'speed': return fact.value === null ? unknown : units.text(fact.value, 'speed', fact.storedUnit);
    case 'power-hp': return fact.value === null ? unknown : `${formatNumber(fact.value)} hp`;
    case 'range-nmi': return fact.value === null ? unknown : `${formatNumber(fact.value)} nmi`;
    case 'inches': return fact.value === null ? unknown : `${formatNumber(fact.value)} in (${formatNumber(fact.value * 25.4)} mm)`;
    case 'count': return fact.value === null ? unknown : formatNumber(fact.value);
    case 'enum': return enumLabel(fact.table, fact.index ?? null);
    case 'flags': {
      if (fact.flags === null || fact.flags === undefined) return w('armament.flags.unknown');
      if (fact.flags.length === 0) return w('armament.flags.none');
      return fact.flags.map(index => enumLabel(fact.table, index)).join(' · ');
    }
    case 'bank': {
      const bank = fact.bank;
      if (!bank || bank.state === 'missing' || bank.state === 'ambiguous') return w('vessel.fact.batteryUnavailable', { bank: bank?.bank ?? '' });
      return w('vessel.fact.batteryLine', {
        bank: bank.bank,
        calibre: bank.calibreIn === null ? unknown : `${formatNumber(bank.calibreIn)} in`,
        barrels: bank.barrels === null ? unknown : formatNumber(bank.barrels),
        mounts: bank.mounts === null ? unknown : formatNumber(bank.mounts),
      });
    }
    case 'ledger': {
      const row = fact.ledger;
      if (!row) return unknown;
      // The policy is stated beside the two masses: a policy-only change is a
      // real change even when the selected and estimated masses are equal.
      return w('armament.ledger.mass', {
        selected: row.selectedT === null ? unknown : units.text(row.selectedT, 'mass', 't'),
        estimate: row.estimateT === null ? unknown : units.text(row.estimateT, 'mass', 't'),
        policy: ledgerPolicyLabel(language, row.mode),
      });
    }
    default: return fact.text ?? unknown;
  }
}

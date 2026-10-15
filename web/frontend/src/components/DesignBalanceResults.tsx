import { type ReactNode } from 'react';

import { useConceptCopy } from '../i18n/concept';
import { useUnits } from './UnitProvider';
import { object, rows } from './formModel';
import { balanceData, balanceStage, metric } from './conceptDesign';
import type { RunView } from '../types';

/**
 * The adapted concept screen, read as its own result.
 *
 * This is deliberately a separate panel from the physical hydrostatics, GM, GZ,
 * trim and roll results, and it never borrows their fields. The recovered
 * strength, stability, steadiness and seakeeping scores are empirical indices
 * over declared inputs; presenting one of them under a physical heading would
 * turn an index into a safety certificate, which is the one thing this screen is
 * not allowed to be.
 *
 * A value the declared inputs cannot support is shown as unknown with the
 * reason beside it. An all-green card that quietly omits the half of the screen
 * the reader cannot yet compute would be a worse reading than no card at all.
 */

/** One long-ton metric. Long tons are the screen's own unit and are not converted. */
function LongTons({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  const c = useConceptCopy();
  const known = metric(value);
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{known === null ? c('proposals.unknownMass') : `${known.toFixed(3)} ${c('balance.unit.lt')}`}</span>
    {unit && <span className="fact-meta">{unit}</span>}
  </div>;
}

function Plain({ label, value, unit = '' }: { label: string; value: unknown; unit?: string }) {
  const c = useConceptCopy();
  const known = metric(value);
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{known === null ? c('proposals.unknownMass') : `${known.toFixed(3)}${unit ? ` ${unit}` : ''}`}</span>
  </div>;
}

function Quantity({ label, text }: { label: string; text: string }) {
  return <div className="fact-field"><span className="fact-label">{label}</span><span className="fact-value">{text}</span></div>;
}

function Group({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return <section className="concept-balance-group">
    <h4>{title}</h4>
    <div className="metric-grid">{children}</div>
    {note && <p className="form-hint">{note}</p>}
  </section>;
}

export function DesignBalanceResults({ run, available }: { run: RunView | null; available: boolean }) {
  const c = useConceptCopy();
  const units = useUnits();
  const envelope = balanceStage(run);
  const data = balanceData(run);
  const status = String(data.status ?? envelope?.status ?? '');
  const values = object(data.values);
  const structure = object(data.structure);
  const strength = object(data.strength);
  const space = object(data.space);
  const stability = object(data.stability);
  const seakeeping = object(data.seakeeping);
  const crew = object(data.crew);
  const hull = object(data.hull_proxy);
  const power = object(data.power);
  const warnings = rows(data.design_warnings);
  const unclassified = (Array.isArray(data.unclassified_item_ids) ? data.unclassified_item_ids : [])
    .filter((item): item is string => typeof item === 'string' && item !== '');

  if (!available || !run) return <section className="form-card concept-balance">
    <h3>{c('balance.title')}</h3>
    <p className="section-intro">{c('balance.notConfigured')}</p>
  </section>;

  if (status === 'not_configured' || (!envelope && !run.result?.stages?.design_balance)) {
    return <section className="form-card concept-balance">
      <h3>{c('balance.title')}</h3>
      <p className="section-intro">{c('balance.notConfigured')}</p>
    </section>;
  }

  return <section className="form-card concept-balance">
    <span className="section-kicker">{c('balance.kicker')}</span>
    <h3>{c('balance.title')}</h3>
    <p>{c('balance.intro')}</p>
    <p className="form-hint">{c('balance.method', {
      method: String(data.method_version ?? ''), scope: String(data.method_scope ?? '') })}</p>
    {typeof data.basis === 'string' && <p className="form-hint">{c('balance.basis', { basis: data.basis })}</p>}
    {typeof data.assumption_source === 'string' && data.assumption_source !== ''
      && <p className="form-hint">{c('balance.assumptionSource', { source: data.assumption_source })}</p>}

    {status !== 'completed' && <div className="notice" role="status">
      {status === 'partial' ? c('balance.partial')
        : c('balance.unavailable', { reason: String(data.reason ?? envelope?.reason ?? '') })}
    </div>}

    <Group title={c('balance.section.mass')} note={c('balance.metric.budgetNote')}>
      <Quantity label={c('balance.metric.selectedTotal')} text={units.text(values.selected_total_mass_t, 'mass', 't')} />
      <Quantity label={c('balance.metric.target')} text={units.text(values.target_displacement_t, 'mass', 't')} />
      <Quantity label={c('balance.metric.difference')} text={units.text(values.difference_t, 'mass', 't')} />
      <LongTons label={c('balance.metric.nonstructure')} value={values.nonstructure_mass_long_tons} />
      <LongTons label={c('balance.metric.budget')} value={values.remaining_structural_budget_long_tons} />
    </Group>

    {Object.keys(structure).length === 0 ? null : <Group title={c('balance.section.structure')}
      note={c('balance.inversionNote')}>
      <LongTons label={c('balance.metric.currentStructure')} value={structure.current_structure_long_tons} />
      <LongTons label={c('balance.metric.demand')} value={structure.required_total_long_tons} />
      <LongTons label={c('balance.metric.requiredAdjustable')} value={structure.required_adjustable_long_tons} />
      <LongTons label={c('balance.metric.currentAdjustable')} value={structure.current_adjustable_structure_long_tons} />
      <LongTons label={c('balance.metric.otherStructure')} value={structure.other_structure_long_tons} />
      <LongTons label={c('balance.metric.margin')} value={structure.structure_margin_long_tons}
        unit={String(structure.structure_item_id ?? '')} />
    </Group>}

    {Object.keys(strength).length === 0 ? null : <Group title={c('balance.section.strength')}
      note={c('balance.strengthNote')}>
      <Plain label={c('balance.metric.cross')} value={strength.cross} />
      <Plain label={c('balance.metric.long')} value={strength.longitudinal} />
      <Plain label={c('balance.metric.composite')} value={strength.composite} />
      <Plain label={c('balance.metric.compositeTarget')} value={strength.composite_target} />
      <Plain label={c('balance.metric.broadside')} value={strength.broadside_lb} unit="lb" />
    </Group>}

    {Object.keys(space).length === 0 ? null : <Group title={c('balance.section.space')}>
      <Plain label={c('balance.metric.hullRatio')} value={space.hull_ratio} />
      <Plain label={c('balance.metric.deckRatio')} value={space.deck_ratio} />
    </Group>}

    {Object.keys(stability).length === 0 && Object.keys(seakeeping).length === 0 ? null
      : <Group title={c('balance.section.performance')} note={c('balance.stabilityNote')}>
        <Plain label={c('balance.metric.stability')} value={stability.score} />
        <Plain label={c('balance.metric.stabilityAdjusted')} value={stability.adjusted} />
        <Plain label={c('balance.metric.steadiness')} value={seakeeping.steadiness_score} />
        <Plain label={c('balance.metric.seaboat')} value={seakeeping.seaboat} />
        <Plain label={c('balance.metric.seakeeping')} value={seakeeping.score} />
      </Group>}

    {Object.keys(crew).length === 0 ? null : <Group title={c('balance.section.crew')}>
      <Plain label={c('balance.metric.crewMin')} value={crew.crew_min} />
      <Plain label={c('balance.metric.crewMax')} value={crew.crew_max} />
    </Group>}

    {Object.keys(hull).length === 0 ? null : <Group title={c('balance.section.hull')}>
      <Quantity label={c('balance.metric.naturalSpeed')} text={units.text(hull.natural_speed_kn, 'speed', 'kn')} />
      <Plain label={c('balance.metric.wetted')} value={hull.wetted_surface_sqft} unit="ft²" />
      <Plain label={c('balance.metric.waterplane')} value={hull.waterplane_area_sqft} unit="ft²" />
      <Plain label={c('balance.metric.coSharp')} value={hull.co_sharp} />
      <Plain label={c('balance.metric.effectiveLength')} value={hull.effective_length_ft} unit="ft" />
    </Group>}

    {Object.keys(power).length === 0 ? null : <Group title={c('balance.section.power')}>
      <Plain label={c('balance.metric.hpMax')} value={power.hp_max} unit="shp" />
      <Plain label={c('balance.metric.friction')} value={power.friction_fraction} />
    </Group>}

    {unclassified.length > 0 && <p className="notice" role="status">
      {c('balance.unclassified', { items: unclassified.join(', ') })}</p>}

    {warnings.length === 0 ? null : <div className="concept-balance-warnings">
      <h4>{c('balance.section.warnings')}</h4>
      <ul className="diagnostics-list">{warnings.map((row, index) =>
        <li key={index}>{String(row.message ?? '')}</li>)}</ul>
    </div>}

    <p className="form-hint">{c('balance.unitConvention')}</p>
  </section>;
}

/** The diagnostics of the screen itself, shown beside it and never folded away. */
export function DesignBalanceDiagnostics({ run }: { run: RunView | null }) {
  const c = useConceptCopy();
  const envelope = balanceStage(run);
  const blocked = rows(envelope?.diagnostics);
  if (blocked.length === 0) return null;
  return <details className="concept-balance-diagnostics">
    <summary>{c('balance.section.warnings')} ({blocked.length})</summary>
    <ul className="diagnostics-list">{blocked.map((row, index) =>
      <li key={index}>{String(row.message ?? row.code ?? '')}</li>)}</ul>
  </details>;
}

/** A one-line pointer from another chapter to the editor that owns the input. */
export function ConceptDesignLink({ label, onOpen }: { label: string; onOpen: () => void }) {
  return <p className="form-hint"><button className="text-button" type="button" onClick={onOpen}>{label}</button></p>;
}

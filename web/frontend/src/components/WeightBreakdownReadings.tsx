import { useMemo, useState, type ReactNode } from 'react';

import { useShipDesignRoleLabel } from '../i18n/shipDesign';
import { useWeightBreakdownCopy, type WeightBreakdownKey } from '../i18n/weightBreakdown';
import { useUnits } from './UnitProvider';
import {
  readWeightBreakdown, type WeightBreakdown, type WeightGroup, type WeightRole,
} from './weightBreakdownModel';
import '../styles/weightBreakdown.css';

/**
 * The managed weight breakdown reader.
 *
 * It reads one pure projection of the saved native result: the six presentation
 * groups built from the ledger's own roles, each role's source estimate and
 * adopted mass, and the ledger's authoritative balance. The bar chart and the
 * role list below it read the same rows, so the picture and the list can never
 * disagree.
 *
 * A pending or failed reading withholds every number. The frozen host passes no
 * edit callback and asks for the static shape, so the reading is read-only and
 * offers no control that does nothing. Selecting a group only opens its reading;
 * it never writes the design, and the reveal button opens the existing binding
 * form the host owns.
 */

export type WeightBreakdownState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface WeightBreakdownReadingsProps {
  result: unknown;
  baseline?: unknown;
  state?: WeightBreakdownState;
  contextLabel?: string | null;
  runId?: string | null;
  onEditRole?: (role: string) => void;
  className?: string;
}

function problemKey(problem: WeightBreakdown['problem']): WeightBreakdownKey {
  switch (problem) {
    case 'unsupported_schema': return 'weight.state.schema';
    case 'unsupported_method': return 'weight.state.method';
    case 'absent': return 'weight.state.absent';
    default: return 'weight.state.unavailable';
  }
}

function groupKey(group: WeightGroup['key']): WeightBreakdownKey {
  return `weight.group.${group}` as WeightBreakdownKey;
}

export function WeightBreakdownReadings({
  result, baseline, state = 'ready', contextLabel, runId, onEditRole, className,
}: WeightBreakdownReadingsProps) {
  const p = useWeightBreakdownCopy();
  const role = useShipDesignRoleLabel();
  const units = useUnits();
  const reading = useMemo(() => readWeightBreakdown(result, baseline), [result, baseline]);
  const [selected, setSelected] = useState<string | null>(null);
  const sectionClass = `weight-breakdown ${className ?? ''}`.trim();

  if (state === 'pending' || state === 'failed') {
    const key: WeightBreakdownKey = state === 'pending' ? 'weight.state.pending' : 'weight.state.failed';
    return <section className={sectionClass} data-weight-breakdown data-state={state} aria-label={p('weight.title')}>
      <p className="weight-state" role="status">{p(key)}</p>
    </section>;
  }
  if (!reading.supported) {
    return <section className={sectionClass} data-weight-breakdown data-state="unavailable" aria-label={p('weight.title')}>
      <p className="weight-state" role="status">{p(problemKey(reading.problem))}</p>
    </section>;
  }

  const unknown = p('weight.unknown');
  const mass = (value: number | null): string => value === null ? unknown : units.text(value, 'mass', 't');
  const interactive = state === 'ready';
  const populated = reading.groups.filter(group => group.populated);
  const active = selected ?? populated[0]?.key ?? null;
  const visible = interactive
    ? populated.filter(group => group.key === active)
    : populated;

  // One scale for every bar, so the picture is comparable across the reading.
  // A negative value extends left of the zero line rather than becoming a
  // positive bar, and no value is turned into a fraction of an invented total.
  const values = reading.roles.flatMap(entry => [entry.estimateT, entry.selectedT]).filter((value): value is number => value !== null);
  const scale = Math.max(1, ...values.map(value => Math.abs(value)));
  const hasNegative = values.some(value => value < 0);
  const zeroPercent = hasNegative ? 50 : 0;

  const barStyle = (value: number): { left: string; width: string } => {
    const span = hasNegative ? 50 : 100;
    const width = Math.min(span, (Math.abs(value) / scale) * span);
    return { left: `${value < 0 ? zeroPercent - width : zeroPercent}%`, width: `${width}%` };
  };

  const roleRow = (entry: WeightRole): ReactNode => <li className={`weight-role${entry.changed ? ' weight-role--changed' : ''}`}
    data-weight-role={entry.role} data-changed={entry.changed ? 'true' : undefined}
    data-conflict={entry.conflict ? 'true' : undefined} key={entry.role}>
    <div className="weight-role-head">
      <span className="weight-role-name">{role(entry.role)}</span>
      {entry.conflict
        ? <span className="weight-role-conflict">{p('weight.role.conflict.title')}</span>
        : <span className="weight-role-mode">{modeText(p, entry.mode, entry.role)}</span>}
      {entry.changed ? <span className="weight-changed">{p('weight.changed')}</span> : null}
    </div>
    {entry.conflict
      ? <p className="weight-role-note">{p('weight.role.conflict.note')}</p>
      : <dl className="weight-role-facts">
        <div><dt>{p('weight.estimate')}</dt><dd>{mass(entry.estimateT)}</dd></div>
        <div><dt>{p('weight.selected')}</dt><dd>{mass(entry.selectedT)}</dd></div>
        <div><dt>{p('weight.adoption')}</dt><dd>{signedMass(p, units, entry.adoptionDeltaT)}</dd></div>
        <div><dt>{p('weight.items')}</dt><dd>{entry.itemIds.length > 0 ? entry.itemIds.join(', ') : p('weight.role.none')}</dd></div>
      </dl>}
    {entry.mode === null && entry.role === 'other' && !entry.conflict
      ? <p className="weight-role-note">{p('weight.role.optional')}</p> : null}
    {interactive && onEditRole && !entry.conflict
      ? <button type="button" className="text-button weight-reveal" data-weight-edit={entry.role}
        onClick={() => onEditRole(entry.role)}>{p('weight.reveal')}</button> : null}
  </li>;

  return <section className={sectionClass} data-weight-breakdown data-state={state} aria-label={p('weight.title')}>
    <header className="weight-head">
      <p className="weight-kicker">{p('weight.kicker')}</p>
      <h3>{p('weight.title')}</h3>
      <p className="weight-intro">{state === 'frozen' ? p('weight.state.frozen') : p('weight.intro')}</p>
      {contextLabel ? <p className="weight-hint" data-weight-context>{contextLabel}</p> : null}
      {runId ? <p className="weight-hint" data-weight-run>{runId}</p> : null}
    </header>

    <article className="weight-block">
      <h4>{p('weight.balance.title')}</h4>
      <dl className="weight-balance" data-weight-balance>
        <div data-weight-balance-row="selected"><dt>{p('weight.balance.selected')}</dt><dd>{mass(reading.balance.selectedT)}</dd></div>
        <div data-weight-balance-row="estimate"><dt>{p('weight.balance.estimate')}</dt><dd>{mass(reading.balance.estimateT)}</dd></div>
        <div data-weight-balance-row="target"><dt>{p('weight.balance.target')}</dt><dd>{mass(reading.balance.targetT)}</dd></div>
        <div data-weight-balance-row="difference"><dt>{p('weight.balance.difference')}</dt><dd>{mass(reading.balance.differenceT)}</dd></div>
        <div data-weight-balance-row="adoption"><dt>{p('weight.balance.adoption')}</dt>
          <dd>{signedMass(p, units, subtract(reading.balance.selectedT, reading.balance.estimateT))}</dd></div>
        <div data-weight-balance-row="estimateVsTarget"><dt>{p('weight.balance.estimateVsTarget')}</dt>
          <dd>{signedMass(p, units, subtract(reading.balance.estimateT, reading.balance.targetT))}</dd></div>
      </dl>
      <p className="weight-hint">{p('weight.balance.note')}</p>
      <p className="weight-hint" data-weight-status>{reading.complete === true
        ? p('weight.complete')
        : reading.complete === false
          ? p('weight.unresolved', { count: reading.roles.filter(entry => entry.unresolved).length })
          : p('weight.complete.unknown')}</p>
      <dl className="weight-reconcile" data-weight-reconcile data-weight-verdict={reading.reconciliation.verdict}>
        <div data-weight-reconcile-row="sum"><dt>{p('weight.reconcile.sum')}</dt>
          <dd>{p('weight.reconcile.estimate')}: {mass(reading.reconciliation.roleEstimateT)} · {p('weight.reconcile.selected')}: {mass(reading.reconciliation.roleSelectedT)}</dd></div>
        <div data-weight-reconcile-row="balance"><dt>{p('weight.reconcile.balance')}</dt>
          <dd>{p('weight.reconcile.estimate')}: {mass(reading.reconciliation.balanceEstimateT)} · {p('weight.reconcile.selected')}: {mass(reading.reconciliation.balanceSelectedT)}</dd></div>
      </dl>
      <p className="weight-hint" data-weight-reconcile-note>{reading.reconciliation.verdict === 'match'
        ? p('weight.reconcile.match')
        : reading.reconciliation.verdict === 'mismatch'
          ? p('weight.reconcile.mismatch')
          : p('weight.reconcile.partial')}</p>
    </article>

    <article className="weight-block">
      <h4>{p('weight.groups.title')}</h4>
      <p className="weight-hint">{p('weight.groups.note')}</p>
      <ul className="weight-groups" role={interactive ? 'group' : undefined} aria-label={p('weight.select.list')}>
        {reading.groups.map(group => {
          const isActive = interactive && group.key === active;
          const content = <>
            <span className="weight-group-label">{p(groupKey(group.key))}</span>
            <span className="weight-group-values">
              <span>{p('weight.group.estimate')}: {mass(group.estimateT)}</span>
              <span>{p('weight.group.selected')}: {mass(group.selectedT)}</span>
            </span>
            {group.changed ? <span className="weight-changed">{p('weight.changed')}</span> : null}
          </>;
          return <li key={group.key} className={`weight-group${isActive ? ' weight-group--active' : ''}${group.changed ? ' weight-group--changed' : ''}`}
            data-weight-group={group.key} data-changed={group.changed ? 'true' : undefined}>
            {interactive
              ? <button type="button" className="weight-group-select" data-weight-select={group.key}
                aria-pressed={isActive} onClick={() => setSelected(group.key)}>{content}</button>
              : <div className="weight-group-static">{content}</div>}
            {group.populated && !group.complete ? <p className="weight-hint weight-group-incomplete">{p('weight.groups.incomplete')}</p> : null}
            {group.missing.length > 0 ? <p className="weight-hint weight-group-missing" data-weight-group-missing={group.key}>
              {p('weight.group.missing', { roles: group.missing.map(name => role(name)).join(', ') })}</p> : null}
            {!group.populated ? <p className="weight-hint">{p('weight.groups.empty')}</p> : null}
          </li>;
        })}
      </ul>
    </article>

    <article className="weight-block" data-weight-chart>
      <h4>{p('weight.chart.title')}</h4>
      <p className="weight-chart-legend">
        <span className="weight-legend weight-legend--estimate">{p('weight.chart.legend.estimate')}</span>
        <span className="weight-legend weight-legend--selected">{p('weight.chart.legend.selected')}</span>
      </p>
      {visible.length === 0 ? <p className="weight-hint">{p('weight.groups.empty')}</p> : visible.map(group =>
        <div className="weight-chart-group" key={group.key} data-weight-chart-group={group.key}>
          <h5>{p(groupKey(group.key))}</h5>
          <ul className="weight-roles" role={interactive ? 'list' : undefined} aria-label={p('weight.roles.title')}>
            {group.roles.map(entry => <li key={entry.role} className="weight-chart-role" data-weight-role={entry.role}
              data-changed={entry.changed ? 'true' : undefined}>
              <span className="weight-role-name">{role(entry.role)}</span>
              <span className="weight-bar-row">
                <span className="weight-bar-legend">{p('weight.chart.legend.estimate')}</span>
                <span className="weight-track" role="img"
                  aria-label={`${role(entry.role)} ${p('weight.chart.legend.estimate')}: ${mass(entry.estimateT)}`}>
                  <span className="weight-zero" style={{ left: `${zeroPercent}%` }} />
                  {entry.estimateT !== null ? <span className="weight-bar weight-bar--estimate" style={barStyle(entry.estimateT)} /> : null}
                  {entry.estimateT === null ? <span className="weight-bar-unknown">{p('weight.chart.unknown')}</span> : null}
                </span>
                <span className="weight-bar-value">{mass(entry.estimateT)}</span>
              </span>
              <span className="weight-bar-row">
                <span className="weight-bar-legend">{p('weight.chart.legend.selected')}</span>
                <span className="weight-track" role="img"
                  aria-label={`${role(entry.role)} ${p('weight.chart.legend.selected')}: ${mass(entry.selectedT)}`}>
                  <span className="weight-zero" style={{ left: `${zeroPercent}%` }} />
                  {entry.selectedT !== null ? <span className="weight-bar weight-bar--selected" style={barStyle(entry.selectedT)} /> : null}
                  {entry.selectedT === null ? <span className="weight-bar-unknown">{p('weight.chart.unknown')}</span> : null}
                </span>
                <span className="weight-bar-value">{mass(entry.selectedT)}</span>
              </span>
            </li>)}
          </ul>
        </div>)}
      <p className="weight-hint">{p('weight.chart.note')}</p>
      {interactive ? <p className="weight-hint">{p('weight.select.hint')}</p> : null}
    </article>

    {/* The role readings keep every fact in the frozen shape too: a frozen
        saved result must be complete on its own, without a comparison. Only the
        selection and edit controls are interactive. */}
    <article className="weight-block" data-weight-role-readings>
      <h4>{p('weight.roles.title')}</h4>
      <ul className="weight-role-list">{visible.flatMap(group => group.roles).map(roleRow)}</ul>
      {interactive && onEditRole ? <p className="weight-hint">{p('weight.reveal.hint')}</p> : null}
    </article>
  </section>;
}

function subtract(left: number | null, right: number | null): number | null {
  return left !== null && right !== null ? left - right : null;
}

function signedMass(p: (key: WeightBreakdownKey, params?: Record<string, string | number>) => string,
  units: ReturnType<typeof useUnits>, value: number | null): string {
  if (value === null) return p('weight.unknown');
  if (value === 0) return units.text(0, 'mass', 't');
  const sign = value > 0 ? '+' : '−';
  return `${sign}${units.text(Math.abs(value), 'mass', 't')}`;
}

function modeText(p: (key: WeightBreakdownKey) => string, mode: WeightRole['mode'], role: string): string {
  if (role === 'other' && mode === null) return p('weight.mode.none');
  return mode === 'declared' ? p('weight.mode.declared')
    : mode === 'estimated' ? p('weight.mode.estimated') : p('weight.mode.none');
}

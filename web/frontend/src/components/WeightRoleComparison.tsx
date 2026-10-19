import { Fragment, useMemo, type ReactNode } from 'react';

import { useShipDesignRoleLabel } from '../i18n/shipDesign';
import { useWeightBreakdownCopy, type WeightBreakdownKey } from '../i18n/weightBreakdown';
import { useUnits } from './UnitProvider';
import { weightComparisonRows, WEIGHT_GROUPS, type WeightComparisonRow, type WeightComparisonSide } from './weightBreakdownModel';
import '../styles/weightBreakdown.css';

/**
 * The frozen role comparison: the ordered union of two saved ledgers.
 *
 * Both sides are read from immutable results, in the same direction as the
 * report comparison beside it — the difference is comparison − current. Each
 * side states its own estimate, adopted mass, policy and binding; a role absent
 * on one side stays unknown there, and a policy or binding change is printed as
 * a categorical change rather than a mass difference. Every row either shows a
 * real difference or says why it cannot.
 */

export interface WeightRoleComparisonProps {
  current: unknown;
  comparison: unknown;
  currentLabel?: string;
  comparisonLabel?: string;
  className?: string;
}

function problemKey(problem: ReturnType<typeof weightComparisonRows>['problem']): WeightBreakdownKey {
  switch (problem) {
    case 'absent': return 'weight.state.absent';
    case 'unsupported_schema': return 'weight.state.schema';
    case 'unsupported_method': return 'weight.state.method';
    case 'incompatible': return 'weight.comparison.incompatible';
    default: return 'weight.state.unavailable';
  }
}

export function WeightRoleComparison({
  current, comparison, currentLabel, comparisonLabel, className,
}: WeightRoleComparisonProps) {
  const p = useWeightBreakdownCopy();
  const role = useShipDesignRoleLabel();
  const units = useUnits();
  const reading = useMemo(() => weightComparisonRows(current, comparison), [current, comparison]);
  const sectionClass = `weight-comparison ${className ?? ''}`.trim();

  if (!reading.comparable) {
    return <section className={sectionClass} data-weight-comparison data-comparable="false" aria-label={p('weight.comparison.title')}>
      <header className="weight-head">
        <h3>{p('weight.comparison.title')}</h3>
      </header>
      <p className="weight-state" role="status">{p(problemKey(reading.problem))}</p>
    </section>;
  }

  const mass = (value: number | null): string => value === null ? p('weight.unknown') : units.text(value, 'mass', 't');
  const signed = (value: number | null): string => {
    if (value === null) return p('weight.unknown');
    if (value === 0) return units.text(0, 'mass', 't');
    return `${value > 0 ? '+' : '−'}${units.text(Math.abs(value), 'mass', 't')}`;
  };
  const side = (value: WeightComparisonSide): ReactNode => value.conflict || !value.present
    ? <span className="weight-comparison-absent">{value.conflict ? p('weight.comparison.conflict') : p('weight.comparison.roleAbsent')}</span>
    : <span className="weight-comparison-side">
      <span>{p('weight.comparison.estimate')}: {mass(value.estimateT)}</span>
      <span>{p('weight.comparison.selected')}: {mass(value.selectedT)}</span>
      <span>{p('weight.comparison.mode')}: {modeText(p, value.mode)}</span>
      <span>{p('weight.comparison.binding')}: {value.itemIds.length > 0 ? value.itemIds.join(', ') : p('weight.role.none')}</span>
    </span>;
  const delta = (row: WeightComparisonRow): ReactNode => {
    if (row.conflict) return <span className="weight-comparison-absent">{p('weight.comparison.conflict')}</span>;
    const categorical = row.modeChanged || row.bindingChanged;
    const anyKnown = row.estimateDeltaT !== null || row.selectedDeltaT !== null;
    if (!anyKnown && !categorical) return <span className="weight-comparison-absent">{p('weight.unknown')}</span>;
    // Each dimension is stated: a known difference is shown, and an unknown one
    // says so rather than being silently dropped from the cell.
    return <span className="weight-comparison-delta">
      <span>{p('weight.comparison.estimate')}: {row.estimateDeltaT !== null ? signed(row.estimateDeltaT) : p('weight.unknown')}</span>
      <span>{p('weight.comparison.selected')}: {row.selectedDeltaT !== null ? signed(row.selectedDeltaT) : p('weight.unknown')}</span>
      {categorical ? <span className="weight-comparison-categorical">{p('weight.comparison.changed')}</span> : null}
    </span>;
  };

  return <section className={sectionClass} data-weight-comparison data-comparable="true" aria-label={p('weight.comparison.title')}>
    <header className="weight-head">
      <h3>{p('weight.comparison.title')}</h3>
      <p className="weight-intro">{p('weight.comparison.intro')}</p>
      <p className="weight-hint">{p('weight.comparison.direction')}</p>
    </header>
    <table className="weight-comparison-table" tabIndex={0} aria-label={p('weight.comparison.title')}>
      <thead><tr>
        <th scope="col">{p('weight.comparison.metric')}</th>
        <th scope="col">{currentLabel ?? p('weight.comparison.current')}</th>
        <th scope="col">{comparisonLabel ?? p('weight.comparison.comparison')}</th>
        <th scope="col">{p('weight.comparison.delta')}</th>
      </tr></thead>
      <tbody>
        {WEIGHT_GROUPS.map(group => {
          const rows = reading.rows.filter(row => row.group === group.key);
          if (rows.length === 0) return null;
          return <Fragment key={group.key}>
            <tr className="weight-comparison-group"><th scope="colgroup" colSpan={4}>{p(`weight.group.${group.key}` as WeightBreakdownKey)}</th></tr>
            {rows.map(row => <tr key={row.role} data-weight-comparison-row={row.role}
              data-changed={row.changed ? 'true' : undefined} data-conflict={row.conflict ? 'true' : undefined}>
              <th scope="row">{role(row.role)}</th>
              <td>{side(row.current)}</td>
              <td>{side(row.comparison)}</td>
              <td>{delta(row)}</td>
            </tr>)}
          </Fragment>;
        })}
      </tbody>
    </table>
    <p className="weight-hint">{p('weight.comparison.note')}</p>
  </section>;
}

function modeText(p: (key: WeightBreakdownKey) => string, mode: WeightComparisonSide['mode']): string {
  return mode === 'declared' ? p('weight.mode.declared')
    : mode === 'estimated' ? p('weight.mode.estimated') : p('weight.mode.none');
}

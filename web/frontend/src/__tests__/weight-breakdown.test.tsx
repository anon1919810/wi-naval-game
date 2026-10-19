import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { readWeightBreakdown, weightComparisonRows } from '../components/weightBreakdownModel';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA } from '../components/sps3b3Model';
import { WeightBreakdownReadings } from '../components/WeightBreakdownReadings';
import { WeightRoleComparison } from '../components/WeightRoleComparison';
import { ShipDesignLedgerSection, type ShipDesignHost } from '../components/ShipDesignEditor';
import { UnitProvider } from '../components/UnitProvider';
import { CANONICAL_PREFERENCES } from '../components/units';
import { weightBreakdownCopy, weightBreakdownDictionary } from '../i18n/weightBreakdown';
import { renderZh } from './locale';
import type { ShipDesignBalance, ShipDesignResult } from '../types';

/**
 * The managed weight breakdown, read the way a reader meets it: the six groups,
 * each role's own estimate and adopted mass, the ledger's authoritative balance
 * that is read rather than rebuilt, and the frozen role comparison of two saved
 * results.
 *
 * The sharp edges are the point. An unknown value is not a zero; a saved zero or
 * negative is a fact; a duplicated role identity is one conflict rather than a
 * sum; a change needs a shared basis; and a value that became unknown is a change
 * with an unknown difference, while two unknowns are not a change at all.
 */

afterEach(cleanup);

const wb = (key: Parameters<typeof weightBreakdownCopy>[1]) => weightBreakdownCopy('zh-CN', key);

type Roles = Record<string, Record<string, unknown>>;

function native(over: Partial<ShipDesignResult> = {}, roles: Roles = {}, balance: ShipDesignBalance = {}): ShipDesignResult {
  return {
    schema: SHIP_DESIGN_RESULT_SCHEMA,
    method_version: SHIP_DESIGN_METHOD_VERSION,
    status: 'available',
    basis_condition_id: 'normal',
    ledger: { roles, complete: true },
    balance,
    ...over,
  } as ShipDesignResult;
}

const renderReader = (node: ReactNode) =>
  renderZh(<UnitProvider preferences={CANONICAL_PREFERENCES}>{node}</UnitProvider>);

const section = () => document.querySelector('[data-weight-breakdown]') as HTMLElement;

describe('reading the managed weight ledger', () => {
  it('keeps the six groups in order and each role s own readings', () => {
    const reading = readWeightBreakdown(native({}, {
      structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated', item_ids: ['hull.structure'] },
      other: {},
    }));
    expect(reading.supported).toBe(true);
    expect(reading.groups.map(group => group.key))
      .toEqual(['structure', 'armament', 'armour', 'machinery', 'fuel', 'other']);
    const structure = reading.groups[0];
    expect(structure.roles.map(role => role.role)).toEqual(['structure']);
    expect(structure.estimateT).toBe(10);
    expect(structure.selectedT).toBe(12);
    expect(structure.roles[0]).toMatchObject({
      estimateT: 10, selectedT: 12, mode: 'estimated', itemIds: ['hull.structure'], adoptionDeltaT: 2,
    });
    expect(structure.complete).toBe(true);
  });

  it('orders each group s roles as the group declares them, keeping unknown roles in other', () => {
    const reading = readWeightBreakdown(native({}, {
      auxiliary: { estimate_t: 5, selected_mass_t: 5, mode: 'estimated' },
      guns: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' },
      mystery_role: { estimate_t: 2, selected_mass_t: 2, mode: 'estimated' },
    }));
    const armament = reading.groups.find(group => group.key === 'armament')!;
    expect(armament.roles.map(role => role.role)).toEqual(['guns', 'auxiliary']);
    const other = reading.groups.find(group => group.key === 'other')!;
    expect(other.roles.map(role => role.role)).toEqual(['mystery_role']);
  });

  it('prints no total for an empty group, and keeps a known adopted sum when only the estimate is unknown', () => {
    const reading = readWeightBreakdown(native({}, {
      belt_main: { estimate_t: 5000, selected_mass_t: 5000, mode: 'estimated' },
      deck: { estimate_t: null, selected_mass_t: 700, mode: 'declared' },
    }));
    const machinery = reading.groups.find(group => group.key === 'machinery')!;
    expect(machinery.populated).toBe(false);
    expect(machinery.estimateT).toBeNull();
    expect(machinery.selectedT).toBeNull();
    // The two dimensions are independent: the unknown estimate does not discard
    // the independently known adopted sum.
    const armour = reading.groups.find(group => group.key === 'armour')!;
    expect(armour.populated).toBe(true);
    expect(armour.allKnown).toBe(false);
    expect(armour.complete).toBe(false);
    expect(armour.estimateT).toBeNull();
    expect(armour.selectedT).toBe(5700);
  });

  it('keeps unknown, zero and negative distinct', () => {
    const reading = readWeightBreakdown(native({}, {
      structure: { estimate_t: 0, selected_mass_t: 0, mode: 'estimated' },
      machinery: { estimate_t: -5, selected_mass_t: 3, mode: 'estimated' },
      fuel: { estimate_t: null, selected_mass_t: 5, mode: 'declared' },
    }));
    const structure = reading.roles.find(role => role.role === 'structure')!;
    expect(structure.estimateT).toBe(0);
    expect(structure.adoptionDeltaT).toBe(0);
    const machinery = reading.roles.find(role => role.role === 'machinery')!;
    expect(machinery.estimateT).toBe(-5);
    expect(machinery.adoptionDeltaT).toBe(8);
    const fuel = reading.roles.find(role => role.role === 'fuel')!;
    expect(fuel.estimateT).toBeNull();
    expect(fuel.selectedT).toBe(5);
    expect(fuel.adoptionDeltaT).toBeNull();
  });

  it('collapses a duplicated role identity to one conflict, even when the values match', () => {
    const reading = readWeightBreakdown(native({}, {
      machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated', item_ids: ['m1'] },
      machinery_again: { role: 'machinery', estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated', item_ids: ['m1'] },
    }));
    expect(reading.roles.map(role => role.role)).toEqual(['machinery']);
    const conflict = reading.roles[0];
    expect(conflict.conflict).toBe(true);
    expect(conflict.estimateT).toBeNull();
    expect(conflict.selectedT).toBeNull();
    expect(conflict.mode).toBeNull();
    expect(conflict.itemIds).toEqual([]);
    const machinery = reading.groups.find(group => group.key === 'machinery')!;
    expect(machinery.estimateT).toBeNull();
    expect(machinery.complete).toBe(false);
  });

  it('does not treat the optional other classification as pending, and reads the ledger s completeness', () => {
    const reading = readWeightBreakdown(native({}, {
      other: {},
      machinery: { estimate_t: 1, selected_mass_t: 1, mode: 'declared' },
    }));
    const other = reading.roles.find(role => role.role === 'other')!;
    expect(other.mode).toBeNull();
    expect(other.unresolved).toBe(false);
    expect(reading.complete).toBe(true);
    expect(readWeightBreakdown(native({ ledger: { roles: {}, complete: false } })).complete).toBe(false);
  });

  it.each([
    ['absent', null, 'absent'],
    ['unsupported_schema', native({ schema: 'plimsoll-other-1' }), 'unsupported_schema'],
    ['unsupported_method', native({ method_version: 'other-v0' }), 'unsupported_method'],
    ['unavailable status', native({ status: 'model_limit' }), 'unavailable'],
  ])('names the problem %s and shows no residual number', (_label, raw, problem) => {
    const reading = readWeightBreakdown(raw);
    expect(reading.supported).toBe(false);
    expect(reading.problem).toBe(problem);
    expect(reading.balance).toEqual({ selectedT: null, estimateT: null, targetT: null, differenceT: null });
    expect(reading.roles).toEqual([]);
    expect(reading.groups.every(group => group.estimateT === null && group.selectedT === null)).toBe(true);
  });

  it('withholds a balance the result carried when it has no readable ledger', () => {
    const reading = readWeightBreakdown(native({ ledger: null },
      {}, { selected_mass_t: 999, estimated_mass_t: 1, target_displacement_t: 1000, difference_t: -1 }));
    expect(reading.supported).toBe(false);
    expect(reading.problem).toBe('unavailable');
    expect(reading.balance.selectedT).toBeNull();
    expect(reading.balance.differenceT).toBeNull();
  });

  it('reads the balance from the ledger and never rebuilds it from the group sums', () => {
    const reading = readWeightBreakdown(native({},
      { structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated' } },
      { selected_mass_t: 999, estimated_mass_t: 1, target_displacement_t: 1000, difference_t: -1 }));
    expect(reading.groups[0].estimateT).toBe(10);
    expect(reading.groups[0].selectedT).toBe(12);
    expect(reading.balance.estimateT).toBe(1);
    expect(reading.balance.selectedT).toBe(999);
    expect(reading.balance.differenceT).toBe(-1);
  });

  it('reads the basis from the ledger when the result does not carry it at the top level', () => {
    const result = native({ basis_condition_id: undefined, ledger: { roles: { machinery: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' } }, complete: true, basis_condition_id: 'deep' } });
    expect(readWeightBreakdown(result).basisConditionId).toBe('deep');
  });

  it('keeps the two group dimensions independent', () => {
    const reading = readWeightBreakdown(native({}, {
      guns: { estimate_t: null, selected_mass_t: 120, mode: 'declared' },
      mounts: { estimate_t: null, selected_mass_t: 80, mode: 'declared' },
    }));
    const armament = reading.groups.find(group => group.key === 'armament')!;
    expect(armament.estimateT).toBeNull();
    expect(armament.selectedT).toBe(200);
    expect(armament.allKnown).toBe(false);
  });

  it('states missing expected fixed roles and keeps the group incomplete', () => {
    const reading = readWeightBreakdown(native({}, { guns: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' } }));
    const armament = reading.groups.find(group => group.key === 'armament')!;
    expect(armament.populated).toBe(true);
    expect(armament.allKnown).toBe(true);
    expect(armament.complete).toBe(false);
    expect(armament.missing).toEqual(['mounts', 'gun_armour', 'ammunition', 'auxiliary']);
    // The optional aggregate never invents a missing role.
    const other = reading.groups.find(group => group.key === 'other')!;
    expect(other.missing).toEqual([]);
  });

  it('reconciles the determinate role sums against the ledger balance and never overrides it', () => {
    const reading = readWeightBreakdown(native({},
      { structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated' } },
      { estimated_mass_t: 10, selected_mass_t: 99 }));
    expect(reading.reconciliation.determinate).toBe(true);
    expect(reading.reconciliation.roleEstimateT).toBe(10);
    expect(reading.reconciliation.roleSelectedT).toBe(12);
    expect(reading.reconciliation.estimateMatches).toBe(true);
    expect(reading.reconciliation.selectedMatches).toBe(false);
    expect(reading.reconciliation.verdict).toBe('mismatch');
    // The balance is read, never rebuilt from the sums that disagree with it.
    expect(reading.balance.selectedT).toBe(99);
  });

  it('cannot reconcile while any role is unknown, and reports that rather than a false verdict', () => {
    const reading = readWeightBreakdown(native({},
      { structure: { estimate_t: null, selected_mass_t: 1, mode: 'declared' } },
      { estimated_mass_t: 1, selected_mass_t: 1 }));
    expect(reading.reconciliation.determinate).toBe(false);
    expect(reading.reconciliation.roleEstimateT).toBeNull();
    expect(reading.reconciliation.estimateMatches).toBeNull();
    expect(reading.reconciliation.verdict).toBe('unknown');
  });

  it('treats a blank basis as no basis, so nothing can be compared', () => {
    const baseline = native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated' } });
    const blank = native({ basis_condition_id: '   ' }, { structure: { estimate_t: 12, selected_mass_t: 12, mode: 'estimated' } });
    expect(readWeightBreakdown(blank).basisConditionId).toBeNull();
    const reading = readWeightBreakdown(blank, baseline);
    expect(reading.comparable).toBe(false);
    expect(reading.roles.every(role => !role.changed)).toBe(true);
    expect(weightComparisonRows(blank, baseline).comparable).toBe(false);
  });

  it('keeps a missing or malformed completeness flag unknown, never an invented false', () => {
    expect(readWeightBreakdown(native({ ledger: { roles: { structure: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' } } } })).complete).toBeNull();
    expect(readWeightBreakdown(native({ ledger: { roles: {}, complete: 'yes' as unknown as boolean } })).complete).toBeNull();
    expect(readWeightBreakdown(native({ ledger: { roles: {}, complete: false } })).complete).toBe(false);
  });
});

describe('comparing a readable result with the saved baseline', () => {
  const baseline = native({},
    { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] },
      guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g'] },
      deck: { estimate_t: 5, selected_mass_t: 5, mode: 'estimated', item_ids: ['d'] } });

  it('requires one known shared basis before anything counts as a change', () => {
    const current = native({ basis_condition_id: 'deep' },
      { structure: { estimate_t: 12, selected_mass_t: 12, mode: 'estimated', item_ids: ['a'] } });
    const reading = readWeightBreakdown(current, baseline);
    expect(reading.comparable).toBe(false);
    expect(reading.roles.every(role => !role.changed)).toBe(true);
    expect(reading.groups.every(group => !group.changed)).toBe(true);
  });

  it('marks a changed value and leaves an unchanged role alone', () => {
    const current = native({},
      { structure: { estimate_t: 12, selected_mass_t: 12, mode: 'estimated', item_ids: ['a'] },
        guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g'] } });
    const reading = readWeightBreakdown(current, baseline);
    expect(reading.comparable).toBe(true);
    expect(reading.roles.find(role => role.role === 'structure')!.changed).toBe(true);
    expect(reading.roles.find(role => role.role === 'guns')!.changed).toBe(false);
    expect(reading.groups.find(group => group.key === 'structure')!.changed).toBe(true);
    expect(reading.groups.find(group => group.key === 'armament')!.changed).toBe(false);
  });

  it('counts a new known role and a known-to-unknown change, but not two unknowns', () => {
    const current = native({},
      { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] },
        guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g'] },
        deck: { estimate_t: null, selected_mass_t: null, mode: null, item_ids: [] },
        fuel: { estimate_t: 1, selected_mass_t: 1, mode: 'declared', item_ids: ['f'] } });
    const reading = readWeightBreakdown(current, baseline);
    expect(reading.roles.find(role => role.role === 'deck')!.changed).toBe(true);
    expect(reading.roles.find(role => role.role === 'fuel')!.changed).toBe(true);

    const unknownBaseline = native({}, { deck: { estimate_t: null, selected_mass_t: null, mode: null, item_ids: [] } });
    const unknownCurrent = native({}, { deck: { estimate_t: null, selected_mass_t: null, mode: null, item_ids: [] } });
    expect(readWeightBreakdown(unknownCurrent, unknownBaseline).roles[0].changed).toBe(false);
  });

  it('counts a policy or binding change even when no mass moved', () => {
    const current = native({},
      { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'declared', item_ids: ['a'] },
        guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g2'] } });
    const reading = readWeightBreakdown(current, baseline);
    expect(reading.roles.find(role => role.role === 'structure')!.changed).toBe(true);
    expect(reading.roles.find(role => role.role === 'guns')!.changed).toBe(true);
  });

  it('counts a known-to-conflict change', () => {
    const current = native({},
      { machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' },
        machinery_again: { role: 'machinery', estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' } });
    const withMachinery = native({}, { machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' } });
    const reading = readWeightBreakdown(current, withMachinery);
    expect(reading.roles[0].conflict).toBe(true);
    expect(reading.roles[0].changed).toBe(true);
  });

  it('rebuilds the groups from the marked roles, so a policy change reaches the group it belongs to', () => {
    const current = native({},
      { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'declared', item_ids: ['a'] } });
    const reading = readWeightBreakdown(current, baseline);
    const structure = reading.groups.find(group => group.key === 'structure')!;
    // Same masses, different policy: the group is changed because its role is.
    expect(structure.estimateT).toBe(10);
    expect(structure.selectedT).toBe(10);
    expect(structure.roles[0].changed).toBe(true);
    expect(structure.changed).toBe(true);
  });
});

describe('the frozen role comparison', () => {
  const current = native({},
    { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] },
      fuel: { estimate_t: 100, selected_mass_t: 100, mode: 'declared', item_ids: ['f'] } });
  const comparison = native({},
    { structure: { estimate_t: 15, selected_mass_t: 12, mode: 'declared', item_ids: ['b'] },
      machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated', item_ids: ['m'] } });

  it('lists the ordered union and states the difference as comparison minus current', () => {
    const reading = weightComparisonRows(current, comparison);
    expect(reading.comparable).toBe(true);
    expect(reading.rows.map(row => row.role)).toEqual(['structure', 'machinery', 'fuel']);
    const structure = reading.rows[0];
    expect(structure.estimateDeltaT).toBe(5);
    expect(structure.selectedDeltaT).toBe(2);
    expect(structure.modeChanged).toBe(true);
    expect(structure.bindingChanged).toBe(true);
  });

  it('leaves a role absent on one side unknown rather than zero', () => {
    const reading = weightComparisonRows(current, comparison);
    const machinery = reading.rows.find(row => row.role === 'machinery')!;
    expect(machinery.current.present).toBe(false);
    expect(machinery.current.estimateT).toBeNull();
    expect(machinery.estimateDeltaT).toBeNull();
    const fuel = reading.rows.find(row => row.role === 'fuel')!;
    expect(fuel.comparison.present).toBe(false);
    expect(fuel.selectedDeltaT).toBeNull();
  });

  it('keeps each comparison dimension independent, so one unknown never hides the other difference', () => {
    const left = native({}, { guns: { estimate_t: null, selected_mass_t: 6100, mode: 'declared' } });
    const right = native({}, { guns: { estimate_t: null, selected_mass_t: 6000, mode: 'declared' } });
    const reading = weightComparisonRows(left, right);
    const guns = reading.rows.find(row => row.role === 'guns')!;
    expect(guns.selectedDeltaT).toBe(-100);
    expect(guns.estimateDeltaT).toBeNull();
    expect(guns.changed).toBe(true);
  });

  it('shows no difference for a conflicting role', () => {
    const conflicted = native({},
      { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated' },
        structure_again: { role: 'structure', estimate_t: 30, selected_mass_t: 30, mode: 'estimated' } });
    const reading = weightComparisonRows(current, conflicted);
    const structure = reading.rows.find(row => row.role === 'structure')!;
    expect(structure.conflict).toBe(true);
    expect(structure.estimateDeltaT).toBeNull();
    expect(structure.selectedDeltaT).toBeNull();
    expect(structure.modeChanged).toBe(false);
    expect(structure.changed).toBe(false);
  });

  it('refuses to compare two results that do not share one known basis', () => {
    const other = native({ basis_condition_id: 'deep' },
      { structure: { estimate_t: 15, selected_mass_t: 15, mode: 'estimated' } });
    const reading = weightComparisonRows(current, other);
    expect(reading.comparable).toBe(false);
    expect(reading.rows).toEqual([]);
  });

  it('names a missing side when neither result is readable', () => {
    expect(weightComparisonRows(null, null)).toMatchObject({ comparable: false, problem: 'absent' });
    expect(weightComparisonRows(native(), native({ schema: 'plimsoll-other-1' })))
      .toMatchObject({ comparable: false, problem: 'unsupported_schema' });
  });
});

describe('the weight breakdown reader', () => {
  it('withholds every number while a change is pending and when it failed', () => {
    for (const state of ['pending', 'failed'] as const) {
      const { unmount } = renderReader(<WeightBreakdownReadings result={native()} state={state} />);
      expect(section().dataset.state).toBe(state);
      expect(document.querySelector('[data-weight-balance]')).toBeNull();
      expect(screen.getByRole('status')).toHaveTextContent(wb(`weight.state.${state}`));
      unmount();
    }
  });

  it('reads the balance, the groups and the chart from one projection', () => {
    renderReader(<WeightBreakdownReadings
      result={native({}, {
        structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated', item_ids: ['a'] },
        guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g'] },
      }, { selected_mass_t: 12, estimated_mass_t: 10, target_displacement_t: 20, difference_t: -8 })}
      onEditRole={() => {}} />);
    expect(within(document.querySelector('[data-weight-balance]') as HTMLElement)
      .getByText('12 t')).toBeVisible();
    expect(document.querySelector('[data-weight-balance-row="difference"]')!.textContent).toContain('-8');
    expect(document.querySelector('[data-weight-chart-group="structure"]')).not.toBeNull();
    expect(document.querySelectorAll('[data-weight-chart-group]')).toHaveLength(1);
    expect(document.querySelector('[data-weight-role="structure"]')).not.toBeNull();
  });

  it('switches the reading panel on a group selection without writing anything', () => {
    const onEditRole = vi.fn();
    renderReader(<WeightBreakdownReadings
      result={native({}, {
        structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] },
        guns: { estimate_t: 1000, selected_mass_t: 1000, mode: 'estimated', item_ids: ['g'] },
      })} onEditRole={onEditRole} />);
    expect(document.querySelector('[data-weight-chart-group="structure"]')).not.toBeNull();
    fireEvent.click(screen.getByRole('button', { name: new RegExp(wb('weight.group.armament')) }));
    expect(onEditRole).not.toHaveBeenCalled();
    expect(document.querySelector('[data-weight-chart-group="structure"]')).toBeNull();
    expect(document.querySelector('[data-weight-chart-group="armament"]')).not.toBeNull();
  });

  it('reveals the real binding only when the reader asks for it', () => {
    const onEditRole = vi.fn();
    renderReader(<WeightBreakdownReadings
      result={native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] } })}
      onEditRole={onEditRole} />);
    expect(onEditRole).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: wb('weight.reveal') }));
    expect(onEditRole).toHaveBeenCalledWith('structure');
  });

  it('shows one conflict row with its own words and no reveal', () => {
    renderReader(<WeightBreakdownReadings
      result={native({}, {
        machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' },
        machinery_again: { role: 'machinery', estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' },
      })} onEditRole={() => {}} />);
    expect(screen.getByText(wb('weight.role.conflict.title'))).toBeVisible();
    expect(document.querySelector('[data-weight-role="machinery"][data-conflict="true"]')).not.toBeNull();
    expect(screen.queryByRole('button', { name: wb('weight.reveal') })).toBeNull();
    expect(screen.getByText(wb('weight.groups.incomplete'))).toBeVisible();
  });

  it('draws a saved zero as no bar and a negative bar to the left of the zero line', () => {
    renderReader(<WeightBreakdownReadings
      result={native({}, {
        structure: { estimate_t: 0, selected_mass_t: 0, mode: 'estimated' },
        machinery: { estimate_t: -5, selected_mass_t: 3, mode: 'estimated' },
      })} />);
    const zeroBar = document.querySelector('[data-weight-chart-group="structure"] .weight-bar--estimate') as HTMLElement;
    expect(zeroBar.style.width).toBe('0%');
    fireEvent.click(screen.getByRole('button', { name: new RegExp(wb('weight.group.machinery')) }));
    const negative = document.querySelector('[data-weight-chart-group="machinery"] .weight-bar--estimate') as HTMLElement;
    const positive = document.querySelector('[data-weight-chart-group="machinery"] .weight-bar--selected') as HTMLElement;
    expect(negative.style.left).toBe('0%');
    expect(parseFloat(positive.style.left)).toBeGreaterThan(parseFloat(negative.style.left));
  });

  it('follows the reader s mass display preference and keeps the saved result intact', () => {
    const result = native({},
      { structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated' } },
      { selected_mass_t: 12, estimated_mass_t: 10 });
    const before = JSON.stringify(result);
    renderZh(<UnitProvider preferences={{ ...CANONICAL_PREFERENCES, mass: 'kg' }}>
      <WeightBreakdownReadings result={result} />
    </UnitProvider>);
    expect(within(document.querySelector('[data-weight-balance]') as HTMLElement).getByText('12,000 kg')).toBeVisible();
    expect(JSON.stringify(result)).toBe(before);
  });

  it('offers no selection and no reveal in the frozen shape', () => {
    const onEditRole = vi.fn();
    renderReader(<WeightBreakdownReadings state="frozen"
      result={native({}, { structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated', item_ids: ['a'] } })}
      onEditRole={onEditRole} />);
    expect(section().dataset.state).toBe('frozen');
    expect(document.querySelector('[data-weight-select]')).toBeNull();
    expect(screen.queryByRole('button', { name: wb('weight.reveal') })).toBeNull();
    expect(document.querySelector('[data-weight-role="structure"]')).not.toBeNull();
  });

  it('keeps every role fact in the frozen own-reading, without needing a comparison', () => {
    renderReader(<WeightBreakdownReadings state="frozen"
      result={native({}, {
        structure: { estimate_t: 10, selected_mass_t: 12, mode: 'estimated', item_ids: ['a'] },
        machinery: { estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' },
        machinery_again: { role: 'machinery', estimate_t: 6000, selected_mass_t: 6000, mode: 'estimated' },
      })} />);
    const list = document.querySelector('[data-weight-role-readings]') as HTMLElement;
    expect(list).not.toBeNull();
    const row = list.querySelector('[data-weight-role="structure"]') as HTMLElement;
    expect(row.textContent).toContain('10');
    expect(row.textContent).toContain('12');
    expect(row.textContent).toContain(wb('weight.mode.estimated'));
    expect(row.textContent).toContain('a');
    expect(row.querySelector('[data-weight-edit]')).toBeNull();
    // The conflict note is present too, even without a comparison to host it.
    expect(within(list).getByText(wb('weight.role.conflict.note'))).toBeVisible();
  });

  it('renders data-changed on the role and its group for a policy change with equal masses', () => {
    const baseline = native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] } });
    renderReader(<WeightBreakdownReadings baseline={baseline}
      result={native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'declared', item_ids: ['a'] } })} />);
    expect(document.querySelector('[data-weight-role="structure"][data-changed="true"]')).not.toBeNull();
    expect(document.querySelector('[data-weight-group="structure"]')!.getAttribute('data-changed')).toBe('true');
  });

  it('states the reconciliation verdict and names the missing expected roles', () => {
    renderReader(<WeightBreakdownReadings result={native({},
      { guns: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' } },
      { estimated_mass_t: 1, selected_mass_t: 1 })} />);
    const reconcile = document.querySelector('[data-weight-reconcile]') as HTMLElement;
    expect(reconcile.getAttribute('data-weight-verdict')).toBe('match');
    expect(within(reconcile).getByText(wb('weight.reconcile.sum'))).toBeVisible();
    expect(document.querySelector('[data-weight-group-missing="armament"]')).not.toBeNull();
    expect(document.querySelector('[data-weight-reconcile-note]')!.textContent)
      .toContain(wb('weight.reconcile.match'));
  });

  it('says the ledger declared no completeness rather than inventing one', () => {
    renderReader(<WeightBreakdownReadings
      result={native({ ledger: { roles: { structure: { estimate_t: 1, selected_mass_t: 1, mode: 'estimated' } } } })} />);
    expect(document.querySelector('[data-weight-status]')!.textContent).toContain(wb('weight.complete.unknown'));
  });
});

describe('the frozen role comparison panel', () => {
  const current = native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated', item_ids: ['a'] } });
  const comparison = native({}, { structure: { estimate_t: 15, selected_mass_t: 12, mode: 'declared', item_ids: ['b'] } });

  it('renders the union table with the comparison-minus-current direction stated', () => {
    renderZh(<UnitProvider preferences={CANONICAL_PREFERENCES}>
      <WeightRoleComparison current={current} comparison={comparison} />
    </UnitProvider>);
    expect(document.querySelector('[data-weight-comparison][data-comparable="true"]')).not.toBeNull();
    expect(screen.getByRole('table')).toBeVisible();
    expect(screen.getByText(wb('weight.comparison.direction'))).toBeVisible();
    const row = document.querySelector('[data-weight-comparison-row="structure"]') as HTMLElement;
    expect(row.textContent).toContain('+5 t');
    expect(row.textContent).toContain('+2 t');
  });

  it('shows a named reason and no table when the two runs are not comparable', () => {
    renderZh(<UnitProvider preferences={CANONICAL_PREFERENCES}>
      <WeightRoleComparison current={current} comparison={null} />
    </UnitProvider>);
    expect(document.querySelector('[data-weight-comparison][data-comparable="false"]')).not.toBeNull();
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByRole('status')).toHaveTextContent(wb('weight.state.absent'));
  });

  it('states the unknown dimension of a difference instead of dropping it', () => {
    const left = native({}, { guns: { estimate_t: null, selected_mass_t: 6100, mode: 'declared' } });
    const right = native({}, { guns: { estimate_t: null, selected_mass_t: 6000, mode: 'declared' } });
    renderZh(<UnitProvider preferences={CANONICAL_PREFERENCES}>
      <WeightRoleComparison current={left} comparison={right} />
    </UnitProvider>);
    const row = document.querySelector('[data-weight-comparison-row="guns"]') as HTMLElement;
    expect(row.textContent).toContain('−100 t');
    expect(row.textContent).toContain(wb('weight.comparison.estimate'));
    expect(row.textContent).toContain(wb('weight.unknown'));
  });
});

describe('the managed ledger section host state', () => {
  const previewResult = native({}, { structure: { estimate_t: 10, selected_mass_t: 10, mode: 'estimated' } });

  function ledgerHost(over: Partial<ShipDesignHost> = {}): ShipDesignHost {
    return {
      project: null, design: null, source: null,
      state: { confirmed: null, display: null, preview: previewResult, diagnostics: [], status: null, pending: 0, busy: false, error: null },
      nativePreview: previewResult,
      catalogue: null, catalogError: null, hasMigration: false,
      busy: false, pending: 0, error: null,
      submitCommand: () => {}, commitField: () => {}, replaceSource: () => {},
      initialize: () => {}, importFile: () => {}, fromMigration: () => {}, retry: () => {},
      ...over,
    } as unknown as ShipDesignHost;
  }

  it('is failed on a queue error or a setup error, and withholds the stale ledger', () => {
    for (const host of [
      ledgerHost({ state: { ...ledgerHost().state, error: 'Offline' } }),
      ledgerHost({ error: 'setup failed' }),
    ]) {
      const { unmount } = renderReader(<ShipDesignLedgerSection host={host} disabled={false} />);
      expect(document.querySelector('[data-weight-breakdown]')!.getAttribute('data-state')).toBe('failed');
      expect(document.querySelector('.sps-ledger-table')).toBeNull();
      expect(screen.queryByRole('button', { name: wb('weight.reveal') })).toBeNull();
      unmount();
    }
  });

  it('is pending on a busy, disabled or still-pending host, and never shows the stale table', () => {
    for (const host of [
      ledgerHost({ state: { ...ledgerHost().state, pending: 1 } }),
      ledgerHost({ pending: 1 }),
      ledgerHost({ busy: true }),
    ]) {
      const { unmount } = renderReader(<ShipDesignLedgerSection host={host} disabled={false} />);
      expect(document.querySelector('[data-weight-breakdown]')!.getAttribute('data-state')).toBe('pending');
      expect(document.querySelector('.sps-ledger-table')).toBeNull();
      unmount();
    }
    const { unmount } = renderReader(<ShipDesignLedgerSection host={ledgerHost()} disabled />);
    expect(document.querySelector('[data-weight-breakdown]')!.getAttribute('data-state')).toBe('pending');
    unmount();
  });

  it('shows the ready reading and its legacy table once the host settles', () => {
    renderReader(<ShipDesignLedgerSection host={ledgerHost()} disabled={false} />);
    expect(document.querySelector('[data-weight-breakdown]')!.getAttribute('data-state')).toBe('ready');
    expect(document.querySelector('.sps-ledger-table')).not.toBeNull();
  });
});

describe('the weight breakdown dictionary', () => {
  it('declares the same keys in English and Chinese', () => {
    expect(Object.keys(weightBreakdownDictionary('zh-CN')).sort())
      .toEqual(Object.keys(weightBreakdownDictionary('en')).sort());
  });
});

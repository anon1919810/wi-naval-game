import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { effectiveItemMass, isUnresolved, sameGovernedSlice } from '../components/shipDesign';
import { Sps3b3Readings } from '../components/Sps3b3Readings';
import { SHIP_DESIGN_METHOD_VERSION, SHIP_DESIGN_RESULT_SCHEMA } from '../components/sps3b3Model';
import type { ProjectDocument } from '../types';

afterEach(cleanup);
const project = () => ({ schema: 'plimsoll-project-1', id: 'p', name: 'Projection', revision: 1,
  hull: {}, geometry: null,
  loading_conditions: [{ id: 'normal', label: 'Normal', overrides: { a: { mass_t: 5 } } }],
  weight_groups: [{ id: 'g', label: 'Weights', items: [{ id: 'a', mass_t: 100,
    design_mass: { owner: 'ship_design', condition_id: 'normal', mass_t: null } }] }],
  ship_design: { schema: 'plimsoll-ship-design-1', condition_id: 'normal', source: 'test', notes: null,
    parameters: { beam_moulded: 25, hull_scale: 1 }, editing: {},
    mass_bindings: { guns: { mode: 'estimated', item_ids: ['a'] }, deck: { mode: 'estimated', item_ids: ['b'] } } },
} as unknown as ProjectDocument);

it('does not dirty a design because the server reordered JSON object properties', () => {
  const a = project(), b = structuredClone(a);
  const design = b.ship_design as Record<string, unknown>;
  design.parameters = Object.fromEntries(Object.entries(design.parameters as object).reverse());
  design.mass_bindings = Object.fromEntries(Object.entries(design.mass_bindings as object).reverse());
  expect(sameGovernedSlice(a, b)).toBe(true);
});

it('keeps unknown scoped and declared mass unknown instead of falling back to base mass', () => {
  const p = project();
  expect(effectiveItemMass(p, 'a')).toBeNull();
  delete p.weight_groups[0].items[0].design_mass;
  (p.loading_conditions[0].overrides as Record<string, unknown>).a = { mass_t: null };
  expect(effectiveItemMass(p, 'a')).toBeNull();
});

it('does not call an unused optional payload role a pending binding', () => {
  expect(isUnresolved({ role: 'other', mode: null, item_ids: [], estimate_t: 0, selected_mass_t: 0 })).toBe(false);
});

/** One frozen native reply; the ledger may be withheld to prove no residual leaks. */
const nativeReply = (withLedger: boolean) => ({
  schema: SHIP_DESIGN_RESULT_SCHEMA, method_version: SHIP_DESIGN_METHOD_VERSION,
  status: 'available', basis_condition_id: 'normal',
  balance: { selected_mass_t: 1111, estimated_mass_t: 1000, target_displacement_t: 1000, difference_t: 111 },
  ...(withLedger ? {
    ledger: { complete: true, basis_condition_id: 'normal',
      selected_mass_t: 1111, estimated_mass_t: 1000, target_displacement_t: 1000, difference_t: 111,
      roles: { machinery: { mode: 'declared', estimate_t: 1000, selected_mass_t: 1111, item_ids: ['a'] } } },
  } : {}),
  report: { text: 'Frozen source', sections: [{ id: 'source', title: 'Source', lines: ['Frozen source'] }] },
});

it('reads the saved native balance through the weight reading instead of a duplicate block', () => {
  const { container } = render(<Sps3b3Readings variant="native" data={nativeReply(true)} />);
  expect(screen.getByText('Frozen source')).toBeVisible();
  // The authoritative four totals now live in the managed weight reading.
  expect(container.querySelector('.ship-design-balance')).toBeNull();
  expect(container.querySelector('[data-weight-balance-row="selected"] dd')?.textContent ?? '').toMatch(/1,111/);
  expect(container.querySelector('[data-weight-balance-row="difference"] dd')?.textContent ?? '').toMatch(/111/);
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
});

it('keeps a balance that has no readable ledger off the sheet', () => {
  const { container } = render(<Sps3b3Readings variant="native" data={nativeReply(false)} />);
  expect(screen.getByText('Frozen source')).toBeVisible();
  const reading = container.querySelector('[data-weight-breakdown]');
  expect(reading?.getAttribute('data-state')).toBe('unavailable');
  // The raw audit may still quote the payload; the reading itself must not.
  expect(reading?.textContent ?? '').not.toMatch(/1,111/);
});

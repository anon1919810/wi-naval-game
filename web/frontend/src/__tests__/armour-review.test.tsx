import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { useState } from 'react';
import { afterEach, expect, it } from 'vitest';
import { ArmourReviewEditor } from '../components/FixedArmourEditor';
import { ConceptComponentReadings } from '../components/ConceptComponentReadings';
import { UnitProvider } from '../components/UnitProvider';
import { conceptCopy } from '../i18n/concept';
import { reportMetrics } from '../components/reportMetrics';
import type { StageEnvelope } from '../types';
afterEach(cleanup);
const c = (key: Parameters<typeof conceptCopy>[1]) => conceptCopy('en', key);

it('enables explicit unknown angle, keeps a negative declaration and disables without touching other sections', () => {
  let last: Record<string, unknown> = {};
  function Editor() {
    const [config, setConfig] = useState<Record<string, unknown>>({ cost: { source: 'kept' } });
    return <ArmourReviewEditor config={config} commit={next => { last = next; setConfig(next); }} />;
  }
  render(<UnitProvider preferences={null}><Editor /></UnitProvider>);
  fireEvent.click(screen.getByLabelText(c('armourReview.enable')));
  expect(last.armour_review).toEqual({ source: null, belt_inclination_deg: null });
  fireEvent.change(screen.getByLabelText(c('armourReview.angle')), { target: { value: '-30' } });
  expect(last.armour_review).toMatchObject({ belt_inclination_deg: -30 });
  fireEvent.change(screen.getByLabelText(c('armourReview.angle')), { target: { value: '' } });
  expect(last.armour_review).toMatchObject({ belt_inclination_deg: null });
  fireEvent.click(screen.getByLabelText(c('armourReview.enable')));
  expect(last).toEqual({ cost: { source: 'kept' } });
});

const data = { armour_review: { status: 'available', method_version: 'review-v1',
  provenance: { belt_inclination_deg: -30, declared_source: 'controlled declaration' },
  values: { minimum_main_belt_length_m: 52.003048 },
  checks: [{ id: 'height:main', record_id: 'main', code: 'height', status: 'warning',
    values: { declared_height_m: 9, maximum_height_m: 8.006096 } }] } };
const stage = { requested: true, status: 'completed', data,
  method_versions: { methods: { armour_review: 'review-v1' } } } as unknown as StageEnvelope;

it('prints returned checks only under the saved report gate', () => {
  const { rerender } = render(<UnitProvider preferences={null}>
    <ConceptComponentReadings data={data} envelope={stage} /></UnitProvider>);
  expect(screen.getByText(c('armourReview.warning'))).toBeVisible();
  expect(screen.getByText('-30.000 °')).toBeVisible();
  expect(screen.getByText('controlled declaration')).toBeVisible();
  expect(screen.getByText('8.006096 m')).toBeVisible();
  rerender(<UnitProvider preferences={null}><ConceptComponentReadings data={data}
    envelope={{ ...stage, status: 'unavailable' }} /></UnitProvider>);
  expect(screen.queryByText(c('armourReview.title'))).toBeNull();
});

it('blocks minimum-length comparison if either method identity is missing', () => {
  const metric = (value: StageEnvelope) => reportMetrics('design_balance', value)[0];
  expect(metric(stage)).toMatchObject({ value: 52.003048, blocked: false, dimension: 'length' });
  expect(metric({ ...stage, method_versions: {} })).toMatchObject({ blocked: true });
  expect(metric({ ...stage, data: { armour_review: { ...data.armour_review, method_version: null } } }))
    .toMatchObject({ blocked: true });
});

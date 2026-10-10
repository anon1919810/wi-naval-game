import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { CoreEvidence } from './Inspector';
import type { LabResult } from './types';

afterEach(cleanup);
it('plots negative GZ samples inside the chart and keeps unavailable gaps open', () => {
  const result = { simulated_duration_s: 0, assumptions: [], method_versions: {}, validity: {}, diagnostics: [],
    core_analysis: { stages: { flooding: { status: 'completed', data: { remaining_gz: { rows: [
      { angle_deg: -20, gz_m: -.2 }, { angle_deg: -10, gz_m: null },
      { angle_deg: 0, gz_m: 0 }, { angle_deg: 10, gz_m: .1 }, { angle_deg: 20, gz_m: .2 },
    ] } } } } } } as unknown as LabResult;
  render(<CoreEvidence result={result} />);
  const chart = screen.getByRole('img', { name: '最终接受状态的剩余稳性曲线' });
  expect(screen.getByText('-20°')).toBeInTheDocument();
  expect(screen.getByText('20°')).toBeInTheDocument();
  for (const point of chart.querySelectorAll('circle')) {
    expect(Number(point.getAttribute('cx'))).toBeGreaterThanOrEqual(20);
    expect(Number(point.getAttribute('cx'))).toBeLessThanOrEqual(340);
  }
  const segments = chart.querySelectorAll('polyline');
  expect(segments).toHaveLength(2);
  expect(segments[0].getAttribute('points')!.trim().split(' ')).toHaveLength(1);
  expect(segments[1].getAttribute('points')!.trim().split(' ')).toHaveLength(3);
});

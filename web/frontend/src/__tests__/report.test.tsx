import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { Report } from '../pages/Report';
import { completedFixture, partialFixture } from './fixtures';

afterEach(cleanup);

describe('stored report semantics', () => {
  it('keeps a partial calculation readable and names its limited stage', () => {
    render(<Report result={partialFixture} runId="r1" />);
    expect(screen.getByText('部分完成')).toBeVisible();
    expect(screen.getByText('超出方法适用范围')).toBeVisible();
    expect(screen.queryByText('历史验证通过')).toBeNull();
    expect(screen.getByText(/request-123/)).toBeVisible();
  });

  it('does not turn unavailable deck coverage into a computed zero', () => {
    render(<Report result={partialFixture} runId="r1" />);
    expect(screen.getByText('甲板端点资料不足')).toBeVisible();
    expect(screen.queryByText('0 %')).toBeNull();
    expect(screen.getByRole('link', { name: /JSON/ })).toHaveAttribute('href', '/api/runs/r1/export?format=json');
    expect(screen.getByRole('link', { name: /CSV/ })).toHaveAttribute('href', '/api/runs/r1/export?format=csv');
  });

  it('marks incompatible method comparisons instead of showing a numeric delta', () => {
    const changed = structuredClone(completedFixture);
    changed.method_versions = { coordinator: 'different-version' };
    changed.request_fingerprint = 'request-456';
    render(<Report result={completedFixture} compareResult={changed} />);
    expect(screen.getByText(/不可直接比较/)).toBeVisible();
    expect(screen.getByText(/request-456/)).toBeVisible();
  });

  it('refuses deltas when a stage kernel version changed', () => {
    const changed = structuredClone(completedFixture);
    changed.stages.loading.method_versions = { kernel: 'new-kernel' };
    render(<Report result={completedFixture} compareResult={changed} />);
    expect(screen.getByText(/不可直接比较/)).toBeVisible();
  });

  it('shows resistance and shaft-power rows with applicability and estimate labels', () => {
    const actualShape = structuredClone(completedFixture);
    actualShape.stages.resistance = {
      ...actualShape.stages.resistance,
      requested: true, status: 'completed', reason: null, diagnostics: [], assumptions: [], method_versions: {},
      data: {
        method: 'holtrop_mennen_1982', estimate: true, primary_result: false,
        scenario: { source: 'Illustrative sourced study' }, validity: { model_applicable: false },
        rows: [{ speed_kn: 18, total_resistance_kn: 765.9, effective_power_kw: 7092.1,
          complete: true, estimate: true, primary_result: false, model_applicable: false }],
        power_rows: [{ speed_kn: 18, qpc: { value: 0.55, source: 'QPC study', estimate: true },
          effective_power_kw: 7092.1, shaft_power_kw: 12894.8, shaft_power_shp: 17292.2,
          complete: true, estimate: true, primary_result: false }],
      },
    };
    render(<Report result={actualShape} />);
    expect(screen.getByText('765.9 kN')).toBeVisible();
    expect(screen.getByText('12,894.8 kW')).toBeVisible();
    expect(screen.getByText('QPC study')).toBeVisible();
    expect(screen.getAllByText(/不在经验适用范围/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/工程估算/).length).toBeGreaterThan(0);
  });
});

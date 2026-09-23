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
});

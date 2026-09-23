import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { StageStatus } from '../components/StageStatus';
import { completedFixture, partialFixture } from './fixtures';

afterEach(cleanup);

describe('stage status', () => {
  it('keeps an unrequested stage distinct from an unavailable one', () => {
    render(<><StageStatus name="flooding" stage={completedFixture.stages.flooding} />
      <StageStatus name="deck" stage={partialFixture.stages.deck} /></>);
    expect(screen.getByText('未请求')).toBeVisible();
    expect(screen.getByText('资料不足')).toBeVisible();
    expect(screen.getByText('甲板端点资料不足')).toBeVisible();
  });

  it('renders a true zero and its unit, preserving source and estimate flags', () => {
    const stage = structuredClone(completedFixture.stages.loading);
    stage.data = { output: { value: 0, unit: 't', source: '量测记录', estimate: true } };
    render(<StageStatus name="loading" stage={stage} />);
    expect(screen.getByText('0 t')).toBeVisible();
    expect(screen.getByText('量测记录')).toBeVisible();
    expect(screen.getByText('工程估算')).toBeVisible();
  });
});

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { StageStatus } from '../components/StageStatus';
import type { StageEnvelope } from '../types';
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

  it('is the stage\'s own positioning and focus target', () => {
    render(<StageStatus name="deck" stage={partialFixture.stages.deck} />);
    const card = document.getElementById('stage-deck')!;
    expect(card.tagName).toBe('ARTICLE');
    expect(card.querySelector('h3')!.getAttribute('tabindex')).toBe('-1');
  });

  it('shows a severe diagnostic in place and folds an ordinary one away', () => {
    const stage = structuredClone(completedFixture.stages.resistance);
    stage.status = 'failed';
    stage.requested = true;
    stage.reason = '阻力表缺失';
    stage.diagnostics = [
      { code: 'resistance.no_bracket', severity: 'error', path: '$.stages.resistance', message: '速度网格内没有完整单调功率区间' },
      { code: 'resistance.estimate', severity: 'warning', path: '$.stages.resistance', message: '使用工程估算方法' },
      // The same wording as the stage reason is one finding, not two: the
      // message is not repeated, but its evidence stays reachable.
      { code: 'resistance.repeat', severity: 'warning', path: '$.stages.resistance.data', source_path: '$.stages.resistance', message: '阻力表缺失' },
    ];
    render(<StageStatus name="resistance" stage={stage} />);

    const open = document.querySelectorAll('.stage-diagnostics-open');
    expect(open).toHaveLength(1);
    expect(screen.getByText('速度网格内没有完整单调功率区间')).toBeVisible();
    expect(open[0].getAttribute('role')).toBe('alert');
    // The ordinary finding stays reachable, but behind the disclosure.
    expect(screen.getByText('使用工程估算方法')).toBeInTheDocument();
    expect(document.querySelector('.stage-diagnostics')).not.toBeNull();
    expect(document.querySelector('.stage-diagnostics')!.hasAttribute('open')).toBe(false);
    // The reason is stated once, and the diagnostic that repeats it keeps its
    // code and both of its paths instead of being dropped.
    expect(screen.getAllByText('阻力表缺失')).toHaveLength(1);
    expect(screen.getByText(/resistance\.repeat/)).toBeInTheDocument();
    expect(screen.getByText('$.stages.resistance.data')).toBeInTheDocument();
    expect(document.querySelector('.stage-diagnostics')!.textContent).toContain('2 条');
  });

  it('treats a blocking warning as a serious finding, because it blocks the stage', () => {
    const stage = structuredClone(completedFixture.stages.equilibrium);
    stage.status = 'model_limit';
    stage.requested = true;
    stage.reason = '超出方法适用范围';
    stage.diagnostics = [
      // `blocking` is what a saved payload can carry; the shared diagnostic
      // type does not name it yet, so the stage reads it defensively.
      { code: 'equilibrium.out_of_range', severity: 'warning', blocking: true, path: '$.stages.equilibrium', message: '横倾超出小角度假设' },
      { code: 'equilibrium.note', severity: 'info', path: '$.stages.equilibrium', message: '使用外推系数' },
    ] as StageEnvelope['diagnostics'];
    render(<StageStatus name="equilibrium" stage={stage} />);
    const open = document.querySelectorAll('.stage-diagnostics-open');
    expect(open).toHaveLength(1);
    expect(screen.getByText('横倾超出小角度假设')).toBeVisible();
    expect(document.querySelector('.stage-diagnostics')!.textContent).not.toContain('横倾超出小角度假设');
    // The ordinary note is still there, and nothing was discarded.
    expect(screen.getByText('使用外推系数')).toBeInTheDocument();
  });

  it('never presents residual numbers of a blocked stage as results', () => {
    const stage = structuredClone(completedFixture.stages.hydrostatics);
    stage.status = 'unavailable';
    stage.requested = true;
    stage.reason = '型线资料不足';
    stage.data = { values: { gm_t_m: 9.99, waterline_d_m: 10.25 } };
    render(<StageStatus name="hydrostatics" stage={stage} />);
    expect(screen.getByText('型线资料不足')).toBeVisible();
    expect(screen.queryByText('9.99')).toBeNull();
    expect(screen.queryByText('10.25')).toBeNull();
    // The raw payload is still reachable, so nothing is lost by not showing it.
    expect(screen.getByText('完整阶段数据与来源')).toBeInTheDocument();
  });

  it('names declared design and trial powers, and keeps the saved balance readings', () => {
    const stage = structuredClone(completedFixture.stages.propulsion);
    stage.status = 'completed';
    stage.requested = true;
    stage.data = { values: { power_design_kw: 12000, power_trial_kw: 13500, power_design_shp: 16000, power_trial_shp: 18000 } };
    const equilibrium = structuredClone(completedFixture.stages.equilibrium);
    equilibrium.status = 'completed';
    equilibrium.requested = true;
    equilibrium.data = { waterline_above_keel_m: 9.92, heel_deg: 0 };
    render(<><StageStatus name="propulsion" stage={stage} />
      <StageStatus name="equilibrium" stage={equilibrium} /></>);
    expect(screen.getAllByText('设计轴功率（设计声明）')).toHaveLength(2);
    expect(screen.getAllByText('试航轴功率（试航声明）')).toHaveLength(2);
    expect(screen.getByText('16,000 shp')).toBeVisible();
    expect(screen.getByText('18,000 shp')).toBeVisible();
    expect(screen.getByText('龙骨基准水线高度')).toBeVisible();
    expect(screen.getByText('横倾角')).toBeVisible();
  });

  it('draws the GZ curve once, inside its own finished stage', () => {
    const gz = structuredClone(completedFixture.stages.gz);
    gz.status = 'completed';
    gz.requested = true;
    gz.data = { rows: [{ angle_deg: 0, gz_m: 0 }, { angle_deg: 20, gz_m: 0.35 }, { angle_deg: 40, gz_m: 0.28 }] };
    render(<><StageStatus name="gz" stage={gz} />
      <StageStatus name="hydrostatics" stage={completedFixture.stages.hydrostatics} /></>);
    const plots = document.querySelectorAll('.stability-plot');
    expect(plots).toHaveLength(1);
    expect(plots[0].closest('#stage-gz')).not.toBeNull();

    // An unfinished gz stage carries no curve.
    const blocked = structuredClone(gz);
    blocked.status = 'model_limit';
    cleanup();
    render(<StageStatus name="gz" stage={blocked} />);
    expect(document.querySelectorAll('.stability-plot')).toHaveLength(0);
  });

  it('shows a severe stage reason once and retains all diagnostic evidence without a payload', () => {
    const stage = structuredClone(partialFixture.stages.deck);
    stage.diagnostics = [{ code: 'analysis.unavailable', severity: 'error', blocking: true,
      message: stage.reason!, path: '$.request.deck', source_path: '$.input_snapshot.deck' }] as StageEnvelope['diagnostics'];
    render(<StageStatus name="deck" stage={stage} />);
    expect(screen.getAllByText('甲板端点资料不足')).toHaveLength(1);
    expect(screen.getByText('analysis.unavailable')).toBeVisible();
    expect(screen.getByText('$.request.deck')).toBeVisible();
    expect(screen.getByText('来源 $.input_snapshot.deck')).toBeVisible();
  });

  it('does not display specialized results from an unrequested residual payload', () => {
    const resistance = structuredClone(completedFixture.stages.resistance);
    resistance.data = { power_rows: [{ speed_kn: 18, shaft_power_kw: 100, complete: true }] };
    const flooding = structuredClone(completedFixture.stages.flooding);
    flooding.data = { status: 'completed', cumulative_sea_exchange_m3: 4.5 };
    render(<><StageStatus name="resistance" stage={resistance} /><StageStatus name="flooding" stage={flooding} /></>);
    expect(document.querySelector('.resistance-results')).toBeNull();
    expect(document.querySelector('.flooding-results')).toBeNull();
    expect(screen.getAllByText('完整阶段数据与来源')).toHaveLength(2);
  });

  it('separates saved resistance method trials from failed residual data', () => {
    const stage = structuredClone(completedFixture.stages.resistance);
    stage.requested = true;
    stage.status = 'failed';
    stage.data = { power_rows: [{ speed_kn: 18, shaft_power_kw: 100, complete: true }] };
    const view = render(<StageStatus name="resistance" stage={stage} />);
    expect(document.querySelector('.resistance-results')).toBeNull();
    view.rerender(<StageStatus name="resistance" stage={{ ...stage, status: 'model_limit' }} />);
    expect(screen.getByText('以下为模型越界试算，不作为有效工作点。')).toBeVisible();
    expect(screen.getByText('轴功率与推进系数')).toBeVisible();
  });
});

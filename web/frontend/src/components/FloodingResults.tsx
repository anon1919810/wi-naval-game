import { number, object, rows, type Raw } from './formModel';
import { useUnits } from './UnitProvider';
import type { Dimension } from './units';
import { formatNumber } from './units';

export type { Dimension };

// Flooding result facts, read straight from the stored run payload.
//
// Nothing is recomputed here, and a partial trajectory is never presented as a
// completed one: the reported status, stop reason and the requested-versus-
// simulated time stay exactly as the kernel recorded them. Volumes, masses,
// angles and lengths follow the reader's unit; durations, densities, forces and
// conservation thresholds keep their canonical units.

const STATUS_LABELS: Record<string, string> = {
  completed: '推进到请求时长或网络静止', model_limit: '模型越界停止',
  downflooding_event: '发生开口浸没事件', equilibrium_failure: '平衡求解失败',
  canceled: '按取消请求停止', invalid_input: '输入无效，未开始求解', running: '未完成',
};
const STOP_LABELS: Record<string, string> = {
  scheduled_completion: '到达请求时长', equal_heads_or_no_open_flow: '网络水头平衡，无活动流动',
  hydraulic_equilibrium_tolerance: '水头差在声明容差内（推进时间短于请求时长）',
  partial_aperture: '液面越过有限开口高度', receiver_capacity: '接收舱室已满', dry_out: '舱室排空',
  step_limit: '达到步数上限', timestep_limit: '时间步长达到模型下限',
  downflooding_event: '已接受状态下开放点浸没', equilibrium_failure: '平衡求解失败',
  canceled: '已请求取消', invalid_input: '输入校验失败',
};

function stateRow(entry: Raw) { return object(entry.equilibrium); }

export function FloodingResults({ data }: { data: Raw }) {
  const units = useUnits();
  const status = typeof data.status === 'string' ? data.status : 'unknown';
  const stop = typeof data.stop_reason === 'string' ? data.stop_reason : '';
  const scenario = object(data.scenario);
  const timeline = rows(data.timeline);
  const finalState = data.final_state === null || data.final_state === undefined ? null : object(data.final_state);
  const requested = number(scenario.duration_s);
  // Durations and step limits are canonical seconds and never rescaled.
  const simulated = finalState ? number(finalState.time_s) : null;
  const validity = object(data.validity);
  const tankIds = Object.keys(object(finalState?.volumes_m3 ?? {})).length > 0
    ? Object.keys(object(finalState?.volumes_m3)) : Object.keys(object(object(timeline[0]).volumes_m3));
  // Long trajectories stay readable: sample at most twelve accepted states and
  // say so, keeping the complete record available in the raw stage payload.
  const sample = timeline.length <= 12 ? timeline
    : Array.from({ length: 12 }, (_, index) => timeline[Math.round(index * (timeline.length - 1) / 11)]);
  const downflooding = object(data.downflooding);

  return <div className="flooding-results">
    <p className="result-context">破损阶段状态：<strong>{STATUS_LABELS[status] ?? status}</strong>
      {stop && <> · 停止原因：{STOP_LABELS[stop] ?? stop}（{stop}）</>}
      {/* numerical_convergence is three-state: only a real false means "did not
          converge", and null stays unknown. */}
      {validity.numerical_convergence === false && ' · 数值收敛：否'}
      {validity.numerical_convergence === null && ' · 数值收敛：未知'}
      {validity.model_applicable === false && ' · 不在方法适用范围'}
      {validity.complete === false && ' · 未完成：不得当作完整结果'}</p>
    <div className="metric-grid">
      <Datum label="请求时长" text={requested === null ? '未知' : `${requested} s`} note="场景声明的进水时长（规范秒）" />
      <Datum label="实际推进时间" text={simulated === null ? '未知' : `${simulated} s`}
        note={simulated === null || requested === null ? '无可接受状态' : simulated < requested ? '未达请求时长即停止' : '达到请求时长'} />
      <Datum label="水量守恒误差" text={units.text(data.volume_conservation_error_m3, 'volume')} note="独立于时间离散精度的守恒判据" />
      <Datum label="质量守恒误差" text={units.text(data.mass_conservation_error_t, 'mass')} note="独立于时间离散精度的守恒判据" />
      <Datum label="初始水量" text={units.text(data.initial_total_water_volume_m3, 'volume')}
        note={`质量 ${units.text(data.initial_total_water_mass_t, 'mass')}，为账本之外的附加质量`} />
      <Datum label="累计海水交换" text={units.text(data.cumulative_sea_exchange_m3, 'volume')}
        note={`质量 ${units.text(data.cumulative_sea_exchange_t, 'mass')}`} />
      <Datum label="已接受状态数" text={String(timeline.length)} note="失败候选不计入时间序列" />
    </div>
    {number(data.terminal_max_head_difference_m) !== null && <p className="form-hint">
      末态活动流动最大水头差 {units.text(data.terminal_max_head_difference_m, 'length')}，数值水头容差 {units.text(data.terminal_head_tolerance_m, 'length')}。
    </p>}
    {Object.keys(downflooding).length > 0 && <p className="form-hint">
      开口浸没评估：{String(downflooding.status ?? '未知')}{downflooding.event ? `（${String(object(downflooding.event).kind ?? object(downflooding.event).time_s ?? '已接受状态')}）` : ''}。
      开口定义来源：{String(data.coordinator_openings_origin ?? data.openings_origin ?? '未知')}。
    </p>}

    {sample.length > 0 && <div className="stage-table-scroll"><table className="stage-table">
      <caption>时间序列（{timeline.length} 个已接受状态{timeline.length > 12 ? '，等间隔抽样 12 行' : ''}）</caption>
      <thead><tr><th>时间 · s</th>{tankIds.map(key => <th key={key}>{key} · {units.unit('volume')}</th>)}<th>舱内总水量 · {units.unit('volume')}</th><th>横倾 · {units.unit('angle')}</th><th>纵倾 · {units.unit('angle')}</th><th>吃水 · {units.unit('length')}</th></tr></thead>
      <tbody>{sample.map((entry, index) => {
        const row = object(entry);
        const solved = stateRow(row);
        return <tr key={index}>
            <td>{number(row.time_s) === null ? '未知' : formatNumber(row.time_s as number)}</td>
          {tankIds.map(key => <td key={key}>{units.number(object(row.volumes_m3)[key], 'volume')}</td>)}
          <td>{units.number(row.total_onboard_water_volume_m3, 'volume')}</td>
          <td>{units.number(solved.heel_deg, 'angle')}</td>
          <td>{units.number(solved.trim_deg, 'angle')}</td>
          <td>{units.number(solved.waterline_above_keel_m, 'length')}</td>
        </tr>;
      })}</tbody></table></div>}

    {rows(object(data.remaining_gz).rows).length > 0 && <div className="stage-table-scroll"><table className="stage-table">
      <caption>剩余稳性曲线（最终已接受状态）</caption>
      <thead><tr><th>横倾角 · {units.unit('angle')}</th><th>剩余静性力臂 GZ · {units.unit('length')}</th></tr></thead>
      <tbody>{rows(object(data.remaining_gz).rows).map((row, index) => {
        const point = object(row);
        return <tr key={index}>
          <td>{units.number(point.angle_deg, 'angle')}</td><td>{units.number(point.gz_m, 'length')}</td>
        </tr>;
      })}</tbody></table></div>}
    {rows(data.gz_snapshots).length > 1 && <p className="form-hint">已保存 {rows(data.gz_snapshots).length} 组剩余稳性快照（每个已接受状态一组）。</p>}

    <p className="form-hint">初始液体按附加质量处理，不作沉性损失扣除，也不重复施加自由液面修正；数值时间离散误差不放宽守恒判据。正 GZ 或正采样值都不构成安全结论。</p>
  </div>;
}

function Datum({ label, text, note }: { label: string; text: string; note: string }) {
  const known = text !== '未知';
  return <div className={`fact-field fact-field--${known ? 'known' : 'unknown'}`}>
    <span className="fact-label">{label}</span>
    <strong className="fact-value">{text}</strong>
    <span className="fact-meta">{note}</span>
  </div>;
}

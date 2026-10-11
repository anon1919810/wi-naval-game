import { useState } from 'react';
import type { ReplayEntry, InspectionTarget } from './narrative';
import { SOURCE } from './narrative';
import { numeric } from './model';

export default function Replay({ entries, frame, playing, speed, onFrame, onPlaying, onSpeed, onInspect }: {
  entries: ReplayEntry[]; frame: number; playing: boolean; speed: number;
  onFrame: (frame: number) => void; onPlaying: (playing: boolean) => void;
  onSpeed: (speed: number) => void; onInspect: (target: InspectionTarget) => void;
}) {
  const [all, setAll] = useState(false);
  const entry = entries[frame];
  const displayed = entries.filter(e => all || e.significant);
  const jump = (next: number) => { onPlaying(false); onFrame(next); };
  return <section aria-label="回放结果" className="lab-replay">
    <div className="lab-replay-head"><span className="lab-kicker">03 / DAMAGE SEQUENCE</span>
      <strong>{numeric(entry?.time, 2)} s</strong><span>{entry?.eventIndex === -1 ? '命中前' : `记录 ${(entry?.eventIndex ?? 0) + 1}`}</span></div>
    <input aria-label="回放事件" type="range" min="0" max={Math.max(0, entries.length - 1)} step="1" value={frame} onChange={e => jump(Number(e.target.value))} />
    <div className="lab-replay-actions"><button onClick={() => jump(0)}>回到命中前</button>
      <button onClick={() => { if (frame >= entries.length - 1) onFrame(0); onPlaying(!playing); }}>{playing ? '暂停' : '播放'}</button>
      <button disabled={frame >= entries.length - 1} onClick={() => jump(entries.find(e => e.frame > frame && (all || e.significant))?.frame ?? entries.length - 1)}>下一变化 →</button>
      <button onClick={() => jump(entries.length - 1)}>最终接受状态</button>
      <label>回放速度<select aria-label="回放速度" value={speed} onChange={e => onSpeed(Number(e.target.value))}><option value=".5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select></label></div>
    <div className="lab-current-event" aria-label="当前变化">
      <h3>{entry?.title}</h3>
      {entry?.changes.length ? entry.changes.map((change, i) => <div key={i} className="lab-change">
        <span className="lab-kicker">{SOURCE[change.source]}</span>
        {change.target ? <button className="lab-change-link" onClick={() => onInspect(change.target!)}>{change.detail}<span aria-hidden="true"> ↗</span></button> : <p>{change.detail}</p>}
      </div>) : <p className="lab-note">{frame === 0 ? '模块与乘员使用已声明初值；船体姿态尚无平衡解。' : '本条保留原始记录；没有新增的模块或乘员变化。'}</p>}
    </div>
    <div className="lab-timeline-head"><span className="lab-kicker">EVENT INDEX / ACCEPTED SNAPSHOTS</span>
      <label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />全部记录 ({entries.length})</label></div>
    <ol className="lab-timeline" aria-label="损伤事件记录">{displayed.map(item => <li key={item.frame}>
      <button aria-current={frame === item.frame ? 'step' : undefined} onClick={() => { jump(item.frame); if (item.targets[0]) onInspect(item.targets[0]); }}>
        <span className="lab-event-time">{numeric(item.time, 2)}<small> s · {item.eventIndex < 0 ? 'PRE' : String(item.eventIndex + 1).padStart(2, '0')}</small></span>
        <span>{item.title}{item.changes.length > 1 && <small> +{item.changes.length - 1}</small>}</span><span aria-hidden="true">→</span>
      </button></li>)}</ol>
    <p className="lab-note">记录顺序保留同一时刻的多个事件。停机与撤离在首次记录的接受状态显示；回放保持视角。</p>
  </section>;
}

import { useState } from 'react';
import type { ReplayEntry, InspectionTarget } from './narrative';
import { useLabCopy } from '../i18n/lab';
import { useLabFormat } from '../i18n/labFormat';

export default function Replay({ entries, frame, playing, speed, onFrame, onPlaying, onSpeed, onInspect }: {
  entries: ReplayEntry[]; frame: number; playing: boolean; speed: number;
  onFrame: (frame: number) => void; onPlaying: (playing: boolean) => void;
  onSpeed: (speed: number) => void; onInspect: (target: InspectionTarget) => void;
}) {
  const l = useLabCopy();
  const f = useLabFormat();
  const [all, setAll] = useState(false);
  const entry = entries[frame];
  const displayed = entries.filter(e => all || e.significant);
  const jump = (next: number) => { onPlaying(false); onFrame(next); };
  return <section aria-label={l('replay.label')} className="lab-replay">
    <div className="lab-replay-head"><span className="lab-kicker">{l('replay.kicker')}</span>
      <strong>{f.numeric(entry?.time, 2)} s</strong><span>{entry?.eventIndex === -1 ? l('replay.before') : l('replay.record', { index: (entry?.eventIndex ?? 0) + 1 })}</span></div>
    <input aria-label={l('replay.eventAria')} type="range" min="0" max={Math.max(0, entries.length - 1)} step="1" value={frame} onChange={e => jump(Number(e.target.value))} />
    <div className="lab-replay-actions"><button onClick={() => jump(0)}>{l('replay.toStart')}</button>
      <button onClick={() => { if (frame >= entries.length - 1) onFrame(0); onPlaying(!playing); }}>{playing ? l('replay.pause') : l('replay.play')}</button>
      <button disabled={frame >= entries.length - 1} onClick={() => jump(entries.find(e => e.frame > frame && (all || e.significant))?.frame ?? entries.length - 1)}>{l('replay.next')}</button>
      <button onClick={() => jump(entries.length - 1)}>{l('replay.final')}</button>
      <label>{l('replay.speed')}<select aria-label={l('replay.speed')} value={speed} onChange={e => onSpeed(Number(e.target.value))}><option value=".5">0.5×</option><option value="1">1×</option><option value="2">2×</option></select></label></div>
    <div className="lab-current-event" aria-label={l('replay.currentLabel')}>
      <h3>{entry?.title}</h3>
      {entry?.changes.length ? entry.changes.map((change, i) => <div key={i} className="lab-change">
        <span className="lab-kicker">{l(`source.${change.source}` as 'source.game' | 'source.core' | 'source.mixed')}</span>
        {change.target ? <button className="lab-change-link" onClick={() => onInspect(change.target!)}>{change.detail}<span aria-hidden="true"> ↗</span></button> : <p>{change.detail}</p>}
      </div>) : <p className="lab-note">{frame === 0 ? l('replay.emptyFirst') : l('replay.emptyOther')}</p>}
    </div>
    <div className="lab-timeline-head"><span className="lab-kicker">{l('replay.indexKicker')}</span>
      <label><input type="checkbox" checked={all} onChange={e => setAll(e.target.checked)} />{l('replay.allRecords', { count: entries.length })}</label></div>
    <ol className="lab-timeline" aria-label={l('replay.timelineLabel')}>{displayed.map(item => <li key={item.frame}>
      <button aria-current={frame === item.frame ? 'step' : undefined} onClick={() => { jump(item.frame); if (item.targets[0]) onInspect(item.targets[0]); }}>
        <span className="lab-event-time">{f.numeric(item.time, 2)}<small> s · {item.eventIndex < 0 ? l('replay.pre') : String(item.eventIndex + 1).padStart(2, '0')}</small></span>
        <span>{item.title}{item.changes.length > 1 && <small> +{item.changes.length - 1}</small>}</span><span aria-hidden="true">→</span>
      </button></li>)}</ol>
    <p className="lab-note">{l('replay.note')}</p>
  </section>;
}
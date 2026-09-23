import type { RunView } from '../types';
import { FactField } from './FactField';
import type { DeckInput, DeckPoint, DeckSegment, MeasureField } from './deckModel';

interface DeclaredFreeboard {
  values: Record<string, unknown>;
  segments: Array<Record<string, unknown>>;
  diagnostics: Array<Record<string, unknown>>;
}

function numeric(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

// Most recent run that carries a deck declared-freeboard result. The aggregate
// values come from the backend computation — the editor never recomputes them.
function pickDeclaredFreeboard(runs: RunView[]): DeclaredFreeboard | null {
  const withData = runs
    .filter(run => {
      const data = run.result?.stages?.deck?.data;
      return !!data && !!(data as Record<string, unknown>).declared_freeboard;
    })
    .sort((a, b) => String(b.created_at ?? '').localeCompare(String(a.created_at ?? '')));
  if (withData.length === 0) return null;
  const data = withData[0].result!.stages.deck.data as Record<string, unknown>;
  return data.declared_freeboard as DeclaredFreeboard;
}

function segmentResult(fb: DeclaredFreeboard | null, id: string): Record<string, unknown> | undefined {
  if (!fb) return undefined;
  return fb.segments.find(item => item.id === id);
}

// Tri-state estimate: unchecked = false, checked = true, indeterminate = undeclared.
function EstimateCheckbox({ value, onChange }: { value: boolean | null; onChange: (next: boolean | null) => void }) {
  return <>
    <input
      type="checkbox"
      aria-label="估算"
      ref={el => { if (el) el.indeterminate = value === null; }}
      checked={value === true}
      onChange={() => onChange(value === null ? true : value === true ? false : null)}
    />
    {value === null && <small>未声明</small>}
  </>;
}

export function DeckFreeboardEditor({ deck, runs, onPatchDeck }: {
  deck: DeckInput;
  runs: RunView[];
  onPatchDeck: (next: DeckInput) => void;
}) {
  const fb = pickDeclaredFreeboard(runs);
  const pointOptions = deck.points.map(p => p.id).filter(id => id.length > 0);

  function updatePoint(index: number, patch: Partial<DeckPoint>) {
    onPatchDeck({ ...deck, points: deck.points.map((p, i) => (i === index ? { ...p, ...patch } : p)) });
  }
  function updatePointFreeboard(index: number, patch: Partial<MeasureField>) {
    onPatchDeck({
      ...deck,
      points: deck.points.map((p, i) =>
        i === index ? { ...p, freeboard_m: { ...p.freeboard_m, ...patch } } : p),
    });
  }
  function addPoint() {
    onPatchDeck({
      ...deck,
      points: [...deck.points, { id: '', x_m: null, y_m: null, z_m: null, freeboard_m: { value: null, source: null, estimate: null } }],
    });
  }
  function removePoint(index: number) {
    onPatchDeck({ ...deck, points: deck.points.filter((_, i) => i !== index) });
  }

  function updateSegment(index: number, patch: Partial<DeckSegment>) {
    onPatchDeck({ ...deck, segments: deck.segments.map((s, i) => (i === index ? { ...s, ...patch } : s)) });
  }
  function addSegment() {
    onPatchDeck({
      ...deck,
      segments: [...deck.segments, { id: '', aft_point_id: null, fore_point_id: null, source: null, estimate: null }],
    });
  }
  function removeSegment(index: number) {
    onPatchDeck({ ...deck, segments: deck.segments.filter((_, i) => i !== index) });
  }

  function updateReference(patch: Partial<MeasureField>) {
    onPatchDeck({ ...deck, reference_length_m: { ...deck.reference_length_m, ...patch } });
  }

  return <div className="deck-editor">
    <div className="deck-group">
      <div className="deck-group-title"><h3>甲板点</h3><button type="button" className="text-button" onClick={addPoint}>添加点</button></div>
      {deck.points.length === 0
        ? <div className="deck-empty"><p>还没有甲板点。可从“高级：原始契约字段”粘贴，或点击“添加点”。</p></div>
        : deck.points.map((point, index) => (
          <div className="deck-row" key={index}>
            <label>点 id<input type="text" value={point.id} onChange={e => updatePoint(index, { id: e.target.value })} placeholder="如 aft-centre" /></label>
            <label>x · m<input type="number" step="any" value={point.x_m ?? ''} onChange={e => updatePoint(index, { x_m: e.target.value.trim() === '' ? null : Number(e.target.value) })} placeholder="未知" /></label>
            <label>干舷值 · m<input type="number" step="any" aria-label={`点 ${point.id} 干舷值`} value={point.freeboard_m.value ?? ''} onChange={e => updatePointFreeboard(index, { value: e.target.value.trim() === '' ? null : Number(e.target.value) })} placeholder="未知" /></label>
            <label>干舷来源<input type="text" aria-label={`点 ${point.id} 干舷来源`} value={point.freeboard_m.source ?? ''} onChange={e => updatePointFreeboard(index, { source: e.target.value })} placeholder="来源" /></label>
            <label>估算<EstimateCheckbox value={point.freeboard_m.estimate} onChange={next => updatePointFreeboard(index, { estimate: next })} /></label>
            <button type="button" className="text-button deck-remove" onClick={() => removePoint(index)} aria-label={`删除点 ${point.id || index}`}>删除</button>
          </div>
        ))}
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>分段</h3><button type="button" className="text-button" onClick={addSegment}>添加段</button></div>
      {deck.segments.length === 0
        ? <div className="deck-empty"><p>还没有分段。可从“高级：原始契约字段”粘贴，或点击“添加段”。</p></div>
        : deck.segments.map((segment, index) => {
          const sr = segmentResult(fb, segment.id);
          const lengthM = numeric(sr?.length_m);
          const lengthPct = numeric(sr?.length_percent);
          return (
            <div className="deck-row deck-row--segment" key={index}>
              <label>段 id<input type="text" value={segment.id} onChange={e => updateSegment(index, { id: e.target.value })} placeholder="如 centreline-profile" /></label>
              <label>艏端点<select value={segment.aft_point_id ?? ''} onChange={e => updateSegment(index, { aft_point_id: e.target.value || null })}>
                <option value="">未选择</option>
                {pointOptions.map(id => <option key={id} value={id}>{id}</option>)}
              </select></label>
              <label>艉端点<select value={segment.fore_point_id ?? ''} onChange={e => updateSegment(index, { fore_point_id: e.target.value || null })}>
                <option value="">未选择</option>
                {pointOptions.map(id => <option key={id} value={id}>{id}</option>)}
              </select></label>
              <span className="deck-readonly">长度：<strong>{lengthM === null ? '—' : `${lengthM} m`}</strong> · 占比：<strong>{lengthPct === null ? '—' : `${lengthPct} %`}</strong></span>
              <button type="button" className="text-button deck-remove" onClick={() => removeSegment(index)} aria-label={`删除段 ${segment.id || index}`}>删除</button>
            </div>
          );
        })}
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>参考长度</h3></div>
      <div className="deck-row">
        <label>参考长度 · m<input type="number" step="any" aria-label="参考长度值" value={deck.reference_length_m.value ?? ''} onChange={e => updateReference({ value: e.target.value.trim() === '' ? null : Number(e.target.value) })} placeholder="未知" /></label>
        <label>来源<input type="text" aria-label="参考长度来源" value={deck.reference_length_m.source ?? ''} onChange={e => updateReference({ source: e.target.value })} placeholder="来源" /></label>
        <label>估算<EstimateCheckbox value={deck.reference_length_m.estimate} onChange={next => updateReference({ estimate: next })} /></label>
      </div>
    </div>

    <div className="section-heading"><h2>聚合结果</h2><span>取自最近一次运行（不在此处复算）</span></div>
    {fb
      ? <>
        <div className="metric-grid">
          <FactField
            label="加权平均干舷"
            value={numeric(fb.values.weighted_mean_freeboard_m)}
            unit="m"
            status={fb.values.weighted_mean_freeboard_m == null ? 'unknown' : fb.values.weighted_mean_estimate ? 'estimate' : 'known'}
            source={typeof fb.values.weighted_mean_source === 'string' ? fb.values.weighted_mean_source : null}
          />
          <FactField
            label="覆盖度"
            value={fb.values.coverage_fraction == null ? null : Math.round((fb.values.coverage_fraction as number) * 1000) / 10}
            unit="%"
            status={fb.values.coverage_fraction == null ? 'unknown' : 'known'}
          />
          <FactField
            label="参考长度"
            value={numeric(fb.values.reference_length_m)}
            unit="m"
            status={fb.values.reference_length_m == null ? 'unknown' : 'known'}
            source={typeof fb.values.reference_source === 'string' ? fb.values.reference_source : null}
          />
        </div>
        {Array.isArray(fb.values.unknown_segment_ids) && (fb.values.unknown_segment_ids as string[]).length > 0 && (
          <p className="section-intro">未知段：{(fb.values.unknown_segment_ids as string[]).join('、')}</p>
        )}
      </>
      : <p className="section-intro">保存并运行后显示聚合值</p>}
  </div>;
}

import type { RunView } from '../types';
import { FactField } from './FactField';
import { QuantityField } from './QuantityField';
import { useUnits } from './UnitProvider';
import { declaredSource, TracedField, type TraceFact } from './InputTrace';
import { useWorkspaceCopy } from '../i18n/workspace';
import type { Dimension } from './units';
import type { DeckInput, DeckPoint, DeckSegment, MeasureField } from './deckModel';

// A deck measure's provenance is exactly what it stores: the value, the declared
// source and the tri-state estimate. Nothing is inferred from a sibling measure.
function measureFact(key: string, label: string, measure: MeasureField,
  dimension?: Dimension, storedUnit?: string, sourceOverride?: MeasureField['source']): TraceFact {
  const source = declaredSource(sourceOverride !== undefined ? sourceOverride : measure.source);
  return { key, label, value: sourceOverride !== undefined ? source : measure.value, dimension, storedUnit, source,
    estimate: measure.estimate === true ? true : measure.estimate === false ? false : null, path: key };
}

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
  const w = useWorkspaceCopy();
  return <>
    <input
      type="checkbox"
      aria-label={w('deck.estimateAria')}
      ref={el => { if (el) el.indeterminate = value === null; }}
      checked={value === true}
      onChange={() => onChange(value === null ? true : value === true ? false : null)}
    />
    {value === null && <small>{w('deck.undeclared')}</small>}
  </>;
}

export function DeckFreeboardEditor({ deck, runs, onPatchDeck }: {
  deck: DeckInput;
  runs: RunView[];
  onPatchDeck: (next: DeckInput) => void;
}) {
  const w = useWorkspaceCopy();
  const fb = pickDeclaredFreeboard(runs);
  const units = useUnits();
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
      <div className="deck-group-title"><h3>{w('deck.points.title')}</h3><button type="button" className="text-button" onClick={addPoint}>{w('deck.points.add')}</button></div>
      {deck.points.length === 0
        ? <div className="deck-empty"><p>{w('deck.points.empty')}</p></div>
        : deck.points.map((point, index) => (
          <div className="deck-row" key={index}>
            <label>{w('deck.pointId')}<input type="text" value={point.id} onChange={e => updatePoint(index, { id: e.target.value })} placeholder={w('deck.pointIdPlaceholder')} /></label>
            <QuantityField small label="x" aria-label={w('deck.pointAxisAria', { id: point.id, axis: 'x' })} value={point.x_m} dimension="length"
              onChange={value => updatePoint(index, { x_m: value })} />
            <QuantityField small label="y" aria-label={w('deck.pointAxisAria', { id: point.id, axis: 'y' })} value={point.y_m} dimension="length"
              onChange={value => updatePoint(index, { y_m: value })} />
            <QuantityField small label="z" aria-label={w('deck.pointAxisAria', { id: point.id, axis: 'z' })} value={point.z_m} dimension="length" kind="nonnegative"
              onChange={value => updatePoint(index, { z_m: value })} />
            {/* Each endpoint measures its own provenance: this point's freeboard
                never borrows the deck-level or segment-level source. */}
            <TracedField fact={measureFact(`deck.points[${point.id}].freeboard_m`, w('deck.pointFreeboard', { id: point.id }), point.freeboard_m, 'length', 'm')}>
            <QuantityField small label={w('deck.freeboardValue')} aria-label={w('deck.freeboardValueAria', { id: point.id })} value={point.freeboard_m.value} dimension="length" kind="nonnegative"
              onChange={value => updatePointFreeboard(index, { value })} />
            </TracedField>
            <TracedField fact={measureFact(`deck.points[${point.id}].freeboard_m.source`, w('deck.pointFreeboardSource', { id: point.id }), point.freeboard_m, undefined, undefined, point.freeboard_m.source ?? null)}>
            <label>{w('deck.freeboardSource')}<input type="text" aria-label={w('deck.pointFreeboardSource', { id: point.id })} value={declaredSource(point.freeboard_m.source) ?? ''} onChange={e => updatePointFreeboard(index, { source: e.target.value })} placeholder={w('fact.source')} /></label>
            </TracedField>
            <label>{w('deck.estimate')}<EstimateCheckbox value={point.freeboard_m.estimate} onChange={next => updatePointFreeboard(index, { estimate: next })} /></label>
            <button type="button" className="text-button deck-remove" onClick={() => removePoint(index)} aria-label={w('deck.removePointAria', { id: point.id || String(index) })}>{w('deck.remove')}</button>
          </div>
        ))}
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>{w('deck.segments.title')}</h3><button type="button" className="text-button" onClick={addSegment}>{w('deck.segments.add')}</button></div>
      {deck.segments.length === 0
        ? <div className="deck-empty"><p>{w('deck.segments.empty')}</p></div>
        : deck.segments.map((segment, index) => {
          const sr = segmentResult(fb, segment.id);
          const lengthM = numeric(sr?.length_m);
          const lengthPct = numeric(sr?.length_percent);
          return (
            <div className="deck-row deck-row--segment" key={index}>
              <label>{w('deck.segmentId')}<input type="text" value={segment.id} onChange={e => updateSegment(index, { id: e.target.value })} placeholder={w('deck.segmentIdPlaceholder')} /></label>
              <label>{w('deck.aftPoint')}<select aria-label={w('deck.pointAria', { id: segment.id, end: w('deck.aftPoint') })} value={segment.aft_point_id ?? ''} onChange={e => updateSegment(index, { aft_point_id: e.target.value || null })}>
                <option value="">{w('deck.unselected')}</option>
                {pointOptions.map(id => <option key={id} value={id}>{id}</option>)}
              </select></label>
              <label>{w('deck.forePoint')}<select aria-label={w('deck.pointAria', { id: segment.id, end: w('deck.forePoint') })} value={segment.fore_point_id ?? ''} onChange={e => updateSegment(index, { fore_point_id: e.target.value || null })}>
                <option value="">{w('deck.unselected')}</option>
                {pointOptions.map(id => <option key={id} value={id}>{id}</option>)}
              </select></label>
              <span className="deck-readonly">{w('deck.length')}<strong>{units.text(lengthM, 'length')}</strong>{w('deck.share')}<strong>{lengthPct === null ? '—' : `${lengthPct} %`}</strong></span>
              {/* A segment declares its own source; it is not the point's. */}
              <TracedField fact={{ key: `deck.segments[${segment.id}].source`, label: w('deck.segmentSource', { id: segment.id }),
                value: declaredSource(segment.source), source: declaredSource(segment.source), estimate: segment.estimate, path: `deck.segments[${segment.id}].source` }}>
                <span className="deck-segment-source">
                  <span>{w('fact.source')}</span>
                  <span className="deck-segment-source-value">{declaredSource(segment.source) ?? w('deck.undeclared')}</span>
                </span>
              </TracedField>
              <button type="button" className="text-button deck-remove" onClick={() => removeSegment(index)} aria-label={w('deck.removeSegmentAria', { id: segment.id || String(index) })}>{w('deck.remove')}</button>
            </div>
          );
        })}
    </div>

    <div className="deck-group">
      <div className="deck-group-title"><h3>{w('deck.reference.title')}</h3></div>
      <div className="deck-row">
        <TracedField fact={measureFact('deck.reference_length_m', w('deck.reference.length'), deck.reference_length_m, 'length', 'm')}>
        <QuantityField small label={w('deck.reference.length')} aria-label={w('deck.reference.lengthAria')} value={deck.reference_length_m.value} dimension="length" kind="positive"
          onChange={value => updateReference({ value })} />
        </TracedField>
        <TracedField fact={measureFact('deck.reference_length_m.source', w('deck.reference.source'), deck.reference_length_m, undefined, undefined, deck.reference_length_m.source ?? null)}>
        <label>{w('fact.source')}<input type="text" aria-label={w('deck.reference.source')} value={declaredSource(deck.reference_length_m.source) ?? ''} onChange={e => updateReference({ source: e.target.value })} placeholder={w('fact.source')} /></label>
        </TracedField>
        <label>{w('deck.estimate')}<EstimateCheckbox value={deck.reference_length_m.estimate} onChange={next => updateReference({ estimate: next })} /></label>
      </div>
    </div>

    <div className="section-heading"><h2>{w('deck.aggregate.title')}</h2><span>{w('deck.aggregate.note')}</span></div>
    {fb
      ? <>
        <div className="metric-grid">
          <FactField
            label={w('deck.aggregate.weightedMean')}
            value={numeric(fb.values.weighted_mean_freeboard_m)}
            dimension="length"
            status={fb.values.weighted_mean_freeboard_m == null ? 'unknown' : fb.values.weighted_mean_estimate ? 'estimate' : 'known'}
            source={typeof fb.values.weighted_mean_source === 'string' ? fb.values.weighted_mean_source : null}
          />
          <FactField
            label={w('deck.aggregate.coverage')}
            value={fb.values.coverage_fraction == null ? null : Math.round((fb.values.coverage_fraction as number) * 1000) / 10}
            unit="%"
            status={fb.values.coverage_fraction == null ? 'unknown' : 'known'}
          />
          <FactField
            label={w('deck.reference.length')}
            value={numeric(fb.values.reference_length_m)}
            dimension="length"
            status={fb.values.reference_length_m == null ? 'unknown' : 'known'}
            source={typeof fb.values.reference_source === 'string' ? fb.values.reference_source : null}
          />
        </div>
        {Array.isArray(fb.values.unknown_segment_ids) && (fb.values.unknown_segment_ids as string[]).length > 0 && (
          <p className="section-intro">{w('deck.aggregate.unknownSegments', { ids: (fb.values.unknown_segment_ids as string[]).join(w('form.listSeparator')) })}</p>
        )}
      </>
      : <p className="section-intro">{w('deck.aggregate.empty')}</p>}
  </div>;
}
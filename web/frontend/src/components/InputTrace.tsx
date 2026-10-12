import { createContext, useCallback, useContext, useEffect, useId, useMemo, useRef, useState, type ReactNode } from 'react';

import { useUnits } from './UnitProvider';
import { useMotionToken } from './useLocalMotion';
import { englishCopy } from './formModel';
import { useWorkspaceCopy } from '../i18n/workspace';
import type { Copy } from './diagnosticGuidance';
import type { Dimension } from './units';

/**
 * The selected input's provenance, and nothing else.
 *
 * A trace fact is only ever built from values the project actually stores: the
 * value itself, a declared `source` string and the three-state `estimate`. There
 * is no fallback text, so a field without provenance reads as unknown rather than
 * borrowing generic wording. A declared source is a statement about where a
 * number came from — it is never a claim of historical confirmation.
 */
export interface TraceFact {
  /** The field's own name in the project; mounted control identity is separate. */
  key: string;
  label: string;
  value: number | string | null;
  dimension?: Dimension;
  storedUnit?: string;
  /** Declared source text, exactly as stored, or null when none was declared. */
  source: string | null;
  /** True / false when declared, null when the project never declared it. */
  estimate: boolean | null;
  /** Where in the document this fact lives, for the reader. */
  path?: string;
}

export type TraceState = TraceFact | null;

/** Preserve an actual string or structured source declaration for inspection. */
export function declaredSource(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() ? value : null;
  if (value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length) return JSON.stringify(value);
  return null;
}

interface InputTraceApi {
  /** The live fact for the selected key, or null when nothing is selected. */
  fact: TraceState;
  /** Publishes one field's provenance to the panel. */
  selectedId: string | null;
  select: (id: string, fact: TraceFact) => void;
  /** Publishes the current value of an already selected field. */
  publish: (id: string, fact: TraceFact) => void;
  forget: (id: string) => void;
  reveal: () => void;
  revealVersion: number;
  clear: () => void;
}

const InputTraceContext = createContext<InputTraceApi>({ fact: null, selectedId: null, select: () => {}, publish: () => {}, forget: () => {}, reveal: () => {}, revealVersion: 0, clear: () => {} });

export function InputTraceProvider({ children, onReveal }: { children: ReactNode; onReveal?: () => void }) {
  const [selected, setSelected] = useState<{ id: string; fact: TraceFact } | null>(null);
  const [revealVersion, setRevealVersion] = useState(0);
  const publish = useCallback((id: string, fact: TraceFact) => {
    setSelected(previous => {
      if (previous?.id !== id) return previous;
      const old = previous.fact;
      if (old.value === fact.value && old.source === fact.source && old.estimate === fact.estimate
        && old.label === fact.label && old.key === fact.key && old.path === fact.path
        && old.dimension === fact.dimension && old.storedUnit === fact.storedUnit) return previous;
      return { id, fact };
    });
  }, []);
  const select = useCallback((id: string, fact: TraceFact) => setSelected({ id, fact }), []);
  const forget = useCallback((id: string) => setSelected(previous => previous?.id === id ? null : previous), []);
  const clear = useCallback(() => setSelected(null), []);
  const reveal = useCallback(() => { onReveal?.(); setRevealVersion(current => current + 1); }, [onReveal]);
  const api = useMemo<InputTraceApi>(() => ({
    fact: selected?.fact ?? null, selectedId: selected?.id ?? null,
    select, publish, forget, clear, reveal, revealVersion,
  }), [selected, select, publish, forget, clear, reveal, revealVersion]);
  // Focus that lands on a control with no declared provenance clears the trace
  // instead of leaving an unrelated field's facts on screen. Focus is never moved.
  return <InputTraceContext.Provider value={api}>
    <div className="input-trace" onFocusCapture={event => {
      const target = event.target as Element | null;
      if (!target?.closest?.('[data-trace-key], .trace-panel')) clear();
    }}>{children}</div>
  </InputTraceContext.Provider>;
}

export function useInputTrace(): InputTraceApi { return useContext(InputTraceContext); }

const ESTIMATE_LABELS = {
  estimate: 'trace.estimate.estimate', declared: 'trace.estimate.declared', unknown: 'trace.estimate.unknown',
} as const satisfies Record<'estimate' | 'declared' | 'unknown', Parameters<Copy>[0]>;

/**
 * The tri-state marker for one field. An estimate that was never declared is
 * `unknown`, which is deliberately different from `false`: "not declared" is
 * never read as "confirmed".
 */
export function estimateLabel(estimate: boolean | null, w: Copy = englishCopy): string {
  return w(ESTIMATE_LABELS[estimate === true ? 'estimate' : estimate === false ? 'declared' : 'unknown']);
}

export function estimateState(estimate: boolean | null): 'estimate' | 'declared' | 'unknown' {
  return estimate === true ? 'estimate' : estimate === false ? 'declared' : 'unknown';
}

/**
 * A compact marker placed next to the field it describes. It states only what the
 * project declares: a source, an engineering estimate, or an explicit unknown.
 */
export function SourceMark({ fact }: { fact: Pick<TraceFact, 'source' | 'estimate'> }) {
  const w = useWorkspaceCopy();
  const state = estimateState(fact.estimate);
  const text = fact.source
    ? state === 'estimate' ? w('trace.mark.estimate') : state === 'declared' ? w('trace.mark.declared') : w('trace.mark.declaredUnknownEstimate')
    : state === 'estimate' ? w('trace.mark.estimateUndeclaredSource') : w('trace.mark.unknownSource');
  return <span className={`source-mark source-mark--${fact.source ? state : 'none'}`} title={fact.source ?? undefined}>
    {text}
  </span>;
}

/**
 * Wraps one real input control. Focusing it selects its provenance without
 * moving focus, and the marker sits next to the control rather than replacing
 * any label or accessible name. An `id` lets a followed diagnostic address this
 * exact control without any selector built from project data.
 */
export function TracedField({ fact, children, className, id }: {
  fact: TraceFact; children: ReactNode; className?: string; id?: string;
}) {
  const key = useId();
  const { selectedId, select, publish, forget } = useInputTrace();
  const active = selectedId === key;
  useEffect(() => { if (active) publish(key, fact); }, [active, key, publish, fact.value, fact.source, fact.estimate, fact.label, fact.key, fact.path, fact.dimension, fact.storedUnit]);
  useEffect(() => () => forget(key), [forget, key]);
  return <div id={id} className={`traced-field ${active ? 'traced-field--active' : ''} ${className ?? ''}`}
    data-trace-key={fact.key}
    onFocusCapture={() => { if (!active) select(key, fact); }}>
    {children}
    <span className="field-provenance">
      <SourceMark fact={fact} />
      <TraceSelectButton id={key} fact={fact} />
    </span>
  </div>;
}

/** The button that publishes one field's provenance to the Trace panel. */
function TraceSelectButton({ id, fact }: { id: string; fact: TraceFact }) {
  const w = useWorkspaceCopy();
  const { selectedId, select, reveal } = useInputTrace();
  const active = selectedId === id;
  return <button type="button" className={`trace-pick ${active ? 'trace-pick--active' : ''}`}
    aria-pressed={active} onClick={() => { select(id, fact); reveal(); }}>
    <span aria-hidden="true">{w('trace.pick')}</span>
    <span className="visually-hidden">{w('trace.pickLabel', { label: fact.label })}</span>
  </button>;
}

function readValue(value: TraceFact['value'], w: Copy): string {
  if (value === null) return w('units.unknown');
  return String(value);
}

/**
 * The Trace panel. With no selection it stays a short guide; with a selection it
 * shows only that field's stored value, declared source and estimate state.
 */
export function TracePanel({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  const w = useWorkspaceCopy();
  const { fact, clear, revealVersion } = useInputTrace();
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (open && revealVersion > 0) panel.current?.scrollIntoView?.({ block: 'nearest', behavior: 'instant' });
  }, [open, revealVersion]);
  // The reveal follows the *field*, not its value: typing a new number into the
  // field that is already selected republishes the same fact and must not replay
  // anything. The panel itself is never re-keyed and never takes focus.
  const motion = useMotionToken(open ? fact?.key ?? 'guide' : null);
  const units = useUnits();
  return <aside ref={panel} className={`trace-panel ${open ? 'trace-panel--open' : ''}`} aria-label={w('trace.panel.label')}>
    <div className="trace-head">
      <span className="section-kicker">{w('trace.panel.kicker')}</span>
      <button type="button" className="trace-toggle" aria-expanded={open} onClick={onToggle}>
        {open ? w('trace.panel.hide') : w('trace.panel.show')}
      </button>
    </div>
    {open && (fact
      ? <div className="trace-body" data-motion={motion}>
        <h2>{fact.label}</h2>
        <dl>
          <dt>{w('trace.panel.value')}</dt>
          <dd>{fact.dimension && typeof fact.value === 'number'
            ? units.text(fact.value, fact.dimension, fact.storedUnit)
            : readValue(fact.value, w)}</dd>
          <dt>{w('trace.panel.source')}</dt>
          <dd>{fact.source?.trim() ? fact.source : w('trace.panel.sourceMissing')}</dd>
          <dt>{w('trace.panel.estimate')}</dt>
          <dd>{estimateLabel(fact.estimate, w)}</dd>
          {fact.path && <><dt>{w('trace.panel.location')}</dt><dd><code>{fact.path}</code></dd></>}
        </dl>
        <p className="trace-note">{w('trace.panel.note')}</p>
        <button type="button" className="text-button" onClick={clear}>{w('trace.panel.clear')}</button>
      </div>
      : <div className="trace-body trace-body--guide" data-motion={motion}>
        <h2>{w('trace.panel.guideTitle')}</h2>
        <p>{w('trace.panel.guide')}</p>
      </div>)}
  </aside>;
}

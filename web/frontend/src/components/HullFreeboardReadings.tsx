import { useId, useMemo, useState } from 'react';

import { useHullFreeboardCopy, type HullFreeboardKey } from '../i18n/hullFreeboard';
import { useLanguage } from '../portfolio/LanguageProvider';
import { armourDiagramFileName, downloadArmourDiagramPng, downloadArmourDiagramSvg } from './armourDiagramExport';
import { freeboardProfileSvg } from './freeboardProfileSvg';
import {
  readHullFreeboard, type FreeboardEndpoint, type FreeboardEndpointKey, type HullFreeboard,
} from './hullFreeboardModel';
import { useUnits } from './UnitProvider';
import { formatNumber } from './units';
import '../styles/hullFreeboard.css';

/**
 * The hull and freeboard readers.
 *
 * Both read one pure projection of the saved native result. The hull chapter
 * prints the linked dimensions, the design's own drivers, its depth-lock
 * declaration and the unified ledger balance; the freeboard chapter draws the
 * declared endpoint outline, lists all eight endpoints separately, and reveals
 * a real source field on an explicit edit request.
 *
 * A pending or failed reading withholds every fact and names the reason. The
 * frozen report passes no edit callback and asks for the static image shape, so
 * it renders read-only with no control that does nothing. Selection is local
 * state only: it never writes the design, and the serialized SVG is independent
 * of it, so a focused endpoint survives the selection re-render.
 */

export type HullFreeboardState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface HullReadingsProps {
  result: unknown;
  baseline?: unknown;
  state?: HullFreeboardState;
  contextLabel?: string | null;
  runId?: string | null;
  onEditField?: (field: string) => void;
  className?: string;
}

export type NativeFreeboardProfileProps = HullReadingsProps;

function problemKey(problem: HullFreeboard['problem']): HullFreeboardKey {
  switch (problem) {
    case 'unsupported_schema': return 'hull.state.schema';
    case 'unsupported_method': return 'hull.state.method';
    case 'absent': return 'hull.state.absent';
    default: return 'hull.state.unavailable';
  }
}

function freeboardProblemKey(problem: HullFreeboard['problem']): HullFreeboardKey {
  switch (problem) {
    case 'unsupported_schema': return 'freeboard.state.schema';
    case 'unsupported_method': return 'freeboard.state.method';
    case 'absent': return 'freeboard.state.absent';
    default: return 'freeboard.state.unavailable';
  }
}

function factText(value: number | null, unit: 'length' | 'lt' | 'ratio', units: ReturnType<typeof useUnits>, unknown: string): string {
  if (value === null) return unknown;
  if (unit === 'length') return units.text(value, 'length', 'ft');
  if (unit === 'lt') return `${formatNumber(value)} LT`;
  return formatNumber(value);
}

/** One linked hull fact, with its reveal button only when a real field exists. */
function HullFactRow({ fact, state, unknown, onEditField }: {
  fact: HullFreeboard['hull']['facts'][number]; state: HullFreeboardState; unknown: string;
  onEditField?: (field: string) => void;
}) {
  const p = useHullFreeboardCopy();
  const units = useUnits();
  const canEdit = state === 'ready' && Boolean(onEditField) && Boolean(fact.editField);
  return <div className={`hull-fact${fact.changed ? ' hull-fact--changed' : ''}`}
    data-hull-fact={fact.key} data-changed={fact.changed ? 'true' : undefined}>
    <dt>{p(fact.label)}{fact.changed ? <small> · {p('hull.changed')}</small> : null}</dt>
    <dd>{factText(fact.value, fact.unit, units, unknown)}
      {canEdit ? <button type="button" className="text-button hull-reveal" data-hull-reveal={fact.editField}
        onClick={() => onEditField?.(fact.editField!)}>{p('hull.reveal')}</button> : null}
    </dd>
  </div>;
}

export function HullReadings({
  result, baseline, state = 'ready', contextLabel, runId, onEditField, className,
}: HullReadingsProps) {
  const p = useHullFreeboardCopy();
  const units = useUnits();
  const reading = useMemo(() => readHullFreeboard(result, baseline), [result, baseline]);
  const sectionClass = `hull-readings ${className ?? ''}`.trim();

  if (state === 'pending' || state === 'failed') {
    const key: HullFreeboardKey = state === 'pending' ? 'hull.state.pending' : 'hull.state.failed';
    return <section className={sectionClass} data-hull-readings data-state={state} aria-label={p('hull.title')}>
      <p className="hull-state" role="status">{p(key)}</p>
    </section>;
  }
  if (!reading.supported) {
    return <section className={sectionClass} data-hull-readings data-state="unavailable" aria-label={p('hull.title')}>
      <p className="hull-state" role="status">{p(problemKey(reading.problem))}</p>
    </section>;
  }

  const unknown = p('hull.unknown');
  const driver = reading.hull.drivers;
  const lengthText = driver.lengthDriver === 'waterline' ? p('hull.driver.waterline')
    : driver.lengthDriver === 'overall' ? p('hull.driver.overall') : unknown;
  const displacementText = driver.displacementDriver === 'block' ? p('hull.driver.block')
    : driver.displacementDriver === 'displacement' ? p('hull.driver.displacementChoice') : unknown;
  const depthText = driver.depthLocked === null ? p('hull.depth.undeclared')
    : driver.depthLocked ? p('hull.depth.locked') : p('hull.depth.unlocked');
  const massText = (value: number | null): string => value === null ? unknown : units.text(value, 'mass', 't');

  return <section className={sectionClass} data-hull-readings data-state={state} aria-label={p('hull.title')}>
    <header className="hull-head">
      <p className="hull-kicker">{p('hull.kicker')}</p>
      <h3>{p('hull.title')}</h3>
      <p className="hull-intro">{state === 'frozen' ? p('hull.state.frozen') : p('hull.intro')}</p>
      {contextLabel ? <p className="hull-hint" data-hull-context>{contextLabel}</p> : null}
      {runId ? <p className="hull-hint" data-hull-run>{runId}</p> : null}
    </header>

    <article className="hull-block">
      <h4>{p('hull.facts.title')}</h4>
      <dl className="hull-facts" data-hull-facts>
        {reading.hull.facts.map(fact => <HullFactRow key={fact.key} fact={fact} state={state}
          unknown={unknown} onEditField={onEditField} />)}
      </dl>
      <p className="hull-hint">{p('hull.fact.units')}</p>
    </article>

    <article className="hull-block">
      <h4>{p('hull.driver.title')}</h4>
      <dl className="hull-facts">
        <div className="hull-fact" data-hull-driver="length"><dt>{p('hull.driver.length')}</dt><dd>{lengthText}</dd></div>
        <div className="hull-fact" data-hull-driver="displacement"><dt>{p('hull.driver.displacement')}</dt><dd>{displacementText}</dd></div>
        <div className="hull-fact" data-hull-driver="depth"><dt>{p('hull.driver.depth')}</dt><dd>{depthText}</dd></div>
        <div className="hull-fact" data-hull-driver-target="overall"><dt>{p('hull.driver.targetOverall')}</dt>
          <dd>{driver.overallTarget === null ? unknown : formatNumber(driver.overallTarget)}</dd></div>
        <div className="hull-fact" data-hull-driver-target="displacement"><dt>{p('hull.driver.targetDisplacement')}</dt>
          <dd>{driver.displacementTargetLt === null ? unknown : `${formatNumber(driver.displacementTargetLt)} LT`}</dd></div>
      </dl>
      <p className="hull-hint">{p('hull.driver.targetNote')}</p>
    </article>

    <article className="hull-block">
      <h4>{p('hull.balance.title')}</h4>
      <dl className="hull-facts">
        <div className="hull-fact" data-hull-balance-row="selected"><dt>{p('hull.balance.selected')}</dt><dd>{massText(reading.balance.selectedT)}</dd></div>
        <div className="hull-fact" data-hull-balance-row="estimate"><dt>{p('hull.balance.estimate')}</dt><dd>{massText(reading.balance.estimateT)}</dd></div>
        <div className="hull-fact" data-hull-balance-row="target"><dt>{p('hull.balance.target')}</dt><dd>{massText(reading.balance.targetT)}</dd></div>
        <div className="hull-fact" data-hull-balance-row="difference"><dt>{p('hull.balance.difference')}</dt><dd>{massText(reading.balance.differenceT)}</dd></div>
      </dl>
      <p className="hull-hint">{p('hull.balance.note')}</p>
    </article>
  </section>;
}

function endpointFrom(target: EventTarget | null): FreeboardEndpointKey | null {
  if (!(target instanceof Element)) return null;
  const node = target.closest('[data-freeboard-point]');
  const key = node?.getAttribute('data-freeboard-point');
  return key && /^free(QD|AD|FD|FC)(Aft|For)$/.test(key) ? key as FreeboardEndpointKey : null;
}

function EndpointPanel({ endpoint, state, unknown, onEditField }: {
  endpoint: FreeboardEndpoint; state: HullFreeboardState; unknown: string;
  onEditField?: (field: string) => void;
}) {
  const p = useHullFreeboardCopy();
  const units = useUnits();
  const canEdit = state === 'ready' && Boolean(onEditField) && !endpoint.pinned;
  return <div className="freeboard-panel" data-freeboard-panel={endpoint.key}>
    <h4>{p('freeboard.panel.title')} · {p(endpoint.label)}</h4>
    <dl className="freeboard-panel-facts">
      <div><dt>{p('freeboard.panel.height')}</dt>
        <dd>{endpoint.value === null ? unknown : units.text(endpoint.value, 'length', 'ft')}</dd></div>
    </dl>
    {endpoint.pinned ? <p className="freeboard-pinned">{p('freeboard.pinned')}</p> : null}
    {canEdit ? <button type="button" className="sps-button" data-freeboard-edit={endpoint.editField}
      onClick={() => onEditField?.(endpoint.editField)}>{p('freeboard.select.edit')}</button> : null}
    {canEdit ? <p className="freeboard-hint">{p('freeboard.select.editHint')}</p> : null}
  </div>;
}

export function NativeFreeboardProfile({
  result, baseline, state = 'ready', contextLabel, runId, onEditField, className,
}: NativeFreeboardProfileProps) {
  const p = useHullFreeboardCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const [selected, setSelected] = useState<FreeboardEndpointKey | null>(null);
  const [exportError, setExportError] = useState('');
  const uid = `freeboard-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const reading = useMemo(() => readHullFreeboard(result, baseline), [result, baseline]);
  const interactive = state === 'ready';
  // Selection is deliberately not an input: the markup stays identical while a
  // reader selects, so the focused SVG endpoint is never replaced.
  const svg = useMemo(() => reading.supported
    ? freeboardProfileSvg(reading, {
      language, prefs: units.prefs, uid, interactive, contextLabel, runId,
    })
    : '', [reading, language, units.prefs, uid, interactive, contextLabel, runId]);
  const sectionClass = `freeboard-profile ${className ?? ''}`.trim();

  if (state === 'pending' || state === 'failed') {
    const key: HullFreeboardKey = state === 'pending' ? 'freeboard.state.pending' : 'freeboard.state.failed';
    return <section className={sectionClass} data-freeboard-profile data-state={state} aria-label={p('freeboard.title')}>
      <p className="freeboard-state" role="status">{p(key)}</p>
    </section>;
  }
  if (!reading.supported) {
    return <section className={sectionClass} data-freeboard-profile data-state="unavailable" aria-label={p('freeboard.title')}>
      <p className="freeboard-state" role="status">{p(freeboardProblemKey(reading.problem))}</p>
    </section>;
  }

  const unknown = p('freeboard.unknown');
  const onActivate = (target: EventTarget | null): void => {
    const key = endpointFrom(target);
    if (key) setSelected(key);
  };
  const download = (format: 'svg' | 'png'): void => {
    setExportError('');
    const filename = armourDiagramFileName(contextLabel ?? p('freeboard.export.file'), format);
    if (format === 'svg') {
      try { downloadArmourDiagramSvg(svg, filename); }
      catch { setExportError(p('freeboard.export.svgError')); }
      return;
    }
    void downloadArmourDiagramPng(svg, filename).catch(() => setExportError(p('freeboard.export.pngError')));
  };
  const endpoint = selected ? reading.freeboard.endpoints.find(item => item.key === selected) ?? null : null;

  return <section className={sectionClass} data-freeboard-profile data-state={state}
    data-selected-endpoint={selected ?? undefined} aria-label={p('freeboard.title')}>
    <header className="freeboard-head">
      <p className="freeboard-kicker">{p('freeboard.kicker')}</p>
      <h3>{p('freeboard.title')}</h3>
      <p className="freeboard-intro">{state === 'frozen' ? p('freeboard.state.frozen') : p('freeboard.intro')}</p>
      {contextLabel ? <p className="freeboard-hint" data-freeboard-context>{contextLabel}</p> : null}
      {runId ? <p className="freeboard-hint" data-freeboard-run>{runId}</p> : null}
    </header>

    <div className="freeboard-canvas"
      onClick={interactive ? event => onActivate(event.target) : undefined}
      onKeyDown={interactive ? event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const key = endpointFrom(event.target);
        if (key) { event.preventDefault(); setSelected(key); }
      } : undefined}
      // This is this repository's own serializer output: fixed tags and escaped text.
      dangerouslySetInnerHTML={{ __html: svg }} />

    {reading.hull.drivers.depthLocked === true ? <p className="freeboard-lock" data-freeboard-lock>{p('freeboard.lock')}</p> : null}

    <div className="freeboard-list" role={interactive ? 'group' : undefined} aria-label={p('freeboard.select.list')}>
      <h4>{p('freeboard.endpoints.title')}</h4>
      {reading.freeboard.endpoints.map(item => {
        const label = `${p(item.label)}${item.changed ? ` · ${p('freeboard.changed')}` : ''}`;
        const value = item.value === null ? unknown : units.text(item.value, 'length', 'ft');
        return <div className={`freeboard-endpoint${item.changed ? ' freeboard-endpoint--changed' : ''}`}
          data-freeboard-endpoint={item.key} data-changed={item.changed ? 'true' : undefined} key={item.key}>
          {interactive ? <button type="button" className="freeboard-select" data-freeboard-select={item.key}
            aria-pressed={selected === item.key} onClick={() => setSelected(item.key)}>
            <span>{label}</span><span>{value}</span>
          </button> : <><span>{label}</span><span>{value}</span></>}
        </div>;
      })}
      {interactive ? <p className="freeboard-hint">{p('freeboard.select.hint')}</p> : null}
    </div>

    {interactive && endpoint ? <EndpointPanel endpoint={endpoint} state={state} unknown={unknown}
      onEditField={onEditField} /> : null}

    <div className="freeboard-actions">
      <button type="button" className="sps-button" data-freeboard-download="svg"
        onClick={() => download('svg')}>{p('freeboard.export.svg')}</button>
      <button type="button" className="sps-button" data-freeboard-download="png"
        onClick={() => download('png')}>{p('freeboard.export.png')}</button>
      {exportError ? <p className="freeboard-error" role="alert">{exportError}</p> : null}
    </div>
  </section>;
}

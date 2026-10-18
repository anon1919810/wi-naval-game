import { useId, useMemo, useState } from 'react';

import { useArmourDiagramCopy, bulkheadTypeLabel, deckCoverageLabel, policyLabel, type ArmourDiagramKey } from '../i18n/armourDiagram';
import { useLanguage } from '../portfolio/LanguageProvider';
import { useUnits } from './UnitProvider';
import { formatNumber } from './units';
import {
  ARMOUR_REGION_ORDER, buildArmourDiagram,
  type ArmourBand, type ArmourDiagram, type ArmourRegionRole,
} from './armourDiagramModel';
import { armourDiagramFileName, armourDiagramSvg, downloadArmourDiagramPng, downloadArmourDiagramSvg } from './armourDiagramExport';
import '../styles/armourDiagram.css';

/**
 * The interactive armour diagram.
 *
 * It renders one serialized SVG — the same string the downloads write — and adds
 * only the reading furniture around it: a region list that is a real control for
 * every region, a metadata panel that reveals the selected region's dimensions
 * and masses, an explicit Edit that hands the region's source field back to the
 * host, and the SVG/PNG downloads. The diagram itself withholds every number and
 * both export buttons while a reading is pending or has failed, and states why a
 * result that is absent or of another shape cannot be drawn.
 *
 * The serialized SVG's regions are focusable buttons, so the diagram is not an
 * image with hidden controls; the frozen report renders the same markup as a
 * static image instead, because there is nothing to select there.
 */

export type ArmourDiagramState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface ArmourDiagramProps {
  /** The native result or the raw saved stage data; gated inside. */
  result: unknown;
  /** A compatible saved revision to compare against, or null. */
  baseline?: unknown;
  state?: ArmourDiagramState;
  /** The run, revision or condition the drawn mass belongs to. */
  contextLabel?: string | null;
  runId?: string | null;
  /** Hand a source field name back so the host can open and focus it. */
  onEditField?: (field: string) => void;
  className?: string;
}

function problemCopyKey(problem: ArmourDiagram['problem']): ArmourDiagramKey {
  switch (problem) {
    case 'unsupported_schema': return 'armour.state.schema';
    case 'unsupported_method': return 'armour.state.method';
    case 'absent': return 'armour.state.absent';
    default: return 'armour.state.unavailable';
  }
}

function regionFrom(target: EventTarget | null): ArmourRegionRole | null {
  if (!(target instanceof Element)) return null;
  const node = target.closest('[data-armour-region]');
  const role = node?.getAttribute('data-armour-region');
  return role && (ARMOUR_REGION_ORDER as readonly string[]).includes(role) ? role as ArmourRegionRole : null;
}

function regionKey(role: ArmourRegionRole): ArmourDiagramKey {
  return `armour.region.${role}` as ArmourDiagramKey;
}

export function ArmourDiagram({
  result, baseline, state = 'ready', contextLabel, runId, onEditField, className,
}: ArmourDiagramProps) {
  const w = useArmourDiagramCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const [selected, setSelected] = useState<ArmourRegionRole | null>(null);
  const [exportError, setExportError] = useState('');
  // A per-instance id, so two diagrams never share a `defs` id in one document.
  const uid = `armour-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`;
  const diagram = useMemo(() => buildArmourDiagram(result, baseline ?? undefined), [result, baseline]);

  const drawable = state === 'ready' || state === 'frozen';
  const interactive = state === 'ready';
  const sectionClass = `armour-diagram ${className ?? ''}`.trim();

  // Pending and failed readings withhold the drawing and its numbers entirely.
  if (!drawable) {
    const key: ArmourDiagramKey = state === 'pending' ? 'armour.state.pending' : 'armour.state.failed';
    return <section className={sectionClass} data-armour-diagram data-state={state} aria-label={w('armour.title')}>
      <p className="armour-diagram-state" role="status">{w(key)}</p>
    </section>;
  }
  if (!diagram.supported) {
    return <section className={sectionClass} data-armour-diagram data-state="unavailable" aria-label={w('armour.title')}>
      <p className="armour-diagram-state" role="status">{w(problemCopyKey(diagram.problem))}</p>
    </section>;
  }

  const svg = armourDiagramSvg(diagram, {
    // Keep markup stable when selecting so the focused SVG node survives.
    language, prefs: units.prefs, uid, interactive, selected: null, contextLabel, runId,
  });

  const onActivate = (target: EventTarget | null): void => {
    const role = regionFrom(target);
    if (role) setSelected(role);
  };
  const download = (format: 'svg' | 'png'): void => {
    setExportError('');
    const filename = armourDiagramFileName(contextLabel ?? diagram.context.sourceName ?? 'armour-diagram', format);
    if (format === 'svg') {
      try { downloadArmourDiagramSvg(svg, filename); }
      catch { setExportError(w('armour.export.svgError')); }
      return;
    }
    downloadArmourDiagramPng(svg, filename).catch(() => setExportError(w('armour.export.pngError')));
  };
  const roles: ArmourRegionRole[] = [...diagram.bands.map(band => band.role), 'deck', 'conning'];

  return <section className={sectionClass} data-armour-diagram data-state={state}
    data-selected-region={selected ?? undefined} aria-label={w('armour.title')}>
    {state === 'frozen' ? <p className="armour-diagram-state">{w('armour.state.frozen')}</p> : null}
    <div className="armour-diagram-canvas"
      onClick={interactive ? event => onActivate(event.target) : undefined}
      onKeyDown={interactive ? event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const role = regionFrom(event.target);
        if (role) { event.preventDefault(); setSelected(role); }
      } : undefined}
      // The markup is this repository's own serializer's output: fixed tags, escaped text.
      dangerouslySetInnerHTML={{ __html: svg }} />
    {interactive ? <div className="armour-diagram-regions" role="group" aria-label={w('armour.select.list')}>
      {roles.map(role => {
        const changed = diagram.comparable && diagram.changed[role] === true;
        return <button type="button" key={role} className="armour-diagram-region" data-armour-select={role}
          aria-pressed={selected === role} onClick={() => setSelected(role)}>
          {w(regionKey(role))}{changed ? ` · ${w('armour.changed')}` : ''}
        </button>;
      })}
      <p className="armour-diagram-hint">{w('armour.select.hint')}</p>
    </div> : null}
    {selected ? <RegionPanel diagram={diagram} role={selected} onEditField={onEditField} frozen={state === 'frozen'} /> : null}
    <div className="armour-diagram-actions">
      <button type="button" className="sps-button" onClick={() => download('svg')}>{w('armour.export.svg')}</button>
      <button type="button" className="sps-button" onClick={() => download('png')}>{w('armour.export.png')}</button>
      {exportError ? <p className="armour-diagram-error" role="alert">{exportError}</p> : null}
    </div>
  </section>;
}

function RegionPanel({ diagram, role, onEditField, frozen }: {
  diagram: ArmourDiagram; role: ArmourRegionRole;
  onEditField?: (field: string) => void; frozen: boolean;
}) {
  const w = useArmourDiagramCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const rows: Array<[string, string]> = [];
  const unknown = w('armour.fact.unknown');
  const length = (value: number | null): string => value === null ? unknown : units.text(value, 'length', 'ft');
  const thickness = (value: number | null): string => value === null
    ? unknown : `${formatNumber(value)} in (${formatNumber(value * 25.4)} mm)`;
  const mass = (value: number | null): string => value === null ? unknown : units.text(value, 'mass', 't');
  const angle = (value: number | null): string => value === null ? unknown : units.text(value, 'angle', 'deg');
  let editField: string | null = null;
  if (role === 'deck' && diagram.deck) {
    editField = diagram.deck.editField;
    rows.push([w('armour.deck.thickness'), thickness(diagram.deck.thicknessIn)]);
    rows.push([w('armour.deck.forecastle'), thickness(diagram.deck.forecastleThicknessIn)]);
    rows.push([w('armour.deck.quarterdeck'), thickness(diagram.deck.quarterdeckThicknessIn)]);
    rows.push([w('armour.deck.coverage'), deckCoverageLabel(language, diagram.deck.coverageIndex) ?? unknown]);
  } else if (role === 'conning') {
    editField = diagram.towers[0]?.editField ?? null;
    rows.push([w('armour.tower.forward'), thickness(diagram.towers[0]?.thicknessIn ?? null)]);
    rows.push([w('armour.tower.aft'), thickness(diagram.towers[1]?.thicknessIn ?? null)]);
  } else {
    const band: ArmourBand | undefined = diagram.bands.find(item => item.role === role);
    if (band) {
      editField = band.editField;
      rows.push([w('armour.fact.length'), length(band.lengthFt)]);
      rows.push([w('armour.fact.height'), length(band.heightFt)]);
      rows.push([w('armour.fact.thickness'), thickness(band.thicknessIn)]);
      if (band.role === 'belt_main') rows.push([w('armour.fact.inclination'), angle(band.inclinationDeg)]);
      if (band.role === 'bulkhead') {
        rows.push([w('armour.bulkhead.beam'), length(band.beamFt)]);
        rows.push([w('armour.bulkhead.type'), bulkheadTypeLabel(language, diagram.context.bulkheadTypeIndex) ?? unknown]);
      }
    }
  }
  const ledger = diagram.ledger[role];
  if (ledger) {
    rows.push([w('armour.fact.mode'), policyLabel(language, ledger.mode)]);
    rows.push([w('armour.fact.selected'), mass(ledger.selectedT)]);
    rows.push([w('armour.fact.estimate'), mass(ledger.estimateT)]);
  }
  const canEdit = !frozen && Boolean(onEditField) && editField !== null;
  return <div className="armour-diagram-panel" data-armour-panel={role}>
    <h4>{w(regionKey(role))}</h4>
    <dl className="armour-diagram-facts">
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>
    {canEdit ? <button type="button" className="sps-button" onClick={() => onEditField?.(editField as string)}>
      {w('armour.select.edit')}
    </button> : null}
    {canEdit ? <p className="armour-diagram-hint">{w('armour.select.editHint')}</p> : null}
  </div>;
}

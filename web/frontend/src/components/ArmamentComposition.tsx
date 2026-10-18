import { useId, useState } from 'react';

import { useLanguage } from '../portfolio/LanguageProvider';
import { useUnits } from './UnitProvider';
import { ledgerPolicyLabel, useVesselOverviewCopy, vesselLabel, type VesselLabelTable, type VesselOverviewKey } from '../i18n/vesselOverview';
import { formatNumber } from './units';
import {
  ARMAMENT_BANK_ORDER, ARMAMENT_LEDGER_ROLES, buildArmament,
  type Armament, type ArmamentBank, type ArmamentLedgerRole,
} from './armamentModel';
import { armamentFileName, armamentSvg, downloadArmamentPng, downloadArmamentSvg } from './armamentExport';
import '../styles/vesselOverview.css';

/**
 * The interactive armament composition.
 *
 * It renders one serialized SVG — the same string the downloads write — and adds
 * only the reading furniture around it: a battery list that is a real control for
 * every bank, a panel that reveals the selected battery's configuration and its
 * source estimates beside the global ledger roles, an explicit Edit that hands
 * the battery's calibre field back to the host, and the SVG/PNG downloads. The
 * composition withholds every number and both export buttons while a reading is
 * pending or has failed, and states why a result that is absent or of another
 * shape cannot be drawn.
 *
 * The serialized SVG's batteries are focusable buttons that select on Enter or
 * Space; because the markup never depends on the selection, the focused node
 * survives the selection. The frozen report renders the same markup read-only.
 */

export type ArmamentState = 'ready' | 'pending' | 'failed' | 'frozen';

export interface ArmamentCompositionProps {
  /** The native result or the raw saved stage data; gated inside. */
  result: unknown;
  /** A compatible saved revision to compare against, or null. */
  baseline?: unknown;
  state?: ArmamentState;
  contextLabel?: string | null;
  runId?: string | null;
  /** Hand `gunN_calibre` back so the host can open and focus it. */
  onEditField?: (field: string) => void;
  className?: string;
}

function problemKey(problem: Armament['problem']): VesselOverviewKey {
  switch (problem) {
    case 'unsupported_schema': return 'armament.state.schema';
    case 'unsupported_method': return 'armament.state.method';
    case 'absent': return 'armament.state.absent';
    default: return 'armament.state.unavailable';
  }
}

function bankFrom(target: EventTarget | null): number | null {
  if (!(target instanceof Element)) return null;
  const node = target.closest('[data-armament-bank]');
  const bank = node?.getAttribute('data-armament-bank');
  return bank && ARMAMENT_BANK_ORDER.includes(Number(bank)) ? Number(bank) : null;
}

export function ArmamentComposition({
  result, baseline, state = 'ready', contextLabel, runId, onEditField, className,
}: ArmamentCompositionProps) {
  const w = useVesselOverviewCopy();
  const { language } = useLanguage();
  const units = useUnits();
  // One stable id per mounted composition: two compositions on one page never
  // share a `defs` id, and the id survives every re-render of this instance.
  const uid = useId().replace(/[^a-zA-Z0-9_-]/g, '');
  const [selected, setSelected] = useState<number | null>(null);
  const [exportError, setExportError] = useState('');
  const armament = buildArmament(result, baseline ?? undefined);

  const drawable = state === 'ready' || state === 'frozen';
  const interactive = state === 'ready';
  const sectionClass = `armament-composition ${className ?? ''}`.trim();

  // Pending and failed readings withhold the drawing and its numbers entirely.
  if (!drawable) {
    const key: VesselOverviewKey = state === 'pending' ? 'armament.state.pending' : 'armament.state.failed';
    return <section className={sectionClass} data-armament-composition data-state={state} aria-label={w('armament.title')}>
      <p className="vessel-state" role="status">{w(key)}</p>
    </section>;
  }
  if (!armament.supported) {
    return <section className={sectionClass} data-armament-composition data-state="unavailable" aria-label={w('armament.title')}>
      <p className="vessel-state" role="status">{w(problemKey(armament.problem))}</p>
    </section>;
  }

  // The markup never depends on the selection, so the focused SVG node survives.
  const svg = armamentSvg(armament, {
    language, prefs: units.prefs, uid, interactive,
    contextLabel, runId,
  });
  const selectedBank: ArmamentBank | null = selected === null ? null : armament.banks.find(bank => bank.bank === selected) ?? null;

  const download = (format: 'svg' | 'png'): void => {
    setExportError('');
    const filename = armamentFileName(contextLabel ?? 'armament', format);
    if (format === 'svg') {
      try { downloadArmamentSvg(svg, filename); }
      catch { setExportError(w('armament.export.svgError')); }
      return;
    }
    downloadArmamentPng(svg, filename).catch(() => setExportError(w('armament.export.pngError')));
  };

  return <section className={sectionClass} data-armament-composition data-state={state}
    data-selected-bank={selected ?? undefined} aria-label={w('armament.title')}>
    {state === 'frozen' ? <p className="vessel-state">{w('armament.state.frozen')}</p> : null}
    <div className="armament-canvas"
      onClick={interactive ? event => { const bank = bankFrom(event.target); if (bank !== null) setSelected(bank); } : undefined}
      onKeyDown={interactive ? event => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        const bank = bankFrom(event.target);
        if (bank !== null) { event.preventDefault(); setSelected(bank); }
      } : undefined}
      // The markup is this repository's own serializer's output: fixed tags, escaped text.
      dangerouslySetInnerHTML={{ __html: svg }} />
    {interactive ? <div className="armament-banks" role="group" aria-label={w('armament.banks.list')}>
      {ARMAMENT_BANK_ORDER.map(bank => {
        const reading = armament.banks.find(item => item.bank === bank);
        return <button type="button" key={bank} className="armament-bank-button" data-armament-select={bank}
          aria-pressed={selected === bank} onClick={() => setSelected(bank)}>
          {w('armament.bank.label', { bank })}{reading?.changed ? ` · ${w('armament.changed')}` : ''}
        </button>;
      })}
      <p className="vessel-hint">{w('armament.select.hint')}</p>
    </div> : null}
    {selectedBank ? <BankPanel bank={selectedBank} armament={armament} onEditField={onEditField} frozen={state === 'frozen'} /> : null}
    <div className="armament-actions">
      <button type="button" className="sps-button" onClick={() => download('svg')}>{w('armament.export.svg')}</button>
      <button type="button" className="sps-button" onClick={() => download('png')}>{w('armament.export.png')}</button>
      {exportError ? <p className="vessel-error" role="alert">{exportError}</p> : null}
    </div>
  </section>;
}

/** One selected battery, its two groups and the global ledger rows. */
function BankPanel({ bank, armament, onEditField, frozen }: {
  bank: ArmamentBank; armament: Armament; onEditField?: (field: string) => void; frozen: boolean;
}) {
  const w = useVesselOverviewCopy();
  const { language } = useLanguage();
  const units = useUnits();
  const unknown = w('vessel.unknown');
  const count = (value: number | null): string => value === null ? unknown
    : Number.isInteger(value) && value >= 0 ? formatNumber(value) : w('armament.count.invalid', { value: formatNumber(value) });
  const thickness = (value: number | null): string => value === null ? unknown : `${formatNumber(value)} in (${formatNumber(value * 25.4)} mm)`;
  const pounds = (value: number | null): string => value === null ? unknown : `${formatNumber(value)} lb`;
  const sourceMass = (value: number | null): string => value === null ? unknown : units.text(value, 'mass', 'long_ton');
  const ledgerMass = (value: number | null): string => value === null ? unknown : units.text(value, 'mass', 't');
  const enumLabel = (table: VesselLabelTable, index: number | null): string => vesselLabel(language, table, index) ?? unknown;

  const state = bank.state === 'missing' ? w('armament.bank.missing')
    : bank.state === 'ambiguous' ? w('armament.bank.ambiguous')
      : bank.state === 'zero' ? w('armament.bank.zero') : null;

  // An undeclared flag is never printed as an explicit false; only a declared
  // one is named, and it is named as a declaration rather than a plotted value.
  const declaredFlags: string[] = [];
  if (bank.superSuper === true) declaredFlags.push(w('armament.fact.flagElevation'));
  if (bank.subSub === true) declaredFlags.push(w('armament.fact.flagDepression'));

  const rows: Array<[string, string]> = [];
  if (bank.state === 'declared' || bank.state === 'zero') {
    rows.push([w('armament.fact.barrels'), count(bank.barrels)]);
    rows.push([w('armament.fact.mounts'), count(bank.mounts)]);
    rows.push([w('armament.fact.calibre'), thickness(bank.calibreIn)]);
    rows.push([w('armament.fact.gunType'), enumLabel('gunType', bank.gunType)]);
    rows.push([w('armament.fact.mountType'), enumLabel('mountType', bank.mountType)]);
    rows.push([w('armament.fact.year'), count(bank.year)]);
    rows.push([w('armament.fact.calLength'), bank.calLength === null ? unknown : w('armament.fact.calibreLength', { value: formatNumber(bank.calLength) })]);
    rows.push([w('armament.fact.magazine'), count(bank.magazine)]);
    rows.push([w('armament.fact.face'), thickness(bank.armFaceIn)]);
    rows.push([w('armament.fact.side'), thickness(bank.armBackIn)]);
    rows.push([w('armament.fact.barbette'), thickness(bank.armBottomIn)]);
    rows.push([w('armament.fact.shellDeclared'), pounds(bank.shellWeightDeclaredLb)]);
    rows.push([w('armament.fact.shellEffective'), pounds(bank.shellWeightLb)]);
    rows.push([w('armament.fact.shellRecovered'), pounds(bank.autoShellWeightLb)]);
    rows.push([w('armament.fact.broadside'), pounds(bank.broadsideWeightLb)]);
    rows.push([w('armament.fact.gunWeight'), sourceMass(bank.gunWeightLt)]);
    rows.push([w('armament.fact.mountWeight'), sourceMass(bank.mountWeightLt)]);
    rows.push([w('armament.fact.magazineWeight'), sourceMass(bank.magazineWeightLt)]);
    rows.push([w('armament.fact.armWeight'), sourceMass(bank.armWeightLt)]);
    rows.push([w('armament.fact.totalWeight'), sourceMass(bank.totalWeightLt)]);
  }
  const canEdit = !frozen && Boolean(onEditField);
  return <div className="armament-panel" data-armament-panel={bank.bank}>
    <h4>{w('armament.bank.label', { bank: bank.bank })}</h4>
    {state ? <p className="vessel-hint" role="status">{state}</p> : null}
    <dl className="armament-facts">
      {rows.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
    </dl>
    {declaredFlags.length ? <p className="vessel-hint">{declaredFlags.join(' · ')}</p> : null}
    {bank.state === 'declared' || bank.state === 'zero' ? bank.groups.map(group => <div className="armament-group" key={group.key}>
      <h5>{w(`armament.group.${group.key}` as VesselOverviewKey)}</h5>
      <dl className="armament-facts">
        <div><dt>{w('armament.fact.groupMounts')}</dt><dd>{count(group.mounts)}</dd></div>
        <div><dt>{w('armament.fact.selector')}</dt><dd>{enumLabel('selector', group.selector)}</dd></div>
        <div><dt>{w('armament.fact.layout')}</dt><dd>{enumLabel('layout', group.layout)}</dd></div>
        <div><dt>{w('armament.fact.perMount')}</dt><dd>{count(group.perMount)}</dd></div>
        <div><dt>{w('armament.fact.elevated')}</dt><dd>{count(group.elevated)}</dd></div>
        <div><dt>{w('armament.fact.deck')}</dt><dd>{count(group.deck)}</dd></div>
        <div><dt>{w('armament.fact.depressed')}</dt><dd>{count(group.depressed)}</dd></div>
      </dl>
    </div>) : null}
    <div className="armament-ledger" data-armament-ledger>
      <h5>{w('armament.ledger.title')}</h5>
      <p className="vessel-hint">{w('armament.ledger.note')}</p>
      <dl className="armament-facts">
        {ARMAMENT_LEDGER_ROLES.map(role => <div key={role}>
          <dt>{w(`armament.ledger.role.${role}` as VesselOverviewKey)}</dt>
          <dd>{w('armament.ledger.mass', {
            selected: ledgerMass(armament.ledger[role as ArmamentLedgerRole].selectedT),
            estimate: ledgerMass(armament.ledger[role as ArmamentLedgerRole].estimateT),
            policy: ledgerPolicyLabel(language, armament.ledger[role as ArmamentLedgerRole].mode),
          })}</dd>
        </div>)}
      </dl>
    </div>
    {canEdit ? <button type="button" className="sps-button" onClick={() => onEditField?.(bank.editField)}>
      {w('armament.select.edit')}
    </button> : null}
    {canEdit ? <p className="vessel-hint">{w('armament.select.editHint')}</p> : null}
  </div>;
}

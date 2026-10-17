import { type ReactNode } from 'react';

import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import { useUnits } from './UnitProvider';
import { number, object, rows, type Raw } from './formModel';
import { metric } from './conceptDesign';
import { ARMOUR_DEFAULT_LABELS, ARMOUR_DEFAULT_VALUE_KEYS } from './armourDefaults';
import type { StageEnvelope } from '../types';

/**
 * The concept screen's own component readings, in one shared projection.
 *
 * The fixed armour regions, the auxiliary weapons, the two-group layout readings
 * and the empirical cost reading are all returned by the same `design_balance`
 * payload, and the workbench and the saved full report both have to print them.
 * This module is that one projection: both surfaces call it, so a reading cannot
 * be presented one way in the workspace and another way on paper.
 *
 * It computes nothing. Every number is the server's own, with its own method,
 * source and status; long tons keep the recovered screen's own unit and the cost
 * keeps the source's own historical currency labels. A reading the declared
 * inputs cannot support is unknown with the server's reason beside it, never a
 * zero, and an optional feature nobody declared adds no section at all.
 *
 * The two surfaces differ only in *which gate* applies, and the gate is a
 * parameter rather than a second implementation:
 *
 * - `'independent'` is the workbench policy. Each component carries its own
 *   status, so a region, a layout, an auxiliary weapon or the cost is still
 *   readable when an unrelated part of the screen is incomplete — that is the
 *   contract's promise that these readings are exposed before the screen's early
 *   returns.
 * - `'report'` is the saved full-report policy, and it is the parent's gate, not
 *   a new one: only a requested envelope that actually completed may show plain
 *   numbers. An unavailable, failed or canceled stage keeps its diagnostics and
 *   its raw evidence and shows no residual figure here.
 */

export type ReadingsPolicy = 'independent' | 'report';

/**
 * Whether this policy may show the payload at all.
 *
 * The report gate is written once, here, so no caller can reach it by accident:
 * `requested === true` *and* `status === 'completed'`, never one of the two.
 */
export function readingsAllowed(policy: ReadingsPolicy, envelope?: StageEnvelope | null): boolean {
  if (policy === 'independent') return true;
  return envelope?.requested === true && envelope.status === 'completed';
}

/** The three component families of one `design_balance` payload. */
export interface ComponentReadings {
  fixedArmour: Raw[];
  layouts: Raw[];
  auxiliaryWeapons: Raw[];
  cost: Raw | null;
}

/**
 * The component readings of one payload, with nothing computed and nothing
 * defaulted. A feature nobody declared is absent rather than an empty list, so
 * "this project declares no fixed armour" stays distinguishable from "it declares
 * some and none of them read".
 */
export function componentReadings(data: Raw | null): ComponentReadings {
  const payload = data ?? {};
  const cost = payload.cost;
  return {
    fixedArmour: rows(payload.fixed_armour),
    layouts: rows(payload.battery_layouts),
    auxiliaryWeapons: rows(payload.auxiliary_weapons),
    cost: cost === null || cost === undefined ? null : (cost as Raw),
  };
}

/** One long-ton metric. Long tons are the recovered screen's own unit, not converted. */
function LongTons({ label, value }: { label: string; value: unknown }) {
  const c = useConceptCopy();
  const known = metric(value);
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{known === null ? c('proposals.unknownMass')
      : `${known.toFixed(3)} ${c('balance.unit.lt')}`}</span>
  </div>;
}

/** One metric in its own source unit: metric tonnes, or a dimensionless factor. */
function Plain({ label, value, unit = '' }: { label: string; value: unknown; unit?: string }) {
  const c = useConceptCopy();
  const known = metric(value);
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{known === null ? c('proposals.unknownMass')
      : `${known.toFixed(3)}${unit ? ` ${unit}` : ''}`}</span>
  </div>;
}

function Quantity({ label, text }: { label: string; text: string }) {
  return <div className="fact-field">
    <span className="fact-label">{label}</span><span className="fact-value">{text}</span>
  </div>;
}

/** One reading, printed verbatim as the server's own enum or text. */
function Text({ label, value }: { label: string; value: unknown }) {
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{value === null || value === undefined || value === '' ? '—' : String(value)}</span>
  </div>;
}

/** A count, printed as the whole number the server derived. */
function Count({ label, value }: { label: string; value: unknown }) {
  const c = useConceptCopy();
  const known = metric(value);
  return <div className="fact-field">
    <span className="fact-label">{label}</span>
    <span className="fact-value">{known === null ? c('proposals.unknownMass') : String(known)}</span>
  </div>;
}

function Group({ title, children, note }: { title: string; children: ReactNode; note?: string }) {
  return <section className="concept-balance-group">
    <h4>{title}</h4>
    <div className="metric-grid">{children}</div>
    {note && <p className="form-hint">{note}</p>}
  </section>;
}

function Diagnostics({ reasons, title }: { reasons: Raw[]; title: ConceptKey }) {
  const c = useConceptCopy();
  if (reasons.length === 0) return null;
  return <div>
    <h4>{c(title)}</h4>
    <ul className="diagnostics-list">{reasons.map((reason, index) =>
      <li key={index}>{String(reason.message ?? reason.code ?? '')}</li>)}</ul>
  </div>;
}

/** One layout's group reading, exactly as the layout kernel derived it. */
function LayoutGroupReading({ title, reading }: { title: string; reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  return <Group title={title}>
    <Text label={c('balance.layout.groupRow')} value={reading.battery_id} />
    <Text label={c('balance.layout.groupState')} value={reading.state} />
    <Count label={c('balance.layout.groupMounts')} value={reading.mounts} />
    <Count label={c('balance.layout.groupBarrels')} value={reading.barrels} />
    <Quantity label={c('balance.layout.groupFreeboard')} text={units.text(reading.freeboard_m, 'length', 'm')} />
    <Text label={c('balance.layout.groupSelector')} value={reading.mount_selector} />
    <Plain label={c('balance.layout.groupAdjustment')} value={reading.weight_adjustment} />
  </Group>;
}

/**
 * One layout's own readings, printed as the server returned them.
 *
 * The freeboard, the height factor and the complete two-group armour are the
 * kernel's numbers. An absent group and a group of zero mounts are different
 * facts and are printed as the different things they are; nothing here
 * recomputes, rounds into a different quantity or fills a gap.
 */
function LayoutReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const armour = reading.armour === null || reading.armour === undefined ? null : (reading.armour as Raw);
  const values = (armour?.values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const groups = (reading.groups ?? {}) as Raw;
  const status = String(reading.status ?? '');
  return <section className="concept-balance-group">
    <h5>{String(reading.id ?? '')}</h5>
    <p className="form-hint">{c('balance.layout.method', {
      method: String(reading.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    <div className="metric-grid">
      <Quantity label={c('balance.layout.freeboard')} text={units.text(reading.freeboard_m, 'length', 'm')} />
      <Plain label={c('balance.layout.super')} value={reading.super_factor} />
      <Count label={c('balance.layout.mounts')} value={reading.mounts} />
      <Count label={c('balance.layout.barrels')} value={reading.barrels} />
    </div>
    <LayoutGroupReading title={c('balance.layout.group1')} reading={(groups.group1 ?? {}) as Raw} />
    <LayoutGroupReading title={c('balance.layout.group2')} reading={(groups.group2 ?? {}) as Raw} />
    {armour === null ? <p className="form-hint">{c('balance.layout.armourNone')}</p> : <>
      <h4>{c('balance.layout.armour')}</h4>
      <p className="form-hint">{c('balance.layout.armourMethod', {
        method: String(((armour.provenance ?? {}) as Raw).method ?? '') })}</p>
      <div className="metric-grid">
        <LongTons label={c('concept.armour.face')} value={values.face_long_tons} />
        <LongTons label={c('concept.armour.side')} value={values.rear_roof_long_tons} />
        <LongTons label={c('concept.armour.barbette')} value={values.barbette_long_tons} />
        <LongTons label={c('balance.layout.armourTotal')} value={values.total_long_tons} />
      </div>
    </>}
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.layout.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.layout.diagnostics" />
  </section>;
}

/**
 * The layout readings of a saved result.
 *
 * A project that declares no layout keeps the old structure exactly: the section
 * is absent rather than empty, because an empty section would claim the screen
 * looked for layouts and found none.
 */
function LayoutReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.layout.title')}</h4>
    <p className="form-hint">{c('balance.layout.note')}</p>
    {readings.map(reading =>
      <LayoutReading key={String(reading.id ?? '')} reading={reading} />)}
  </section>;
}

/**
 * The per-term breakdown one recovered region actually has.
 *
 * The core reports `plate_long_tons` for a planar plate, the three deck areas for
 * a deck and the fore/aft towers for a conning tower. Which of those exists is
 * the *kind's* own fact, read from the returned key set rather than from a
 * recomputed kind: an unknown kind shows nothing rather than a guessed breakdown.
 */
function FixedArmourBreakdown({ kind, values }: { kind: unknown; values: Raw }) {
  const c = useConceptCopy();
  if (kind === 'deck') return <>
    <LongTons label={c('balance.fixedArmour.metric.central')} value={values.central_long_tons} />
    <LongTons label={c('balance.fixedArmour.metric.fore')} value={values.fore_long_tons} />
    <LongTons label={c('balance.fixedArmour.metric.quarter')} value={values.quarter_long_tons} />
  </>;
  if (kind === 'conning') return <>
    <LongTons label={c('balance.fixedArmour.metric.foreTower')} value={values.fore_long_tons} />
    <LongTons label={c('balance.fixedArmour.metric.aftTower')} value={values.aft_long_tons} />
  </>;
  if (typeof kind === 'string') {
    return <LongTons label={c('balance.fixedArmour.plate')} value={values.plate_long_tons} />;
  }
  return null;
}

/** One fixed region's own reading, with its method, source and status beside it. */
function FixedArmourReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const values = (reading.values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const id = reading.id;
  return <section className="concept-balance-group">
    <h5>{typeof id === 'string' && id !== '' ? id : c('balance.fixedArmour.unidentified')}</h5>
    <p className="form-hint">{c('balance.fixedArmour.method', {
      method: String(reading.method_version ?? ''),
      source: String(provenance.source_sha256 ?? '') })}</p>
    {typeof reading.kind === 'string' ? <Text label={c('concept.fixedArmour.kind')}
      value={String(reading.kind)} /> : null}
    <div className="metric-grid">
      <LongTons label={c('balance.fixedArmour.total')} value={values.total_long_tons} />
      <Plain label={c('balance.fixedArmour.metric.mass')} value={values.mass_t} unit="t" />
      <FixedArmourBreakdown kind={reading.kind} values={values} />
    </div>
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.fixedArmour.unavailable', { status })}</div>}
    {/* A region opted into the rectangular panel model keeps this reading for
        comparison but no longer adopts from it: the geometric model replaced it,
        and saying so is not the same as relabelling the empirical number. */}
    {reading.active_mass_model === 'geometry' ? <div className="notice" role="status">
      {c('balance.fixedArmour.geometryInactive')}</div> : null}
    <Diagnostics reasons={reasons} title="balance.fixedArmour.diagnostics" />
  </section>;
}

/** The fixed armour readings of a saved result, absent when none were declared. */
function FixedArmourReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.fixedArmour.title')}</h4>
    <p className="form-hint">{c('balance.fixedArmour.note')}</p>
    {readings.map((reading, index) =>
      <FixedArmourReading key={`${String(reading.id ?? '')}-${index}`} reading={reading} />)}
  </section>;
}

/**
 * One auxiliary weapon's own reading, with its method, source and status beside it.
 *
 * The recovered expression returns the weapons and their mount as two separate
 * long-ton contributions and the recovered per-location mount factor beside them,
 * and the combined figure is proposed exactly once. Printing all three keeps the
 * reader able to see which part of the mass is the weapon and which is its mount,
 * which is the one distinction this declaration exists to preserve.
 */
function AuxiliaryWeaponReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const values = (reading.values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const id = reading.id;
  return <section className="concept-balance-group">
    <h5>{typeof id === 'string' && id !== '' ? id : c('balance.auxiliary.unidentified')}</h5>
    <p className="form-hint">{c('balance.auxiliary.method', {
      method: String(reading.method_version ?? ''),
      source: String(provenance.source_sha256 ?? '') })}</p>
    {typeof reading.kind === 'string'
      ? <Text label={c('concept.auxiliary.kind')} value={reading.kind} /> : null}
    <div className="metric-grid">
      <LongTons label={c('balance.auxiliary.metric.weapon')} value={values.weapon_long_tons} />
      <LongTons label={c('balance.auxiliary.metric.mount')} value={values.mount_long_tons} />
      <LongTons label={c('balance.auxiliary.metric.total')} value={values.total_long_tons} />
      <Plain label={c('balance.auxiliary.metric.mass')} value={values.mass_t} unit="t" />
      <Plain label={c('balance.auxiliary.metric.factor')} value={values.mount_factor} />
    </div>
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.auxiliary.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.auxiliary.diagnostics" />
  </section>;
}

/** The auxiliary weapon readings, absent when none were declared. */
function AuxiliaryWeaponReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.auxiliary.title')}</h4>
    <p className="form-hint">{c('balance.auxiliary.note')}</p>
    {readings.map((reading, index) =>
      <AuxiliaryWeaponReading key={`${String(reading.id ?? '')}-${index}`} reading={reading} />)}
  </section>;
}

/**
 * The empirical cost reading, with the source's own currency convention beside it.
 *
 * Both money figures keep the recovered labels — million dollars and million
 * pounds, converted with the source's own fixed ratio. Nothing here converts to
 * a modern currency, applies an exchange rate or adjusts for inflation, and the
 * masses that produced the reading are the *selected* masses of one loading
 * condition: a proposed mass is never one of them.
 */
function ArmourReviewReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const provenance = (reading.provenance ?? {}) as Raw;
  return <section className="concept-balance-group" aria-label={c('armourReview.title')}>
    <h4>{c('armourReview.title')}</h4>
    <p className="form-hint">{String(reading.method_version ?? '')} · {String(provenance.source_sha256 ?? '')}</p>
    <p className="form-hint">{c('armourReview.note')}</p>
    <div className="metric-grid">
      <Plain label={c('armourReview.angle')} value={provenance.belt_inclination_deg} unit="°" />
      <Text label={c('armourReview.source')} value={provenance.declared_source} />
    </div>
    {rows(reading.checks).map(check => {
      const values = (check.values ?? {}) as Raw;
      const status = check.status === 'warning' ? 'warning' : check.status === 'pass' ? 'pass' : 'unavailable';
      const code = String(check.code ?? '');
      const knownRule = ['minimum_length', 'belt_pair', 'normal_length', 'main_coverage', 'height'].includes(code);
      return <div className="form-card" key={String(check.id)}>
        <strong>{knownRule ? c(`armourReview.rule.${code}` as ConceptKey) : code}
          {check.record_id ? ` · ${String(check.record_id)}` : ''}</strong>
        <p className="form-hint">{c(`armourReview.${status}` as ConceptKey)}</p>
        <div className="metric-grid">
          {([
            ['minimum_main_belt_length_m', 'armourReview.minimum'],
            ['maximum_height_m', 'armourReview.limit'], ['declared_height_m', 'armourReview.height'],
            ['declared_length_m', 'armourReview.length'],
          ] as const).filter(([key]) => key in values).map(([key, label]) =>
            <Quantity key={key} label={c(label)} text={units.text(values[key], 'length', 'm')} />)}
          {'normal_length_ratio' in values && <Plain label={c('armourReview.ratio')} value={values.normal_length_ratio} />}
        </div>
      </div>;
    })}
  </section>;
}

/**
 * One whole-battery reading: the recovered source estimate and the current
 * condition's selected ledger, side by side and never added together.
 *
 * The declared estimate is the recovered expression's own figures with its own
 * method and source beside them; the selected figures are the current
 * condition's ledger and are labelled as such. A figure the declared inputs
 * cannot support is unknown, and the source total is the recovered one that
 * excludes ammunition — stated on the panel rather than assumed.
 */
function BatteryTotalReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const values = (reading.values ?? {}) as Raw;
  const selected = (reading.selected_values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const id = reading.id;
  return <section className="concept-balance-group">
    <h5>{typeof id === 'string' && id !== '' ? id : c('balance.batteryTotals.unidentified')}</h5>
    <p className="form-hint">{c('balance.batteryTotals.method', {
      method: String(reading.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    <Group title={c('balance.batteryTotals.estimated')} note={c('balance.batteryTotals.ammunition')}>
      <Quantity label={c('balance.batteryTotals.metric.guns')} text={units.text(values.guns_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.mounts')} text={units.text(values.mounts_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.armour')} text={units.text(values.armour_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.total')} text={units.text(values.total_t, 'mass', 't')} />
    </Group>
    <Group title={c('balance.batteryTotals.selected')}>
      <Quantity label={c('balance.batteryTotals.metric.guns')} text={units.text(selected.guns_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.mounts')} text={units.text(selected.mounts_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.armour')} text={units.text(selected.armour_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryTotals.metric.total')} text={units.text(selected.total_t, 'mass', 't')} />
    </Group>
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.batteryTotals.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.batteryTotals.diagnostics" />
  </section>;
}

/** Every declared layout's whole-battery reading, absent when none is declared. */
function BatteryTotalReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.batteryTotals.title')}</h4>
    <p className="form-hint">{c('balance.batteryTotals.note')}</p>
    {readings.map((reading, index) =>
      <BatteryTotalReading key={`${String(reading.id ?? '')}-${index}`} reading={reading} />)}
  </section>;
}

/**
 * One selected layout's whole-battery allocation, with the three totals kept
 * apart and the per-battery records printed exactly as the server returned them.
 *
 * The source total is the recovered SPS estimate, the allocated total is the
 * product's proportional policy, the old per-row subtotal is the unreferenced
 * legacy figure, and the selected total is the current condition's own ledger.
 * They are named apart and never added together. Every number here is the
 * server's: this component evaluates no share and no allocation. A partial
 * reading — one whose source allocation is unavailable while the independently
 * selected facts were still read — is shown as partial rather than refused.
 */
function BatteryAllocationReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const values = (reading.values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const id = reading.id;
  const records = rows(reading.records);
  return <section className="concept-balance-group">
    <h5>{typeof id === 'string' && id !== '' ? id : c('balance.batteryAllocation.unidentified')}</h5>
    <p className="form-hint">{c('balance.batteryAllocation.method', {
      method: String(reading.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    {/* The source method and the product policy are separate facts, named side
        by side rather than merged into one `method_version`. */}
    <div className="metric-grid">
      <Text label={c('balance.batteryAllocation.sourceMethod')} value={provenance.source_method_version} />
      <Text label={c('balance.batteryAllocation.policy')} value={provenance.allocation_policy} />
      <Text label={c('balance.batteryAllocation.declaredSource')} value={provenance.declared_source} />
    </div>
    <Group title={c('balance.batteryAllocation.totals')} note={c('balance.batteryAllocation.note')}>
      <Quantity label={c('balance.batteryAllocation.sourceTotal')}
        text={units.text(values.source_mounts_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryAllocation.legacyTotal')}
        text={units.text(values.legacy_mounts_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryAllocation.allocatedTotal')}
        text={units.text(values.allocated_total_t, 'mass', 't')} />
      <Quantity label={c('balance.batteryAllocation.selectedTotal')}
        text={units.text(values.selected_mounts_t, 'mass', 't')} />
    </Group>
    {records.length > 0 && <section className="concept-balance-group">
      <h4>{c('balance.batteryAllocation.records')}</h4>
      {records.map((record, index) => {
        const memberId = typeof record.id === 'string' && record.id !== '' ? record.id : '';
        return <section className="concept-balance-group"
          key={`${memberId}-${index}`} aria-label={memberId || undefined}>
          <h5>{memberId !== '' ? memberId : c('balance.batteryAllocation.member', { id: index + 1 })}</h5>
          <p className="form-hint">{String(record.method_version ?? '')}</p>
          <div className="metric-grid">
            <Text label={c('balance.batteryAllocation.target')} value={record.target_id} />
            <Quantity label={c('balance.batteryAllocation.weight')}
              text={units.text(record.weight_t, 'mass', 't')} />
            <Plain label={c('balance.batteryAllocation.share')} value={record.share} />
            <Quantity label={c('balance.batteryAllocation.allocated')}
              text={units.text(record.allocated_mass_t, 'mass', 't')} />
            <Quantity label={c('balance.batteryAllocation.selected')}
              text={units.text(record.selected_mass_t, 'mass', 't')} />
          </div>
        </section>;
      })}
    </section>}
    {status === 'partial' ? <div className="notice" role="status">
      {c('balance.batteryAllocation.partial', { status })}
    </div> : status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.batteryAllocation.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.batteryAllocation.diagnostics" />
  </section>;
}

/** Every selected layout's allocation reading, absent when none is declared. */
function BatteryAllocationReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.batteryAllocation.title')}</h4>
    <p className="form-hint">{c('balance.batteryAllocation.note')}</p>
    {readings.map((reading, index) =>
      <BatteryAllocationReading key={`${String(reading.id ?? '')}-${index}`} reading={reading} />)}
  </section>;
}

/**
 * The one armour-totals reading: the declared estimate and the selected actual.
 *
 * The three belts and the full nine-role total are separate figures, and the
 * complete declared totals exist only when the scope is confirmed complete and
 * no component is unknown; otherwise only the known subtotal is reported, with
 * the components that have no derived mass named beside it. A partial reading is
 * never presented as a total. The selected actual keeps its own belts and full
 * total, unknown whenever a required role is unknown or the ledger is not fully
 * classified.
 *
 * Confirming the scope and having a full estimated total are two different
 * facts: the scope statement is printed whenever the declaration is confirmed,
 * but the "complete total" sentence is printed only when the server actually
 * returned a full `estimated_total_t`. A confirmed scope whose full total is
 * unknown says exactly that — the reading is never asserted to exist because a
 * flag was set.
 */
function ArmourTotalReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const values = (reading.values ?? {}) as Raw;
  const coverage = (reading.coverage ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const inputs = (provenance.inputs ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const uncovered = Array.isArray(coverage.uncovered_component_ids)
    ? coverage.uncovered_component_ids.filter((id): id is string => typeof id === 'string' && id !== '')
    : [];
  return <section className="concept-balance-group">
    <h4>{c('balance.armourTotals.title')}</h4>
    <p className="form-hint">{c('balance.armourTotals.method', {
      method: String(reading.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    <p className="form-hint">{c('balance.armourTotals.note')}</p>
    <Group title={c('balance.armourTotals.declared')}>
      <Quantity label={c('balance.armourTotals.metric.estimatedBelts')}
        text={units.text(values.estimated_belts_t, 'mass', 't')} />
      <Quantity label={c('balance.armourTotals.metric.estimatedTotal')}
        text={units.text(values.estimated_total_t, 'mass', 't')} />
      <Quantity label={c('balance.armourTotals.metric.knownSubtotal')}
        text={units.text(values.known_estimate_subtotal_t, 'mass', 't')} />
    </Group>
    <Group title={c('balance.armourTotals.selected')}>
      <Quantity label={c('balance.armourTotals.metric.selectedBelts')}
        text={units.text(values.selected_belts_t, 'mass', 't')} />
      <Quantity label={c('balance.armourTotals.metric.selectedTotal')}
        text={units.text(values.selected_total_t, 'mass', 't')} />
    </Group>
    <p className="form-hint">{inputs.declared_complete === true
      ? c('balance.armourTotals.scopeComplete') : c('balance.armourTotals.incomplete')}</p>
    {inputs.declared_complete === true && (metric(values.estimated_total_t) === null
      ? <p className="form-hint">{c('balance.armourTotals.fullUnavailable')}</p>
      : <p className="form-hint">{c('balance.armourTotals.complete')}</p>)}
    {uncovered.length > 0 && <p className="form-hint">
      {c('balance.armourTotals.uncovered', { ids: uncovered.join(', ') })}</p>}
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.armourTotals.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.armourTotals.diagnostics" />
  </section>;
}

/**
 * The recovered default armour sizes, exactly as the server returned them.
 *
 * The eight dimensions are the recovered expression's own suggestion, each with
 * its own availability: a dimension the core could not derive from the declared
 * hull is named unavailable with the server's reason beside it, never filled from
 * a neighbouring field and never read as a zero. This is a reading, not a copy:
 * the panel that writes the suggestion into a record's two declared dimensions is
 * the only thing that ever edits a draft, and it does so under the reader's own
 * explicit choice.
 */
function ArmourDefaultsReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const values = (reading.values ?? {}) as Raw;
  const availability = (reading.availability ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  return <section className="concept-balance-group">
    <h4>{c('balance.armourDefaults.title')}</h4>
    <p className="form-hint">{c('balance.armourDefaults.method', {
      method: String(reading.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    <p className="form-hint">{c('balance.armourDefaults.note')}</p>
    <div className="metric-grid">
      {ARMOUR_DEFAULT_VALUE_KEYS.map(([kind, field, key]) => {
        const entry = object(availability[key]);
        const state = entry.state ?? entry.status;
        const available = state === 'available';
        return <div className="fact-field" key={key}>
          <span className="fact-label">{c(ARMOUR_DEFAULT_LABELS[kind][field])}</span>
          <span className="fact-value">{units.text(available ? values[key] : null, 'length', 'm')}</span>
          <span className="fact-meta">{available ? c('balance.armourDefaults.state.available')
            : c('balance.armourDefaults.state.unavailable')}
            {typeof entry.reason === 'string' && entry.reason !== '' ? ` · ${entry.reason}` : ''}</span>
        </div>;
      })}
    </div>
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.armourDefaults.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.armourDefaults.diagnostics" />
  </section>;
}

/**
 * One region's geometric panel reading: area, volume and masses in their units,
 * with each plate read separately.
 *
 * Canonical SI values render in the reader's preferred area, volume and mass
 * units. The region's own `adoptable` and its
 * source diagnostics are printed as the server stated them, so a number that is
 * mathematically available but not adoptable reads as exactly that.
 */
function ArmourGeometryReading({ reading }: { reading: Raw }) {
  const c = useConceptCopy();
  const units = useUnits();
  const values = (reading.values ?? {}) as Raw;
  const provenance = (reading.provenance ?? {}) as Raw;
  const reasons = rows(reading.diagnostics);
  const status = String(reading.status ?? '');
  const id = reading.id;
  const records = rows(reading.records);
  return <section className="concept-balance-group">
    <h5>{typeof id === 'string' && id !== '' ? id : c('balance.armourGeometry.unidentified')}</h5>
    <p className="form-hint">{c('balance.armourGeometry.method', {
      method: String(reading.method_version ?? ''),
      source: [provenance.source, provenance.region_source]
        .filter(value => typeof value === 'string' && value !== '').join(' · ') })}</p>
    <p className="form-hint">{reading.adoptable === true
      ? c('balance.armourGeometry.adoptable') : c('balance.armourGeometry.notAdoptable')}</p>
    <Group title={c('balance.armourGeometry.totals')} note={c('balance.armourGeometry.note')}>
      <Quantity label={c('balance.armourGeometry.area')} text={units.text(values.area_m2, 'area', 'm')} />
      <Quantity label={c('balance.armourGeometry.volume')} text={units.text(values.volume_m3, 'volume', 'm')} />
      <Quantity label={c('balance.armourGeometry.mass')} text={units.text(values.mass_t, 'mass', 't')} />
      <Quantity label={c('balance.armourGeometry.knownSubtotal')}
        text={units.text(values.known_mass_subtotal_t, 'mass', 't')} />
    </Group>
    {records.length > 0 && <section className="concept-balance-group">
      <h4>{c('balance.armourGeometry.plates')}</h4>
      {records.map((record, index) => {
        const plateId = typeof record.id === 'string' ? record.id : '';
        const plateValues = (record.values ?? {}) as Raw;
        const plateProvenance = (record.provenance ?? {}) as Raw;
        const plateStatus = String(record.status ?? '');
        return <section className="concept-balance-group"
          key={`${plateId}-${index}`} aria-label={plateId !== '' ? plateId : undefined}>
          <h5>{plateId !== '' ? plateId : c('balance.armourGeometry.plate', { id: index + 1 })}</h5>
          <p className="form-hint">{c('balance.armourGeometry.method', {
            method: String(record.method_version ?? ''),
            source: [plateProvenance.plate_source, plateProvenance.density_source]
              .filter(value => typeof value === 'string' && value !== '').join(' · ') })}</p>
          <div className="metric-grid">
            <Quantity label={c('balance.armourGeometry.area')} text={units.text(plateValues.area_m2, 'area', 'm')} />
            <Quantity label={c('balance.armourGeometry.volume')} text={units.text(plateValues.volume_m3, 'volume', 'm')} />
            <Quantity label={c('balance.armourGeometry.mass')} text={units.text(plateValues.mass_t, 'mass', 't')} />
          </div>
          {plateStatus === '' || plateStatus === 'available' ? null : <div className="notice" role="status">
            {c('balance.armourGeometry.unavailable', { status: plateStatus })}</div>}
          {record.adoptable === false ? <div className="notice" role="status">
            {c('balance.armourGeometry.notAdoptable')}</div> : null}
          <Diagnostics reasons={rows(record.diagnostics)} title="balance.armourGeometry.diagnostics" />
        </section>;
      })}
    </section>}
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.armourGeometry.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.armourGeometry.diagnostics" />
  </section>;
}

/** Every selected region's geometric reading, absent when none was declared. */
function ArmourGeometryReadings({ readings }: { readings: Raw[] }) {
  const c = useConceptCopy();
  if (readings.length === 0) return null;
  return <section className="concept-balance-group">
    <h4>{c('balance.armourGeometry.title')}</h4>
    <p className="form-hint">{c('balance.armourGeometry.whole')}</p>
    {readings.map((reading, index) =>
      <ArmourGeometryReading key={`${String(reading.id ?? '')}-${index}`} reading={reading} />)}
  </section>;
}

function AuxiliarySpaceReading({reading}:{reading:Raw}) {
  const c=useConceptCopy();const provenance=object(reading.provenance);
  const definitions=[['deck_area_m2','space.deck','m²'],['hull_volume_m3','space.hull','m³'],
    ['deck_ratio','space.deckRatio',''],['hull_ratio','space.hullRatio','']] as const;
  return <section className="concept-balance-group">
    <h4>{c('space.title')}</h4><p className="form-hint">{c('space.note')}</p>
    <p className="form-hint">{c('space.method',{method:String(reading.method_version??''),source:String(provenance.source_sha256??'')})}</p>
    {[{row:reading,summary:true},...rows(reading.records).map(row=>({row,summary:false}))].map(({row,summary},index)=>{
      const values=object(row.values);const availability=object(row.availability);
      return <div key={index} className="form-card"><h5>{summary?c('space.summary'):String(row.id??'—')}</h5>
        <div className="metric-grid">{definitions.map(([key,label,unit])=>{
          const state=object(availability[key]);const value=state.state==='available'?metric(values[key]):null;
          return <div className="fact-field" key={key}><span className="fact-label">{c(label)}</span>
            <span className="fact-value">{value===null?c('space.unavailable'):`${value.toFixed(3)}${unit?' '+unit:''}`}</span>
            {typeof state.reason==='string'?<span className="fact-meta">{state.reason}</span>:null}</div>;
        })}</div><Diagnostics reasons={rows(row.diagnostics)} title="space.diagnostics"/>
      </div>;
    })}
  </section>;
}

function CostReading({ cost }: { cost: Raw }) {
  const c = useConceptCopy();
  const values = (cost.values ?? {}) as Raw;
  const provenance = (cost.provenance ?? {}) as Raw;
  const reasons = rows(cost.diagnostics);
  const status = String(cost.status ?? '');
  return <section className="concept-balance-group">
    <h4>{c('balance.cost.title')}</h4>
    <p className="form-hint">{c('balance.cost.method', {
      method: String(cost.method_version ?? ''), source: String(provenance.source_sha256 ?? '') })}</p>
    <p className="form-hint">{c('balance.cost.note')}</p>
    <div className="metric-grid">
      <Plain label={c('balance.cost.metric.usd')} value={values.usd_million} unit="million USD" />
      <Plain label={c('balance.cost.metric.gbp')} value={values.gbp_million} unit="million GBP" />
      <LongTons label={c('balance.cost.metric.load')} value={values.load_long_tons} />
      <LongTons label={c('balance.cost.metric.light')} value={values.light_basis_long_tons} />
      <Plain label={c('balance.cost.metric.yearFactor')} value={values.year_factor} />
      <Plain label={c('balance.cost.metric.base')} value={values.base_usd_million} unit="million USD" />
      <Plain label={c('balance.cost.metric.lightShare')} value={values.light_usd_million} unit="million USD" />
      <Plain label={c('balance.cost.metric.machineryShare')} value={values.machinery_usd_million} unit="million USD" />
      <Plain label={c('balance.cost.metric.borneShare')} value={values.borne_usd_million} unit="million USD" />
    </div>
    <p className="form-hint">{c('balance.cost.currency')}</p>
    {status === '' || status === 'available' ? null : <div className="notice" role="status">
      {c('balance.cost.unavailable', { status })}</div>}
    <Diagnostics reasons={reasons} title="balance.cost.diagnostics" />
    <p className="form-hint">{c('balance.cost.unitConvention')}</p>
  </section>;
}

/**
 * The three optional component readings, under whichever gate applies.
 *
 * Nothing renders when the gate refuses: an absent optional feature adds no
 * section, and an envelope the parent gate did not deliver shows no residual
 * figure here at all.
 */
export function ConceptComponentReadings({ data, envelope, policy = 'report' }: {
  data: StageEnvelope['data'] | null; envelope?: StageEnvelope | null; policy?: ReadingsPolicy;
}) {
  if (!readingsAllowed(policy, envelope)) return null;
  const { fixedArmour, layouts, auxiliaryWeapons, cost } = componentReadings(data);
  const batteryTotals = rows(data?.battery_totals);
  const allocations = rows(data?.battery_mass_allocation);
  const armourGeometry = rows(data?.armour_geometry);
  const armourTotals = data?.armour_totals && typeof data.armour_totals === 'object'
    ? data.armour_totals as Raw : null;
  const armourDefaults = data?.armour_defaults && typeof data.armour_defaults === 'object'
    ? data.armour_defaults as Raw : null;
  return <>
    <LayoutReadings readings={layouts} />
    <FixedArmourReadings readings={fixedArmour} />
    <AuxiliaryWeaponReadings readings={auxiliaryWeapons} />
    <BatteryTotalReadings readings={batteryTotals} />
    <BatteryAllocationReadings readings={allocations} />
    <ArmourGeometryReadings readings={armourGeometry} />
    {armourTotals === null ? null : <ArmourTotalReading reading={armourTotals} />}
    {armourDefaults === null ? null : <ArmourDefaultsReading reading={armourDefaults} />}
    {data?.auxiliary_space && typeof data.auxiliary_space === 'object'
      ? <AuxiliarySpaceReading reading={data.auxiliary_space as Raw}/> : null}
    {data?.armour_review && typeof data.armour_review === 'object'
      ? <ArmourReviewReading reading={data.armour_review as Raw} /> : null}
    {cost === null ? null : <CostReading cost={cost} />}
  </>;
}

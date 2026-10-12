import type { ProjectDocument, RunView } from '../types';
import { FactInput } from './FactInput';
import { QuantityField } from './QuantityField';
import { DeclaredFact, Metric, ResultSection } from './FormResults';
import { inputNumber, number, object, stageData } from './formModel';
import { CHOICES, DIMENSION_KEYS } from './units';
import { useWorkspaceCopy, type WorkspaceKey } from '../i18n/workspace';

// `display_preferences` is a reading preference recorded in the project. It
// converts presentation only: every declared input, the ledger, every stage
// result, every export and every fingerprint stays canonical (m / t / kW / kn /
// deg, and kg or mm where the contract stores those units).
const PREFERENCE_LABELS: Record<string, WorkspaceKey> = {
  length: 'report.units.length', mass: 'report.units.mass', power: 'report.units.power',
  speed: 'report.units.speed', angle: 'report.units.angle',
};

const IDENTITY_FIELDS = [
  ['country', 'hull.identity.country', 'text'],
  ['type', 'hull.identity.type', 'text'],
  ['design_year', 'hull.identity.designYear', 'integer'],
  ['laid_down_year', 'hull.identity.laidDown', 'integer'],
  ['engine_built_year', 'hull.identity.engineYear', 'integer'],
] as const;

export function HullSupplementEditor({ project, run, onChange }: { project: ProjectDocument; run: RunView | null; onChange: (project: ProjectDocument) => void }) {
  const w = useWorkspaceCopy();
  const metadata = object(project.metadata); const hull = project.hull; const facts = object(hull.design_facts);
  const preferences = object(project.display_preferences);
  const data = stageData(run, 'l0'); const hydro = stageData(run, 'hydrostatics');
  const declared = object(data.declared_hull);
  function patchPreference(key: string, value: string) {
    const next = { ...preferences };
    if (value === 'project_default') delete next[key]; else next[key] = value;
    onChange({ ...project, display_preferences: next });
  }
  return <div className="form-stack"><div className="form-card"><h3>{w('hull.identity.title')}</h3>
    <label className="field-label">{w('hull.identity.name')}<input aria-label={w('hull.identity.nameAria')} value={project.name} onChange={e => onChange({ ...project, name: e.target.value })} /></label>
    {IDENTITY_FIELDS.map(([key, labelKey, kind]) =>
      <FactInput key={key} label={w(labelKey)} kind={kind} value={metadata[key]} onChange={value => onChange({ ...project, metadata: { ...metadata, [key]: value } })} />)}
  </div><div className="form-card"><h3>{w('hull.design.title')}</h3><p>{w('hull.design.note')}</p>
    <QuantityField label={w('hull.design.maxDraught')} ariaLabel={w('hull.design.maxDraughtAria')} value={number(hull.draught_deep_m)} dimension="length" kind="nonnegative"
      onChange={value => onChange({ ...project, hull: { ...hull, draught_deep_m: value } })} />
    {([['block_coeff_deep', 'hull.design.blockCoeffDeep', undefined], ['reference_displacement_normal_t', 'hull.design.displacementNormal', 'mass'],
      ['reference_displacement_deep_t', 'hull.design.displacementDeep', 'mass']] as const).map(([key, labelKey, dimension]) =>
      <FactInput key={key} label={w(labelKey)} value={facts[key]} dimension={dimension}
        onChange={value => onChange({ ...project, hull: { ...hull, design_facts: { ...facts, [key]: value } } })} />)}
    <p className="form-hint">{w('hull.design.hint')}</p>
  </div><div className="form-card"><h3>{w('hull.display.title')}</h3>
    <p>{w('hull.display.noteLead')}<strong>{w('hull.display.noteStrong')}</strong>{w('hull.display.noteTail')}</p>
    <details className="form-help"><summary>{w('hull.display.helpTitle')}</summary><p>{w('hull.display.helpNote')}</p></details>
    <div className="form-grid">{DIMENSION_KEYS.map(key => <label className="field-label" key={key}>{w('hull.display.unit', { dimension: w(PREFERENCE_LABELS[key]) })}
      <select aria-label={w('hull.display.unit', { dimension: w(PREFERENCE_LABELS[key]) })} value={typeof preferences[key] === 'string' ? String(preferences[key]) : 'project_default'}
        onChange={e => patchPreference(key, e.target.value)}>
        <option value="project_default">{w('hull.display.projectDefault')}</option>
        {CHOICES[key].map(choice => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
      </select></label>)}</div>
  </div>
  <ResultSection available={!!run}>
    <div className="metric-grid">
      <Metric label={w('hull.result.designRatio')} value={object(data.hull_ratios).design_lwl_over_beam} />
      <Metric label={w('hull.result.currentRatio')} value={object(hydro.selected_length_beam_ratio).value} />
      <Metric label={w('hull.result.awp')} value={object(hydro.values).awp_m2} dimension="area" />
      <Metric label={w('hull.result.wetted')} value={object(hydro.wetted_surface).area_m2} dimension="area" />
      <Metric label={w('hull.result.volume')} value={object(hydro.values).volume_m3} dimension="volume" />
      <Metric label={w('hull.result.displacement')} value={object(hydro.values).displacement_t} dimension="mass" />
    </div>
    {Object.keys(object(declared.design_facts)).length > 0 && <div className="form-card"><h3>{w('hull.result.declaredTitle')}</h3>
      <p className="form-hint">{String(declared.boundary ?? w('hull.result.boundary'))}</p>
      <div className="metric-grid">
        {([['reference_displacement_normal_t', 'hull.design.displacementNormal', 'mass'], ['reference_displacement_deep_t', 'hull.design.displacementDeep', 'mass']] as const).map(([key, labelKey, dimension]) =>
          <DeclaredFact key={key} label={w(labelKey)} unit="" fact={object(declared.design_facts)[key]} dimension={dimension} />)}
      </div>
    </div>}
  </ResultSection></div>;
}
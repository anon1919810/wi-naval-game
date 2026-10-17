import { useConceptCopy } from '../i18n/concept';
import { object, type Raw } from './formModel';
import {
  massSummaryEnabled, massSummaryOf, newMassSummary, patchMassSummary, removeMassSummary,
} from './conceptDesign';

/**
 * The optional whole-battery and armour mass summary, declared as ordinary inputs.
 *
 * This is a *declaration of scope*, not a mass: one source text and one
 * complete-scope flag, and nothing else. It offers no ledger target and no
 * adoption button, because the readings it turns on are the server's own: the
 * whole-battery estimate is the recovered expression's figure and the current
 * condition is the selected ledger, kept apart from it and never copied into a
 * weight by anything on this screen.
 *
 * The complete-scope flag is deliberately the only thing that can make a complete
 * estimated total: an absent, null or unchecked flag says the declaration does not
 * cover every armour category, so a known subtotal stays readable but is never
 * called a whole total. Confirming it says exactly that the declarations cover all
 * armour and every category left out is a declared zero — which is why the hint
 * spells that meaning out rather than leaving the checkbox to be guessed at.
 */

interface MassSummaryPanelProps {
  config: Raw;
  commit: (next: Raw) => void;
}

export function MassSummaryPanel({ config, commit }: MassSummaryPanelProps) {
  const c = useConceptCopy();
  const summary = massSummaryOf(config);
  const enabled = massSummaryEnabled(config);
  // A null flag is not a claim of completeness: only an explicit true does it.
  const complete = object(summary).armour_scope_complete === true;

  return <div className="form-card">
    <h3>{c('concept.group.massSummary')}</h3>
    <label className="field-label">
      <input type="checkbox" aria-label={c('concept.massSummary.use')} checked={enabled}
        onChange={event => commit(event.target.checked
          ? { ...config, mass_summary: newMassSummary() } : removeMassSummary(config))} />
      {enabled ? c('concept.on') : c('concept.off')}
    </label>
    <p className="form-hint">{c('concept.massSummary.note')}</p>
    {!enabled ? null : <>
      <div className="form-grid">
        <label className="field-label">{c('concept.massSummary.source')}
          <input aria-label={c('concept.massSummary.source')}
            value={typeof object(summary).source === 'string' ? String(object(summary).source) : ''}
            placeholder={c('concept.source.placeholder')}
            onChange={event => commit(patchMassSummary(config,
              { source: event.target.value.trim() === '' ? null : event.target.value }))} />
          <small>{c('concept.massSummary.sourceHint')}</small>
        </label>
      </div>
      <label className="field-label">
        <input type="checkbox" aria-label={c('concept.massSummary.complete')} checked={complete}
          onChange={event => commit(patchMassSummary(config,
            { armour_scope_complete: event.target.checked }))} />
        {c('concept.massSummary.complete')}
      </label>
      <p className="form-hint">{c('concept.massSummary.completeHint')}</p>
      <p className="form-hint">{c('concept.massSummary.separate')}</p>
    </>}
  </div>;
}

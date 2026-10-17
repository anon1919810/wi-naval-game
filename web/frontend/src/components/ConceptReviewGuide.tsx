import { useConceptCopy, type ConceptKey } from '../i18n/concept';
import type { RunView } from '../types';

/**
 * Where this saved revision stands, in six steps.
 *
 * The guide is a *reading* of state the workbench already owns: whether the
 * concept screen is enabled, whether the draft has edits the saved revision does
 * not describe, whether a result exists for exactly this saved revision and the
 * selected loading condition, and whether the calculation options on screen are
 * the ones that produced it. It adds no request, no endpoint and no engineering
 * calculation of its own.
 *
 * Its discipline is the one the whole apply workflow already has, stated rather
 * than reimplemented: an old check stays *history* and is never presented as the
 * current result, a proposal is never chosen for the reader, a mass is replaced
 * only by an explicit adoption against a saved revision, and a successful apply
 * is not convergence. The cost reading is called out separately because it reads
 * the *selected* masses: adopting armour alone does not move it, and only an
 * explicit adoption of a component the recovered expression actually reads — and
 * then only after the next run — can.
 */

export interface ReviewGuideProps {
  /** The concept design section exists, so this chapter is requested at all. */
  enabled: boolean;
  /** The draft has edits, or hand-written JSON that has not been applied. */
  dirty: boolean;
  /** The saved revision the reader is standing on. */
  revision: number;
  /** The selected loading condition; every reading belongs to one condition. */
  conditionId: string;
  /** The current result: this project, this saved revision, this condition. */
  current: RunView | null;
  /** The request on screen asks for the concept screen. */
  requested: boolean;
  /** The saved result's options are the options now on screen. */
  requestCurrent: boolean;
}

interface Step {
  name: ConceptKey;
  done: boolean;
  detail: ConceptKey | null;
  params?: Record<string, string | number>;
}

export function ConceptReviewGuide({ enabled, dirty, revision, conditionId, current,
  requested, requestCurrent }: ReviewGuideProps) {
  const c = useConceptCopy();
  const resultAvailable = current !== null;
  const reviewable = resultAvailable && requested && requestCurrent;

  const steps: Step[] = [
    { name: 'concept.guide.step.declare', done: enabled,
      detail: enabled ? 'concept.guide.state.declare' : 'concept.guide.state.declareOff' },
    { name: 'concept.guide.step.save', done: enabled && !dirty,
      detail: dirty ? 'concept.guide.state.saveDirty' : 'concept.guide.state.save',
      params: { revision } },
    { name: 'concept.guide.step.run', done: enabled && !dirty && resultAvailable && requested,
      // No current result and no request is a different refusal than no result.
      detail: !requested ? 'concept.guide.state.runUnrequested'
        : resultAvailable ? 'concept.guide.state.run' : 'concept.guide.state.runNone' },
    { name: 'concept.guide.step.review', done: reviewable,
      // A result that exists but is not current for these options is kept, and
      // said to be kept, rather than quietly presented as the one to review. With
      // no current result at all, an older check stays history and says so.
      detail: !resultAvailable ? 'concept.guide.state.reviewStale'
        : !requested ? 'concept.guide.state.runUnrequested'
          : !requestCurrent ? 'concept.guide.state.reviewChanged'
            : 'concept.guide.state.review' },
    { name: 'concept.guide.step.apply', done: false, detail: 'concept.guide.state.apply' },
    { name: 'concept.guide.step.rerun', done: false, detail: 'concept.guide.state.rerun' },
  ];

  return <section className="form-card" aria-label={c('concept.guide.title')}>
    <h4>{c('concept.guide.title')}</h4>
    <p className="form-hint">{c('concept.guide.revision', {
      revision, condition: conditionId === '' ? '—' : conditionId })}</p>
    <p className="form-hint">{c('concept.guide.note')}</p>
    {/* Existing list and hint classes only: this guide adds no new styling, so it
        cannot change the look of the chapter it sits in. */}
    <ol className="diagnostics-list">{steps.map(step => <li key={step.name}>
      <strong>{c(step.name)}</strong>
      <span className="form-hint"> · {step.done ? c('concept.guide.done') : c('concept.guide.pending')}</span>
      {step.detail && <p className="form-hint">{c(step.detail, step.params ?? { revision })}</p>}
    </li>)}</ol>
    <p className="form-hint">{c('concept.guide.cost')}</p>
  </section>;
}

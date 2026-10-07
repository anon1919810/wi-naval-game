import type { MouseEventHandler, RefObject } from 'react';
import { Artwork } from './Artwork';
import { APP_ENTRY_LINK, publicHref } from './routes';
import { TitleEntry } from './TitleEntry';
import type { PlanSheet } from './plans';

interface Row {
  readonly label: string;
  readonly text: string;
}

interface Section {
  readonly index: string;
  readonly title: string;
  /** Rows for the flat editorial layout; no card wall, no invented numbers. */
  readonly body: readonly Row[];
}

const OVERVIEW: readonly Row[] = [
  { label: 'What it is', text: 'A naval design and analysis workbench for studying ship projects: loading conditions, stability, resistance and simplified damage. Projects are edited in the browser, saved as immutable revisions, and calculated by one Python core that also runs from a command line, with no interface at all.' },
  { label: 'How it is organised', text: 'One weight ledger per loading condition, then a request for the calculation stages you actually need. Each result records the revision, condition, scenario and request it belongs to, so a stored number always says what produced it.' },
  { label: 'One work, three drawings', text: 'The three reference line sheets on the Work page are alternatives inside this single project, not three projects and not interchangeable verified specifications of one vessel.' },
];

const CAPABILITIES: readonly Row[] = [
  { label: 'Weight ledger', text: 'One ledger is the only mass authority. Every item keeps its own identity, source and estimate flag, and two items claiming the same weight block a complete total rather than counting it twice.' },
  { label: 'Loading conditions', text: 'Normal, full and custom loadings, with mass and the three axis moments. A present zero is known zero, a present null is unknown, and missing mass is never replaced by a residual invented to match a reference displacement.' },
  { label: 'Hydrostatics', text: 'A parameterized hull or a strictly imported offsets table, plus Bonjean and hydrostatic curves, deck freeboard and opening checks. A deck coverage percentage is reported only when both areas have sources; otherwise it stays unknown.' },
  { label: 'Equilibrium and stability', text: 'Draft, trim and heel calculations with liquid-load effects, GM and sampled GZ curves, including opening-immersion checks.' },
  { label: 'Resistance and endurance', text: 'Taylor-Gertler, Schoenherr, Holtrop-Mennen, fixed power and QPC sensitivity, with each method’s validity range, its estimated inputs and any historical comparison condition kept explicit in the result.' },
  { label: 'Simplified damage', text: 'Connected quasi-static flooding of declared compartments over time, with mass conservation, remaining GZ, and explicit completed, partial, failed and cancelled states.' },
  { label: 'Interfaces', text: 'A Python API, single-case, batch and parameter-scan commands, and JSON plus CSV export. The calculation core does not depend on the web service, the database or this site.' },
];

const WORKFLOW: readonly Row[] = [
  { label: '1 · Open', text: 'A visitor gets an anonymous workspace in their own browser. Nothing is shared between visitors, and no account is required.' },
  { label: '2 · Fill', text: 'Edit the ship’s inputs while retaining source and estimate information. Missing data stays explicit.' },
  { label: '3 · Save', text: 'Revisions are immutable. An edit creates a new revision instead of rewriting the one a stored result was calculated from.' },
  { label: '4 · Run', text: 'Choose the stages you need and run. An independent worker claims the queued run from the database, executes the core in a bounded child process, and reports completion, partial results, failure or cancellation.' },
  { label: '5 · Read', text: 'The report names the revision, loading condition, damage scenario and request fingerprint the result belongs to, and changing the request never recomputes a stored one.' },
];

const TECHNOLOGY: readonly Row[] = [
  { label: 'React · TypeScript · Vite', text: 'The public shell: one hash router, the exhibit, this detail and About. The workspace is a separate chunk fetched on demand, so no page here can reach the API.' },
  { label: 'Python calculation core', text: 'Project, loading, hydrostatics, stability, resistance and flooding kernels. The API, the command line and the web service all call this one module.' },
  { label: 'FastAPI · SQLAlchemy · Alembic', text: 'FastAPI serves the application; SQLAlchemy manages stored data, and Alembic versions the database schema.' },
  { label: 'PostgreSQL', text: 'Project storage, immutable revisions, the calculation queue and stored results.' },
  { label: 'Independent worker', text: 'A separate process that claims each queued run, enforces the time and result-size limits, supports cancellation, and marks a lost worker’s run failed instead of leaving it running forever.' },
];

const LIMITS: readonly Row[] = [
  { label: 'Not a full SPS reproduction', text: 'An independent implementation of comparable ideas. Field-for-field equivalence with SPS is not claimed, and proprietary SPS scoring is not implemented.' },
  { label: 'Damage is simplified', text: 'Connected quasi-static flooding only. There is no armour penetration, no explosion and no CFD, and closing a valve does not remove a free surface.' },
  { label: 'Outside the current scope', text: 'Full seakeeping, structural strength, historical cost and combat damage simulation are not modelled.' },
  { label: 'Not a certified design tool', text: '“Completed” means the requested calculation stages finished. It does not mean the inputs are historically verified or that a vessel is seaworthy.' },
  { label: 'Inputs carry declared gaps', text: 'Historical ship inputs are partly estimated. A model’s bounding box is not a real armour spread area, and no tonnage is reconciled with an arbitrary balancing weight. Missing historical data is reported as unknown rather than filled in.' },
  { label: 'Method boundaries are enforced', text: 'A locked-CG proxy with no free surface cannot drive a connected flood; the interface blocks that combination up front with a stated reason instead of letting the kernel stop mid-run and keep partial results.' },
  { label: 'A result belongs to its identity', text: 'Results are valid for the revision, condition, scenario and request fingerprint they were computed with. A trace shorter than the requested duration must be read together with its stop reason; a partial result is not a complete or safe conclusion.' },
];

const SECTIONS: readonly Section[] = [
  { index: '01', title: 'Overview', body: OVERVIEW },
  { index: '02', title: 'Capabilities', body: CAPABILITIES },
  { index: '03', title: 'Workflow', body: WORKFLOW },
  { index: '04', title: 'Technology', body: TECHNOLOGY },
  { index: '05', title: 'Methods & Limits', body: LIMITS },
];

interface Props {
  /** The reference the exhibit is showing, so the hero really is the same drawing. */
  sheet: PlanSheet;
  dark: boolean;
  details: boolean;
  /** The page's own node, so the reading ruler measures this document and not the shell. */
  pageRef: RefObject<HTMLElement | null>;
  /** The H1, still claimed when a route strands the focus on the page it replaced. */
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** The tool link inside that heading. Coming back from the workspace focuses it. */
  ctaRef: RefObject<HTMLAnchorElement | null>;
  /** Same warm-the-chunk entry the exhibit's title uses; the click itself is left to the anchor. */
  prefetchApp: () => void;
  /** Retires the exhibit and the opening before the browser follows the link. */
  onEnterTool: MouseEventHandler<HTMLAnchorElement>;
}

/**
 * The one work detail. Editorial rather than decorative: five numbered sections on
 * the About page's own twelve columns, flat rows, hairline rules and the existing
 * accent, with the selected reference sheet as the only picture. Every claim here
 * is either what the repository actually does or an explicitly stated limit, with
 * no invented statistics, credentials or project repositories.
 *
 * The title is the way into the tool, not a heading with a button under it, and
 * there is no second entry here: this page is already the detail, so it has no
 * project link to offer and one less thing to say the same thing twice.
 */
export function ProjectDetail({ sheet, dark, details, pageRef, headingRef, ctaRef, prefetchApp, onEnterTool }: Props) {
  return <article className="ff-detail" aria-label="Plimsoll, project detail" ref={pageRef}>
    <a className="ff-detail-back" href={publicHref('home')}>BACK TO WORK <span aria-hidden="true">↖</span></a>
    <span className="ff-eyebrow">WORK / 01 · NAVAL DESIGN WORKBENCH</span>
    <TitleEntry
      headingRef={headingRef}
      linkRef={ctaRef}
      parts={['Pl', 'i', 'msoll']}
      dot={1}
      name="Open Plimsoll"
      href={APP_ENTRY_LINK}
      prefetch={prefetchApp}
      onEnter={onEnterTool} />
    <p className="ff-detail-lede">A workbench for studying ship projects — loading, stability, resistance and simplified damage — built on one Python calculation core with a browser interface in front of it.</p>

    <div className="ff-detail-hero">
      <div className="ff-art-scene"><Artwork sheet={sheet} dark={dark} details={details} /></div>
      <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
      <span className="ff-detail-hero-note">REFERENCE {sheet.id} / SAME DRAWING AS THE EXHIBIT</span>
    </div>

    <div className="ff-detail-body">
      {SECTIONS.map(section => <section key={section.index} className="ff-detail-section" aria-labelledby={`ff-detail-${section.index}`} data-ff-section={section.title}>
        <h2 id={`ff-detail-${section.index}`} tabIndex={-1}><span>{section.index}</span>{section.title}</h2>
        <dl className="ff-detail-rows">
          {section.body.map(row => <div className="ff-detail-row" key={row.label}>
            <dt>{row.label}</dt><dd>{row.text}</dd>
          </div>)}
        </dl>
      </section>)}
    </div>
  </article>;
}

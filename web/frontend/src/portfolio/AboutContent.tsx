import type { RefObject } from 'react';
import { Contact } from './Contact';
import { AboutFigure, FrictionStudy, PageField, PowerStudy, ScaleStudy } from './pageGeometry';
import { publicHref } from './routes';

/** What this specific site is built from, so the claim stays checkable. */
const BUILT_WITH: readonly { readonly label: string; readonly text: string }[] = [
  { label: 'React · TypeScript · Vite', text: 'The whole public shell: one hash router, the exhibit, this page and the work detail.' },
  { label: 'SVG and CSS', text: 'Framing, construction lines, inspection lens and transitions. The geometry around the vessel is decorative composition, not measured naval engineering data.' },
  { label: 'Original reference sheets', text: 'The three line drawings are the archived scans themselves, cropped in place and toned per theme. Nothing redrawn, traced or generated.' },
  { label: 'Space Grotesk · Inter', text: 'Self-hosted variable fonts, Latin subset, SIL OFL 1.1. Space Grotesk for headings, Inter for body text.' },
  { label: 'No API on this site', text: 'These public pages never call the Plimsoll service and never create a workspace. Open Plimsoll is the only thing that reaches the tool.' },
];

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
}

/**
 * The public About: who builds it, what direction it takes, what this site is
 * made of, and a contact route that works without a backend. No invented
 * biography, no claim of employment or credentials, and no contact form —
 * there is nothing on this site that could receive one.
 *
 * The three naval studies are worked through as editorial sections rather than a
 * card wall: each one states the relationship, sets the symbols, names its
 * limits, and owns one drawing. Every formula here is the one the calculation
 * core actually uses; none of them is a measurement of a ship.
 */
export function AboutContent({ headingRef }: Props) {
  return <article className="ff-about" aria-label="About Y’s Formfield">
    {/* Same-paper clearances in pageGeometry.css keep this field off the text. */}
    <PageField page="about" />
    {/* A twelve-column field rather than a stack, so every block below starts on
        the same left edge and the figures sit where an editor would put them:
        text on the low columns, drawing on the high ones, never a card grid. */}
    <div className="ff-about-masthead">
      <div className="ff-about-intro">
        <span className="ff-eyebrow">ABOUT THE COLLECTION</span>
        <h1 ref={headingRef} tabIndex={-1}>A field for<br />useful ideas.</h1>
        <p>Yang Duanming’s collection of tools and experiments: naval design work you can open and run, with the drawings it came from.</p>
      </div>
      <AboutFigure />
    </div>

    <section className="ff-about-author" aria-labelledby="ff-about-author-title">
      <h2 id="ff-about-author-title">The person behind it</h2>
      <p>My name is Yang Duanming. I build tools and explore interface design.</p>
      <p>Working software, and the drawings it came from. Plimsoll is the first featured project.</p>
    </section>

    <div className="ff-about-work">
      <span>FIRST WORK / 01</span>
      <h2>Plimsoll</h2>
      <p>Naval design and analysis: ship projects, loading, stability, resistance, simplified damage. An independent Python core with a browser interface, a command line, JSON/CSV export — not a full SPS reproduction.</p>
      <a href={publicHref('project')}>VIEW THE PROJECT <span aria-hidden="true">↗</span></a>
    </div>

    {/* The three quantities the tool reasons in, each a section of the page. */}
    <ScaleStudy />
    <FrictionStudy />
    <PowerStudy />

    <section className="ff-about-built" aria-labelledby="ff-about-built-title">
      <h2 id="ff-about-built-title">Built with</h2>
      <dl className="ff-about-rows">
        {BUILT_WITH.map(row => <div className="ff-about-row" key={row.label}>
          <dt>{row.label}</dt><dd>{row.text}</dd>
        </div>)}
      </dl>
    </section>

    <Contact />
  </article>;
}
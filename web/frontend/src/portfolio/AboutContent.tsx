import type { RefObject } from 'react';
import { Contact } from './Contact';
import { publicHref } from './routes';

/** What this specific site is built from, so the claim stays checkable. */
const BUILT_WITH: readonly { readonly label: string; readonly text: string }[] = [
  { label: 'React · TypeScript · Vite', text: 'The whole public shell: one hash router, the exhibit, this page and the work detail.' },
  { label: 'SVG and CSS', text: 'The framing, construction lines, inspection lens and transitions. The construction geometry around the vessel is decorative composition, not measured naval engineering data.' },
  { label: 'Original reference sheets', text: 'The three line drawings are the archived scans themselves, cropped in place and toned per theme. Nothing is redrawn, traced or generated.' },
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
 */
export function AboutContent({ headingRef }: Props) {
  return <article className="ff-about" aria-label="About Y’s Formfield">
    <span className="ff-eyebrow">ABOUT THE COLLECTION</span>
    <h1 ref={headingRef} tabIndex={-1}>A field for<br />useful ideas.</h1>
    <p>Y’s Formfield is Yang Duanming’s collection of tools and experiments. A place to build, explore, and keep making things better.</p>

    <section className="ff-about-author" aria-labelledby="ff-about-author-title">
      <h2 id="ff-about-author-title">The person behind it</h2>
      <p>My name is Yang Duanming. I build tools and explore interface design.</p>
      <p>This collection brings together practical software and visual experiments. Plimsoll is the first featured project.</p>
    </section>

    <div className="ff-about-work">
      <span>FIRST WORK / 01</span>
      <h2>Plimsoll</h2>
      <p>A naval design and analysis tool for studying ship projects, loading conditions, stability, resistance, and simplified damage. It is an independent Python calculation core with a browser interface, a command line and JSON/CSV export in front of it — not a full SPS reproduction.</p>
      <a href={publicHref('project')}>VIEW THE PROJECT <span aria-hidden="true">↗</span></a>
    </div>

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

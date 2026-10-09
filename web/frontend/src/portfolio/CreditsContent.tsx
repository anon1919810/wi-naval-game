import type { RefObject } from 'react';

/**
 * The public Credits page.
 *
 * Three sections: the two people whose help shaped the site, who planned it and who
 * implemented it, and what it stands on — one printed source, the three typefaces
 * actually shipped with their foundries, the licence they ship under, and the open
 * source the site is built on.
 *
 * Two people are named with what each of them did, and nothing else: no biography
 * and no account is claimed for either. The reference drawings carry no attribution
 * here, because none has been confirmed for them.
 */

/** The two personal thanks. What each of them did, and nothing else. */
const THANKS: readonly { readonly name: string; readonly text: string }[] = [
  { name: 'simppleasedie', text: 'For thoughtful suggestions on the art direction and visual style of this website.' },
  { name: 'Suxx', text: 'For generously providing Coding Plan credits that supported its development.' },
];

/** Who planned this site and who implemented it. */
const COLOPHON: readonly { readonly label: string; readonly text: string }[] = [
  { label: 'Concept, planning & design direction', text: 'Yang Duanming' },
  { label: 'Review', text: 'Codex · DSH · Kimi Code' },
  { label: 'Implementation assistance', text: 'OpenCode' },
];

/** The one printed source this site leans on, already cited where it is used. */
const SOURCE = { label: 'Ship Resistance and Propulsion', text: 'Molland, Turnock & Hudson.' } as const;

/** The three families shipped, with the foundry that made each one. */
const TYPE: readonly { readonly label: string; readonly text: string; readonly href: string }[] = [
  { label: 'Space Grotesk', text: 'Florian Karsten Typefaces', href: 'https://floriankarsten.github.io/space-grotesk/' },
  { label: 'Inter', text: 'Rasmus Andersson', href: 'https://rsms.me/inter/' },
  { label: 'Archivo', text: 'Omnibus-Type (workspace)', href: 'https://www.omnibus-type.com/fonts/archivo/' },
];

/** The licence text of each shipped family, linked as the file itself. */
const OFL: readonly { readonly label: string; readonly file: string }[] = [
  { label: 'Space Grotesk', file: 'SpaceGrotesk-OFL.txt' },
  { label: 'Inter', file: 'Inter-OFL.txt' },
  { label: 'Archivo', file: 'Archivo-OFL.txt' },
];

/** The open source the public site and the workbench behind it are built on. */
const STACK: readonly { readonly label: string; readonly text: string }[] = [
  { label: 'Open source', text: 'React · TypeScript · Vite' },
  { label: 'Open source', text: 'Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL' },
];

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** The page's own node, so the reading ruler measures this document and not the shell. */
  pageRef: RefObject<HTMLElement | null>;
}

export function CreditsContent({ headingRef, pageRef }: Props) {
  return <article className="ff-credits" aria-label="Credits" ref={pageRef}>
    {/* Same-paper clearance keeps the shell's faint field off the text, as About's
        sections do. Credits draws no field of its own: the shared one is enough,
        and a second drawing would be decoration rather than content. */}
    <div className="ff-credits-masthead">
      <span className="ff-eyebrow">CREDITS</span>
      <h1 ref={headingRef} tabIndex={-1}>With thanks.</h1>
    </div>

    <section className="ff-credits-section ff-credits-section--thanks" aria-labelledby="ff-credits-01" data-ff-section="Acknowledgements">
      <h2 id="ff-credits-01" tabIndex={-1}><span>01</span>Acknowledgements</h2>
      <dl className="ff-credits-rows">
        {THANKS.map(row => <div className="ff-credits-row" key={row.name}>
          <dt>{row.name}</dt><dd>{row.text}</dd>
        </div>)}
      </dl>
    </section>

    <section className="ff-credits-section" aria-labelledby="ff-credits-02" data-ff-section="Colophon">
      <h2 id="ff-credits-02" tabIndex={-1}><span>02</span>Colophon</h2>
      <dl className="ff-credits-rows">
        {COLOPHON.map(row => <div className="ff-credits-row" key={row.label}>
          <dt>{row.label}</dt><dd>{row.text}</dd>
        </div>)}
      </dl>
    </section>

    <section className="ff-credits-section" aria-labelledby="ff-credits-03" data-ff-section="Sources">
      <h2 id="ff-credits-03" tabIndex={-1}><span>03</span>Sources</h2>
      <dl className="ff-credits-rows">
        <div className="ff-credits-row">
          <dt>{SOURCE.label}</dt><dd>{SOURCE.text}</dd>
        </div>
        {TYPE.map(row => <div className="ff-credits-row" key={row.label}>
          <dt>{row.label}</dt>
          <dd><a className="ff-credits-link" href={row.href} target="_blank" rel="noopener noreferrer">{row.text} ↗</a></dd>
        </div>)}
        <div className="ff-credits-row">
          <dt>Licence</dt>
          <dd><span className="ff-credits-licence">SIL Open Font License 1.1</span>{OFL.map(entry => <a className="ff-credits-licence-file" key={entry.file} href={`/fonts/${entry.file}`} target="_blank" rel="noopener noreferrer">{entry.label} OFL ↗</a>)}</dd>
        </div>
        {STACK.map(row => <div className="ff-credits-row" key={row.text}>
          <dt>{row.label}</dt><dd>{row.text}</dd>
        </div>)}
      </dl>
    </section>
  </article>;
}

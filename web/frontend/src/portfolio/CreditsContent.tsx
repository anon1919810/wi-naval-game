import type { RefObject } from 'react';
import { useLanguage, type TranslationKey } from './LanguageProvider';

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
 *
 * What is stated is stated identically in both languages, and each of the three
 * fact boxes below holds exactly what it is allowed to hold. A person's own name,
 * a book, a foundry and a licence are names: they are written the same way in
 * either language and marked as Latin text, and only the sentence describing what
 * someone did is translated. Nothing about anyone is added by the translation.
 */

/** The two personal thanks. What each of them did, and nothing else. */
const THANKS = [
  { name: 'simppleasedie', text: 'credits.thanks.0' },
  { name: 'Suxx', text: 'credits.thanks.1' },
] as const satisfies readonly { readonly name: string; readonly text: TranslationKey }[];

/** Who planned this site and who implemented it. */
const COLOPHON: readonly TranslationKey[] = ['credits.colophon.0', 'credits.colophon.1', 'credits.colophon.2'];

/**
 * The colophon's answers are people's and products' names, so they are written
 * exactly as those names are written and marked as Latin text. The label above
 * each one is prose and is translated.
 */
const COLOPHON_NAMES = ['Yang Duanming', 'Codex · DSH · Kimi Code', 'OpenCode'] as const;

/** The one printed source this site leans on, already cited where it is used. */
const SOURCE: readonly TranslationKey[] = ['credits.sourceBook', 'credits.sourceAuthors'];

/** The three families shipped, with the foundry that made each one. */
const TYPE = [
  { label: 'Space Grotesk', text: 'Florian Karsten Typefaces', href: 'https://floriankarsten.github.io/space-grotesk/' },
  { label: 'Inter', text: 'Rasmus Andersson', href: 'https://rsms.me/inter/' },
  { label: 'Archivo', text: 'Omnibus-Type (workspace)', href: 'https://www.omnibus-type.com/fonts/archivo/' },
] as const;

/** The licence text of each shipped family, linked as the file itself. */
const OFL = [
  { label: 'Space Grotesk', file: 'SpaceGrotesk-OFL.txt' },
  { label: 'Inter', file: 'Inter-OFL.txt' },
  { label: 'Archivo', file: 'Archivo-OFL.txt' },
] as const;

/** The open source the public site and the workbench behind it are built on. */
const STACK: readonly string[] = ['React · TypeScript · Vite', 'Python · FastAPI · SQLAlchemy · Alembic · PostgreSQL', 'Three.js'];

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** The page's own node, so the reading ruler measures this document and not the shell. */
  pageRef: RefObject<HTMLElement | null>;
}

export function CreditsContent({ headingRef, pageRef }: Props) {
  const { t } = useLanguage();
  return <article className="ff-credits" aria-label={t('credits.label')} ref={pageRef}>
    {/* Same-paper clearance keeps the shell's faint field off the text, as About's
        sections do. Credits draws no field of its own: the shared one is enough,
        and a second drawing would be decoration rather than content. */}
    <div className="ff-credits-masthead">
      <span className="ff-eyebrow">{t('credits.eyebrow')}</span>
      <h1 ref={headingRef} tabIndex={-1}>{t('credits.title')}</h1>
    </div>

    <section className="ff-credits-section ff-credits-section--thanks" aria-labelledby="ff-credits-01" data-ff-section={t('credits.sectionThanks')}>
      <h2 id="ff-credits-01" tabIndex={-1}><span>01</span>{t('credits.sectionThanks')}</h2>
      <dl className="ff-credits-rows">
        {THANKS.map(row => <div className="ff-credits-row" key={row.name}>
          {/* Handles are Latin in both languages; the sentence saying what each
              of them did is translated. */}
          <dt lang="en">{row.name}</dt><dd>{t(row.text)}</dd>
        </div>)}
      </dl>
    </section>

    <section className="ff-credits-section" aria-labelledby="ff-credits-02" data-ff-section={t('credits.sectionColophon')}>
      <h2 id="ff-credits-02" tabIndex={-1}><span>02</span>{t('credits.sectionColophon')}</h2>
      <dl className="ff-credits-rows">
        {COLOPHON.map((key, index) => <div className="ff-credits-row" key={key}>
          <dt>{t(key)}</dt><dd lang="en">{COLOPHON_NAMES[index]}</dd>
        </div>)}
      </dl>
    </section>

    <section className="ff-credits-section" aria-labelledby="ff-credits-03" data-ff-section={t('credits.sectionSources')}>
      <h2 id="ff-credits-03" tabIndex={-1}><span>03</span>{t('credits.sectionSources')}</h2>
      <dl className="ff-credits-rows">
        <div className="ff-credits-row">
          <dt lang="en">{t(SOURCE[0])}</dt><dd lang="en">{t(SOURCE[1])}</dd>
        </div>
        {TYPE.map(row => <div className="ff-credits-row" key={row.label} lang="en">
          <dt>{row.label}</dt>
          <dd><a className="ff-credits-link" href={row.href} target="_blank" rel="noopener noreferrer">{row.text} ↗</a></dd>
        </div>)}
        <div className="ff-credits-row">
          <dt>{t('credits.licence')}</dt>
          <dd lang="en"><span className="ff-credits-licence">SIL Open Font License 1.1</span>{OFL.map(entry => <a className="ff-credits-licence-file" key={entry.file} href={`/fonts/${entry.file}`} target="_blank" rel="noopener noreferrer">{entry.label} OFL ↗</a>)}</dd>
        </div>
        {/* Where the drawings on Work came from. A question about the material
            rather than about the stack, so it is stated here with the other
            sources and not in the About technology list. */}
        <div className="ff-credits-row">
          <dt>{t('credits.sheets.label')}</dt><dd>{t('credits.sheets.text')}</dd>
        </div>
        {STACK.map(row => <div className="ff-credits-row" key={row}>
          <dt>{t('credits.openSource')}</dt><dd lang="en">{row}</dd>
        </div>)}
      </dl>
    </section>
  </article>;
}
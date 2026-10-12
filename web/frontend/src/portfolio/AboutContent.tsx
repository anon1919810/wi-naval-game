import type { RefObject } from 'react';
import { Contact } from './Contact';
import { useLanguage } from './LanguageProvider';
import { AboutFigure, FrictionStudy, PageField, PowerStudy, ScaleStudy } from './pageGeometry';
import { publicHref } from './routes';

/**
 * The technology stack, as it is actually built.
 *
 * The keys, not the words: each row names the thing it is about and points at
 * the dictionary entry that says what this project does with it. The claims are
 * identical in both languages — the same frontend, the same drawing and viewer
 * work, the same fonts, the same licence, and the same honest boundary that
 * these public pages never reach the API.
 *
 * Reference-sheet provenance is deliberately not here: it is a question about
 * where the drawings came from, not about how the site is built, so it is stated
 * once in the Credits sources alongside the book and the typefaces.
 */
const BUILT_WITH = [
  'about.built.react',
  'about.built.svg',
  'about.built.three',
  'about.built.python',
  'about.built.fonts',
  'about.built.noApi',
] as const;

/** The rows whose label is a name, a product or a file format, not prose. */
const BUILT_WITH_NAMES = new Set([
  'about.built.react',
  'about.built.three',
  'about.built.python',
  'about.built.fonts',
]);

interface Props {
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** The page's own node, so the reading ruler measures this document and not the shell. */
  pageRef: RefObject<HTMLElement | null>;
}

/**
 * The public About: who builds it, what direction it takes, what this site is
 * made of, and a contact route that works without a backend. No invented
 * biography, no claim of employment or credentials, and no contact form —
 * there is nothing on this site that could receive one. None of that changes in
 * the other language: the Chinese page says the same things about the same
 * person, and says no more.
 *
 * The three naval studies are worked through as editorial sections rather than a
 * card wall: each one states the relationship, sets the symbols, names its
 * limits, and owns one drawing. Every formula here is the one the calculation
 * core actually uses; none of them is a measurement of a ship, and the equations
 * themselves are identical in both languages.
 *
 * Each block is also a section of the reading ruler, named for the ruler in its
 * own words: the numbering the page already prints is the studies' numbering and
 * stays exactly as it is.
 */
export function AboutContent({ headingRef, pageRef }: Props) {
  const { language, t } = useLanguage();
  return <article className="ff-about" aria-label={t('about.label')} ref={pageRef} data-ff-lang={language}>
    {/* Same-paper clearances in pageGeometry.css keep this field off the text. */}
    <PageField page="about" />
    {/* A twelve-column field rather than a stack, so every block below starts on
        the same left edge and the figures sit where an editor would put them:
        text on the low columns, drawing on the high ones, never a card grid. */}
    <div className="ff-about-masthead" data-ff-section={t('about.sectionCollection')}>
      <div className="ff-about-intro">
        <span className="ff-eyebrow">{t('about.eyebrow')}</span>
        {/* The break between the two halves of the headline is part of the
            composition, so it stays a real <br> in both languages. */}
        <h1 ref={headingRef} tabIndex={-1}>{t('about.titleLead')}<br />{t('about.titleTail')}</h1>
        <p>{t('about.intro')}</p>
      </div>
      <AboutFigure />
    </div>

    <section className="ff-about-author" aria-labelledby="ff-about-author-title" data-ff-section={t('about.sectionPerson')}>
      <h2 id="ff-about-author-title" tabIndex={-1}>{t('about.authorTitle')}</h2>
      <p>{t('about.authorP1')}</p>
      <p>{t('about.authorP2')}</p>
    </section>

    <div className="ff-about-work" data-ff-section={t('about.sectionPlimsoll')}>
      <span>{t('about.workLabel')}</span>
      <h2 tabIndex={-1}>{t('about.workTitle')}</h2>
      <p>{t('about.workText')}</p>
      <a href={publicHref('project')}>{t('about.viewProject')} <span aria-hidden="true">↗</span></a>
    </div>

    {/* The three quantities the tool reasons in, each a section of the page. */}
    <ScaleStudy />
    <FrictionStudy />
    <PowerStudy />

    <section className="ff-about-built" aria-labelledby="ff-about-built-title" data-ff-section={t('about.sectionBuilt')}>
      <h2 id="ff-about-built-title" tabIndex={-1}>{t('about.builtTitle')}</h2>
      <dl className="ff-about-rows">
        {BUILT_WITH.map(key => <div className="ff-about-row" key={key}>
          {/* A row whose label is a stack of product names stays Latin in both
              languages; the body beside it is prose and is translated. */}
          <dt lang={BUILT_WITH_NAMES.has(key) ? 'en' : undefined}>{t(`${key}.label`)}</dt><dd>{t(`${key}.text`)}</dd>
        </div>)}
      </dl>
    </section>

    <Contact />
  </article>;
}
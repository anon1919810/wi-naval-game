import type { MouseEventHandler, RefObject } from 'react';
import { Artwork } from './Artwork';
import { useLanguage, type TranslationKey } from './LanguageProvider';
import { APP_ENTRY_LINK, publicHref } from './routes';
import { TitleEntry } from './TitleEntry';
import type { PlanSheet } from './plans';

/** Five numbered sections, in the page's own order. */
const SECTIONS: readonly { readonly index: string; readonly title: TranslationKey; readonly body: readonly string[] }[] = [
  { index: '01', title: 'detail.overview', body: ['detail.overview.0', 'detail.overview.1', 'detail.overview.2'] },
  { index: '02', title: 'detail.capabilities', body: ['detail.capabilities.0', 'detail.capabilities.1', 'detail.capabilities.2', 'detail.capabilities.3', 'detail.capabilities.4', 'detail.capabilities.5', 'detail.capabilities.6', 'detail.capabilities.7'] },
  { index: '03', title: 'detail.workflow', body: ['detail.workflow.0', 'detail.workflow.1', 'detail.workflow.2', 'detail.workflow.3', 'detail.workflow.4'] },
  { index: '04', title: 'detail.technology', body: ['detail.technology.0', 'detail.technology.1', 'detail.technology.2', 'detail.technology.3', 'detail.technology.4', 'detail.technology.5'] },
  { index: '05', title: 'detail.limits', body: ['detail.limits.0', 'detail.limits.1', 'detail.limits.2', 'detail.limits.3', 'detail.limits.4', 'detail.limits.5', 'detail.limits.6'] },
];

/**
 * The rows whose label is a stack of product names rather than prose.
 *
 * `React · TypeScript · Vite`, `FastAPI · SQLAlchemy · Alembic` and `PostgreSQL`
 * are the names of things, so they read the same in either language and are
 * marked as Latin text. The body beside each one is prose and is translated —
 * including the honest parts, which are the point of this page.
 */
const STACK_LABELS = new Set(['React · TypeScript · Vite', 'FastAPI · SQLAlchemy · Alembic', 'PostgreSQL']);

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
 * no invented statistics, credentials or project repositories — and the Chinese
 * edition claims exactly the same things, including every limit. Nothing is
 * certified here in either language: no naval, armour or blast physics is claimed
 * as verified, and the equations, sources and disclaimers are identical on both.
 *
 * The title is the way into the tool, not a heading with a button under it, and
 * there is no second entry here: this page is already the detail, so it has no
 * project link to offer and one less thing to say the same thing twice.
 */
export function ProjectDetail({ sheet, dark, details, pageRef, headingRef, ctaRef, prefetchApp, onEnterTool }: Props) {
  const { t } = useLanguage();
  return <article className="ff-detail" aria-label={t('detail.label')} ref={pageRef}>
    <a className="ff-detail-back" href={publicHref('home')}>{t('detail.back')} <span aria-hidden="true">↖</span></a>
    <span className="ff-eyebrow">{t('detail.eyebrow')}</span>
    <TitleEntry
      headingRef={headingRef}
      linkRef={ctaRef}
      parts={['Pl', 'i', 'msoll']}
      dot={1}
      name={t('detail.openTool')}
      href={APP_ENTRY_LINK}
      prefetch={prefetchApp}
      onEnter={onEnterTool} />
    <p className="ff-detail-lede">{t('detail.lede')}</p>

    <div className="ff-detail-hero">
      <div className="ff-art-scene"><Artwork sheet={sheet} dark={dark} details={details} /></div>
      <span className="ff-corner ff-corner-tl" /><span className="ff-corner ff-corner-tr" /><span className="ff-corner ff-corner-bl" /><span className="ff-corner ff-corner-br" />
      {/* The sheet's own number is a reference mark, not a sentence. */}
      <span className="ff-detail-hero-note">{t('detail.heroNote', { id: sheet.id })}</span>
    </div>

    <div className="ff-detail-body">
      {SECTIONS.map(section => <section key={section.index} className="ff-detail-section" aria-labelledby={`ff-detail-${section.index}`} data-ff-section={t(section.title)}>
        <h2 id={`ff-detail-${section.index}`} tabIndex={-1}><span>{section.index}</span>{t(section.title)}</h2>
        <dl className="ff-detail-rows">
          {section.body.map(row => {
            const label = t(`${row}.label` as TranslationKey);
            return <div className="ff-detail-row" key={row}>
              <dt lang={STACK_LABELS.has(label) ? 'en' : undefined}>{label}</dt><dd>{t(`${row}.text` as TranslationKey)}</dd>
            </div>;
          })}
        </dl>
      </section>)}
    </div>
  </article>;
}
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';
import {
  measureSections,
  RULER_MINOR_MARKS,
  rulerStops,
  sectionLabel,
  sectionNodes,
  sectionScrollTop,
  type Reading,
  type ReadingSection,
  type RulerStop,
} from './readingScroll';
import { prefersReducedMotion } from './transitions';
import './readingRuler.css';

/**
 * The reading ruler: where a long page is, and how to get to any of it.
 *
 * It is a labelled secondary navigation in its own right, a *sibling* of the
 * main navigation rather than a child of it — nesting one landmark inside
 * another is what makes a screen reader's landmark list lie about this page — and
 * it is mounted only on the two views that are actually long. Work's own exhibit
 * is one screenful and has nothing to measure.
 *
 * Everything it shows is measured rather than assumed:
 *
 * - The major marks are the sections' own top edges, so a mark is at the section
 *   rather than at a guess of it, and the minor marks divide the gaps, which is
 *   what makes a long gap between two short sections read as distance.
 * - The current mark is the section the reading controller reports, and it is the
 *   only blue thing on the track. Hovering or focusing *another* mark turns it
 *   red; the current one stays blue, because where you are and where you are
 *   about to go are two different answers.
 * - Activating a mark is a native scroll — smooth, and instant under reduced
 *   motion — followed by focus on that section's own heading. No hash is written,
 *   so using the ruler can never raise a route or a transition.
 */

interface Props {
  /** The page whose sections the ruler reads. Its own node, so nothing else is queried. */
  pageRef: RefObject<HTMLElement | null>;
  /** The shared reading controller: it owns the current section and the voice. */
  reading: RefObject<Reading | null>;
  current: number;
}

export function ReadingRuler({ pageRef, reading, current }: Props) {
  const [sections, setSections] = useState<readonly ReadingSection[]>([]);
  const [stops, setStops] = useState<readonly RulerStop[]>([]);
  const [hover, setHover] = useState<number | null>(null);
  const nodes = useRef<HTMLElement[]>([]);

  /**
   * One measurement pass: the sections the page declares, and the track they
   * imply. Read on mount, on resize, and whenever the page's own content
   * changes size, rather than on every scroll frame.
   */
  const measure = useCallback(() => {
    const page = pageRef.current;
    if (!page) return;
    nodes.current = sectionNodes(page);
    const declared = nodes.current.map((node, index) => ({ id: node.id || `ff-section-${index}`, label: node.dataset.ffSection ?? '' }))
      .filter(section => section.label.length > 0);
    const tops = measureSections(nodes.current, window.scrollY);
    const span = Math.max(1, (tops.at(-1) ?? 0) - (tops[0] ?? 0));
    setSections(declared);
    setStops(rulerStops(tops, span, RULER_MINOR_MARKS));
    // The current section is recomputed from the geometry we just measured, so a
    // resize cannot leave the track claiming a section the reader is not in.
    reading.current?.refresh();
  }, [pageRef, reading]);

  useEffect(() => {
    let active = true;
    measure();
    window.addEventListener('resize', measure);
    void (document as Document & { fonts?: { ready?: Promise<unknown> } }).fonts?.ready?.then(() => { if (active) measure(); }, () => {});
    // The page grows and shrinks as images decode and sections are revealed, so
    // its own box is watched rather than assumed.
    const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(measure) : null;
    if (pageRef.current) observer?.observe(pageRef.current);
    return () => { active = false; observer?.disconnect(); window.removeEventListener('resize', measure); };
  }, [measure, pageRef]);

  /** Scroll to a section and hand its heading the keyboard. */
  const go = useCallback((index: number) => {
    const node = nodes.current[index];
    if (!node) return;
    // A press is a gesture, so the section's own voice is owed this time.
    reading.current?.arm();
    window.scrollTo({ top: sectionScrollTop(node.getBoundingClientRect().top + window.scrollY), behavior: prefersReducedMotion() ? 'auto' : 'smooth' });
    node.querySelector<HTMLElement>('h1, h2')?.focus({ preventScroll: true });
  }, [reading]);

  if (!sections.length) return null;

  return <div className="ff-ruler" role="navigation" aria-label="Reading position" data-ff-ruler={current}>
    <p className="ff-ruler-label">{current >= 0 && sections[current] ? sectionLabel(current, sections[current].label) : 'READING'}</p>
    <div className="ff-ruler-track">
      <span className="ff-ruler-line" aria-hidden="true" />
      {stops.map((stop, position) => {
        const key = `${stop.index}-${stop.major ? 'major' : position}`;
        if (!stop.major) return <span key={key} className="ff-ruler-tick ff-ruler-tick--minor" style={{ top: `${stop.at * 100}%` }} aria-hidden="true" />;
        const index = stop.index;
        const active = index === current;
        const preview = index === hover;
        return <button
          key={key}
          type="button"
          className="ff-ruler-mark"
          data-ff-ruler-mark={active ? 'current' : preview ? 'preview' : 'rest'}
          style={{ top: `${stop.at * 100}%` }}
          aria-current={active ? 'true' : undefined}
          title={sectionLabel(index, sections[index]?.label ?? '')}
          onPointerEnter={() => setHover(index)}
          onPointerLeave={() => setHover(null)}
          onFocus={() => setHover(index)}
          onBlur={() => setHover(null)}
          onClick={() => go(index)}>
          <span className="ff-ruler-tick" aria-hidden="true" />
          <span className="ff-ruler-name">{sectionLabel(index, sections[index]?.label ?? '')}</span>
        </button>;
      })}
    </div>
  </div>;
}

import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEventHandler, type PointerEvent, type RefObject } from 'react';
import { entryPoint, revealRadius, wordCentre, type NavBox, type NavPoint } from './navPreview';
import { onTransitionEnd, transitionGeneration } from './transitions';
import './titleEntry.css';

/**
 * The one way into the tool, and — on Work — the way into the detail beside it.
 *
 * The heading stays a real heading and holds the real link. Nothing here is a
 * button that behaves like a link, and nothing here is a second copy of the tool
 * entry: the H1 *is* the entry, spelled the way it always was, and named
 * `Open Plimsoll` so a reader who cannot see the word is told what it opens.
 *
 * The heading keeps the name `Plimsoll` for the same reason: the action beside it
 * is a second link, and folding it into the heading would make the page's own
 * title read as "Plimsoll VIEW PROJECT". The action is therefore a *sibling* of
 * the heading, inside the one region that owns the hover and the focus.
 *
 * Four rules the shape of the answer depends on, and all four are the rail's own
 * rather than new ones:
 *
 * - **The circle opens where the pointer went in.** A reversal with the circle
 *   still open keeps the origin it already had and only aims the radius back, so
 *   it picks up from wherever it had reached. A keyboard has no entry point, so it
 *   opens from the middle of the word.
 * - **One rule, not two.** A single underline scales from the word's first glyph
 *   to the whole word while its colour goes ink to accent, in the same 300 ms as
 *   the circle.
 * - **The `i` dot is the only red.** The dot is isolated by a plain inline
 *   element, so the word's shaping, weight and spacing are the font's own, and
 *   only the band above the x-height is painted — the stem stays whatever colour
 *   is behind it.
 * - **The two links share one region.** Pointer and keyboard entry open it, the
 *   gap between the words is inside it, and leaving closes it after a short delay
 *   rather than instantly, so crossing to the action cannot drop the title's own
 *   preview. Focus alone reveals the action so Tab can reach it; while hidden it
 *   is genuinely hidden, so it is not an invisible tab stop and cannot swallow a
 *   press meant for the title.
 */

interface Secondary {
  readonly href: string;
  readonly label: string;
}

interface Props {
  /** The H1. Kept a heading, with the tool link inside it. */
  headingRef: RefObject<HTMLHeadingElement | null>;
  /** The tool link. Coming back from the workspace focuses this. */
  linkRef: RefObject<HTMLAnchorElement | null>;
  /** The word, split so the lower-case `i` can be isolated without reshaping it. */
  parts: readonly string[];
  /** Which part carries the red dot, or -1 for a word that has none. */
  dot: number;
  /** What the link opens, for a reader who cannot see the word. */
  name: string;
  href: string;
  /** Work only: the adjacent, secondary way into the detail. */
  secondary?: Secondary;
  /** Warms the workspace chunk. The navigation itself is left to the anchor. */
  prefetch: () => void;
  /** Retires the opening before the browser follows the link. */
  onEnter: MouseEventHandler<HTMLAnchorElement>;
}

/** How long the region stays open after the pointer has left all of it. */
const REGION_CLOSE_MS = 140;
/** A pointer that is not a mouse is a press, and a press is not a preview. */
const isMouse = (event: { pointerType?: string }) => event.pointerType === 'mouse';
/** Only a plain primary press is ours; the rest belong to the browser. */
const isOwnPress = (event: { button: number; metaKey: boolean; ctrlKey: boolean; shiftKey: boolean; altKey: boolean }) =>
  event.button === 0 && !event.metaKey && !event.ctrlKey && !event.shiftKey && !event.altKey;

const box = (node: HTMLElement | null): NavBox => {
  const rect = node?.getBoundingClientRect();
  return rect ? { left: rect.left, top: rect.top, width: rect.width, height: rect.height } : { left: 0, top: 0, width: 0, height: 0 };
};

/**
 * The real width of a word's first glyph.
 *
 * The glyph is never wrapped in its own box to measure it: that would change how
 * it pairs with the letter after it. A range over the first *text node* inside the
 * word measures it exactly as painted, kerning and side bearings included, which
 * is what keeps the rule sitting on the first letter at rest.
 */
function firstGlyphWidth(word: HTMLElement): number {
  const ink = word.querySelector('.ff-title-ink') ?? word;
  const walker = document.createTreeWalker(ink, NodeFilter.SHOW_TEXT);
  const text = walker.nextNode();
  if (!text || !text.nodeValue?.length) return 0;
  const range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 1);
  return typeof range.getBoundingClientRect === 'function' ? range.getBoundingClientRect().width : 0;
}

function TitleWord({ parts, dot, wordRef }: { parts: readonly string[] | string; dot: number; wordRef: RefObject<HTMLSpanElement | null> }) {
  const glyphs = (typeof parts === 'string' ? [parts] : parts).map((part, index) => index === dot
    ? <span className="ff-title-i" key={index}>{part}</span>
    : <span key={index}>{part}</span>);
  return <span className="ff-title-word" ref={wordRef}>
    <span className="ff-title-ink">{glyphs}</span>
    <span className="ff-title-dup" aria-hidden="true">{glyphs}</span>
    <span className="ff-title-rule" aria-hidden="true" />
  </span>;
}

export function TitleEntry({ headingRef, linkRef, parts, dot, name, href, secondary, prefetch, onEnter }: Props) {
  const [open, setOpen] = useState(false);
  const [overAction, setOverAction] = useState(false);
  const [focusAction, setFocusAction] = useState(false);
  /** A destination that was pressed and whose move is still running. */
  const [held, setHeld] = useState(false);
  const title = useRef<HTMLSpanElement>(null);
  const action = useRef<HTMLSpanElement>(null);
  const origins = useRef(new Map<HTMLElement, NavPoint>());
  const closing = useRef(0);
  const region = useRef<HTMLSpanElement>(null);
  const pointerInside = useRef(false);
  /**
   * The controller's generation at the moment of the press, and zero when no
   * transition was running.
   *
   * Starting a move bumps that generation, so "the first move to end after my
   * press" is exactly `generation > pressedDuring`. A cut already in flight when
   * the visitor pressed carries a lower generation and cannot end the hold, which
   * is the case a guess at the current value would get wrong.
   */
  const pressedDuring = useRef(0);

  const titleActive = open || held;
  const actionActive = (overAction || focusAction) && !held;

  const clearClose = useCallback(() => {
    if (closing.current) { window.clearTimeout(closing.current); closing.current = 0; }
  }, []);
  const closeLater = useCallback(() => {
    clearClose();
    closing.current = window.setTimeout(() => {
      closing.current = 0;
      if (!pointerInside.current && !region.current?.contains(document.activeElement)) setOpen(false);
    }, REGION_CLOSE_MS);
  }, [clearClose]);
  const reveal = useCallback(() => { clearClose(); setOpen(true); }, [clearClose]);
  useEffect(() => clearClose, [clearClose]);

  /**
   * Install an origin for a word whose circle is still closed.
   *
   * The duplicate's transition is off for exactly this step, the origin is
   * written and the radius left closed, and the box is read back so the browser
   * acts on it now. A reversal with the circle still open keeps what it has:
   * snapping to a new target here is what would make it jump.
   */
  const aim = useCallback((word: HTMLElement | null, point: NavPoint) => {
    const layer = word?.querySelector<HTMLElement>('.ff-title-dup');
    if (!word || !layer) return;
    const radius = Number.parseFloat(getComputedStyle(layer).clipPath?.match(/^circle\(\s*([\d.]+)/)?.[1] ?? '0');
    if (radius > 0.1) return;
    origins.current.set(word, point);
    word.style.setProperty('--ff-title-x', `${point.x}px`);
    word.style.setProperty('--ff-title-y', `${point.y}px`);
    layer.setAttribute('data-ff-title-armed', 'true');
    void getComputedStyle(layer).clipPath;
  }, []);

  /** The numbers each word needs, measured before every paint. */
  const paint = useCallback(() => {
    for (const [node, active] of [[title.current, titleActive], [action.current, actionActive]] as const) {
      if (!node) continue;
      const rect = node.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) continue;
      const origin = origins.current.get(node) ?? wordCentre(rect);
      origins.current.set(node, origin);
      node.querySelector('.ff-title-dup')?.removeAttribute('data-ff-title-armed');
      node.style.setProperty('--ff-title-radius', active ? `${revealRadius(rect, origin)}px` : '0px');
      // A glyph that cannot be measured falls back to the whole word.
      const glyph = firstGlyphWidth(node);
      node.style.setProperty('--ff-title-rule', String(active || glyph <= 0 ? 1 : Math.min(1, glyph / rect.width)));
    }
  }, [actionActive, titleActive]);
  useLayoutEffect(paint);

  useEffect(() => {
    let active = true;
    const update = () => { if (active) paint(); };
    window.addEventListener('resize', update);
    void (document as Document & { fonts?: { ready?: Promise<unknown> } }).fonts?.ready?.then(update, () => {});
    return () => { active = false; window.removeEventListener('resize', update); };
  }, [paint]);

  // The hold lasts for the move it asked for and ends with it — finished, skipped
  // or superseded.
  useEffect(() => {
    if (!held) return;
    return onTransitionEnd(({ generation }) => { if (generation > pressedDuring.current) setHeld(false); });
  }, [held]);

  // The address is the other truth. A Back, a Forward or a second navigation to
  // somewhere else abandons the request at once rather than leaving the word
  // accent for a page nobody asked for. A navigation *to* the tool keeps its own
  // hold, because that move is the one it belongs to.
  useEffect(() => {
    if (!held) return;
    const check = () => { if (window.location.hash !== href) setHeld(false); };
    window.addEventListener('hashchange', check);
    return () => window.removeEventListener('hashchange', check);
  }, [held, href]);

  return <span
    className="ff-title-region"
    ref={region}
    data-ff-title-region={open ? 'open' : 'closed'}
    onPointerEnter={(event: PointerEvent<HTMLSpanElement>) => {
      pointerInside.current = isMouse(event);
      reveal();
      if (isMouse(event)) aim(title.current, entryPoint(box(title.current), event.clientX, event.clientY));
    }}
    onPointerLeave={(event: PointerEvent<HTMLSpanElement>) => {
      if (isMouse(event)) { pointerInside.current = false; closeLater(); }
    }}
    onFocusCapture={() => reveal()}
    onBlurCapture={event => { if (!event.currentTarget.contains(event.relatedTarget as Node | null)) closeLater(); }}>
    <h1 className="ff-title" ref={headingRef} tabIndex={-1} aria-label={parts.join('')}>
      <a
        className="ff-title-link"
        data-ff-title-active={titleActive ? 'true' : undefined}
        data-ff-title-held={held ? 'true' : undefined}
        href={href}
        aria-label={name}
        onClick={event => {
          // A modified or middle press opens a tab or a window. This tab's state
          // must not follow it there, so nothing is held.
          if (event.defaultPrevented || !isOwnPress(event)) return;
          pressedDuring.current = transitionGeneration();
          setHeld(true);
          onEnter(event);
        }}
        onPointerEnter={prefetch}
        onFocus={event => {
          prefetch();
          // A key has no entry point: the middle of the word is the fair one.
          aim(title.current, wordCentre(box(title.current)));
          void event;
        }}
        ref={linkRef}>
        <TitleWord parts={parts} dot={dot} wordRef={title} />
        <span className="ff-title-arrow" aria-hidden="true">↗</span>
      </a>
    </h1>
    {secondary && <a
      className="ff-title-action"
      data-ff-title-action={actionActive ? 'preview' : 'rest'}
      href={secondary.href}
      style={{ visibility: open ? 'visible' : 'hidden' }}
      onPointerEnter={(event: PointerEvent<HTMLAnchorElement>) => {
        reveal();
        if (!isMouse(event)) return;
        setOverAction(true);
        aim(action.current, entryPoint(box(action.current), event.clientX, event.clientY));
      }}
      onPointerLeave={(event: PointerEvent<HTMLAnchorElement>) => { if (isMouse(event)) setOverAction(false); }}
      onFocus={() => { reveal(); setFocusAction(true); aim(action.current, wordCentre(box(action.current))); }}
      onBlur={() => setFocusAction(false)}>
      <TitleWord parts={secondary.label} dot={-1} wordRef={action} />
      <span className="ff-title-arrow" aria-hidden="true">↗</span>
    </a>}
  </span>;
}

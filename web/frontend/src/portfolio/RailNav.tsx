import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent } from 'react';
import { classifyHash, publicHref, type PublicView } from './routes';
import { entryPoint, previewTarget, railView, revealRadius, wordCentre, type NavPoint, type RailView } from './navPreview';
import { onTransitionEnd, transitionGeneration } from './transitions';
import type { PreviewSound } from './previewAudio';

/**
 * The rail: Work and About, and nothing else.
 *
 * Both entries are ordinary anchors with real hashes, in the tab order, doing the
 * browser's own navigation — nothing here intercepts a press. What this component
 * adds is the answer *before* the press: pointing at a destination, or tabbing to
 * it, paints that word blue behind a circle that opens from where the pointer
 * entered it, and takes the underline back off the word that is actually on
 * screen. Leaving restores the truthful route, so a preview never lies about
 * where the visitor is.
 *
 * Three things are deliberate here:
 *
 * - **The ink never changes colour.** Blue belongs to one element — the duplicate
 *   word — and it is only ever blue where the circle has reached. That is what
 *   makes the reveal a reveal rather than a cross-fade, and it is why a word that
 *   is not selected is genuinely ink again once the circle has closed over.
 * - **The reveal's centre never travels.** A new origin is installed while the
 *   circle is still closed and its transition is switched off for that one step,
 *   so the radius alone grows from where the pointer actually entered. A reversal
 *   with the circle still open keeps the origin it already had and simply aims the
 *   radius back the other way, which is what lets it pick up from wherever it had
 *   reached instead of starting again.
 * - **One underline, not two.** A single rule under the word scales from the real
 *   width of its first glyph to the whole word, and its colour goes ink to blue in
 *   the same move, so the rule shortens onto the first glyph rather than
 *   disappearing and another one taking its place.
 *
 * The blue duplicate is hidden from assistive technology and never a pointer
 * target, and the link names itself outright, so the rail keeps exactly one
 * accessible name no matter how the word is split up for the reveal.
 */

interface Entry {
  readonly view: RailView;
  readonly label: string;
  /** One work exists, so Work carries the truthful count. */
  readonly badge?: string;
}

const ENTRIES: readonly Entry[] = [
  { view: 'home', label: 'Work', badge: '01' },
  { view: 'about', label: 'About' },
];

interface Props {
  /** The route React has committed. Work owns the detail as well as the exhibit. */
  current: PublicView;
  sound: PreviewSound;
  /**
   * A press on the page that is already on screen. It raises no new address, so
   * it would otherwise raise no new route either — and any transition still
   * travelling away from this page is now obsolete.
   */
  onCurrentPagePress: () => void;
  /** The splash owns the screen while it is open. */
  inert?: boolean;
}

/**
 * The real width of the word's first glyph, measured on the plain text itself.
 *
 * The word is not split into a first glyph and a remainder: an inline-block around
 * the first letter changes how the letter pairs with the one after it, and it
 * breaks the word apart for anything reading the link. A range over the first
 * character of the text node measures the glyph exactly as it is painted, with
 * its real kerning and side bearings.
 */
function firstGlyphWidth(word: HTMLElement): number {
  const text = word.firstChild;
  if (!text || text.nodeType !== Node.TEXT_NODE) return 0;
  const range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 1);
  return typeof range.getBoundingClientRect === 'function' ? range.getBoundingClientRect().width : 0;
}

export function RailNav({ current, sound, onCurrentPagePress, inert }: Props) {
  const [hover, setHover] = useState<RailView | null>(null);
  const [focus, setFocus] = useState<RailView | null>(null);
  /** A destination that has been pressed and whose move is still running. */
  const [held, setHeld] = useState<RailView | null>(null);
  const here = railView(current);
  const target = previewTarget(here, hover, focus, held);
  const preview = hover ?? focus;
  const words = useRef(new Map<RailView, HTMLElement>());
  const origins = useRef(new Map<RailView, NavPoint>());
  const binders = useRef(new Map<RailView, (node: HTMLElement | null) => void>());
  const initialized = useRef(new Set<RailView>());
  const tapped = useRef<RailView | null>(null);
  /** The controller's generation at the moment a destination was requested. */
  const heldFrom = useRef(0);
  /**
   * Whether the last thing the visitor did in the rail was a key. Focus that came
   * from a pointer is not an intention to inspect a destination, so it must not
   * leave a word selected after the pointer has gone.
   */
  const keyed = useRef(true);

  useEffect(() => {
    const keyboard = () => { keyed.current = true; };
    const pointer = () => { keyed.current = false; };
    window.addEventListener('keydown', keyboard, true);
    window.addEventListener('pointerdown', pointer, true);
    return () => {
      window.removeEventListener('keydown', keyboard, true);
      window.removeEventListener('pointerdown', pointer, true);
    };
  }, []);

  /** A stable ref callback per entry, so no node is detached and re-attached. */
  const bind = useCallback((view: RailView) => {
    let binder = binders.current.get(view);
    if (!binder) {
      binder = (node: HTMLElement | null) => { if (node) words.current.set(view, node); else words.current.delete(view); };
      binders.current.set(view, binder);
    }
    return binder;
  }, []);

  /**
   * Install a new origin for a word that is not on screen yet.
   *
   * The duplicate's transition is switched off for exactly this step, the origin
   * is written and the radius left closed, and the box is read back to make the
   * browser act on it now. The radius is then free to grow from this origin alone,
   * instead of the circle sliding over from wherever the last origin was.
   */
  const aim = useCallback((view: RailView, origin: NavPoint) => {
    const word = words.current.get(view);
    if (!word) return;
    const layer = word.querySelector<HTMLElement>('.ff-rail-dup');
    if (!layer) return;
    // Re-entering an unfinished reveal keeps its painted radius and origin.
    // Disabling its transition here would snap the radius to its target (zero).
    const radius = Number.parseFloat(getComputedStyle(layer).clipPath?.match(/^circle\(\s*([\d.]+)/)?.[1] ?? '0');
    if (radius > 0.1) return;
    origins.current.set(view, origin);
    word.style.setProperty('--ff-nav-x', `${origin.x}px`);
    word.style.setProperty('--ff-nav-y', `${origin.y}px`);
    layer.setAttribute('data-ff-nav-armed', 'true');
    void getComputedStyle(layer).clipPath;
  }, []);

  /**
   * The numbers the CSS needs: the circle's radius, aimed at or away from the far
   * corner, and the rule's scale — the word's real width when the word is
   * selected, its first glyph's real width when it is not.
   */
  const reveal = useCallback(() => {
    for (const [view, word] of [...words.current]) {
      if (!word.isConnected) { words.current.delete(view); continue; }
      const box = word.getBoundingClientRect();
      // An origin is only remembered from a box that had a size: measured against
      // nothing, the centre would be the top-left corner and the reveal would open
      // from the wrong place for the rest of the session.
      const origin = box.width > 0 && box.height > 0 ? (origins.current.get(view) ?? wordCentre(box)) : wordCentre(box);
      if (box.width > 0) origins.current.set(view, origin);
      // Armed origins are installed with the transition off; re-enabling it is
      // what lets the radius alone animate from the closed circle.
      const layer = word.querySelector<HTMLElement>('.ff-rail-dup');
      const fresh = !initialized.current.has(view);
      if (fresh) layer?.setAttribute('data-ff-nav-armed', 'true');
      else layer?.removeAttribute('data-ff-nav-armed');
      const selected = view === target;
      word.style.setProperty('--ff-nav-radius', selected ? `${revealRadius(box, origin)}px` : '0px');
      if (box.width > 0) {
        // A glyph that cannot be measured falls back to the whole word: an
        // understated rule is better than a missing one.
        const glyph = firstGlyphWidth(word.querySelector('.ff-rail-ink') ?? word);
        word.style.setProperty('--ff-nav-rule', String(selected || glyph <= 0 ? 1 : Math.min(1, glyph / box.width)));
      }
      if (fresh && layer) {
        void getComputedStyle(layer).clipPath;
        layer.removeAttribute('data-ff-nav-armed');
        initialized.current.add(view);
      }
    }
  }, [target]);

  // Measured before every paint, so the first frame already has the final radius
  // and a reversal never has a frame to snap in.
  useLayoutEffect(reveal);

  // Type can arrive after the first paint, and the word box moves with the
  // viewport: re-measure both, without ever moving an origin.
  useEffect(() => {
    let active = true;
    const update = () => { if (active) reveal(); };
    window.addEventListener('resize', update);
    const fonts = (document as Document & { fonts?: { ready?: Promise<unknown> } }).fonts;
    void fonts?.ready?.then(update, () => {});
    return () => { active = false; window.removeEventListener('resize', update); };
  }, [reveal]);

  // A requested destination is held for the whole move, not just to the arrival:
// the destination page is already on screen while its 260 ms entrance is still
// running, and a pointer that drifted back onto the outgoing word must not take
// the blue back for the rest of it. The hold ends when the controller's move
// ends — finished, cancelled or reached at once — and only for a move that
// *started* after the press, so a cut already in flight cannot end a hold it
// knows nothing about.
  useEffect(() => {
    if (held === null) return;
    return onTransitionEnd(({ generation }) => {
      if (generation > heldFrom.current) setHeld(null);
    });
  }, [held]);

  // The address is the other truth. A Back, a Forward or a second navigation that
  // lands somewhere else abandons the request at once, rather than leaving a word
  // blue for a page nobody asked for.
  useEffect(() => {
    if (held === null) return;
    const requested = held;
    const check = () => {
      const route = classifyHash(window.location.hash);
      if (route.kind !== 'public' || railView(route.view) !== requested) setHeld(value => value === requested ? null : value);
    };
    window.addEventListener('hashchange', check);
    return () => window.removeEventListener('hashchange', check);
  }, [held]);

  // One tap per real change of destination. Looking at the page already on screen,
  // or leaving, is not a change of destination.
  useEffect(() => {
    if (held !== null) return;
    if (preview === null || preview === here) { tapped.current = null; return; }
    if (tapped.current === preview) return;
    tapped.current = preview;
    sound.tap();
  }, [preview, here, held, sound]);

  const enter = (view: RailView) => (event: PointerEvent<HTMLAnchorElement>) => {
    // Only a mouse previews. A finger is going to press, and a pen is a press.
    if (event.pointerType !== 'mouse') return;
    const word = words.current.get(view);
    if (word) aim(view, entryPoint(word.getBoundingClientRect(), event.clientX, event.clientY));
    setHover(view);
  };
  const leave = (view: RailView) => () => { setHover(shown => shown === view ? null : shown); };
  const onFocus = (view: RailView) => () => {
    // A click's own focus is not an intention to inspect a destination, and it
    // must not be allowed to outlive the pointer that caused it. Genuine keyboard
    // focus previews, and opens the circle from the middle of the word, because a
    // key has no entry point.
    if (!keyed.current) return;
    const word = words.current.get(view);
    if (word) aim(view, wordCentre(word.getBoundingClientRect()));
    setFocus(view);
  };
  const onBlur = (view: RailView) => () => { setFocus(shown => shown === view ? null : shown); };
  const onClick = (view: RailView) => (event: MouseEvent<HTMLAnchorElement>) => {
    // A modified or non-primary press belongs to the browser: it opens a tab or a
    // window, and this tab's state must not follow it anywhere.
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    if (view === here) {
      // The address will not change, so no route will arrive either: drop
      // whatever is still travelling away from this page, and drop any hold with
      // it — this press asks for the page already on screen, not for the word
      // that was blue a moment ago.
      setHeld(null);
      onCurrentPagePress();
      return;
    }
    // Pressing the same destination again asks for nothing new: the hold already
    // belongs to the move that is running, so its generation must stand.
    if (held !== view) {
      heldFrom.current = transitionGeneration();
      setHeld(view);
    }
  };

  return (
    <nav
      className="ff-rail"
      aria-label="Main navigation"
      inert={inert}
      onPointerDown={() => { keyed.current = false; sound.unlock(); }}
      onKeyDown={() => { keyed.current = true; sound.unlock(); }}>
      {ENTRIES.map(entry => {
        const selected = entry.view === target;
        // Named outright, because the word is split across elements for the reveal
        // and a reader must never see "w ork" or a name that counts twice.
        const name = entry.badge ? `${entry.label} ${entry.badge}` : entry.label;
        return <a
          key={entry.view}
          className="ff-rail-link"
          data-ff-nav={selected ? 'selected' : 'rest'}
          data-ff-nav-held={held === entry.view ? 'true' : undefined}
          href={publicHref(entry.view)}
          aria-label={name}
          aria-current={entry.view === here ? 'page' : undefined}
          onPointerEnter={enter(entry.view)}
          onPointerLeave={leave(entry.view)}
          onFocus={onFocus(entry.view)}
          onBlur={onBlur(entry.view)}
          onClick={onClick(entry.view)}>
          {/* The word box is the frame for the reveal and for the rule. The badge
              is deliberately outside it, so the rule never crosses the count. The
              space is a real text node, and a flex container drops a
              whitespace-only child, so it costs no layout. */}
          <span className="ff-rail-word" ref={bind(entry.view)}>
            <span className="ff-rail-ink">{entry.label}</span>
            <span className="ff-rail-dup" aria-hidden="true">{entry.label}</span>
          </span>
          {entry.badge && <>{' '}<span className="ff-rail-badge">{entry.badge}</span></>}
        </a>;
      })}
    </nav>
  );
}

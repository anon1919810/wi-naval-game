import { useCallback, useEffect, useLayoutEffect, useRef, useState, type MouseEvent, type PointerEvent, type ReactNode } from 'react';
import { classifyHash, publicHref, type PublicView } from './routes';
import { destinationOrigin, entryPoint, previewTarget, railView, revealRadius, wordCentre, type NavPoint, type RailView } from './navPreview';
import { onTransitionEnd, transitionGeneration } from './transitions';
import type { PreviewSound, PreviewVoice } from './previewAudio';

/**
 * The rail: Work, About and Credits, and nothing else.
 *
 * Every entry is an ordinary anchor with a real hash, in the tab order, doing the
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
 * - **The count answers for its own destination.** Work's 01 badge crossfades to
 *   red while Work is being previewed, which is a signal about the move rather
 *   than about the page: `aria-current` never follows it, and About's preview
 *   leaves it blue.
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
  /**
   * The word split around an isolated `i`, which carries the red preview dot. The
   * glyphs stay plain text on both sides of it, so the first glyph of the word is
   * still a text node and the resting underline has something to measure — see
   * firstGlyphWidth below.
   */
  readonly parts?: readonly string[];
  /** Which voice this destination's preview answers with. */
  readonly voice: PreviewVoice;
}

const ENTRIES: readonly Entry[] = [
  { view: 'home', label: 'Work', badge: '01', voice: 'work' },
  { view: 'about', label: 'About', voice: 'about' },
  // A third destination, and no new voice: Credits answers with About's, because
  // both are the pages that are read rather than the exhibit that is explored, and
  // one quiet register for the reading destinations is the point.
  { view: 'credits', label: 'Credits', parts: ['Cred', 'i', 'ts'], voice: 'about' },
];

/**
 * A word's own glyphs, with the middle part isolated when the entry has one.
 *
 * The split is a plain inline element around a single letter, so the font shapes,
 * weights and spaces the word exactly as it would unstyled — and both copies of the
 * word are built from the same call, so the duplicate the circle opens onto is the
 * same word at the same width.
 */
function glyphs(entry: Entry): ReactNode {
  if (!entry.parts) return entry.label;
  return entry.parts.map((part, index) =>
    <span key={index} className={index === 1 ? 'ff-rail-i' : undefined}>{part}</span>);
}

/** The page reveal asks the rail where a destination's circle should open. */
export type DestinationOrigin = (view: RailView, centreOnly?: boolean) => NavPoint | null;

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
  /**
   * Where the page reveal reads a destination's circle origin from. The rail owns
   * every measurement of its own words, so it answers the question rather than
   * being asked to re-measure. `revealOrigins` is the name because the rail also
   * keeps its own per-word entry points, which is a different thing.
   */
  revealOrigins?: { current: DestinationOrigin | null };
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
 *
 * The first text node is walked to rather than assumed to be `word.firstChild`:
 * `credits` isolates its `i` in a span, so the leading `Cred` sits behind a
 * wrapper on its way in, and a range taken against an element measures the box
 * rather than the glyph.
 */
function firstGlyphWidth(word: HTMLElement): number {
  const ink = word.querySelector('.ff-rail-ink') ?? word;
  const text = document.createTreeWalker(ink, NodeFilter.SHOW_TEXT).nextNode();
  if (!text?.nodeValue?.length) return 0;
  const range = document.createRange();
  range.setStart(text, 0);
  range.setEnd(text, 1);
  return typeof range.getBoundingClientRect === 'function' ? range.getBoundingClientRect().width : 0;
}

export function RailNav({ current, sound, onCurrentPagePress, revealOrigins, inert }: Props) {
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
  /**
   * A press whose origin the page reveal has already read.
   *
   * The origin is a property of *that* press: a pointer's entry point describes
   * where the visitor went in, and it says nothing about where they went next.
   * So the reveal reads it once and spends it, and the next move for the same
   * destination — a Back an hour later, a second press — falls back to the middle
   * of the word rather than reopening from a place nobody chose this time.
   */
  const spent = useRef<RailView | null>(null);
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
// the destination page is already on screen while its 500 ms reveal is still
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

  // One touch per audible preview. Selected words and pointer leave stay quiet;
  // an accepted click receives Passage from the shared transition controller.
  const voiceOf = (view: RailView) => ENTRIES.find(entry => entry.view === view)!.voice;
  useEffect(() => {
    if (held !== null) return;
    if (preview === null || preview === here) { tapped.current = null; return; }
    if (tapped.current === preview) return;
    // A cold hover creates no context and queues no delayed preview.
    if (sound.tap(voiceOf(preview))) tapped.current = preview;
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
      // that was blue a moment ago. Nothing is tapped: this is not a destination.
      tapped.current = null;
      setHeld(null);
      onCurrentPagePress();
      return;
    }
    // The route controller supplies Passage for the accepted navigation. A
    // direct click does not add a touch ahead of it; hover remains a preview.
    // Pressing the same destination again asks for nothing new: the hold already
    // belongs to the move that is running, so its generation must stand.
    if (held !== view) {
      heldFrom.current = transitionGeneration();
      spent.current = null;
      setHeld(view);
    }
  };

  /**
   * The page reveal asks one question: where does this destination's circle open?
   *
   * The rail answers it from what it already knows, and answers from *this*
   * press: only a destination that is actually held continues its own preview
   * origin, so Back, Forward and a typed address get the middle of the word
   * rather than wherever a pointer was the last time someone happened to be
   * here. Measured at call time, not cached, so a word that has moved — or is not
   * on screen at all — simply has no answer and the caller falls back.
   */
  useEffect(() => {
    if (!revealOrigins) return;
    const read: DestinationOrigin = (view, centreOnly = false) => {
      const word = words.current.get(view);
      if (!word) return null;
      const box = word.getBoundingClientRect();
      // A centre-only read happens after route placement. An ordinary read only
      // consumes the entry point of a fresh press, so history cannot reuse it.
      if (centreOnly) {
        return destinationOrigin({ left: box.left, top: box.top, width: box.width, height: box.height }, false);
      }
      if (held !== view || spent.current === view) return null;
      // Reading it spends it. The reveal asks once per route change and commits
      // immediately, so the next move for this destination cannot reopen from a
      // place the visitor chose for the move before it. A new press arms it again.
      spent.current = view;
      return destinationOrigin({ left: box.left, top: box.top, width: box.width, height: box.height }, true, origins.current.get(view));
    };
    revealOrigins.current = read;
    return () => { if (revealOrigins.current === read) revealOrigins.current = null; };
  }, [revealOrigins, held]);

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
        // The badge answers for its own destination only. Work's count turns red
        // while Work itself is being previewed — Work's own pointer, Work's own
        // keyboard focus, or a Work press that is still travelling. About's
        // preview is about About and says nothing about Work's count, and the
        // page on screen never changes what is current.
        const previewing = entry.view === (held ?? hover ?? focus);
        return <a
          key={entry.view}
          className="ff-rail-link"
          data-ff-nav={selected ? 'selected' : 'rest'}
          data-ff-nav-held={held === entry.view ? 'true' : undefined}
          // Credits' own red dot, on the same terms as Work's badge: a preview of
          // this destination, or a press of it still travelling. The page on screen
          // is a different question — a selected Credits is blue, dot included.
          data-ff-dot={entry.parts ? (previewing ? 'preview' : 'idle') : undefined}
          data-ff-badge={entry.badge ? (previewing ? 'preview' : 'idle') : undefined}
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
              whitespace-only child, so it costs no layout. Both copies carry the
              same glyph markup, so the duplicate is the same word painted twice and
              the isolated `i` lines up exactly across the clip edge. */}
          <span className="ff-rail-word" ref={bind(entry.view)}>
            <span className="ff-rail-ink">{glyphs(entry)}</span>
            <span className="ff-rail-dup" aria-hidden="true">{glyphs(entry)}</span>
          </span>
          {entry.badge && <>{' '}<span className="ff-rail-badge">{entry.badge}</span></>}
        </a>;
      })}
    </nav>
  );
}

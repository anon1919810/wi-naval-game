import { useLayoutEffect, useRef, useState } from 'react';

/**
 * A one-shot reveal token for local motion.
 *
 * The animation is plain CSS, keyed on an attribute, so nothing here animates:
 * the hook only produces a value that changes when, and only when, the thing
 * being revealed changes. Two names are enough to make a browser restart a CSS
 * animation — a single fixed name would only run once, on mount.
 *
 * The container it is attached to is never re-keyed and never remounted. That is
 * the whole point: a chapter switch may animate the middle column, but the
 * textarea holding a hand-edited JSON document, the focused control and the
 * browser's own selection all have to survive it untouched. React commits one
 * attribute here, not a tree, and nothing is committed per frame.
 */

export type MotionToken = 'a' | 'b';

/**
 * `trigger` is the identity of the content, not its value: pass the chapter id,
 * or the traced field's key. Typing a new number into the same field leaves the
 * trigger unchanged, so an edit does not restart the reveal either.
 */
export function useMotionToken(trigger: string | null): MotionToken {
  const [token, setToken] = useState<MotionToken>('a');
  const previous = useRef(trigger);
  useLayoutEffect(() => {
    if (previous.current === trigger) return;
    previous.current = trigger;
    setToken(current => (current === 'a' ? 'b' : 'a'));
  }, [trigger]);
  return token;
}
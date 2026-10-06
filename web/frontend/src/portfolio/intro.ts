/**
 * The opening plays once per browser session, and only on request after that.
 *
 * `sessionStorage` is the right scope: the intro belongs to a visit, not to the
 * device, so a reload or a Back does not replay it and a new tab does. It is
 * also the one storage surface a browser can refuse outright, in private modes
 * and under strict settings — so both reads degrade: a refused read plays the
 * intro as though it had never been seen, and a refused write simply means the
 * next load may play it again. Neither path blocks the page, and the decoded
 * artwork, the skip control and the failure recovery around them are untouched.
 */

const KEY = 'formfield-intro-played';

export function introPlayed(): boolean {
  try { return window.sessionStorage?.getItem(KEY) === '1'; } catch { return false; }
}

export function markIntroPlayed(): void {
  try { window.sessionStorage?.setItem(KEY, '1'); } catch { /* Storage refused: the intro may play again. */ }
}
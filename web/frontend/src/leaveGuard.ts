/** Eagerly imported by Portfolio, before either shell registers route listeners. */
export interface LeaveGuardState { message: string; current: string }

const KEY = '__formfieldNavigation';
interface Position { session: string; index: number }
const initial = typeof window === 'undefined' ? null : readPosition(window.history.state);
const session = initial?.session ?? 'ff-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
let index = initial?.index ?? 0;
let ask: (() => LeaveGuardState | null) | null = null;
let approvedHash: string | null = null;
let restoring: { hash: string; index: number } | null = null;
const ignoredHashes = new Map<string, number>();

function readPosition(state: unknown): Position | null {
  if (!state || typeof state !== 'object') return null;
  const value = (state as Record<string, unknown>)[KEY] as Partial<Position> | undefined;
  return value && typeof value.session === 'string' && Number.isSafeInteger(value.index)
    ? value as Position : null;
}

function ownedPosition(): Position | null {
  const position = readPosition(window.history.state);
  return position?.session === session ? position : null;
}

function stateAt(next: number): Record<string, unknown> {
  const previous = window.history.state;
  return { ...(previous && typeof previous === 'object' ? previous : {}), [KEY]: { session, index: next } };
}

function stamp(next: number): void {
  window.history.replaceState(stateAt(next), '');
}

function approve(hash: string): boolean {
  const state = ask?.();
  if (!state || hash === state.current) return true;
  // Extra same-project fragments are view state, not a departure.
  const project = /^#\/?projects\/([^/]+)/.exec(state.current)?.[1];
  if (project && /^#\/?projects\/([^/]+)/.exec(hash)?.[1] === project) return true;
  return window.confirm(state.message);
}

export function setLeaveGuard(register: (() => LeaveGuardState | null) | null): void {
  ask = register;
  if (!register) approvedHash = null;
}

export function clearLeaveGuard(): void { ask = null; approvedHash = null; }

/** Buttons preflight before pushState; their owner commits the route itself. */
export function pushHash(hash: string): boolean {
  if (!hash || hash === window.location.hash || !approve(hash)) return false;
  index = ownedPosition()?.index ?? index;
  approvedHash = null;
  const next = index + 1;
  window.history.pushState(stateAt(next), '', hash);
  index = next;
  return true;
}

function ignoreHash(url: string): void {
  ignoredHashes.set(url, (ignoredHashes.get(url) ?? 0) + 1);
}

function takeIgnoredHash(event: HashChangeEvent): boolean {
  const url = event.newURL || window.location.href;
  const count = ignoredHashes.get(url) ?? 0;
  if (!count) return false;
  if (count === 1) ignoredHashes.delete(url); else ignoredHashes.set(url, count - 1);
  event.stopImmediatePropagation();
  return true;
}

function reject(event: Event, destination: number, fromPop: boolean): void {
  event.stopImmediatePropagation();
  const state = ask?.();
  if (!state) return;
  const source = index;
  // Preserve both entries. Replacing the refused entry would erase the next Back.
  if (fromPop) ignoreHash(window.location.href);
  const sourceUrl = new URL(state.current || '#', window.location.href).href;
  ignoreHash(sourceUrl);
  restoring = { hash: state.current, index: source };
  const delta = source - destination;
  // Finish the append's trailing event before restoration. Never issue go(0):
  // that reloads the page and discards the retained draft.
  if (delta) window.setTimeout(() => window.history.go(delta), 0);
}

/**
 * Native hash appends emit popstate too. They have no owned position yet;
 * traversals do. Only an actual traversal uses the recorded destination index.
 */
function onPopState(event: PopStateEvent): void {
  const hash = window.location.hash;
  const position = ownedPosition();
  if (restoring && hash === restoring.hash && position?.index === restoring.index) {
    index = restoring.index;
    restoring = null;
    event.stopImmediatePropagation();
    return;
  }
  const destination = position?.index ?? index + 1;
  const approved = approvedHash === hash;
  approvedHash = null;
  if (!approved && !approve(hash)) {
    // A refused native append can be reached again with Forward; record its
    // position before undoing it, without changing either entry's address.
    if (!position) stamp(destination);
    reject(event, destination, true);
    return;
  }
  if (!position) stamp(destination);
  index = destination;
}

/** Fallback for engines that emit only hashchange on a fragment append. */
function onHashChange(event: HashChangeEvent): void {
  if (takeIgnoredHash(event)) return;
  const position = ownedPosition();
  if (position) { index = position.index; return; }
  const hash = window.location.hash;
  const approved = approvedHash === hash;
  approvedHash = null;
  const destination = index + 1;
  if (!approved && !approve(hash)) { reject(event, destination, false); return; }
  stamp(destination);
  index = destination;
}

function onClick(event: MouseEvent): void {
  if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
  const anchor = (event.target as Element | null)?.closest?.('a[href]') as HTMLAnchorElement | null;
  if (!anchor || anchor.hasAttribute('download') || (anchor.target && anchor.target !== '_self')) return;
  const href = anchor.getAttribute('href') ?? '';
  if (!href.startsWith('#') || href === window.location.hash || !ask?.()) return;
  if (!approve(href)) { event.preventDefault(); return; }
  approvedHash = href;
}

function onBeforeUnload(event: BeforeUnloadEvent): void {
  if (!ask?.()) return;
  event.preventDefault();
  event.returnValue = '';
}

if (typeof window !== 'undefined') {
  stamp(index);
  window.addEventListener('click', onClick, true);
  window.addEventListener('popstate', onPopState);
  window.addEventListener('hashchange', onHashChange);
  window.addEventListener('beforeunload', onBeforeUnload);
}

/**
 * Hash classification for the public shell.
 *
 * The public portfolio owns the document root; the existing Plimsoll application
 * keeps its own hash behaviour and is only mounted when the hash names it. Every
 * legacy hash (`#/projects…`, `#/runs…`, `#/reports…`) must keep resolving to the
 * application so old links and bookmarks survive.
 */

export type PublicView = 'home' | 'about' | 'project';

export type PortfolioRoute = { kind: 'public'; view: PublicView } | { kind: 'app' };

export const PUBLIC_HOME_HASH = '/';
export const PUBLIC_WORK_HASH = '/work';
/** The one public work detail. Matched exactly, before any first-segment rule. */
export const PUBLIC_WORK_DETAIL_HASH = '/work/plimsoll';
export const PUBLIC_ABOUT_HASH = '/about';
export const APP_ENTRY_HASH = '/plimsoll';

/** Hash sections that belong to the existing Plimsoll application. */
export const APP_HASH_SECTIONS = ['plimsoll', 'projects', 'runs', 'reports'] as const;

/**
 * Public routes that name a specific view. `#/work` itself is a first segment, so
 * the detail has to be an exact whole-path match: it must never swallow a legacy
 * app hash, and an unrecognised sub-path of it must fall back to Work rather than
 * resolve to a detail that does not exist.
 */
const PUBLIC_EXACT_VIEWS: ReadonlyMap<string, PublicView> = new Map([
  [normalizeHash(PUBLIC_WORK_DETAIL_HASH), 'project'],
]);

export function normalizeHash(hash: string): string {
  return hash.replace(/^#/, '').replace(/^\/+/, '').replace(/\/+$/, '');
}

export function hashSection(hash: string): string {
  return normalizeHash(hash).split('/')[0] ?? '';
}

export function classifyHash(hash: string): PortfolioRoute {
  const path = normalizeHash(hash);
  const exact = PUBLIC_EXACT_VIEWS.get(path);
  if (exact) return { kind: 'public', view: exact };
  const section = path.split('/')[0] ?? '';
  if (section === 'about') return { kind: 'public', view: 'about' };
  if (section === '' || section === 'work' || section === 'home') return { kind: 'public', view: 'home' };
  if ((APP_HASH_SECTIONS as readonly string[]).includes(section)) return { kind: 'app' };
  // Unknown hashes belong to the public surface, which is now the document root.
  return { kind: 'public', view: 'home' };
}

export function isAppHash(hash: string): boolean {
  return classifyHash(hash).kind === 'app';
}

export function publicHref(view: PublicView): string {
  if (view === 'about') return `#${PUBLIC_ABOUT_HASH}`;
  if (view === 'project') return `#${PUBLIC_WORK_DETAIL_HASH}`;
  return `#${PUBLIC_WORK_HASH}`;
}

export const APP_ENTRY_LINK = `#${APP_ENTRY_HASH}`;
/** Where the home page's secondary "view project" entry points. */
export const WORK_DETAIL_LINK = `#${PUBLIC_WORK_DETAIL_HASH}`;

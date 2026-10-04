/**
 * Hash classification for the public shell.
 *
 * The public portfolio owns the document root; the existing Plimsoll application
 * keeps its own hash behaviour and is only mounted when the hash names it. Every
 * legacy hash (`#/projects…`, `#/runs…`, `#/reports…`) must keep resolving to the
 * application so old links and bookmarks survive.
 */

export type PublicView = 'home' | 'about';

export type PortfolioRoute = { kind: 'public'; view: PublicView } | { kind: 'app' };

export const PUBLIC_HOME_HASH = '/';
export const PUBLIC_WORK_HASH = '/work';
export const PUBLIC_ABOUT_HASH = '/about';
export const APP_ENTRY_HASH = '/plimsoll';

/** Hash sections that belong to the existing Plimsoll application. */
export const APP_HASH_SECTIONS = ['plimsoll', 'projects', 'runs', 'reports'] as const;

export function normalizeHash(hash: string): string {
  return hash.replace(/^#/, '').replace(/^\/+/, '').replace(/\/+$/, '');
}

export function hashSection(hash: string): string {
  return normalizeHash(hash).split('/')[0] ?? '';
}

export function classifyHash(hash: string): PortfolioRoute {
  const section = hashSection(hash);
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
  return `#${view === 'about' ? PUBLIC_ABOUT_HASH : PUBLIC_WORK_HASH}`;
}

export const APP_ENTRY_LINK = `#${APP_ENTRY_HASH}`;

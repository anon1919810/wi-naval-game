import { useWorkspaceCopy } from '../i18n/workspace';

/**
 * The structural reading diagram.
 *
 * It is explicitly not to scale and carries no numbers: the caption says so in
 * both languages, because a reader who took a measurement off it would be
 * wrong. That sentence is the whole reason this figure is safe to show, so it is
 * looked up rather than left as a literal.
 */
export function ShipProfile() {
  const w = useWorkspaceCopy();
  return <figure className="ship-profile"><svg viewBox="0 0 720 145" role="img" aria-label={w('shipProfile.label')}><path d="M22 76 L74 53 L150 49 L255 45 L395 48 L535 47 L646 55 L698 77 L685 104 Q365 129 71 104 Z"/><path d="M15 88 H706" className="profile-waterline"/><path d="M234 47 L255 13 L274 47 M520 47 L536 22 L552 48" className="profile-mast"/><rect x="342" y="22" width="18" height="27"/><rect x="389" y="18" width="22" height="30"/><rect x="447" y="22" width="19" height="26"/></svg><figcaption>{w('shipProfile.caption')}</figcaption></figure>;
}
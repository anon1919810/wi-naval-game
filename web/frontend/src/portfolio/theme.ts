/**
 * The public shell's own colour preference.
 *
 * There are exactly two: light and dark, both chosen here and remembered here.
 * The shell does not follow the operating system, because a portfolio that
 * re-themes itself under the reader is a portfolio that cannot show one page the
 * way it was designed. A `system` value left behind by an earlier build reads as
 * light, so an old preference resolves to something real instead of to a mode
 * that no longer exists. Nothing outside this shell reads this module.
 */
export type PortfolioTheme = 'light' | 'dark';
export const THEME_KEY = 'formfield-theme';

/** The stored preference, always one this shell can actually honour. */
export function storedTheme(): PortfolioTheme {
  try { return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'; }
  catch { return 'light'; }
}

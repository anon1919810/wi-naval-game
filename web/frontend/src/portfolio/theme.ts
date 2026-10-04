export type PortfolioTheme = 'light' | 'dark' | 'system';
export const THEME_KEY = 'formfield-theme';
export function storedTheme(): PortfolioTheme {
  try { const value = localStorage.getItem(THEME_KEY); return value === 'dark' || value === 'system' ? value : 'light'; }
  catch { return 'light'; }
}
export function resolveTheme(value: PortfolioTheme, systemDark: boolean): 'light' | 'dark' {
  return value === 'system' ? systemDark ? 'dark' : 'light' : value;
}

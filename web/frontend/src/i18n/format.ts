import { useMemo } from 'react';
import { useLanguage, type SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * Number and date formatting that follows the one language state.
 *
 * These are presentation only. A stored value, a fingerprint, an exported
 * payload and every JSON field keep their own canonical text; what changes here
 * is the grouping separator and the date order a reader sees on screen, which is
 * part of reading a number in one's own language rather than part of its value.
 *
 * `en` and `zh-CN` are passed explicitly rather than taken from the browser, so
 * the first visit is served the same locale as the words on screen — the same
 * rule the language preference itself follows.
 */
export function numberLocale(language: SiteLanguage): string {
  return language === 'zh-CN' ? 'zh-CN' : 'en';
}

/** A saved timestamp, in the reader's own date and time order. */
export function formatMoment(language: SiteLanguage, value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleString(numberLocale(language));
}

/** A saved date, without a time, for a list row. */
export function formatDate(language: SiteLanguage, value: string | null | undefined): string | null {
  if (!value) return null;
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed.toLocaleDateString(numberLocale(language));
}

/** The BCP 47 tag for the current language, for `Intl` and for `toLocale*`. */
export function useNumberLocale(): string {
  const { language } = useLanguage();
  return useMemo(() => numberLocale(language), [language]);
}

/** The current language's saved-timestamp formatter, or null when not recorded. */
export function useMomentText(): (value: string | null | undefined) => string | null {
  const { language } = useLanguage();
  return useMemo(() => (value: string | null | undefined) => formatMoment(language, value), [language]);
}

/** The current language's saved-date formatter, or null when not recorded. */
export function useDateText(): (value: string | null | undefined) => string | null {
  const { language } = useLanguage();
  return useMemo(() => (value: string | null | undefined) => formatDate(language, value), [language]);
}
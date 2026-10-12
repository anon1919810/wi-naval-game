import { useMemo } from 'react';
import { useLanguage, type CopyParams, type SiteLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';
import { labDictionary, type LabKey } from './lab';

/**
 * Numbers that belong to the laboratory, in the reader's language.
 *
 * These are presentation helpers over values the core already produced. None of
 * them computes anything, and none of them turns an absent value into a zero: an
 * unknown quantity prints as the word for unknown and nothing else, because a
 * fabricated digit here would read as a measurement that was never taken.
 *
 * The grouping separator follows the language and the digits do not, which is
 * presentation only: the frozen result payload, its request fingerprint and
 * every export keep their own canonical text.
 */
export interface LabFormat {
  /** A fixed-decimal number, or the unknown marker when there is no value. */
  numeric: (value: number | null | undefined, digits?: number) => string;
  /** A whole-number percentage, or the unknown marker. */
  percent: (value: number | null | undefined) => string;
  /** Yes / no, or the unknown marker. */
  yesNo: (value: boolean | null | undefined) => string;
  /** A saved trial status in this language; empty when there is no status. */
  status: (status: string | null | undefined) => string;
  locale: string;
}

/** The formatter for one language, for code that is not a component. */
export function labFormat(language: SiteLanguage): LabFormat {
  const dictionary = labDictionary(language);
  const t = (key: LabKey, params?: CopyParams) => interpolate(dictionary[key] ?? key, params);
  const locale = language === 'zh-CN' ? 'zh-CN' : 'en';
  return {
    locale,
    numeric: (value, digits = 1) => value == null || !Number.isFinite(value)
      ? t('value.unknown')
      : new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value),
    percent: value => value == null
      ? t('value.unknown')
      : `${new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(Math.round(value * 100))}%`,
    yesNo: value => value == null ? t('value.unknown') : value ? t('value.yes') : t('value.no'),
    status: status => (status ? t(`status.${status}` as LabKey) : ''),
  };
}

/** The laboratory formatter bound to the current language. */
export function useLabFormat(): LabFormat {
  const { language } = useLanguage();
  return useMemo(() => labFormat(language), [language]);
}
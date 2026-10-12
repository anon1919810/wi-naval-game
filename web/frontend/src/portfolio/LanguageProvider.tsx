import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react';
import { translate, type CopyParams, type SiteLanguage, type TranslationKey } from './language';

export type { CopyParams, SiteLanguage, TranslationKey } from './language';

/** What a public component needs from the shell's language state. */
export interface LanguageApi {
  readonly language: SiteLanguage;
  /** One message. `t('nav.work')` — typed against the English dictionary. */
  t: (key: TranslationKey, params?: CopyParams) => string;
  /** The only writer. A no-op where there is no provider. */
  setLanguage: (language: SiteLanguage) => void;
}

/**
 * English is the default everywhere below the provider.
 *
 * A component rendered on its own — a page in a test, `Contact` beside the
 * clipboard policy, `RailNav` beside the preview geometry — gets the English
 * strings it always printed, with no provider and no wrapper. That is what keeps
 * every existing English expectation true without rewriting it, and it is why
 * the default is a working lookup rather than a stub.
 *
 * The lookup takes the same parameters the real one does, so a component below
 * the provider and the same component standing alone interpolate identically:
 * a standalone `Contact` still resolves `{email}` in its “copied” message rather
 * than printing the placeholder.
 */
const LanguageContext = createContext<LanguageApi>({
  language: 'en',
  t: (key, params) => translate('en', key, params),
  setLanguage: () => {},
});

/** The shell's language, for the public pages and the chrome around them. */
export function useLanguage(): LanguageApi {
  return useContext(LanguageContext);
}

interface Props {
  language: SiteLanguage;
  /** The shell's own writer; the provider never stores anything itself. */
  onLanguage: (language: SiteLanguage) => void;
  children: ReactNode;
}

/**
 * The provider, mounted once around the whole shell.
 *
 * It is mounted above the public route, not inside it, which is the whole point:
 * a switch is a state change, not a navigation, so React reconciles the same
 * elements in place. The exhibit, the rail, the open sheet, the running
 * calculation, the muted-or-not speaker, the theme and the reader's scroll
 * position are all state that lives above this component, and none of it is
 * touched by a dictionary changing. Nothing here unmounts, and nothing here is
 * re-created per route — so going into the workspace and coming back finds the
 * language exactly as it was left.
 */
export function LanguageProvider({ language, onLanguage, children }: Props) {
  const t = useCallback(
    (key: TranslationKey, params?: CopyParams) => translate(language, key, params),
    [language],
  );
  // Stable while the language is, so the context value does not churn and the
  // children below it are not re-rendered by anything but their own state.
  const value = useMemo<LanguageApi>(() => ({ language, t, setLanguage: onLanguage }), [language, t, onLanguage]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}
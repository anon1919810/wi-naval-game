import type { ReactNode, ReactElement } from 'react';
import { render, type RenderOptions } from '@testing-library/react';
import { LanguageProvider } from '../portfolio/LanguageProvider';
import { workspaceCopy } from '../i18n/workspace';
import { shellCopy } from '../i18n/shell';
import { labCopy } from '../i18n/lab';
import type { WorkspaceKey } from '../i18n/workspace';
import type { SiteLanguage } from '../portfolio/LanguageProvider';

/**
 * Rendering under an explicit language, for the tests that check Chinese.
 *
 * English is the default everywhere below the provider and must stay the
 * default, so a suite that asserts the Chinese wording says so here instead of
 * relying on a global that would quietly make Chinese the default for everyone.
 * This helper only supplies the language; every behavioural assertion in those
 * suites stands exactly as it was.
 *
 * There are three forms because there are three kinds of copy in the app:
 *
 * - `zh(node)` renders a component under a Chinese provider.
 * - `zhCopy` / `zhShell` / `zhLab` are lookups for the pure functions that take
 *   their dictionary as a parameter, and for code that renders nothing.
 */

/** A Chinese workspace lookup, for the pure modules that take one. */
export const zhCopy = (key: WorkspaceKey, params?: Record<string, string | number>) =>
  workspaceCopy('zh-CN', key, params);

/** The shared chrome in Chinese. */
export const zhShell = (key: Parameters<typeof shellCopy>[1], params?: Record<string, string | number>) =>
  shellCopy('zh-CN', key, params);

/** The laboratory in Chinese. */
export const zhLab = (key: Parameters<typeof labCopy>[1], params?: Record<string, string | number>) =>
  labCopy('zh-CN', key, params);

/** The Chinese lookup for the component under test, with no wrapper needed. */
export function ChineseProvider({ children, language = 'zh-CN' as SiteLanguage }: {
  children: ReactNode; language?: SiteLanguage;
}) {
  // The provider's own writer is a no-op here: these suites change the language
  // by unmounting, never by pressing the switch, so nothing needs to persist.
  return <LanguageProvider language={language} onLanguage={() => {}}>{children}</LanguageProvider>;
}

/** The node wrapped in a Chinese provider, for `render(...)`. */
export const zh = (node: ReactNode) => <ChineseProvider>{node}</ChineseProvider>;

/** The node wrapped in a provider for any language, for `render(...)`. */
export const inLanguage = (node: ReactNode, language: SiteLanguage) =>
  <ChineseProvider language={language}>{node}</ChineseProvider>;

/** Legacy workspace tests explicitly select the language their assertions use. */
export const renderZh = (node: ReactElement, options?: Omit<RenderOptions, 'wrapper'>) =>
  render(node, { ...options, wrapper: ChineseProvider });

import { useCallback } from 'react';
import { useLanguage, type CopyParams, type SiteLanguage } from '../portfolio/LanguageProvider';
import { interpolate } from './terms';

/**
 * The shared chrome dictionary: the few sentences both surfaces must be able to
 * print, whichever route is on screen.
 *
 * This module exists because of a bundle boundary, not because these words are
 * more important than the others. The public shell is the eager entry chunk: it
 * imports `ReadPending`, `SoundToggle` and the failed-chunk boundary directly,
 * because a workspace chunk that fails to arrive still has to find its
 * placeholder and its recovery on screen. If those components read the
 * workspace dictionary, every editor, report and laboratory string is pulled
 * into the chunk the home page loads — which would make a static public page
 * ship the whole tool, and would break the route boundary the workspace and the
 * laboratory are lazy-loaded behind.
 *
 * So this is the whole of what the eager chunk is allowed to own: one reading
 * placeholder, one read failure, the chunk-failure panel, the workspace word the
 * placeholder names, and the sound control's three labels. Everything else —
 * every chapter, field, stage, report and laboratory word — lives in
 * `./workspace` and `./lab`, which are reached only through their route's own
 * dynamic import.
 *
 * English is the source and the two dictionaries are shape-checked against each
 * other, exactly as in `./workspace` and the public shell's own dictionary. The
 * values are identical where the same word appears in both modules, which is why
 * a reader moving between the public shell and the tool is not told two
 * different things about the same control.
 */
const EN = {
  /* ---- the reading placeholder and read failure, used by every route ------ */
  'read.status': 'Reading {object}',
  'read.waiting': 'Still waiting for {object}; more than 2 seconds so far.',
  'read.retry': 'Read again',
  'read.back': 'Back',

  /* ---- the object the eager shell's own fallback is waiting for ------------- */
  'shell.connect.object': 'the workspace',

  /* ---- the failed workspace chunk, rendered by the eager shell -------------- */
  'shell.module.title': 'The workspace could not be loaded',
  'shell.module.note': 'Reload the page to restore the workspace. The existing browser workspace is kept, and you can return to the public pages first.',
  'shell.module.reload': 'Reload the page',
  'shell.toolReturn': '↖ Y’s Formfield',

  /* ---- the document title on a tool route, set by the eager shell ----------- */
  'doc.title.app': 'Plimsoll · Vessel calculation workbench',

  /* ---- the sound control, mounted by both surfaces ------------------------- */
  'sound.label': 'Interaction sound',
  'sound.on': 'Turn interaction sound on',
  'sound.off': 'Mute interaction sound',
} as const;

/** Every string the shared chrome can print, from either surface. */
export type ShellKey = keyof typeof EN;

/** The shape both dictionaries must have. */
export type ShellDictionary = Readonly<Record<ShellKey, string>>;

const ZH: ShellDictionary = {
  'read.status': '正在读取{object}',
  'read.waiting': '仍在等待{object}的读取结果，已超过 2 秒。',
  'read.retry': '重新读取',
  'read.back': '返回',

  'shell.connect.object': '工作空间',

  'shell.module.title': '工作空间未能加载',
  'shell.module.note': '请重新载入页面以恢复工作空间。现有浏览器工作区会保留，也可以先返回公共页面。',
  'shell.module.reload': '重新载入页面',
  'shell.toolReturn': '↖ Y’s Formfield',

  'doc.title.app': 'Plimsoll · 舰船计算工作台',

  'sound.label': '交互音效',
  'sound.on': '开启交互音效',
  'sound.off': '关闭交互音效',
};

/** The whole shared chrome dictionary for one language. */
export function shellDictionary(language: SiteLanguage): ShellDictionary {
  return language === 'zh-CN' ? ZH : EN;
}

/**
 * One shared chrome message, with its `{slot}`s filled.
 *
 * An unknown key returns the key itself, as in every other dictionary here.
 */
export function shellCopy(language: SiteLanguage, key: ShellKey, params?: CopyParams): string {
  const text: string = (shellDictionary(language) as Record<string, string>)[key] ?? key;
  return interpolate(text, params);
}

/**
 * The shared chrome lookup, bound to the shell's one language state.
 *
 * With no provider above it, this is the English lookup the eager chunk has
 * always printed, so a component rendered on its own keeps its existing words
 * and every standalone English expectation stays true.
 */
export function useShellCopy(): (key: ShellKey, params?: CopyParams) => string {
  const { language } = useLanguage();
  return useCallback((key: ShellKey, params?: CopyParams) => shellCopy(language, key, params), [language]);
}
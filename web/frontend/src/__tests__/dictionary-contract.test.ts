import { describe, expect, it } from 'vitest';

import { labCopy, labDictionary, type LabKey } from '../i18n/lab';
import { shellCopy, shellDictionary, type ShellKey } from '../i18n/shell';
import { workspaceCopy, workspaceDictionary, type WorkspaceKey } from '../i18n/workspace';
import { GLOSSARY, interpolate } from '../i18n/terms';

/**
 * The contract the three dictionaries make with each other.
 *
 * This is deliberately *not* a set of string snapshots. What has to hold is
 * structural: the same keys on both sides, the same `{slot}` names in the same
 * message, no unknown key silently rendering as an empty line, and a glossary
 * that the copy actually uses. A sentence may be rewritten at any time; a
 * missing key or a renamed slot may not.
 */

interface Contract {
  readonly name: string;
  readonly en: Readonly<Record<string, string>>;
  readonly zh: Readonly<Record<string, string>>;
  readonly lookup: (key: string, params?: Record<string, string | number>) => string;
}

const CONTRACTS: readonly Contract[] = [
  { name: 'shell', en: shellDictionary('en'), zh: shellDictionary('zh-CN'), lookup: (key, params) => shellCopy('en', key as ShellKey, params) },
  { name: 'workspace', en: workspaceDictionary('en'), zh: workspaceDictionary('zh-CN'), lookup: (key, params) => workspaceCopy('en', key as WorkspaceKey, params) },
  { name: 'lab', en: labDictionary('en'), zh: labDictionary('zh-CN'), lookup: (key, params) => labCopy('en', key as LabKey, params) },
];

/** Every `{slot}` a message declares, as a sorted set. */
function slots(text: string): string[] {
  return [...text.matchAll(/\{(\w+)\}/g)].map(m => m[1]).sort();
}

describe('the bilingual dictionaries', () => {
  it.each(CONTRACTS)('$name declares the same keys in both languages', ({ en, zh }) => {
    const english = Object.keys(en).sort();
    const chinese = Object.keys(zh).sort();
    // A missing Chinese entry is a blank line on screen; an extra one is a key
    // that the English side cannot print. Either way the build should have failed.
    expect(chinese.filter(key => !english.includes(key))).toEqual([]);
    expect(english.filter(key => !chinese.includes(key))).toEqual([]);
    expect(english.length).toBeGreaterThan(0);
  });

  it.each(CONTRACTS)('$name uses the same interpolation slots in both languages', ({ en, zh }) => {
    const mismatched: string[] = [];
    for (const [key, english] of Object.entries(en)) {
      const chinese = zh[key];
      if (chinese === undefined) continue;
      const left = slots(english);
      const right = slots(chinese);
      // Every slot the Chinese side fills must exist in the English side, and
      // vice versa: a message that drops `{revision}` prints the placeholder.
      if (left.join(',') !== right.join(',')) mismatched.push(key);
    }
    expect(mismatched).toEqual([]);
  });

  it.each(CONTRACTS)('$name leaves no message empty in either language', ({ en, zh }) => {
    for (const [key, english] of Object.entries(en)) {
      expect(english.trim(), `${key} (en)`).not.toBe('');
      expect((zh[key] ?? '').trim(), `${key} (zh)`).not.toBe('');
    }
  });

  it.each(CONTRACTS)('$name reports an unknown key as itself rather than as an empty line', ({ lookup }) => {
    // A typo must be visible on screen as something obviously wrong.
    expect(lookup('no.such.key' as never)).toBe('no.such.key');
  });

  it.each(CONTRACTS)('$name fills every slot it is given and keeps the rest verbatim', ({ en, lookup }) => {
    const withSlots = Object.entries(en).find(([, text]) => slots(text).length > 0);
    expect(withSlots).toBeDefined();
    const [key, text] = withSlots!;
    const name = slots(text)[0];
    expect(lookup(key as never, { [name]: 'X' } as never)).toContain('X');
    expect(lookup(key as never, {} as never)).toBe(text);
  });

  it('fills slots the same way the public shell does', () => {
    // The rule every dictionary shares: a supplied slot is filled, a missing one
    // is left in the text rather than becoming the word `undefined`.
    expect(interpolate('Reading {object}', { object: 'the run' })).toBe('Reading the run');
    expect(interpolate('Reading {object}')).toBe('Reading {object}');
    expect(interpolate('Reading {object}', { other: 'x' })).toBe('Reading {object}');
    expect(interpolate('Reading {object}', { object: 3 })).toBe('Reading 3');
  });
});

describe('the glossary', () => {
  it('fixes one word per concept in both languages', () => {
    for (const [id, entry] of Object.entries(GLOSSARY)) {
      expect(entry.en.trim(), `${id}.en`).not.toBe('');
      expect(entry.zh.trim(), `${id}.zh`).not.toBe('');
      expect(entry.note.trim(), `${id}.note`).not.toBe('');
    }
  });

  it('keeps the four kinds of absence distinct, in both dictionaries', () => {
    // The glossary's central rule: not-requested, unknown, not-applicable and
    // not-computable-now are four facts and never one word.
    const concepts = [GLOSSARY.unknown.zh, GLOSSARY.notRequested.zh, GLOSSARY.notApplicable.zh, GLOSSARY.unavailable.zh];
    expect(new Set(concepts).size).toBe(4);

    const workspace = workspaceDictionary('zh-CN');
    const statuses = ['status.not_requested', 'reading.unknown', 'units.unknown'] as const;
    expect(new Set(statuses.map(key => workspace[key])).size).toBeGreaterThan(1);

    const english = workspaceDictionary('en');
    expect(new Set(statuses.map(key => english[key])).size).toBeGreaterThan(1);
  });


});

describe('the keys the type system checks', () => {
  it('are the ones the dictionaries declare', () => {
    // A typed alias that names a key the table does not have would compile only
    // if it were cast; checking the count here keeps the export honest.
    const workspaceKeys = Object.keys(workspaceDictionary('en')) as WorkspaceKey[];
    const labKeys = Object.keys(labDictionary('en')) as LabKey[];
    const shellKeys = Object.keys(shellDictionary('en')) as ShellKey[];
    expect(workspaceKeys.length).toBe(Object.keys(workspaceDictionary('zh-CN')).length);
    expect(labKeys.length).toBe(Object.keys(labDictionary('zh-CN')).length);
    expect(shellKeys.length).toBe(Object.keys(shellDictionary('zh-CN')).length);
  });
});

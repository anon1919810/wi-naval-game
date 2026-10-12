import type { CopyParams, SiteLanguage } from '../portfolio/language';

/**
 * The bilingual glossary every workspace and laboratory string is written from.
 *
 * This is the short list the plan asked for, and it exists so the same word is
 * not two words in two places. It is data, not a lookup the interface calls: a
 * component asks for its own typed key in its own dictionary, and this file is
 * the checklist those keys are drawn from. `glossaryTerms()` is what the
 * evidence inventory prints, and `GLOSSARY` is what a test checks the
 * dictionaries against.
 *
 * Four rules the terms themselves follow, taken from what the tool already means
 * by them:
 *
 * - **A thing, its revision and its condition are three different things.**
 *   项目 is the project, 修订 the immutable saved revision, 工况 one loading
 *   condition inside it. A run always names all three.
 * - **A run and a trial are not the same act.** 运行 is a submitted calculation
 *   with a queue ticket and a fingerprint; 试验 is a declared damage trial in the
 *   laboratory, which is an input rather than a result.
 * - **Absent is absent.** 未请求 means the request never asked for the stage,
 *   未知 means nothing was known and no value exists, 不适用 means the quantity
 *   does not apply here, and 暂不可计算 means it could not be computed now. These
 *   four are never collapsed into one another and never into zero.
 * - **Raw data is never a term.** User names, source strings, identifiers,
 *   diagnostic codes and API enums keep their original spelling in both
 *   languages; `RAW_DATA_EXCEPTIONS` records that as a rule, not a gap.
 */

export type TermId =
  | 'project' | 'revision' | 'condition' | 'run' | 'trial'
  | 'unknown' | 'notRequested' | 'notApplicable' | 'unavailable'
  | 'estimate' | 'source' | 'stage' | 'diagnostic' | 'fingerprint'
  | 'draft' | 'ledger' | 'scenario' | 'request' | 'report';

export interface GlossaryEntry {
  /** The English word, used as the dictionary's own wording. */
  en: string;
  /** The Simplified Chinese word, used by the Chinese dictionary. */
  zh: string;
  /** Why the pair is fixed; the thing it must not be confused with. */
  note: string;
}

export const GLOSSARY: Readonly<Record<TermId, GlossaryEntry>> = {
  project: { en: 'Project', zh: '项目',
    note: 'The saved document. Its name is the reader’s own text and is never translated.' },
  revision: { en: 'Revision', zh: '修订',
    note: 'One immutable saved state. Saving creates a new revision rather than rewriting the old one.' },
  condition: { en: 'Loading condition', zh: '工况',
    note: 'One entry in the project’s loading conditions. Its label is project data; the id is an identifier.' },
  run: { en: 'Run', zh: '运行',
    note: 'A queued calculation belonging to one project, revision and condition. Not a trial and not a report.' },
  trial: { en: 'Trial', zh: '试验',
    note: 'A declared damage trial in the laboratory. A declared input, never a computed result.' },
  unknown: { en: 'Unknown', zh: '未知',
    note: 'Nothing was known, so there is no value. Never shown as zero.' },
  notRequested: { en: 'Not requested', zh: '未请求',
    note: 'The request never asked for this stage. Not a failure and not an unknown value.' },
  notApplicable: { en: 'Not applicable', zh: '不适用',
    note: 'The quantity does not apply to this case. Not an unknown value and not zero.' },
  unavailable: { en: 'Not computable now', zh: '暂不可计算',
    note: 'It could not be computed for a stated reason. The reason stays beside the label.' },
  estimate: { en: 'Engineering estimate', zh: '工程估算',
    note: 'A declared three-state marker on one field. Undeclared is unknown, never “confirmed”.' },
  source: { en: 'Source', zh: '来源',
    note: 'Where a number came from. A declaration of provenance, never historical confirmation.' },
  stage: { en: 'Stage', zh: '阶段',
    note: 'One requested calculation stage. The stage name is an API key; its display name is translated.' },
  diagnostic: { en: 'Diagnostic', zh: '诊断',
    note: 'One finding attached to a saved stage. Its code and message stay exactly as the core wrote them.' },
  fingerprint: { en: 'Request fingerprint', zh: '请求指纹',
    note: 'The identity a stored result belongs to. An opaque identifier, never translated.' },
  draft: { en: 'Draft', zh: '草稿',
    note: 'The edited, possibly unsaved state of a project in the browser. Lost by leaving without saving.' },
  ledger: { en: 'Weight ledger', zh: '重量账本',
    note: 'The single mass authority of a project. Not a second ledger, and never inferred.' },
  scenario: { en: 'Scenario', zh: '情景',
    note: 'A declared set of compartments, connections and openings. Research input, not a mass ledger.' },
  request: { en: 'Calculation request', zh: '计算请求',
    note: 'The set of stages this run will compute. It decides scope, not readiness.' },
  report: { en: 'Report', zh: '报告',
    note: 'The immutable reading of one saved run. Exporting JSON/CSV is not a project backup.' },
};

/** The whole glossary, for the evidence inventory and for the consistency test. */
export function glossaryTerms(): ReadonlyArray<{ id: TermId } & GlossaryEntry> {
  return (Object.keys(GLOSSARY) as TermId[]).map(id => ({ id, ...GLOSSARY[id] }));
}

/**
 * Fill a message's `{slot}`s.
 *
 * The rule is deliberately identical to the public shell's `translate`, so a
 * component below the provider and the same component standing alone
 * interpolate the same way: a slot the caller did not supply is left in the
 * text rather than becoming the word `undefined`.
 */
export function interpolate(text: string, params?: CopyParams): string {
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, slot: string) =>
    Object.hasOwn(params, slot) ? String(params[slot]) : match);
}

/**
 * Text that stays exactly as it was written, in both languages.
 *
 * User-entered names and template names, the template key, API enum values,
 * JSON field names, diagnostic codes, original diagnostic messages, source
 * strings, citations and identifiers are all in this category. They are printed
 * verbatim, marked `lang="en"` where the interface surrounds them with prose,
 * and never routed through a dictionary: a translation layer that rewrote them
 * would corrupt the record the reader is here to check.
 */
export const RAW_DATA_EXCEPTIONS: readonly string[] = [
  'User project names and the names of template, loading-condition, weight-group and item entries.',
  'Template keys (`analytic_box`, `generic_steamer`, `queen_mary_1913`) and every project/condition/run identifier.',
  'API enum values and saved JSON field names, including `plimsoll-project-1` and `$.weight_groups[…].items[…].mass_t` paths.',
  'Diagnostic codes and the original diagnostic messages and stage reasons the core wrote, shown verbatim beside any localized description.',
  'Declared source strings (drawings, plans, archives) as stored.',
  'Unit symbols, method names, equations and citations (Conn, Schoenherr, Taylor-Gertler, Molland).',
];

/** True when the interface should mark a raw fragment as Latin text for a reader. */
export function isLatinSpan(text: string): boolean {
  return /[A-Za-z]/.test(text) && !/[㐀-鿿]/.test(text);
}

/** Re-exported so a dictionary never needs to reach past this module for a type. */
export type { CopyParams, SiteLanguage };
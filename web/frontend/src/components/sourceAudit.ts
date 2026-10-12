import { englishCopy } from './formModel';
import type { Copy } from './diagnosticGuidance';
import type { AnalysisResult } from '../types';

/**
 * The provenance of a saved result, read out of the result itself.
 *
 * A declaration is a field named `source`. A nonempty string is a declaration, and
 * a nonempty structured value is one complete declaration: it is kept whole and
 * never searched again for `source` fields inside it, because "this drawing,
 * page 4" is a single statement, not two. Whatever sits next to it as `estimate`
 * is part of the statement: true, false, or unsaid, which stays unknown rather
 * than becoming false.
 *
 * Every declaration that exists is collected — none is capped, sampled or
 * summarised — and identical declarations are grouped by a stable serialization,
 * so the same drawing recorded twice under different key order is one entry that
 * lists both of its actual paths. Nothing is inferred: a path that is not in the
 * saved payload does not appear.
 */

export type EstimateState = true | false | null;

export interface ProvenanceEntry {
  /** The declaration exactly as saved. */
  declaration: unknown;
  /** The declaration as the reader reads it, independent of key order. */
  text: string;
  estimate: EstimateState;
  /** The actual field path, for independent checking. */
  path: string;
}

export interface ProvenanceGroup {
  /** Stable identity of this declaration and its estimate state. */
  key: string;
  text: string;
  estimate: EstimateState;
  /** Every actual path that declares exactly this. */
  paths: string[];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function childPath(base: string, key: string): string {
  return /^\d+$/.test(key) ? `${base}[${key}]` : `${base}.${key}`;
}

/** Stable text for a structured value: key order must not change what it is. */
export function stableDeclarationText(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableDeclarationText).join(',')}]`;
  if (isRecord(value)) {
    return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${stableDeclarationText(value[key])}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}

/** A declaration exists only when it actually says something. */
function declarationText(value: unknown): string | null {
  if (typeof value === 'string') return value.trim() ? value : null;
  if (isRecord(value) && Object.keys(value).length) return stableDeclarationText(value);
  return null;
}

function estimateOf(record: Record<string, unknown>): EstimateState {
  return record.estimate === true ? true : record.estimate === false ? false : null;
}

/**
 * The estimate state a declaration carries, in the reader's language.
 *
 * The three states stay three facts — an engineering estimate, a declared
 * non-estimate, and a state the payload never declared at all. `w` is a
 * parameter rather than a hidden global so the same saved result reads the same
 * in either language; without one this module falls back to the English words
 * rather than pretending to know the reader's preference.
 */
export function estimateLabel(estimate: EstimateState, w: Copy = englishCopy): string {
  return estimate === true ? w('trace.estimate.estimate') : estimate === false ? w('trace.estimate.declared') : w('trace.estimate.unknown');
}

/** Every declaration under one value, in document order, with its path. */
export function collectDeclarations(root: unknown, base: string): ProvenanceEntry[] {
  const found: ProvenanceEntry[] = [];
  const queue: Array<{ value: unknown; path: string }> = [{ value: root, path: base }];
  for (let index = 0; index < queue.length; index += 1) {
    const { value, path } = queue[index];
    if (Array.isArray(value)) {
      value.forEach((item, position) => queue.push({ value: item, path: childPath(path, String(position)) }));
      continue;
    }
    if (!isRecord(value)) continue;
    const entries = Object.entries(value);
    const declared = entries.find(([key]) => key === 'source');
    if (declared) {
      const text = declarationText(declared[1]);
      if (text !== null) found.push({ declaration: declared[1], text, estimate: estimateOf(value), path: `${path}.source` });
    }
    for (const [key, child] of entries) {
      // A structured declaration is one statement: it is not searched again.
      if (declared && key === 'source' && declarationText(declared[1]) !== null) continue;
      queue.push({ value: child, path: childPath(path, key) });
    }
  }
  return found;
}

/**
 * The roots that hold declarations: the saved sources, the saved input snapshot
 * and the saved data of the stages this result actually requested. A snapshot
 * covers the whole project including scenarios this run never used; stage data
 * covers only what was asked for.
 */
export function provenanceRoots(result: AnalysisResult): Array<{ path: string; value: unknown }> {
  const roots: Array<{ path: string; value: unknown }> = [
    { path: 'result.sources', value: result.sources },
    { path: 'result.input_snapshot', value: result.input_snapshot },
  ];
  for (const [name, stage] of Object.entries(result.stages ?? {})) {
    if (!stage || typeof stage !== 'object' || stage.requested !== true || stage.data === null || stage.data === undefined) continue;
    roots.push({ path: `result.stages.${name}.data`, value: stage.data });
  }
  return roots;
}

const computed = new WeakMap<AnalysisResult, ProvenanceGroup[]>();

/**
 * Every declaration in this saved result, grouped by declaration and estimate.
 * Computed once per result object: the appendix can be opened, printed and
 * reopened without walking the payload again.
 */
export function provenanceGroups(result: AnalysisResult): ProvenanceGroup[] {
  const cached = computed.get(result);
  if (cached) return cached;
  const groups = new Map<string, ProvenanceGroup>();
  for (const root of provenanceRoots(result)) {
    for (const entry of collectDeclarations(root.value, root.path)) {
      const key = `${entry.text}${entry.estimate === null ? 'unknown' : entry.estimate}`;
      const existing = groups.get(key);
      if (existing) existing.paths.push(entry.path);
      else groups.set(key, { key, text: entry.text, estimate: entry.estimate, paths: [entry.path] });
    }
  }
  const result_ = [...groups.values()];
  computed.set(result, result_);
  return result_;
}
import type { Chapter } from './ProjectNav';
import type { ProjectDocument, StageEnvelope } from '../types';

/**
 * Where one saved diagnostic can be followed to, and what it can honestly claim.
 *
 * A diagnostic carries a path into the project that was analysed, never into the
 * project on screen. This resolver therefore reads the *source snapshot* first:
 * an indexed ledger path such as `$.weight_groups[2].items[1].mass_t` names a
 * group and an item **by the ids the source run actually saw**, and only those
 * ids are looked up in the live project. A path is never followed by live index,
 * because editing a ledger reorders it, and a reader would be sent to another
 * vessel's item — or to an item that has since been removed.
 *
 * Nothing here decides whether a project *can* be calculated. It resolves where
 * a field lives, or states truthfully that there is nothing to focus. Paths that
 * point at generated output (`$.stages.*`, `$.diagnostics[...]`), at result
 * metadata, or at anything unrecognised stay plain evidence: a fabricated link
 * to a field that does not exist is worse than no link at all.
 */

/** A diagnostic as the saved result stores it. */
export type Diagnostic = StageEnvelope['diagnostics'][number];

/**
 * - `control` — a real editable control exists and takes focus.
 * - `section`  — a real chapter area exists and takes focus (request area,
 *   ledger, project JSON).
 * - `evidence` — nothing on screen corresponds to this path.
 */
export type GuidanceKind = 'control' | 'section' | 'evidence';

export interface DiagnosticLocation {
  kind: GuidanceKind;
  /** The chapter a jump selects; null when there is nothing to jump to. */
  chapter: Chapter | null;
  /** Id of the element that takes focus; null when there is nothing to focus. */
  target: string | null;
  /** What the reader is being taken to, in the reader's own words. */
  label: string;
  /** The diagnostic's original path, verbatim. */
  path: string;
  /** One truthful sentence about what this location can and cannot do. */
  note: string;
}

export interface DiagnosticSource {
  /** The saved input snapshot the diagnostic was computed against. */
  snapshot: ProjectDocument | null;
  /** The live project the reader is editing now. */
  live: ProjectDocument | null;
}

/** Chapter-level targets. Each id is mounted by the workspace itself. */
export const LEDGER_SECTION = 'guidance-ledger';
export const REQUEST_PERFORMANCE = 'guidance-request-performance';
export const REQUEST_DAMAGE = 'guidance-request-damage';
/** The project document editor every chapter owns; focus lands in its textarea. */
export const PROJECT_JSON = 'chapter-json';
export const CHAPTER_HEAD = 'guidance-chapter-head';

/** The six hull scalars the workspace edits as their own controls. */
const HULL_LABELS: Record<string, string> = {
  loa_m: '船长', length_m: '船长', lwl_m: '水线长', beam_m: '型宽',
  draught_normal_m: '设计吃水', draft_m: '设计吃水',
  block_coeff: '方形系数', waterplane_coeff: '水线面系数',
};

/** The legacy spellings one control answers to, never a second control. */
const HULL_ALTERNATES: Record<string, string> = { length_m: 'loa_m', draft_m: 'draught_normal_m' };

/** The three ledger facts each ledger row owns as its own control. */
const LEDGER_LABELS: Record<string, string> = { mass_t: '质量', x_m: '纵向位置', source: '来源' };

/** Project roots the JSON chapter edits in full; nothing else is claimed here. */
const PROJECT_JSON_ROOTS = new Set([
  'geometry', 'deck', 'systems', 'compartments', 'openings', 'loading_conditions',
  'flooding_scenarios', 'resistance_scenarios', 'endurance_scenarios', 'damage_presets',
  'display_preferences', 'metadata',
]);

/**
 * Control identity. Group and item ids are project data, so the whole tuple is
 * encoded as one value: a separator-joined form collides for ids that contain
 * the separator, and two different ledger rows must never share one id.
 */
export function ledgerGuidanceId(groupId: string, itemId: string, field: string): string {
  return `guidance-ledger-${encodeURIComponent(JSON.stringify([groupId, itemId, field]))}`;
}

export function hullGuidanceId(key: string): string {
  return `guidance-hull-${key}`;
}

type Segment = { key: string } | { index: number };

/**
 * A strict reader for the `$`-rooted paths the coordinator writes. Anything it
 * does not fully understand returns null instead of a partial reading, so a
 * malformed path degrades to evidence rather than to a wrong field.
 */
export function parseDiagnosticPath(path: string): Segment[] | null {
  let rest = String(path ?? '').trim();
  if (!rest.startsWith('$')) return null;
  rest = rest.slice(1);
  const segments: Segment[] = [];
  while (rest.length > 0) {
    if (rest[0] === '.') {
      const name = /^\.([A-Za-z_][A-Za-z0-9_]*)/.exec(rest);
      if (!name) return null;
      segments.push({ key: name[1] });
      rest = rest.slice(name[0].length);
    } else if (rest[0] === '[') {
      const index = /^\[(\d+)\]/.exec(rest);
      if (index) { segments.push({ index: Number(index[1]) }); rest = rest.slice(index[0].length); continue; }
      const quoted = /^\["([^"\\]*)"\]/.exec(rest);
      if (quoted) { segments.push({ key: quoted[1] }); rest = rest.slice(quoted[0].length); continue; }
      return null;
    } else return null;
  }
  return segments;
}

function keyOf(segment: Segment | undefined): string | undefined {
  return segment && 'key' in segment ? segment.key : undefined;
}

function indexOf(segment: Segment | undefined): number | undefined {
  return segment && 'index' in segment ? segment.index : undefined;
}

function entries(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value) ? value.filter(entry => !!entry && typeof entry === 'object' && !Array.isArray(entry)) as Record<string, unknown>[] : [];
}

function entryAt(list: Record<string, unknown>[], index: number | undefined): Record<string, unknown> | undefined {
  return index === undefined ? undefined : list[index];
}

function idOf(entry: Record<string, unknown> | undefined): string | null {
  return typeof entry?.id === 'string' && entry.id !== '' ? entry.id : null;
}

function evidence(path: string, note: string): DiagnosticLocation {
  return { kind: 'evidence', chapter: null, target: null, label: '', path, note };
}

function control(path: string, chapter: Chapter, target: string, label: string, note: string): DiagnosticLocation {
  return { kind: 'control', chapter, target, label, path, note };
}

function section(path: string, chapter: Chapter, target: string, label: string, note: string): DiagnosticLocation {
  return { kind: 'section', chapter, target, label, path, note };
}

function hullLocation(path: string, segments: Segment[]): DiagnosticLocation {
  const field = keyOf(segments[1]);
  const label = field ? HULL_LABELS[field] : undefined;
  const control = field ? HULL_ALTERNATES[field] ?? field : undefined;
  // Only the number itself is a control, and one spelling of it. A declared
  // source has no editor of its own in the workspace, so it is never dressed up
  // as the dimension: typing a number would not repair missing provenance.
  if (label && control && segments.length === 2) return hullControl(path, control, label);
  if (field === 'warnings') return evidence(path, '这条路径是船型资料的历史警告，不是可编辑的项目输入。');
  return section(path, 'json', PROJECT_JSON, '项目数据', `这条路径没有对应的独立表单控件：在“项目数据”中按原路径 ${path} 查看与编辑。`);
}

function hullControl(path: string, key: string, label: string): DiagnosticLocation {
  return { kind: 'control', chapter: 'hull', target: hullGuidanceId(key), label, path,
    note: `在“船型与几何”中编辑${label}，保存修订后重新运行才会生效。` };
}

function ledgerLocation(path: string, segments: Segment[], source: DiagnosticSource): DiagnosticLocation {
  // The indices are read against the source snapshot, never against the live
  // ledger: only the ids that run actually saw may be looked up now.
  const groupIndex = indexOf(segments[1]);
  const snapshotGroup = entryAt(entries(source.snapshot?.weight_groups), groupIndex);
  const groupId = idOf(snapshotGroup);
  if (groupIndex === undefined || !groupId) {
    // A whole ledger, a group or a group list has no editor anywhere: the
    // workspace only edits rows that already exist, so the document is the only
    // honest place to go.
    return section(path, 'json', PROJECT_JSON, '项目数据', `这条路径指向账本整体或分组，不是可编辑的单行：在“项目数据”中按原路径 ${path} 查看与编辑。`);
  }
  if (keyOf(segments[2]) !== 'items') {
    return section(path, 'json', PROJECT_JSON, '项目数据', `这条路径指向分组整体，不是可编辑的单行：在“项目数据”中按原路径 ${path} 查看与编辑。`);
  }
  const itemIndex = indexOf(segments[3]);
  if (itemIndex === undefined) {
    return section(path, 'json', PROJECT_JSON, '项目数据', `这条路径指向条目列表；“重量与载荷”只编辑已有条目，新增条目请在“项目数据”中按原路径 ${path} 进行。`);
  }
  const snapshotItem = entryAt(entries(snapshotGroup?.items), itemIndex);
  const itemId = idOf(snapshotItem);
  if (!itemId) {
    return evidence(path, '来源运行中的这条账本路径没有可用的条目 id，无法定位到当前项目。');
  }
  // Removal is checked before any fallback: an item that is gone is not
  // something the reader can edit anywhere, least of all in the document.
  const liveGroups = entries(source.live?.weight_groups);
  const liveGroupIndex = liveGroups.findIndex(entry => entry.id === groupId);
  const liveGroup = liveGroups[liveGroupIndex];
  const liveItems = entries(liveGroup?.items);
  const liveItemIndex = liveItems.findIndex(entry => entry.id === itemId);
  if (liveGroupIndex === -1 || liveItemIndex === -1) {
    return evidence(path, `来源运行中的账本条目 ${groupId} / ${itemId} 已不在当前项目，无法定位到对应控件；原路径 ${path} 保留为证据。`);
  }
  const currentPath = `$.weight_groups[${liveGroupIndex}].items[${liveItemIndex}]`;
  const field = keyOf(segments[4]);
  const fieldLabel = field ? LEDGER_LABELS[field] : undefined;
  // A scalar control exists for exactly `…items[i].mass_t|x_m|source` and nothing
  // longer: `…mass_t.value` is not that control.
  if (segments.length === 5 && field && fieldLabel) {
    return control(path, 'weights', ledgerGuidanceId(groupId, itemId, field), `${groupId} · ${itemId} 的${fieldLabel}`,
      `在“重量与载荷”中编辑 ${groupId} / ${itemId} 的${fieldLabel}，保存修订后重新运行才会生效。`);
  }
  if (segments.length === 4) {
    return section(path, 'weights', LEDGER_SECTION, '重量与载荷',
      `这一行现在位于 ${currentPath}（${groupId} / ${itemId}）；保存修订后重新运行才会生效。`);
  }
  return section(path, 'json', PROJECT_JSON, '项目数据',
    `${groupId} / ${itemId} 现在位于 ${currentPath}。该字段没有对应的表单控件：在“项目数据”中按当前路径编辑，原路径 ${path} 保留为证据。`);
}

function conditionsLocation(path: string, segments: Segment[], source: DiagnosticSource): DiagnosticLocation {
  const index = indexOf(segments[1]);
  const snapshot = entryAt(entries(source.snapshot?.loading_conditions), index);
  const conditionId = idOf(snapshot);
  if (conditionId === null) {
    return section(path, 'json', PROJECT_JSON, '项目数据', `这条路径指向工况列表；在“项目数据”中按原路径 ${path} 查看与编辑。`);
  }
  const live = entries(source.live?.loading_conditions);
  const current = live.findIndex(entry => entry.id === conditionId);
  if (current === -1) {
    return evidence(path, `来源运行中的工况 ${conditionId} 已不在当前项目，无法定位到对应控件；原路径 ${path} 保留为证据。`);
  }
  return section(path, 'json', PROJECT_JSON, '项目数据',
    `工况 ${conditionId} 现在位于 $.loading_conditions[${current}]：在“项目数据”中按当前路径编辑，原路径 ${path} 保留为证据。`);
}

function optionsLocation(path: string, segments: Segment[]): DiagnosticLocation {
  const head = keyOf(segments[1]);
  // The flooding request — including the shared environment density — is the
  // damage chapter's own request area; everything else is the performance one.
  if (head === 'flooding' || (head === 'equilibrium' && keyOf(segments[2]) === 'rho_t_m3')) {
    return section(path, 'damage', REQUEST_DAMAGE, '破损研究的计算请求', `破损请求在“破损研究”中编辑；诊断原路径 ${path} 保持不变，不会自动重建旧请求。`);
  }
  return section(path, 'performance', REQUEST_PERFORMANCE, '性能与工况的计算请求', `计算请求在“性能与工况”中编辑；诊断原路径 ${path} 保持不变，不会自动重建旧请求。`);
}

/**
 * The one resolver both surfaces share. It returns null only when there is no
 * path at all; a path it cannot place is still returned, as evidence, so the
 * caller can say so instead of quietly dropping the finding.
 */
export function resolveDiagnosticPath(path: unknown, source: DiagnosticSource): DiagnosticLocation | null {
  if (typeof path !== 'string' || path.trim() === '') return null;
  const literal = path.trim();
  const segments = parseDiagnosticPath(literal);
  if (!segments || segments.length === 0) {
    return evidence(literal, '这条诊断的路径无法解析，只作为证据保留。');
  }
  const root = keyOf(segments[0]);
  if (!root) return evidence(literal, '这条诊断的路径没有可识别的项目字段，只作为证据保留。');
  if (root === 'hull') return hullLocation(literal, segments);
  if (root === 'weight_groups') return ledgerLocation(literal, segments, source);
  if (root === 'loading_conditions') return conditionsLocation(literal, segments, source);
  if (root === 'options') return optionsLocation(literal, segments);
  if (PROJECT_JSON_ROOTS.has(root)) {
    return section(literal, 'json', PROJECT_JSON, '项目数据', `在“项目数据”中按原路径 ${path} 查看与编辑。`);
  }
  return evidence(literal, '这条路径不是可编辑的项目输入（结果、诊断或未知字段），只作为证据保留。');
}

/**
 * The finding's own location, preferring a path that can actually be followed.
 * Both the diagnostic's `path` and its `source_path` are evidence and both stay
 * on screen; only the navigation is chosen here.
 */
export function resolveDiagnosticLocation(diagnostic: Diagnostic, source: DiagnosticSource): DiagnosticLocation | null {
  const found = [diagnostic.path, diagnostic.source_path]
    .map(candidate => resolveDiagnosticPath(candidate, source))
    .filter((entry): entry is DiagnosticLocation => entry !== null);
  if (found.length === 0) return null;
  return found.find(entry => entry.kind !== 'evidence') ?? found[0];
}

/**
 * A native address back into the project, in the tool's own hash route. The run
 * id stays in the address because every diagnostic belongs to the run that
 * produced it; refreshing, copying and Back/Forward all resolve to the same
 * project and the same source run.
 */
export function diagnosticHref(projectId: string, runId: string, path: string): string {
  return `#/projects/${encodeURIComponent(projectId)}/diagnostics/${encodeURIComponent(runId)}/${encodeURIComponent(path)}`;
}

function safeDecode(segment: string): string | null {
  try { return decodeURIComponent(segment); } catch { return null; }
}

/**
 * What the address says, in three honest parts. `none` is an ordinary project
 * address; `target` is a usable diagnostic link; `malformed` is a diagnostic
 * address that cannot be trusted — a foreign project, a missing segment, a
 * broken percent-escape or a path that is not a path. The third is reported to
 * the reader instead of being passed off as a normal arrival.
 */
export type DiagnosticTail =
  | { kind: 'none' }
  | { kind: 'target'; runId: string; path: string }
  | { kind: 'malformed'; reason: string };

export function readDiagnosticTail(hash: string, projectId: string): DiagnosticTail {
  const parts = String(hash ?? '').replace(/^#/, '').replace(/^\/+/, '').split('/');
  // An ordinary project address carries nothing to do; a `…/diagnostics/…` tail
  // is one, and is judged rather than assumed.
  if (parts[0] !== 'projects' || parts[2] !== 'diagnostics') return { kind: 'none' };
  if (parts.length !== 5) return { kind: 'malformed', reason: '地址里的诊断定位不完整，无法解析。' };
  const id = safeDecode(parts[1]);
  const runId = safeDecode(parts[3]);
  const path = safeDecode(parts[4]);
  if (id === null || runId === null || path === null) return { kind: 'malformed', reason: '地址里的诊断定位包含无法解码的内容。' };
  if (id !== projectId) return { kind: 'malformed', reason: '这条诊断链接属于其他项目，已拒绝跳转。' };
  if (runId === '') return { kind: 'malformed', reason: '地址里没有指明来源运行，无法定位输入。' };
  if (!path.startsWith('$')) return { kind: 'malformed', reason: '地址里的诊断路径不是项目路径，只作为证据保留。' };
  return { kind: 'target', runId, path };
}

/**
 * The diagnostic named by `hash`, or null when it is not this project's own
 * diagnostic address. The reader stays where they are instead of being sent to
 * a wrong field.
 */
export function readDiagnosticTarget(hash: string, projectId: string): { runId: string; path: string } | null {
  const tail = readDiagnosticTail(hash, projectId);
  return tail.kind === 'target' ? { runId: tail.runId, path: tail.path } : null;
}
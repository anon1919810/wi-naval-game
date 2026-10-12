/**
 * Reading a project backup off this device.
 *
 * A backup is a file the reader chose on their own machine, so everything here
 * is a refusal rather than a repair. The rules are deliberately narrow:
 *
 * - It is read as bytes and decoded as UTF-8, allowing the single byte-order
 *   mark that Windows editors add, because a backup that decodes into
 *   replacement characters is not the document the reader saved.
 * - A file that is not JSON, or is JSON but not an object, or is an analysis
 *   report, is refused with a reason instead of being coerced into a project.
 * - Non-finite numbers are refused. `JSON.stringify` writes `Infinity` as `null`
 *   without complaint, so sending one would silently change the saved data; the
 *   original value is not representable, and saying so beats altering it.
 * - Both the raw file and the actual UTF-8 bytes of each request envelope are
 *   held under the server's 8 MiB limit, because a request that exceeds it is
 *   refused by middleware the reader can never see.
 *
 * Every sentence this module writes is application copy, so the words come from
 * the dictionary through the `Copy` the caller passes. This module stays pure:
 * without one it answers in English, the workspace's own default.
 */

import type { WorkspaceKey } from '../i18n/workspace';
import { englishCopy } from './formModel';
import type { Copy } from './diagnosticGuidance';

/** The bounded request middleware's limit; a larger backup cannot be sent. */
export const MAX_BACKUP_BYTES = 8 * 1024 * 1024;

/**
 * The one byte-order mark JSON text may legitimately begin with. A decoder
 * configured normally already consumes it; one that does not leaves exactly
 * one, and a second would be content rather than a mark.
 */
const BOM = '\uFEFF';

export interface BackupDocument {
  /** The parsed canonical project, exactly as the file described it. */
  project: Record<string, unknown>;
  /** The file's own name, so a reader can tell which backup they chose. */
  filename: string;
  /** Raw file size in bytes, before any parsing. */
  size: number;
}

/** A refusal with a sentence a reader can act on. */
export class BackupFileError extends Error {
  constructor(readonly key: WorkspaceKey, readonly params: Record<string, string | number> = {}, copy: Copy = englishCopy) {
    super(copy(key, params));
    this.name = 'BackupFileError';
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * The first non-finite number in a decoded document, with the path that names
 * it. Returns null when every number is finite.
 */
export function findNonFiniteNumber(value: unknown, path = '$'): string | null {
  if (typeof value === 'number') return Number.isFinite(value) ? null : path;
  if (Array.isArray(value)) {
    for (const [index, member] of value.entries()) {
      const found = findNonFiniteNumber(member, `${path}[${index}]`);
      if (found) return found;
    }
    return null;
  }
  if (isPlainObject(value)) {
    for (const [key, member] of Object.entries(value)) {
      const found = findNonFiniteNumber(member, `${path}.${key}`);
      if (found) return found;
    }
  }
  return null;
}

/**
 * The exact bytes this client will put on the wire, so the size check is made
 * against the request rather than against an estimate of it.
 */
export function envelopeSize(payload: unknown): number {
  return new TextEncoder().encode(JSON.stringify(payload)).length;
}

/** Refuse an envelope the server's middleware would refuse anyway. */
export function assertEnvelopeFits(payload: unknown, label: string, w: Copy = englishCopy): void {
  const size = envelopeSize(payload);
  if (size > MAX_BACKUP_BYTES) {
    throw new BackupFileError('backup.tooLarge', { label, size: (size / 1024 / 1024).toFixed(1) }, w);
  }
}

function decodeUtf8(bytes: Uint8Array, w: Copy): string {
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  } catch {
    throw new BackupFileError('backup.encoding', {}, w);
  }
  return text.startsWith(BOM) ? text.slice(BOM.length) : text;
}

/**
 * Parse already-read text as a canonical project backup.
 *
 * Split from the file read so the rules above can be exercised directly, and so
 * a component can reuse them for a file it has already loaded.
 */
export function parseBackup(text: string, filename: string, size: number, w: Copy = englishCopy): BackupDocument {
  const trimmed = text.trim();
  if (trimmed === '') throw new BackupFileError('backup.empty', {}, w);
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new BackupFileError('backup.notJson', {}, w);
  }
  if (!isPlainObject(parsed)) {
    throw new BackupFileError('backup.notObject', {}, w);
  }
  if (parsed.schema === 'plimsoll-analysis-1') {
    throw new BackupFileError('backup.isReport', {}, w);
  }
  const broken = findNonFiniteNumber(parsed);
  if (broken) {
    throw new BackupFileError('backup.nonFinite', { path: broken }, w);
  }
  assertEnvelopeFits({ project: parsed }, w('backup.label'), w);
  return { project: parsed, filename, size };
}

function readBytes(file: Blob, w: Copy): Promise<Uint8Array> {
  if (typeof file.arrayBuffer === 'function') return file.arrayBuffer().then(buffer => new Uint8Array(buffer));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(new BackupFileError('backup.readFailed', {}, w));
    reader.onabort = () => reject(new BackupFileError('backup.readAborted', {}, w));
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Read one chosen file into a canonical project document, or refuse it.
 *
 * The size is checked before any read so an oversized file costs nothing, and
 * the decode is strict so a mis-encoded file is reported rather than repaired.
 */
export async function readBackupFile(file: File, w: Copy = englishCopy): Promise<BackupDocument> {
  const name = file.name || w('backup.unnamed');
  if (file.size > MAX_BACKUP_BYTES) {
    throw new BackupFileError('backup.fileTooLarge', { name, size: (file.size / 1024 / 1024).toFixed(1) }, w);
  }
  if (file.size === 0) throw new BackupFileError('backup.empty', {}, w);
  return parseBackup(decodeUtf8(await readBytes(file, w), w), name, file.size, w);
}
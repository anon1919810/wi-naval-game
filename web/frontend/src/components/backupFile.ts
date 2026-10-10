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
 */

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
  constructor(message: string) {
    super(message);
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
export function assertEnvelopeFits(payload: unknown, label: string): void {
  const size = envelopeSize(payload);
  if (size > MAX_BACKUP_BYTES) {
    throw new BackupFileError(
      `${label}按 JSON 编码后约 ${(size / 1024 / 1024).toFixed(1)} MiB，超过 8 MiB 的请求上限。请改用体积更小的备份。`,
    );
  }
}

function decodeUtf8(bytes: Uint8Array): string {
  let text: string;
  try {
    text = new TextDecoder('utf-8', { fatal: true, ignoreBOM: true }).decode(bytes);
  } catch {
    throw new BackupFileError('文件不是有效的 UTF-8 文本，无法作为项目备份读取。');
  }
  return text.startsWith(BOM) ? text.slice(BOM.length) : text;
}

/**
 * Parse already-read text as a canonical project backup.
 *
 * Split from the file read so the rules above can be exercised directly, and so
 * a component can reuse them for a file it has already loaded.
 */
export function parseBackup(text: string, filename: string, size: number): BackupDocument {
  const trimmed = text.trim();
  if (trimmed === '') throw new BackupFileError('文件是空的，没有可读取的项目备份。');
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new BackupFileError('文件不是有效的 JSON。请选择「下载项目 JSON」保存的备份文件。');
  }
  if (!isPlainObject(parsed)) {
    throw new BackupFileError('备份文件的顶层必须是一个 JSON 对象，而不是数组或其他值。');
  }
  if (parsed.schema === 'plimsoll-analysis-1') {
    throw new BackupFileError('这是计算报告，不是项目备份。请在项目页用「下载项目 JSON」保存备份。');
  }
  const broken = findNonFiniteNumber(parsed);
  if (broken) {
    throw new BackupFileError(`备份中的 ${broken} 不是有限数值，无法原样保存。`);
  }
  assertEnvelopeFits({ project: parsed }, '该备份');
  return { project: parsed, filename, size };
}

function readBytes(file: Blob): Promise<Uint8Array> {
  if (typeof file.arrayBuffer === 'function') return file.arrayBuffer().then(buffer => new Uint8Array(buffer));
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(new BackupFileError('文件无法读取，请重新选择一次。'));
    reader.onabort = () => reject(new BackupFileError('文件读取已中止，请重新选择一次。'));
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Read one chosen file into a canonical project document, or refuse it.
 *
 * The size is checked before any read so an oversized file costs nothing, and
 * the decode is strict so a mis-encoded file is reported rather than repaired.
 */
export async function readBackupFile(file: File): Promise<BackupDocument> {
  const name = file.name || '未命名备份';
  if (file.size > MAX_BACKUP_BYTES) {
    throw new BackupFileError(
      `文件 ${name} 约 ${(file.size / 1024 / 1024).toFixed(1)} MiB，超过 8 MiB 的请求上限。`,
    );
  }
  if (file.size === 0) throw new BackupFileError('文件是空的，没有可读取的项目备份。');
  return parseBackup(decodeUtf8(await readBytes(file)), name, file.size);
}

/**
 * Reading a SpringSharp 3.0 source file off this device.
 *
 * A `.sship` file is somebody's ship: 280 positional records whose meaning comes
 * from their position and whose decimal convention is stated by its header, plus
 * an operator's notes. Nothing in a browser can read that, and this module does
 * not try. It reads the chosen file as bytes and hands those bytes on:
 *
 * - **No text decoding.** The header's separator, an encoding the browser would
 *   guess wrong, a note in a legacy code page and a record that is not valid
 *   UTF-8 all have to survive intact, because the server archives the file as it
 *   arrived. Decoding and re-encoding would silently replace those bytes.
 * - **No numeric interpretation.** A field is a byte range, not a number here.
 *   Whether `1.234,5` means what it looks like is the server's answer, given
 *   together with the rest of the file.
 * - **No large spread.** Base64 is produced from a lookup table, so a megabyte
 *   is encoded without `String.fromCharCode(...bytes)`, which throws on one.
 * - **A bound the server also enforces.** The decoded source is held to the same
 *   1 MiB the endpoint accepts, and the size is checked before any read, so an
 *   oversized file costs nothing.
 *
 * Every sentence this module writes is application copy and comes from the
 * dictionary through the `Copy` the caller passes; without one it answers in
 * English, the workspace's own default.
 */

import type { WorkspaceKey } from '../i18n/workspace';
import { englishCopy } from './formModel';
import type { Copy } from './diagnosticGuidance';

/** The bound the sship endpoints place on the decoded source. */
export const MAX_SSHIP_BYTES = 1024 * 1024;

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';

/**
 * One base64 block per twelve-bit group, indexed by the two bytes it covers, so
 * encoding a whole file is a table lookup per block rather than a string builder
 * call per character.
 */
const BLOCKS: string[] = (() => {
  const table: string[] = [];
  for (let index = 0; index < 4096; index += 1) {
    table.push(ALPHABET[index >> 6] + ALPHABET[index & 0x3f]);
  }
  return table;
})();

export interface SshipSourceFile {
  /** The file's own name, so a reader can tell which source they chose. */
  filename: string;
  /** The original bytes, standard base64, exactly as they will be sent. */
  content_base64: string;
  /** Raw file size in bytes, before anything was done to them. */
  size: number;
}

/** A refusal with a sentence a reader can act on. */
export class SshipFileError extends Error {
  constructor(readonly key: WorkspaceKey, readonly params: Record<string, string | number> = {},
              copy: Copy = englishCopy) {
    super(copy(key, params));
    this.name = 'SshipFileError';
  }
}

/**
 * Encode original bytes as standard base64, without interpreting them.
 *
 * The result is the same alphabet, padding and all that `JSON.stringify` would
 * carry for the same numbers, which is what the endpoint decodes back into the
 * file the reader chose.
 */
export function encodeBase64(bytes: Uint8Array): string {
  let out = '';
  let index = 0;
  for (; index + 2 < bytes.length; index += 3) {
    const first = bytes[index] << 4 | bytes[index + 1] >> 4;
    const second = (bytes[index + 1] & 0x0f) << 8 | bytes[index + 2];
    out += BLOCKS[first] + BLOCKS[second];
  }
  if (index + 1 === bytes.length) {
    const last = bytes[index];
    out += ALPHABET[last >> 2] + ALPHABET[(last & 0x03) << 4] + '==';
  } else if (index + 2 === bytes.length) {
    const first = bytes[index] << 4 | bytes[index + 1] >> 4;
    out += BLOCKS[first] + ALPHABET[(bytes[index + 1] & 0x0f) << 2] + '=';
  }
  return out;
}

/**
 * Read a file's bytes, refusing a read that fails rather than sending no file.
 *
 * Both available readers end at the same refusal, so a source that cannot be
 * read from disk is reported in the reader's own words rather than as whatever
 * error the device happened to raise.
 */
function readBytes(file: Blob, w: Copy): Promise<Uint8Array> {
  if (typeof file.arrayBuffer === 'function') {
    return file.arrayBuffer()
      .then(buffer => new Uint8Array(buffer))
      .catch(() => { throw new SshipFileError('sship.file.readFailed', {}, w); });
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(new Uint8Array(reader.result as ArrayBuffer));
    reader.onerror = () => reject(new SshipFileError('sship.file.readFailed', {}, w));
    reader.onabort = () => reject(new SshipFileError('sship.file.readAborted', {}, w));
    reader.readAsArrayBuffer(file);
  });
}

/**
 * Read one chosen source file into bytes the server will parse, or refuse it.
 *
 * The size is checked before any read, so an oversized file costs nothing; the
 * bytes are never decoded, so what arrives is what the reader chose.
 */
export async function readSshipFile(file: File, w: Copy = englishCopy): Promise<SshipSourceFile> {
  const name = file.name || w('sship.file.unnamed');
  if (file.size > MAX_SSHIP_BYTES) {
    throw new SshipFileError('sship.file.tooLarge',
      { name, size: (file.size / 1024 / 1024).toFixed(1) }, w);
  }
  if (file.size === 0) throw new SshipFileError('sship.file.empty', {}, w);
  const bytes = await readBytes(file, w);
  return { filename: name, content_base64: encodeBase64(bytes), size: bytes.length };
}
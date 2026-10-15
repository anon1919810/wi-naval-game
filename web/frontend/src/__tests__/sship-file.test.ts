import { describe, expect, it } from 'vitest';

import {
  MAX_SSHIP_BYTES,
  SshipFileError,
  encodeBase64,
  readSshipFile as readInLanguage,
} from '../components/sshipFile';
import { zhCopy } from './locale';

const readSshipFile = (file: File) => readInLanguage(file, zhCopy);

/**
 * What this file may refuse, and what it must not touch.
 *
 * A SpringSharp source is somebody's ship: 280 positional records whose decimal
 * convention is stated by its own header. The browser therefore does not parse
 * it, decode it, re-encode it or interpret a single number in it — it reads the
 * chosen file as bytes and sends those bytes. These tests pin that, using bytes
 * that are deliberately not valid UTF-8 so any decode-then-re-encode would
 * change them, and a vector long enough to catch an implementation that spreads
 * a byte array into a string-builder call.
 */

function bytes(...values: number[]): Uint8Array<ArrayBuffer> {
  return new Uint8Array(values);
}

/** The exact bytes behind a base64 answer, without trusting the encoder. */
function decoded(encoded: string): number[] {
  return Array.from(atob(encoded), character => character.charCodeAt(0));
}

describe('encoding original bytes', () => {
  it('produces the standard alphabet, including padding', () => {
    expect(encodeBase64(bytes(0x53, 0x50, 0x0d, 0x0a, 0xff, 0x41))).toBe('U1ANCv9B');
    expect(encodeBase64(bytes(0x4d))).toBe('TQ==');
    expect(encodeBase64(bytes(0x4d, 0x61))).toBe('TWE=');
    expect(encodeBase64(bytes())).toBe('');
  });

  it('keeps bytes that no text decoder would reproduce', () => {
    // 0xff is never valid UTF-8; a decoded-and-re-encoded string would carry
    // U+FFFD here, and the server would archive a different file.
    const original = bytes(0xff, 0xfe, 0x00, 0x80, 0x0d, 0x0a, 0x3a, 0x2c);
    expect(decoded(encodeBase64(original))).toEqual(Array.from(original));
  });

  it('encodes a long file without spreading it into one call', () => {
    const original = new Uint8Array(200_000);
    for (let index = 0; index < original.length; index += 1) original[index] = index % 256;
    const encoded = encodeBase64(original);

    expect(encoded).toHaveLength(Math.ceil(original.length / 3) * 4);
    const back = decoded(encoded);
    expect(back).toHaveLength(original.length);
    expect(back[199_999]).toBe(original[199_999]);
  });
});

describe('reading a SpringSharp source file', () => {
  it('sends the chosen bytes as they are, with the name they had', async () => {
    const original = bytes(0x53, 0x50, 0x0d, 0x0a, 0xff, 0x41);
    const source = await readSshipFile(new File([original], 'Test Ship.sship'));

    expect(source.filename).toBe('Test Ship.sship');
    expect(source.content_base64).toBe('U1ANCv9B');
    expect(source.size).toBe(original.length);
  });

  it('does not touch the bytes of a file that is far too large', async () => {
    const huge = { name: 'huge.sship', size: MAX_SSHIP_BYTES + 1, arrayBuffer: () => {
      throw new Error('an oversized source must not be read');
    } } as unknown as File;

    await expect(readSshipFile(huge)).rejects.toThrow(SshipFileError);
    await expect(readSshipFile(huge)).rejects.toThrow(/1 MiB/);
  });

  it('refuses an empty file rather than previewing nothing', async () => {
    await expect(readSshipFile(new File([], 'empty.sship'))).rejects.toThrow(SshipFileError);
  });

  it('refuses a read that fails, in the reader’s own words', async () => {
    const unreadable = { name: 'broken.sship', size: 4, arrayBuffer: () => Promise.reject(new Error('disk error')) } as unknown as File;
    await expect(readSshipFile(unreadable)).rejects.toThrow(SshipFileError);
  });
});
import { describe, expect, it } from 'vitest';

import {
  BackupFileError,
  MAX_BACKUP_BYTES,
  assertEnvelopeFits,
  envelopeSize,
  findNonFiniteNumber,
  parseBackup,
  readBackupFile,
} from '../components/backupFile';

/**
 * What this file may refuse.
 *
 * A backup arrives from the reader's own disk, so every failure here is a file
 * that would otherwise be saved as something it is not. The rules that matter
 * are refusals: no coercion of a report into a project, no silent `Infinity` to
 * `null`, and no request larger than the server will accept.
 */

const canonical = {
  schema: 'plimsoll-project-1', id: 'backup-1', name: '解析方箱', revision: 3,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 }, geometry: null,
  opening_definition: 'unknown', weight_groups: [], loading_conditions: [],
};

function jsonFile(body: string, name = 'backup.json', type = 'application/json') {
  return new File([body], name, { type });
}

async function refusal(promise: Promise<unknown>): Promise<string> {
  try {
    await promise;
  } catch (cause) {
    expect(cause).toBeInstanceOf(BackupFileError);
    return (cause as BackupFileError).message;
  }
  throw new Error('expected the backup to be refused');
}

describe('reading a backup file', () => {
  it('reads a canonical project and remembers which file it was', async () => {
    const backup = await readBackupFile(jsonFile(JSON.stringify(canonical), '解析方箱-r3.json'));
    expect(backup.filename).toBe('解析方箱-r3.json');
    expect(backup.project).toEqual(canonical);
    expect(backup.size).toBeGreaterThan(0);
  });

  it('accepts one UTF-8 byte-order mark and keeps the Chinese name intact', async () => {
    const body = `﻿${JSON.stringify(canonical)}`;
    const backup = await readBackupFile(jsonFile(body));
    expect(backup.project).toEqual(canonical);
    expect((backup.project as { name: string }).name).toBe('解析方箱');
  });

  it('accepts a pretty-printed document larger than a megabyte', async () => {
    const stations = Array.from({ length: 12_000 }, (_, index) => ({
      x: index / 100, halfBreadths: Array.from({ length: 12 }, (_, point) => point / 10),
    }));
    const large = {
      ...canonical,
      name: '大体积备份',
      geometry: { kind: 'offsets', source: 'plan', estimate: true, keel_offset_m: 0,
        offsets: { stations } },
    };
    const body = JSON.stringify(large, null, 2);
    expect(new TextEncoder().encode(body).length).toBeGreaterThan(1_000_000);
    const backup = await readBackupFile(jsonFile(body, 'queen-mary.json'));
    expect(backup.project).toMatchObject({ name: '大体积备份' });
    expect((backup.project as { geometry: { offsets: { stations: unknown[] } } })
      .geometry.offsets.stations).toHaveLength(12_000);
  });
});

describe('files this refuses rather than repairs', () => {
  it('refuses a report payload and says what it actually is', async () => {
    const report = JSON.stringify({ schema: 'plimsoll-analysis-1', status: 'completed', stages: {} });
    expect(await refusal(readBackupFile(jsonFile(report, 'report.json'))))
      .toContain('计算报告');
  });

  it('refuses a file that is not JSON at all', async () => {
    expect(await refusal(readBackupFile(jsonFile('id,name\n1,box\n', 'table.csv', 'text/csv'))))
      .toContain('不是有效的 JSON');
  });

  it('refuses a JSON array, because a project is an object', async () => {
    expect(await refusal(readBackupFile(jsonFile('[{"schema":"plimsoll-project-1"}]'))))
      .toContain('顶层必须是一个 JSON 对象');
  });

  it('refuses JSON scalars for the same reason', async () => {
    for (const body of ['"a string"', '42', 'null', 'true']) {
      expect(await refusal(readBackupFile(jsonFile(body)))).toContain('顶层必须是一个 JSON 对象');
    }
  });

  it('refuses an empty file instead of pretending it parsed', async () => {
    expect(await refusal(readBackupFile(jsonFile('   \n', 'empty.json')))).toContain('空的');
  });

  it('refuses bytes that are not UTF-8 text', async () => {
    // 0xFF is never valid in UTF-8; decoding it non-strictly yields U+FFFD.
    const file = new File([new Uint8Array([0x7b, 0x22, 0xff, 0x22, 0x7d])], 'bad.json');
    expect(await refusal(readBackupFile(file))).toContain('UTF-8');
  });

  it('refuses a number JSON cannot hold, naming the path it was found at', async () => {
    // JSON.parse yields Infinity for 1e400; JSON.stringify would write null.
    const value = '{"schema":"plimsoll-project-1","id":"b","name":"n","revision":1,' +
      '"hull":{"length_m":1e400},"geometry":null,"opening_definition":"unknown",' +
      '"weight_groups":[],"loading_conditions":[]}';
    const message = await refusal(readBackupFile(jsonFile(value)));
    expect(message).toContain('$.hull.length_m');
    expect(message).toContain('不是有限数值');
  });

  it('refuses a file above the request limit without reading it', async () => {
    const file = { name: 'huge.json', size: MAX_BACKUP_BYTES + 1, arrayBuffer: () => {
      throw new Error('an oversized file must not be read');
    } } as unknown as File;
    expect(await refusal(readBackupFile(file))).toContain('8 MiB');
  });
});

describe('measuring what will actually be sent', () => {
  it('counts the UTF-8 bytes of the envelope, not of the file', () => {
    expect(envelopeSize({ project: canonical })).toBe(
      new TextEncoder().encode(JSON.stringify({ project: canonical })).length);
    // A name in Chinese costs three bytes per character on the wire.
    expect(envelopeSize({ name: '舰' })).toBe(new TextEncoder().encode('{"name":"舰"}').length);
  });

  it('refuses an envelope the server would refuse', () => {
    expect(() => assertEnvelopeFits({ note: 'x'.repeat(MAX_BACKUP_BYTES) }, '该备份'))
      .toThrow(BackupFileError);
    // The message says the real size, so a reader is not left guessing.
    expect(() => assertEnvelopeFits({ note: 'x'.repeat(MAX_BACKUP_BYTES) }, '该备份'))
      .toThrow(/超过 8 MiB/);
  });

  it('lets an envelope just under the limit through', () => {
    expect(() => assertEnvelopeFits({ project: canonical }, '该备份')).not.toThrow();
  });
});

describe('locating a non-finite number', () => {
  it('names the deepest path it reaches', () => {
    expect(findNonFiniteNumber({ a: [{ b: Number.POSITIVE_INFINITY }] })).toBe('$.a[0].b');
    expect(findNonFiniteNumber({ a: { b: -Infinity } })).toBe('$.a.b');
    expect(findNonFiniteNumber([1, [2, Number.NaN]])).toBe('$[1][1]');
  });

  it('reports nothing for a document whose numbers are all finite', () => {
    expect(findNonFiniteNumber(canonical)).toBeNull();
    expect(findNonFiniteNumber({ a: 0, b: -1, c: null, d: 'x', e: [1e308] })).toBeNull();
  });
});

describe('parsing text already in hand', () => {
  it('tolerates surrounding whitespace, as a written file has', () => {
    expect(parseBackup(`\n  ${JSON.stringify(canonical)}\n`, 'a.json', 10).project).toEqual(canonical);
  });
});

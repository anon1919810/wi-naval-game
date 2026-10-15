import { act, cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderZh as render } from './locale';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api';
import { Library } from '../pages/Library';
import * as api from '../api';
import type { ProjectView, SshipMigrationField, SshipProjectImportPreview } from '../types';

/**
 * Migrating a SpringSharp 3.0 source file, from the reader's side.
 *
 * The browser is not trusted with this format and does not pretend to be: it
 * sends the chosen bytes unchanged, shows what the server read out of them —
 * version, digest, how many fields were mapped against preserved, and what this
 * migration cannot give them — and saves only the bytes it is still holding
 * under the digest it was last shown. What these tests pin is that a second
 * file, a cancelled one, a late answer and a second press of Save can never mix
 * one file's name, bytes, digest or project into another's.
 *
 * Every fixture below is synthetic: the field records stand in for the recovered
 * 3b3 positions and describe no real ship.
 */

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, listProjects: vi.fn(), createProject: vi.fn(),
    previewProjectImport: vi.fn(), importProject: vi.fn(),
    previewSshipImport: vi.fn(), importSshipProject: vi.fn() };
});

const FIELD_COUNT = 280;
const SHA256 = 'a'.repeat(64);

const DISPOSITIONS: Array<[number, SshipMigrationField['disposition']]> = [
  [200, 'mapped'], [230, 'preserved'], [247, 'duplicate'],
];

function fieldRecords(): SshipMigrationField[] {
  return Array.from({ length: FIELD_COUNT }, (_, index) => {
    const boundary = DISPOSITIONS.find(([from]) => index === from);
    return {
      index,
      line: index + 2,
      name: index === 0 ? 'hullControl.shipNameBox.Text' : `synthetic.field${index}`,
      raw: index === 0 ? 'SYNTHETIC TEST SHIP' : index === 13 ? '300' : '',
      disposition: index >= 247 ? 'reserved' : boundary?.[1] ?? 'mapped',
      destinations: index === 0 ? ['$.name'] : [],
      reason: index >= 247 ? 'ignored padding in the source reader' : null,
    };
  });
}

const migrationPreview = (patch: Partial<SshipProjectImportPreview['migration']> = {}): SshipProjectImportPreview => ({
  source_id: 'sship-aaaaaaaaaaaaaaaaaaaaaaaa', name: 'SYNTHETIC TEST SHIP', source_revision: 1,
  geometry_kind: null,
  counts: { loading_conditions: 1, weight_groups: 1, weight_items: 0,
    damage_scenarios: 0, compartments: 0, openings: 0 },
  diagnostics: [],
  migration: {
    method_version: 'springsharp-3.0-migration-1',
    source: { filename: 'ship.sship', sha256: SHA256, byte_length: 4096, encoding: 'utf-8',
      header: 'SpringSharp Version 3.0', version: '3.0', decimal_separator: '.' },
    fields: fieldRecords(),
    counts: { mapped: 200, preserved: 30, duplicate: 17, reserved: 33 },
    diagnostics: [],
    limitations: ['no hull offsets are created; calculations that need geometry stay unavailable'],
    ...patch,
  },
});

const view = (id = 'migrated-1'): ProjectView => ({
  project_id: id, revision: 1,
  project: { schema: 'plimsoll-project-1', id, name: 'SYNTHETIC TEST SHIP', revision: 1,
    hull: {}, geometry: null, loading_conditions: [], weight_groups: [] },
});

function sourceFile(name = 'ship.sship') {
  return new File([new Uint8Array([0x53, 0x50, 0x0d, 0x0a, 0xff, 0x41])], name);
}

const jsonFile = (name = 'backup.json') => new File(['{"schema":"plimsoll-project-1"}'], name);

/** Choose a file the way a reader does: through the real input element. */
async function choose(input: HTMLElement, file: File) {
  fireEvent.change(input, { target: { files: [file] } });
  await act(async () => { await Promise.resolve(); });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (cause: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

const sshipInput = () => screen.getByLabelText('选择 SpringSharp 文件') as HTMLInputElement;
const jsonInput = () => screen.getByLabelText('选择项目备份 JSON') as HTMLInputElement;

beforeEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.previewSshipImport).mockResolvedValue(migrationPreview());
});
afterEach(() => { cleanup(); });

describe('choosing a SpringSharp source previews it and saves nothing', () => {
  it('sends the chosen bytes unchanged and shows what the server read', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile('Test Ship.sship'));

    expect(await screen.findByText('源文件版本')).toBeVisible();
    // The original bytes, not a decoded and re-encoded copy of them.
    expect(api.previewSshipImport).toHaveBeenCalledWith('Test Ship.sship', 'U1ANCv9B');
    expect(screen.getByText('3.0')).toBeVisible();
    expect(screen.getByText('Test Ship.sship')).toBeVisible();
    expect(screen.getByText(SHA256)).toBeVisible();
    expect(screen.getByText('springsharp-3.0-migration-1')).toBeVisible();

    expect(api.importSshipProject).not.toHaveBeenCalled();
    expect(api.importProject).not.toHaveBeenCalled();
    expect(api.createProject).not.toHaveBeenCalled();
  });

  it('states what the migration does not create, before anything is saved', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());

    await screen.findByText('源文件版本');
    expect(screen.getByText(/不会创建几何/)).toBeVisible();
    expect(screen.getByText(/完整重量台账或重心/)).toBeVisible();
    expect(screen.getByText(/经过历史验证/)).toBeVisible();
    // The core's own limitation is shown in its own words, not summarised away.
    expect(screen.getByText('no hull offsets are created; calculations that need geometry stay unavailable')).toBeVisible();
  });

  it('counts mapped against preserved, duplicate and reserved padding', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());

    await screen.findByText('源文件版本');
    for (const label of ['已映射', '仅保留', '重复', '填充保留', '读取字段数']) {
      expect(screen.getByText(label)).toBeVisible();
    }
    expect(screen.getByText('280')).toBeVisible();
    expect(screen.getByText('33')).toBeVisible();
  });

  it('keeps the canonical validator’s own warnings about the draft, apart from the migration’s', async () => {
    const base = migrationPreview();
    vi.mocked(api.previewSshipImport).mockResolvedValue({
      ...base,
      // What the canonical project validator says about the draft being saved.
      diagnostics: [
        { code: 'loading_conditions.empty', severity: 'warning', path: '$.loading_conditions',
          message: 'the imported draft has no loading conditions', blocking: false },
        { code: 'value.unknown', severity: 'warning', path: '$.weight_groups[0].items[0].mass_t',
          message: 'the ledger mass is unknown', blocking: false },
      ],
      migration: {
        ...base.migration!,
        // What the migration itself reported, which is a different statement.
        diagnostics: [{ code: 'sship.derived.bulged_beam_required', severity: 'warning',
          path: '$.fields[127]', message: 'the beam at the bulges is archived, not mapped',
          blocking: false }],
      },
    });
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());

    const disclosure = await screen.findByText('规范校验仍有提示（2）');
    const unknown = screen.getByText('$.weight_groups[0].items[0].mass_t');
    expect(unknown).not.toBeVisible();

    fireEvent.click(disclosure);
    expect(unknown).toBeVisible();
    expect(screen.getByText('the ledger mass is unknown')).toBeVisible();
    expect(screen.getByText('$.loading_conditions')).toBeVisible();
    // The migration's own findings and limits are still shown beside them.
    expect(screen.getByText('迁移提示（1）')).toBeVisible();
    expect(screen.getByText('$.fields[127]')).toBeVisible();
    expect(screen.getByText('the beam at the bulges is archived, not mapped')).toBeVisible();
    expect(screen.getByText('no hull offsets are created; calculations that need geometry stay unavailable')).toBeVisible();
  });

  it('keeps every source field available, but only when it is asked for', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());

    const disclosure = await screen.findByText('全部 280 个源字段');
    const row = screen.getByText('hullControl.shipNameBox.Text');
    expect(row).not.toBeVisible();
    expect(screen.getByText('SYNTHETIC TEST SHIP')).not.toBeVisible();

    fireEvent.click(disclosure);
    expect(row).toBeVisible();
    expect(screen.getByText('SYNTHETIC TEST SHIP')).toBeVisible();
    expect(screen.getByText('300')).toBeVisible();
    expect(screen.getAllByText(/ignored padding in the source reader/).length).toBe(33);
    expect(screen.getAllByText('填充保留')).toHaveLength(1);
  });

  it('saves the frozen bytes under the digest the reader was shown', async () => {
    vi.mocked(api.importSshipProject).mockResolvedValue(view());
    const onOpen = vi.fn();
    render(<Library onOpen={onOpen} />);
    await choose(sshipInput(), sourceFile());
    const field = await screen.findByLabelText('迁移后的项目名称');
    expect(field).toHaveValue('SYNTHETIC TEST SHIP');

    fireEvent.change(field, { target: { value: ' 迁移的测试舰 ' } });
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));

    await waitFor(() => expect(api.importSshipProject).toHaveBeenCalledTimes(1));
    expect(api.importSshipProject).toHaveBeenCalledWith('ship.sship', 'U1ANCv9B', SHA256, '迁移的测试舰');
    expect(onOpen).toHaveBeenCalledWith('migrated-1');
  });

  it('will not save a name the reader has not actually filled in', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());
    const field = await screen.findByLabelText('迁移后的项目名称');
    fireEvent.change(field, { target: { value: '   ' } });

    expect(screen.getByRole('button', { name: '保存为新项目' })).toBeDisabled();
    fireEvent.submit(field.closest('form')!);
    expect(api.importSshipProject).not.toHaveBeenCalled();
  });
});

describe('the two choosers never share a source', () => {
  it('replacing the source drops the previous preview at once', async () => {
    vi.mocked(api.previewSshipImport)
      .mockResolvedValueOnce(migrationPreview())
      .mockResolvedValueOnce(migrationPreview({
        source: { filename: 'second.sship', sha256: 'b'.repeat(64), byte_length: 2048, encoding: 'utf-8',
          header: 'SpringSharp Version 3,0', version: '3,0', decimal_separator: ',' },
        fields: fieldRecords(),
      }));
    render(<Library onOpen={vi.fn()} />);
    const input = sshipInput();
    await choose(input, sourceFile('first.sship'));
    await screen.findByText(SHA256);

    await choose(input, sourceFile('second.sship'));
    expect(screen.getAllByText('second.sship').length).toBeGreaterThan(0);
    expect(screen.queryByText(SHA256)).toBeNull();
    expect(screen.queryByText('first.sship')).toBeNull();
  });

  it('choosing a JSON backup drops a SpringSharp preview entirely', async () => {
    vi.mocked(api.previewProjectImport).mockResolvedValue({
      source_id: 'backup-1', name: '备份里的名字', source_revision: 3, geometry_kind: 'offsets',
      counts: { loading_conditions: 0, weight_groups: 0, weight_items: 0,
        damage_scenarios: 0, compartments: 0, openings: 0 },
      diagnostics: [],
    });
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile('ship.sship'));
    await screen.findByText(SHA256);

    await choose(jsonInput(), jsonFile());
    expect(await screen.findByText('备份内名称')).toBeVisible();
    expect(screen.queryByText(SHA256)).toBeNull();
    expect(screen.queryByLabelText('迁移后的项目名称')).toBeNull();
    // The two flows keep their own endpoints.
    expect(api.previewProjectImport).toHaveBeenCalledTimes(1);
    expect(api.previewSshipImport).toHaveBeenCalledTimes(1);
  });

  it('cancelling returns the section to nothing', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile('ship.sship'));
    await screen.findByText('源文件版本');

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByText('源文件版本')).toBeNull();
    expect(screen.queryByText('ship.sship')).toBeNull();
    expect(screen.queryByRole('button', { name: '保存为新项目' })).toBeNull();
    expect(sshipInput()).toHaveFocus();
  });
});

describe('answers that arrive for a question nobody is asking', () => {
  it('never shows a preview that answers after another source was chosen', async () => {
    const first = deferred<SshipProjectImportPreview>();
    vi.mocked(api.previewSshipImport)
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce(migrationPreview({
        source: { filename: 'second.sship', sha256: 'c'.repeat(64), byte_length: 2048, encoding: 'utf-8',
          header: 'SpringSharp Version 3.0', version: '3.0', decimal_separator: '.' },
        fields: fieldRecords(),
      }));
    render(<Library onOpen={vi.fn()} />);
    const input = sshipInput();
    await choose(input, sourceFile('first.sship'));
    await waitFor(() => expect(api.previewSshipImport).toHaveBeenCalledTimes(1));
    await choose(input, sourceFile('second.sship'));
    await waitFor(() => expect(screen.getAllByText('second.sship').length).toBeGreaterThan(0));

    await act(async () => {
      first.resolve(migrationPreview());
      await first.promise;
    });
    expect(screen.queryByText(SHA256)).toBeNull();
    expect(screen.getAllByText('second.sship').length).toBeGreaterThan(0);
  });

  it('never shows an answer that arrives after the reader cancelled', async () => {
    const pending = deferred<SshipProjectImportPreview>();
    vi.mocked(api.previewSshipImport).mockReturnValue(pending.promise);
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());
    await waitFor(() => expect(api.previewSshipImport).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    await act(async () => { pending.resolve(migrationPreview()); await pending.promise; });

    expect(screen.queryByText('源文件版本')).toBeNull();
    expect(screen.queryByRole('button', { name: '保存为新项目' })).toBeNull();
  });

  it('does not navigate a save that answers after the library is gone', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.importSshipProject).mockReturnValue(pending.promise);
    const onOpen = vi.fn();
    const { unmount } = render(<Library onOpen={onOpen} />);
    await choose(sshipInput(), sourceFile());
    await screen.findByLabelText('迁移后的项目名称');
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await screen.findByRole('button', { name: '保存中…' });
    unmount();

    await act(async () => { pending.resolve(view()); await pending.promise; });
    expect(onOpen).not.toHaveBeenCalled();
  });
});

describe('a save that fails is a retry, not a restart', () => {
  it('keeps the file, the preview and the entered name', async () => {
    vi.mocked(api.importSshipProject)
      .mockRejectedValueOnce(new ApiError(409, [{ code: 'sship.source_mismatch', severity: 'error',
        path: '$.source_sha256', message: 'the source file changed since it was previewed' }]))
      .mockResolvedValueOnce(view('migrated-2'));
    const onOpen = vi.fn();
    render(<Library onOpen={onOpen} />);
    await choose(sshipInput(), sourceFile('kept.sship'));
    const field = await screen.findByLabelText('迁移后的项目名称');
    fireEvent.change(field, { target: { value: '重试用的名字' } });

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    expect(await screen.findByText('$.source_sha256：the source file changed since it was previewed')).toBeVisible();
    expect(screen.getByText('sship.source_mismatch')).toBeVisible();
    expect(screen.getByText('kept.sship')).toBeVisible();
    expect(screen.getByLabelText('迁移后的项目名称')).toHaveValue('重试用的名字');
    expect(onOpen).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('migrated-2'));
    expect(api.importSshipProject).toHaveBeenLastCalledWith('kept.sship', 'U1ANCv9B', SHA256, '重试用的名字');
  });

  it('refuses a second press while one save is in flight', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.importSshipProject).mockReturnValue(pending.promise);
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());
    const field = await screen.findByLabelText('迁移后的项目名称');

    act(() => {
      fireEvent.submit(field.closest('form')!);
      fireEvent.submit(field.closest('form')!);
    });
    const saving = await screen.findByRole('button', { name: '保存中…' });
    expect(saving).toBeDisabled();
    fireEvent.click(saving);
    fireEvent.click(saving);
    expect(api.importSshipProject).toHaveBeenCalledTimes(1);

    await act(async () => { pending.resolve(view()); await pending.promise; });
  });

  it('locks the other creation while a migration is in flight', async () => {
    vi.mocked(api.importSshipProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());
    await screen.findByLabelText('迁移后的项目名称');

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await screen.findByRole('button', { name: '保存中…' });
    expect(jsonInput()).toBeDisabled();
    expect(sshipInput()).toBeDisabled();
    for (const label of ['解析方箱', '通用试验船', 'HMS Queen Mary']) {
      for (const entry of screen.getAllByRole('button', { name: new RegExp(label) })) expect(entry).toBeDisabled();
    }
    expect(api.createProject).not.toHaveBeenCalled();
  });
});

describe('a file this refuses before the server sees it', () => {
  it('shows the size limit and asks for no preview', async () => {
    const huge = { name: 'huge.sship', size: 1024 * 1024 + 1, arrayBuffer: () => {
      throw new Error('an oversized source must not be read');
    } } as unknown as File;
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), huge);

    expect(await screen.findByText('这个 SpringSharp 文件无法导入')).toBeVisible();
    expect(screen.getByText(/超过 1 MiB/)).toBeVisible();
    expect(api.previewSshipImport).not.toHaveBeenCalled();
  });

  it('shows the server’s refusal with its code, and offers another file', async () => {
    vi.mocked(api.previewSshipImport).mockRejectedValue(new ApiError(422, [
      { code: 'sship.version_unsupported', severity: 'error', path: '$.source.header',
        message: 'SpringSharp Version 2.0 is not a supported source', blocking: true },
    ]));
    render(<Library onOpen={vi.fn()} />);
    await choose(sshipInput(), sourceFile());

    const failure = (await screen.findByText('$.source.header：SpringSharp Version 2.0 is not a supported source')).closest('li')!;
    expect(within(failure).getByText('错误')).toBeVisible();
    expect(screen.getByText('sship.version_unsupported')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByText('sship.version_unsupported')).toBeNull();
    expect(sshipInput()).toBeEnabled();
  });
});
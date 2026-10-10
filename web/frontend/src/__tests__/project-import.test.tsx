import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api';
import { Library } from '../pages/Library';
import * as api from '../api';
import type { ProjectDocument, ProjectImportPreview, ProjectView } from '../types';

/**
 * Restoring a backup, from the reader's side.
 *
 * These are the properties a reader depends on: choosing a file reads it and
 * previews it but saves nothing; the preview is described in the server's words
 * with its field paths intact; a name is confirmed explicitly; a failed save
 * keeps everything so it can be retried; a cancelled or superseded read never
 * comes back; and a page that is gone is never navigated.
 */

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, listProjects: vi.fn(), createProject: vi.fn(),
    previewProjectImport: vi.fn(), importProject: vi.fn() };
});

const backup: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'backup-source-0000', name: '解析方箱 备份', revision: 3,
  hull: { length_m: 90, beam_m: 20, draft_m: 4 }, geometry: null,
  opening_definition: 'unknown', weight_groups: [], loading_conditions: [],
};

const preview = (patch: Partial<ProjectImportPreview> = {}): ProjectImportPreview => ({
  source_id: backup.id, name: backup.name, source_revision: 3, geometry_kind: 'offsets',
  counts: { loading_conditions: 2, weight_groups: 9, weight_items: 2,
    damage_scenarios: 1, compartments: 1, openings: 2 },
  diagnostics: [], ...patch,
});

const view = (id = 'restored-1'): ProjectView => ({
  project_id: id, revision: 1, project: { ...backup, id, name: '解析方箱 备份', revision: 1 },
});

function jsonFile(body: string, name = 'backup.json') {
  return new File([body], name, { type: 'application/json' });
}

function backupFile(name = '解析方箱-r3.json') {
  return jsonFile(JSON.stringify(backup), name);
}

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

const fileInput = () => screen.getByLabelText('选择项目备份 JSON') as HTMLInputElement;

beforeEach(() => {
  cleanup();
  vi.resetAllMocks();
  vi.mocked(api.listProjects).mockResolvedValue([]);
  vi.mocked(api.previewProjectImport).mockResolvedValue(preview());
});
afterEach(() => { cleanup(); });

describe('choosing a backup previews it and saves nothing', () => {
  it('shows the file, the server description, and never posts an import', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    await screen.findByText('备份内名称');
    expect(screen.getByText('解析方箱-r3.json')).toBeVisible();
    expect(screen.getByText('备份内名称')).toBeVisible();
    expect(screen.getByText('备份内 ID')).toBeVisible();
    expect(screen.getByText(backup.id)).toBeVisible();
    expect(screen.getByText('修订 3')).toBeVisible();
    expect(screen.getByText('型值表（内嵌）')).toBeVisible();
    // The counts are the file's own, in the order a reader reads a project.
    for (const label of ['载荷工况', '重量分组', '重量条目', '破损场景', '舱室', '开口']) {
      expect(screen.getByText(label)).toBeVisible();
    }
    expect(screen.getAllByText('2')).toHaveLength(3);

    expect(api.previewProjectImport).toHaveBeenCalledWith(backup);
    expect(api.importProject).not.toHaveBeenCalled();
    expect(api.createProject).not.toHaveBeenCalled();
  });

  it('says the preview is a file-structure check, not a readiness claim', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByText('备份内名称');
    expect(screen.getByText(/不代表计算已就绪或经过历史验证/)).toBeVisible();
  });

  it('confirms a name explicitly and says what importing does not do', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    const field = await screen.findByLabelText('恢复后的项目名称');
    expect(field).toHaveValue('解析方箱 备份');
    expect(screen.getByText('导入只恢复项目输入，不恢复运行记录；不会覆盖已有项目。')).toBeVisible();

    fireEvent.change(field, { target: { value: ' 恢复的解析方箱 ' } });
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));

    await waitFor(() => expect(api.importProject).toHaveBeenCalledTimes(1));
    expect(api.importProject).toHaveBeenCalledWith(backup, '恢复的解析方箱');
  });

  it('opens the new project exactly once after a confirmed save', async () => {
    const onOpen = vi.fn();
    vi.mocked(api.importProject).mockResolvedValue(view());
    render(<Library onOpen={onOpen} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));

    await waitFor(() => expect(onOpen).toHaveBeenCalledTimes(1));
    expect(onOpen).toHaveBeenCalledWith('restored-1');
  });

  it('never silently falls back to the backup name when the reader cleared it', async () => {
    vi.mocked(api.importProject).mockResolvedValue(view());
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    const field = await screen.findByLabelText('恢复后的项目名称');
    fireEvent.change(field, { target: { value: '   ' } });

    // A blank name cannot be confirmed: the button is the reader's consent.
    expect(screen.getByRole('button', { name: '保存为新项目' })).toBeDisabled();
    fireEvent.submit(field.closest('form')!);
    expect(api.importProject).not.toHaveBeenCalled();
  });
});

describe('warnings are shown with their field paths', () => {
  it('lists canonical warnings under the preview', async () => {
    vi.mocked(api.previewProjectImport).mockResolvedValue(preview({ diagnostics: [
      { code: 'value.unknown', severity: 'warning', path: '$.weight_groups[0].items[0].mass_t',
        message: 'value is unknown; downstream calculations must not substitute zero', blocking: false },
      { code: 'source.missing', severity: 'warning', path: '$.weight_groups[0].items[0].source',
        message: 'weight item has no source metadata', blocking: false },
    ] }));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    expect(await screen.findByText('校验提示（2）')).toBeVisible();
    expect(screen.getByText('$.weight_groups[0].items[0].mass_t')).toBeVisible();
    expect(screen.getByText('$.weight_groups[0].items[0].source')).toBeVisible();
    expect(screen.getByText('source.missing')).toBeVisible();
    expect(screen.getByText('value.unknown')).toBeVisible();
  });

  it('lets the reader disclose every remaining warning with its code and path', async () => {
    vi.mocked(api.previewProjectImport).mockResolvedValue(preview({ diagnostics: Array.from(
      { length: 6 }, (_, index) => ({ code: 'value.unknown', severity: 'warning',
        path: `$.weight_groups[${index}].items[0].mass_t`, message: `unknown ${index}` })) }));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    await screen.findByText('校验提示（6）');
    const hidden = screen.getByText('unknown 5');
    expect(hidden).not.toBeVisible();
    fireEvent.click(screen.getByText('查看其余 2 条校验提示'));
    expect(hidden).toBeVisible();
    expect(screen.getByText('$.weight_groups[5].items[0].mass_t')).toBeVisible();
  });

  it('shows no warnings heading for a file the validator is content with', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByText('备份内名称');
    expect(screen.queryByText(/校验提示/)).toBeNull();
  });
});

describe('files and answers this refuses', () => {
  it('refuses a calculation report as a file, without asking the server', async () => {
    const report = jsonFile(JSON.stringify({ schema: 'plimsoll-analysis-1', stages: {} }), 'report.json');
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), report);

    expect(await screen.findByText('这个备份无法导入')).toBeVisible();
    expect(screen.getByText(/这是计算报告/)).toBeVisible();
    expect(api.previewProjectImport).not.toHaveBeenCalled();
    expect(api.importProject).not.toHaveBeenCalled();
  });

  it('refuses an oversized file and states the limit', async () => {
    const huge = { name: 'huge.json', size: 9 * 1024 * 1024, arrayBuffer: () => {
      throw new Error('an oversized file must not be read');
    } } as unknown as File;
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), huge);

    expect(await screen.findByText(/超过 8 MiB/)).toBeVisible();
    expect(api.previewProjectImport).not.toHaveBeenCalled();
  });

  it('shows a canonical field error with its path when the server refuses', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new ApiError(422, [
      { code: 'geometry.kind_unsupported', severity: 'error', path: '$.geometry.kind',
        message: "unsupported geometry kind 'hull_table'", blocking: true },
    ]));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    expect(await screen.findByText(/\$\.geometry\.kind：unsupported geometry kind/)).toBeVisible();
    expect(screen.getByText('geometry.kind_unsupported')).toBeVisible();
    expect(api.importProject).not.toHaveBeenCalled();
  });

  it('shows a plain server message when the answer is a string', async () => {
    vi.mocked(api.previewProjectImport)
      .mockRejectedValue(new ApiError(422, 'external geometry paths are unavailable on the web'));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    expect(await screen.findByText('external geometry paths are unavailable on the web')).toBeVisible();
  });

  it('falls back to a readable message when the failure is not the server’s', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new Error(''));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());

    expect(await screen.findByText('导入失败，请检查备份文件后重试。')).toBeVisible();
  });

  it('offers another file instead of leaving the reader stuck', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new ApiError(422, 'unsupported'));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByText('这个备份无法导入');

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByText('这个备份无法导入')).toBeNull();
    expect(screen.queryByText('解析方箱-r3.json')).toBeNull();
    expect(fileInput()).toBeEnabled();
  });
});

describe('a recoverable save failure keeps the work', () => {
  it('retains the file, the preview and the entered name, and allows one retry', async () => {
    const onOpen = vi.fn();
    vi.mocked(api.importProject)
      .mockRejectedValueOnce(new ApiError(503, 'storage is temporarily unavailable'))
      .mockResolvedValueOnce(view('restored-2'));
    render(<Library onOpen={onOpen} />);
    await choose(fileInput(), backupFile('保留的备份.json'));
    const field = await screen.findByLabelText('恢复后的项目名称');
    fireEvent.change(field, { target: { value: '重试用的名字' } });

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    expect(await screen.findByText('storage is temporarily unavailable')).toBeVisible();
    // Everything the reader did survives: same file, same preview, same name.
    expect(screen.getByText('保留的备份.json')).toBeVisible();
    expect(screen.getByText('备份内名称')).toBeVisible();
    expect(screen.getByLabelText('恢复后的项目名称')).toHaveValue('重试用的名字');
    expect(onOpen).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await waitFor(() => expect(onOpen).toHaveBeenCalledWith('restored-2'));
    expect(api.importProject).toHaveBeenLastCalledWith(backup, '重试用的名字');
  });

  it('names the failure while it is saving, and refuses a second press', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.importProject).mockReturnValue(pending.promise);
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    const field = await screen.findByLabelText('恢复后的项目名称');

    // Two events in one render batch also need to produce only one request.
    act(() => {
      fireEvent.submit(field.closest('form')!);
      fireEvent.submit(field.closest('form')!);
    });
    const saving = await screen.findByRole('button', { name: '保存中…' });
    expect(saving).toBeDisabled();
    // A second press while one is in flight cannot create a second project.
    fireEvent.click(saving);
    fireEvent.click(saving);
    expect(api.importProject).toHaveBeenCalledTimes(1);

    await act(async () => { pending.resolve(view()); await pending.promise; });
  });
});

describe('two creations never overlap', () => {
  it.each(['template', 'import'] as const)('locks the other creation synchronously when %s starts first', async first => {
    vi.mocked(api.createProject).mockReturnValue(new Promise(() => {}));
    vi.mocked(api.importProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    const field = await screen.findByLabelText('恢复后的项目名称');
    const template = screen.getByRole('button', { name: /解析方箱/ });
    const form = field.closest('form')!;
    act(() => {
      if (first === 'template') {
        fireEvent.click(template);
        fireEvent.submit(form);
      } else {
        fireEvent.submit(form);
        fireEvent.click(template);
      }
    });
    expect(api.createProject).toHaveBeenCalledTimes(first === 'template' ? 1 : 0);
    expect(api.importProject).toHaveBeenCalledTimes(first === 'import' ? 1 : 0);
  });

  it('disables template and blank creation while a restore is in flight', async () => {
    vi.mocked(api.importProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');

    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await screen.findByRole('button', { name: '保存中…' });
    for (const label of ['解析方箱', '通用试验船', 'HMS Queen Mary']) {
      expect(screen.getByRole('button', { name: new RegExp(label) })).toBeDisabled();
    }
    expect(screen.getByRole('button', { name: '创建空白项目' })).toBeDisabled();
    expect(api.createProject).not.toHaveBeenCalled();
  });

  it('disables the restore while a template is being created', async () => {
    vi.mocked(api.createProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    await screen.findByText('还没有舰船项目');
    fireEvent.click(screen.getByRole('button', { name: /解析方箱/ }));

    await screen.findByRole('button', { name: /解析方箱.*建立中/ });
    expect(fileInput()).toBeDisabled();
    expect(api.previewProjectImport).not.toHaveBeenCalled();
  });
});

describe('answers that arrive for a question nobody is asking', () => {
  it('does not show a preview that answers after another file was chosen', async () => {
    const first = deferred<ProjectImportPreview>();
    vi.mocked(api.previewProjectImport)
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce(preview({ name: '第二个文件', source_id: 'backup-second' }));
    render(<Library onOpen={vi.fn()} />);
    const input = fileInput();
    await choose(input, backupFile('第一个.json'));
    await waitFor(() => expect(api.previewProjectImport).toHaveBeenCalledTimes(1));
    expect(input).toBeEnabled();

    // The reader changes their mind before the first answer lands.
    await choose(input, backupFile('第二个.json'));
    expect(await screen.findByText('第二个文件')).toBeVisible();

    await act(async () => {
      first.resolve(preview({ name: '过期预览', source_id: 'backup-first' }));
      await first.promise;
    });
    expect(screen.queryByText('过期预览')).toBeNull();
    expect(screen.queryByText('backup-first')).toBeNull();
    expect(screen.getByText('第二个文件')).toBeVisible();
  });

  it('does not resurrect a preview after the reader cancels', async () => {
    const pending = deferred<ProjectImportPreview>();
    vi.mocked(api.previewProjectImport).mockReturnValue(pending.promise);
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await waitFor(() => expect(api.previewProjectImport).toHaveBeenCalledTimes(1));

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(screen.queryByText('解析方箱-r3.json')).toBeNull();
    expect(screen.getByRole('button', { name: /解析方箱/ })).toBeEnabled();

    await act(async () => { pending.resolve(preview()); await pending.promise; });
    expect(screen.queryByText('备份内名称')).toBeNull();
    expect(screen.queryByRole('button', { name: '保存为新项目' })).toBeNull();
  });

  it('does not navigate a save that answers after the reader left the library', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.importProject).mockReturnValue(pending.promise);
    const onOpen = vi.fn();
    const { unmount } = render(<Library onOpen={onOpen} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await screen.findByRole('button', { name: '保存中…' });
    unmount();

    await act(async () => { pending.resolve(view()); await pending.promise; });
    // The project really was created, but nobody is here to open it.
    expect(onOpen).not.toHaveBeenCalled();
    expect(document.body.textContent).toBe('');
  });

  it('does not speak a save failure into a library that is already gone', async () => {
    const pending = deferred<ProjectView>();
    vi.mocked(api.importProject).mockReturnValue(pending.promise);
    const { unmount } = render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');
    fireEvent.click(screen.getByRole('button', { name: '保存为新项目' }));
    await screen.findByRole('button', { name: '保存中…' });
    unmount();

    await act(async () => {
      pending.reject(new ApiError(500, 'late failure'));
      await pending.promise.catch(() => {});
    });
    expect(document.body.textContent).toBe('');
  });

  it('gives the file field back its focus after a cancel, for the next choice', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');

    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(fileInput()).toHaveFocus();
  });
});

describe('the library keeps its own behaviour', () => {
  it('releases creation controls when previewing has finished', async () => {
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByLabelText('恢复后的项目名称');
    expect(fileInput()).toBeEnabled();
    expect(screen.getByRole('button', { name: /解析方箱/ })).toBeEnabled();
    expect(screen.getByRole('button', { name: '保存为新项目' })).toBeEnabled();
  });

  it('allows the same file to be retried after a preview failure', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValueOnce(new Error('temporary preview failure'));
    render(<Library onOpen={vi.fn()} />);
    const file = backupFile();
    await choose(fileInput(), file);
    await screen.findByText('temporary preview failure');
    expect(fileInput()).toBeEnabled();
    expect(fileInput().value).toBe('');
    expect(screen.getByRole('button', { name: /解析方箱/ })).toBeEnabled();
    await choose(fileInput(), file);
    await screen.findByLabelText('恢复后的项目名称');
    expect(api.previewProjectImport).toHaveBeenCalledTimes(2);
    expect(screen.queryByText('temporary preview failure')).toBeNull();
  });

  it('prevents two blank creations submitted before the next render', async () => {
    vi.mocked(api.createProject).mockReturnValue(new Promise(() => {}));
    render(<Library onOpen={vi.fn()} />);
    const field = screen.getByLabelText('新项目名称');
    fireEvent.change(field, { target: { value: 'new baseline' } });
    act(() => {
      fireEvent.submit(field.closest('form')!);
      fireEvent.submit(field.closest('form')!);
    });
    expect(api.createProject).toHaveBeenCalledTimes(1);
    expect(fileInput()).toBeDisabled();
  });

  it('still reads the list, and a failed read is not a failed import', async () => {
    vi.mocked(api.listProjects).mockRejectedValue(new Error('项目库暂时不可达'));
    render(<Library onOpen={vi.fn()} />);
    expect(await screen.findByText('无法读取项目库')).toBeVisible();

    // Nothing about choosing a backup depends on being able to list projects.
    await choose(fileInput(), backupFile());
    expect(await screen.findByText('备份内名称')).toBeVisible();
  });

  it('points an anonymous reader at this section instead of a manual procedure', async () => {
    render(<Library onOpen={vi.fn()} anonymous />);
    fireEvent.click(await screen.findByText('保存与恢复说明'));
    const note = within(screen.getByRole('note')).getByText(/「下载项目 JSON」/);
    expect(note).toHaveTextContent('从备份恢复');
    // The distinction that matters is kept exactly as it was.
    expect(screen.getByText(/运行页导出的 JSON\/CSV 是计算报告，不是项目备份/)).toBeVisible();
  });
});

describe('pending file work can be retired', () => {
  it('cancels a slow file read before it can contact the server', async () => {
    const reading = deferred<ArrayBuffer>();
    const file = backupFile('slow.json');
    Object.defineProperty(file, 'arrayBuffer', { value: () => reading.promise });
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), file);
    expect(screen.getByRole('status')).toHaveTextContent('正在读取备份');
    expect(fileInput()).toBeEnabled();
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(fileInput()).toHaveFocus();
    expect(screen.getByRole('button', { name: /解析方箱/ })).toBeEnabled();
    await act(async () => {
      reading.resolve(new TextEncoder().encode(JSON.stringify(backup)).buffer);
      await reading.promise;
    });
    expect(api.previewProjectImport).not.toHaveBeenCalled();
    expect(screen.queryByText('slow.json')).toBeNull();
  });

  it('ignores a file read replaced by a newer file', async () => {
    const reading = deferred<ArrayBuffer>();
    const file = backupFile('slow.json');
    Object.defineProperty(file, 'arrayBuffer', { value: () => reading.promise });
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), file);
    await choose(fileInput(), backupFile('current.json'));
    await screen.findByLabelText('恢复后的项目名称');
    await act(async () => {
      reading.resolve(new TextEncoder().encode(JSON.stringify({ ...backup, name: 'stale file' })).buffer);
      await reading.promise;
    });
    expect(api.previewProjectImport).toHaveBeenCalledTimes(1);
    expect(screen.getByText('current.json')).toBeVisible();
    expect(screen.queryByText('slow.json')).toBeNull();
  });
});

describe('all server refusal details remain available', () => {
  it('keeps warnings distinct from blocking errors in a refused document', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new ApiError(422, [
      { code: 'id.invalid', severity: 'error', path: '$.id', message: 'invalid identity' },
      { code: 'value.unknown', severity: 'warning', path: '$.hull.mass_t', message: 'unknown mass' },
    ]));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    const error = (await screen.findByText('$.id：invalid identity')).closest('li')!;
    const warning = screen.getByText('$.hull.mass_t：unknown mass').closest('li')!;
    expect(within(error).getByText('错误')).toBeVisible();
    expect(within(warning).getByText('提示')).toBeVisible();
    expect(within(warning).queryByText('错误')).toBeNull();
  });

  it('discloses errors beyond the first four, retaining their diagnostic code', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new ApiError(422, Array.from(
      { length: 6 }, (_, index) => ({ code: `invalid.${index}`, severity: 'error',
        path: `$.field${index}`, message: `invalid value ${index}`, blocking: true }))));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    await screen.findByText('这个备份无法导入');
    const last = screen.getByText('$.field5：invalid value 5');
    expect(last).not.toBeVisible();
    fireEvent.click(screen.getByText('查看其余 2 条校验信息'));
    expect(last).toBeVisible();
    expect(screen.getByText('invalid.5')).toBeVisible();
  });

  it('renders request validation locations and messages as readable text', async () => {
    vi.mocked(api.previewProjectImport).mockRejectedValue(new ApiError(422, [
      { type: 'dict_type', loc: ['body', 'project'], msg: 'Input should be a valid dictionary', input: [] },
    ]));
    render(<Library onOpen={vi.fn()} />);
    await choose(fileInput(), backupFile());
    expect(await screen.findByText('body.project：Input should be a valid dictionary')).toBeVisible();
    expect(screen.getByText('dict_type')).toBeVisible();
    expect(screen.queryByText(/"loc"/)).toBeNull();
  });
});

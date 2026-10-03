import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument, RunView } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn(), getRun: vi.fn() };
});

const miscRows = [
  { row: 'hull_below', label: 'Hull below water', source: 'No positional miscellaneous-weight breakdown was located', typed: { mass_t: null }, weight_item_ids: [] as string[] },
  { row: 'hull_above', label: 'Hull above water', source: 'No positional miscellaneous-weight breakdown was located', typed: { mass_t: null }, weight_item_ids: [] as string[] },
  { row: 'on_deck', label: 'On deck', source: 'No positional miscellaneous-weight breakdown was located', typed: { mass_t: null }, weight_item_ids: [] as string[] },
  { row: 'above_deck', label: 'Above deck', source: 'No positional miscellaneous-weight breakdown was located', typed: { mass_t: null }, weight_item_ids: [] as string[] },
  { row: 'void', label: 'Void', source: 'No positional miscellaneous-weight breakdown was located', typed: { mass_t: null }, weight_item_ids: [] as string[] },
];

const weaponsProject: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '玛丽皇后号', revision: 1,
  hull: { length_m: 213.4 }, geometry: null, weight_groups: [],
  loading_conditions: [{ id: 'normal-engineering', label: '正常载荷' }],
  systems: {
    weapons: {
      torpedo: {
        installed_tubes: 2,
        page_rows: [
          { row: 'torpedo_main', label: 'Torpedo tubes (main)', source: 'Navypedia / 维基', typed: { tubes: 2, carried: 14, diameter_mm: 533.0, length_m: null, arrangement: 'submerged beam' }, weight_item_ids: ['torpedo-launch-outfit', 'torpedoes'] },
          { row: 'torpedo_secondary', label: 'Torpedo tubes (secondary)', source: '未采集', typed: { tubes: null, carried: null, diameter_mm: null, length_m: null, arrangement: null }, weight_item_ids: [] },
          { row: 'mines', label: 'Mines', source: '未采集', typed: { count: null, kind: null }, weight_item_ids: [] },
          { row: 'depth_charges', label: 'Depth charges', source: '未采集', typed: { count: null, kind: null }, weight_item_ids: [] },
        ],
        weight_item_ids: ['torpedo-launch-outfit', 'torpedoes'],
      },
      misc_weight: {
        status: 'absent',
        reason: 'no sourced positional breakdown',
        page_rows: miscRows,
      },
    },
  },
};

function findWeaponsLeaf(project: ProjectDocument, leafId: string): Record<string, unknown> {
  const weapons = (project.systems as Record<string, unknown>).weapons as Record<string, unknown>;
  return weapons[leafId] as Record<string, unknown>;
}
// Read the weapons object actually submitted on the most recent save.
function savedWeapons(): Record<string, unknown> {
  const calls = vi.mocked(api.saveProject).mock.calls;
  const last = calls[calls.length - 1][1] as { project: ProjectDocument };
  return (last.project.systems as Record<string, unknown>).weapons as Record<string, unknown>;
}
function savedLeaf(leafId: string): Record<string, unknown> {
  return findWeaponsLeaf({ systems: { weapons: savedWeapons() } } as unknown as ProjectDocument, leafId);
}
async function openWeapons(project: ProjectDocument) {
  vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project });
  vi.mocked(api.listRuns).mockResolvedValue([]);
  vi.mocked(api.saveProject).mockImplementation(async (_id, input) => ({
    project_id: 'p1', revision: input.base_revision + 1, project: input.project,
  }));
  render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
  fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
}
async function saveDraft() {
  const previousCalls = vi.mocked(api.saveProject).mock.calls.length;
  fireEvent.click(screen.getByRole('button', { name: '保存修订' }));
  await waitFor(() => expect(api.saveProject).toHaveBeenCalledTimes(previousCalls + 1));
  await waitFor(() => expect(screen.getByRole('button', { name: '保存修订' })).toBeDisabled());
}

beforeEach(() => { cleanup(); vi.clearAllMocks(); });

describe('weapons page form', () => {
  it('writes a declared torpedo typed field and keeps the row source on save', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: weaponsProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: weaponsProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
    const input = await screen.findByLabelText('torpedo torpedo_main 管数');
    fireEvent.change(input, { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const torpedo = findWeaponsLeaf(submitted.project, 'torpedo');
    const rows = torpedo.page_rows as Array<Record<string, unknown>>;
    const main = rows.find(r => r.row === 'torpedo_main')!;
    expect((main.typed as Record<string, unknown>).tubes).toBe(4);
    // The declared source on the row is preserved, not overwritten by the edit.
    expect(main.source).toBe('Navypedia / 维基');
  });

  it('writes a declared misc-zone mass into the contract', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: weaponsProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: weaponsProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
    fireEvent.change(screen.getByLabelText('选择武器分区'), { target: { value: 'misc_weight' } });
    const input = await screen.findByLabelText('misc_weight hull_below 质量 · t');
    fireEvent.change(input, { target: { value: '12.5' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const misc = findWeaponsLeaf(submitted.project, 'misc_weight');
    const rows = misc.page_rows as Array<Record<string, unknown>>;
    const zone = rows.find(r => r.row === 'hull_below')!;
    expect((zone.typed as Record<string, unknown>).mass_t).toBe(12.5);
    expect(zone.source).toBe('No positional miscellaneous-weight breakdown was located');
  });

  it('does not write 0 when a misc-zone mass is cleared', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: weaponsProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: weaponsProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
    fireEvent.change(screen.getByLabelText('选择武器分区'), { target: { value: 'misc_weight' } });
    const input = await screen.findByLabelText('misc_weight hull_below 质量 · t');
    fireEvent.change(input, { target: { value: '12.5' } });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const misc = findWeaponsLeaf(submitted.project, 'misc_weight');
    const rows = misc.page_rows as Array<Record<string, unknown>>;
    const zone = rows.find(r => r.row === 'hull_below')!;
    expect((zone.typed as Record<string, unknown>).mass_t).not.toBe(0);
    expect((zone.typed as Record<string, unknown>).mass_t).toBeNull();
  });

  it('shows a prompt instead of a zero aggregate when there is no run', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: weaponsProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
    // No run -> the aggregate region explains it must be computed, never shows 0.
    expect(await screen.findByText('鱼雷：保存并运行后显示聚合值')).toBeVisible();
  });

  describe('blank project declaration', () => {
    const blank: ProjectDocument = {
      schema: 'plimsoll-project-1', id: 'p1', name: '空白项目', revision: 1,
      hull: { loa_m: 90, beam_m: 12 }, geometry: null,
      weight_groups: [{ id: 'outfit', label: 'Outfit', items: [
        { id: 'torpedoes', mass_t: 14 }, { id: 'stores', mass_t: 6 }] }],
      loading_conditions: [{ id: 'normal-engineering', label: '正常载荷' }],
    };

    it('creates the torpedo leaf with a row, provenance, tri-state estimate and binding', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加鱼雷分区' }));
      fireEvent.change(screen.getByLabelText('新增行模板'), { target: { value: 'torpedo_main' } });
      fireEvent.click(screen.getByRole('button', { name: '添加声明行' }));
      fireEvent.change(screen.getByLabelText('torpedo torpedo_main 管数'), { target: { value: '4' } });
      fireEvent.change(screen.getByLabelText('torpedo torpedo_main 行来源'), { target: { value: 'Navypedia' } });
      fireEvent.change(screen.getByLabelText('torpedo torpedo_main 估算状态'), { target: { value: 'estimate' } });
      fireEvent.click(screen.getByLabelText('torpedo torpedo_main 账本绑定 torpedoes'));
      await saveDraft();
      const torpedo = savedLeaf('torpedo');
      expect(torpedo.page_rows).toEqual([{ row: 'torpedo_main', label: '鱼雷管（主）',
        weight_item_ids: ['torpedoes'],
        typed: { tubes: 4, carried: null, diameter_mm: null, length_m: null, arrangement: null },
        source: 'Navypedia', estimate: true }]);
      // The leaf binding follows the rows so the projection can read ledger mass.
      expect(torpedo.weight_item_ids).toEqual(['torpedoes']);
    });

    it('creates the misc leaf and keeps a declared zone mass out of the ledger', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加杂项分区' }));
      fireEvent.change(screen.getByLabelText('新增行模板'), { target: { value: 'hull_below' } });
      fireEvent.click(screen.getByRole('button', { name: '添加声明行' }));
      fireEvent.change(screen.getByLabelText('misc_weight hull_below 质量 · t'), { target: { value: '12.5' } });
      await saveDraft();
      const misc = savedLeaf('misc_weight');
      expect((misc.page_rows as Array<Record<string, unknown>>)[0].row).toBe('hull_below');
      expect((misc.page_rows as Array<Record<string, Record<string, unknown>>>)[0].typed.mass_t).toBe(12.5);
      // A declared zone mass never becomes ledger mass or displacement.
      const project = vi.mocked(api.saveProject).mock.calls[0][1].project;
      expect(project.weight_groups[0].items.map(item => item.mass_t)).toEqual([14, 6]);
    });

    it('adds and removes several torpedo, mine and depth-charge rows', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加鱼雷分区' }));
      for (const template of ['torpedo_main', 'torpedo_secondary', 'mines', 'depth_charges']) {
        fireEvent.change(screen.getByLabelText('新增行模板'), { target: { value: template } });
        fireEvent.click(screen.getByRole('button', { name: '添加声明行' }));
      }
      // A repeated template gets a distinct row identity instead of a duplicate id.
      fireEvent.change(screen.getByLabelText('新增行模板'), { target: { value: 'torpedo_main' } });
      fireEvent.click(screen.getByRole('button', { name: '添加声明行' }));
      await saveDraft();
      expect((savedLeaf('torpedo').page_rows as Array<Record<string, unknown>>).map(row => row.row))
        .toEqual(['torpedo_main', 'torpedo_secondary', 'mines', 'depth_charges', 'torpedo_main_2']);

      fireEvent.click(screen.getAllByRole('button', { name: '移除声明行' })[1]);
      await saveDraft();
      expect((savedLeaf('torpedo').page_rows as Array<Record<string, unknown>>).map(row => row.row))
        .toEqual(['torpedo_main', 'mines', 'depth_charges', 'torpedo_main_2']);
    });

    it('declares all five misc zones and omits page_rows after the last removal', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加杂项分区' }));
      for (const zone of ['hull_below', 'hull_above', 'on_deck', 'above_deck', 'void']) {
        fireEvent.change(screen.getByLabelText('新增行模板'), { target: { value: zone } });
        fireEvent.click(screen.getByRole('button', { name: '添加声明行' }));
      }
      await saveDraft();
      expect((savedLeaf('misc_weight').page_rows as Array<Record<string, unknown>>).map(row => row.row))
        .toEqual(['hull_below', 'hull_above', 'on_deck', 'above_deck', 'void']);
      // `page_rows: []` is rejected by the contract, so an empty declaration omits the key.
      for (let i = 0; i < 5; i += 1) fireEvent.click(screen.getAllByRole('button', { name: '移除声明行' })[0]);
      await saveDraft();
      const misc = savedLeaf('misc_weight');
      expect(misc).not.toHaveProperty('page_rows');
      expect(misc.weight_item_ids).toEqual([]);
    });

    it('keeps row bindings when unassigned leaf items are added and removed', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加鱼雷分区' }));
      fireEvent.click(await screen.findByRole('button', { name: '添加声明行' }));
      fireEvent.click(screen.getByLabelText('torpedo torpedo_main 账本绑定 torpedoes'));
      fireEvent.click(screen.getByLabelText('未分配到行的分区账本条目 stores'));
      await saveDraft();
      let leaf = savedLeaf('torpedo');
      // Row binding T survives: the leaf is the union, never a replacement.
      expect(leaf.weight_item_ids).toEqual(['torpedoes', 'stores']);
      expect((leaf.page_rows as Array<Record<string, unknown>>)[0].weight_item_ids).toEqual(['torpedoes']);

      fireEvent.click(screen.getByLabelText('未分配到行的分区账本条目 stores'));
      await saveDraft();
      leaf = savedLeaf('torpedo');
      expect(leaf.weight_item_ids).toEqual(['torpedoes']);
      expect((leaf.page_rows as Array<Record<string, unknown>>)[0].weight_item_ids).toEqual(['torpedoes']);
    });

    it('refuses an out-of-contract typed value instead of writing an invalid payload', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加鱼雷分区' }));
      fireEvent.click(await screen.findByRole('button', { name: '添加声明行' }));
      const tubes = screen.getByLabelText('torpedo torpedo_main 管数');
      fireEvent.change(tubes, { target: { value: '1.5' } });
      expect(await screen.findByText('必须是非负整数')).toBeVisible();
      fireEvent.change(tubes, { target: { value: '-2' } });
      expect(await screen.findByText('必须是非负整数')).toBeVisible();
      await saveDraft();
      // Nothing invalid reached the project: the count stays unknown, never 0 or 1.5.
      const rows = savedLeaf('torpedo').page_rows as Array<Record<string, Record<string, unknown>>>;
      expect(rows[0].typed.tubes).toBeNull();
    });

    it('declares a leaf as explicitly absent with a reason', async () => {
      await openWeapons(blank);
      fireEvent.click(await screen.findByRole('button', { name: '添加杂项分区' }));
      fireEvent.click(await screen.findByRole('button', { name: '添加声明行' }));
      fireEvent.change(screen.getByLabelText('misc_weight 分区状态'), { target: { value: 'absent' } });
      fireEvent.change(screen.getByLabelText('misc_weight 不存在原因'), { target: { value: 'no positional breakdown' } });
      await saveDraft();
      const misc = savedLeaf('misc_weight');
      expect(misc.status).toBe('absent');
      expect(misc.reason).toBe('no positional breakdown');
    });

    it('shows a declared zone mass separately from the unknown ledger mass', async () => {
      const zoneView = {
        rows: [{ row: 'hull_below', label: 'Hull below water', weight_t: null,
          mass_status: 'no_ledger_binding', typed: { mass_t: 12.5 } }],
        values: {}, diagnostics: [],
        weapons: { misc_zone_mass_declared_count: 1, misc_zone_mass_unknown_count: 4 },
      };
      const run = {
        id: 'r1', project_id: 'p1', revision: 1, condition_id: 'normal-engineering', status: 'completed',
        request_fingerprint: 'f', created_at: '2026-10-02T00:00:00Z', started_at: null, finished_at: null,
        cancel_requested: false, error: null,
        result: { stages: { systems: { data: { page_rows: { 'weapons.misc_weight': zoneView } } } } },
      } as unknown as RunView;
      vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: weaponsProject });
      vi.mocked(api.listRuns).mockResolvedValue([run]);
      render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
      fireEvent.click(await screen.findByRole('button', { name: '鱼雷与水雷武备' }));
      fireEvent.change(screen.getByLabelText('选择武器分区'), { target: { value: 'misc_weight' } });
      const ledger = await screen.findByText('Hull below water · 账本质量');
      // No binding: unknown, never presented as 0 t.
      expect(ledger.closest('.fact-field')!.querySelector('.fact-value')!.textContent).toBe('未知');
      // The declared mass is a separate, clearly informational figure.
      const declared = screen.getByText('Hull below water · 声明质量').closest('.fact-field')!;
      expect(declared.querySelector('.fact-value')!.textContent).toBe('12.5 t');
      expect(declared.querySelector('.fact-meta')!.textContent).toContain('不计入排水量');
    });
  });
});

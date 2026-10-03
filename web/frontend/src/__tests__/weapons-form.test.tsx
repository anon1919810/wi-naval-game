import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn() };
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
});

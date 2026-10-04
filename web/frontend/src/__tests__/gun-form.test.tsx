import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { Workbench } from '../pages/Workbench';
import * as api from '../api';
import type { ProjectDocument, RunView } from '../types';

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getProject: vi.fn(), saveProject: vi.fn(), listRuns: vi.fn() };
});

const gunProject: ProjectDocument = {
  schema: 'plimsoll-project-1', id: 'p1', name: '玛丽皇后号', revision: 1,
  hull: { length_m: 213.4 }, geometry: null, weight_groups: [],
  loading_conditions: [{ id: 'normal-engineering', label: '正常载荷' }],
  systems: {
    weapons: {
      main: {
        installed_guns: 8,
        broadside_guns: 8,
        rounds_per_gun: 80,
        mass_models: [
          {
            id: 'main-ammunition-outfit-mass-check',
            method: 'counted_ammunition_mass',
            linked_weight_item_id: 'main-ammunition',
            inputs: { count_field: 'installed_guns', projectile_mass_kg: 635.029318, charge_mass_kg: 134.71693389, rounds_field: 'rounds_per_gun' },
            input_provenance: {
              projectile_mass_kg: { source: 'NavWeaps 1400 lb projectile value converted with 0.45359237 kg/lb', estimate: true },
              charge_mass_kg: { source: 'NavWeaps 297 lb charge value converted with 0.45359237 kg/lb', estimate: true },
            },
          },
        ],
        page_rows: [
          { row: 'guns', weight_item_ids: ['main-guns'] },
          { row: 'mounts', weight_item_ids: ['main-mounts'] },
          { row: 'ammunition', weight_item_ids: ['main-ammunition'] },
        ],
        weight_item_ids: ['main-guns', 'main-mounts', 'main-ammunition'],
      },
      torpedo: {
        installed_guns: 2,
        broadside_guns: 2,
        rounds_per_gun: 0,
        mass_models: [],
        page_rows: [],
        weight_item_ids: ['torpedo-tubes'],
      },
    },
  },
};

function runWithGuns(): RunView {
  return {
    id: 'r1', project_id: 'p1', revision: 1, condition_id: 'normal-engineering', status: 'completed',
    request_fingerprint: 'fp', created_at: '2026-01-01T00:00:00Z',
    started_at: null, finished_at: null, cancel_requested: false, error: null,
    result: {
      schema: 'plimsoll-analysis-1', status: 'completed', project_id: 'p1', condition_id: 'normal-engineering',
      project_fingerprint: '', input_fingerprint: '', request_fingerprint: '',
      request: {}, input_snapshot: gunProject, units: {}, method_versions: {}, sources: {},
      diagnostics: [], validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
      stages: {
        systems: {
          status: 'completed', requested: true, reason: null,
          validity: { complete: true, converged: true, model_applicable: true, historical_validated: null },
          method_versions: {}, assumptions: [], diagnostics: [],
          data: {
            page_rows: {
              'weapons.main': {
                guns: {
                  schema: 'plimsoll-guns-1', method: 'declared_weapon_battery_inputs_v1', battery: 'main',
                  installed_guns: 8, broadside_guns: 8, rounds_per_gun: 80,
                  shell_mass_kg: { value: 635.029318, source: 'NavWeaps 1400 lb projectile value converted with 0.45359237 kg/lb', estimate: true, status: 'declared' },
                  broadside_mass_kg: 5080.234544, broadside_mass_lb: 11199.999, per_gun_shell_kg: 50802.34544,
                  ship_wide_ammunition_t: 492, ship_wide_ammunition_source: null,
                  ledger_mass_t: 1000, ledger_source: null, status: 'completed', formula: '', diagnostics: [],
                },
              },
            },
          },
        },
      },
    },
  };
}

beforeEach(() => { cleanup(); vi.clearAllMocks(); });

describe('guns battery form', () => {
  it('writes a declared gun count and keeps the rest of the battery on save', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: gunProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: gunProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '火炮武备' }));
    const input = await screen.findByLabelText(/main 单舷炮数/);
    fireEvent.change(input, { target: { value: '10' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const battery = ((submitted.project as Record<string, unknown>).systems as Record<string, unknown>).weapons as Record<string, unknown>;
    const main = battery.main as Record<string, unknown>;
    expect(main.broadside_guns).toBe(10);
    expect(main.installed_guns).toBe(8);
    expect(main.rounds_per_gun).toBe(80);
  });

  it('updates the declared projectile mass and keeps its source/estimate on save', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: gunProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: gunProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '火炮武备' }));
    const input = await screen.findByLabelText('main 单发弹重');
    // The default reader unit is tonnes; the ammunition model stores kilograms.
    fireEvent.change(input, { target: { value: '0.6' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const weapons = ((submitted.project as Record<string, unknown>).systems as Record<string, unknown>).weapons as Record<string, unknown>;
    const models = ((weapons.main as Record<string, unknown>).mass_models as Array<Record<string, unknown>>);
    const ammo = models.find(m => m.method === 'counted_ammunition_mass')!;
    expect((ammo.inputs as Record<string, unknown>).projectile_mass_kg).toBe(600);
    const prov = (ammo.input_provenance as Record<string, unknown>).projectile_mass_kg as Record<string, unknown>;
    expect(prov.source).toBe('NavWeaps 1400 lb projectile value converted with 0.45359237 kg/lb');
    expect(prov.estimate).toBe(true);
  });

  it('does not write 0 when a gun input is cleared', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: gunProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.saveProject).mockResolvedValue({ project_id: 'p1', revision: 2, project: gunProject });

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '火炮武备' }));
    const input = await screen.findByLabelText('main 单发弹重');
    fireEvent.change(input, { target: { value: '600' } });
    fireEvent.change(input, { target: { value: '' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修订' }));

    await waitFor(() => expect(api.saveProject).toHaveBeenCalled());
    const submitted = vi.mocked(api.saveProject).mock.calls[0][1] as { project: ProjectDocument };
    const weapons = ((submitted.project as Record<string, unknown>).systems as Record<string, unknown>).weapons as Record<string, unknown>;
    const models = ((weapons.main as Record<string, unknown>).mass_models as Array<Record<string, unknown>>);
    const ammo = models.find(m => m.method === 'counted_ammunition_mass')!;
    const value = (ammo.inputs as Record<string, unknown>).projectile_mass_kg;
    expect(value).not.toBe(0);
    expect(value).toBeNull();
  });

  it('shows a prompt instead of a zero aggregate when there is no run', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: gunProject });
    vi.mocked(api.listRuns).mockResolvedValue([]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '火炮武备' }));
    expect(await screen.findByText('保存并运行后显示聚合值')).toBeVisible();
  });

  it('renders the backend aggregate, not a local recomputation', async () => {
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: gunProject });
    vi.mocked(api.listRuns).mockResolvedValue([runWithGuns()]);

    render(<Workbench projectId="p1" onBack={vi.fn()} onRun={vi.fn()} />);
    fireEvent.click(await screen.findByRole('button', { name: '火炮武备' }));
    expect(await screen.findByText('5.080235 t')).toBeVisible();
    expect(screen.getByText('50.802345 t')).toBeVisible();
    expect(screen.getByText('492 t')).toBeVisible();
  });
});

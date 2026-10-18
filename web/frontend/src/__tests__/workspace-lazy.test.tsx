import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { renderZh } from './locale';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import App, { RouteChunk } from '../App';
import * as api from '../api';
import { useRouteModule } from '../components/useRouteModule';
import { reloadPage } from '../components/reloadPage';
import { shellCopy } from '../i18n/shell';
import type { UserSession } from '../types';

/**
 * The route boundary.
 *
 * The heavy pages are their own chunks, so the project library can be read
 * without downloading the editors, the run reader and the report. These tests
 * pin three properties: the library pulls none of those chunks, entering a route
 * pulls exactly its own, and a chunk that fails is a visible localized panel
 * whose recovery is an explicit reload: a second import of the same URL can be
 * answered from Chromium's failed-fetch record without reaching the network.
 */

const loaded = vi.hoisted(() => ({ workbench: 0, run: 0, report: 0 }));

vi.mock('../pages/Workbench', () => { loaded.workbench += 1; return { Workbench: () => null }; });
vi.mock('../pages/Run', () => { loaded.run += 1; return { Run: () => null }; });
vi.mock('../pages/Report', () => { loaded.report += 1; return { ReportPage: () => null }; });

vi.mock('../api', async importOriginal => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn() };
});

vi.mock('../components/reloadPage', () => ({ reloadPage: vi.fn() }));

const session: UserSession = {
  id: 'a-1', email: 'anonymous-abc@anonymous.invalid', theme: 'light',
  csrf_token: 'csrf-1', mode: 'anonymous', label: '本浏览器工作区',
};

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  window.location.hash = '';
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue(session);
  vi.mocked(api.listProjects).mockResolvedValue([]);
});

afterEach(cleanup);

describe('the library reads without the heavy pages', () => {
  it('pulls none of the workbench, run or report chunks for the project list', async () => {
    window.location.hash = '#/projects';
    renderZh(<App />);
    // The library renders with its own words, so the workspace has settled.
    expect(await screen.findByText('项目库')).toBeVisible();
    expect(loaded.workbench).toBe(0);
    expect(loaded.run).toBe(0);
    expect(loaded.report).toBe(0);
  });

  it('pulls exactly the route chunk that was entered', async () => {
    window.location.hash = '#/projects/p1';
    renderZh(<App />);
    await waitFor(() => expect(loaded.workbench).toBe(1));
    expect(loaded.run).toBe(0);
    expect(loaded.report).toBe(0);
  });
});

describe('the route chunk is not re-fetched or remounted', () => {
  it('imports once and keeps the first module across re-renders', async () => {
    const load = vi.fn(() => Promise.resolve({ value: 'first' }));
    function Harness({ label }: { label: string }) {
      const state = useRouteModule(load);
      return <p>{`${state.status}:${label}${state.status === 'ready' ? `:${state.module.value}` : ''}`}</p>;
    }
    const { rerender } = render(<Harness label="a" />);
    expect(await screen.findByText('ready:a:first')).toBeVisible();
    rerender(<Harness label="b" />);
    expect(await screen.findByText('ready:b:first')).toBeVisible();
    expect(load).toHaveBeenCalledTimes(1);
  });
});

describe('a failed chunk is recoverable', () => {
  it('offers a localized reload rather than replaying the cached failed import', async () => {
    const load = vi.fn((): Promise<{ value: string }> => Promise.reject(new Error('chunk failed')));
    render(<RouteChunk load={load} object="the page">{module => <p>{module.value}</p>}</RouteChunk>);
    expect(await screen.findByText(shellCopy('en', 'shell.route.failedTitle'))).toBeVisible();
    expect(screen.getByText(shellCopy('en', 'shell.route.failedNote'))).toBeVisible();
    // There is no second chance at the same URL presented as a retry.
    expect(screen.queryByRole('button', { name: shellCopy('en', 'read.retry') })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: shellCopy('en', 'shell.route.reload') }));
    expect(vi.mocked(reloadPage)).toHaveBeenCalledTimes(1);
    expect(load).toHaveBeenCalledTimes(1);
  });
});

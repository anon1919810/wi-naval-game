import { useState } from 'react';
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import Portfolio from '../portfolio/Portfolio';
import App from '../App';
import { LanguageProvider } from '../portfolio/LanguageProvider';
import { Contact, CONTACT_EMAIL } from '../portfolio/Contact';
import { initialLanguage, LANGUAGE_KEY, rememberLanguage, storedLanguage, translate, type SiteLanguage } from '../portfolio/language';
import { PUBLIC_WORK_DETAIL_HASH } from '../portfolio/routes';
import * as api from '../api';

/**
 * Cluster: the bilingual public shell.
 *
 * What is checked here is behaviour a visitor can lose, not the wording itself:
 * that the two choices are one labelled pair of real buttons that say which is
 * live; that pressing one changes the words of every public page at once, in
 * place, without a reload, a new address, a replayed intro or a reset exhibit;
 * that a choice made by hand survives and is preferred over the browser's; and
 * that a preference nobody can keep — refused or nonsense — is tolerated rather
 * than crashing the shell or pinning a language that was never chosen.
 *
 * The English expectations in the other suites are untouched: this file proves
 * the switch exists and is honest, not that English changed.
 */

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(),
  authConfig: vi.fn(), me: vi.fn(), bootstrapAnonymous: vi.fn(), listProjects: vi.fn(),
  getProject: vi.fn(), listRuns: vi.fn(), saveProject: vi.fn(), enqueueRun: vi.fn(),
}));

const listeners = new Map<string, Set<(event: MediaQueryListEvent) => void>>();
const preferences = new Map<string, boolean>();

// Keep cold module transformation outside the navigation assertions' timeouts.
// Importing the tool does not mount it and does not call its API.
beforeAll(async () => { await import('../App'); });

beforeEach(() => {
  window.history.replaceState(null, '', '/');
  localStorage.clear();
  vi.clearAllMocks();
  listeners.clear(); preferences.clear();
  delete (document as { startViewTransition?: unknown }).startViewTransition;
  vi.stubGlobal('matchMedia', (query: string) => {
    const handlers = listeners.get(query) ?? new Set<(event: MediaQueryListEvent) => void>();
    listeners.set(query, handlers);
    return {
      get matches() { return preferences.get(query) ?? false; }, media: query,
      addEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => { handlers.add(handler); },
      removeEventListener: (_: string, handler: (event: MediaQueryListEvent) => void) => { handlers.delete(handler); },
    };
  });
  vi.stubGlobal('Image', class { src = ''; decode = () => Promise.resolve(); });
  vi.stubGlobal('scrollTo', vi.fn());
  vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
  vi.mocked(api.me).mockResolvedValue({ id: 'existing', email: 'existing@anonymous.invalid', theme: 'light', csrf_token: 'test', mode: 'anonymous', label: '本浏览器工作区' });
  vi.mocked(api.listProjects).mockResolvedValue([]);
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

const flush = () => act(async () => {});
function open(hashValue: string) {
  act(() => { window.history.replaceState(null, '', `/${hashValue}`); window.dispatchEvent(new HashChangeEvent('hashchange')); });
}
const zh = () => screen.getByRole('button', { name: '中文' });
const en = () => screen.getByRole('button', { name: 'EN' });
/** The pair, as one labelled group rather than as two loose controls. */
const pair = () => screen.getByRole('group', { name: 'Language' });

describe('the language control', () => {
  it('is one labelled pair of real buttons that says which language is live', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    expect(pair()).toBeInTheDocument();
    // Both languages are always present: there is no menu to open and no
    // disclosure to expand, so neither is ever hidden behind a press.
    expect(zh()).toBeVisible();
    expect(en()).toBeVisible();
    expect(en()).toHaveAttribute('aria-pressed', 'true');
    expect(zh()).toHaveAttribute('aria-pressed', 'false');
    // Real buttons, in the tab order, with a tooltip that says what each is.
    expect(en().tagName).toBe('BUTTON');
    expect(zh().tagName).toBe('BUTTON');
    expect(zh()).toHaveAttribute('type', 'button');
    expect(zh()).toHaveAttribute('title', 'Chinese interface');
    // Each carries its own language, so one is not read with the other's voice.
    expect(zh()).toHaveAttribute('lang', 'zh-CN');
    expect(en()).toHaveAttribute('lang', 'en');
  });

  it('switches the page in place, with no reload, no new address and no replayed intro', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    const address = window.location.hash;
    expect(screen.getByRole('link', { name: 'Work 01' })).toBeInTheDocument();

    fireEvent.click(zh());

    // The words changed everywhere at once, on the page already on screen.
    expect(screen.getByRole('link', { name: '作品 01' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Work 01' })).toBeNull();
    expect(screen.getByRole('navigation', { name: '主导航' })).toBeInTheDocument();
    // And nothing about the page's own machinery moved: the address is the one
    // it already had, the exhibit is still the exhibit, and the opening is not
    // replayed by a dictionary changing.
    expect(window.location.hash).toBe(address);
    expect(screen.queryByRole('status', { name: /Opening Y’s Formfield|Loading reference/ })).toBeNull();
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(document.title).toBe('Y’s Formfield — 工具与实验');

    // And back, which is the same press with the other word on it.
    fireEvent.click(en());
    expect(screen.getByRole('link', { name: 'Work 01' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('en');
  });
});

describe('the localized routes', () => {
  it('translates each public page, its headings and its controls, and leaves the equations alone', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    fireEvent.click(zh());

    // Work: the exhibit, its tools and its error text.
    expect(screen.getByRole('group', { name: /交互式俯视图/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '放大镜已关闭' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '参考图纸 01' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重置视图' })).toBeInTheDocument();
    expect(screen.getByRole('group', { name: '参考图纸' })).toBeInTheDocument();
    // The brand name in the title is never a translation of itself.
    expect(screen.getByRole('link', { name: '打开 Plimsoll' })).toHaveAttribute('href', '#/plimsoll');

    // About, reached by its Chinese word.
    open('#/about');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('让想法');
    expect(document.title).toBe('Y’s Formfield — 工具与实验');
    expect(screen.getByRole('link', { name: /查看项目/ })).toHaveAttribute('href', `#${PUBLIC_WORK_DETAIL_HASH}`);
    expect(screen.getByRole('button', { name: '复制邮箱' })).toBeInTheDocument();
    // Contact says the same thing it says in English, and the address beside it
    // is still an address rather than a translation of one.
    const mail = screen.getByRole('link', { name: CONTACT_EMAIL });
    expect(mail).toHaveAttribute('href', `mailto:${CONTACT_EMAIL}`);
    // The studies still draw the same equations: a translated spoken name around
    // them, and the notation itself unchanged and marked as Latin.
    const maths = [...document.querySelectorAll('.ff-math')];
    expect(maths.length).toBeGreaterThan(1);
    for (const math of maths) {
      expect(math).toHaveAttribute('lang', 'zh-CN');
      expect(math.getAttribute('aria-label')).toBeTruthy();
      expect(math.querySelectorAll('span[lang="en"]').length).toBeGreaterThan(0);
    }
    const whole = document.querySelector('.ff-about')!.textContent!;
    expect(whole).toContain('sin(');
    expect(whole).toContain('0.4631');
    expect(whole).toContain('log');
    expect(whole).toContain('ν');
  });

  it('translates the detail and keeps every limit, and the credits with it', async () => {
    open(`#${PUBLIC_WORK_DETAIL_HASH}`);
    render(<Portfolio introEnabled={false} />);
    await flush();
    fireEvent.click(zh());

    // The five sections, by the approved headings.
    expect(screen.getAllByRole('heading', { level: 2 }).map(node => node.textContent))
      .toEqual(['01概述', '02功能', '03首次使用', '04技术构成', '05方法与限制']);
    // The limits are stated, not softened by the translation.
    const detail = document.querySelector<HTMLElement>('.ff-detail')!;
    expect(detail.textContent).toContain('不是经认证的船舶设计工具');
    // The laboratory boundary is stated precisely rather than as a flat denial:
    // these approximations exist, and each one says what it is not.
    expect(detail.textContent).toContain('都不是真实的装甲穿透');
    expect(detail.textContent).toContain('更不是完整的战斗模拟');
    expect(detail.textContent).toContain('重量账本');
    expect(detail.textContent).toContain('装载工况');
    expect(detail.textContent).toContain('静水力');
    expect(detail.textContent).toContain('连通舱室进行随时间推进的准静态进水计算');
    expect(detail.textContent).toContain('不可改写的修订版本');
    // Nothing is certified in either language, and nothing invented for this one.
    expect(detail.textContent).not.toMatch(/certified by|class-approved|ISO|取得认证|通过认证/);

    // Credits, on its own route, with the people named as they are.
    open('#/credits');
    const credits = document.querySelector<HTMLElement>('.ff-credits')!;
    expect(document.title).toBe('致谢 — Y’s Formfield');
    expect(credits.textContent).toContain('为本站的艺术设计与视觉风格提供了宝贵建议。');
    expect(credits.textContent).toContain('提供了宝贵的 Coding Plan 额度，支持网站开发。');
    // A person's name is a name: never translated, and marked as Latin text.
    const names = [...credits.querySelectorAll('dt')].filter(node => node.textContent === 'Yang Duanming');
    expect(names).toHaveLength(0);
    expect(credits.textContent).toContain('Yang Duanming');
    expect(credits.querySelector('dt[lang="en"]')!.textContent).toBe('simppleasedie');
  });

  it('names the reading ruler in the language on screen', async () => {
    open('#/credits');
    render(<Portfolio introEnabled={false} />);
    await flush();
    expect(screen.getByRole('navigation', { name: 'Reading position' })).toBeInTheDocument();

    fireEvent.click(zh());
    const ruler = screen.getByRole('navigation', { name: '阅读进度' });
    const marks = [...ruler.querySelectorAll<HTMLButtonElement>('.ff-ruler-mark')];
    // One mark per declared section, as before, and each is named from the
    // section it is on rather than from a translation table of its own.
    expect(marks).toHaveLength(3);
    expect(marks[0]).toHaveAttribute('title', '01 / 特别感谢');
    expect(marks[2].getAttribute('title')).toContain('资料来源');
    for (const mark of marks) expect(mark).toHaveAttribute('type', 'button');
  });
});

describe('a switch changes words and nothing else', () => {
  it('leaves the route, the exhibit, its sheet, the lens and the theme exactly as they were', async () => {
    render(<Portfolio introEnabled={false} />);
    await flush();
    // Something chosen, not something inherited.
    fireEvent.click(screen.getByRole('button', { name: 'Reference sheet 02' }));
    await flush();
    fireEvent.click(screen.getByRole('button', { name: 'Inspect Off' }));
    const exhibit = screen.getByRole('group', { name: /Interactive top-view/ });
    vi.spyOn(exhibit, 'getBoundingClientRect').mockReturnValue(new DOMRect(0, 0, 800, 350));
    fireEvent.keyDown(exhibit, { key: 'ArrowRight' });
    const pan = () => document.querySelector('.ff-layer-vessel')!.getAttribute('transform');
    const panned = pan();
    const lens = () => document.querySelector('.ff-lens-view')?.getAttribute('viewBox');
    const sampled = lens();
    fireEvent.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    const address = window.location.hash;

    fireEvent.click(zh());

    // The same reference, the same inspection, the same pan and sample, the same
    // theme, the same address: a dictionary changing is not a navigation and is
    // not a reset of anything the visitor did.
    expect(screen.getByRole('button', { name: '参考图纸 02' })).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '放大镜已开启' })).toHaveAttribute('aria-pressed', 'true');
    expect(pan()).toBe(panned);
    expect(lens()).toBe(sampled);
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.location.hash).toBe(address);
    // The viewer is still on Work, and the reading position was never moved.
    expect(screen.getByRole('link', { name: '作品 01' })).toHaveAttribute('aria-current', 'page');
    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  it('keeps the choice when the workspace is opened and left again', async () => {
    const captures: { capture: () => Promise<void>; finish: () => Promise<void> }[] = [];
    (document as { startViewTransition?: unknown }).startViewTransition = vi.fn((update: () => void) => {
      let ready!: () => void, finish!: () => void;
      const readyPromise = new Promise<void>(yes => { ready = yes; });
      const finished = new Promise<void>(yes => { finish = yes; });
      captures.push({ capture: () => act(async () => { update(); ready(); }), finish: () => act(async () => { finish(); }) });
      return { ready: readyPromise, finished, skipTransition: () => { update(); finish(); } };
    });
    render(<Portfolio introEnabled={false} />);
    await flush();
    fireEvent.click(zh());

    // Into the tool, and out of it again the way the shell itself does it.
    open('#/plimsoll');
    const enter = captures.at(-1)!;
    await enter.capture(); await enter.finish();
    await screen.findByTitle('本浏览器工作区');
    open('#/work');
    const back = captures.at(-1)!;
    await back.capture(); await back.finish();

    // The public shell comes back in the language it was left in, with its
    // Chinese words and its Chinese document language intact.
    expect(screen.getByRole('link', { name: '作品 01' })).toBeInTheDocument();
    expect(document.documentElement.lang).toBe('zh-CN');
    expect(zh()).toHaveAttribute('aria-pressed', 'true');
  });
});

describe('the stored preference', () => {
  it('is written only when the visitor chooses, and never merely because the browser asked', async () => {
    const navigatorLanguage = vi.spyOn(navigator, 'language', 'get');
    navigatorLanguage.mockReturnValue('zh-CN');
    render(<Portfolio introEnabled={false} />);
    await flush();
    // A Chinese browser is still served English on a first visit, and nothing
    // was stored: the locale is not a choice this visitor made here.
    expect(en()).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: 'Work 01' })).toBeInTheDocument();
    expect(localStorage.getItem(LANGUAGE_KEY)).toBeNull();

    fireEvent.click(zh());
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe('zh-CN');
    navigatorLanguage.mockReturnValue('en-GB');
  });

  it('serves English to a first visit whatever locale the browser reports', async () => {
    for (const locale of ['zh-CN', 'zh-Hans', 'zh-TW', 'de-DE', 'fr-FR', 'ja-JP']) {
      const navigatorLanguage = vi.spyOn(navigator, 'language', 'get');
      navigatorLanguage.mockReturnValue(locale);
      localStorage.clear();
      expect(storedLanguage()).toBeNull();
      expect(initialLanguage()).toBe('en');

      const view = render(<Portfolio introEnabled={false} />);
      await flush();
      expect(en()).toHaveAttribute('aria-pressed', 'true');
      expect(screen.getByRole('link', { name: 'Work 01' })).toBeInTheDocument();
      expect(document.documentElement.lang).toBe('en');
      view.unmount();
      navigatorLanguage.mockRestore();
    }
  });

  it('keeps a manual choice across the shell going away, whatever the browser says', async () => {
    const navigatorLanguage = vi.spyOn(navigator, 'language', 'get');
    navigatorLanguage.mockReturnValue('en-US');
    // Chosen here, not inferred: stored, and preferred over the locale.
    localStorage.setItem(LANGUAGE_KEY, 'zh-CN');
    expect(storedLanguage()).toBe('zh-CN');
    expect(initialLanguage()).toBe('zh-CN');

    const first = render(<Portfolio introEnabled={false} />);
    await flush();
    expect(zh()).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: '作品 01' })).toBeInTheDocument();
    first.unmount();

    render(<Portfolio introEnabled={false} />);
    await flush();
    expect(zh()).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: '作品 01' })).toBeInTheDocument();
    navigatorLanguage.mockRestore();
  });

  it.each([
    ['nonsense', 'klingon'],
    ['a number', '2'],
    ['empty', ''],
  ])('treats %s left in storage as no choice at all', async (_case, value) => {
    vi.spyOn(navigator, 'language', 'get').mockReturnValue('fr-FR');
    localStorage.setItem(LANGUAGE_KEY, value);
    expect(storedLanguage()).toBeNull();
    expect(initialLanguage()).toBe('en');
    render(<Portfolio introEnabled={false} />);
    await flush();
    // Nothing usable stored, so the one unchosen state: English, rather than a
    // third language nothing here can print.
    expect(en()).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('link', { name: 'Work 01' })).toBeInTheDocument();
  });

  it('carries on when the browser will not keep a preference', async () => {
    const denied = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('denied'); });
    render(<Portfolio introEnabled={false} />);
    await flush();
    // The choice still applies to the page in front of this visitor...
    fireEvent.click(zh());
    expect(screen.getByRole('link', { name: '作品 01' })).toBeInTheDocument();
    // ...and refusing to store it is not an error to raise.
    expect(denied).toHaveBeenCalledWith(LANGUAGE_KEY, 'zh-CN');
    expect(() => rememberLanguage('en')).not.toThrow();

    denied.mockRestore();
    const read = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('denied'); });
    expect(storedLanguage()).toBeNull();
    expect(initialLanguage()).toBe('en');
    read.mockRestore();
  });
});

describe('the workspace language switch', () => {
  // The same pair the public shell offers, in the application header, writing the
  // same single stored preference. The workspace below is a real one: an
  // anonymous session, a saved project and an unsaved edit the reader can lose.
  const box = {
    schema: 'plimsoll-project-1', id: 'p1', name: '解析方箱', revision: 1,
    hull: { length_m: 90, beam_m: 20, draught_normal_m: 4 }, geometry: null,
    weight_groups: [], loading_conditions: [{ id: 'loaded', label: '满载' }],
  };

  /** A minimal shell: the provider owns the language, exactly as Portfolio does. */
  function Workspace() {
    const [language, setLanguage] = useState<SiteLanguage>('zh-CN');
    return <LanguageProvider language={language} onLanguage={value => { rememberLanguage(value); setLanguage(value); }}><App returnHref="#/work" /></LanguageProvider>;
  }

  beforeEach(() => {
    window.history.replaceState(null, '', '/#/projects/p1');
    window.dispatchEvent(new HashChangeEvent('hashchange'));
    vi.mocked(api.authConfig).mockResolvedValue({ mode: 'anonymous' });
    vi.mocked(api.me).mockRejectedValue(new api.ApiError(401, 'login required'));
    vi.mocked(api.bootstrapAnonymous).mockResolvedValue({
      id: 'a-1', email: 'a-1@anonymous.invalid', theme: 'light', csrf_token: 'csrf',
      mode: 'anonymous', label: '本浏览器工作区',
    });
    vi.mocked(api.getProject).mockResolvedValue({ project_id: 'p1', revision: 1, project: box as never });
    vi.mocked(api.listRuns).mockResolvedValue([]);
    vi.mocked(api.enqueueRun).mockResolvedValue({ id: 'run-1' } as never);
  });

  it('exposes the same Chinese/EN pair in the application header and writes the one stored preference', async () => {
    render(<Workspace />);
    // The pair is the public shell's pair: two real buttons, one labelled group,
    // each carrying its own language, and `aria-pressed` says which is live.
    const pair = screen.getAllByRole('group', { name: '语言' }).at(-1)!;
    const zh = within(pair).getByRole('button', { name: '中文' });
    const en = within(pair).getByRole('button', { name: 'EN' });
    expect(zh).toHaveAttribute('aria-pressed', 'true');
    expect(en).toHaveAttribute('aria-pressed', 'false');
    expect(zh).toHaveAttribute('lang', 'zh-CN');
    expect(en).toHaveAttribute('lang', 'en');

    fireEvent.click(en);
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe('en');
    // One preference, not two: the shell's key is the only one written.
    expect(Object.keys(localStorage).filter(key => key.includes('language'))).toEqual([LANGUAGE_KEY]);
  });

  it('switches every workspace word in place, keeping the draft, the identity and the queue', async () => {
    render(<Workspace />);
    // The chapter is opened by its Chinese name and an input is edited, so the
    // switch below has real unsaved work to lose if it is not in-place.
    fireEvent.click(await screen.findByRole('button', { name: '船型与几何' }));
    const length = await screen.findByLabelText('船长');
    fireEvent.change(length, { target: { value: '91' } });
    expect(screen.getByText('未保存修改')).toBeVisible();

    const bootstrapCalls = vi.mocked(api.bootstrapAnonymous).mock.calls.length;
    const enqueueCalls = vi.mocked(api.enqueueRun).mock.calls.length;
    const runsReads = vi.mocked(api.listRuns).mock.calls.length;

    fireEvent.click(screen.getAllByRole('button', { name: 'EN' }).at(-1)!);

    // Every application-owned word changed at once: the chapter index, the
    // toolbar, the field label, the save state and the page heading.
    expect(await screen.findByRole('button', { name: 'Hull & Geometry' })).toBeVisible();
    expect(screen.getByText('Unsaved changes')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Save revision' })).toBeVisible();
    // The unsaved draft itself is untouched: the same control, the same chapter,
    // the same typed value, and the reader is still in the vessel they edited.
    expect(screen.getByLabelText('Length overall (LOA)')).toHaveValue(91);
    expect(screen.getByRole('heading', { level: 1, name: 'Hull & Geometry' })).toBeVisible();

    // Nothing about identity, project data or runs was restarted by a dictionary
    // changing: no second workspace was minted and nothing was queued or re-read.
    expect(vi.mocked(api.bootstrapAnonymous).mock.calls.length).toBe(bootstrapCalls);
    expect(vi.mocked(api.enqueueRun).mock.calls.length).toBe(enqueueCalls);
    expect(vi.mocked(api.listRuns).mock.calls.length).toBe(runsReads);

    // And back again, with the same unsaved work still in place.
    fireEvent.click(screen.getAllByRole('button', { name: '中文' }).at(-1)!);
    expect(await screen.findByRole('button', { name: '船型与几何' })).toBeVisible();
    expect(screen.getByLabelText('船长')).toHaveValue(91);
  });

  it('updates a refused JSON edit in place without applying or discarding its text', async () => {
    render(<Workspace />);
    fireEvent.click(await screen.findByRole('button', { name: '项目数据' }));
    const invalid = JSON.stringify({ ...box, id: 'foreign-project' });
    fireEvent.change(screen.getByLabelText('项目 JSON'), { target: { value: invalid } });
    fireEvent.click(screen.getByRole('button', { name: '应用到草稿' }));
    expect(screen.getByRole('alert')).toHaveTextContent('项目 ID 必须与当前项目一致');
    fireEvent.click(screen.getAllByRole('button', { name: 'EN' }).at(-1)!);
    expect(screen.getByRole('alert')).toHaveTextContent('The project id must match the current project');
    expect(screen.getByLabelText('Project JSON')).toHaveValue(invalid);
    expect(api.saveProject).not.toHaveBeenCalled();
    expect(api.enqueueRun).not.toHaveBeenCalled();
  });
});

describe('below the provider', () => {
  it('a component rendered alone is English, and still interpolates its own messages', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } });
    render(<Contact />);
    // No provider, no wrapper: the English strings, with the same `{email}`
    // substitution the provider would have done.
    expect(screen.getByRole('button', { name: 'COPY EMAIL' })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' }));
    await act(async () => {});
    expect(screen.getByRole('status')).toHaveTextContent(`COPIED — ${CONTACT_EMAIL} is on your clipboard.`);
  });

  it('a provider above a component is all that is needed to read it in Chinese', () => {
    render(<LanguageProvider language="zh-CN" onLanguage={() => {}}><Contact /></LanguageProvider>);
    expect(screen.getByRole('button', { name: '复制邮箱' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '联系方式' })).toBeInTheDocument();
  });

  it('reports an unknown key as itself rather than as an empty line', () => {
    expect(translate('en', 'nav.work')).toBe('Work');
    expect(translate('zh-CN', 'nav.work')).toBe('作品');
    expect(translate('en', 'nav.work', { unused: 'x' })).toBe('Work');
  });
});

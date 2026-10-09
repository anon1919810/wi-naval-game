import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { controlCue, installInteractionFeedback } from '../audio/feedback';
import { interactionAudio, SOUND_KEY } from '../audio/interactionAudio';
import { SoundToggle } from '../audio/SoundToggle';
import * as feedback from '../audio/feedback';
import { Contact } from '../portfolio/Contact';

beforeEach(() => { localStorage.clear(); interactionAudio.setMuted(false); });
afterEach(() => { cleanup(); interactionAudio.dispose(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
describe('interaction feedback policy', () => {
  it('shares the same persistent mute between public and workspace controls', () => {
    render(<><SoundToggle /><SoundToggle workspace /></>);
    fireEvent.click(screen.getByRole('button', { name: 'Sound' }));
    expect(screen.getByRole('button', { name: '交互音效' })).toHaveAttribute('aria-pressed', 'false');
    expect(localStorage.getItem(SOUND_KEY)).toBe('muted');
    fireEvent.click(screen.getByRole('button', { name: '交互音效' }));
    expect(screen.getByRole('button', { name: 'Sound' })).toHaveAttribute('aria-pressed', 'true');
    expect(localStorage.getItem(SOUND_KEY)).toBeNull();
  });

  it('assigns one owner to navigation and ruler cues and keeps disabled actions quiet', () => {
    render(<><nav className="ff-rail"><a href="#/about">About</a></nav>
      <div className="ff-ruler"><button>Position</button></div>
      <button data-audio="manual">Open project</button><button disabled>Save</button>
      <button className="nav-item" aria-current="page">Current chapter</button><button className="nav-item">Other chapter</button>
      <details><summary>More</summary></details><a href="/api/export" download>Download</a>
      <nav className="stage-index"><a href="#/runs/r/loading">Loading</a></nav></>);
    for (const name of ['Position', 'Open project', 'Save', 'Current chapter']) expect(controlCue(screen.getByRole('button', { name }))).toBeNull();
    expect(controlCue(screen.getByRole('link', { name: 'About' }))).toBeNull();
    expect(controlCue(screen.getByRole('button', { name: 'Other chapter' }))).toBe('detent');
    expect(controlCue(screen.getByText('More'))).toBe('detent');
    expect(controlCue(screen.getByRole('link', { name: 'Download' }))).toBe('touch');
    expect(controlCue(screen.getByRole('link', { name: 'Loading' }))).toBe('detent');
  });

  it('does not unlock or play for scripted clicks, input changes or focus', () => {
    const unlock = vi.spyOn(interactionAudio, 'unlock'); const play = vi.spyOn(interactionAudio, 'play');
    const remove = installInteractionFeedback();
    render(<><button>Save</button><a className="ff-title-link" href="#/projects">Plimsoll</a><select aria-label="Unit"><option>m</option><option>ft</option></select></>);
    fireEvent.pointerDown(screen.getByText('Save')); fireEvent.click(screen.getByText('Save'));
    fireEvent.change(screen.getByLabelText('Unit'), { target: { value: 'ft' } }); fireEvent.focus(screen.getByText('Plimsoll'));
    expect(unlock).not.toHaveBeenCalled(); expect(play).not.toHaveBeenCalled(); remove();
  });

  it.each([true, false])('announces a clipboard outcome only after resolution (success %s)', async success => {
    const announce = vi.spyOn(feedback, 'outcome').mockImplementation(() => {});
    let resolve!: () => void, reject!: () => void;
    const write = new Promise<void>((res, rej) => { resolve = res; reject = rej; });
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: () => write } });
    render(<Contact />); fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' }));
    expect(announce).not.toHaveBeenCalled();
    await act(async () => { if (success) resolve(); else reject(); });
    expect(announce.mock.calls).toEqual([[success ? 'resolve' : 'hold']]);
  });

  it('discards a clipboard completion after the contact page has unmounted', async () => {
    const announce = vi.spyOn(feedback, 'outcome').mockImplementation(() => {});
    let resolve!: () => void;
    const write = new Promise<void>(res => { resolve = res; });
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText: () => write } });
    const page = render(<Contact />); fireEvent.click(screen.getByRole('button', { name: 'COPY EMAIL' })); page.unmount();
    await act(async () => { resolve(); });
    expect(announce).not.toHaveBeenCalled();
  });
});

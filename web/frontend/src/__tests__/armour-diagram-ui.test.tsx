import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArmourDiagram } from '../components/ArmourDiagram';
import { ShipDesignChapter, type ShipDesignHost } from '../components/ShipDesignEditor';
import { inLanguage } from './locale';

/**
 * The armour diagram as a reader meets it: a gated panel that withholds numbers
 * while a reading is pending or failed, a drawing whose regions can be selected
 * and whose explicit Edit hands a source field back, a frozen report that is
 * read-only, and downloads that produce real files and real errors.
 */

afterEach(cleanup);

const realFractions = {
  fcLength: 0.20499999821186066, fdLength: 0.30000001192092896,
  adLength: 0.3400000035762787, qdLength: 0.1550000011920929,
};

const native = (over: Record<string, unknown> = {}) => ({
  schema: 'plimsoll-ship-design-result-1',
  method_version: 'ship-design-native-v1',
  status: 'available',
  basis_condition_id: 'design-normal',
  hull: { length: 590.55, beam: 88.58 },
  freeboard: {
    ...realFractions,
    freeQDAft: 26, freeQDFor: 26, freeADAft: 25, freeADFor: 25,
    freeFDAft: 24, freeFDFor: 24, freeFCAft: 30, freeFCFor: 34,
    lengthBow: 20, lengthStern: 0,
  },
  armour: {
    beltMain: 7, beltEnds: 3, beltUpper: 4, bulkhead: 1.5, bulge: 0.5,
    deck: 2, deckFC: 1, deckQD: 1.25, conningFor: 8, conningAft: 4,
    beltMainLength: 280, beltMainHeight: 12, beltEndsLength: 140, beltEndsHeight: 10,
    beltUpperLength: 260, beltUpperHeight: 8, bulkheadLength: 240, bulkheadHeight: 14,
    bulgeLength: 300, bulgeHeight: 10, bulkheadBeam: 88.58, beltsIncline: 30,
    bulkheadType: 0, deckCoverage: 0, beltCover: 0.72, maxBeltHeight: 49.15, armourWarn: false,
    weight: 3579.7, weightBeltMain: 1096.9,
  },
  ledger: { roles: {
    belt_main: { mode: 'estimated', estimate_t: 1114.57, selected_mass_t: 1114.57 },
    belt_ends: { mode: 'estimated', estimate_t: 157.89, selected_mass_t: 157.89 },
    belt_upper: { mode: 'estimated', estimate_t: 402.2, selected_mass_t: 402.2 },
    bulkhead: { mode: 'estimated', estimate_t: 189.47, selected_mass_t: 189.47 },
    bulge: { mode: 'estimated', estimate_t: 56.39, selected_mass_t: 56.39 },
    deck: { mode: 'declared', estimate_t: 1267.13, selected_mass_t: 1277.13 },
    conning: { mode: 'estimated', estimate_t: 449.5, selected_mass_t: 449.5 },
  } },
  balance: { selected_mass_t: 71934.15, estimated_mass_t: 71924.15, target_displacement_t: 71924.15, difference_t: 10 },
  source_design: { parameters: { ship_name: 'Queen Mary' } },
  ...over,
});

describe('armour diagram states', () => {
  it('withholds the drawing and the numbers while pending or failed', () => {
    const pending = render(<ArmourDiagram result={native()} state="pending" />).container;
    expect(pending.querySelector('[data-state]')).not.toBeNull();
    expect(document.querySelector('[data-state="pending"]')).not.toBeNull();
    expect(screen.queryByText(/Download SVG/)).toBeNull();
    cleanup();
    const failed = render(<ArmourDiagram result={native()} state="failed" />).container;
    expect(failed.querySelector('[data-state="failed"]')).not.toBeNull();
    expect(screen.queryByText(/Download SVG/)).toBeNull();
  });

  it('names an unsupported shape instead of drawing one', () => {
    const container = render(<ArmourDiagram result={{ schema: 'other' }} />).container;
    expect(container.querySelector('[data-state="unavailable"]')).not.toBeNull();
    expect(document.body.textContent).toMatch(/supported native result shape/);
    expect(screen.queryByText(/Download SVG/)).toBeNull();
  });

  it('reports a failed queued edit even while that edit remains pending for retry', () => {
    const host = {
      source: { parameters: {}, editing: {} }, catalogue: null, project: null,
      busy: false, error: null,
      state: { preview: native(), pending: 1, busy: false, error: 'Offline', diagnostics: [] },
    } as unknown as ShipDesignHost;
    const { container } = render(<ShipDesignChapter page="armour" host={host} disabled={false} />);
    expect(container.querySelector('[data-armour-diagram]')?.getAttribute('data-state')).toBe('failed');
    expect(container.querySelector('[data-armour-diagram] svg')).toBeNull();
    expect(screen.queryByText('Download SVG')).toBeNull();
  });
});

describe('armour diagram interaction', () => {
  it('renders the drawing, selects a region and reveals its ledger masses', () => {
    render(<ArmourDiagram result={native()} />);
    expect(document.querySelector('svg[role="group"]')).not.toBeNull();
    for (const role of ['belt_main', 'belt_ends', 'belt_upper', 'bulkhead', 'bulge', 'deck', 'conning']) {
      expect(document.querySelector(`[data-armour-region="${role}"]`)).not.toBeNull();
    }
    const button = document.querySelector('[data-armour-select="belt_main"]') as HTMLButtonElement;
    fireEvent.click(button);
    const panel = document.querySelector('[data-armour-panel="belt_main"]') as HTMLElement;
    expect(panel).not.toBeNull();
    expect(panel.textContent).toContain('1,114.57');
    expect(panel.textContent).toContain('estimated');
  });

  it('hands the region\'s source field back through the explicit Edit', () => {
    const onEditField = vi.fn();
    render(<ArmourDiagram result={native()} onEditField={onEditField} />);
    fireEvent.click(document.querySelector('[data-armour-select="bulkhead"]') as HTMLButtonElement);
    fireEvent.click(screen.getByRole('button', { name: 'Edit this region' }));
    expect(onEditField).toHaveBeenCalledWith('armour_bulkhead_length');
  });

  it('selects a region from the drawing itself, by keyboard', () => {
    render(<ArmourDiagram result={native()} />);
    const group = document.querySelector('[data-armour-region="deck"]') as SVGGElement;
    group.focus();
    fireEvent.keyDown(group, { key: 'Enter' });
    expect(document.querySelector('[data-armour-panel="deck"]')).not.toBeNull();
    expect(document.activeElement).toBe(group);
    fireEvent.keyDown(group, { key: ' ' });
    expect(document.activeElement).toBe(group);
  });

  it('marks a changed region against a compatible saved revision', () => {
    const container = render(<ArmourDiagram result={native({ armour: { ...native().armour, beltMain: 8 } })} baseline={native()} />).container;
    expect(container.querySelector('[data-armour-region="belt_main"]')?.getAttribute('data-changed')).toBe('true');
    expect(container.querySelector('[data-armour-region="belt_ends"]')?.getAttribute('data-changed')).toBeNull();
  });
});

describe('frozen report diagram', () => {
  it('is a static image with no selection or Edit, but keeps its downloads', () => {
    render(inLanguage(<ArmourDiagram result={native()} state="frozen" runId="run-7" contextLabel="design-normal · r2" />, 'en'));
    expect(document.querySelector('svg[role="img"]')).not.toBeNull();
    expect(document.querySelector('[data-armour-select]')).toBeNull();
    expect(screen.getByText('Download SVG')).toBeInTheDocument();
    expect(document.body.textContent).toContain('design-normal · r2');
  });

  it('prints Chinese region names for a Chinese reader', () => {
    render(inLanguage(<ArmourDiagram result={native()} />, 'zh-CN'));
    expect(document.querySelector('[data-armour-select="belt_main"]')?.textContent).toContain('主装甲带');
  });
});

describe('webgl-free uniqueness', () => {
  it('gives two mounted diagrams distinct defs ids', () => {
    const { container } = render(<div><ArmourDiagram result={native()} /><ArmourDiagram result={native()} /></div>);
    const svgs = [...container.querySelectorAll('svg')];
    expect(svgs.length).toBe(2);
    const ids = svgs.map(svg => [...svg.querySelectorAll('pattern')].map(pattern => pattern.id).join());
    expect(new Set(ids).size).toBe(2);
  });
});

describe('downloads', () => {
  it('shows a readable error if the browser cannot start an SVG download', () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => { throw new Error('Unavailable'); } });
    try {
      render(<ArmourDiagram result={native()} />);
      fireEvent.click(screen.getByText('Download SVG'));
      expect(screen.getByRole('alert')).toHaveTextContent(/SVG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('writes a real SVG download from an object URL it releases', () => {
    const createObjectURL = vi.fn(() => 'blob:armour');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    try {
      render(<ArmourDiagram result={native()} contextLabel="design-normal" />);
      fireEvent.click(screen.getByText('Download SVG'));
      expect(createObjectURL).toHaveBeenCalledTimes(1);
      expect(click).toHaveBeenCalledTimes(1);
    } finally {
      click.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it('says so in words when the PNG cannot be produced', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:armour', revokeObjectURL: () => {} });
    class BrokenImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      width = 960;
      height = 700;
      set src(_value: string) { queueMicrotask(() => this.onerror?.()); }
    }
    vi.stubGlobal('Image', BrokenImage);
    try {
      render(<ArmourDiagram result={native()} />);
      fireEvent.click(screen.getByText('Download PNG'));
      expect(await screen.findByRole('alert')).toHaveTextContent(/PNG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

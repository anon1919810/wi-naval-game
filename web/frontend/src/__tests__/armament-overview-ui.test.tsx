import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ArmamentComposition } from '../components/ArmamentComposition';
import { VesselDesignOverview } from '../components/VesselDesignOverview';
import { buildArmament } from '../components/armamentModel';
import { armamentSvg } from '../components/armamentExport';
import { inLanguage } from './locale';

/**
 * The armament composition and vessel overview as a reader meets them: a gated
 * sheet that withholds numbers while a reading is pending or failed, a drawing
 * whose batteries can be selected and whose explicit Edit hands a field back, a
 * frozen report that is read-only, and exports that produce one complete
 * standalone document and visible errors.
 */

afterEach(cleanup);

const group = (over: Record<string, unknown> = {}) => ({
  bank: 1, id: 'gun1', barrels: 12, mounts: 5, gunType: 1, mountType: 3, dateGun: 1910, calLength: 45,
  magazine: 150, layoutG1: 0, layoutG2: 0, selectorG1: 4, selectorG2: 6, perMountG1: 2, perMountG2: 3,
  mountsG1: 3, mountsG2: 2, mountSuperG1: 1, mountSubG1: 0, mountSuperG2: 1, mountDeckG1: 2, mountDeckG2: 1,
  mountSubG2: 0, superSuper: false, subSub: false, calibre: 6, armFace: 0, armBack: 0, armBottom: 0,
  autoShellWeight: 108.92068909286012, shellWeightDeclared: 100, shellWeight: 100.0016860961914,
  gunWeight: 73.5140174405157, mountWeight: 269.32618116578857, magazineWeight: 100.00168252470262,
  broadsideWeight: 1200.0202331542969, armWeight: 0, totalWeight: 342.8401986063043, ...over,
});

const zeroBanks = [2, 3, 4, 5].map(bank => ({ bank, id: `gun${bank}`, barrels: 0, mounts: 0, calibre: 0 }));

const native = (over: Record<string, unknown> = {}) => ({
  schema: 'plimsoll-ship-design-result-1', method_version: 'ship-design-native-v1',
  status: 'available', basis_condition_id: 'design-normal',
  hull: { length: 590.55, beam: 82.02, draught: 26.25 }, freeboard: { freeboard: 17.04 },
  armour: { beltMain: 7, deck: 2, deckCoverage: 0 },
  engine: { speedMax: 27, speedCruise: 14, hpMax: 72098.86, range: 7000, fuelArray: [true, true, false, false, false], engineArray: [false, false, true], driveArray: [false, true, false, false] },
  guns: { groups: [group(), ...zeroBanks] },
  ledger: { roles: {
    guns: { mode: 'estimated', estimate_t: 74.69, selected_mass_t: 74.69 },
    mounts: { mode: 'declared', estimate_t: 273.65, selected_mass_t: 300 },
    ammunition: { mode: 'estimated', estimate_t: 101.61, selected_mass_t: 101.61 },
    gun_armour: { mode: 'estimated', estimate_t: 0, selected_mass_t: 0 },
  } },
  balance: { selected_mass_t: 21120.54, estimated_mass_t: 21110.54, target_displacement_t: 21110.54, difference_t: 10 },
  ...over,
});

describe('armament composition states', () => {
  it('withholds the drawing and the numbers while pending or failed', () => {
    render(<ArmamentComposition result={native()} state="pending" />);
    expect(document.querySelector('[data-armament-composition][data-state="pending"]')).not.toBeNull();
    expect(screen.queryByText('Download SVG')).toBeNull();
    cleanup();
    render(<ArmamentComposition result={native()} state="failed" />);
    expect(document.querySelector('[data-armament-composition][data-state="failed"]')).not.toBeNull();
    expect(screen.queryByText('Download SVG')).toBeNull();
  });

  it('names an unsupported shape instead of drawing one', () => {
    render(<ArmamentComposition result={{ schema: 'other' }} />);
    expect(document.querySelector('[data-armament-composition][data-state="unavailable"]')).not.toBeNull();
    expect(document.body.textContent).toMatch(/supported native result shape/);
    expect(screen.queryByText('Download SVG')).toBeNull();
  });
});

describe('armament composition interaction', () => {
  it('renders the drawing, selects a battery and reveals its configuration and ledger', () => {
    render(<ArmamentComposition result={native()} />);
    expect(document.querySelector('svg[role="group"]')).not.toBeNull();
    for (const bank of [1, 2, 3, 4, 5]) {
      expect(document.querySelector(`[data-armament-bank="${bank}"]`)).not.toBeNull();
    }
    fireEvent.click(document.querySelector('[data-armament-select="1"]') as HTMLButtonElement);
    const panel = document.querySelector('[data-armament-panel="1"]') as HTMLElement;
    expect(panel).not.toBeNull();
    // The selected battery's own source estimate is shown, converted once into
    // the reader's chosen mass unit.
    expect(panel.textContent).toMatch(/74\.69\d* t/);
    // The global ledger is shown separately, with the manual declared policy
    // stated beside the two masses even though they are separate facts.
    const ledger = panel.querySelector('[data-armament-ledger]') as HTMLElement;
    expect(ledger.textContent).toContain('declared (manual)');
    expect(ledger.textContent).toContain('300 t');
    expect(ledger.textContent).toContain('estimated');
    // The ledger selected mass is never presented as a source estimate.
    expect(panel.textContent).not.toContain('300 long ton');
  });

  it('states the ledger policy in the drawing the composition shows', () => {
    render(<ArmamentComposition result={native()} />);
    // The on-screen composition renders the same serialized document a download
    // writes, so the policy word is present there too.
    expect(document.querySelector('svg')?.textContent).toContain('declared (manual)');
    expect(document.querySelector('svg')?.textContent).toContain('estimated');
  });

  it('hands the battery calibre field back through the explicit Edit', () => {
    const onEditField = vi.fn();
    render(<ArmamentComposition result={native()} onEditField={onEditField} />);
    fireEvent.click(document.querySelector('[data-armament-select="1"]') as HTMLButtonElement);
    fireEvent.click(screen.getByRole('button', { name: 'Edit this battery calibre' }));
    expect(onEditField).toHaveBeenCalledWith('gun1_calibre');
  });

  it('selects a battery from the drawing itself, by keyboard, without losing focus', () => {
    render(<ArmamentComposition result={native()} />);
    const bank = document.querySelector('[data-armament-bank="1"]') as SVGGElement;
    bank.focus();
    fireEvent.keyDown(bank, { key: 'Enter' });
    expect(document.querySelector('[data-armament-panel="1"]')).not.toBeNull();
    expect(document.activeElement).toBe(bank);
    fireEvent.keyDown(bank, { key: ' ' });
    expect(document.activeElement).toBe(bank);
  });

  it('marks a changed battery against a compatible saved revision', () => {
    const container = render(<ArmamentComposition result={native({ guns: { groups: [group({ calibre: 8 }), ...zeroBanks] } })} baseline={native()} />).container;
    expect(container.querySelector('[data-armament-bank="1"]')?.getAttribute('data-changed')).toBe('true');
    expect(container.querySelector('[data-armament-bank="2"]')?.getAttribute('data-changed')).toBeNull();
  });
});

describe('frozen report composition', () => {
  it('is a static image with no selection or Edit, but keeps its downloads', () => {
    render(inLanguage(<ArmamentComposition result={native()} state="frozen" runId="run-7" contextLabel="design-normal · r2" />, 'en'));
    expect(document.querySelector('svg[role="img"]')).not.toBeNull();
    expect(document.querySelector('[data-armament-select]')).toBeNull();
    expect(screen.getByText('Download SVG')).toBeInTheDocument();
    expect(document.body.textContent).toContain('design-normal · r2');
  });

  it('prints Chinese battery and fact names for a Chinese reader', () => {
    render(inLanguage(<ArmamentComposition result={native()} />, 'zh-CN'));
    expect(document.querySelector('[data-armament-select="1"]')?.textContent).toContain('炮组 1');
    fireEvent.click(document.querySelector('[data-armament-select="1"]') as HTMLButtonElement);
    expect(document.querySelector('[data-armament-panel="1"]')?.textContent).toContain('炮管');
  });
});

describe('standalone export document', () => {
  it('parses as XML and carries all five batteries independent of selection', () => {
    const svg = armamentSvg(buildArmament(native()), { language: 'en', prefs: { length: 'm', mass: 't', power: 'kW', speed: 'kn', angle: 'deg' }, uid: 'x', interactive: false });
    const parsed = new DOMParser().parseFromString(svg, 'image/svg+xml');
    expect(parsed.querySelector('parsererror')).toBeNull();
    expect(parsed.documentElement.namespaceURI).toBe('http://www.w3.org/2000/svg');
    expect(parsed.querySelectorAll('[data-armament-bank]')).toHaveLength(5);
    expect(parsed.querySelector('svg')?.getAttribute('xmlns')).toBe('http://www.w3.org/2000/svg');
  });

  it('keeps every battery in the on-screen drawing after a selection', () => {
    render(<ArmamentComposition result={native()} />);
    fireEvent.click(document.querySelector('[data-armament-select="3"]') as HTMLButtonElement);
    expect(document.querySelectorAll('[data-armament-bank]')).toHaveLength(5);
  });
});

describe('armament downloads', () => {
  it('shows a readable error if the browser cannot start an SVG download', () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => { throw new Error('Unavailable'); } });
    try {
      render(<ArmamentComposition result={native()} />);
      fireEvent.click(screen.getByText('Download SVG'));
      expect(screen.getByRole('alert')).toHaveTextContent(/SVG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it('says so in words when the PNG cannot be produced', async () => {
    vi.stubGlobal('URL', { ...URL, createObjectURL: () => 'blob:armament', revokeObjectURL: () => {} });
    class BrokenImage {
      onload: (() => void) | null = null;
      onerror: (() => void) | null = null;
      width = 960;
      height = 700;
      set src(_value: string) { queueMicrotask(() => this.onerror?.()); }
    }
    vi.stubGlobal('Image', BrokenImage);
    try {
      render(<ArmamentComposition result={native()} />);
      fireEvent.click(screen.getByText('Download PNG'));
      expect(await screen.findByRole('alert')).toHaveTextContent(/PNG could not/);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe('vessel overview', () => {
  it('shows six sections, each opening its own chapter', () => {
    const onOpenChapter = vi.fn();
    const container = render(<VesselDesignOverview result={native()} onOpenChapter={onOpenChapter} />).container;
    expect(container.querySelectorAll('[data-vessel-section]')).toHaveLength(6);
    for (const id of ['hull', 'freeboard', 'armament', 'armour', 'propulsion', 'weight']) {
      expect(container.querySelector(`[data-vessel-section="${id}"]`)).not.toBeNull();
    }
    fireEvent.click(container.querySelector('[data-vessel-open="guns"]') as HTMLButtonElement);
    expect(onOpenChapter).toHaveBeenCalledWith('guns');
    fireEvent.click(container.querySelector('[data-vessel-open="weights"]') as HTMLButtonElement);
    expect(onOpenChapter).toHaveBeenCalledWith('weights');
  });

  it('names every undeclared value as unknown, never zero', () => {
    const container = render(<VesselDesignOverview result={native({ hull: { length: 590.55 } })} />).container;
    const beam = container.querySelector('[data-vessel-fact="hull.beam"]') as HTMLElement;
    expect(beam.textContent).toContain('—');
  });

  it('labels a battery by its own number, not by a raw template', () => {
    const container = render(<VesselDesignOverview result={native()} />).container;
    const battery = container.querySelector('[data-vessel-fact="armament.bank1"]') as HTMLElement;
    expect(battery.querySelector('dt')?.textContent).toBe('Battery 1');
    expect(battery.textContent).not.toContain('{bank}');
    expect(battery.querySelector('dd')?.textContent).toContain('6 in');
  });

  it('states the frozen reading in frozen words and offers no navigation', () => {
    const onOpenChapter = vi.fn();
    const container = render(<VesselDesignOverview result={native()} state="frozen" onOpenChapter={onOpenChapter} />).container;
    expect(container.querySelectorAll('[data-vessel-open]')).toHaveLength(0);
    expect(container.textContent).toContain('Read-only');
    expect(container.textContent).not.toContain('confirmed draft as one design');
  });

  it('offers no navigation button when the host supplies no chapter callback', () => {
    const container = render(<VesselDesignOverview result={native()} />).container;
    expect(container.querySelectorAll('[data-vessel-open]')).toHaveLength(0);
    expect(container.querySelectorAll('[data-vessel-section]')).toHaveLength(6);
  });

  it('states each armament ledger policy beside its masses in the weight section', () => {
    const container = render(<VesselDesignOverview result={native()} />).container;
    const guns = container.querySelector('[data-vessel-fact="weight.ledger.guns"]') as HTMLElement;
    expect(guns.textContent).toContain('estimated');
    const mounts = container.querySelector('[data-vessel-fact="weight.ledger.mounts"]') as HTMLElement;
    expect(mounts.textContent).toContain('declared (manual)');
  });

  it('withholds every fact while an edit is pending or failed', () => {
    render(<VesselDesignOverview result={native()} state="pending" />);
    expect(document.querySelector('[data-vessel-overview][data-state="pending"]')).not.toBeNull();
    expect(document.querySelectorAll('[data-vessel-section]')).toHaveLength(0);
    cleanup();
    render(<VesselDesignOverview result={{ schema: 'other' }} />);
    expect(document.querySelector('[data-vessel-overview][data-state="unavailable"]')).not.toBeNull();
  });
});

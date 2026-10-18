import { useEffect, useState } from 'react';

import * as api from '../api';
import { readSps3b3Catalog, type Sps3b3Catalogue } from './sps3b3Model';

/**
 * The read-only field catalogue, for surfaces that have no editor host.
 *
 * The report's frozen summary needs the same curated field labels and resolved
 * units the workbench editor uses, but it only ever reads a saved result — it
 * must not ask for a preview of a historical run. The catalogue is a static
 * description of the interface, so one read is cached for the lifetime of the
 * page and shared by every summary that mounts.
 *
 * A failed read is not cached: the next summary that mounts may try again. The
 * hook is allowed to return `null` while the catalogue is unavailable, and the
 * panel then falls back to the recovered register names rather than inventing
 * labels.
 */

let cached: Sps3b3Catalogue | null = null;
let pending: Promise<Sps3b3Catalogue> | null = null;

function catalogue(): Promise<Sps3b3Catalogue> {
  if (!pending) {
    pending = api.designCatalog().then(raw => {
      cached = readSps3b3Catalog(raw);
      return cached;
    }).catch(error => {
      pending = null;
      throw error;
    });
  }
  return pending;
}

export function useDesignCatalogue(enabled: boolean): Sps3b3Catalogue | null {
  const [value, setValue] = useState<Sps3b3Catalogue | null>(cached);

  useEffect(() => {
    if (!enabled) return;
    if (cached) { setValue(cached); return; }
    let live = true;
    catalogue().then(next => { if (live) setValue(next); }).catch(() => {});
    return () => { live = false; };
  }, [enabled]);

  return value;
}

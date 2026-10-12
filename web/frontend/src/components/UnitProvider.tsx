import { createContext, useContext, useMemo, type ReactNode } from 'react';

import {
  burnRateText, CANONICAL_PREFERENCES, classifyKey, displayNumber, displayUnit, displayValue, formatNumber,
  fromDisplay, inputText, readPreferences, toDisplay, unitLabel, type Dimension, type DisplayPreferences,
} from './units';
import { useLanguage } from '../portfolio/LanguageProvider';
import { useWorkspaceCopy } from '../i18n/workspace';

// Display units are a reading choice only. A provider wraps the workbench (from
// the edited draft) and a run or report (from the immutable result snapshot), so
// a stored value, fingerprint or export is never touched by a preference change.

export interface UnitApi {
  prefs: DisplayPreferences;
  /** The unit a reader currently sees for this dimension. */
  unit(dimension: Dimension): string;
  /** Displayed value with its unit; unknown stays the unknown marker. */
  text(value: unknown, dimension: Dimension, storedUnit?: string): string;
  /** Displayed number only, for table cells and axes. */
  number(value: unknown, dimension: Dimension, storedUnit?: string): string;
  /** Displayed numeric value, or null when the stored value is unknown. */
  value(value: unknown, dimension: Dimension, storedUnit?: string): number | null;
  /** Controlled-input text for a stored value. */
  typed(storedValue: unknown, dimension: Dimension, storedUnit?: string): string;
  /** Typed (displayed) value converted back into the field's stored unit. */
  stored(typedValue: unknown, dimension: Dimension, storedUnit?: string): number | null;
  /** Convert a data/result key, using the unit that key is stored in. */
  keyed(key: string, value: unknown): string;
  keyedNumber(key: string, value: unknown): string;
  /** Defined compound burn rate: t/day follows the reader's mass unit. */
  burn(tPerDay: unknown): string;
}

// An unclassified value keeps its canonical text, including the unknown marker.
function rawText(w: Copy, value: unknown): string {
  if (value === null || value === undefined) return w('units.unknown');
  if (typeof value === 'number') return formatNumber(value);
  if (typeof value === 'boolean') return value ? w('units.yes') : w('units.no');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

/** The three words a value can be when it is not a number. */
type Copy = (key: 'units.unknown' | 'units.yes' | 'units.no') => string;

function build(prefs: DisplayPreferences, w: Copy): UnitApi {
  const raw = (value: unknown) => rawText(w, value);
  const shown = (value: unknown, dimension: Dimension, storedUnit?: string) => {
    // An unknown or non-numeric value stays explicitly unknown; it never becomes
    // NaN or a zero with a unit.
    const displayed = toDisplay(dimension, value, prefs, storedUnit);
    return displayed === null ? w('units.unknown')
      : `${formatNumber(displayed)} ${unitLabel(dimension, displayUnit(dimension, prefs))}`;
  };
  return {
    prefs,
    unit: dimension => unitLabel(dimension, displayUnit(dimension, prefs)),
    text: (value, dimension, storedUnit) => shown(value, dimension, storedUnit),
    number: (value, dimension, storedUnit) => {
      const displayed = toDisplay(dimension, value, prefs, storedUnit);
      return displayed === null ? w('units.unknown') : formatNumber(displayed);
    },
    value: (value, dimension, storedUnit) => displayValue(dimension, value, prefs, storedUnit),
    typed: (storedValue, dimension, storedUnit) => inputText(dimension, storedValue, prefs, storedUnit),
    stored: (typedValue, dimension, storedUnit) => fromDisplay(dimension, typedValue, prefs, storedUnit),
    keyed: (key, value) => {
      const kind = classifyKey(key);
      return kind ? shown(value, kind.dimension, kind.storedUnit) : raw(value);
    },
    keyedNumber: (key, value) => {
      const kind = classifyKey(key);
      if (!kind) return raw(value);
      const displayed = toDisplay(kind.dimension, value, prefs, kind.storedUnit);
      return displayed === null ? w('units.unknown') : formatNumber(displayed);
    },
    burn: tPerDay => burnRateText(tPerDay, prefs),
  };
}

// The default context is the English unit reader, exactly as it has always been,
// so a component rendered on its own — a page in a test, an editor beside the
// preferences — keeps the strings it always printed.
const UnitContext = createContext<UnitApi>(build(CANONICAL_PREFERENCES, key => ({
  'units.unknown': 'Unknown', 'units.yes': 'Yes', 'units.no': 'No',
}[key])));

export function UnitProvider({ preferences, children }: { preferences: unknown; children: ReactNode }) {
  // The unit reader follows the one language state for its own three words. The
  // numbers, the unit symbols and the stored values are untouched by it: this is
  // presentation only, and the saved snapshot and every export stay canonical.
  const w = useWorkspaceCopy();
  const { language } = useLanguage();
  const api = useMemo(() => build(readPreferences(preferences), w), [preferences, w, language]);
  return <UnitContext.Provider value={api}>{children}</UnitContext.Provider>;
}

export function useUnits(): UnitApi {
  return useContext(UnitContext);
}

export { displayNumber };
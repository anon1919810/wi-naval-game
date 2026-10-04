import { createContext, useContext, useMemo, type ReactNode } from 'react';

import {
  burnRateText, CANONICAL_PREFERENCES, classifyKey, displayNumber, displayUnit, displayValue, formatNumber,
  fromDisplay, inputText, readPreferences, toDisplay, unitLabel, type Dimension, type DisplayPreferences,
} from './units';

// Display units are a reading choice only. A provider wraps the workbench (from
// the edited draft) and a run or report (from the immutable result snapshot), so
// a stored value, fingerprint or export is never touched by a preference change.

export interface UnitApi {
  prefs: DisplayPreferences;
  /** The unit a reader currently sees for this dimension. */
  unit(dimension: Dimension): string;
  /** Displayed value with its unit; unknown stays 未知. */
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
function rawText(value: unknown): string {
  if (value === null || value === undefined) return '未知';
  if (typeof value === 'number') return formatNumber(value);
  if (typeof value === 'boolean') return value ? '是' : '否';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function build(prefs: DisplayPreferences): UnitApi {
  const shown = (value: unknown, dimension: Dimension, storedUnit?: string) => {
    // An unknown or non-numeric value stays explicitly unknown; it never becomes
    // NaN or a zero with a unit.
    const displayed = toDisplay(dimension, value, prefs, storedUnit);
    return displayed === null ? '未知'
      : `${formatNumber(displayed)} ${unitLabel(dimension, displayUnit(dimension, prefs))}`;
  };
  return {
    prefs,
    unit: dimension => unitLabel(dimension, displayUnit(dimension, prefs)),
    text: (value, dimension, storedUnit) => shown(value, dimension, storedUnit),
    number: (value, dimension, storedUnit) => {
      const displayed = toDisplay(dimension, value, prefs, storedUnit);
      return displayed === null ? '未知' : formatNumber(displayed);
    },
    value: (value, dimension, storedUnit) => displayValue(dimension, value, prefs, storedUnit),
    typed: (storedValue, dimension, storedUnit) => inputText(dimension, storedValue, prefs, storedUnit),
    stored: (typedValue, dimension, storedUnit) => fromDisplay(dimension, typedValue, prefs, storedUnit),
    keyed: (key, value) => {
      const kind = classifyKey(key);
      return kind ? shown(value, kind.dimension, kind.storedUnit) : rawText(value);
    },
    keyedNumber: (key, value) => {
      const kind = classifyKey(key);
      if (!kind) return rawText(value);
      const displayed = toDisplay(kind.dimension, value, prefs, kind.storedUnit);
      return displayed === null ? '未知' : formatNumber(displayed);
    },
    burn: tPerDay => burnRateText(tPerDay, prefs),
  };
}

const UnitContext = createContext<UnitApi>(build(CANONICAL_PREFERENCES));

export function UnitProvider({ preferences, children }: { preferences: unknown; children: ReactNode }) {
  const api = useMemo(() => build(readPreferences(preferences)), [preferences]);
  return <UnitContext.Provider value={api}>{children}</UnitContext.Provider>;
}

export function useUnits(): UnitApi {
  return useContext(UnitContext);
}

export { displayNumber };
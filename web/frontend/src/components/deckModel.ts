import type { ProjectDocument } from '../types';

// Declared deck freeboard input (draft.deck) and its typed accessors.
// `null` always means "unknown" — it must never be coerced to 0 when serialised.

type SourceDeclaration = string | Record<string, unknown> | null;
function sourceDeclaration(raw: unknown): SourceDeclaration {
  return typeof raw === 'string' ? raw : raw && typeof raw === 'object' && !Array.isArray(raw) ? raw as Record<string, unknown> : null;
}

export interface MeasureField {
  value: number | null;
  source: SourceDeclaration;
  estimate: boolean | null;
}

export interface DeckPoint {
  id: string;
  x_m: number | null;
  y_m: number | null;
  z_m: number | null;
  freeboard_m: MeasureField;
}

export interface DeckSegment {
  id: string;
  aft_point_id: string | null;
  fore_point_id: string | null;
  source: SourceDeclaration;
  estimate: boolean | null;
}

export interface DeckInput {
  estimate: boolean | null;
  source: SourceDeclaration;
  points: DeckPoint[];
  segments: DeckSegment[];
  reference_length_m: MeasureField;
}

export function normalizeMeasure(raw: unknown): MeasureField {
  if (!raw || typeof raw !== 'object') return { value: null, source: null, estimate: null };
  const r = raw as Record<string, unknown>;
  const estimate = r.estimate === true ? true : r.estimate === false ? false : null;
  const value = typeof r.value === 'number' && Number.isFinite(r.value) ? r.value : null;
  const source = sourceDeclaration(r.source);
  return { value, source, estimate };
}

export function normalizePoint(raw: unknown): DeckPoint {
  if (!raw || typeof raw !== 'object') {
    return { id: '', x_m: null, y_m: null, z_m: null, freeboard_m: { value: null, source: null, estimate: null } };
  }
  const r = raw as Record<string, unknown>;
  const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
  return {
    id: typeof r.id === 'string' ? r.id : '',
    x_m: num(r.x_m),
    y_m: num(r.y_m),
    z_m: num(r.z_m),
    freeboard_m: normalizeMeasure(r.freeboard_m),
  };
}

export function normalizeSegment(raw: unknown): DeckSegment {
  if (!raw || typeof raw !== 'object') {
    return { id: '', aft_point_id: null, fore_point_id: null, source: null, estimate: null };
  }
  const r = raw as Record<string, unknown>;
  const estimate = r.estimate === true ? true : r.estimate === false ? false : null;
  const str = (v: unknown) => (typeof v === 'string' ? v : null);
  return {
    id: str(r.id) ?? '',
    aft_point_id: str(r.aft_point_id),
    fore_point_id: str(r.fore_point_id),
    source: sourceDeclaration(r.source),
    estimate,
  };
}

export function emptyDeck(): DeckInput {
  return {
    estimate: null,
    source: null,
    points: [],
    segments: [],
    reference_length_m: { value: null, source: null, estimate: null },
  };
}

export function getDeck(draft: ProjectDocument): DeckInput {
  const raw = (draft as Record<string, unknown>).deck;
  if (!raw || typeof raw !== 'object') return emptyDeck();
  const r = raw as Record<string, unknown>;
  const estimate = r.estimate === true ? true : r.estimate === false ? false : null;
  const source = sourceDeclaration(r.source);
  return {
    estimate,
    source,
    points: Array.isArray(r.points) ? r.points.map(normalizePoint) : [],
    segments: Array.isArray(r.segments) ? r.segments.map(normalizeSegment) : [],
    reference_length_m: normalizeMeasure(r.reference_length_m),
  };
}

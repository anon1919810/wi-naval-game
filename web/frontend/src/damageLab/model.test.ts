import { describe, expect, it } from 'vitest';
import { bodyPoint, attitudeRows, seaHeight, clippedBoxFaces, acceptedWaterFaces } from './geometry';
import { frameAt, visibleResult } from './model';
import type { LabResult, LabRun, TankState } from './types';

describe('damage laboratory replay and projection', () => {
  it('uses event indices for simultaneous events and clamps to accepted frames', () => {
    const result = { snapshots: [{ event_index: -1, time_s: 0 }, { event_index: 0, time_s: 0 },
      { event_index: 1, time_s: 0 }, { event_index: 2, time_s: 1 }] } as LabResult;
    expect(frameAt(result, 1)?.event_index).toBe(0);
    expect(frameAt(result, 2)?.event_index).toBe(1);
    expect(frameAt(result, 1000)?.time_s).toBe(1);
    expect(frameAt(result, -1)?.event_index).toBe(-1);
  });
  it('never shows an old result under a changed draft, condition or revision', () => {
    const experiment = { impact: { severity: .5 }, rules: { estimate: true } };
    const result = {} as LabResult;
    const run = { project_id: 'p', revision: 1, condition_id: 'c', request: { experiment }, result } as LabRun;
    expect(visibleResult(run, 'p', 1, 'c', experiment)).toBe(result);
    expect(visibleResult(run, 'p', 1, 'c', { ...experiment, impact: { severity: .6 } })).toBeNull();
    expect(visibleResult(run, 'p', 2, 'c', experiment)).toBeNull();
    expect(visibleResult(run, 'p', 1, 'other', experiment)).toBeNull();
    expect(visibleResult(run, 'other', 1, 'c', experiment)).toBeNull();
    expect(visibleResult(run, 'p', 1, 'c', { rules: experiment.rules, impact: experiment.impact })).toBe(result);
  });
  it('maps keel coordinates and raw hull datum without reversing starboard', () => {
    expect(bodyPoint([1, 2, 3])).toEqual([1, 3, -2]);
    expect(bodyPoint([1, 2, -6.9], -9.9)).toEqual([1, 3, -2]);
    expect(seaHeight({ p: 0, q: 0, waterline_d_m: -3.9 }, -9.9)).toBeCloseTo(6);
  });
  it('matches the core vertical normal for combined heel and trim', () => {
    const p = .2, q = -.3;
    const rows = attitudeRows(p, q);
    const vertical = rows[1][0]*2 + rows[1][1]*4 + rows[1][2]*-3;
    expect(vertical).toBeCloseTo((4-p*2-q*3) / Math.sqrt(1+p*p+q*q));
    for (const row of rows) expect(Math.hypot(...row)).toBeCloseTo(1);
  });
  it('clips visual water to the native liquid plane instead of a fake fill cube', () => {
    const box = { center_m: [0, 0, 2] as [number, number, number], size_m: [2, 2, 4] as [number, number, number] };
    const faces = clippedBoxFaces(box, [0, 0, 1], 1);
    expect(faces.length).toBe(6);
    expect(Math.max(...faces.flat().map(p => p[2]))).toBeCloseTo(1);
    expect(Math.min(...faces.flat().map(p => p[2]))).toBe(0);
    expect(clippedBoxFaces(box, [0, 0, 1], -1)).toEqual([]);
  });
  it('keeps full accepted water visible without inventing a partial free surface', () => {
    const box = { center_m: [0, 0, 2] as [number, number, number], size_m: [2, 2, 4] as [number, number, number] };
    const full: TankState = { tank_id: 'lab-water:room', volume_m3: 12.8, fill_fraction: 1,
      plane_normal: null, plane_offset_m: null };
    const faces = acceptedWaterFaces(box, full);
    expect(faces).toHaveLength(6);
    expect(Math.max(...faces.flat().map(p=>p[2]))).toBe(4);
    expect(acceptedWaterFaces(box, { ...full, volume_m3: 0, fill_fraction: 0 })).toEqual([]);
    expect(acceptedWaterFaces(box, { ...full, volume_m3: 4, fill_fraction: .25 })).toEqual([]);
    expect(Math.max(...acceptedWaterFaces(box, { ...full, volume_m3: 3.2, fill_fraction: .25,
      plane_normal: [0,0,1], plane_offset_m: 1 }).flat().map(p=>p[2]))).toBe(1);
  });
});

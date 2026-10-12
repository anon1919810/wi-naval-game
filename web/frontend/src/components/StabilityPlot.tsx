import { useEffect, useState } from 'react';

import type { StageEnvelope } from '../types';
import { useUnits } from './UnitProvider';
import { useWorkspaceCopy } from '../i18n/workspace';

type Point = { angle_deg: number; gz_m: number };

// The curve geometry uses canonical values (scaling is unit independent); the
// caption, axis text and table show the reader's units.
export function StabilityPlot({ stage }: { stage: StageEnvelope }) {
  const w = useWorkspaceCopy();
  const units = useUnits();
  const rows = Array.isArray(stage.data?.rows) ? stage.data.rows : [];
  const points = rows.filter((row): row is Point => Boolean(row && typeof row === 'object' && typeof row.angle_deg === 'number' && typeof row.gz_m === 'number'));
  if (points.length < 2) return null;
  const angles = points.map(point => point.angle_deg);
  const values = points.map(point => point.gz_m);
  const minX = Math.min(...angles), maxX = Math.max(...angles);
  const minY = Math.min(0, ...values), maxY = Math.max(0, ...values);
  const sx = (angle: number) => 38 + (angle - minX) / (maxX - minX || 1) * 492;
  const sy = (gz: number) => 157 - (gz - minY) / (maxY - minY || 1) * 126;
  const angleUnit = units.unit('angle');
  const gzUnit = units.unit('length');
  return <figure className="stability-plot">
    <figcaption>{w('plot.caption', { angle: angleUnit, gz: gzUnit })}</figcaption>
    <svg viewBox="0 0 560 190" role="img" aria-label={w('plot.aria', { angle: angleUnit, gz: gzUnit })}>
      <path className="plot-axis" d={`M38 ${sy(0)} H530 M38 20 V157`} />
      <polyline className="plot-line" points={points.map(point => `${sx(point.angle_deg)},${sy(point.gz_m)}`).join(' ')} />
      {points.map((point, index) => <circle key={index} cx={sx(point.angle_deg)} cy={sy(point.gz_m)} r="3" />)}
    </svg>
    <table><caption>{w('plot.captionTable')}</caption>
      <thead><tr><th>{w('plot.th.angle', { angle: angleUnit })}</th><th>{w('plot.th.gz', { gz: gzUnit })}</th></tr></thead>
      <tbody>{points.map((point, index) => <tr key={index}>
        <td>{units.number(point.angle_deg, 'angle')}</td><td>{units.number(point.gz_m, 'length')}</td>
      </tr>)}</tbody></table>
  </figure>;
}
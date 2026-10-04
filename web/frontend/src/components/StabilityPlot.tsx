import { useEffect, useState } from 'react';

import type { StageEnvelope } from '../types';
import { useUnits } from './UnitProvider';

type Point = { angle_deg: number; gz_m: number };

// The curve geometry uses canonical values (scaling is unit independent); the
// caption, axis text and table show the reader's units.
export function StabilityPlot({ stage }: { stage: StageEnvelope }) {
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
    <figcaption>GZ 稳性曲线 · 来自本次保存的运行 · 横倾 {angleUnit} · GZ {gzUnit}</figcaption>
    <svg viewBox="0 0 560 190" role="img" aria-label={`GZ 随横倾角（${angleUnit}）变化，GZ 单位 ${gzUnit}`}>
      <path className="plot-axis" d={`M38 ${sy(0)} H530 M38 20 V157`} />
      <polyline className="plot-line" points={points.map(point => `${sx(point.angle_deg)},${sy(point.gz_m)}`).join(' ')} />
      {points.map((point, index) => <circle key={index} cx={sx(point.angle_deg)} cy={sy(point.gz_m)} r="3" />)}
    </svg>
    <table><caption>曲线数据表</caption>
      <thead><tr><th>横倾角 ({angleUnit})</th><th>GZ ({gzUnit})</th></tr></thead>
      <tbody>{points.map((point, index) => <tr key={index}>
        <td>{units.number(point.angle_deg, 'angle')}</td><td>{units.number(point.gz_m, 'length')}</td>
      </tr>)}</tbody></table>
  </figure>;
}
import { useState } from 'react';
import type { RadarAxis } from '../lib/api';

const CX = 150;
const CY = 150;
const R = 130;
const RINGS = [25, 50, 75];
const VIEW_BOX = '-124 -46 512 380';
const DENSE_AXES = 7;

export function spokePoint(pct: number, index: number, total: number, radius = R) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const r = (Math.max(0, Math.min(100, pct)) / 100) * radius;
  return { x: CX + r * Math.cos(angle), y: CY + r * Math.sin(angle) };
}

const polygon = (pct: (i: number) => number, total: number, radius = R) =>
  Array.from({ length: total }, (_, i) => {
    const p = spokePoint(pct(i), i, total, radius);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ');

export default function Radar({ axes, title }: { axes: RadarAxis[]; title: string }) {
  const [active, setActive] = useState<number | null>(null);
  if (axes.length < 3) return null; // fewer than three spokes is not a shape

  const n = axes.length;
  const shape = polygon((i) => axes[i]!.percentile, n);
  const subject = title.toLowerCase().includes('club') ? 'club' : 'player';
  const dense = n >= DENSE_AXES;
  const hasInverted = axes.some((a) => a.lower_is_better);

  return (
    <div className="radar">
      <svg
        viewBox={VIEW_BOX}
        className="radar-plot"
        role="img"
        aria-label={`${title}. ${axes
          .map((a) => `${a.label}: ${a.value}, ${a.percentile}th percentile`)
          .join('. ')}`}
      >
        <g className="radar-grid">
          {RINGS.map((ring) => (
            <polygon key={ring} points={polygon(() => ring, n)} />
          ))}
          {axes.map((a, i) => {
            const p = spokePoint(100, i, n);
            return <line key={a.key} x1={CX} y1={CY} x2={p.x} y2={p.y} />;
          })}
        </g>
        <polygon className="radar-bound" points={polygon(() => 100, n)} />

        <polygon className="radar-area" points={shape} />
        <polygon className="radar-line" points={shape} />

        {axes.map((a, i) => {
          const p = spokePoint(a.percentile, i, n);
          return (
            <g key={a.key}>
              <circle className="radar-dot" cx={p.x} cy={p.y} r={4} />
              <circle
                cx={p.x}
                cy={p.y}
                r={14}
                fill="transparent"
                onMouseEnter={() => setActive(i)}
                onMouseLeave={() => setActive((v) => (v === i ? null : v))}
              />
            </g>
          );
        })}

        {axes.map((a, i) => {
          const p = spokePoint(dense ? 122 : 128, i, n);
          const anchor = p.x > CX + 6 ? 'start' : p.x < CX - 6 ? 'end' : 'middle';
          const y = dense || p.y >= CY - 10 ? p.y : p.y - 15;
          return (
            <g
              key={a.key}
              className={[
                'radar-label',
                dense ? 'is-dense' : '',
                active === i ? 'is-active' : '',
              ].join(' ')}
            >
              <text x={p.x} y={y} textAnchor={anchor}>
                {a.label}
              </text>
              {!dense && (
                <text x={p.x} y={y + 15} textAnchor={anchor} className="radar-value">
                  {a.value}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      <p className="radar-readout" aria-live="polite">
        {active !== null ? (
          <>
            <strong>{axes[active]!.label}</strong> {axes[active]!.value} ·{' '}
            {axes[active]!.percentile}th percentile
          </>
        ) : (
          <span className="muted">Hover a point for its rank.</span>
        )}
      </p>

      <details className="radar-table">
        <summary>How to read this</summary>
        <p className="muted radar-help">
          Each spoke is this {subject}'s percentile against the league — the outer edge
          is the league best.{' '}
          {dense
            ? 'Hover a point, or open the table, for the underlying rate.'
            : 'Figures beside each spoke are the actual rates, not the percentile.'}
          {hasInverted
            ? ' Where a smaller number is better — turnovers, opponent shooting — the ranking is flipped, so further out always means better.'
            : ''}
        </p>
      </details>

      <details className="radar-table">
        <summary>Table view</summary>
        <table>
          <thead>
            <tr>
              <th style={{ textAlign: 'left' }}>Metric</th>
              <th>Rate</th>
              <th>Percentile</th>
            </tr>
          </thead>
          <tbody>
            {axes.map((a) => (
              <tr key={a.key}>
                <td style={{ textAlign: 'left' }}>
                  {a.label}
                  {a.lower_is_better && <span className="muted"> (lower is better)</span>}
                </td>
                <td className="num">{a.value}</td>
                <td className="num">{a.percentile}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}

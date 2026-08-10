/**
 * Radar of a player's or club's core rates.
 *
 * The honest-radar problem: raw figures on shared spokes are meaningless —
 * "24 points" and "1.6 assists" would draw the same length if the axes were
 * scaled independently, and the shape would be an artefact of the units. So
 * the radius is one thing only: **percentile against the league**, computed by
 * the API. The raw figure rides along as a direct label, never tooltip-gated.
 *
 * A single series, so no legend — the heading names it. The values are also
 * available as a table below, which is the accessible twin of the shape.
 */

import { useState } from 'react';
import type { RadarAxis } from '../lib/api';

const CX = 150;
const CY = 150;
const R = 130;
// Inner rings only. The outer ring is the scale's edge — "league best" — so it
// is drawn separately and darker than the grid it closes.
const RINGS = [25, 50, 75];
// The viewBox reserves room for the spoke labels, which sit outside the outer
// ring. Kept as tight as the longest label allows: every extra unit of margin
// is width the plot itself does not get.
const VIEW_BOX = '-104 -40 460 362';

/** Spoke `i` of `total`, at `pct` of full radius. First spoke points up. */
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
        {/* recessive hairline grid, solid — dashes would read as a threshold */}
        <g className="radar-grid">
          {RINGS.map((ring) => (
            <polygon key={ring} points={polygon(() => ring, n)} />
          ))}
          {axes.map((a, i) => {
            const p = spokePoint(100, i, n);
            return <line key={a.key} x1={CX} y1={CY} x2={p.x} y2={p.y} />;
          })}
        </g>
        {/* the scale's edge: league best. Darker than the grid, lighter than
            the series, so the three layers stay in order. */}
        <polygon className="radar-bound" points={polygon(() => 100, n)} />

        <polygon className="radar-area" points={shape} />
        <polygon className="radar-line" points={shape} />

        {axes.map((a, i) => {
          const p = spokePoint(a.percentile, i, n);
          return (
            <g key={a.key}>
              <circle className="radar-dot" cx={p.x} cy={p.y} r={4} />
              {/* generous hit target: the 8px dot itself is far too small to aim at */}
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

        {/* direct labels: metric and its real figure, so the shape is readable
            without hovering anything */}
        {axes.map((a, i) => {
          const p = spokePoint(128, i, n);
          const anchor = p.x > CX + 6 ? 'start' : p.x < CX - 6 ? 'end' : 'middle';
          // Both lines hang below their anchor, so on the upper half they would
          // grow back toward the plot and collide with the spoke's own dot.
          const y = p.y < CY - 10 ? p.y - 15 : p.y;
          return (
            <g key={a.key} className={active === i ? 'radar-label is-active' : 'radar-label'}>
              <text x={p.x} y={y} textAnchor={anchor}>
                {a.label}
              </text>
              <text x={p.x} y={y + 15} textAnchor={anchor} className="radar-value">
                {a.value}
              </text>
            </g>
          );
        })}
      </svg>

      {/* Only the hover readout stays inline; the explanation is a disclosure,
          so the chart is not fronted by a paragraph every time. */}
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
          Each spoke is this {subject}'s percentile against the league — the outer edge is
          the league best. Figures beside each spoke are the actual rates, not the
          percentile, so the shape and the numbers answer different questions.
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
                <td style={{ textAlign: 'left' }}>{a.label}</td>
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

import { useCallback, useMemo, useRef, useState } from 'react';
import { gameClock, type GameTimeline } from '../lib/api';

const VB_W = 900;
const VB_H = 280;
const PAD = { top: 22, right: 16, bottom: 26, left: 40 };
const REGULATION = 2400;
const Q_LEN = 600;
const OT_LEN = 300;

interface Sample {
  t: number;
  home: number;
  away: number;
  margin: number;
}

export default function ScoreWorm({ tl }: { tl: GameTimeline }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<Sample | null>(null);

  const home = tl.home_club_code ?? 'HOME';
  const away = tl.away_club_code ?? 'AWAY';

  const samples: Sample[] = useMemo(() => {
    const out: Sample[] = [{ t: 0, home: 0, away: 0, margin: 0 }];
    for (const p of tl.points) {
      out.push({ t: p.t, home: p.home, away: p.away, margin: p.home - p.away });
    }
    return out;
  }, [tl]);

  const duration = tl.duration ?? REGULATION;
  const peak = Math.max(5, ...samples.map((s) => Math.abs(s.margin)));
  const domain = Math.ceil(peak / 5) * 5;

  const x = useCallback(
    (t: number) => PAD.left + (t / duration) * (VB_W - PAD.left - PAD.right),
    [duration],
  );
  const y = useCallback(
    (m: number) => {
      const h = VB_H - PAD.top - PAD.bottom;
      return PAD.top + h / 2 - (m / domain) * (h / 2);
    },
    [domain],
  );

  const stepPath = useMemo(() => {
    let d = `M ${x(0)} ${y(0)}`;
    let prev = 0;
    for (const s of samples) {
      d += ` L ${x(s.t)} ${y(prev)} L ${x(s.t)} ${y(s.margin)}`;
      prev = s.margin;
    }
    d += ` L ${x(duration)} ${y(prev)}`;
    return d;
  }, [samples, x, y, duration]);

  const areaPath = `${stepPath} L ${x(duration)} ${y(0)} L ${x(0)} ${y(0)} Z`;

  const rules: Array<{ t: number; label: string }> = [];
  for (let q = 1; q * Q_LEN < duration; q++) {
    const t = q * Q_LEN;
    if (t <= REGULATION) rules.push({ t, label: q === 4 ? 'END' : `Q${q + 1}` });
  }
  for (let o = 1; REGULATION + o * OT_LEN < duration; o++) {
    rules.push({ t: REGULATION + o * OT_LEN, label: `OT${o + 1}` });
  }

  const best = { home: samples[0]!, away: samples[0]! };
  for (const s of samples) {
    if (s.margin > best.home.margin) best.home = s;
    if (s.margin < best.away.margin) best.away = s;
  }

  const onMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const ux = ((event.clientX - rect.left) / rect.width) * VB_W;
    const t = ((ux - PAD.left) / (VB_W - PAD.left - PAD.right)) * duration;
    let found = samples[0]!;
    for (const s of samples) {
      if (s.t <= t) found = s;
      else break;
    }
    setHover(found);
  };

  const yTicks = [domain, domain / 2, 0, -domain / 2, -domain].filter(
    (v, i, arr) => arr.indexOf(v) === i,
  );

  return (
    <figure className="worm">
      <figcaption>
        <span className="legend">
          <span className="swatch home" aria-hidden="true" /> {home} ahead
        </span>
        <span className="legend">
          <span className="swatch away" aria-hidden="true" /> {away} ahead
        </span>
        <span className="muted">
          {hover
            ? `${gameClock(hover.t)} — ${home} ${hover.home}–${hover.away} ${away}`
            : `final ${home} ${tl.home_final}–${tl.away_final} ${away}`}
        </span>
      </figcaption>

      <svg
        ref={svgRef}
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        width="100%"
        role="img"
        aria-label={`Score margin over time. ${home} led by at most ${best.home.margin}, ${away} by at most ${-best.away.margin}. Final ${tl.home_final}–${tl.away_final}.`}
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        <clipPath id="worm-above">
          <rect x={0} y={0} width={VB_W} height={y(0)} />
        </clipPath>
        <clipPath id="worm-below">
          <rect x={0} y={y(0)} width={VB_W} height={VB_H - y(0)} />
        </clipPath>

        {yTicks.map((v) => (
          <g key={v}>
            <line x1={PAD.left} x2={VB_W - PAD.right} y1={y(v)} y2={y(v)} className="grid" />
            <text x={PAD.left - 6} y={y(v) + 4} className="tick" textAnchor="end">
              {v === 0 ? '0' : Math.abs(v)}
            </text>
          </g>
        ))}

        {rules.map((r) => (
          <g key={r.t}>
            <line x1={x(r.t)} x2={x(r.t)} y1={PAD.top} y2={VB_H - PAD.bottom} className="rule" />
            <text x={x(r.t)} y={VB_H - PAD.bottom + 16} className="tick" textAnchor="middle">
              {r.label}
            </text>
          </g>
        ))}

        <path d={areaPath} className="area home" clipPath="url(#worm-above)" />
        <path d={areaPath} className="area away" clipPath="url(#worm-below)" />
        <path d={stepPath} className="line home" clipPath="url(#worm-above)" />
        <path d={stepPath} className="line away" clipPath="url(#worm-below)" />

        <line x1={PAD.left} x2={VB_W - PAD.right} y1={y(0)} y2={y(0)} className="zero" />

        {best.home.margin > 0 && (
          <text x={x(best.home.t)} y={y(best.home.margin) - 6} className="peak" textAnchor="middle">
            +{best.home.margin}
          </text>
        )}
        {best.away.margin < 0 && (
          <text
            x={x(best.away.t)}
            y={y(best.away.margin) + 14}
            className="peak away"
            textAnchor="middle"
          >
            +{-best.away.margin}
          </text>
        )}

        {hover && (
          <g className="cursor">
            <line x1={x(hover.t)} x2={x(hover.t)} y1={PAD.top} y2={VB_H - PAD.bottom} />
            <circle cx={x(hover.t)} cy={y(hover.margin)} r={5} />
          </g>
        )}
      </svg>

      <style>{`
        .worm { margin: 0 0 1.4rem; }
        .worm figcaption {
          display: flex; flex-wrap: wrap; gap: 0.4rem 1.2rem;
          align-items: center; font-size: 0.78rem; margin-bottom: 0.4rem;
        }
        .worm .legend { display: inline-flex; align-items: center; gap: 0.4rem; font-weight: 700; }
        .worm .swatch { width: 0.8rem; height: 0.8rem; border: 1px solid var(--line); }
        .worm .swatch.home { background: var(--chart-home); }
        .worm .swatch.away { background: var(--chart-away); }
        .worm svg {
          border: 2px solid var(--line);
          box-shadow: 6px 6px 0 var(--line);
          background: var(--bg-raised);
          display: block;
          touch-action: none;
        }
        .worm .grid { stroke: var(--ghost); stroke-width: 1; }
        .worm .rule { stroke: var(--ghost); stroke-width: 1; stroke-dasharray: 3 4; }
        .worm .zero { stroke: var(--line); stroke-width: 1.5; }
        .worm .tick {
          font-family: inherit; font-size: 11px; fill: var(--text-muted);
        }
        .worm .area { stroke: none; opacity: 0.16; }
        .worm .area.home { fill: var(--chart-home); }
        .worm .area.away { fill: var(--chart-away); }
        .worm .line { fill: none; stroke-width: 2; stroke-linejoin: round; }
        .worm .line.home { stroke: var(--chart-home); }
        .worm .line.away { stroke: var(--chart-away); }
        .worm .peak {
          font-family: inherit; font-size: 12px; font-weight: 700; fill: var(--chart-home);
        }
        .worm .peak.away { fill: var(--chart-away); }
        .worm .cursor line { stroke: var(--accent); stroke-width: 1; }
        .worm .cursor circle { fill: var(--accent); stroke: var(--bg-raised); stroke-width: 2; }
      `}</style>
    </figure>
  );
}

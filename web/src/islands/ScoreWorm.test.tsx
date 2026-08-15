import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { GameTimeline, TimelinePoint } from '../lib/api';
import ScoreWorm from './ScoreWorm';

const VB_W = 900;
const VB_H = 280;

function point(t: number, home: number, away: number): TimelinePoint {
  return { t, home, away, quarter: 1, ot: 0, play_type: '2FGM', club_code: null, player_code: null };
}

const tl: GameTimeline = {
  game_code: 1,
  has_pbp: true,
  home_club_code: 'IST',
  away_club_code: 'TEL',
  home_final: 80,
  away_final: 83,
  duration: 2400,
  n_ot: 0,
  points: [
    point(60, 12, 0),
    point(600, 30, 25),
    point(1200, 45, 45),
    point(1800, 60, 70),
    point(2390, 80, 83),
  ],
};

function pathCoords(markup: string): Array<[number, number]> {
  const d = /class="line home"[^>]*d="([^"]+)"|d="([^"]+)"[^>]*class="line home"/.exec(markup);
  const raw = d?.[1] ?? d?.[2];
  expect(raw, 'line path should be rendered').toBeTruthy();
  return [...raw!.matchAll(/(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)/g)].map((m) => [
    Number(m[1]),
    Number(m[2]),
  ]);
}

describe('ScoreWorm', () => {
  const markup = renderToStaticMarkup(<ScoreWorm tl={tl} />);

  it('keeps every drawn point inside the viewBox', () => {
    const coords = pathCoords(markup);
    expect(coords.length).toBeGreaterThan(5);
    for (const [x, y] of coords) {
      expect(Number.isFinite(x) && Number.isFinite(y)).toBe(true);
      expect(x).toBeGreaterThanOrEqual(0);
      expect(x).toBeLessThanOrEqual(VB_W);
      expect(y).toBeGreaterThanOrEqual(0);
      expect(y).toBeLessThanOrEqual(VB_H);
    }
  });

  it('ends below the zero line, because the away side won', () => {
    const coords = pathCoords(markup);
    const [, lastY] = coords[coords.length - 1]!;
    const zeroY = 22 + (VB_H - 22 - 26) / 2; // PAD.top + plot height / 2
    expect(lastY).toBeGreaterThan(zeroY);
  });

  it('labels both peaks with the lead each side reached', () => {
    expect(markup).toContain('+12'); // home's best, early
    expect(markup).toContain('+10'); // away's best, at 60-70
  });

  it('describes the game for screen readers', () => {
    expect(markup).toMatch(/aria-label="[^"]*IST led by at most 12[^"]*80–83/);
  });

  it('draws a legend so identity is never color alone', () => {
    expect(markup).toContain('IST ahead');
    expect(markup).toContain('TEL ahead');
  });

  it('survives a game with no scoring events', () => {
    const empty = { ...tl, points: [], home_final: 0, away_final: 0 };
    expect(() => renderToStaticMarkup(<ScoreWorm tl={empty} />)).not.toThrow();
  });
});

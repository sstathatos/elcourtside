/** Only the pure helpers — the fetch layer is exercised by the manual pass. */

import { describe, expect, it } from 'vitest';
import { gameClock, isBoxscoreOnly, mmss, num, param, qs, shortDate, signed } from './api';

describe('mmss', () => {
  it('formats court time the way a boxscore does', () => {
    expect(mmss(0)).toBe('0:00');
    expect(mmss(65)).toBe('1:05');
    expect(mmss(1234.5)).toBe('20:35'); // seconds are fractional in the DB
  });

  it('shows an em dash rather than 0:00 for missing time', () => {
    expect(mmss(null)).toBe('—');
    expect(mmss(undefined)).toBe('—');
  });
});

describe('num / signed', () => {
  it('keeps decimals fixed so columns line up', () => {
    expect(num(22.14159, 1)).toBe('22.1');
    expect(num(7, 0)).toBe('7');
  });

  it('never prints NaN or null', () => {
    expect(num(null)).toBe('—');
    expect(num(Number.NaN)).toBe('—');
  });

  it('always signs plus/minus values', () => {
    expect(signed(14)).toBe('+14');
    expect(signed(-14)).toBe('-14');
    expect(signed(0)).toBe('0');
    expect(signed(null)).toBe('—');
  });
});

describe('gameClock', () => {
  it('maps elapsed seconds to the period clock', () => {
    expect(gameClock(0)).toBe('Q1 0:00');
    expect(gameClock(599)).toBe('Q1 9:59');
    expect(gameClock(600)).toBe('Q2 0:00');
    expect(gameClock(2399)).toBe('Q4 9:59');
  });

  it('continues into overtime', () => {
    expect(gameClock(2400)).toBe('Q4 10:00'); // buzzer, still regulation
    expect(gameClock(2401)).toBe('OT1 0:01');
    expect(gameClock(2701)).toBe('OT2 0:01');
  });
});

describe('qs', () => {
  it('drops empty values so /api/players?club= is never sent', () => {
    expect(qs({ season: 'E2025', club: undefined, limit: 50 })).toBe('?season=E2025&limit=50');
    expect(qs({ club: '' })).toBe('');
    expect(qs({})).toBe('');
  });

  it('keeps false, which is a meaningful desc value', () => {
    expect(qs({ desc: false })).toBe('?desc=false');
  });
});

describe('param', () => {
  it('reads the detail-view entity from the query string', () => {
    expect(param('code', '?code=42')).toBe('42');
    expect(param('code', '?club=OLY')).toBeNull();
  });
});

describe('shortDate', () => {
  it('formats UTC dates without shifting the day', () => {
    expect(shortDate('2025-09-30T18:00:00Z')).toBe('30 Sep 2025');
    expect(shortDate(null)).toBe('—');
    expect(shortDate('not a date')).toBe('—');
  });
});

describe('isBoxscoreOnly', () => {
  // 2005-06 predates play-by-play; no Final Four winner recorded for it either
  const season = {
    season_code: 'E2005',
    season_name: null,
    year: 2005,
    games: 200,
    computed_at: null,
    winner_club_code: null,
  };

  it('flags the pre-2007 era, where no play-by-play exists', () => {
    expect(isBoxscoreOnly({ ...season, games_with_pbp: 0 })).toBe(true);
    expect(isBoxscoreOnly({ ...season, games_with_pbp: 402 })).toBe(false);
    expect(isBoxscoreOnly(undefined)).toBe(false);
  });
});

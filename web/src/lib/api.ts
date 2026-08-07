/**
 * Typed client for the elcourtside API.
 *
 * Always same-origin `/api`: the ingress routes it in the cluster, Vite proxies
 * it in dev (see astro.config.mjs). No base-URL switching, no CORS in the
 * browser.
 *
 * There is no client-side cache here on purpose — the API sends
 * `Cache-Control: max-age=300` plus an ETag derived from when the metrics were
 * computed, so the browser's own cache handles repeats and revalidation.
 *
 * Types mirror the Pydantic models in api/app/models.py.
 */

export const API = '/api';

export interface Season {
  season_code: string;
  season_name: string | null;
  year: number | null;
  games: number;
  games_with_pbp: number;
  computed_at: string | null;
}

export interface Club {
  club_code: string;
  club_name: string | null;
  crest_url: string | null;
}

export interface StandingsRow {
  club_code: string;
  club_name: string | null;
  games: number | null;
  wins: number | null;
  losses: number | null;
  points_for: number | null;
  points_against: number | null;
  point_diff: number | null;
  rank: number | null;
}

export interface GameSummary {
  game_code: number;
  round: number | null;
  round_name: string | null;
  phase_type_code: string | null;
  utc_date: string | null;
  played: number | null;
  home_club_code: string | null;
  home_club_name: string | null;
  home_score: number | null;
  away_club_code: string | null;
  away_club_name: string | null;
  away_score: number | null;
  winner_club_code: string | null;
  pbp_status: string | null;
}

export interface BoxscoreLine {
  is_home: number;
  entry_type: string;
  player_code: string;
  club_code: string | null;
  player_name: string | null;
  dorsal: string | null;
  start_five: number | null;
  seconds_played: number | null;
  points: number | null;
  fg2m: number | null;
  fg2a: number | null;
  fg3m: number | null;
  fg3a: number | null;
  ftm: number | null;
  fta: number | null;
  reb_off: number | null;
  reb_def: number | null;
  reb_total: number | null;
  assists: number | null;
  steals: number | null;
  turnovers: number | null;
  blocks_favour: number | null;
  blocks_against: number | null;
  fouls_committed: number | null;
  fouls_received: number | null;
}

export interface PlayerGameMetric {
  player_code: string;
  club_code: string | null;
  is_home: number | null;
  pir: number | null;
  pm_computed: number | null;
  seconds_computed: number | null;
  fouls_drawn: number | null;
  clutch_seconds: number | null;
  clutch_points: number | null;
  clutch_pm: number | null;
}

export interface TeamGameMetric {
  club_code: string;
  is_home: number | null;
  points: number | null;
  possessions: number | null;
  fouls_drawn: number | null;
  max_run: number | null;
  max_run_detail: { points: number; start_s: number; end_s: number } | null;
  max_lead: number | null;
  lost: number | null;
  clutch_pts_for: number | null;
  clutch_pts_against: number | null;
  clutch_pm: number | null;
  clutch_seconds: number | null;
}

export interface GameDetail extends GameSummary {
  boxscore: BoxscoreLine[];
  player_metrics: PlayerGameMetric[];
  team_metrics: TeamGameMetric[];
}

export interface TimelinePoint {
  t: number;
  quarter: number;
  ot: number;
  home: number;
  away: number;
  play_type: string | null;
  club_code: string | null;
  player_code: string | null;
}

export interface GameTimeline {
  game_code: number;
  has_pbp: boolean;
  home_club_code: string | null;
  away_club_code: string | null;
  home_final: number | null;
  away_final: number | null;
  duration: number | null;
  n_ot: number | null;
  points: TimelinePoint[];
}

export interface TeamSeason {
  club_code: string;
  club_name: string | null;
  games: number | null;
  possessions_avg: number | null;
  fouls_drawn_per100: number | null;
  max_run: number | null;
  max_run_game: number | null;
  max_blown_lead: number | null;
  max_blown_lead_game: number | null;
  clutch_pts_for: number | null;
  clutch_pts_against: number | null;
  clutch_seconds: number | null;
  wins: number | null;
  losses: number | null;
  point_diff: number | null;
  rank: number | null;
}

export interface TeamGameLogRow {
  game_code: number;
  is_home: number | null;
  points: number | null;
  possessions: number | null;
  fouls_drawn: number | null;
  max_run: number | null;
  max_lead: number | null;
  lost: number | null;
  clutch_pm: number | null;
  utc_date: string | null;
  round: number | null;
  opponent_code: string | null;
  opponent_points: number | null;
}

export interface TeamDetail extends Omit<TeamSeason, 'games'> {
  games: TeamGameLogRow[];
}

export interface PlayerSeason {
  player_code: string;
  player_name: string | null;
  clubs: string | null;
  games_played: number | null;
  seconds: number | null;
  points: number | null;
  reb_total: number | null;
  assists: number | null;
  steals: number | null;
  blocks_favour: number | null;
  turnovers: number | null;
  fouls_drawn: number | null;
  pir_total: number | null;
  pir_avg: number | null;
  pir_per36: number | null;
  pm_total: number | null;
  pm_per36: number | null;
  clutch_seconds: number | null;
  clutch_points: number | null;
  clutch_pm: number | null;
  fouls_drawn_per100: number | null;
  headshot_url: string | null;
}

export interface PlayerGameLogRow {
  game_code: number;
  club_code: string | null;
  is_home: number | null;
  pir: number | null;
  pm_computed: number | null;
  seconds_computed: number | null;
  fouls_drawn: number | null;
  clutch_pm: number | null;
  points: number | null;
  reb_total: number | null;
  assists: number | null;
  seconds_played: number | null;
  utc_date: string | null;
  round: number | null;
  opponent_code: string | null;
}

export interface PlayerDetail extends PlayerSeason {
  games: PlayerGameLogRow[];
  /** Null for players the registry has no photo for (~3%). */
  headshot_url: string | null;
  action_url: string | null;
}

export interface RunRow {
  game_code: number;
  club_code: string;
  opponent_code: string | null;
  max_run: number | null;
  max_run_detail: string | null;
  points: number | null;
  utc_date: string | null;
  round: number | null;
}

export interface BlownLeadRow {
  game_code: number;
  club_code: string;
  opponent_code: string | null;
  max_lead: number | null;
  points: number | null;
  opponent_points: number | null;
  utc_date: string | null;
  round: number | null;
}

export interface ClutchIndex {
  players: Array<
    Pick<PlayerSeason, 'player_code' | 'player_name' | 'clubs' | 'games_played'> & {
      clutch_seconds: number | null;
      clutch_points: number | null;
      clutch_pm: number | null;
    }
  >;
  teams: Array<{
    club_code: string;
    club_name: string | null;
    clutch_pts_for: number | null;
    clutch_pts_against: number | null;
    clutch_seconds: number | null;
    clutch_pm: number | null;
  }>;
}

export interface FoulsDrawnIndex {
  players: Array<
    Pick<PlayerSeason, 'player_code' | 'player_name' | 'clubs' | 'games_played'> & {
      fouls_drawn: number | null;
      fouls_drawn_per100: number | null;
    }
  >;
  teams: Array<{
    club_code: string;
    club_name: string | null;
    games: number | null;
    fouls_drawn_per100: number | null;
    possessions_avg: number | null;
  }>;
}

export type PlayerSort =
  | 'pir_avg'
  | 'pir_total'
  | 'pir_per36'
  | 'pm_total'
  | 'pm_per36'
  | 'points'
  | 'clutch_pm'
  | 'clutch_points'
  | 'fouls_drawn_per100';

export type TeamSort =
  | 'possessions_avg'
  | 'fouls_drawn_per100'
  | 'max_run'
  | 'max_blown_lead'
  | 'clutch_pts_for';

/** Thrown for any non-2xx so islands can show the API's own message. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

type Params = Record<string, string | number | boolean | null | undefined>;

export function qs(params: Params): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') {
      search.set(key, String(value));
    }
  }
  const s = search.toString();
  return s ? `?${s}` : '';
}

async function get<T>(path: string, params: Params = {}): Promise<T> {
  const res = await fetch(`${API}${path}${qs(params)}`);
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export const api = {
  seasons: () => get<Season[]>('/seasons'),
  clubs: (season?: string) => get<Club[]>('/clubs', { season }),
  standings: (season?: string) => get<StandingsRow[]>('/standings', { season }),
  games: (p: { season?: string; round?: number; club?: string; limit?: number; offset?: number }) =>
    get<GameSummary[]>('/games', p),
  game: (code: number, season?: string) => get<GameDetail>(`/games/${code}`, { season }),
  timeline: (code: number, season?: string) =>
    get<GameTimeline>(`/games/${code}/timeline`, { season }),
  teams: (p: { season?: string; sort?: TeamSort; desc?: boolean } = {}) =>
    get<TeamSeason[]>('/teams', p),
  team: (club: string, season?: string) => get<TeamDetail>(`/teams/${club}`, { season }),
  players: (
    p: {
      season?: string;
      sort?: PlayerSort;
      desc?: boolean;
      club?: string;
      min_games?: number;
      limit?: number;
      offset?: number;
    } = {},
  ) => get<PlayerSeason[]>('/players', p),
  player: (code: string, season?: string) => get<PlayerDetail>(`/players/${code}`, { season }),
  runs: (p: { season?: string; limit?: number } = {}) => get<RunRow[]>('/indexes/runs', p),
  blownLeads: (p: { season?: string; limit?: number } = {}) =>
    get<BlownLeadRow[]>('/indexes/blown-leads', p),
  clutch: (p: { season?: string; limit?: number } = {}) => get<ClutchIndex>('/indexes/clutch', p),
  foulsDrawn: (p: { season?: string; limit?: number; min_games?: number } = {}) =>
    get<FoulsDrawnIndex>('/indexes/fouls-drawn', p),
};

/* --- formatting helpers (pure — unit tested) ----------------------------- */

/** 1234.5 → "20:35". The boxscore stores court time in seconds. */
export function mmss(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—';
  const total = Math.round(seconds);
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

/** Fixed-decimal number, em dash for nulls so columns never look broken. */
export function num(value: number | null | undefined, decimals = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return value.toFixed(decimals);
}

/** Integers with an explicit sign — +/- columns read wrong without it. */
export function signed(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—';
  return value > 0 ? `+${value}` : String(value);
}

export function signClass(value: number | null | undefined): string {
  if (value === null || value === undefined || value === 0) return 'num';
  return value > 0 ? 'num pos' : 'num neg';
}

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
];

/**
 * "2025-09-30T18:00:00Z" → "30 Sep 2025".
 *
 * Formatted by hand rather than with toLocaleDateString: ICU renders some
 * months with four letters ("Sept") and differs between Node and browsers, so
 * a locale-formatted column would be ragged and untestable. Kept in UTC — the
 * API's dates are UTC and a local-time conversion would move tip-offs across
 * the date line for some readers.
 */
export function shortDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return `${String(d.getUTCDate()).padStart(2, '0')} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** Elapsed seconds → "Q3 04:12" / "OT1 02:00" for chart axes and events. */
export function gameClock(t: number): string {
  if (t <= 2400) {
    const q = Math.min(4, Math.floor(t / 600) + 1);
    return `Q${q} ${mmss(t - (q - 1) * 600)}`;
  }
  const ot = Math.floor((t - 2400) / 300) + 1;
  return `OT${ot} ${mmss(t - 2400 - (ot - 1) * 300)}`;
}

/** Seasons before 2007-08 have no play-by-play: hide the derived columns. */
export function isBoxscoreOnly(season: Season | undefined): boolean {
  return !!season && season.games_with_pbp === 0;
}

/** Read a query-string param — how detail views get their entity on a static site. */
export function param(name: string, search = typeof location === 'undefined' ? '' : location.search) {
  return new URLSearchParams(search).get(name);
}

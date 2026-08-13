/**
 * Page-header decoration for Teams and Players.
 *
 * These two pages replace the generic basketball with the thing the page is
 * actually about — the league's crests, or the faces at the top of the
 * leaderboard. Both degrade to nothing while loading or if the API is down:
 * the header is decoration, and an empty gap reads better than a spinner or a
 * row of broken images.
 */

import { useEffect } from 'react';
import { api } from '../lib/api';
import { useApi, useClubs, useParam, useSeasons } from './hooks';
import { PlayerPhoto } from './ui';

/** Every club's crest, or just one club's on a team detail view. */
export function TeamCrests() {
  const { season } = useSeasons();
  const club = useParam('club');
  const state = useApi(() => (season ? api.clubs(season) : Promise.resolve([])), [season]);
  const clubs = (state.data ?? []).filter((c) => c.crest_url);
  if (!clubs.length) return null;

  const one = club ? clubs.find((c) => c.club_code === club) : undefined;
  if (one) {
    return (
      <div className="head-art head-art-single">
        <img src={one.crest_url!} alt="" width={104} height={104} />
      </div>
    );
  }

  return (
    <div className="head-art head-art-grid">
      {clubs.map((c) => (
        <img key={c.club_code} src={c.crest_url!} alt="" title={c.club_name ?? c.club_code} loading="lazy" />
      ))}
    </div>
  );
}

/**
 * The two clubs of the game being viewed, in place of the basketball.
 *
 * Only renders on a game detail view (?code=N); the schedule keeps the ball.
 * Re-requesting the game here is free — the Games island has already fetched
 * it, and the API's max-age makes the second call a browser cache hit.
 */
export function GameTeams() {
  const code = useParam('code');
  const { season } = useSeasons();
  const clubs = useClubs(season);
  const state = useApi(
    () => (code ? api.game(Number(code), season) : Promise.resolve(null)),
    [code, season],
  );

  // Hides the basketball while a game is open. The inline script in
  // games/index.astro covers the first paint; this keeps it in step as the
  // reader moves between the schedule and a game.
  useEffect(() => {
    const root = document.documentElement;
    if (code) root.dataset.gameView = 'detail';
    else delete root.dataset.gameView;
  }, [code]);

  const g = state.data;
  if (!code || !g) return null;
  const home = clubs.get(g.home_club_code ?? '')?.crest_url;
  const away = clubs.get(g.away_club_code ?? '')?.crest_url;
  if (!home && !away) return null;

  return (
    <div className="head-art game-teams">
      {home && <img src={home} alt={g.home_club_name ?? ''} />}
      <span className="vs">VS</span>
      {away && <img src={away} alt={g.away_club_name ?? ''} />}
    </div>
  );
}

/** The faces at the top of the PIR leaderboard. */
export function PlayerFaces() {
  const { season } = useSeasons();
  const state = useApi(
    () => (season ? api.players({ season, min_games: 10, limit: 6 }) : Promise.resolve([])),
    [season],
  );
  const players = state.data ?? [];
  if (!players.length) return null;

  return (
    <div className="head-art head-faces">
      {players.map((p) => (
        <PlayerPhoto key={p.player_code} src={p.headshot_url} name={p.player_name} size={54} />
      ))}
    </div>
  );
}

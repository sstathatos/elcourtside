import { useEffect } from 'react';
import { api } from '../lib/api';
import { useApi, useClubs, useParam, useSeasons } from './hooks';
import { PlayerPhoto } from './ui';

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

export function GameTeams() {
  const code = useParam('code');
  const { season } = useSeasons();
  const clubs = useClubs(season);
  const state = useApi(
    () => (code ? api.game(Number(code), season) : Promise.resolve(null)),
    [code, season],
  );

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

/**
 * Landing-page strip: what the database actually holds right now.
 *
 * The homepage is otherwise static prose; this is the one live piece, so the
 * claim "computed nightly" is visible rather than asserted. Renders nothing
 * until it has data — a landing page should never show a spinner or an error
 * box above the fold.
 */

import { api } from '../lib/api';
import { useApi } from './hooks';

export default function SeasonSummary() {
  const state = useApi(() => api.seasons(), []);
  const seasons = state.data ?? [];
  if (!seasons.length) return null;

  const current = seasons[0]!;
  const games = seasons.reduce((n, s) => n + (s.games ?? 0), 0);
  const withPbp = seasons.reduce((n, s) => n + (s.games_with_pbp ?? 0), 0);

  return (
    <div className="stat-row season-summary">
      <div className="stat">
        <span className="k">Current season</span>
        <span className="v">{current.season_name ?? current.season_code}</span>
      </div>
      <div className="stat">
        <span className="k">Games ingested</span>
        <span className="v">{games}</span>
      </div>
      <div className="stat">
        <span className="k">With play-by-play</span>
        <span className="v">{withPbp}</span>
      </div>
    </div>
  );
}

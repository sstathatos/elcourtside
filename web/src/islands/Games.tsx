/**
 * Games: the schedule, and one game's detail behind ?code=N.
 *
 * Detail lives on the same static page rather than a prerendered /games/42,
 * so the build never has to know which games exist — the nightly ingest can
 * add games without a rebuild.
 */

import { api, mmss, num, shortDate, signClass, signed, type BoxscoreLine } from '../lib/api';
import { setParam, useApi, useParam, useSeasons } from './hooks';
import {
  BackLink,
  BoxscoreOnlyNote,
  ClubsProvider,
  Crest,
  Panel,
  SeasonPicker,
  Stat,
  Th,
} from './ui';
import ScoreWorm from './ScoreWorm';

export default function Games() {
  const code = useParam('code');
  return code ? <GameDetail code={Number(code)} /> : <GameList />;
}

function GameList() {
  const { seasons, season, current, setSeason } = useSeasons();
  const state = useApi(
    () => (season ? api.games({ season, limit: 500 }) : Promise.resolve([])),
    [season],
  );

  return (
    <ClubsProvider season={season}>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        <span className="muted">Click a game for its boxscore and score worm.</span>
      </div>
      <BoxscoreOnlyNote current={current} />

      <Panel state={state} what="games">
        {(games) => (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <Th metric="date" label="Date" left />
                  <Th metric="round" label="Round" left />
                  <Th label="Game" left />
                  <Th metric="score" label="Score" />
                  <Th label="" />
                </tr>
              </thead>
              <tbody>
                {[...games].reverse().map((g) => {
                  const homeWon = (g.home_score ?? 0) > (g.away_score ?? 0);
                  return (
                    <tr key={g.game_code}>
                      <td style={{ textAlign: 'left' }}>{shortDate(g.utc_date)}</td>
                      <td style={{ textAlign: 'left' }} className="muted">
                        {g.round}
                      </td>
                      <td style={{ textAlign: 'left' }}>
                        <span className="club">
                          <Crest code={g.home_club_code} />
                          <strong style={homeWon ? undefined : { fontWeight: 400 }}>
                            {g.home_club_name}
                          </strong>
                          <span className="muted">vs</span>
                          <Crest code={g.away_club_code} />
                          <span style={homeWon ? undefined : { fontWeight: 700 }}>
                            {g.away_club_name}
                          </span>
                        </span>
                      </td>
                      <td className="num">
                        <strong>{g.home_score}</strong>–<strong>{g.away_score}</strong>
                      </td>
                      <td>
                        <a href={`/games/?code=${g.game_code}`}>open</a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </ClubsProvider>
  );
}

function GameDetail({ code }: { code: number }) {
  const game = useApi(() => api.game(code), [code]);
  const timeline = useApi(() => api.timeline(code), [code]);
  const { season } = useSeasons();

  return (
    <ClubsProvider season={season}>
      <BackLink onClick={() => setParam('code', null)}>all games</BackLink>

      <Panel state={game} what="game">
        {(g) => {
          const home = g.team_metrics.find((t) => t.is_home === 1);
          const away = g.team_metrics.find((t) => t.is_home === 0);
          return (
            <>
              <h2 className="section-title club">
                <Crest code={g.home_club_code} size={24} />
                {g.home_club_name} {g.home_score}–{g.away_score} {g.away_club_name}
                <Crest code={g.away_club_code} size={24} />
              </h2>
              <p className="muted" style={{ marginBottom: '1.4rem' }}>
                Round {g.round} · {shortDate(g.utc_date)} · game {g.game_code}
              </p>

              <div className="stat-row">
                <Stat k="Possessions" v={`${num(home?.possessions, 0)} / ${num(away?.possessions, 0)}`} />
                <Stat k="Biggest run" v={`${home?.max_run ?? '—'} / ${away?.max_run ?? '—'}`} />
                <Stat k="Biggest lead" v={`${home?.max_lead ?? '—'} / ${away?.max_lead ?? '—'}`} />
                <Stat
                  k="Clutch points"
                  v={`${home?.clutch_pts_for ?? '—'} / ${away?.clutch_pts_for ?? '—'}`}
                />
              </div>

              {timeline.data?.has_pbp ? (
                <ScoreWorm tl={timeline.data} />
              ) : timeline.loading ? (
                <p className="loading">loading the score worm</p>
              ) : (
                <p className="note">No play-by-play for this game — boxscore only.</p>
              )}

              <Side g={g} isHome={1} name={g.home_club_name} code={g.home_club_code} />
              <Side g={g} isHome={0} name={g.away_club_name} code={g.away_club_code} />
            </>
          );
        }}
      </Panel>
    </ClubsProvider>
  );
}

function Side({
  g,
  isHome,
  name,
  code,
}: {
  g: { boxscore: BoxscoreLine[]; player_metrics: Array<{ player_code: string; pir: number | null; pm_computed: number | null }> };
  isHome: 0 | 1;
  name: string | null;
  code: string | null;
}) {
  const metrics = new Map(g.player_metrics.map((m) => [m.player_code, m]));
  const lines = g.boxscore.filter((b) => b.is_home === isHome && b.entry_type === 'player');
  const total = g.boxscore.find((b) => b.is_home === isHome && b.entry_type === 'total');

  return (
    <>
      <h3 className="section-title club">
        <Crest code={code} size={22} />
        {name}
      </h3>
      <div className="table-frame">
        <table>
          <thead>
            <tr>
              <Th metric="player" label="Player" left />
              <Th metric="min" label="Min" />
              <Th metric="pts" label="Pts" />
              <Th metric="fg2" label="2FG" />
              <Th metric="fg3" label="3FG" />
              <Th metric="ft" label="FT" />
              <Th metric="reb" label="Reb" />
              <Th metric="ast" label="Ast" />
              <Th metric="stl" label="Stl" alignEnd />
              <Th metric="to" label="TO" alignEnd />
              <Th metric="pir" label="PIR" alignEnd />
              <Th metric="pm" label="+/-" alignEnd />
            </tr>
          </thead>
          <tbody>
            {lines.map((b) => {
              const m = metrics.get(b.player_code);
              return (
                <tr key={b.player_code}>
                  <td>
                    <a href={`/players/?code=${b.player_code}`}>{b.player_name}</a>
                    {b.start_five ? <span className="muted"> ·</span> : null}
                  </td>
                  <td className="num">{mmss(b.seconds_played)}</td>
                  <td className="num">
                    <strong>{b.points}</strong>
                  </td>
                  <td className="num">{b.fg2m}/{b.fg2a}</td>
                  <td className="num">{b.fg3m}/{b.fg3a}</td>
                  <td className="num">{b.ftm}/{b.fta}</td>
                  <td className="num">{b.reb_total}</td>
                  <td className="num">{b.assists}</td>
                  <td className="num">{b.steals}</td>
                  <td className="num">{b.turnovers}</td>
                  <td className="num">
                    <strong>{m?.pir ?? '—'}</strong>
                  </td>
                  <td className={signClass(m?.pm_computed)}>{signed(m?.pm_computed)}</td>
                </tr>
              );
            })}
            {total && (
              <tr>
                <td>
                  <strong>Team</strong>
                </td>
                <td className="num">—</td>
                <td className="num">
                  <strong>{total.points}</strong>
                </td>
                <td className="num">{total.fg2m}/{total.fg2a}</td>
                <td className="num">{total.fg3m}/{total.fg3a}</td>
                <td className="num">{total.ftm}/{total.fta}</td>
                <td className="num">{total.reb_total}</td>
                <td className="num">{total.assists}</td>
                <td className="num">{total.steals}</td>
                <td className="num">{total.turnovers}</td>
                <td className="num">—</td>
                <td className="num">—</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="muted" style={{ margin: '0.5rem 0 1.6rem' }}>
        · marks a starter. PIR is ours, computed from this boxscore; +/- is
        reconstructed from substitution events.
      </p>
    </>
  );
}

/**
 * Players: the leaderboard, and one player behind ?code=NNNNNN.
 *
 * Sorting happens server-side here (unlike Teams): the leaderboard is paged,
 * so sorting only the current page would be a lie. The sort keys are exactly
 * the enum the API accepts.
 */

import { useEffect, useState } from 'react';
import { api, mmss, num, shortDate, signClass, signed, type PlayerSort } from '../lib/api';
import { setParam, useApi, useParam, useSeasons } from './hooks';
import {
  BackLink,
  BoxscoreOnlyNote,
  ClubLabel,
  ClubList,
  ClubsProvider,
  Panel,
  PlayerPhoto,
  SeasonPicker,
  Stat,
  Th,
} from './ui';

export default function Players() {
  const code = useParam('code');

  // Keeps the page's own header hidden while a player is open. The inline
  // script in players/index.astro sets this for the first paint; this keeps it
  // right as the reader moves between the leaderboard and a player.
  useEffect(() => {
    const root = document.documentElement;
    if (code) root.dataset.playerView = 'detail';
    else delete root.dataset.playerView;
  }, [code]);

  return code ? <PlayerDetail code={code} /> : <PlayerTable />;
}

const SORTS: Array<{ key: PlayerSort; label: string }> = [
  { key: 'pir_avg', label: 'PIR / game' },
  { key: 'pir_total', label: 'PIR total' },
  { key: 'pir_per36', label: 'PIR / 36' },
  { key: 'pm_total', label: '+/- total' },
  { key: 'pm_per36', label: '+/- per 36' },
  { key: 'points', label: 'Points' },
  { key: 'clutch_pm', label: 'Clutch +/-' },
  { key: 'fouls_drawn_per100', label: 'Fouls drawn /100' },
];

function PlayerTable() {
  const { seasons, season, current, setSeason } = useSeasons();
  const [sort, setSort] = useState<PlayerSort>('pir_avg');
  const [minGames, setMinGames] = useState(10);
  const state = useApi(
    () =>
      season
        ? api.players({ season, sort, min_games: minGames, limit: 100 })
        : Promise.resolve([]),
    [season, sort, minGames],
  );

  return (
    <ClubsProvider season={season}>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        <label className="muted">
          Sort by{' '}
          <select value={sort} onChange={(e) => setSort(e.target.value as PlayerSort)}>
            {SORTS.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="muted">
          Min games{' '}
          <input
            type="number"
            min={0}
            max={60}
            value={minGames}
            style={{ width: '4.5rem' }}
            onChange={(e) => setMinGames(Number(e.target.value))}
          />
        </label>
      </div>
      <BoxscoreOnlyNote current={current} />

      <Panel state={state} what="players">
        {(rows) => (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <Th metric="player" label="Player" left />
                  <Th metric="club" label="Club" left />
                  <Th metric="gp" label="GP" />
                  <Th metric="min" label="Min" />
                  <Th metric="pts" label="Pts" />
                  <Th metric="reb" label="Reb" />
                  <Th metric="ast" label="Ast" />
                  <Th metric="pir_avg" label="PIR/g" />
                  <Th metric="pir_per36" label="PIR/36" />
                  <Th metric="pm_total" label="+/-" alignEnd />
                  <Th metric="clutch_pm" label="Clutch +/-" alignEnd />
                  <Th metric="fd100" label="FD/100" alignEnd />
                </tr>
              </thead>
              <tbody>
                {rows.map((p, i) => (
                  <tr key={p.player_code}>
                    <td>
                      <span className="rank">{i + 1}.</span>{' '}
                      <a href={`/players/?code=${p.player_code}`}>{p.player_name}</a>
                    </td>
                    <td style={{ textAlign: 'left' }} className="muted">
                      <ClubList clubs={p.clubs} />
                    </td>
                    <td className="num">{p.games_played}</td>
                    <td className="num">{mmss((p.seconds ?? 0) / (p.games_played || 1))}</td>
                    <td className="num">{p.points}</td>
                    <td className="num">{p.reb_total}</td>
                    <td className="num">{p.assists}</td>
                    <td className="num">
                      <strong>{num(p.pir_avg, 1)}</strong>
                    </td>
                    <td className="num">{num(p.pir_per36, 1)}</td>
                    <td className={signClass(p.pm_total)}>{signed(p.pm_total)}</td>
                    <td className={signClass(p.clutch_pm)}>{signed(p.clutch_pm)}</td>
                    <td className="num">{num(p.fouls_drawn_per100, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </ClubsProvider>
  );
}

function PlayerDetail({ code }: { code: string }) {
  const state = useApi(() => api.player(code), [code]);
  const { season } = useSeasons();

  return (
    <ClubsProvider season={season}>
      <BackLink onClick={() => setParam('code', null)}>leaderboard</BackLink>
      <Panel state={state} what="player">
        {(p) => (
          <>
            {/* This player's own header, in place of the leaderboard's:
                name and figures at full size, portraits off to the side. */}
            <div className="player-head">
              <div className="player-head-main">
                <h1 className="player-name">{p.player_name ?? p.player_code}</h1>
                <p className="muted player-meta">
                  <ClubList clubs={p.clubs} /> · {p.games_played} games ·{' '}
                  {mmss(p.seconds)} on court
                </p>
              </div>
              <div className="player-shots">
                <figure>
                  <PlayerPhoto src={p.headshot_url} name={p.player_name} size={132} />
                  <figcaption>Headshot</figcaption>
                </figure>
                <figure>
                  <PlayerPhoto src={p.action_url} name={p.player_name} size={132} />
                  <figcaption>Action</figcaption>
                </figure>
              </div>
            </div>

            <div className="stat-row stat-row-lg">
              <Stat k="PIR / game" v={num(p.pir_avg, 1)} />
              <Stat k="PIR / 36" v={num(p.pir_per36, 1)} />
              <Stat k="+/- total" v={signed(p.pm_total)} />
              <Stat k="+/- per 36" v={num(p.pm_per36, 1)} />
              <Stat k="Clutch +/-" v={signed(p.clutch_pm)} />
              <Stat k="Fouls drawn /100" v={num(p.fouls_drawn_per100, 1)} />
            </div>

            <h3 className="section-title">Game log</h3>
            <div className="table-frame">
              <table>
                <thead>
                  <tr>
                    <Th metric="date" label="Date" left />
                    <Th metric="opponent" label="Opponent" left />
                    <Th metric="min" label="Min" />
                    <Th metric="pts" label="Pts" />
                    <Th metric="reb" label="Reb" />
                    <Th metric="ast" label="Ast" />
                    <Th metric="pir" label="PIR" alignEnd />
                    <Th metric="pm" label="+/-" alignEnd />
                    <Th label="" />
                  </tr>
                </thead>
                <tbody>
                  {p.games.map((g) => (
                    <tr key={g.game_code}>
                      <td style={{ textAlign: 'left' }}>{shortDate(g.utc_date)}</td>
                      <td style={{ textAlign: 'left' }}>
                        <span className="club">
                          <span className="muted">{g.is_home ? 'vs' : '@'}</span>
                          <ClubLabel code={g.opponent_code} />
                        </span>
                      </td>
                      <td className="num">{mmss(g.seconds_played)}</td>
                      <td className="num">{g.points}</td>
                      <td className="num">{g.reb_total}</td>
                      <td className="num">{g.assists}</td>
                      <td className="num">
                        <strong>{g.pir}</strong>
                      </td>
                      <td className={signClass(g.pm_computed)}>{signed(g.pm_computed)}</td>
                      <td>
                        <a href={`/games/?code=${g.game_code}`}>open</a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Panel>
    </ClubsProvider>
  );
}

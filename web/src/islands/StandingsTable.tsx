import { api, shortDate, signClass, signed, type Phase } from '../lib/api';
import { useApi, useSeasons } from './hooks';
import { ClubLabel, ClubsProvider, Crest, Panel, SeasonPicker, Th } from './ui';
import { useState } from 'react';

const STAGES: Array<{ key: 'RS' | 'FF'; label: string }> = [
  { key: 'RS', label: 'Regular season' },
  { key: 'FF', label: 'Final Four' },
];

export default function StandingsTable() {
  const { seasons, season, current, setSeason } = useSeasons();
  const [stage, setStage] = useState<'RS' | 'FF'>('RS');

  return (
    <ClubsProvider season={season}>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        {STAGES.map((s) => (
          <button
            key={s.key}
            type="button"
            className="btn"
            aria-pressed={s.key === stage}
            onClick={() => setStage(s.key)}
          >
            {s.label}
          </button>
        ))}
      </div>

      {stage === 'RS' ? <RegularSeason season={season} /> : (
        <FinalFour season={season} champion={current?.winner_club_code ?? null} />
      )}
    </ClubsProvider>
  );
}

function RegularSeason({ season }: { season: string | undefined }) {
  const state = useApi(() => (season ? api.standings(season) : Promise.resolve([])), [season]);

  return (
    <>
      <p className="note">
        Ranked by wins, then the Euroleague tiebreak chain: head-to-head record,
        head-to-head difference, overall difference, points scored.
      </p>
      <Panel state={state} what="standings">
        {(rows) => (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <Th metric="club" label="Club" left />
                  <Th metric="gp" label="GP" />
                  <Th metric="w" label="W" />
                  <Th metric="l" label="L" />
                  <Th metric="pf" label="PF" />
                  <Th metric="pa" label="PA" />
                  <Th metric="diff" label="Diff" />
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.club_code}>
                    <td>
                      <span className="club">
                        <span className="rank">{r.rank}.</span>
                        <ClubLabel code={r.club_code} name={r.club_name} />
                      </span>
                    </td>
                    <td className="num">{r.games}</td>
                    <td className="num">{r.wins}</td>
                    <td className="num">{r.losses}</td>
                    <td className="num">{r.points_for}</td>
                    <td className="num">{r.points_against}</td>
                    <td className={signClass(r.point_diff)}>{signed(r.point_diff)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

function FinalFour({ season, champion }: { season: string | undefined; champion: string | null }) {
  const table = useApi(
    () => (season ? api.standings(season, 'FF') : Promise.resolve([])),
    [season],
  );
  const state = useApi(
    () => (season ? api.games({ season, phase: 'FF' as Phase, limit: 10 }) : Promise.resolve([])),
    [season],
  );

  return (
    <>
      <p className="note">
        Placings are derived from the results — the source publishes no Final Four
        table. Where no third-place game is recorded, the beaten semi-finalists
        share third: from 2025-26 none is played, and 2001-02 is missing it.
      </p>
      {champion && (
        <p className="champion-line">
          <span className="champion">champion</span>{' '}
          <ClubLabel code={champion} />
        </p>
      )}

      <Panel state={table} what="Final Four placings">
        {(rows) =>
          rows.length === 0 ? (
            <></>
          ) : (
            <div className="table-frame" style={{ marginBottom: '1.6rem' }}>
              <table>
                <thead>
                  <tr>
                    <Th metric="club" label="Club" left />
                    <Th metric="gp" label="GP" />
                    <Th metric="w" label="W" />
                    <Th metric="l" label="L" />
                    <Th metric="pf" label="PF" />
                    <Th metric="pa" label="PA" />
                    <Th metric="diff" label="Diff" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.club_code}>
                      <td>
                        <span className="club">
                          <span className="rank">{r.rank ? `${r.rank}.` : '—'}</span>
                          <ClubLabel code={r.club_code} name={r.club_name} />
                        </span>
                      </td>
                      <td className="num">{r.games}</td>
                      <td className="num">{r.wins}</td>
                      <td className="num">{r.losses}</td>
                      <td className="num">{r.points_for}</td>
                      <td className="num">{r.points_against}</td>
                      <td className={signClass(r.point_diff)}>{signed(r.point_diff)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </Panel>

      <h3 className="section-title">Games</h3>
      <Panel state={state} what="Final Four games">
        {(games) =>
          games.length === 0 ? (
            <p className="muted">
              No Final Four games for this season yet — it is played in May.
            </p>
          ) : (
            <div className="table-frame">
              <table>
                <thead>
                  <tr>
                    <Th metric="date" label="Date" left />
                    <Th label="Game" left />
                    <Th metric="score" label="Score" />
                    <Th label="" />
                  </tr>
                </thead>
                <tbody>
                  {games.map((g) => {
                    const homeWon = (g.home_score ?? 0) > (g.away_score ?? 0);
                    return (
                      <tr key={g.game_code}>
                        <td style={{ textAlign: 'left' }}>{shortDate(g.utc_date)}</td>
                        <td style={{ textAlign: 'left' }}>
                          <span className="club">
                            <Crest code={g.home_club_code} />
                            <span style={{ fontWeight: homeWon ? 700 : 400 }}>
                              {g.home_club_name}
                            </span>
                            <span className="muted">vs</span>
                            <Crest code={g.away_club_code} />
                            <span style={{ fontWeight: homeWon ? 400 : 700 }}>
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
          )
        }
      </Panel>
    </>
  );
}

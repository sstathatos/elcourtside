/** Standings — rank order as the engine computed it (Euroleague tiebreaks). */

import { api, signClass, signed } from '../lib/api';
import { useApi, useSeasons } from './hooks';
import { ClubLabel, ClubsProvider, Panel, SeasonPicker, Th } from './ui';

export default function StandingsTable() {
  const { seasons, season, current, setSeason } = useSeasons();
  const state = useApi(() => (season ? api.standings(season) : Promise.resolve([])), [season]);

  return (
    <ClubsProvider season={season}>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        <span className="muted">
          Regular season only, ranked by wins then the Euroleague tiebreak chain.
        </span>
      </div>

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
                        {/* Topping this table is not winning the league: it
                            ranks the regular season, and the Final Four
                            decides the title. Fenerbahce won 2024-25 from
                            second place, which is exactly the confusion this
                            badge removes. */}
                        {current?.winner_club_code === r.club_code && (
                          <span className="champion" title="Won the Final Four">
                            champion
                          </span>
                        )}
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
    </ClubsProvider>
  );
}

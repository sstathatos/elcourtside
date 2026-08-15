import { useState } from 'react';
import { api, gameClock, mmss, num, signClass, signed } from '../lib/api';
import { useApi, useSeasons } from './hooks';
import { BoxscoreOnlyNote, ClubLabel, ClubList, ClubsProvider, Panel, SeasonPicker, Th } from './ui';

type Tab = 'runs' | 'leads' | 'clutch' | 'fouls';

const TABS: Array<{ key: Tab; label: string; blurb: string }> = [
  {
    key: 'runs',
    label: 'Scoring runs',
    blurb: 'Longest unanswered point streaks, from the running score in the play-by-play.',
  },
  {
    key: 'leads',
    label: 'Blown leads',
    blurb: 'The biggest lead a club held in a game it went on to lose.',
  },
  {
    key: 'clutch',
    label: 'Clutch',
    blurb: 'Last 5:00 of the 4th or any OT, with the margin within 5 points before the play.',
  },
  {
    key: 'fouls',
    label: 'Fouls drawn',
    blurb: 'Fouls received per 100 possessions (FGA + 0.44·FTA − ORB + TO).',
  },
];

export default function Indexes() {
  const { seasons, season, current, setSeason } = useSeasons();
  const [tab, setTab] = useState<Tab>('runs');
  const active = TABS.find((t) => t.key === tab)!;

  return (
    <ClubsProvider season={season}>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className="btn"
            aria-pressed={t.key === tab}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      <p className="note">{active.blurb}</p>
      <BoxscoreOnlyNote current={current} />

      {tab === 'runs' && <Runs season={season} />}
      {tab === 'leads' && <Leads season={season} />}
      {tab === 'clutch' && <Clutch season={season} />}
      {tab === 'fouls' && <Fouls season={season} />}
    </ClubsProvider>
  );
}

function Runs({ season }: { season: string | undefined }) {
  const state = useApi(
    () => (season ? api.runs({ season, limit: 40 }) : Promise.resolve([])),
    [season],
  );
  return (
    <Panel state={state} what="runs">
      {(rows) => (
        <div className="table-frame">
          <table>
            <thead>
              <tr>
                <Th label="#" />
                <Th metric="club" label="Club" left />
                <Th metric="opponent" label="Opponent" left />
                <Th metric="max_run" label="Run" />
                <Th metric="run_when" label="When" left />
                <Th label="" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const detail = r.max_run_detail
                  ? (JSON.parse(r.max_run_detail) as { start_s: number; end_s: number })
                  : null;
                return (
                  <tr key={`${r.game_code}-${r.club_code}`}>
                    <td className="rank">{i + 1}</td>
                    <td style={{ textAlign: 'left' }}>
                      <ClubLabel code={r.club_code} />
                    </td>
                    <td style={{ textAlign: 'left' }} className="muted">
                      <ClubLabel code={r.opponent_code} link={false} />
                    </td>
                    <td className="num">
                      <strong>{r.max_run}–0</strong>
                    </td>
                    <td style={{ textAlign: 'left' }} className="muted">
                      {detail ? `${gameClock(detail.start_s)} → ${gameClock(detail.end_s)}` : '—'}
                    </td>
                    <td>
                      <a href={`/games/?code=${r.game_code}`}>game</a>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Leads({ season }: { season: string | undefined }) {
  const state = useApi(
    () => (season ? api.blownLeads({ season, limit: 40 }) : Promise.resolve([])),
    [season],
  );
  return (
    <Panel state={state} what="blown leads">
      {(rows) => (
        <div className="table-frame">
          <table>
            <thead>
              <tr>
                <Th label="#" />
                <Th metric="blown_lead" label="Led" left />
                <Th metric="opponent" label="Lost to" left />
                <Th metric="max_lead" label="Lead" />
                <Th metric="score" label="Final" />
                <Th label="" />
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={`${r.game_code}-${r.club_code}`}>
                  <td className="rank">{i + 1}</td>
                  <td style={{ textAlign: 'left' }}>
                    <ClubLabel code={r.club_code} />
                  </td>
                  <td style={{ textAlign: 'left' }} className="muted">
                    <ClubLabel code={r.opponent_code} link={false} />
                  </td>
                  <td className="num">
                    <strong>+{r.max_lead}</strong>
                  </td>
                  <td className="num neg">
                    {r.points}–{r.opponent_points}
                  </td>
                  <td>
                    <a href={`/games/?code=${r.game_code}`}>game</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

function Clutch({ season }: { season: string | undefined }) {
  const state = useApi(
    () => (season ? api.clutch({ season, limit: 30 }) : Promise.resolve(null)),
    [season],
  );
  return (
    <Panel state={state} what="clutch numbers">
      {(d) =>
        d && (
          <div className="two-col">
            <div>
              <h3 className="section-title">Players</h3>
              <div className="table-frame">
                <table>
                  <thead>
                    <tr>
                      <Th metric="player" label="Player" left />
                      <Th metric="clutch_time" label="Time" />
                      <Th metric="clutch_pts" label="Pts" />
                      <Th metric="clutch_pm" label="+/-" />
                    </tr>
                  </thead>
                  <tbody>
                    {d.players.map((p) => (
                      <tr key={p.player_code}>
                        <td>
                          <a href={`/players/?code=${p.player_code}`}>{p.player_name}</a>{' '}
                          <ClubList clubs={p.clubs} />
                        </td>
                        <td className="num">{mmss(p.clutch_seconds)}</td>
                        <td className="num">{p.clutch_points}</td>
                        <td className={signClass(p.clutch_pm)}>{signed(p.clutch_pm)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <h3 className="section-title">Teams</h3>
              <div className="table-frame">
                <table>
                  <thead>
                    <tr>
                      <Th metric="club" label="Club" left />
                      <Th metric="clutch_for" label="For" />
                      <Th metric="clutch_against" label="Against" />
                      <Th metric="clutch_pm" label="+/-" />
                    </tr>
                  </thead>
                  <tbody>
                    {d.teams.map((t) => (
                      <tr key={t.club_code}>
                        <td>
                          <ClubLabel code={t.club_code} name={t.club_name} />
                        </td>
                        <td className="num">{t.clutch_pts_for}</td>
                        <td className="num">{t.clutch_pts_against}</td>
                        <td className={signClass(t.clutch_pm)}>{signed(t.clutch_pm)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )
      }
    </Panel>
  );
}

function Fouls({ season }: { season: string | undefined }) {
  const state = useApi(
    () => (season ? api.foulsDrawn({ season, limit: 30, min_games: 10 }) : Promise.resolve(null)),
    [season],
  );
  return (
    <Panel state={state} what="fouls drawn">
      {(d) =>
        d && (
          <div className="two-col">
            <div>
              <h3 className="section-title">Players (10+ games)</h3>
              <div className="table-frame">
                <table>
                  <thead>
                    <tr>
                      <Th metric="player" label="Player" left />
                      <Th metric="gp" label="GP" />
                      <Th metric="fouls_drawn" label="Drawn" />
                      <Th metric="fd100" label="/100" />
                    </tr>
                  </thead>
                  <tbody>
                    {d.players.map((p) => (
                      <tr key={p.player_code}>
                        <td>
                          <a href={`/players/?code=${p.player_code}`}>{p.player_name}</a>{' '}
                          <ClubList clubs={p.clubs} />
                        </td>
                        <td className="num">{p.games_played}</td>
                        <td className="num">{p.fouls_drawn}</td>
                        <td className="num">
                          <strong>{num(p.fouls_drawn_per100, 1)}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
            <div>
              <h3 className="section-title">Teams</h3>
              <div className="table-frame">
                <table>
                  <thead>
                    <tr>
                      <Th metric="club" label="Club" left />
                      <Th metric="poss_avg" label="Poss/g" />
                      <Th metric="fd100" label="FD/100" />
                    </tr>
                  </thead>
                  <tbody>
                    {d.teams.map((t) => (
                      <tr key={t.club_code}>
                        <td>
                          <ClubLabel code={t.club_code} name={t.club_name} />
                        </td>
                        <td className="num">{num(t.possessions_avg, 1)}</td>
                        <td className="num">
                          <strong>{num(t.fouls_drawn_per100, 1)}</strong>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )
      }
    </Panel>
  );
}

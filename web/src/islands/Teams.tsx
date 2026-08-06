/** Teams: season table sorted client-side, plus one club behind ?club=CODE. */

import { api, num, shortDate, signClass, signed, type TeamSeason } from '../lib/api';
import { setParam, useApi, useParam, useSeasons, useSort } from './hooks';
import { BackLink, BoxscoreOnlyNote, Panel, SeasonPicker, Stat, Th } from './ui';
import type { MetricKey } from '../lib/glossary';

export default function Teams() {
  const club = useParam('club');
  return club ? <TeamDetail club={club} /> : <TeamTable />;
}

const COLUMNS: Array<{
  key: keyof TeamSeason;
  label: string;
  metric: MetricKey;
  decimals?: number;
}> = [
  { key: 'wins', label: 'W', metric: 'w' },
  { key: 'losses', label: 'L', metric: 'l' },
  { key: 'point_diff', label: 'Diff', metric: 'diff' },
  { key: 'possessions_avg', label: 'Poss/g', metric: 'poss_avg', decimals: 1 },
  { key: 'fouls_drawn_per100', label: 'FD/100', metric: 'fd100', decimals: 1 },
  { key: 'max_run', label: 'Best run', metric: 'max_run' },
  { key: 'max_blown_lead', label: 'Blown lead', metric: 'blown_lead' },
  { key: 'clutch_pts_for', label: 'Clutch pts', metric: 'clutch_for' },
];

function TeamTable() {
  const { seasons, season, current, setSeason } = useSeasons();
  const state = useApi(() => (season ? api.teams({ season }) : Promise.resolve([])), [season]);
  const rows = state.data ?? [];
  const { sorted, toggle, ariaSort } = useSort<TeamSeason>(rows, 'wins');

  return (
    <>
      <div className="controls">
        <SeasonPicker seasons={seasons} season={season} onChange={setSeason} />
        <span className="muted">Click a column to sort.</span>
      </div>
      <BoxscoreOnlyNote current={current} />

      <Panel state={state} what="teams">
        {() => (
          <div className="table-frame">
            <table>
              <thead>
                <tr>
                  <Th metric="club" label="Club" left />
                  {COLUMNS.map((c, i) => (
                    <Th
                      key={String(c.key)}
                      metric={c.metric}
                      label={c.label}
                      sortable
                      sorted={ariaSort(c.key)}
                      onSort={() => toggle(c.key)}
                      alignEnd={i >= COLUMNS.length - 3}
                    />
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map((t) => (
                  <tr key={t.club_code}>
                    <td>
                      <a href={`/teams/?club=${t.club_code}`}>{t.club_name ?? t.club_code}</a>
                    </td>
                    {COLUMNS.map((c) => {
                      const v = t[c.key] as number | null;
                      if (c.key === 'point_diff') {
                        return (
                          <td key={String(c.key)} className={signClass(v)}>
                            {signed(v)}
                          </td>
                        );
                      }
                      return (
                        <td key={String(c.key)} className="num">
                          {c.decimals === undefined ? (v ?? '—') : num(v, c.decimals)}
                        </td>
                      );
                    })}
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

function TeamDetail({ club }: { club: string }) {
  const state = useApi(() => api.team(club), [club]);

  return (
    <>
      <BackLink onClick={() => setParam('club', null)}>all teams</BackLink>
      <Panel state={state} what="team">
        {(t) => (
          <>
            <h2 className="section-title">{t.club_name ?? t.club_code}</h2>
            <div className="stat-row">
              <Stat k="Record" v={`${t.wins ?? '—'}-${t.losses ?? '—'}`} />
              <Stat k="Point diff" v={signed(t.point_diff)} />
              <Stat k="Poss / game" v={num(t.possessions_avg, 1)} />
              <Stat k="Fouls drawn /100" v={num(t.fouls_drawn_per100, 1)} />
              <Stat k="Biggest run" v={t.max_run ?? '—'} />
              <Stat k="Biggest blown lead" v={t.max_blown_lead ?? '—'} />
            </div>

            <h3 className="section-title">Game log</h3>
            <div className="table-frame">
              <table>
                <thead>
                  <tr>
                    <Th metric="date" label="Date" left />
                    <Th metric="opponent" label="Opponent" left />
                    <Th metric="result" label="Result" />
                    <Th metric="poss" label="Poss" />
                    <Th metric="max_run" label="Run" />
                    <Th metric="max_lead" label="Max lead" />
                    <Th metric="clutch_pm" label="Clutch +/-" alignEnd />
                    <Th label="" />
                  </tr>
                </thead>
                <tbody>
                  {t.games.map((g) => (
                    <tr key={g.game_code}>
                      <td style={{ textAlign: 'left' }}>{shortDate(g.utc_date)}</td>
                      <td style={{ textAlign: 'left' }}>
                        <span className="muted">{g.is_home ? 'vs' : '@'}</span>{' '}
                        <a href={`/teams/?club=${g.opponent_code}`}>{g.opponent_code}</a>
                      </td>
                      <td className={g.lost ? 'num neg' : 'num pos'}>
                        {g.lost ? 'L' : 'W'} {g.points}–{g.opponent_points}
                      </td>
                      <td className="num">{num(g.possessions, 0)}</td>
                      <td className="num">{g.max_run ?? '—'}</td>
                      <td className="num">{g.max_lead ?? '—'}</td>
                      <td className={signClass(g.clutch_pm)}>{signed(g.clutch_pm)}</td>
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
    </>
  );
}

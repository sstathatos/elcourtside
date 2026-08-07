/**
 * What every column abbreviation means, in one place.
 *
 * Half the point of this site is metrics people haven't seen before, so a
 * header like "FD/100" has to explain itself. Tables render these as the
 * `title` of the <th>, which gives a hover tooltip everywhere and is read out
 * by screen readers without extra markup.
 */

export const GLOSSARY = {
  // identity
  club: 'Club, as ranked by the standings',
  player: 'Player name — open for the full season and game log',
  dorsal: 'Shirt number as registered for the season',
  pos: 'Registered position: guard, forward or centre',
  height: 'Height in centimetres, as listed in the club registration',
  country: 'Country on the player registration, which is not always their birthplace',
  opponent: 'Opposing club in this game',
  date: 'Tip-off date (UTC)',
  round: 'Regular-season round number',
  game: 'Open this game — boxscore and score worm',

  // basic counting stats
  gp: 'Games played — games with any court time',
  min: 'Minutes on court, from the official boxscore',
  pts: 'Points scored in the game or season',
  reb: 'Total rebounds — offensive plus defensive',
  ast: 'Assists — a pass leading directly to a made basket',
  stl: 'Steals — possessions taken directly off the opponent',
  to: 'Turnovers — possessions lost without a shot attempt',
  fg2: 'Two-point field goals: made / attempted',
  fg3: 'Three-point field goals: made / attempted',
  ft: 'Free throws: made / attempted',

  // standings
  w: 'Wins in the regular season',
  l: 'Losses in the regular season',
  pf: 'Points scored across the season',
  pa: 'Points conceded across the season',
  diff: 'Point differential — points scored minus conceded',
  result: 'Win or loss, with the final score',

  // PIR
  pir: 'Performance Index Rating — the official Euroleague formula: (points + rebounds + assists + steals + blocks + fouls drawn) − (missed FG + missed FT + turnovers + shots blocked + fouls committed). Computed here from the boxscore.',
  pir_avg: 'PIR per game played',
  pir_total: 'PIR summed over the season',
  pir_per36: 'PIR scaled to 36 minutes on court — rate rather than volume, so bench players are comparable to starters',

  // plus/minus
  pm: 'Plus/minus — points scored minus conceded while this player was on court, reconstructed from substitution events in the play-by-play',
  pm_total: 'Plus/minus summed over the season',
  pm_per36: 'Plus/minus scaled to 36 minutes on court',

  // clutch
  clutch_pm: 'Plus/minus in clutch time: the last 5:00 of the 4th quarter or any overtime, while the margin was within 5 points',
  clutch_pts: 'Points scored in clutch time',
  clutch_time: 'Time on court during clutch situations',
  clutch_for: 'Points the club scored in clutch time',
  clutch_against: 'Points the club conceded in clutch time',

  // possessions and fouls
  poss: 'Estimated possessions: FGA + 0.44 × FTA − offensive rebounds + turnovers',
  poss_avg: 'Estimated possessions per game — the club’s pace',
  fouls_drawn: 'Fouls drawn (received) from opponents',
  fd100: 'Fouls drawn per 100 possessions — contact drawn at a rate that is comparable between starters and bench players',

  // play-by-play indexes
  max_run: 'Longest unanswered scoring streak — consecutive points with none conceded',
  run_when: 'When the run started and ended, in game clock',
  max_lead: 'Largest lead held at any point in the game',
  blown_lead: 'Largest lead held in a game the club went on to lose',
  score: 'Final score, home team first',
} as const;

export type MetricKey = keyof typeof GLOSSARY;

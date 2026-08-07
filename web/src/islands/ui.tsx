/** Small presentational pieces every island shares. */

import { createContext, useContext, useState, type ReactNode } from 'react';
import type { Club, Season } from '../lib/api';
import { useClubs } from './hooks';
import { GLOSSARY, type MetricKey } from '../lib/glossary';

/**
 * Crest lookup for the island's current season.
 *
 * A context rather than a prop: clubs are named at every depth of these
 * tables — rows, opponent cells, game sides, detail headings — and threading a
 * map through all of them would touch every component in between.
 */
const ClubsContext = createContext<Map<string, Club>>(new Map());

export function ClubsProvider({
  season,
  children,
}: {
  season: string | undefined;
  children: ReactNode;
}) {
  const clubs = useClubs(season);
  return <ClubsContext.Provider value={clubs}>{children}</ClubsContext.Provider>;
}

/**
 * A club's crest. Renders nothing when the club has no crest or the CDN image
 * fails, so a broken URL degrades to the plain name rather than a broken-image
 * icon — the name beside it always carries the meaning.
 */
export function Crest({ code, size = 18 }: { code: string | null | undefined; size?: number }) {
  const clubs = useContext(ClubsContext);
  const [failed, setFailed] = useState(false);
  const url = code ? clubs.get(code)?.crest_url : null;
  if (!url || failed) return null;
  return (
    <img
      className="crest"
      src={url}
      // inline, not a CSS class: a fixed `.crest` size would override the
      // attributes and pin every crest to the inline-text size
      style={{ width: size, height: size }}
      width={size}
      height={size}
      alt=""
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

/**
 * The standard way a club is named anywhere on the site: crest then label,
 * linking to the team page. `alt=""` on the crest is deliberate — the name is
 * right there, so announcing the logo too would just repeat it.
 */
export function ClubLabel({
  code,
  name,
  link = true,
  size,
}: {
  code: string | null | undefined;
  name?: string | null;
  link?: boolean;
  size?: number;
}) {
  const label = name ?? code ?? '—';
  return (
    <span className="club">
      <Crest code={code} size={size} />
      {link && code ? <a href={`/teams/?club=${code}`}>{label}</a> : <span>{label}</span>}
    </span>
  );
}

/** `clubs` is a comma-joined list — a player who transferred mid-season has two. */
export function ClubList({ clubs, link = true }: { clubs: string | null; link?: boolean }) {
  const codes = (clubs ?? '')
    .split(',')
    .map((c) => c.trim())
    .filter(Boolean);
  if (!codes.length) return <>—</>;
  return (
    <span className="club">
      {codes.map((c) => (
        <ClubLabel key={c} code={c} link={link} />
      ))}
    </span>
  );
}

/** Stand-in for the ~3% of players with no photo, and anyone who isn't a player. */
export function AvatarFallback({ size = 96 }: { size?: number }) {
  return (
    <svg
      className="avatar"
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="No photo available"
    >
      <circle cx="32" cy="23" r="11" />
      <path d="M8 62c0-13 11-22 24-22s24 9 24 22z" />
    </svg>
  );
}

/** A player portrait that falls back to the silhouette on a missing or dead URL. */
export function PlayerPhoto({
  src,
  name,
  size = 96,
}: {
  src: string | null | undefined;
  name: string | null;
  size?: number;
}) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return <AvatarFallback size={size} />;
  return (
    <img
      className="player-photo"
      src={src}
      width={size}
      height={size}
      alt={name ?? ''}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  );
}

/**
 * Table header cell that explains its own abbreviation on hover.
 *
 * The description lives in the glossary, not here, so "PIR" means the same
 * thing on every page. The panel is our own markup rather than the browser's
 * `title`: a native tooltip is rendered by the OS in its own font and colours,
 * which looks nothing like the rest of the page. `tabIndex` makes it reachable
 * by keyboard, which `title` never is, and `aria-describedby` ties it to the
 * header for screen readers.
 *
 * `alignEnd` flips the panel to hang from the right edge — the last columns of
 * a wide table would otherwise push it outside the scroll frame and get
 * clipped.
 */
export function Th({
  metric,
  label,
  left = false,
  sortable = false,
  sorted,
  onSort,
  alignEnd = false,
}: {
  metric?: MetricKey;
  label: ReactNode;
  left?: boolean;
  sortable?: boolean;
  sorted?: 'ascending' | 'descending';
  onSort?: () => void;
  alignEnd?: boolean;
}) {
  const help = metric ? GLOSSARY[metric] : undefined;
  const id = metric ? `help-${metric}` : undefined;
  return (
    <th
      aria-sort={sorted}
      aria-describedby={help ? id : undefined}
      tabIndex={help ? 0 : undefined}
      className={[sortable ? 'sortable' : '', help ? 'has-help' : ''].join(' ').trim() || undefined}
      style={left ? { textAlign: 'left' } : undefined}
      onClick={onSort}
    >
      {label}
      {help && (
        <span className={alignEnd ? 'tip tip-end' : 'tip'} id={id} role="tooltip">
          {help}
        </span>
      )}
    </th>
  );
}

export function Loading({ what }: { what: string }) {
  return <p className="loading">loading {what}</p>;
}

export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error">
      <strong>API error:</strong> {message}
    </div>
  );
}

/** Loading / error / empty in one place so every island behaves the same. */
export function Panel<T>({
  state,
  what,
  children,
}: {
  state: { data: T | null; error: string | null; loading: boolean };
  what: string;
  children: (data: T) => ReactNode;
}) {
  if (state.error) return <ErrorBox message={state.error} />;
  if (state.loading && !state.data) return <Loading what={what} />;
  if (!state.data) return <p className="muted">no {what}</p>;
  return <>{children(state.data)}</>;
}

export function SeasonPicker({
  seasons,
  season,
  onChange,
}: {
  seasons: Season[];
  season: string | undefined;
  onChange: (code: string) => void;
}) {
  if (seasons.length <= 1) return null;
  return (
    <label className="muted">
      Season{' '}
      <select value={season ?? ''} onChange={(e) => onChange(e.target.value)}>
        {seasons.map((s) => (
          <option key={s.season_code} value={s.season_code}>
            {s.season_name ?? s.season_code}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Shown for pre-2007 seasons, where no play-by-play exists to derive from. */
export function BoxscoreOnlyNote({ current }: { current: Season | undefined }) {
  if (!current || current.games_with_pbp > 0) return null;
  return (
    <p className="note">
      {current.season_name ?? current.season_code} predates play-by-play data, so
      +/-, clutch, runs and blown leads cannot be computed — boxscore metrics only.
    </p>
  );
}

export function Stat({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="stat">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  );
}

export function BackLink({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      className="btn"
      style={{ marginBottom: '1.2rem' }}
      onClick={onClick}
      type="button"
    >
      ← {children}
    </button>
  );
}

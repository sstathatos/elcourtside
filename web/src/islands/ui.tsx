/** Small presentational pieces every island shares. */

import type { ReactNode } from 'react';
import type { Season } from '../lib/api';
import { GLOSSARY, type MetricKey } from '../lib/glossary';

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

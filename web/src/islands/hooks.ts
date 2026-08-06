/** Shared island plumbing: async loading, the season selection, sorting. */

import { useCallback, useEffect, useMemo, useState } from 'react';
import { ApiError, api, type Season } from '../lib/api';

export interface Async<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
}

/**
 * Run an API call and track its state. `deps` behaves like useEffect's.
 * Late responses from superseded requests are dropped — switching season
 * quickly must not paint the previous season's rows.
 */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[]): Async<T> {
  const [state, setState] = useState<Async<T>>({ data: null, error: null, loading: true });

  useEffect(() => {
    let live = true;
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => live && setState({ data, error: null, loading: false }))
      .catch((err: unknown) =>
        live &&
        setState({
          data: null,
          loading: false,
          error: err instanceof ApiError ? err.message : 'could not reach the API',
        }),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return state;
}

/** The season list plus the currently selected code (defaults to newest). */
export function useSeasons() {
  const { data: seasons, error } = useApi(() => api.seasons(), []);
  const [selected, setSelected] = useState<string | undefined>(undefined);
  const season = selected ?? seasons?.[0]?.season_code;
  const current: Season | undefined = seasons?.find((s) => s.season_code === season);
  return { seasons: seasons ?? [], season, current, setSeason: setSelected, error };
}

/** Client-side sort state for tables whose rows are already in memory. */
export function useSort<T>(rows: T[], initial: keyof T, initialDesc = true) {
  const [key, setKey] = useState<keyof T>(initial);
  const [desc, setDesc] = useState(initialDesc);

  const toggle = useCallback(
    (next: keyof T) => {
      if (next === key) setDesc((d) => !d);
      else {
        setKey(next);
        setDesc(true);
      }
    },
    [key],
  );

  const sorted = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      const x = a[key];
      const y = b[key];
      // nulls always sink, whichever direction is active
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      if (typeof x === 'number' && typeof y === 'number') return desc ? y - x : x - y;
      return desc ? String(y).localeCompare(String(x)) : String(x).localeCompare(String(y));
    });
    return copy;
  }, [rows, key, desc]);

  const ariaSort = (column: keyof T): 'ascending' | 'descending' | undefined =>
    column === key ? (desc ? 'descending' : 'ascending') : undefined;

  return { sorted, key, desc, toggle, ariaSort };
}

/** Push a query param without a reload — detail views are same-page on a static site. */
export function setParam(name: string, value: string | null) {
  const url = new URL(window.location.href);
  if (value === null) url.searchParams.delete(name);
  else url.searchParams.set(name, value);
  window.history.pushState({}, '', url);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

/** Track a query param, including back/forward navigation. */
export function useParam(name: string): string | null {
  const read = () => new URLSearchParams(window.location.search).get(name);
  const [value, setValue] = useState<string | null>(
    typeof window === 'undefined' ? null : read(),
  );
  useEffect(() => {
    const onPop = () => setValue(read());
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name]);
  return value;
}

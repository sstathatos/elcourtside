# Running things on demand

Everything scheduled is also runnable by hand. The pattern is always the same:
create a Job **from** the CronJob, so the run inherits the chart's pod spec —
image tag, volume, security context — instead of a hand-written manifest that
quietly drifts from what actually ships.

```sh
kubectl -n elcourtside create job --from=cronjob/<name> <run-name>
```

Job names must be unique, hence the `$(date +%s)` suffixes below.

## Fetch new games now (what runs nightly)

Fetches games that are not yet final, then recomputes the metrics the site
reads. Minutes, typically 0–12 games.

```sh
kubectl -n elcourtside create job --from=cronjob/elcourtside-ingest ingest-$(date +%s)
kubectl -n elcourtside logs -f job/ingest-<stamp>
```

## Full backfill — every season

The `elcourtside-backfill` CronJob exists only to be triggered this way; it is
permanently suspended and never fires on its own.

```sh
kubectl -n elcourtside create job --from=cronjob/elcourtside-backfill backfill-$(date +%s)
```

Roughly 8 hours, paced at about one request every two seconds because the
Euroleague API is free and we do not get to be rude to it. Safe to interrupt
and rerun: writes are idempotent upserts and progress is tracked per game, so
a second run resumes rather than restarts.

## Back up now

```sh
kubectl -n elcourtside create job --from=cronjob/elcourtside-backup backup-$(date +%s)
```

Writes a `VACUUM INTO` snapshot to the backup volume and prunes to the newest
7. See [RESTORE.md](RESTORE.md) for going the other way.

## Why ingest and metrics run in one pod

`python -m ingest` fetches and parses; `python -m metrics` derives the tables
the API serves. Ingesting without recomputing leaves the site showing stale
numbers over fresh games — which is exactly what happened on the first
production deploy, when the chart shipped only the ingest step.

They are chained inside a single job rather than split across two schedules
because SQLite takes one writer: a long ingest and a clock-triggered metrics
run would collide. Sequencing them in one pod makes the ordering a property of
the job instead of a race between two schedules.

## Checking on things

```sh
# What the API thinks of its own database
kubectl -n elcourtside exec deploy/elcourtside-api -- \
  python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"

# Pipeline health, as Grafana sees it
kubectl -n elcourtside exec deploy/elcourtside-api -- \
  python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8000/metrics').read().decode())" \
  | grep elcourtside_
```

`status: degraded` with `database: unreadable` means the volume has no
database yet — run a backfill. It is deliberately not a crash: restarting the
pod does not conjure data, so the API stays up and says so.

# Restoring the elcourtside database

The database is **fully rebuildable** — every metric is derived from raw API
payloads that are themselves stored in it. So there are two recovery paths,
and the slow one always works:

| Path | Time | When |
|---|---|---|
| Restore the newest snapshot | minutes | Normal case — a corrupted or deleted volume |
| Re-backfill from the Euroleague API | ~8 h | No usable snapshot, or you want to start clean |

## What the backups are

The backup CronJob runs daily and keeps the newest `backup.retention`
snapshots (7 by default) on its own PVC, **pinned to a different node than
the data volume**. That pin is the point: a pod cannot mount another node's
local volume, so losing the data node must not take the backups with it.

Each snapshot is a complete SQLite file produced by `VACUUM INTO` on the API
side and streamed over HTTP from `/internal/backup.sqlite`. It is never a
copy of the live file, which could catch a half-written transaction. Files
are written as `.partial-*` and renamed only once complete, so an interrupted
run cannot leave something that looks like a good backup.

## Restore from a snapshot

```sh
NS=elcourtside

# 1. List what you have. The backup PVC is on the *other* node, so this pod
#    needs the same nodeSelector/tolerations the CronJob uses.
kubectl -n $NS get cronjob elcourtside-backup \
  -o jsonpath='{.spec.jobTemplate.spec.template.spec.nodeSelector}'

kubectl -n $NS create job --from=cronjob/elcourtside-backup list-backups
kubectl -n $NS logs job/list-backups

# 2. Stop the writer. The API is read-only, but an ingest mid-restore would
#    write into a file you are replacing.
kubectl -n $NS patch cronjob elcourtside-ingest -p '{"spec":{"suspend":true}}'
kubectl -n $NS scale deploy/elcourtside-api --replicas=0

# 3. Copy the snapshot across. The two PVCs are on different nodes, so this
#    goes through your machine rather than pod-to-pod.
#    (Run a helper pod on the backup node, stream out, then stream in.)
kubectl -n $NS exec <backup-helper-pod> -- \
  cat /backup/elcourtside-<STAMP>.sqlite > /tmp/restore.sqlite

kubectl -n $NS scale deploy/elcourtside-api --replicas=1
kubectl -n $NS rollout status deploy/elcourtside-api
kubectl -n $NS exec -i deploy/elcourtside-api -- \
  sh -c 'cat > /data/elcourtside.db' < /tmp/restore.sqlite

# 4. Check it before trusting it.
kubectl -n $NS exec deploy/elcourtside-api -- python -c "
import sqlite3
c = sqlite3.connect('file:/data/elcourtside.db?mode=ro', uri=True)
print('integrity:', c.execute('PRAGMA integrity_check').fetchone()[0])
print('games:', c.execute('SELECT COUNT(*) FROM games').fetchone()[0])
"

# 5. Restart the API so it reopens the file, and resume ingest.
kubectl -n $NS rollout restart deploy/elcourtside-api
kubectl -n $NS patch cronjob elcourtside-ingest -p '{"spec":{"suspend":false}}'
```

The `-wal` and `-shm` files are deliberately not restored: a `VACUUM INTO`
snapshot is self-contained, and stale sidecar files next to a replaced
database are worse than none.

## Rebuild from scratch

If no snapshot is usable, delete the PVC and let the ingest backfill:

```sh
kubectl -n elcourtside scale deploy/elcourtside-api --replicas=0
kubectl -n elcourtside delete pvc elcourtside-data     # `keep` policy means Helm will not do this for you
helm upgrade elcourtside helm/elcourtside -n elcourtside   # recreates the claim

# One-off full-history backfill; the nightly CronJob only does `latest`.
kubectl -n elcourtside create job backfill --from=cronjob/elcourtside-ingest
kubectl -n elcourtside patch job backfill --type json \
  -p '[{"op":"replace","path":"/spec/template/spec/containers/0/command","value":["python","-m","ingest","--seasons","all"]}]'
```

Expect ~8 hours: the ingest is paced at roughly one request every two seconds
because we do not get to be rude to a free public API. It is safe to
interrupt and re-run — every write is an idempotent upsert, and progress is
recorded per game, so a second run resumes rather than restarts.

## Both PVCs survive `helm uninstall`

Both carry `helm.sh/resource-policy: keep`. Uninstalling the release leaves
the data and the backups behind; removing them is a deliberate, separate
`kubectl delete pvc`.

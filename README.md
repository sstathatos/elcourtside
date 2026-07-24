# elcourtside

Fan-made Euroleague statistics site — standings, boxscores, PIR and +/-
leaderboards, and play-by-play-derived indexes: clutch performance, scoring
runs, blown leads, fouls drawn per possession.

Live at [elcourtside.sstathatos.dev](https://elcourtside.sstathatos.dev).
Data from the public Euroleague API; not affiliated with Euroleague Basketball.

- `api/` — FastAPI backend, metrics engine, and ingest ETL (Python)
- `web/` — Astro + React frontend
- `helm/` — Kubernetes chart, deployed by ArgoCD from the
  [sstathatos.dev](https://github.com/sstathatos/sstathatos.dev) app-of-apps
- `doc/` — [project plan](doc/plan.md) and phase knowledge checks

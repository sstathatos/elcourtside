# elcourtside API — and the ingest/metrics CLIs.
#
# One image, three entrypoints. The API serves what the pipeline wrote, so
# shipping them together is what keeps a parser change and the reader that
# depends on it from drifting apart:
#
#   uvicorn app.main:app     the API          (default CMD)
#   python -m ingest         the nightly ETL  (CronJob command)
#   python -m metrics        the recompute    (CronJob command)
#
# Build context is this directory: `docker build api/`.

FROM python:3.14-slim AS build

WORKDIR /src
COPY . ./
# --prefix keeps the install relocatable, so the runtime stage takes the
# packages and console scripts without pip, its cache, or the build deps.
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ELCOURTSIDE_DB=/data/elcourtside.db

COPY --from=build /install /usr/local

# The cluster's securityContext enforces runAsNonRoot, so the image has to be
# usable as a non-root UID rather than relying on the manifest to drop it.
RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown app:app /data

USER app
WORKDIR /home/app

# The database lives on a PVC in the cluster and a bind mount locally; it is
# never baked into the image.
VOLUME ["/data"]
EXPOSE 8000

# No --reload: this is the production entrypoint.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# elcourtside web — Astro's static output behind nginx.
#
# Deliberately the same shape as the sibling site's Dockerfile
# (sstathatos.dev), so both deployments are the same thing to operate.
#
# The build never contacts the API: the pages are static shells and the React
# islands fetch at runtime, which is what lets a nightly ingest change what
# visitors see without rebuilding this image.
#
# Build context is this directory: `docker build web/`.

FROM node:22-alpine AS build

WORKDIR /app
# Lockfile first: dependencies only reinstall when they actually change.
COPY package.json package-lock.json ./
RUN npm ci
COPY . ./
RUN npm run build

# Unprivileged variant: runs as UID 101 with pid/cache under /tmp — required
# because the pod securityContext enforces runAsNonRoot.
FROM nginxinc/nginx-unprivileged:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

# syntax=docker/dockerfile:1.7
#
# Mimik Suite — web image (Next.js 16 standalone).
# Build context is this `web/` directory (no external path deps).
#     docker build -f web/Dockerfile -t mimik-suite-web ./web
#
# Requires `output: "standalone"` in next.config.mjs (already set), which emits
# .next/standalone (self-contained server + traced node_modules) and
# .next/static (client assets).

# ── deps: install node_modules from the lockfile only ────────────────────────
FROM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ── build: compile the standalone server bundle ──────────────────────────────
FROM node:24-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined into the client bundle at BUILD time. They are
# public by design (never put secrets here). Passed as build args so the API
# origin can be baked per-environment; docker-compose.prod.yml wires this.
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL} \
    NEXT_TELEMETRY_DISABLED=1
RUN npm run build \
    && find .next/standalone -type f -name '*.map' -delete

# ── runner: minimal image serving the standalone output ──────────────────────
FROM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Run as a non-root user.
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 nextjs

# standalone/ contains server.js + the minimal traced node_modules.
COPY --from=build --chown=nextjs:nodejs /app/.next/standalone ./
# static/ and public/ are NOT bundled into standalone — copy them alongside.
COPY --from=build --chown=nextjs:nodejs /app/.next/static ./.next/static
# public/ is optional; copy if present (harmless no-op guard via the build stage).
COPY --from=build --chown=nextjs:nodejs /app/public ./public

USER nextjs
EXPOSE 3000

# server.js is emitted at the root of standalone/.
CMD ["node", "server.js"]

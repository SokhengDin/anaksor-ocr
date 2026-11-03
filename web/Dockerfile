# syntax=docker/dockerfile:1

FROM oven/bun:1.4.4-alpine@sha256:4cf82f5686b196504fe119db3fcd9185b191f82ece82c40680e597228ec6070a AS build
WORKDIR /src
ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json bun.lock ./
RUN bun install --frozen-lockfile --ignore-scripts

COPY . .

ARG API_URL=""
ARG SITE_URL=""
RUN if [ -n "$API_URL" ]; then export NEXT_PUBLIC_API_URL="$API_URL"; fi; \
    if [ -n "$SITE_URL" ]; then export NEXT_PUBLIC_SITE_URL="$SITE_URL"; fi; \
    bun run build


FROM node:24-alpine
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=8080 HOSTNAME=0.0.0.0

COPY --from=build --chown=node:node /src/.next/standalone ./
USER node
EXPOSE 8080
CMD ["node", "server.js"]

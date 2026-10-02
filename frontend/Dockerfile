# Sports Oracle frontend image. Builder runs the Vite build; the runtime is a
# dependency-free Node server that serves dist/ and proxies /api/<sport>/* to
# the NFL, NBA and NHL APIs named by NFL_API_URL / NBA_API_URL / NHL_API_URL.

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/dist ./dist
COPY server ./server
COPY package.json ./package.json
USER node
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget --spider --quiet http://127.0.0.1:${PORT:-8080}/healthz || exit 1
CMD ["node", "server/index.mjs"]

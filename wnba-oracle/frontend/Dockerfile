# WNBA Oracle frontend image. Multi-stage: builder runs Vite build, runtime
# serves the static bundle via a minimal Node http server.

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html serve.template.json build-serve-config.mjs ./
COPY src ./src
ARG VITE_API_URL
RUN case "$VITE_API_URL" in https://*) ;; *) echo "VITE_API_URL must be an HTTPS production endpoint" >&2; exit 1 ;; esac
ENV VITE_API_URL=${VITE_API_URL}
RUN node build-serve-config.mjs serve.template.json serve.json
RUN npm run build

FROM builder AS runtime-dependencies
RUN npm prune --omit=dev --ignore-scripts --no-audit --no-fund

FROM node:22-alpine AS runtime
WORKDIR /app
COPY --from=runtime-dependencies /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/serve.json ./serve.json
USER node
EXPOSE 4173
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD wget --spider --quiet http://127.0.0.1:4173/ || exit 1
CMD ["./node_modules/.bin/serve", "-c", "/app/serve.json", "-s", "dist", "-l", "4173"]

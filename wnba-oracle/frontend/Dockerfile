# WNBA Oracle frontend image. Multi-stage: builder runs Vite build, runtime
# serves the static bundle via a minimal Node http server.

FROM node:22-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM node:22-alpine AS runtime
RUN npm install -g serve@14
WORKDIR /app
COPY --from=builder /app/dist ./dist
EXPOSE 4173
CMD ["serve", "-s", "dist", "-l", "4173"]

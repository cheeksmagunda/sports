# NHL Oracle frontend

Lean Vite + React + TypeScript shell for NHL Oracle, modeled on the
`wnba-oracle/frontend` deploy shape with an NHL ice aesthetic.

## Local

```sh
cd nhl-oracle/frontend
npm ci
npm run dev
```

Optional: `VITE_API_URL=https://your-nhl-api.example` (HTTPS origin, no
path). Defaults to `http://localhost:8000`.

```sh
npm run lint
npm run typecheck
npm run test
npm run build
```

## Expected API (hosted NHL API not live yet)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | Probe; 404/network -> UI shows `unavailable` |
| GET | `/slate/{YYYY-MM-DD}` | Slate timing (TODO backend) |
| GET | `/lineup/{YYYY-MM-DD}` | Frozen five-card lineup (TODO backend) |

Contest law (from live audit): five-card ordered, slot multipliers
`(2.0, 1.8, 1.6, 1.4, 1.2)`, boost `none` until every team has played,
score label `value`, goalie eligible.

## Railway

Same pattern as WNBA frontend:

- `Dockerfile` multi-stage Node 22 build + `serve`
- `railway.toml` dockerfile builder
- Build arg / env `VITE_API_URL` must be an HTTPS origin (no path)
- Intended service name under sports-oracle mono: `nhl-frontend` on
  `nhl-staging` (provisioning is out of scope for the scaffold)

Do not mint secrets in this package.

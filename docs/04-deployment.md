# 04 — Deployment Plan

## Topology

```
                    ┌──────────────────────────────────────────┐
   Internet  ──TLS──▶│  Reverse proxy (Caddy / Nginx / Traefik) │
                    │   - TLS termination (Let's Encrypt)        │
                    │   - HTTP/2 + WebSocket upgrade             │
                    └───────────────┬──────────────┬────────────┘
                                    │              │
                         /api,/ws   │              │  / (static PWA)
                                    ▼              ▼
                         ┌────────────────┐  ┌──────────────┐
                         │ FastAPI (uvicorn)│  │ Next.js (node│
                         │  N replicas      │  │  or static)  │
                         └───────┬─────────┘  └──────────────┘
                                 │
                  ┌──────────────┼───────────────┐
                  ▼              ▼               ▼
            ┌──────────┐  ┌────────────┐  ┌─────────────┐
            │PostgreSQL│  │ Redis (pub/ │  │ Object store│
            │          │  │ sub for WS  │  │ (S3/MinIO)  │
            └──────────┘  │ fan-out)    │  └─────────────┘
                          └────────────┘
```

## docker-compose (single host / staging)

```yaml
# docker-compose.yml  (place at repo root)
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: thermo
      POSTGRES_PASSWORD: thermo
      POSTGRES_DB: thermobaby
    volumes: ["pgdata:/var/lib/postgresql/data"]

  backend:
    build: ./backend
    environment:
      THERMOBABY_DATABASE_URL: postgresql+psycopg://thermo:thermo@db:5432/thermobaby
      THERMOBABY_JWT_SECRET: ${JWT_SECRET}
      THERMOBABY_CORS_ORIGINS: '["https://app.example.com"]'
    depends_on: [db]
    ports: ["8000:8000"]

  frontend:
    build: ./frontend
    environment:
      NEXT_PUBLIC_API_BASE: https://api.example.com
      NEXT_PUBLIC_WS_BASE: wss://api.example.com
    ports: ["3000:3000"]

  proxy:
    image: caddy:2
    ports: ["80:80", "443:443"]
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile", "caddy_data:/data"]
    depends_on: [backend, frontend]

volumes: { pgdata: {}, caddy_data: {} }
```

```
# Caddyfile
app.example.com {
    reverse_proxy frontend:3000
}
api.example.com {
    reverse_proxy backend:8000
}
```

Caddy auto-provisions HTTPS and transparently upgrades WebSockets, satisfying the **HTTPS**
requirement (also required by `getUserMedia` and PWA install).

## Frontend build

- **Dynamic (SSR):** `next build && next start` behind the proxy.
- **Static export** (if no SSR needed): serve `out/` from any CDN/static host. The PWA service
  worker + manifest still work.

## Environments

| Env | DB | Notes |
|---|---|---|
| local | SQLite (`local mode`) | `gateway.py --simulate`, no Postgres needed |
| staging | Postgres (compose) | self-signed or staging cert |
| prod | managed Postgres + Redis + S3/MinIO | horizontal scaling, backups, log aggregation |

## Scaling notes

- WebSocket fan-out: the in-process `StreamHub` works for one backend replica. For **N replicas**
  put a **Redis pub/sub** behind it (publish processed frames on `session:<id>`, each replica
  subscribes and pushes to its local viewers). Sticky sessions or a shared bus are required.
- Thermal processing is CPU-bound (OpenCV/NumPy). Scale backend replicas horizontally; pin
  per-frame work and cap ingest FPS (the gateway already throttles via `--fps`).
- Store snapshots/recordings in object storage, not the DB; keep DB for metadata + downsampled
  readings.

## Security checklist (prod)

- [ ] TLS everywhere (`https`/`wss`); HSTS at the proxy.
- [ ] Strong `THERMOBABY_JWT_SECRET`; short access tokens + refresh rotation.
- [ ] Lock `CORS_ORIGINS` to the real frontend origin (no `*`).
- [ ] Authn on WebSocket ingest/stream (pass JWT as a query param/subprotocol; validate on
      `accept`). Reference code accepts unauthenticated for brevity — **gate before prod**.
- [ ] Encrypt data at rest (DB volume + object store) and PII fields.
- [ ] Rate-limit auth endpoints; audit-log alert events and exports.
- [ ] Backups + retention policy for patient data; document data-subject deletion.

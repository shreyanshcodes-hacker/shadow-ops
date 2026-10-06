# Railway Deployment Guide

## Overview

ShadowOps is designed to deploy on **Railway** with the following services:

| Service | Type | Purpose |
|---------|------|---------|
| `frontend` | Next.js (Docker) | React application |
| `backend` | FastAPI (Docker) | Python API server |
| `celery-worker` | Python (Docker) | Async task workers |
| `celery-beat` | Python (Docker) | Scheduled tasks |
| `n8n` | Docker (n8nio/n8n) | Workflow automation |
| `redis` | Railway Managed | Cache, queue, rate limiting |
| `postgresql` | Supabase (External) | Primary database |

## Architecture

```
Railway Project: shadow-ops
│
├── Service: frontend
│   ├── Dockerfile: apps/frontend/Dockerfile
│   ├── Build: npm run build
│   ├── Start: npm run start
│   ├── Port: 3000
│   ├── Health: GET /api/health
│   └── Domain: app.shadowops.io
│
├── Service: backend
│   ├── Dockerfile: apps/backend/Dockerfile
│   ├── Build: pip install -r requirements.txt
│   ├── Start: uvicorn app.main:app --host 0.0.0.0 --port 8000
│   ├── Port: 8000
│   ├── Health: GET /health
│   └── Domain: api.shadowops.io
│
├── Service: celery-worker
│   ├── Dockerfile: apps/backend/Dockerfile.worker
│   ├── Start: celery -A worker worker --loglevel=info --concurrency=4
│   └── Scaling: KEDA (queue depth)
│
├── Service: celery-beat
│   ├── Dockerfile: apps/backend/Dockerfile.beat
│   ├── Start: celery -A worker beat --loglevel=info
│   └── Replicas: 1 (fixed)
│
├── Service: n8n
│   ├── Image: n8nio/n8n:latest
│   ├── Port: 5678
│   └── Domain: n8n.shadowops.io (internal)
│
└── Service: redis
    └── Railway Managed Redis (HA)
```

## Prerequisites

1. Railway account
2. Supabase project (external)
3. Firebase project
4. Custom domains configured in Railway

## Deployment Steps

### 1. Create Railway Project

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project
railway init
```

### 2. Add Services

```bash
# Add Redis
railway add redis

# Add services from Dockerfiles
railway service create --name frontend --dockerfile apps/frontend/Dockerfile
railway service create --name backend --dockerfile apps/backend/Dockerfile
railway service create --name celery-worker --dockerfile apps/backend/Dockerfile.worker
railway service create --name celery-beat --dockerfile apps/backend/Dockerfile.beat
railway service create --name n8n --image n8nio/n8n:latest
```

### 3. Configure Environment Variables

#### Frontend Service

```bash
railway variables set --service frontend \
  NEXT_PUBLIC_API_URL=https://api.shadowops.io \
  NEXT_PUBLIC_FIREBASE_API_KEY=*** \
  NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=*** \
  NEXT_PUBLIC_FIREBASE_PROJECT_ID=*** \
  NEXT_PUBLIC_SUPABASE_URL=*** \
  NEXT_PUBLIC_SUPABASE_ANON_KEY=*** \
  NEXT_PUBLIC_WS_URL=wss://api.shadowops.io
```

#### Backend Service

```bash
railway variables set --service backend \
  ENVIRONMENT=production \
  DEBUG=false \
  FRONTEND_URL=https://app.shadowops.io \
  DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:6543/postgres?sslmode=require \
  SUPABASE_URL=https://xxx.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=*** \
  SUPABASE_ANON_KEY=*** \
  SUPABASE_JWT_SECRET=*** \
  FIREBASE_PROJECT_ID=*** \
  FIREBASE_CLIENT_EMAIL=*** \
  FIREBASE_PRIVATE_KEY=*** \
  REDIS_URL=redis://redis.railway.internal:6379/0 \
  CELERY_BROKER_URL=redis://redis.railway.internal:6379/0 \
  CELERY_RESULT_BACKEND=redis://redis.railway.internal:6379/1 \
  GEMINI_API_KEY=*** \
  GROK_API_KEY=*** \
  N8N_WEBHOOK_URL=https://n8n.shadowops.io/webhook \
  N8N_API_KEY=*** \
  SECRET_KEY=*** \
  SCAN_BUDGET_DEFAULT_USD=10.0 \
  LOG_LEVEL=info
```

#### Celery Worker & Beat

```bash
railway variables set --service celery-worker --service celery-beat \
  ENVIRONMENT=production \
  DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:6543/postgres?sslmode=require \
  SUPABASE_URL=https://xxx.supabase.co \
  SUPABASE_SERVICE_ROLE_KEY=*** \
  SUPABASE_ANON_KEY=*** \
  SUPABASE_JWT_SECRET=*** \
  FIREBASE_PROJECT_ID=*** \
  FIREBASE_CLIENT_EMAIL=*** \
  FIREBASE_PRIVATE_KEY=*** \
  REDIS_URL=redis://redis.railway.internal:6379/0 \
  CELERY_BROKER_URL=redis://redis.railway.internal:6379/0 \
  CELERY_RESULT_BACKEND=redis://redis.railway.internal:6379/1 \
  GEMINI_API_KEY=*** \
  GROK_API_KEY=*** \
  N8N_WEBHOOK_URL=https://n8n.shadowops.io/webhook \
  N8N_API_KEY=*** \
  SECRET_KEY=*** \
  LOG_LEVEL=info
```

#### n8n Service

```bash
railway variables set --service n8n \
  N8N_HOST=n8n.shadowops.io \
  N8N_PORT=5678 \
  N8N_PROTOCOL=https \
  WEBHOOK_URL=https://n8n.shadowops.io/webhook \
  N8N_BASIC_AUTH_ACTIVE=true \
  N8N_BASIC_AUTH_USER=admin \
  N8N_BASIC_AUTH_PASSWORD=*** \
  N8N_ENCRYPTION_KEY=*** \
  DB_TYPE=postgresdb \
  DB_POSTGRESDB_HOST=*** \
  DB_POSTGRESDB_PORT=5432 \
  DB_POSTGRESDB_DATABASE=n8n \
  DB_POSTGRESDB_USER=*** \
  DB_POSTGRESDB_PASSWORD=*** \
  EXECUTIONS_MODE=queue \
  QUEUE_BULL_REDIS_HOST=redis.railway.internal \
  QUEUE_BULL_REDIS_PORT=6379 \
  NODE_ENV=production
```

### 4. Configure Custom Domains

```bash
# Frontend
railway domain add app.shadowops.io --service frontend

# Backend
railway domain add api.shadowops.io --service backend

# n8n (internal access)
railway domain add n8n.shadowops.io --service n8n
```

### 5. Deploy

```bash
# Deploy all services
railway up

# Or deploy specific service
railway up --service backend
```

## Dockerfiles

### Frontend (apps/frontend/Dockerfile)

```dockerfile
FROM node:20-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM base AS runner
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

**Required next.config.js:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Frame-Options', value: 'DENY' },
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        ],
      },
    ];
  },
};
module.exports = nextConfig;
```

### Backend (apps/backend/Dockerfile)

```dockerfile
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

FROM base AS deps
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

RUN pip install --no-cache-dir semgrep

RUN addgroup --system --gid 1001 appgroup
RUN adduser --system --uid 1001 --gid 1001 appuser
USER appuser

COPY --chown=appuser:appgroup . .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Worker (apps/backend/Dockerfile.worker)

```dockerfile
FROM shadowops-backend:latest
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*
USER appuser
CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--concurrency=4", "--pool=prefork"]
```

### Beat (apps/backend/Dockerfile.beat)

```dockerfile
FROM shadowops-backend:latest
CMD ["celery", "-A", "worker", "beat", "--loglevel=info", "--scheduler", "celery.beat.PersistentScheduler"]
```

## Railway Configuration

### railway.toml

```toml
[build]
builder = "docker"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3

[[services]]
name = "frontend"
dockerfilePath = "apps/frontend/Dockerfile"
startCommand = "npm run start"

[[services]]
name = "backend"
dockerfilePath = "apps/backend/Dockerfile"
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4"

[[services]]
name = "celery-worker"
dockerfilePath = "apps/backend/Dockerfile.worker"

[[services]]
name = "celery-beat"
dockerfilePath = "apps/backend/Dockerfile.beat"

[[services]]
name = "n8n"
image = "n8nio/n8n:latest"
```

## Scaling Configuration

### Frontend
- Metric: CPU > 70% for 2min OR Memory > 80%
- Min Replicas: 2
- Max Replicas: 10
- Scale-up Cooldown: 60s
- Scale-down Cooldown: 300s

### Backend
- Metric: CPU > 70% OR Request latency P99 > 2s OR Queue depth > 50
- Min Replicas: 2
- Max Replicas: 20
- Scale-up Cooldown: 60s
- Scale-down Cooldown: 300s

### Celery Workers (KEDA)
- Metric: `celery_queue_length` > 10 per worker
- Min Replicas: 1
- Max Replicas: 10
- Cooldown: 120s

## Networking

### Internal Communication
- Services communicate via `.railway.internal` DNS
- Frontend → Backend via public domain
- Backend → n8n via `n8n.railway.internal`
- Backend → Redis via `redis.railway.internal`

### CORS
```python
CORS_ORIGINS = ["https://app.shadowops.io"]
```

## Health Checks

### Frontend
```
GET /api/health
```

### Backend
```
GET /health
```
Checks: Database, Redis, Supabase Storage

### n8n
```
GET /healthz
```

## Secrets Management

### Railway Variables (All Secrets)
- Never commit `.env` files
- Use Railway dashboard for all secrets
- Rotate quarterly

### Secret Rotation Procedure
1. Generate new secret
2. Update in Railway Variables
3. Deploy affected services (zero-downtime rolling)
4. Verify health checks pass
5. Revoke old secret

### Supabase Vault (Per-Asset Secrets)
- Asset credentials stored in Supabase Vault
- Backend accesses via `supabase_vault.get_secret(ref)`
- Audit trail on all secret access

## Monitoring & Logging

### Log Aggregation
- Railway built-in logs (stdout/stderr)
- Forward to: Datadog / Logtail / Axiom
- Retention: 30 days (Railway), 1 year (external)

### Metrics
- Railway Metrics: CPU, Memory, Network, Requests
- Custom Prometheus endpoint `/metrics`

### Alerting
| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| Backend down | Health check fails 3x | Critical | PagerDuty |
| High error rate | 5xx > 5% for 5min | Critical | PagerDuty |
| Queue backlog | Celery queue > 100 for 10min | Warning | Slack |
| AI cost spike | Daily cost > $50 | Warning | Slack + Email |

## Disaster Recovery

| Component | Backup | RPO | RTO |
|-----------|--------|-----|-----|
| PostgreSQL (Supabase) | Daily + PITR | 1 hour | < 1 hour |
| Supabase Storage | Cross-region replication | 24 hours | < 4 hours |
| Redis | AOF + RDB | 1 second | < 5 min |
| n8n Workflows | Git backup (daily) | 24 hours | < 30 min |
| Railway Config | Git (railway.toml) | N/A | < 10 min |

## Cost Estimation (Monthly)

| Service | Configuration | Est. Cost |
|---------|---------------|-----------|
| Frontend | 2-10 replicas, 1 vCPU/2GB | $20-100 |
| Backend | 2-20 replicas, 2 vCPU/4GB | $50-500 |
| Celery Workers | 1-10 replicas, 2 vCPU/4GB | $25-250 |
| Celery Beat | 1 replica, 0.5 vCPU/1GB | $5 |
| n8n | 1 replica, 1 vCPU/2GB | $20 |
| Redis | 2GB HA | $25 |
| **Total (typical)** | | **$150-500/mo** |

## Staging Environment

```
Railway Project: shadow-ops-staging
├── frontend-staging (app-staging.shadowops.io)
├── backend-staging (api-staging.shadowops.io)
├── celery-worker-staging
├── celery-beat-staging
├── n8n-staging
├── redis-staging
└── Supabase: shadow-ops-staging (separate project)
```

- Auto-deploy from `develop` branch
- Reduced resources (min replicas = 1)
- Separate Firebase project

## Local Development with Docker Compose

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build: ./apps/frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    volumes:
      - ./apps/frontend:/app
      - /app/node_modules

  backend:
    build: ./apps/backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/shadowops
      - REDIS_URL=redis://redis:6379
    depends_on: [db, redis]
    volumes:
      - ./apps/backend:/app

  celery-worker:
    build:
      context: ./apps/backend
      dockerfile: Dockerfile.worker
    environment: *backend_env
    depends_on: [redis, db]

  celery-beat:
    build:
      context: ./apps/backend
      dockerfile: Dockerfile.beat
    environment: *backend_env
    depends_on: [redis, db]

  n8n:
    image: n8nio/n8n:latest
    ports: ["5678:5678"]
    environment:
      - N8N_HOST=localhost
      - DB_TYPE=postgresdb
      - DB_POSTGRESDB_HOST=db
    depends_on: [db]

  db:
    image: postgres:16
    environment:
      - POSTGRES_DB=shadowops
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=postgres
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

volumes:
  pgdata:
```

## CI/CD Pipeline

```yaml
# .github/workflows/deploy.yml
name: Deploy to Railway

on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run tests
        run: |
          cd apps/frontend && npm test
          cd ../backend && pytest

  deploy-frontend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Railway
        uses: railwayapp/railway-deploy@v1
        with:
          service: frontend
          token: ${{ secrets.RAILWAY_TOKEN }}

  deploy-backend:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy to Railway
        uses: railwayapp/railway-deploy@v1
        with:
          service: backend
          token: ${{ secrets.RAILWAY_TOKEN }}

  deploy-workers:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Deploy workers
        uses: railwayapp/railway-deploy@v1
        with:
          service: celery-worker
          token: ${{ secrets.RAILWAY_TOKEN }}
      - name: Deploy beat
        uses: railwayapp/railway-deploy@v1
        with:
          service: celery-beat
          token: ${{ secrets.RAILWAY_TOKEN }}
```
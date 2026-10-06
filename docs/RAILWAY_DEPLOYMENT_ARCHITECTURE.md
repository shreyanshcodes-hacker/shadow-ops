# RAILWAY DEPLOYMENT ARCHITECTURE

## Deployment Topology

```
Railway Project: shadow-ops
│
├── Service: frontend
│   ├── Type: Next.js (Static + SSR)
│   ├── Dockerfile: apps/frontend/Dockerfile
│   ├── Build Command: npm run build
│   ├── Start Command: npm run start
│   ├── Port: 3000
│   ├── Health Check: GET /api/health
│   ├── Replicas: 2 (min) - 10 (max)
│   ├── Resources: 1 vCPU, 2GB RAM
│   ├── Environment Variables:
│   │   ├── NEXT_PUBLIC_API_URL=https://api.shadowops.io
│   │   ├── NEXT_PUBLIC_FIREBASE_API_KEY=***
│   │   ├── NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=***
│   │   ├── NEXT_PUBLIC_FIREBASE_PROJECT_ID=***
│   │   ├── NEXT_PUBLIC_SUPABASE_URL=***
│   │   ├── NEXT_PUBLIC_SUPABASE_ANON_KEY=***
│   │   └── NEXT_PUBLIC_WS_URL=wss://api.shadowops.io
│   └── Domains:
│       ├── app.shadowops.io (Custom, TLS)
│       └── shadowops-frontend.railway.app (Railway default)
│
├── Service: backend
│   ├── Type: FastAPI (Python)
│   ├── Dockerfile: apps/backend/Dockerfile
│   ├── Build Command: pip install -r requirements.txt
│   ├── Start Command: uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
│   ├── Port: 8000
│   ├── Health Check: GET /health
│   ├── Replicas: 2 (min) - 20 (max)
│   ├── Resources: 2 vCPU, 4GB RAM
│   ├── Environment Variables:
│   │   ├── DATABASE_URL=postgresql://... (Supabase pooler)
│   │   ├── SUPABASE_URL=***
│   │   ├── SUPABASE_SERVICE_KEY=***
│   │   ├── SUPABASE_JWT_SECRET=***
│   │   ├── FIREBASE_PROJECT_ID=***
│   │   ├── FIREBASE_ADMIN_KEY=*** (JSON)
│   │   ├── GEMINI_API_KEY=***
│   │   ├── GROK_API_KEY=***
│   │   ├── REDIS_URL=redis://redis.railway.internal:6379
│   │   ├── CELERY_BROKER_URL=redis://redis.railway.internal:6379/0
│   │   ├── CELERY_RESULT_BACKEND=redis://redis.railway.internal:6379/1
│   │   ├── N8N_WEBHOOK_URL=https://n8n.shadowops.io/webhook
│   │   ├── N8N_API_KEY=***
│   │   ├── SCAN_BUDGET_DEFAULT_USD=10.0
│   │   ├── LOG_LEVEL=info
│   │   └── ENVIRONMENT=production
│   └── Domains:
│       ├── api.shadowops.io (Custom, TLS)
│       └── shadowops-backend.railway.app (Railway default)
│
├── Service: celery-worker
│   ├── Type: Python (Celery)
│   ├── Dockerfile: apps/backend/Dockerfile.worker
│   ├── Start Command: celery -A worker worker --loglevel=info --concurrency=4
│   ├── Replicas: 1 (min) - 10 (max)
│   ├── Resources: 2 vCPU, 4GB RAM
│   ├── Environment Variables: (Same as backend)
│   └── Scaling: KEDA based on queue depth
│
├── Service: celery-beat
│   ├── Type: Python (Celery Beat)
│   ├── Dockerfile: apps/backend/Dockerfile.beat
│   ├── Start Command: celery -A worker beat --loglevel=info
│   ├── Replicas: 1 (fixed)
│   ├── Resources: 0.5 vCPU, 1GB RAM
│   ├── Environment Variables: (Same as backend)
│
├── Service: n8n
│   ├── Type: Docker (n8nio/n8n:latest)
│   ├── Port: 5678
│   ├── Health Check: GET /healthz
│   ├── Replicas: 1 (fixed)
│   ├── Resources: 1 vCPU, 2GB RAM
│   ├── Environment Variables:
│   │   ├── N8N_HOST=n8n.shadowops.io
│   │   ├── N8N_PORT=5678
│   │   ├── N8N_PROTOCOL=https
│   │   ├── WEBHOOK_URL=https://n8n.shadowops.io/webhook
│   │   ├── N8N_BASIC_AUTH_ACTIVE=true
│   │   ├── N8N_BASIC_AUTH_USER=admin
│   │   ├── N8N_BASIC_AUTH_PASSWORD=***
│   │   ├── N8N_ENCRYPTION_KEY=***
│   │   ├── DB_TYPE=postgresdb
│   │   ├── DB_POSTGRESDB_HOST=***
│   │   ├── DB_POSTGRESDB_PORT=5432
│   │   ├── DB_POSTGRESDB_DATABASE=n8n
│   │   ├── DB_POSTGRESDB_USER=***
│   │   ├── DB_POSTGRESDB_PASSWORD=***
│   │   ├── EXECUTIONS_MODE=queue
│   │   ├── QUEUE_BULL_REDIS_HOST=redis.railway.internal
│   │   ├── QUEUE_BULL_REDIS_PORT=6379
│   │   └── NODE_ENV=production
│   └── Domains:
│       ├── n8n.shadowops.io (Custom, TLS, internal access only)
│       └── n8n.railway.internal (Internal)
│
├── Service: redis
│   ├── Type: Railway Redis (Managed)
│   ├── Plan: Standard (HA)
│   ├── Max Memory: 2GB
│   ├── Eviction Policy: allkeys-lru
│   └── Used by: Celery broker, Celery results, Rate limiting, Caching, n8n queue
│
└── Database: Supabase (External)
    ├── Host: db.xxx.supabase.co
    ├── Port: 5432 (Pooled: 6543)
    ├── Connection: Transaction Pooler (PgBouncer)
    ├── Region: Same as Railway (us-east-1)
    ├── Backups: Daily, PITR enabled
    ├── Extensions: pgvector, uuid-ossp, pgcrypto
    └── Connection String: postgresql://user:pass@host:6543/postgres?sslmode=require
```

---

## Service Communication

```
┌─────────────┐     HTTPS      ┌─────────────┐
│  Frontend   │ ◄─────────────► │  Backend    │
│  (Railway)  │                 │  (Railway)  │
└─────────────┘                 └──────┬──────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
             ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
             │  Supabase   │    │   Redis     │    │    n8n      │
             │  (External) │    │  (Railway)  │    │  (Railway)  │
             └─────────────┘    └─────────────┘    └─────────────┘
                    │                  │                  │
                    ▼                  ▼                  ▼
             PostgreSQL +          Celery Broker      Workflow
             Storage               + Results           Engine
```

### Internal Networking
- All Railway services communicate via `.railway.internal` DNS
- No public exposure for backend, celery, n8n, redis
- Frontend → Backend via public domain (CORS configured)
- Backend → n8n via internal domain `n8n.railway.internal`

---

## Dockerfiles

### Frontend: `apps/frontend/Dockerfile`

```dockerfile
# Base
FROM node:20-alpine AS base
WORKDIR /app
RUN apk add --no-cache libc6-compat

# Dependencies
FROM base AS deps
COPY package.json package-lock.json* ./
RUN npm ci

# Builder
FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Runner
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

**Next.js Config** (`next.config.js`):
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  experimental: {
    serverActions: { allowedOrigins: ['app.shadowops.io'] },
  },
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

### Backend: `apps/backend/Dockerfile`

```dockerfile
# Base
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Dependencies
FROM base AS deps
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Runtime
FROM base AS runtime
COPY --from=deps /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=deps /usr/local/bin /usr/local/bin

# Install Semgrep
RUN pip install --no-cache-dir semgrep

# Create non-root user
RUN addgroup --system --gid 1001 appgroup
RUN adduser --system --uid 1001 --gid 1001 appuser
USER appuser

COPY --chown=appuser:appgroup . .

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Worker: `apps/backend/Dockerfile.worker`

```dockerfile
FROM shadowops-backend:latest
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*
USER appuser
CMD ["celery", "-A", "worker", "worker", "--loglevel=info", "--concurrency=4", "--pool=prefork"]
```

### Beat: `apps/backend/Dockerfile.beat`

```dockerfile
FROM shadowops-backend:latest
CMD ["celery", "-A", "worker", "beat", "--loglevel=info", "--scheduler", "celery.beat.PersistentScheduler"]
```

---

## Environment Variables

### Frontend (Railway Variables)
| Variable | Source | Required |
|----------|--------|----------|
| `NEXT_PUBLIC_API_URL` | Railway (backend domain) | Yes |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Firebase Console | Yes |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | Firebase Console | Yes |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | Firebase Console | Yes |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase Dashboard | Yes |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase Dashboard | Yes |
| `NEXT_PUBLIC_WS_URL` | Railway (backend domain + /ws) | Yes |

### Backend (Railway Variables)
| Variable | Source | Required |
|----------|--------|----------|
| `DATABASE_URL` | Supabase (Pooler) | Yes |
| `SUPABASE_URL` | Supabase Dashboard | Yes |
| `SUPABASE_SERVICE_KEY` | Supabase Dashboard | Yes |
| `SUPABASE_JWT_SECRET` | Supabase Dashboard (Settings → API) | Yes |
| `FIREBASE_PROJECT_ID` | Firebase Console | Yes |
| `FIREBASE_ADMIN_KEY` | Firebase Console (Service Account JSON) | Yes |
| `GEMINI_API_KEY` | Google AI Studio | Yes |
| `GROK_API_KEY` | xAI Console | Yes |
| `REDIS_URL` | Railway Redis (Internal) | Yes |
| `CELERY_BROKER_URL` | Railway Redis (Internal) | Yes |
| `CELERY_RESULT_BACKEND` | Railway Redis (Internal) | Yes |
| `N8N_WEBHOOK_URL` | Railway n8n domain | Yes |
| `N8N_API_KEY` | n8n Settings | Yes |
| `SCAN_BUDGET_DEFAULT_USD` | Config | Yes (default: 10.0) |
| `LOG_LEVEL` | Config | No (default: info) |
| `ENVIRONMENT` | Railway | Yes (production) |

### n8n (Railway Variables)
| Variable | Source | Required |
|----------|--------|----------|
| `N8N_ENCRYPTION_KEY` | Generate (32 chars) | Yes |
| `DB_POSTGRESDB_*` | Supabase (separate DB) | Yes |
| `QUEUE_BULL_REDIS_HOST` | Railway Redis | Yes |

---

## Build & Deploy Pipeline

### Railway Configuration (`railway.toml`)

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
startCommand = "uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"

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

### GitHub Actions (CI/CD)

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

---

## Health Checks

### Frontend
```typescript
// app/api/health/route.ts
export async function GET() {
  // Check backend connectivity
  const backendHealth = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/health`).catch(() => null);
  
  return NextResponse.json({
    status: 'healthy',
    timestamp: new Date().toISOString(),
    services: {
      backend: backendHealth?.ok ? 'healthy' : 'unhealthy',
    },
  });
}
```

### Backend
```python
# main.py
@app.get("/health")
async def health_check(db: DatabaseSession = Depends(get_db)):
    checks = {}
    
    # Database
    try:
        await db.execute("SELECT 1")
        checks["database"] = "healthy"
    except Exception:
        checks["database"] = "unhealthy"
    
    # Redis
    try:
        await redis.ping()
        checks["redis"] = "healthy"
    except Exception:
        checks["redis"] = "unhealthy"
    
    # Supabase Storage
    try:
        supabase.storage.list_buckets()
        checks["storage"] = "healthy"
    except Exception:
        checks["storage"] = "unhealthy"
    
    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"
    
    return {"status": overall, "checks": checks, "timestamp": datetime.utcnow().isoformat()}
```

### n8n
```bash
# Built-in: GET /healthz returns 200 if running
```

---

## Scaling Configuration

### Frontend
- **Metric**: CPU > 70% for 2min OR Memory > 80%
- **Min Replicas**: 2
- **Max Replicas**: 10
- **Scale-up Cooldown**: 60s
- **Scale-down Cooldown**: 300s

### Backend
- **Metric**: CPU > 70% OR Request latency P99 > 2s OR Queue depth > 50
- **Min Replicas**: 2
- **Max Replicas**: 20
- **Scale-up Cooldown**: 60s
- **Scale-down Cooldown**: 300s

### Celery Workers
- **KEDA Scaling**: Based on Redis queue depth
- **Metric**: `celery_queue_length` > 10 per worker
- **Min Replicas**: 1
- **Max Replicas**: 10
- **Cooldown**: 120s

---

## CORS Configuration

```python
# backend/main.py
CORS_ORIGINS = [
    "https://app.shadowops.io",
    "https://app-staging.shadowops.io",  # Staging
    "http://localhost:3000",  # Local dev
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=3600,
)
```

---

## Secrets Management

### Railway Variables (All Secrets)
- Never commit `.env` files
- Use Railway dashboard for all secrets
- Rotate quarterly (documented procedure)

### Secret Rotation Procedure
1. Generate new secret (API key, password, encryption key)
2. Update in Railway Variables
3. Deploy affected services (zero-downtime rolling)
4. Verify health checks pass
5. Revoke old secret
6. Update documentation

### Supabase Vault (Per-Asset Secrets)
- Asset credentials stored in Supabase Vault
- Backend accesses via `supabase_vault.get_secret(ref)`
- Audit trail on all secret access

---

## Logging & Monitoring

### Structured Logging (Backend)
```python
import structlog

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage
logger.info("scan_started", scan_id=scan_id, asset_id=asset_id, user_id=user_id)
logger.error("scan_failed", scan_id=scan_id, error=str(e), exc_info=True)
```

### Log Aggregation
- Railway built-in logs (stdout/stderr)
- Forward to: Datadog / Logtail / Axiom (configure log drain)
- Retention: 30 days (Railway), 1 year (external)

### Metrics
- **Railway Metrics**: CPU, Memory, Network, Requests
- **Custom Metrics** (Prometheus endpoint `/metrics`):
  - `scans_total`, `scans_duration_seconds`
  - `findings_total`, `findings_by_severity`
  - `ai_tokens_total`, `ai_cost_usd_total`
  - `verification_runs_total`, `verification_pass_rate`
  - `queue_depth`, `worker_utilization`

### Alerting
| Alert | Condition | Severity | Channel |
|-------|-----------|----------|---------|
| Backend down | Health check fails 3x | Critical | PagerDuty |
| High error rate | 5xx > 5% for 5min | Critical | PagerDuty |
| Queue backlog | Celery queue > 100 for 10min | Warning | Slack |
| AI cost spike | Daily cost > $50 | Warning | Slack + Email |
| Scan failure rate | > 20% fail in 1hr | Warning | Slack |
| Disk space | Redis > 80% | Warning | Slack |
| Cert expiry | < 30 days | Warning | Email |

---

## Disaster Recovery

### Backup Strategy
| Component | Backup | RPO | RTO |
|-----------|--------|-----|-----|
| PostgreSQL (Supabase) | Daily + PITR | 1 hour | < 1 hour |
| Supabase Storage | Cross-region replication | 24 hours | < 4 hours |
| Redis | AOF + RDB | 1 second | < 5 min |
| n8n Workflows | Git backup (daily) | 24 hours | < 30 min |
| Railway Config | Git (railway.toml) | N/A | < 10 min |

### Failover
- **Database**: Supabase handles (multi-AZ)
- **Redis**: Railway Redis HA (auto-failover)
- **Services**: Railway multi-region (future)
- **DNS**: Cloudflare (fast failover)

---

## Cost Estimation (Monthly, Production)

| Service | Configuration | Est. Cost |
|---------|---------------|-----------|
| Frontend | 2-10 replicas, 1 vCPU/2GB | $20-100 |
| Backend | 2-20 replicas, 2 vCPU/4GB | $50-500 |
| Celery Workers | 1-10 replicas, 2 vCPU/4GB | $25-250 |
| Celery Beat | 1 replica, 0.5 vCPU/1GB | $5 |
| n8n | 1 replica, 1 vCPU/2GB | $20 |
| Redis | 2GB HA | $25 |
| **Total (typical)** | | **$150-500/mo** |
| **Total (peak)** | | **$900-1200/mo** |

*Plus Supabase (Pro: $25/mo + usage) and external AI API costs*

---

## Staging Environment

```
Railway Project: shadow-ops-staging
│
├── frontend-staging (app-staging.shadowops.io)
├── backend-staging (api-staging.shadowops.io)
├── celery-worker-staging
├── celery-beat-staging
├── n8n-staging (n8n-staging.shadowops.io)
├── redis-staging
└── Supabase Project: shadow-ops-staging (separate)
```

- Auto-deploy from `develop` branch
- Reduced resources (min replicas = 1)
- Separate Firebase project
- Test data only

---

## Local Development (Docker Compose)

```yaml
# docker-compose.yml
version: '3.8'

services:
  frontend:
    build: ./apps/frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      - NEXT_PUBLIC_FIREBASE_*=...
    volumes:
      - ./apps/frontend:/app
      - /app/node_modules

  backend:
    build: ./apps/backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/shadowops
      - REDIS_URL=redis://redis:6379
      - ...
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
      - ...
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

---

## Security Checklist (Production)

- [ ] All secrets in Railway Variables (not code)
- [ ] CORS restricted to production domain only
- [ ] Security headers configured (CSP, HSTS, etc.)
- [ ] Rate limiting enabled on all endpoints
- [ ] RLS policies verified on all Supabase tables
- [ ] Firebase Auth: MFA required for admins
- [ ] Supabase: SSL required, connection pooling enabled
- [ ] n8n: Basic auth + HTTPS only
- [ ] Railway: Private networking for internal services
- [ ] Audit logging enabled and monitored
- [ ] Vulnerability scanning in CI (trivy, pip-audit, npm audit)
- [ ] Dependency updates automated (Renovate/Dependabot)
- [ ] Penetration test scheduled
- [ ] Incident response plan documented
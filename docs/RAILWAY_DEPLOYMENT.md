# RAILWAY DEPLOYMENT — ShadowOps

**Target:** Railway (railway.app)
**Status:** Configuration Required — Not Deployed
**Stage:** 12 Preparation

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Railway Project                       │
├──────────────┬──────────────┬──────────────┬────────────────┤
│   Frontend   │   FastAPI    │   Worker     │   Redis        │
│  (Next.js)   │   (API)      │  (Celery)    │  (Queue/Cache) │
│              │              │              │                │
│ Port: 3000   │ Port: 8000   │ Background   │ Port: 6379     │
│              │              │              │                │
└──────┬───────┴──────┬───────┴──────┬───────┴────────────────┘
       │              │              │
       └──────────────┼──────────────┘
                      ▼
            ┌──────────────────┐
            │   Supabase       │
            │  (PostgreSQL)    │
            │  External Managed│
            └──────────────────┘
```

---

## 2. Required Configuration Files

### 2.1 Backend Dockerfile

**File:** `backend/Dockerfile` (to be created)

```dockerfile
# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Install Semgrep
RUN pip install --no-cache-dir --user semgrep==1.45.0

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Create non-root user
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy Python packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser ./app ./app

# Create scan workspace directory
RUN mkdir -p /scan-workspace && chown -R appuser:appuser /scan-workspace

# Switch to non-root user
USER appuser

# PATH for user-installed packages
ENV PATH=/home/appuser/.local/bin:$PATH

# Environment variables (set in Railway UI)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health', timeout=5)"

# Expose port
EXPOSE 8000

# Start command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Frontend Dockerfile

**File:** `frontend/Dockerfile` (to be created)

```dockerfile
# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Install pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy package files
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# Copy source
COPY . .

# Build
RUN pnpm build

# Runtime stage
FROM node:20-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Create non-root user
RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

# Copy built assets
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

CMD ["node", "server.js"]
```

**Note:** Requires `output: 'standalone'` in `next.config.js`:
```javascript
// frontend/next.config.js
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // ... existing config
};
module.exports = nextConfig;
```

### 2.3 Worker Dockerfile

**File:** `backend/Dockerfile.worker` (to be created)

```dockerfile
# Build stage (same as backend)
FROM python:3.12-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

RUN pip install --no-cache-dir --user semgrep==1.45.0

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r appuser && useradd -r -g appuser appuser

COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser ./app ./app

RUN mkdir -p /scan-workspace && chown -R appuser:appuser /scan-workspace

USER appuser

ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Worker doesn't expose ports
# Health check via Redis/queue connectivity
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import redis; r=redis.Redis.from_url('$REDIS_URL'); r.ping()"

CMD ["celery", "-A", "app.workers.celery_app", "worker", "--loglevel=info", "--concurrency=2"]
```

### 2.4 Railway Configuration

**File:** `railway.json` (to be created at repo root)

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "DOCKERFILE",
    "dockerfilePath": "backend/Dockerfile"
  },
  "deploy": {
    "numReplicas": 1,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3,
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
```

**Service-specific configs (Railway UI):**
- **Frontend:** Dockerfile: `frontend/Dockerfile`, Port: 3000
- **API:** Dockerfile: `backend/Dockerfile`, Port: 8000
- **Worker:** Dockerfile: `backend/Dockerfile.worker`, No port

---

## 3. Environment Variables (Railway Secrets)

### 3.1 Required Secrets (Set in Railway UI → Variables → Raw Editor)

| Variable | Service | Description | Example |
|----------|---------|-------------|---------|
| `DATABASE_URL` | API, Worker | Supabase PostgreSQL connection | `postgresql+asyncpg://user:pass@host:5432/db` |
| `SUPABASE_URL` | API, Worker | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | API, Worker | Service role key (backend only) | `eyJ...` |
| `SUPABASE_ANON_KEY` | Frontend | Anon key for client | `eyJ...` |
| `SUPABASE_JWT_SECRET` | API | JWT secret for token verification | `xxx` |
| `FIREBASE_PROJECT_ID` | API | Firebase project ID | `shadowops-prod` |
| `FIREBASE_CLIENT_EMAIL` | API | Service account email | `firebase-adminsdk@shadowops-prod.iam.gserviceaccount.com` |
| `FIREBASE_PRIVATE_KEY` | API | Service account private key (multiline) | `-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----` |
| `SECRET_KEY` | API | JWT signing key (32+ chars) | `openssl rand -base64 32` |
| `GEMINI_API_KEY` | API, Worker | Google Gemini API key | `AIza...` |
| `GROK_API_KEY` | API, Worker | xAI Grok API key | `xai-...` |
| `REDIS_URL` | API, Worker | Railway Redis connection | `redis://default:pass@host:6379/0` |
| `CELERY_BROKER_URL` | API, Worker | Same as REDIS_URL | `redis://default:pass@host:6379/0` |
| `CELERY_RESULT_BACKEND` | API, Worker | Redis DB 1 | `redis://default:pass@host:6379/1` |
| `SCAN_WORKSPACE_ROOT` | API, Worker | Persistent volume path | `/scan-workspace` |
| `FRONTEND_URL` | API | Production frontend URL | `https://shadowops.railway.app` |
| `ENVIRONMENT` | All | `production` | `production` |
| `DEBUG` | All | `false` | `false` |
| `LOG_LEVEL` | All | `INFO` | `INFO` |

### 3.2 Optional Secrets

| Variable | Service | Description |
|----------|---------|-------------|
| `N8N_WEBHOOK_URL` | API, Worker | n8n webhook endpoint |
| `N8N_API_KEY` | API, Worker | n8n API key |
| `SMTP_HOST` | API, Worker | SMTP server for email |
| `SMTP_PORT` | API, Worker | SMTP port (587) |
| `SMTP_USER` | API, Worker | SMTP username |
| `SMTP_PASSWORD` | API, Worker | SMTP password |
| `SMTP_FROM` | API, Worker | From email address |

---

## 4. Persistent Storage

### 4.1 Scan Workspace Volume

**Requirement:** Semgrep scanner needs persistent workspace for repository clones.

**Railway Configuration:**
- Add Volume: `scan-workspace` → Mount path: `/scan-workspace`
- Size: 10GB minimum (configurable per plan)
- Shared between API and Worker services

**Alternative:** Use Railway's ephemeral storage with git clone per scan (slower but no volume cost).

### 4.2 Volume Mount in Dockerfile

Already handled in `Dockerfile` and `Dockerfile.worker`:
```dockerfile
RUN mkdir -p /scan-workspace && chown -R appuser:appuser /scan-workspace
VOLUME ["/scan-workspace"]
```

---

## 5. Database Migration Strategy

### 5.1 Migration Execution

**Option A: Pre-deploy Hook (Recommended)**
```json
// railway.json
{
  "deploy": {
    "preDeployCommand": "python -m alembic upgrade head"
  }
}
```

**Option B: Separate Migration Service**
- Create one-off Railway job for migrations
- Run before deploying API/Worker

**Critical: Prevent Concurrent Migrations**
```python
# app/db/session.py or migration script
import asyncio

async def run_migrations_with_lock():
    async with engine.begin() as conn:
        # Advisory lock prevents concurrent migrations
        await conn.execute(text("SELECT pg_advisory_xact_lock(123456789)"))
        await conn.run_sync(Base.metadata.create_all)
```

### 5.2 Migration Files Location

Ensure `alembic.ini` and `alembic/` directory are in backend:
```
backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_initial_schema.py
│       └── ...
```

**Action Required:** Convert Supabase SQL migrations to Alembic Python migrations, or use `alembic upgrade head` with raw SQL execution.

---

## 6. Health Checks & Readiness

### 6.1 Endpoints

| Endpoint | Purpose | Checks |
|----------|---------|--------|
| `GET /health` | Liveness | Always returns 200 if process alive |
| `GET /health/database` | DB connectivity | `SELECT 1` |
| `GET /ready` | Readiness | DB + Scanner binary + AI provider + Queue |

### 6.2 Railway Health Check Config

```json
// railway.json per service
{
  "deploy": {
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100,
    "healthcheckInterval": 30,
    "healthcheckFailureThreshold": 3
  }
}
```

---

## 7. CORS & Domain Configuration

### 7.1 CORS Origins

**Production:** `FRONTEND_URL` only (e.g., `https://shadowops.railway.app`)

**Code:** `app/core/config.py:88-91`
```python
@property
def cors_origins(self) -> list[str]:
    if self.is_production:
        return [self.FRONTEND_URL]
    return ["http://localhost:3000", "http://127.0.0.1:3000"]
```

### 7.2 Custom Domain

1. Add domain in Railway UI → Settings → Domains
2. Configure DNS: `CNAME shadowops.yourdomain.com → shadowops.railway.app`
3. Update `FRONTEND_URL` secret
4. Update Firebase authorized domains

---

## 8. Worker Concurrency & Scaling

### 8.1 Celery Configuration

**File:** `backend/app/workers/celery_app.py` (to be created)

```python
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "shadowops",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.scan_tasks",
        "app.workers.ai_tasks",
        "app.workers.verification_tasks",
        "app.workers.notification_tasks",
        "app.workers.outbox_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour hard limit
    task_soft_time_limit=3000,  # 50 min soft limit
    worker_prefetch_multiplier=1,  # One task per worker at a time
    worker_max_tasks_per_child=10,  # Recycle after 10 tasks
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
```

### 8.2 Concurrency Settings

| Worker Type | Concurrency | Rationale |
|-------------|-------------|-----------|
| Scan worker | 1-2 | Semgrep is CPU/memory intensive |
| AI worker | 2-4 | I/O bound (API calls) |
| Verification worker | 1 | Heavy scanner + tests |
| Notification worker | 4 | I/O bound (SMTP, webhooks) |
| Outbox processor | 2 | DB polling + delivery |

**Railway Scaling:** Horizontal scaling via `numReplicas` in service config.

---

## 9. Logging & Observability

### 9.1 Structured Logging

Already implemented in `app/main.py:15-30` (structlog JSON).

**Railway Logs:** Automatically captured from stdout/stderr.

### 9.2 Log Shipping (Recommended)

Add Vector/Fluent Bit sidecar or use Railway's log drain:
- Datadog
- Logtail
- New Relic
- Custom HTTP endpoint

---

## 10. Rollback Procedure

### 10.1 Application Rollback

1. Railway UI → Deployments → Select previous deployment → "Rollback"
2. Or: `railway rollback` CLI command

### 10.2 Database Rollback

**Risk:** Migrations are not reversible (no DOWN scripts).

**Mitigation:**
1. Always test migrations on staging first
2. Supabase PITR (Point-in-Time Recovery) — 7 day window
3. For schema changes: Add column → Deploy → Backfill → Remove column (multi-deploy)

**Emergency Rollback:**
1. Railway rollback application
2. Supabase Dashboard → Database → Backups → Restore to timestamp
3. Verify application works with restored schema

---

## 11. Secrets Management

### 11.1 Railway Secrets

- All sensitive values in Railway UI → Variables (Raw Editor)
- Never in Dockerfile, never in repo
- Rotate via Railway UI → Variables → Edit

### 11.2 Secret Rotation Schedule

| Secret | Rotation | Procedure |
|--------|----------|-----------|
| `SECRET_KEY` | 90 days | Generate new, update Railway, restart services |
| `SUPABASE_SERVICE_ROLE_KEY` | 90 days | Supabase Dashboard → Settings → API → Regenerate |
| `FIREBASE_PRIVATE_KEY` | 90 days | Firebase Console → Service Accounts → Generate new key |
| `GEMINI_API_KEY` | 90 days | Google AI Studio → API Keys → Regenerate |
| `GROK_API_KEY` | 90 days | xAI Console → API Keys → Regenerate |
| `SMTP_PASSWORD` | 90 days | Email provider → Regenerate app password |

---

## 12. Deployment Checklist

### Pre-Deploy
- [ ] All CRITICAL/HIGH findings from `docs/SECURITY_AUDIT.md` resolved
- [ ] `Dockerfile`, `Dockerfile.worker`, `frontend/Dockerfile` created and tested locally
- [ ] `railway.json` created
- [ ] `alembic` migrations configured and tested
- [ ] Railway project created
- [ ] Supabase production project created
- [ ] Firebase production project created
- [ ] All secrets added to Railway UI
- [ ] Redis addon provisioned
- [ ] Scan workspace volume created
- [ ] Custom domain configured (optional)

### Deploy
- [ ] Push to main branch (triggers Railway deploy)
- [ ] Verify all 3 services deploy successfully
- [ ] Run migrations (pre-deploy hook or manual)
- [ ] Verify `/health` and `/ready` endpoints
- [ ] Test authentication flow
- [ ] Test scan creation (with demo target)

### Post-Deploy
- [ ] Monitor logs for errors
- [ ] Verify Celery workers processing tasks
- [ ] Test notification delivery
- [ ] Configure log drain (Datadog/Logtail)
- [ ] Set up uptime monitoring (UptimeRobot/Pingdom)
- [ ] Document deployment in runbook

---

## 13. Cost Estimation (Railway Hobby/Pro)

| Resource | Hobby Plan | Pro Plan |
|----------|------------|----------|
| Frontend (1 replica) | $5/mo | Included |
| API (1 replica) | $5/mo | Included |
| Worker (1 replica) | $5/mo | Included |
| Redis | $5/mo | Included |
| Volume (10GB) | $1/mo | Included |
| **Total** | **~$21/mo** | **~$20/mo** |

*Note: Railway pricing changes; verify at railway.app/pricing*

---

## 14. References

- `docs/STAGE_12_BASELINE.md` — Deployment readiness audit
- `docs/SECURITY_AUDIT.md` — Security findings affecting deployment
- `docs/INCIDENT_RESPONSE.md` — Incident procedures
- `docs/BACKUP_AND_RECOVERY.md` — Backup/restore procedures
- Railway Docs: https://docs.railway.app
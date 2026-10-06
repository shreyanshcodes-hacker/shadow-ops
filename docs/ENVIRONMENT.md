# Environment Configuration

## Overview

ShadowOps uses environment variables for all configuration. Different environments (development, test, production) use separate `.env` files.

## Environment Files

| File | Purpose | Committed |
|------|---------|-----------|
| `.env.example` | Template with all variables | Yes |
| `.env` | Local development | No (gitignored) |
| `.env.test` | Test environment | No (gitignored) |
| `.env.production` | Production (Railway) | No (gitignored) |

## Variable Categories

### Core Application

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `ENVIRONMENT` | Runtime environment | Yes | `development` |
| `DEBUG` | Enable debug mode | No | `true` |
| `API_V1_PREFIX` | API route prefix | No | `/api/v1` |
| `FRONTEND_URL` | Frontend origin for CORS | Yes | `http://localhost:3000` |

### Database (Supabase)

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | PostgreSQL connection string | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key (admin) | Yes |
| `SUPABASE_ANON_KEY` | Anonymous key (client) | Yes |
| `SUPABASE_JWT_SECRET` | JWT secret for RLS | Yes |

**DATABASE_URL Format:**
```
# Local development (direct connection)
postgresql://postgres:postgres@localhost:5432/shadowops

# Production (Supabase pooler - transaction mode)
postgresql://user:pass@db.xxx.supabase.co:6543/postgres?sslmode=require
```

### Firebase Authentication

| Variable | Description | Required |
|----------|-------------|----------|
| `FIREBASE_PROJECT_ID` | Firebase project ID | Yes |
| `FIREBASE_CLIENT_EMAIL` | Service account email | Yes |
| `FIREBASE_PRIVATE_KEY` | Service account private key | Yes |

**FIREBASE_PRIVATE_KEY Format:**
```
"-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY_HERE\n-----END PRIVATE KEY-----\n"
```

### Redis

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `REDIS_URL` | Redis connection string | Yes | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | No | Same as REDIS_URL |
| `CELERY_RESULT_BACKEND` | Celery result backend | No | `redis://localhost:6379/1` |

### AI Providers (Future Stages)

| Variable | Description | Required |
|----------|-------------|----------|
| `GEMINI_API_KEY` | Google Gemini API key | Future |
| `GROK_API_KEY` | xAI Grok API key | Future |

### n8n (Future Stages)

| Variable | Description | Required |
|----------|-------------|----------|
| `N8N_WEBHOOK_URL` | n8n webhook endpoint | Future |
| `N8N_API_KEY` | n8n API key | Future |

### Security

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SECRET_KEY` | Application secret key | Yes | Generate with `openssl rand -hex 32` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiry | No | `60` |
| `ALGORITHM` | JWT algorithm | No | `HS256` |

### Scan Defaults

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `SCAN_BUDGET_DEFAULT_USD` | Default AI budget per scan | No | `10.0` |

### Logging

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `LOG_LEVEL` | Log level (DEBUG, INFO, WARNING, ERROR) | No | `INFO` |

## Environment-Specific Values

### Development (.env)

```bash
ENVIRONMENT=development
DEBUG=true
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/shadowops
REDIS_URL=redis://localhost:6379/0
LOG_LEVEL=DEBUG
```

### Test (.env.test)

```bash
ENVIRONMENT=test
DEBUG=false
FRONTEND_URL=http://localhost:3000
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/shadowops_test
REDIS_URL=redis://localhost:6379/1
LOG_LEVEL=WARNING
```

### Production (Railway Variables)

```bash
ENVIRONMENT=production
DEBUG=false
FRONTEND_URL=https://app.shadowops.io
DATABASE_URL=postgresql://user:pass@db.xxx.supabase.co:6543/postgres?sslmode=require
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=***
SUPABASE_ANON_KEY=***
SUPABASE_JWT_SECRET=***
FIREBASE_PROJECT_ID=***
FIREBASE_CLIENT_EMAIL=***
FIREBASE_PRIVATE_KEY=***
REDIS_URL=redis://redis.railway.internal:6379/0
CELERY_BROKER_URL=redis://redis.railway.internal:6379/0
CELERY_RESULT_BACKEND=redis://redis.railway.internal:6379/1
GEMINI_API_KEY=***
GROK_API_KEY=***
N8N_WEBHOOK_URL=https://n8n.shadowops.io/webhook
N8N_API_KEY=***
SECRET_KEY=***
LOG_LEVEL=INFO
```

## Secret Generation

```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate N8N_ENCRYPTION_KEY
openssl rand -hex 32
```

## Security Rules

1. **Never commit `.env` files** - They are in `.gitignore`
2. **Use `.env.example` as template** - Keep it updated
3. **Rotate secrets quarterly** - Document rotation procedure
4. **Use Railway Variables for production** - Never in code
5. **Use Supabase Vault for per-asset credentials** - Never in database
6. **Separate environments completely** - Different DBs, Redis, Firebase projects

## Validation

The application validates required environment variables on startup:

```python
# In app/core/config.py
class Settings(BaseSettings):
    DATABASE_URL: str  # Required - will raise if missing
    FIREBASE_PROJECT_ID: str  # Required
    # ... etc
```

Missing required variables will cause startup failure with clear error messages.
# Development Guide

## Prerequisites

- Node.js 20+
- Python 3.11+
- PostgreSQL 16+ (or Supabase)
- Redis 7+
- Firebase Project

## Quick Start

### 1. Clone and Install

```bash
# Frontend
cd frontend
npm install

# Backend
cd backend
pip install -r requirements.txt
```

### 2. Environment Setup

```bash
# Copy example env
cp .env.example .env

# Edit with your values
# Required: DATABASE_URL, FIREBASE_*, SUPABASE_*
```

### 3. Database Setup

```bash
# Run migrations
cd backend
alembic upgrade head
```

### 4. Start Development Servers

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

## Project Structure

```
shadowops/
├── frontend/                 # Next.js 14 App Router
│   ├── app/                  # App Router pages
│   ├── components/           # React components
│   │   ├── ui/              # Base UI components
│   │   ├── providers/       # Context providers
│   │   └── dashboard/       # Dashboard components
│   ├── lib/                 # Utilities, API client, auth
│   ├── hooks/               # Custom React hooks
│   └── types/               # TypeScript types
│
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── api/             # API routes
│   │   ├── core/            # Config, security
│   │   ├── db/              # Database session, models
│   │   ├── models/          # SQLAlchemy models
│   │   ├── schemas/         # Pydantic schemas
│   │   ├── services/        # Business logic
│   │   ├── repositories/    # Data access layer
│   │   ├── security/        # Auth, audit, middleware
│   │   ├── ai/              # AI provider abstractions
│   │   ├── agents/          # Agent framework
│   │   └── scanners/        # Semgrep integration
│   └── tests/
│
├── supabase/
│   └── migrations/          # SQL migrations
│
└── docs/                    # Documentation
```

## Available Scripts

### Frontend
```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run start        # Start production server
npm run lint         # Run ESLint
npm run typecheck    # Run TypeScript check
npm run test         # Run Jest tests
```

### Backend
```bash
uvicorn app.main:app --reload    # Start dev server
pytest                              # Run tests
pytest --cov=app                   # Run with coverage
alembic upgrade head               # Apply migrations
alembic revision --autogenerate -m "message"  # Create migration
```

## Design System

The ShadowOps design system uses:
- **Colors**: Black/charcoal backgrounds, crimson accents, white/cool-gray text
- **Typography**: Inter (UI), JetBrains Mono (code)
- **Components**: Glass cards, thin borders, subtle red glow
- **Dark mode only** - no light mode support

## API Conventions

- RESTful endpoints under `/api/v1`
- All responses wrapped in consistent format
- Errors: `{ "error": { "code": "...", "message": "...", "details": {} } }`
- Pagination: `page`, `page_size` query params
- Filtering: `?field=value` query params

## Authentication Flow

1. User authenticates via Firebase (email/password, OAuth)
2. Frontend gets Firebase ID token
3. Frontend sends `Authorization: Bearer <token>` to backend
4. Backend verifies token with Firebase Admin SDK
5. Backend creates/updates ShadowOps profile
6. Subsequent requests include user context

## Database Conventions

- All tables use UUID primary keys
- Workspace-scoped tables have `workspace_id` FK
- Audit fields: `created_at`, `updated_at`, `created_by`
- Soft deletes: `deleted_at` timestamp
- RLS policies enforce workspace isolation

## Testing

```bash
# Frontend tests
cd frontend
npm run test

# Backend tests
cd backend
pytest
pytest -v --tb=short
```

## Linting & Type Checking

```bash
# Frontend
npm run lint
npm run typecheck

# Backend
# Uses ruff/pylint for linting, mypy for type checking
```

## Deployment

See [Railway Deployment Guide](./RAILWAY.md)
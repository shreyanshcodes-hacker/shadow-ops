# SYSTEM ARCHITECTURE

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER                                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEXT.JS FRONTEND (React/TypeScript)                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │ Dashboard   │  │ Scan Mgmt   │  │ Findings    │  │ AI Security Chat    │ │
│  │ Assets      │  │ Attack Paths│  │ Remediation │  │ Reports             │ │
│  │ Team/Settings                    │  │ Agents      │  │                     │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────────────┘ │
│                                      │                                      │
│                            Firebase Auth (Client SDK)                        │
└──────────────────────────────────────│──────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PYTHON BACKEND (FastAPI)                           │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      API GATEWAY / ROUTER                           │   │
│  │  Auth Middleware │ Workspace Middleware │ Rate Limit │ Audit Log   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│        ┌─────────────────────────────┼─────────────────────────────┐       │
│        ▼                             ▼                             ▼       │
│ ┌───────────────┐            ┌───────────────┐            ┌───────────────┐ │
│ │   SERVICES    │            │  AGENT SYSTEM │            │SECURITY CONTROLS│ │
│ │               │            │               │            │               │ │
│ │ • Asset Svc   │            │ • AI Manager  │            │ • AuthZ       │ │
│ │ • Scan Svc    │            │ • Agents      │            │ • Workspace   │ │
│ │ • Finding Svc │            │ • Orchestrator│            │   Isolation   │ │
│ │ • Risk Svc    │            │ • Workflows   │            │ • Secrets     │ │
│ │ • Report Svc  │            │ • State Mgmt  │            │   Mgmt        │ │
│ │ • Chat Svc    │            │               │            │ • Audit Log   │ │
│ │ • AuthZ Svc   │            │               │            │ • Rate Limit  │ │
│ └───────────────┘            └───────────────┘            └───────────────┘ │
│        │                             │                             │       │
│        └─────────────────────────────┼─────────────────────────────┘       │
│                                      │                                      │
│        ┌─────────────────────────────┼─────────────────────────────┐       │
│        ▼                             ▼                             ▼       │
│ ┌───────────────┐            ┌───────────────┐            ┌───────────────┐ │
│ │  SUPABASE     │            │  GEMINI /     │            │   SEMGREP     │ │
│ │  POSTGRESQL   │            │  GROK AI      │            │   (CLI/API)   │ │
│ │               │            │               │            │               │ │
│ │ • Primary DB  │            │ • LLM Calls   │            │ • Static      │ │
│ │ • RLS Policies│            │ • Structured  │            │   Analysis    │ │
│ │ • Realtime    │            │   Output      │            │ • SAST        │ │
│ │ • Auth Hooks  │            │ • Cost Ctrl   │            │ • SCA         │ │
│ └───────────────┘            └───────────────┘            └───────────────┘ │
│        │                                                          │       │
│        ▼                                                          ▼       │
│ ┌───────────────┐                                         ┌───────────────┐ │
│ │  SUPABASE     │                                         │   N8N         │ │
│ │  STORAGE      │                                         │  (OPTIONAL)   │ │
│ │               │                                         │               │ │
│ │ • Evidence    │                                         │ • Notifications│ │
│ │ • Reports     │                                         │ • Schedules   │ │
│ │ • Artifacts   │                                         │ • Integrations│ │
│ │ • Scan Logs   │                                         │ • Ops Auto    │ │
│ └───────────────┘                                         └───────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### Frontend: Next.js + TypeScript + Tailwind CSS

| Aspect | Decision |
|--------|----------|
| Framework | Next.js 14+ (App Router) |
| Language | TypeScript (strict mode) |
| Styling | Tailwind CSS + custom design system |
| State | React Query (server state) + Zustand (client state) |
| Auth | Firebase Auth Client SDK |
| Real-time | Supabase Realtime subscriptions |
| Charts | Recharts / Tremor |
| Components | Custom + Radix UI primitives |

### Backend: Python + FastAPI

| Aspect | Decision |
|--------|----------|
| Framework | FastAPI (async) |
| Language | Python 3.11+ |
| ORM | SQLAlchemy 2.0 (async) + Alembic |
| Validation | Pydantic v2 |
| Auth | Firebase Admin SDK (token verification) |
| DB | Supabase (PostgreSQL) via asyncpg |
| Task Queue | Redis + Celery (for scan orchestration) |
| AI Client | Custom wrappers for Gemini/Grok APIs |
| Semgrep | Subprocess execution + JSON output parsing |

### Database: Supabase PostgreSQL

| Feature | Usage |
|---------|-------|
| Row Level Security (RLS) | Workspace isolation enforcement |
| Realtime | Live scan progress, finding updates |
| Auth Hooks | Sync Firebase users → profiles |
| Storage | Evidence files, reports, scan artifacts |
| Functions | RPC for complex queries (attack paths) |
| pgvector | Embeddings for AI chat retrieval (future) |

### AI: Gemini + Grok

| Model | Primary Use Cases |
|-------|-------------------|
| **Gemini 1.5 Pro** | Complex reasoning, large context (code analysis, attack paths, remediation) |
| **Gemini 1.5 Flash** | High-volume, low-latency (classification, summarization, chat) |
| **Grok** | Alternative reasoning, security-specific knowledge, unfiltered analysis |

**Model Selection Strategy**: Route by task complexity, context size, and cost. Never treat as interchangeable.

### Automation: n8n (Self-hosted on Railway)

| Workflow Type | Examples |
|---------------|----------|
| Notifications | Slack, Email, PagerDuty on critical findings |
| Scheduled | Daily scans, weekly reports, license checks |
| Integrations | GitHub/GitLab webhooks, Jira ticket creation |
| Operational | Cleanup, retention, health checks |

---

## Data Flow: Scan Request

```
User (Frontend)
    │
    ▼ POST /api/v1/scans { asset_id, scan_type }
Frontend
    │
    ▼ Firebase ID Token + Workspace Context
Python Backend (FastAPI)
    │
    ├── Auth Middleware: Verify token, extract user_id
    ├── Workspace Middleware: Verify membership, set RLS context
    ├── AuthZ Service: Check asset.authorization_status == VERIFIED
    ├── Scan Service: Create scan record (status=QUEUED)
    ├── Event: Publish SCAN_QUEUED to Redis/Celery
    └── Response: { scan_id, status: "queued" }
    │
    ▼ Celery Worker (Scan Orchestrator)
Scan Orchestrator
    │
    ├── Update scan: RUNNING
    ├── For each phase: RECON → CODE_ANALYSIS → DEP_ANALYSIS
    │   ├── Spawn agent runs (tracked in agent_runs table)
    │   ├── Execute Semgrep (code/dep phases)
    │   ├── Call AI Manager for analysis phases
    │   ├── Normalize & store findings + evidence
    │   └── Emit scan_events for realtime UI
    ├── AI Analysis: Correlate findings, build attack paths
    ├── Risk Engine: Calculate deterministic scores
    ├── Update scan: COMPLETED / FAILED / CANCELLED
    └── Trigger: Notifications, Report Generation
```

---

## Network & Security Boundaries

```
┌──────────────────┐     HTTPS/TLS      ┌──────────────────┐
│   Frontend       │ ◄─────────────────► │   Backend API    │
│   (Railway)      │                     │   (Railway)      │
└──────────────────┘                     └────────┬─────────┘
                                                   │
                    ┌──────────────────────────────┼──────────────────────────────┐
                    ▼                              ▼                              ▼
           ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
           │   Supabase    │              │   AI APIs     │              │   Semgrep     │
           │   (Managed)   │              │   (External)  │              │   (Local)     │
           └───────────────┘              └───────────────┘              └───────────────┘
                    │                              │                              │
                    ▼                              ▼                              ▼
           ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
           │  PostgreSQL   │              │  Gemini/Grok  │              │  Rulesets     │
           │  + Storage    │              │               │              │  (Local/Remote)│
           └───────────────┘              └───────────────┘              └───────────────┘
```

### CORS Policy
- Frontend origin only (configured via Railway environment)
- No wildcard origins
- Credentials: true (for Firebase auth cookies if used)

### Secrets Management
- **Railway Variables**: All secrets (API keys, DB URLs, Firebase config)
- **Never in code**: No .env files committed
- **Rotation**: Documented procedure for each secret type

---

## Deployment Topology (Railway)

```
Railway Project: shadow-ops
│
├── Service: frontend (Next.js)
│   ├── Build: npm run build
│   ├── Start: npm run start
│   ├── Port: 3000
│   ├── Health: GET /api/health
│   ├── Env: NEXT_PUBLIC_*, FIREBASE_*
│   └── Domain: app.shadowops.io (custom)
│
├── Service: backend (FastAPI)
│   ├── Build: pip install -r requirements.txt
│   ├── Start: uvicorn main:app --host 0.0.0.0 --port 8000
│   ├── Port: 8000
│   ├── Health: GET /health
│   ├── Env: SUPABASE_*, FIREBASE_*, GEMINI_*, GROK_*, REDIS_*
│   └── Internal: backend.railway.internal
│
├── Service: n8n (Optional)
│   ├── Image: n8nio/n8n
│   ├── Port: 5678
│   ├── Env: N8N_*, WEBHOOK_URL
│   └── Internal: n8n.railway.internal
│
├── Service: redis (Managed)
│   └── Used by: Celery, Rate limiting, Caching
│
└── Database: Supabase (External Managed)
    ├── Host: db.xxx.supabase.co
    ├── Port: 5432
    └── Connection: Pooler (transaction mode)
```

---

## API Contract (High-Level)

### Authentication
```
POST   /api/v1/auth/verify          # Verify Firebase token, return session
GET    /api/v1/auth/me              # Current user profile
```

### Workspaces
```
POST   /api/v1/workspaces           # Create workspace
GET    /api/v1/workspaces           # List user's workspaces
GET    /api/v1/workspaces/{id}      # Get workspace
PATCH  /api/v1/workspaces/{id}      # Update workspace
DELETE /api/v1/workspaces/{id}      # Delete workspace
POST   /api/v1/workspaces/{id}/members  # Invite member
PATCH  /api/v1/workspaces/{id}/members/{user_id}  # Update role
DELETE /api/v1/workspaces/{id}/members/{user_id}  # Remove member
```

### Assets
```
POST   /api/v1/workspaces/{ws_id}/assets           # Add asset
GET    /api/v1/workspaces/{ws_id}/assets           # List assets
GET    /api/v1/workspaces/{ws_id}/assets/{id}      # Get asset
PATCH  /api/v1/workspaces/{ws_id}/assets/{id}      # Update asset
POST   /api/v1/workspaces/{ws_id}/assets/{id}/authorization  # Record authorization
DELETE /api/v1/workspaces/{ws_id}/assets/{id}      # Delete asset
```

### Scans
```
POST   /api/v1/workspaces/{ws_id}/scans            # Start scan
GET    /api/v1/workspaces/{ws_id}/scans            # List scans
GET    /api/v1/workspaces/{ws_id}/scans/{id}       # Get scan details
GET    /api/v1/workspaces/{ws_id}/scans/{id}/events # Scan event stream (SSE)
POST   /api/v1/workspaces/{ws_id}/scans/{id}/cancel # Cancel scan
```

### Findings
```
GET    /api/v1/workspaces/{ws_id}/findings         # List findings (filterable)
GET    /api/v1/workspaces/{ws_id}/findings/{id}    # Get finding + evidence
PATCH  /api/v1/workspaces/{ws_id}/findings/{id}    # Update finding status
GET    /api/v1/workspaces/{ws_id}/findings/{id}/evidence # Get evidence
```

### Attack Paths
```
GET    /api/v1/workspaces/{ws_id}/attack-paths     # List attack paths
GET    /api/v1/workspaces/{ws_id}/attack-paths/{id} # Get path graph
```

### Remediation
```
POST   /api/v1/workspaces/{ws_id}/findings/{id}/remediation  # Generate proposal
GET    /api/v1/workspaces/{ws_id}/remediations               # List proposals
POST   /api/v1/workspaces/{ws_id}/remediations/{id}/approve  # Approve
POST   /api/v1/workspaces/{ws_id}/remediations/{id}/apply    # Apply (authorized)
GET    /api/v1/workspaces/{ws_id}/remediations/{id}/verify   # Verify
```

### Reports
```
POST   /api/v1/workspaces/{ws_id}/reports          # Generate report
GET    /api/v1/workspaces/{ws_id}/reports          # List reports
GET    /api/v1/workspaces/{ws_id}/reports/{id}     # Get report
GET    /api/v1/workspaces/{ws_id}/reports/{id}/download # Download PDF/HTML
```

### AI Chat
```
POST   /api/v1/workspaces/{ws_id}/chat/conversations  # New conversation
GET    /api/v1/workspaces/{ws_id}/chat/conversations  # List conversations
POST   /api/v1/workspaces/{ws_id}/chat/conversations/{id}/messages  # Send message
GET    /api/v1/workspaces/{ws_id}/chat/conversations/{id}/messages  # Get history
```

### Audit Logs
```
GET    /api/v1/workspaces/{ws_id}/audit-logs       # Query audit logs (admin)
```

---

## Error Handling Standards

| HTTP Code | Use Case |
|-----------|----------|
| 200 | Success |
| 201 | Created |
| 400 | Invalid request body/params |
| 401 | Invalid/expired Firebase token |
| 403 | Workspace access denied, authorization missing |
| 404 | Resource not found |
| 409 | Conflict (e.g., duplicate asset) |
| 422 | Validation error (Pydantic) |
| 429 | Rate limited |
| 500 | Internal server error |
| 503 | Service unavailable (AI, Semgrep, DB) |

### Error Response Format
```json
{
  "error": {
    "code": "AUTHORIZATION_REQUIRED",
    "message": "Asset requires verified authorization before scanning",
    "details": { "asset_id": "asset_123", "required": "verified" }
  }
}
```
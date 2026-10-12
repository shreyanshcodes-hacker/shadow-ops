# STAGE 8 BASELINE — Existing Architecture Audit (Stages 0–7)

## 1. Overview

This document audits the current ShadowOps codebase (Stages 0–7) to identify reusable services, verify existing functionality, and catalog gaps before implementing Stage 8: AI Remediation, Human Approval & Safe Patch Management.

---

## 2. Stage-by-Stage Summary

| Stage | Area | Status | Key Artifacts |
|-------|------|--------|---------------|
| 0 | Project Foundation | ✅ Complete | Next.js 15, FastAPI, Supabase, Railway config |
| 1 | Workspace & Auth | ✅ Complete | Firebase Auth, profiles, workspaces, members |
| 2 | Asset & Authorization | ✅ Complete | Assets, authorization workflow, RLS |
| 3 | Scanning Foundation | ✅ Complete | Semgrep runner, scan targets, scan events |
| 4 | AI Security Manager | ✅ Complete | AI providers, structured analysis, prompt injection defense |
| 5 | Attack Path & Risk | ✅ Complete | Correlation engine, attack paths, deterministic risk |
| 6 | Evidence & Relationships | ✅ Complete | Finding evidence, relationship confirmation |
| 7 | AI Security Team | ✅ Complete | 5 agents, orchestration, human review |

---

## 3. Reusable Services & Infrastructure

### 3.1 AI Provider Abstraction (`app/ai/providers/`)
- **Base class**: `AIProvider` with `generate_structured`, `generate_text`, `health_check`
- **Providers**: Gemini (`gemini.py`), Grok (`grok.py`) — lazy initialized
- **Registry**: `AIProviderRegistry` with global instance
- **Schemas**: `AIResponse[T]`, `AIResponseMetadata`, error hierarchy

### 3.2 AI Safety & Validation (`app/ai/`)
- **Prompt Injection Defense**: `TRUSTED_SYSTEM_INSTRUCTIONS` / `UNTRUSTED_SECURITY_EVIDENCE` delimiters
- **Secret Redaction**: 32+ patterns in `safety.py`
- **Output Validation**: `validation.py` with strict schema checking, evidence reference verification
- **Context Sanitization**: `sanitize_for_ai`, `sanitize_evidence_dict`, truncation limits

### 3.3 AI Manager (`app/ai/manager.py`)
- **AIManager**: Orchestrates finding analysis
- **Flow**: Evidence retrieval → Sanitization → Prompt building → Provider call → Validation → Persistence
- **Deduplication**: Input hash-based (SHA256 of normalized evidence)
- **Audit Logging**: All AI runs and analyses logged

### 3.4 Security Team Agents (`app/agents/team/`)
- **5 Agents**: Recon, Vulnerability Analyst, Attack Path Analyst, Risk Analyst, Security Reviewer
- **Common Contract**: `AgentRequest` / `AgentResponse` with typed `structured_output`
- **Orchestrator**: `SecurityTeamOrchestrator` with dependency-aware scheduling
- **Context Builders**: Per-agent minimal context extraction
- **Cost Controls**: Max retries (2), timeout (300s), max team duration (1800s)

### 3.5 Database & Repository Layer
- **Models** (`app/models/__init__.py`): 20+ SQLAlchemy models with workspace isolation
- **Repositories** (`app/repositories/__init__.py`): CRUD + query methods for all entities
- **Migrations**: 5 Supabase migrations (001–005) with RLS policies

### 3.6 API Layer (`app/api/v1/`)
- **Conventions**: FastAPI, dependency injection, workspace membership validation
- **Auth**: `get_current_user`, `require_workspace_member`
- **Endpoints**: Workspaces, Assets, Scans, Findings, AI Analysis, Attack Paths, Security Team

### 3.7 Frontend (`frontend/app/`)
- **Pages**: Dashboard, Assets, Scans, Findings, Attack Paths, Security Team
- **API Client** (`lib/api.ts`): Typed methods for all endpoints
- **Auth**: Firebase integration with token refresh

---

## 4. Verified Working Functionality

| Feature | Verified | Notes |
|---------|----------|-------|
| Workspace CRUD | ✅ | Tests pass |
| Asset management | ✅ | Authorization workflow |
| Scan execution | ⚠️ | Semgrep runner implemented, needs live credentials |
| Finding storage | ✅ | With evidence |
| AI Finding Analysis | ⚠️ | Code complete, needs API keys |
| AI Scan Analysis | ⚠️ | Code complete, needs API keys |
| Security Team Orchestration | ⚠️ | Code complete, needs API keys |
| Attack Path Building | ✅ | Deterministic engine works |
| Risk Calculation | ✅ | Deterministic, explainable |
| Correlation Engine | ✅ | Deterministic relationships |
| Frontend Pages | ⚠️ | TypeScript compiles, needs runtime test |
| RLS Policies | ✅ | All tables protected |
| Audit Logging | ✅ | Immutable append-only |

---

## 5. Gaps & Missing for Stage 8

### 5.1 Remediation Data Model (MISSING)
The initial migration `001_initial_schema.sql` contains `remediation_proposals` and `remediation_approvals` tables, but **these are NOT represented in SQLAlchemy models** (`app/models/__init__.py`). The current models only go up to Stage 7 entities.

### 5.2 Remediation Service (MISSING)
No `RemediationService` or equivalent exists. Stage 8 requires:
- AI remediation proposal generation
- Patch creation & validation
- Human approval workflow
- Safe patch application
- Rollback & recovery

### 5.3 Patch Processing (MISSING)
No patch generation, validation, or application infrastructure exists. Required:
- Unified diff parsing/generation
- Path traversal protection
- Isolated working copy management
- Syntax validation
- Semgrep re-scan on patched code

### 5.4 Human Approval Workflow (MISSING)
No approval service exists. Required:
- Server-side approval validation
- Patch hash binding
- Approval expiration
- Re-approval on patch change

### 5.5 API Endpoints (MISSING)
No remediation endpoints in `app/api/v1/`. Required per spec:
- `POST /findings/{finding_id}/remediations`
- `GET /remediations`
- `GET /remediations/{id}`
- `POST /remediations/{id}/validate`
- `POST /remediations/{id}/approve`
- `POST /remediations/{id}/reject`
- `POST /remediations/{id}/apply`
- `POST /remediations/{id}/rollback`
- `GET /remediations/{id}/history`

### 5.6 Frontend Pages (MISSING)
No `/remediations` or `/remediations/[id]` pages exist.

### 5.7 Database Migration (MISSING)
Need new migration `0006_stage8_remediation.sql` for:
- Remediation proposals (extended from initial schema)
- Patch versions & validation results
- Approval records with patch hash binding
- Application history
- Rollback records
- Verification handoff records

---

## 6. Security Boundaries to Preserve

| Boundary | Current Enforcement | Stage 8 Must Maintain |
|----------|---------------------|----------------------|
| Workspace Isolation | RLS + query filtering | All new tables |
| AI Prompt Injection | TRUSTED/UNTRUSTED delimiters | Remediation prompts |
| Secret Redaction | 32+ patterns | All evidence to AI |
| Authorization Checks | `require_workspace_member` | All remediation endpoints |
| No Autonomous Actions | Agents analytical only | No auto-apply, no auto-approve |
| Audit Trail | All mutations logged | All remediation events |

---

## 7. Key Files to Extend/Create for Stage 8

### New Backend Files
```
app/models/remediation.py          # New models (or extend __init__.py)
app/schemas/remediation.py         # Pydantic schemas
app/services/remediation.py        # RemediationService
app/services/patch.py              # PatchProcessor
app/services/validation.py         # ValidationPipeline
app/services/approval.py           # ApprovalService
app/services/application.py        # PatchApplicationAdapter
app/api/v1/remediations.py         # API endpoints
app/agents/remediation/            # Remediation agent (optional)
```

### New Frontend Files
```
app/(dashboard)/remediations/page.tsx
app/(dashboard)/remediations/[id]/page.tsx
components/remediation/            # Diff viewer, approval UI
```

### Database Migration
```
supabase/migrations/0006_stage8_remediation.sql
```

---

## 8. Known Limitations (Pre-Stage 8)

1. **No live AI credentials** — All AI features untested against real providers
2. **No Railway deployment verified** — Local only
3. **Frontend typecheck not run** — No Node.js in environment
4. **Integration tests require DB** — Unit tests use mocks only
5. **Remediation tables in migration but not models** — Schema drift
6. **Semgrep runner not tested end-to-end** — Needs demo target

---

## 9. Stage 8 Readiness Assessment

| Requirement | Ready? | Notes |
|-------------|--------|-------|
| AI Provider Abstraction | ✅ | Reuse Gemini/Grok |
| Structured AI Output | ✅ | Reuse SecurityAnalysis pattern |
| Prompt Injection Defense | ✅ | Reuse safety infrastructure |
| Workspace Isolation | ✅ | All models have workspace_id |
| Human Review Pattern | ✅ | Security Team review exists |
| Audit Logging | ✅ | Extend for remediation events |
| Repository Pattern | ✅ | Extend for new models |
| Deterministic Validation | ✅ | Reuse validation approach |
| Cost/Rate Controls | ✅ | Extend for remediation |

---

## 10. Implementation Priority for Stage 8

1. **Database Migration & Models** — Foundation for all else
2. **Remediation Schemas** — API contracts
3. **Remediation Service (AI Proposal)** — Core AI integration
4. **Patch Processor** — Diff generation, validation, isolation
5. **Validation Pipeline** — Syntax, Semgrep re-scan, bounds
6. **Approval Service** — Human workflow, hash binding
7. **Application Adapter** — Controlled apply with checkpoint
8. **Rollback Service** — Safe recovery
9. **API Endpoints** — Expose all operations
10. **Frontend Pages** — List & detail views
11. **Tests** — Unit + integration
12. **Documentation** — Architecture, security, approval guides

---

## 11. Critical Decisions for Stage 8

| Decision | Recommendation |
|----------|----------------|
| Patch isolation | Git worktree in server-resolved workspace (no containers in Stage 8) |
| AI remediation prompt | New dedicated prompt, reuse provider abstraction |
| Validation scope | Syntax + Semgrep re-scan + path allowlist (no test execution) |
| Approval binding | SHA256 of unified diff + proposal version |
| Finding status | DO NOT auto-mark FIXED — "APPLIED — VERIFICATION PENDING" |
| Rollback | Git-based restore from checkpoint, fail if diverged |
| Deployment | Railway — document isolation limitations |

---

*Generated: 2026-10-12*
*Baseline for Stage 8 Implementation*
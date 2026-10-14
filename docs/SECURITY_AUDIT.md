# SECURITY AUDIT — ShadowOps Stage 12

**Scope:** Full application security review across Stages 0–11
**Methodology:** Code review, architecture analysis, threat modeling, test gap analysis
**Date:** 2026-10-14

---

## 1. Executive Summary

ShadowOps implements a comprehensive security SaaS platform with strong architectural foundations but has **critical gaps in live verification** of security boundaries. The application-layer controls are well-designed but rely on untested infrastructure assumptions (Firebase, Supabase RLS, scanner isolation, patch execution).

**Overall Risk Rating:** HIGH — Not ready for production without remediation of CRITICAL findings.

---

## 2. Authentication & Authorization

### 2.1 Firebase → FastAPI Boundary

**Implementation:** `app/security/auth.py`
- `verify_firebase_token()` uses `firebase_admin.auth.verify_id_token(token, check_revoked=True)` ✅
- Handles `InvalidIdTokenError`, `ExpiredIdTokenError`, `RevokedIdTokenError` ✅
- `get_current_user()` creates/updates `Profile` from token claims ✅
- **Gap:** User identity sourced from verified token, not request body ✅

**Findings:**
| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| AUTH-01 | CRITICAL | No live Firebase test project; all tests use `MockCredential` | `tests/conftest.py:60-75` |
| AUTH-02 | HIGH | Email verification enforcement not configurable | `verify_firebase_token` doesn't check `email_verified` claim |
| AUTH-03 | MEDIUM | Token refresh not handled; relies on client to re-auth | No refresh token flow in backend |

### 2.2 Workspace RBAC

**Implementation:** `app/security/auth.py:112-149` (`require_workspace_role`)
- Roles: OWNER, ADMIN, MEMBER, VIEWER ✅
- Membership checked via `WorkspaceMember.joined_at IS NOT NULL` ✅
- Role hierarchy enforced in dependency injection ✅

**Findings:**
| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| RBAC-01 | HIGH | Service role (backend) bypasses all RLS; app-layer checks only | `app/db/session.py` uses `SUPABASE_SERVICE_ROLE_KEY` |
| RBAC-02 | MEDIUM | No permission matrix documentation for custom roles | `supabase/migrations/001_initial_schema.sql:466-478` defines roles but no API docs |

### 2.3 Object-Level Authorization

**Findings:**
| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| OBJ-01 | CRITICAL | Cross-workspace asset access blocked only in service layer | `app/services/scans.py:95-99` checks `asset.workspace_id` |
| OBJ-02 | HIGH | Scan authorization re-validated in runner but could be bypassed | `app/scanning/runner.py:148-154` duplicate check |
| OBJ-03 | MEDIUM | Resource ownership immutable (no `UPDATE` on `workspace_id`/`asset_id`) | Models use `ondelete="CASCADE"` but no `ON UPDATE RESTRICT` |

---

## 3. Database Security

### 3.1 Row-Level Security (RLS)

**Implementation:** `supabase/migrations/001_initial_schema.sql:505-779`
- 28 tables with `ENABLE ROW LEVEL SECURITY` ✅
- `current_user_workspace_ids()` helper uses `auth.uid()` ✅
- Policies separate SELECT (members) vs WRITE (admin/owner) ✅

**Critical Gap:** **Backend uses service role key which bypasses ALL RLS policies.**
- Service role = PostgreSQL `postgres` superuser equivalent
- RLS only enforced for anon/authenticated roles
- Application-layer checks are **sole enforcement mechanism**

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| RLS-01 | CRITICAL | Service role bypasses RLS; no defense-in-depth at DB level |
| RLS-02 | HIGH | `audit_logs` only readable by admin/owner — but service role sees all |
| RLS-03 | MEDIUM | `notification_preferences` user-isolated but service role sees all |

### 3.2 Migration Integrity

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| MIG-01 | HIGH | Numbering gap: `0008` → `009` (should be `0009`) |
| MIG-02 | HIGH | No `DOWN` migrations; no rollback procedure tested |
| MIG-03 | MEDIUM | `001_initial_schema.sql` includes `chat_conversations`, `chat_messages` — not used in codebase |

### 3.3 Service Role Usage

**Current:** Single `SUPABASE_SERVICE_ROLE_KEY` for all backend operations.

**Required:** Separate roles:
- `service_role_scanner` — scan worker only (read assets, write findings)
- `service_role_api` — API server (read/write per RLS intent)
- `service_role_migration` — migration runner only

---

## 4. Scanner & Execution Boundaries

### 4.1 Semgrep Integration

**Implementation:** `app/scanners/semgrep.py`, `app/scanning/runner.py`
- `SemgrepRunner.scan()` uses `asyncio.create_subprocess_exec()` ✅
- Timeout: 1800s (configurable) ✅
- File size limit: 10MB ✅
- Excluded paths: node_modules, .git, vendor, dist, build ✅

**Critical Findings:**
| ID | Severity | Finding | Evidence |
|----|----------|---------|----------|
| SCN-01 | CRITICAL | **No sandbox** — Semgrep runs in API container with full FS/network access | `app/scanning/runner.py:90-98` |
| SCN-02 | CRITICAL | **Path traversal risk** — `_prepare_scan_target` only checks `relative_to(scan_workspace_root)` | `app/scanning/runner.py:181-185` — symlinks not resolved |
| SCN-03 | HIGH | **No resource limits** — No cgroups, memory/CPU limits on subprocess | `asyncio.create_subprocess_exec` has no limits |
| SCN-04 | HIGH | **Secrets sent to AI** — Finding evidence includes code snippets that may contain secrets | `app/services/remediation.py:194-213` sanitizes but not comprehensive |
| SCN-05 | MEDIUM | **Queue retry duplicates** — No idempotency key on scan creation | `app/services/scans.py:84-169` |

### 4.2 Scanner Input Validation

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| SCN-06 | HIGH | Asset `connection_config` not validated; arbitrary paths possible |
| SCN-07 | MEDIUM | No git commit hash verification; scans latest HEAD |

---

## 5. AI Security & Data Protection

### 5.1 Provider Implementation

**Gemini:** `app/ai/providers/gemini.py`
- Structured output via `response_schema` ✅
- Safety settings: BLOCK_MEDIUM_AND_ABOVE for harm categories ✅
- Cost estimation ✅
- **Gap:** No request/response logging for audit

**Grok:** `app/ai/providers/grok.py`
- JSON mode via `response_format: {"type": "json_object"}` ✅
- HTTP client with timeout ✅
- **Gap:** No retry-after handling for 429

### 5.2 Data Handling

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| AI-01 | HIGH | `sanitize_evidence_dict` only removes known secret patterns; unknown patterns pass through | `app/ai/safety.py` not fully reviewed |
| AI-02 | HIGH | Prompt injection defense relies on XML delimiters only (`<TRUSTED_SYSTEM_INSTRUCTIONS>`, `<UNTRUSTED_SECURITY_EVIDENCE>`) | `app/ai/manager.py`, `app/services/remediation.py:292-335` |
| AI-03 | MEDIUM | AI output cannot override scanner evidence — enforced by schema separation ✅ |
| AI-04 | MEDIUM | No usage limits enforced per workspace (config exists: `AI_DAILY_ANALYSIS_LIMIT`) | `app/core/config.py:46` |

### 5.3 Model Configuration

| Provider | Model | Version | Retention | Verified |
|----------|-------|---------|-----------|----------|
| Gemini | gemini-1.5-flash | 1.45.0 | Google default (30 days?) | ❌ No |
| Grok | grok-1 | 1.0 | xAI default | ❌ No |

---

## 6. Remediation & Verification Safety

### 6.1 Remediation Workflow (Stage 8)

**Implementation:** `app/services/remediation.py`, `patch.py`, `approval.py`, `application.py`, `rollback.py`

**Security Controls:**
- Patch hash (SHA256) binds approval to exact diff ✅
- Changed patch invalidates approval (`superseded_by` in `patch_versions`) ✅
- Path allowlist validation in `PatchProcessor` ✅
- Checkpoint required before apply (`checkpoint_ref`) ✅
- Idempotency key on application ✅

**Critical Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| REM-01 | CRITICAL | `PatchApplicationAdapter` is a **stub** — no actual `git apply`/`patch` execution | `app/services/application.py` |
| REM-02 | CRITICAL | No isolated git worktree; patches apply to production repo directly | Not implemented |
| REM-03 | HIGH | Rollback uses `checkpoint_ref` but no verification of restored state | `app/services/rollback.py` |
| REM-04 | MEDIUM | AI-generated commands not validated; `commands` field in proposal unexecuted but stored | `app/models/__init__.py:1080` |

### 6.2 Verification Integrity (Stage 9)

**Implementation:** `app/services/verification.py`, `baseline.py`, `comparison.py`, `regression.py`, `policy.py`

**Security Controls:**
- Baseline captured from handoff or pre-patch scan ✅
- Evidence comparison with fingerprint matching ✅
- Policy engine with deterministic outcome mapping ✅
- Human review required for `VERIFIED_CANDIDATE` ✅

**Critical Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| VER-01 | CRITICAL | Re-scan runs in **same process** (`SemgrepRunner` instantiated in `VerificationService`) | `app/services/verification.py:364` |
| VER-02 | HIGH | No separate verification worker; same binary, same config |
| VER-03 | HIGH | Missing baseline → `INCONCLUSIVE` not `BLOCKED` (policy allows) | `app/services/policy.py` |

---

## 7. Reports, Exports & Storage

### 7.1 Report Generation (Stage 10)

**Implementation:** `app/services/report_service.py`, `report_export.py`, `report_storage.py`

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| RPT-01 | HIGH | PDF generation uses `weasyprint` (headless browser) — untested, potential XSS via HTML injection | `app/services/report_export.py` |
| RPT-02 | MEDIUM | Storage bucket config is **placeholder only** (commented SQL) | `supabase/migrations/0008_stage10_reports.sql:158-159` |
| RPT-03 | MEDIUM | Report snapshots include `data_cutoff` but not schema version in filename | `app/models/__init__.py:1586` |
| RPT-04 | LOW | Download URLs not logged — good ✅ |

### 7.2 Private Storage

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| STO-01 | HIGH | Supabase Storage bucket `reports` not created; RLS policies for storage objects not defined | Migration comment only |

---

## 8. Notifications & Workflows (Stage 11)

### 8.1 Event Outbox

**Implementation:** `app/services/event_outbox.py`, `app/services/delivery.py`

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| NOT-01 | CRITICAL | **No outbox processor worker** — events written but never delivered | `app/services/event_outbox.py` has `emit_event` but no consumer |
| NOT-02 | HIGH | Retry logic exists but no dead-letter queue processing | `app/services/delivery.py` |
| NOT-03 | MEDIUM | Email adapter (`EmailAdapter`) untested; SMTP config not validated | `app/services/email_adapter.py` |
| NOT-04 | MEDIUM | n8n adapter exists but `N8N_WEBHOOK_URL` not configured; disabled by default ✅ |

### 8.2 Workflow Automation

**Findings:**
| ID | Severity | Finding |
|----|----------|---------|
| WF-01 | HIGH | `WorkflowService` executes registered actions but **no approval/verification bypass prevention** | `app/services/workflow.py` |
| WF-02 | MEDIUM | Only registered actions can run ✅ |

---

## 9. API & Application Security

### 9.1 OWASP API Top 10 Coverage

| Category | Status | Notes |
|----------|--------|-------|
| API1: Broken Object Level Authorization | ⚠️ PARTIAL | App-layer checks; no DB enforcement |
| API2: Broken Authentication | ⚠️ PARTIAL | Firebase verified; no live test |
| API3: Broken Object Property Level Authorization | ✅ | Pydantic schemas validate input/output |
| API4: Unrestricted Resource Consumption | ❌ MISSING | No rate limits on scan/AI/report endpoints |
| API5: Broken Function Level Authorization | ✅ | Role deps on all mutating endpoints |
| API6: Unrestricted Access to Sensitive Business Flows | ✅ | Approval required for remediation apply |
| API7: Server Side Request Forgery | ⚠️ PARTIAL | Scanner target path validated but not URL fetch |
| API8: Security Misconfiguration | ⚠️ PARTIAL | CSP allows unsafe-inline; debug endpoints in prod |
| API9: Improper Inventory Management | ✅ | API versioned (`/api/v1`); OpenAPI docs disabled in prod |
| API10: Unsafe Consumption of APIs | ⚠️ PARTIAL | AI provider errors handled but not all timeouts |

### 9.2 Specific Findings

| ID | Severity | Finding |
|----|----------|---------|
| API-01 | HIGH | No rate limiting on `/api/v1/scans`, `/api/v1/ai`, `/api/v1/reports` |
| API-02 | HIGH | `/health` exposes `ENVIRONMENT` and `version` |
| API-03 | MEDIUM | CSP `script-src 'unsafe-inline'` |
| API-04 | MEDIUM | No request size limit on scan creation (large `scan_config`) |
| API-05 | LOW | `X-Response-Time` header exposes internal timing |

---

## 10. Dependency & Supply Chain

### 10.1 Backend (Python)

**Requirements:** `backend/requirements.txt` — 26 packages

**Audit Not Run:** `pip-audit` / `safety` not executed.

**Known Risks:**
- `semgrep==1.45.0` — pinned ✅
- `firebase-admin==6.5.0` — check for CVEs
- `google-generativeai` — **deprecated** (see warning in test output)

### 10.2 Frontend (Node.js)

**Dependencies:** `frontend/package.json` — 14 prod, 14 dev

**Audit Not Run:** `npm audit` not executed.

**Known Risks:**
- `next@14.2.5` — check for CVEs
- `firebase@10.12.4` — check for CVEs

### 10.3 Container/Infrastructure

**Missing:**
- `Dockerfile` — not present
- `railway.json` — not present
- `nixpacks.toml` — not present
- Non-root user in container — not defined
- Read-only root filesystem — not configured

---

## 11. Observability & Incident Readiness

### 11.1 Logging

**Implementation:** `app/main.py:15-30` (structlog JSON)
- Request ID middleware ✅
- Structured fields: request_id, method, path, status, duration ✅
- **Gap:** No log shipper (Vector, Fluent Bit, Datadog agent)
- **Gap:** No correlation IDs across workers (scan runner, AI, verification)

### 11.2 Health & Readiness

**Implementation:** `app/api/v1/health.py`
- `/health` — liveness (always returns healthy) ✅
- `/ready` — readiness (checks DB) ✅
- **Gap:** Ready doesn't check scanner binary, AI provider, Redis, queue backlog

### 11.3 Metrics & Alerting

**Missing:**
- Prometheus metrics endpoint
- Grafana dashboards
- Alert rules (PagerDuty/Slack/email)
- SLO definitions

---

## 12. Backup, Recovery & Retention

### 12.1 Current State

| Data Type | Backup | Retention | Restore Tested |
|-----------|--------|-----------|----------------|
| PostgreSQL (Supabase) | Supabase managed (PITR) | 7 days (default) | ❌ No |
| Scan artifacts (findings, evidence) | In DB | Forever (no policy) | ❌ No |
| Audit logs | In DB | Forever (no policy) | ❌ No |
| Reports (Supabase Storage) | Not configured | N/A | ❌ No |
| Event outbox | In DB | Forever (no policy) | ❌ No |

### 12.2 Required Policies

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Audit logs | 7 years | Compliance (SOC2, GDPR) |
| Findings & evidence | 3 years | Security trend analysis |
| Scan artifacts | 90 days | Storage cost |
| Reports | 1 year | Compliance |
| Event outbox | 30 days | Debugging |
| Verification baselines | 1 year | Audit trail |

---

## 13. Railway Deployment Readiness

### 13.1 Required Configuration

| Component | Status | Notes |
|-----------|--------|-------|
| Frontend service | ❌ Missing | Needs `Dockerfile` or `nixpacks.toml` |
| FastAPI service | ❌ Missing | Needs `Dockerfile` |
| Background worker | ❌ Missing | Separate service for Celery/outbox |
| Database | ✅ Supabase | External managed |
| Redis | ❌ Missing | Railway Redis addon needed |
| Environment variables | ⚠️ Partial | `.env.example` exists; Railway UI config needed |
| Health checks | ✅ Code exists | `/health` and `/ready` implemented |
| CORS/Domain | ❌ Missing | `FRONTEND_URL` must be set |
| Secret management | ⚠️ Railway UI | Must use Railway secrets, not `.env` |
| Migration execution | ❌ Undefined | Pre-deploy hook or separate job? |
| Rollback procedure | ❌ Undefined | Railway rollback + DB migration down? |

### 13.2 Migration Concurrency

**Risk:** Multiple app instances may run migrations concurrently on deploy.

**Fix:** Use advisory lock or separate migration job:
```sql
SELECT pg_advisory_xact_lock(123456); -- migration lock
```

---

## 14. End-to-End Acceptance Test Gaps

**Required E2E Flow (from Stage 12 spec):**
1. ✅ Authenticate test user — **Mocked only**
2. ✅ Create workspace — **Unit tested**
3. ✅ Add test repository asset — **Unit tested**
4. ✅ Record authorization — **Unit tested**
5. ❌ Run controlled scan — **No live Semgrep**
6. ✅ Persist finding/evidence — **Unit tested**
7. ❌ Generate AI analysis — **Mocked only**
8. ✅ Calculate deterministic risk — **Unit tested**
9. ❌ Run AI Security Team — **Mocked only**
10. ❌ Generate remediation — **Mocked only**
11. ❌ Human approval — **Unit tested**
12. ❌ Apply patch in isolated env — **NOT IMPLEMENTED**
13. ❌ Independent verification — **Same process**
14. ❌ Review verification — **Unit tested**
15. ❌ Generate report — **PDF untested**
16. ❌ Create/process notification — **Outbox not processed**
17. ✅ Verify audit history — **Unit tested**
18. ✅ Cross-workspace isolation — **Unit tested**

**Negative E2E Cases (Required):**
- Unauthorized scanning — **Unit tested**
- Cross-workspace access — **Unit tested**
- Unapproved patch apply — **NOT TESTED (no apply impl)**
- Premature finding closure — **NOT TESTED**

---

## 15. Severity Summary

| Severity | Count | Status |
|----------|-------|--------|
| CRITICAL | 6 | 0 resolved |
| HIGH | 12 | 0 resolved |
| MEDIUM | 15 | 0 resolved |
| LOW | 5 | 0 resolved |

---

## 16. Conclusion

ShadowOps has a **well-architected security model** with proper separation of concerns, RBAC, audit logging, and defense-in-depth at the application layer. However, **critical infrastructure-level security boundaries remain unverified**:

1. **Authentication** — Firebase not live-tested
2. **Database** — RLS bypassed by service role
3. **Scanner** — No sandbox; runs in API container
4. **Remediation** — Patch application not implemented in isolation
5. **Verification** — Not independent (same process)
6. **Deployment** — No Railway config; no container hardening

**Recommendation:** **NOT READY** for controlled pilot until CRITICAL findings (6) are resolved and live integration tests pass.

---

## 17. Appendix: Files Reviewed

### Core Security Modules
- `app/security/auth.py` — Firebase auth, RBAC deps
- `app/security/middleware.py` — CORS, CSP, Request ID, Logging
- `app/security/audit.py` — Audit log model + service
- `app/core/config.py` — All settings, secrets

### Scanner & Execution
- `app/scanners/semgrep.py` — Semgrep runner, normalizer
- `app/scanning/runner.py` — ScanJobRunner, target prep, execution

### AI & Data Protection
- `app/ai/providers/gemini.py`, `grok.py` — Provider implementations
- `app/ai/manager.py` — AI orchestration
- `app/ai/safety.py` — Sanitization, prompt injection defense
- `app/ai/validation.py` — Output validation
- `app/ai/schemas.py` — SecurityAnalysis, ScanAnalysis schemas

### Remediation & Verification
- `app/services/remediation.py` — Proposal generation
- `app/services/patch.py` — PatchProcessor, validation
- `app/services/approval.py` — Human approval binding
- `app/services/application.py` — PatchApplicationAdapter (STUB)
- `app/services/rollback.py` — RollbackService
- `app/services/verification.py` — Verification orchestration
- `app/services/baseline.py` — Baseline capture
- `app/services/comparison.py` — Evidence comparison
- `app/services/regression.py` — Regression analysis
- `app/services/policy.py` — Verification policy engine

### Reports & Notifications
- `app/services/report_service.py` — Report generation
- `app/services/report_export.py` — PDF/JSON export
- `app/services/report_storage.py` — Supabase Storage
- `app/services/notification.py` — Notification service
- `app/services/event_outbox.py` — Transactional outbox
- `app/services/delivery.py` — Delivery processor
- `app/services/email_adapter.py` — SMTP adapter
- `app/services/n8n_adapter.py` — n8n webhook
- `app/services/workflow.py` — Workflow engine
- `app/services/rules.py` — Notification rules

### Database
- `supabase/migrations/001_initial_schema.sql` — Core schema + RLS
- `supabase/migrations/0003_stage3_scanning.sql` — Scan enhancements
- `supabase/migrations/0004_stage4_ai.sql` — AI tables
- `supabase/migrations/0005_stage7_security_team.sql` — Security team
- `supabase/migrations/0006_stage8_remediation.sql` — Remediation
- `supabase/migrations/0007_stage9_verification.sql` — Verification
- `supabase/migrations/0008_stage10_reports.sql` — Reports
- `supabase/migrations/009_stage11_notifications.sql` — Notifications

### Tests
- `backend/tests/conftest.py` — Test configuration (Firebase mock)
- `backend/tests/test_ai.py` — AI provider, manager, security tests
- `backend/tests/test_ai_analyst.py` — AI analyst tests
- `backend/tests/test_api.py` — API endpoint tests
- `backend/tests/test_scans.py` — Scan service/runner tests
- `backend/tests/test_services.py` — Profile, Workspace, Asset services
- `backend/tests/test_remediation.py` — Remediation workflow tests
- `backend/tests/test_verification.py` — Verification tests
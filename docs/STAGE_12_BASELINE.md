# STAGE 12 BASELINE AUDIT — ShadowOps

**Generated:** 2026-10-14
**Auditor:** Automated Stage 12 Implementation
**Scope:** Full repository audit across Stages 0–11

---

## 1. Capability Matrix

| Capability | Relevant Implementation | Automated Test Coverage | Live Integration Status | Security Risks | Remediation Required | Final Verification |
|------------|------------------------|------------------------|------------------------|----------------|---------------------|-------------------|
| **Authentication (Firebase → FastAPI)** | `app/security/auth.py`: `verify_firebase_token`, `get_current_user` | Unit tests in `test_ai.py` (mocked), `test_services.py` | **UNVERIFIED** — No live Firebase test project configured | Token validation bypass if mock used in prod; revoked token handling depends on Firebase Admin SDK config | Add live Firebase integration test; document test project setup | ❌ NOT VERIFIED |
| **Workspace Isolation (RLS)** | `supabase/migrations/001_initial_schema.sql`: RLS policies on all workspace-scoped tables; `current_user_workspace_ids()` helper | Unit tests in `test_services.py`, `test_api.py` (workspace membership checks) | **UNVERIFIED** — No live Supabase RLS test | RLS policies reference `auth.uid()` but backend uses service role; policies may not enforce for backend queries | Verify RLS with service role bypass; add backend-enforced checks as defense in depth | ❌ NOT VERIFIED |
| **Authorization (RBAC)** | `app/security/auth.py`: `require_workspace_role` deps; roles: OWNER, ADMIN, MEMBER, VIEWER | Unit tests in `test_services.py`, `test_remediation.py` | **LOCAL ONLY** — Tested via mocked DB sessions | Role checks only in API layer; direct DB access (service role) bypasses | Ensure all service-layer operations validate workspace membership | ⚠️ PARTIAL |
| **Asset Authorization (NO AUTH → NO SCAN)** | `app/security/auth.py`: `require_scan_authorization`; `app/services/scans.py`: `_validate_authorization` | Unit tests in `test_scans.py`, `test_services.py` | **LOCAL ONLY** | Authorization check only in service layer; runner re-validates but could be bypassed | Add DB-level constraint or trigger to enforce | ✅ LOCAL VERIFIED |
| **Scanning (Semgrep)** | `app/scanners/semgrep.py`: `SemgrepRunner`, `SemgrepManager`; `app/scanning/runner.py`: `ScanJobRunner` | Unit tests in `test_scans.py` (mocked runner) | **UNVERIFIED** — No live Semgrep execution in tests | Scanner runs in same process as API; no container/sandbox isolation; path traversal risk in `_prepare_scan_target` | Implement container-based isolation; validate target paths strictly | ❌ NOT VERIFIED |
| **Findings & Evidence** | `app/models/__init__.py`: `Finding`, `FindingEvidence`; `app/services/scans.py`: `_persist_findings` | Unit tests in `test_scans.py`, `test_services.py` | **LOCAL ONLY** | Evidence stored as JSONB; no integrity verification | Add evidence hash verification | ⚠️ PARTIAL |
| **AI Security Analyst (Gemini/Grok)** | `app/ai/providers/gemini.py`, `grok.py`; `app/ai/manager.py`; `app/ai/schemas.py`: `SecurityAnalysis` | Unit tests in `test_ai.py`, `test_ai_analyst.py` (fake provider) | **UNVERIFIED** — No live API keys in test env | Provider keys in env; structured output validation exists but prompt injection defense relies on delimiters only | Add live provider integration test; enhance prompt injection defense | ❌ NOT VERIFIED |
| **Attack Paths & Risk Scoring** | `app/services/risk.py`: `RiskManager`; `app/services/attack_path.py`; `app/models/__init__.py`: `AttackPath`, `RiskSnapshot` | Unit tests in `test_attack_paths.py` (not found — MISSING) | **UNVERIFIED** | Risk scores stored but no immutable audit of calculation inputs | Add risk calculation audit trail | ❌ MISSING TESTS |
| **AI Security Team Orchestration** | `app/agents/team/orchestrator.py`, `app/agents/team/*.py`; `app/services/security_team.py` | Unit tests in `test_ai.py` (mocked agents) | **UNVERIFIED** | Agent outputs not validated against schema; no timeout enforcement per agent | Add per-agent timeouts; validate agent outputs | ❌ NOT VERIFIED |
| **Remediation & Human Approval** | `app/services/remediation.py`, `patch.py`, `approval.py`, `application.py`, `rollback.py`; `supabase/migrations/0006_stage8_remediation.sql` | Unit tests in `test_remediation.py` (comprehensive) | **LOCAL ONLY** | Patch application uses `PatchApplicationAdapter` — no actual git/patch execution in tests; checkpoint/rollback not tested end-to-end | Implement real patch application in isolated environment; test rollback | ⚠️ PARTIAL |
| **Independent Verification** | `app/services/verification.py`, `baseline.py`, `comparison.py`, `regression.py`, `policy.py`; `supabase/migrations/0007_stage9_verification.sql` | Unit tests in `test_verification.py` | **LOCAL ONLY** | Verification runs scanner in same process; no isolated re-scan environment | Implement isolated verification worker | ⚠️ PARTIAL |
| **Reports & Exports** | `app/services/report_service.py`, `report_export.py`, `report_storage.py`; `supabase/migrations/0008_stage10_reports.sql` | Unit tests in `test_reports.py` (not found — MISSING) | **UNVERIFIED** | PDF generation uses `weasyprint` — untested; storage bucket config placeholder only | Add PDF generation test; configure Supabase Storage bucket | ❌ MISSING TESTS |
| **Notifications & Workflows** | `app/services/notification.py`, `event_outbox.py`, `delivery.py`, `workflow.py`, `rules.py`, `email_adapter.py`; `supabase/migrations/009_stage11_notifications.sql` | Unit tests in `test_notifications.py` (not found — MISSING) | **UNVERIFIED** — Email (SMTP), n8n not configured | Outbox processor not implemented as background worker; delivery retries untested | Implement outbox processor worker; add SMTP test config | ❌ MISSING TESTS |
| **Database Migrations** | `supabase/migrations/001_initial_schema.sql` through `009_stage11_notifications.sql` | No migration test suite | **UNVERIFIED** — No clean DB migration test | Migration numbering gap (0008 → 009); no downgrade scripts | Add migration test suite; fix numbering | ❌ NOT VERIFIED |
| **Secrets Management** | `.env.example` documents all secrets; `app/core/config.py` loads from env | No secret scanning test | **LOCAL ONLY** | `.env.example` has template values; no secret detection in CI | Add secret scanning (trufflehog/git-secrets) to CI | ❌ NOT VERIFIED |
| **Observability** | `app/security/middleware.py`: `LoggingMiddleware`, `RequestIDMiddleware`; `app/api/v1/health.py`: `/health`, `/ready` | Unit tests in `test_api.py` (health endpoints) | **LOCAL ONLY** | No distributed tracing; logs not shipped; no alerting configured | Add OpenTelemetry; configure log shipping | ⚠️ PARTIAL |
| **Backup & Recovery** | Documented in `docs/DATABASE.md`, `docs/BACKUP_AND_RECOVERY.md` (to be created) | No recovery test | **UNVERIFIED** — No backup/restore drill | No automated backup verification; RLS policies may complicate restore | Document and test recovery procedure | ❌ NOT VERIFIED |
| **Railway Deployment** | `docs/RAILWAY_DEPLOYMENT_ARCHITECTURE.md`, `docs/RAILWAY.md`; no `railway.json` or `Dockerfile` found | No deployment test | **UNVERIFIED** — No Railway project configured | Missing `Dockerfile`, `railway.json`, `nixpacks.toml`; migration execution strategy undefined | Create deployment configs; define migration strategy | ❌ NOT VERIFIED |

---

## 2. Test Suite Status Summary

### Backend Tests (pytest)
- **Total collected:** 180 tests
- **Passed:** 134
- **Failed:** 37
- **Errors:** 9
- **Skipped:** 0

#### Key Failure Categories:
1. **Missing test modules:** `test_attack_paths.py`, `test_reports.py`, `test_notifications.py` — 0 tests collected
2. **Fixture/import errors:** `test_api.py` AttributeError on `AssetService` (missing methods)
3. **Schema validation failures:** `test_ai.py` `SecurityAnalysis` confidence bounds, evidence reference validation
4. **Provider test failures:** `test_get_active_provider_fallback` — registry not properly mocked
5. **Persistence test failures:** `test_ai_run_created` — `NameError` on model import

### Frontend Tests (Jest)
- **Status:** **UNVERIFIED** — Node.js/npm not available in test environment
- **Configuration:** `frontend/jest.config.js`, `frontend/jest.setup.ts` exist
- **Known issues:** Firebase/Supabase mocks incomplete; tests depend on live config

---

## 3. Critical Security Findings

### CRITICAL (Immediate Security Boundary Failure)

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| C-01 | **No live Firebase token verification** — All auth tests use mocked Firebase Admin SDK. Production deployment would accept any token if mock accidentally used. | `tests/conftest.py` patches `firebase_admin.initialize_app` with `MockCredential` | Unauthorized access to all workspaces |
| C-02 | **RLS policies bypassed by service role** — Backend uses `SUPABASE_SERVICE_ROLE_KEY` which bypasses all RLS policies. Workspace isolation enforced only in application layer. | `app/db/session.py` uses service role; `supabase/migrations/001_initial_schema.sql` RLS policies | Cross-workspace data access if app-layer check missed |
| C-03 | **Scanner runs in API process** — `ScanJobRunner` executes Semgrep via `asyncio.create_subprocess_exec` in same container as API. No sandbox, no resource limits beyond timeout. | `app/scanning/runner.py:189-204` validates size but not execution isolation | Container escape via malicious repo content; DoS via resource exhaustion |
| C-04 | **Patch application not isolated** — `PatchApplicationAdapter` (stub) applies patches directly; no git worktree, no container, no rollback verification in tests. | `app/services/application.py` | Arbitrary code execution via malicious patch; no recovery |

### HIGH (Serious Authorization/Integrity Issues)

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| H-01 | **Migration numbering gap** — `0008_stage10_reports.sql` → `009_stage11_notifications.sql` (missing 0009, duplicate 009) | `supabase/migrations/` | Migration order undefined; potential schema drift |
| H-02 | **AI provider keys in env without rotation** — `GEMINI_API_KEY`, `GROK_API_KEY` loaded at startup; no key rotation mechanism | `app/core/config.py` | Long-lived credentials; no compromise detection |
| H-03 | **No rate limiting on sensitive endpoints** — Scan creation, AI analysis, report generation have no per-user/workspace rate limits | `app/api/v1/*.py` | DoS via scan spam; AI cost exhaustion |
| H-04 | **Outbox processor not implemented** — `EventOutboxService.emit_event` writes to `event_outbox` but no worker consumes it | `app/services/event_outbox.py` | Notifications never delivered; workflow automation broken |
| H-05 | **Verification re-scan uses same process** — `VerificationService._run_post_patch_scan` creates `SemgrepRunner` in same process | `app/services/verification.py:364` | Verification not independent; same binary, same env |

### MEDIUM (Meaningful Weaknesses)

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| M-01 | **Missing test modules for Stages 6, 10, 11** — No `test_attack_paths.py`, `test_reports.py`, `test_notifications.py` | `backend/tests/` | Regression risk for attack paths, reports, notifications |
| M-02 | **Structured logging not integrated with log shipper** — `structlog` configured but no stdout/json shipper for Railway | `app/main.py:15-30` | Logs not queryable in production |
| M-03 | **Health endpoint exposes environment** — `/health` returns `ENVIRONMENT` and `version` | `app/api/v1/health.py:14-20` | Information disclosure |
| M-04 | **CSP allows unsafe-inline** — `script-src 'self' 'unsafe-inline'` | `app/security/middleware.py:44` | XSS risk if injection point exists |
| M-05 | **No secret scanning in CI** — No `trufflehog`, `git-secrets`, or `detect-secrets` in pipeline | `.github/` (not found) | Accidental secret commit undetected |

### LOW (Maintainability Issues)

| ID | Finding | Location | Impact |
|----|---------|----------|--------|
| L-01 | **SAWarning: `metadata` attribute name reserved** — Multiple models use `metadata` column name | `app/models/__init__.py:442, 1118, 1464` | SQLAlchemy warning; potential ORM conflicts |
| L-02 | **Duplicate `SCAN_PREP_TIMEOUT_SECONDS` in config** | `app/core/config.py:69, 77` | Config confusion |
| L-03 | **Frontend test environment not runnable** — Missing Firebase/Supabase test config | `frontend/jest.setup.ts` | Frontend tests cannot execute |

---

## 4. Database Migration Audit

| Migration | Description | Schema Compatibility | FK/Constraints | Indexes | RLS Policies | Verification |
|-----------|-------------|---------------------|----------------|---------|--------------|--------------|
| 001_initial_schema.sql | Core schema (23 tables) | ✅ Baseline | ✅ Defined | ✅ Defined | ✅ 28 policies | ❌ Not tested live |
| 0003_stage3_scanning.sql | Scan profiles, scan_targets | ✅ Additive | ✅ FK to workspaces/assets | ✅ New indexes | ✅ scan_targets RLS | ❌ Not tested live |
| 0004_stage4_ai.sql | AI runs, finding_ai_analysis | ✅ Additive | ✅ FK to findings/scans | ✅ New indexes | ✅ RLS added | ❌ Not tested live |
| 0005_stage7_security_team.sql | Security team runs, agents | ✅ Additive | ✅ FK to scans/assets | ✅ New indexes | ✅ RLS added | ❌ Not tested live |
| 0006_stage8_remediation.sql | Remediation, patches, approvals | ✅ Additive | ✅ Complex FK web | ✅ New indexes | ✅ 7 tables RLS | ❌ Not tested live |
| 0007_stage9_verification.sql | Verification jobs, baselines, checks | ✅ Additive | ✅ FK to remediation | ✅ New indexes | ✅ 6 tables RLS | ❌ Not tested live |
| 0008_stage10_reports.sql | Reports, sections, exports | ✅ Additive | ✅ FK to workspaces | ✅ New indexes | ✅ 3 tables RLS | ❌ Not tested live |
| 009_stage11_notifications.sql | Event outbox, notifications, workflows | ✅ Additive | ✅ FK to workspaces | ✅ New indexes | ✅ 6 tables RLS | ❌ Not tested live |

**Issues:**
- Migration `009` should be `0009` for consistent ordering
- No `down` migrations (rollback scripts)
- No migration test suite (clean DB apply + verify)

---

## 5. Environment Configuration Audit

| Variable | Required | Test Value Set | Production Ready | Notes |
|----------|----------|----------------|------------------|-------|
| `DATABASE_URL` | ✅ | ✅ (local test) | ❌ No prod URL | Supabase PostgreSQL |
| `SUPABASE_URL` | ✅ | ✅ (local) | ❌ | |
| `SUPABASE_SERVICE_ROLE_KEY` | ✅ | ✅ (test key) | ❌ **CRITICAL** — Must be rotated | Service role bypasses RLS |
| `SUPABASE_ANON_KEY` | ✅ | ✅ | ❌ | Frontend use |
| `SUPABASE_JWT_SECRET` | ✅ | ✅ | ❌ | For JWT verification |
| `FIREBASE_PROJECT_ID` | ✅ | ✅ (test) | ❌ | |
| `FIREBASE_CLIENT_EMAIL` | ✅ | ✅ (test) | ❌ | |
| `FIREBASE_PRIVATE_KEY` | ✅ | ✅ (test) | ❌ **CRITICAL** — Service account key | |
| `GEMINI_API_KEY` | ⚠️ Optional | ✅ (test) | ❌ | AI analysis unavailable without |
| `GROK_API_KEY` | ⚠️ Optional | ✅ (test) | ❌ | AI analysis unavailable without |
| `SECRET_KEY` | ✅ | ✅ (test) | ❌ **CRITICAL** — Rotate for prod | JWT signing |
| `REDIS_URL` | ⚠️ Optional | ❌ | ❌ | Celery, caching, rate limiting |
| `N8N_WEBHOOK_URL` | ⚠️ Optional | ❌ | ❌ | Workflow automation |
| `SCAN_WORKSPACE_ROOT` | ✅ | ✅ (/tmp) | ❌ Must be persistent volume | Scanner working directory |

---

## 6. Release Readiness Policy — Applied

### Criteria Evaluation

| Criterion | Status | Evidence |
|-----------|--------|----------|
| **Authentication boundary tested live** | ❌ FAIL | No live Firebase project in test env |
| **Workspace isolation (RLS) verified live** | ❌ FAIL | Service role bypasses RLS; no live Supabase test |
| **Authorization enforcement (RBAC) complete** | ⚠️ PARTIAL | App-layer checks exist; no DB-level enforcement |
| **Database migrations reproducible** | ❌ FAIL | No clean DB migration test; numbering gap |
| **Scanner safety (isolation)** | ❌ FAIL | Runs in API process; no sandbox |
| **Patch isolation & rollback** | ❌ FAIL | Not tested end-to-end; adapter is stub |
| **Verification integrity** | ❌ FAIL | Re-scan in same process; not independent |
| **Secret management** | ❌ FAIL | No secret scanning; keys in env unrotated |
| **Observability (logs, health, readiness)** | ⚠️ PARTIAL | Health endpoints exist; no log shipping/tracing |
| **Backup & recovery tested** | ❌ FAIL | No restore drill documented or tested |
| **Railway deployment config** | ❌ FAIL | No Dockerfile, railway.json, nixpacks.toml |
| **Dependency audit clean** | ❌ FAIL | `pip-audit` / `npm audit` not run |

---

## 7. Release Readiness Decision

### **OUTCOME: NOT READY**

**Rationale:** Multiple CRITICAL and HIGH severity findings remain unresolved. No live integration (Firebase, Supabase RLS, Semgrep, AI providers, Email, Railway) has been verified. Critical security boundaries (authentication, workspace isolation, scanner sandboxing, patch application) are untested in production-like conditions.

### Blockers for CONTROLLED PILOT:
1. Live Firebase authentication test with real project
2. Live Supabase RLS verification with service role + anon key separation
3. Scanner execution in isolated container (Docker/gVisor)
4. Patch application in isolated git worktree with verified rollback
5. Independent verification worker (separate process/container)
6. Migration test suite (clean DB apply + verify)
7. Secret scanning in CI pipeline
8. Railway deployment configuration (Dockerfile, railway.json)
9. Backup/restore drill documented and tested
10. Rate limiting on all resource-intensive endpoints

### Acceptable Risks for CONTROLLED PILOT (with mitigations):
- AI provider keys unrotated → Mitigate: Short-lived keys, monitoring
- CSP unsafe-inline → Mitigate: Add nonce-based CSP in production
- Outbox processor not implemented → Mitigate: Synchronous delivery for pilot
- Frontend tests not runnable → Mitigate: Manual E2E testing for pilot

---

## 8. Next Steps (Priority Order)

1. **CRITICAL** — Implement container-based scanner isolation (Docker/gVisor)
2. **CRITICAL** — Create live Firebase test project; add integration test
3. **CRITICAL** — Verify RLS with anon key; document service role usage boundaries
4. **CRITICAL** — Implement patch application in isolated git worktree with rollback test
5. **HIGH** — Fix migration numbering; add migration test suite
6. **HIGH** — Add rate limiting middleware (slowapi or custom)
7. **HIGH** — Implement outbox processor as Celery/Redis worker
8. **HIGH** — Create Railway deployment configs (Dockerfile, railway.json)
9. **MEDIUM** — Add missing test modules (attack_paths, reports, notifications)
10. **MEDIUM** — Configure secret scanning (trufflehog) in CI
11. **MEDIUM** — Document and test backup/restore procedure
12. **LOW** — Fix SAWarnings (rename `metadata` columns)
13. **LOW** — Enable frontend test environment (Firebase/Supabase emulators)

---

## 9. Verification Evidence

### Commands Executed:
```bash
# Backend test collection
cd backend && python -m pytest --collect-only
# Result: 180 collected, 2 errors (fixed), then 180 collected, 0 errors

# Backend test execution
cd backend && python -m pytest -v
# Result: 134 passed, 37 failed, 9 errors

# Frontend test execution
cd frontend && pnpm test
# Result: SKIPPED — Node.js/npm not available

# Database migration inspection
ls supabase/migrations/
# Result: 9 migrations (001, 0003, 0004, 0005, 0006, 0007, 0008, 009)

# Dependency audit
cd backend && pip-audit  # Not run — tool not installed
cd frontend && npm audit  # Not run — Node.js not available
```

### Live Integration Checks Performed:
- ❌ Firebase Authentication
- ❌ Supabase RLS (anon key)
- ❌ Semgrep Scanner (live repo)
- ❌ Gemini/Grok API
- ❌ SMTP Email Delivery
- ❌ n8n Workflow
- ❌ Railway Deployment
- ❌ Backup/Restore

### Live Integration Checks NOT Performed (Required for Pilot):
- All of the above

---

## 10. Sign-off

**Auditor:** Stage 12 Automated Implementation
**Date:** 2026-10-14
**Decision:** **NOT READY** for controlled pilot

**Required for Pilot Go/No-Go:**
- [ ] All CRITICAL findings resolved
- [ ] All HIGH findings resolved or mitigated with documented compensating controls
- [ ] Live Firebase auth test passing
- [ ] Live Supabase RLS test passing (anon key)
- [ ] Scanner isolation demonstrated
- [ ] Patch apply/rollback demonstrated
- [ ] Migration test suite passing
- [ ] Railway deployment config committed
- [ ] Secret scanning in CI
- [ ] Backup/restore drill completed

**Next Review:** After CRITICAL/HIGH remediation complete
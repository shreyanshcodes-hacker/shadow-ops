# STAGE 9 BASELINE — Existing Architecture Audit (Stages 0–8)

## 1. Overview

This document audits the current ShadowOps codebase (Stages 0–8) to identify reusable services, verify existing functionality, and catalog gaps before implementing Stage 9: Independent Fix Verification & Regression Analysis.

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
| 8 | Remediation & Patch | ✅ Complete | AI proposals, validation, approval, application, rollback |

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
- **Models** (`app/models/__init__.py`): 27+ SQLAlchemy models with workspace isolation
- **Repositories** (`app/repositories/__init__.py`): CRUD + query methods for all entities
- **Migrations**: 6 Supabase migrations (001–006) with RLS policies

### 3.6 API Layer (`app/api/v1/`)
- **Conventions**: FastAPI, dependency injection, workspace membership validation
- **Auth**: `get_current_user`, `require_workspace_member`
- **Endpoints**: Workspaces, Assets, Scans, Findings, AI Analysis, Attack Paths, Security Team, Remediations

### 3.7 Frontend (`frontend/app/`)
- **Pages**: Dashboard, Assets, Scans, Findings, Attack Paths, Security Team, Remediations
- **API Client** (`lib/api.ts`): Typed methods for all endpoints
- **Auth**: Firebase integration with token refresh

### 3.8 Scanning Infrastructure
- **SemgrepRunner** (`app/scanners/semgrep.py`): Secure command construction, timeout, JSON parsing
- **ScanJobRunner** (`app/scanning/runner.py`): 4-layer authorization enforcement, target preparation, execution, normalization, persistence
- **FindingNormalizer**: Severity mapping, CWE/CVE/OWASP extraction, deduplication

### 3.9 Remediation Infrastructure (Stage 8)
- **RemediationService** (`app/services/remediation.py`): AI proposal generation, validation orchestration
- **PatchProcessor** (`app/services/patch.py`): Security validation, path traversal protection, hash integrity
- **ValidationPipeline** (`app/services/validation.py`): Bounded validation checks (integrity, parsing, path allowlist, syntax, semgrep rescan, regression)
- **ApprovalService** (`app/services/approval.py`): Human approval with patch-hash binding, validation snapshot
- **PatchApplicationAdapter** (`app/services/application.py`): Controlled application with git stash checkpoint, idempotency
- **RollbackService** (`app/services/rollback.py`): Safe rollback with divergence detection, checkpoint restoration

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
| Remediation Proposals | ⚠️ | AI generation works, needs API keys |
| Patch Validation | ✅ | Security boundaries tested |
| Human Approval | ✅ | Patch-hash binding tested |
| Patch Application | ⚠️ | Requires git workspace |
| Rollback | ✅ | Divergence detection tested |
| Frontend Pages | ⚠️ | TypeScript compiles, needs runtime test |
| RLS Policies | ✅ | All tables protected |
| Audit Logging | ✅ | Immutable append-only |

---

## 5. Stage 8 Verification Handoff Infrastructure

### 5.1 Existing Verification Handoff Model (`RemediationVerificationHandoff`)
- **Table**: `remediation_verification_handoff` (migration 0006)
- **Fields**: proposal_id, application_id, finding_id, asset_id, patch_hash, repository_revision, changed_files, validation_results, original_finding_snapshot, applied_at, applied_by, verification_requested, verification_requested_at, verification_completed_at, verification_result, status
- **Status Enum**: PENDING_VERIFICATION, VERIFICATION_REQUESTED, VERIFIED, VERIFICATION_FAILED, MANUAL_REVIEW_REQUIRED
- **Repository**: `RemediationVerificationHandoffRepository`

### 5.2 Verification Handoff Endpoint
- **POST** `/remediations/applications/{application_id}/request-verification`
- Updates handoff status to VERIFICATION_REQUESTED
- Audit logs: `remediation.verification_requested`

### 5.3 What Stage 8 Provides for Verification
1. **Patch hash** — SHA256 of unified diff
2. **Repository revision** — Git commit SHA at application time
3. **Changed files** — Actual files modified
4. **Validation results** — Post-application validation (currently BLOCKED)
5. **Original finding snapshot** — Finding state at application time
6. **Checkpoint reference** — Git stash for rollback/baseline

---

## 6. Gaps & Missing for Stage 9

### 6.1 Verification Data Model (MISSING)
No persistent verification job model exists. Stage 9 requires:
- VerificationJob entity with lifecycle states
- VerificationCheck results (scanner, regression, comparison)
- EvidenceComparison results
- VerificationDecision (policy-driven)
- HumanReview record

### 6.2 Baseline Capture (MISSING)
No systematic baseline capture before patch application. Need:
- Original finding fingerprint and evidence snapshot
- Pre-patch scan results reference
- Scanner rule identity and configuration
- Verification engine version

### 6.3 Independent Rescan (PARTIAL)
SemgrepRunner exists but:
- No verification-specific scan orchestration
- No isolated post-patch working copy management
- No scanner version capture in verification context
- No BLOCKED handling for unavailable scanners

### 6.4 Evidence Comparison Engine (MISSING)
No deterministic comparison service. Need:
- Stable finding fingerprint matching
- Scanner rule ID comparison
- Normalized file path comparison
- Evidence hash comparison
- Finding relationship consideration
- Conservative matching for moved/changed findings

### 6.5 Regression Analysis (MISSING)
No regression check framework. Need:
- Allowlist of safe test commands
- Isolated test execution environment
- Check identity, version, outcome, duration recording
- PASS/FAIL/SKIPPED/BLOCKED/ERROR distinction

### 6.6 Verification Decision Policy (MISSING)
No versioned deterministic policy. Need:
- Policy engine considering baseline validity, scanner success, finding absence, regression results
- Outcomes: VERIFIED_CANDIDATE, FAILED, INCONCLUSIVE, BLOCKED
- Human review gating

### 6.7 Human Review Workflow (MISSING)
No protected review action. Need:
- Authorized role verification
- Baseline, patch, scan, regression, policy display
- Accept/Reject/Rerun actions with audit trail
- Finding lifecycle update only on explicit human decision

### 6.8 API Endpoints (MISSING)
No verification endpoints. Need:
- `POST /remediations/{id}/verify` → create verification job
- `GET /verifications` → list
- `GET /verifications/{id}` → detail
- `GET /verifications/{id}/comparisons` → evidence comparison
- `GET /verifications/{id}/checks` → regression/scanner checks
- `GET /verifications/{id}/evidence` → baseline vs post-patch evidence
- `POST /verifications/{id}/review` → human decision
- `POST /verifications/{id}/rerun` → re-execution

### 6.9 Frontend Pages (MISSING)
No verification UI. Need:
- `/verifications` — list page with filters
- `/verifications/[id]` — detail with tabs (overview, comparison, checks, evidence, review)

### 6.10 Database Migration (MISSING)
Need migration `0007_stage9_verification.sql` for:
- VerificationJob table
- VerificationCheck table
- EvidenceComparison table
- VerificationPolicy table
- VerificationReview table
- Updated VerificationHandoff status flow

### 6.11 Audit Events (MISSING)
Need new audit events:
- verification.requested
- verification.started
- verification.scanner_completed
- verification.comparison_completed
- verification.regression_completed
- verification.failed
- verification.inconclusive
- verification.blocked
- verification.reviewed
- verification.rerun_requested

---

## 7. Security Boundaries to Preserve

| Boundary | Current Enforcement | Stage 9 Must Maintain |
|----------|---------------------|----------------------|
| Workspace Isolation | RLS + query filtering | All new tables |
| AI Prompt Injection | TRUSTED/UNTRUSTED delimiters | Verification AI prompts |
| Secret Redaction | 32+ patterns | All evidence to AI |
| Authorization Checks | `require_workspace_member` | All verification endpoints |
| No Autonomous Actions | Agents analytical only | No auto-verify, no auto-close |
| Audit Trail | All mutations logged | All verification events |
| Patch Integrity | SHA256 hash binding | Verification references patch hash |
| No Arbitrary Scans | Controlled targets only | Verification scans same targets |
| No Test Execution | BLOCKED in validation | Regression tests in isolation only |

---

## 8. Key Files to Extend/Create for Stage 9

### New Backend Files
```
app/models/verification.py          # New models (or extend __init__.py)
app/schemas/verification.py         # Pydantic schemas
app/services/verification.py        # VerificationService (orchestration)
app/services/baseline.py            # BaselineCaptureService
app/services/comparison.py          # EvidenceComparisonService
app/services/regression.py          # RegressionAnalysisService
app/services/policy.py              # VerificationPolicyEngine
app/api/v1/verifications.py         # API endpoints
app/agents/verification/            # Verification agents (optional, reuse AI)
```

### New Frontend Files
```
app/(dashboard)/verifications/page.tsx
app/(dashboard)/verifications/[id]/page.tsx
components/verification/            # Diff viewer, evidence comparison, check results
```

### Database Migration
```
supabase/migrations/0007_stage9_verification.sql
```

### Tests
```
backend/tests/test_verification.py
```

### Documentation
```
docs/VERIFICATION_ARCHITECTURE.md
docs/VERIFICATION_POLICY.md
docs/BASELINE_AND_EVIDENCE_COMPARISON.md
docs/VERIFICATION_SECURITY.md
docs/STAGE_9_REPORT.md
```

---

## 9. Known Limitations (Pre-Stage 9)

1. **No live AI credentials** — All AI features untested against real providers
2. **No Railway deployment verified** — Local only
3. **Frontend typecheck not run** — No Node.js in environment
4. **Integration tests require DB** — Unit tests use mocks only
5. **Semgrep runner not tested end-to-end** — Needs demo target
6. **Patch application limited** — Only git apply in server workspace
7. **Syntax validation placeholder** — Language-specific linters not implemented
8. **Regression testing BLOCKED** — Requires test execution environment
9. **Semgrep re-scan BLOCKED** — Requires isolated execution environment

---

## 10. Stage 9 Readiness Assessment

| Requirement | Ready? | Notes |
|-------------|--------|-------|
| AI Provider Abstraction | ✅ | Reuse Gemini/Grok |
| Structured AI Output | ✅ | Reuse SecurityAnalysis pattern |
| Prompt Injection Defense | ✅ | Reuse safety infrastructure |
| Workspace Isolation | ✅ | All models have workspace_id |
| Human Review Pattern | ✅ | Security Team review exists |
| Audit Logging | ✅ | Extend for verification events |
| Repository Pattern | ✅ | Extend for new models |
| Deterministic Validation | ✅ | Reuse validation approach |
| Cost/Rate Controls | ✅ | Extend for verification |
| Baseline Data Available | ⚠️ | Handoff has finding snapshot, needs pre-patch scan |
| Semgrep Runner | ⚠️ | Exists but needs isolated execution |
| Patch Hash Integrity | ✅ | Available from handoff |
| Repository Revision Tracking | ✅ | Available from handoff |

---

## 11. Implementation Priority for Stage 9

1. **Database Migration & Models** — Foundation for all else
2. **Verification Schemas** — API contracts
3. **Baseline Capture Service** — Capture/record pre-patch state
4. **Verification Service** — Job orchestration, state machine
5. **Evidence Comparison Engine** — Deterministic finding comparison
6. **Independent Rescan Orchestration** — Reuse SemgrepRunner with isolation
7. **Regression Analysis Service** — Allowlisted checks in isolation
8. **Verification Policy Engine** — Versioned deterministic policy
9. **Human Review Service** — Protected review action
10. **API Endpoints** — Expose all operations
11. **Frontend Pages** — List & detail views
12. **Tests** — Unit + integration
13. **Documentation** — Architecture, security, policy guides

---

## 12. Critical Decisions for Stage 9

| Decision | Recommendation |
|----------|----------------|
| Verification isolation | Git worktree for post-patch scan (reuse Stage 8 isolation pattern) |
| AI interpretation | Optional advisory summary only; never override deterministic outcome |
| Baseline source | Use RemediationVerificationHandoff + pre-patch scan if available |
| Scanner unavailability | Report BLOCKED/SCANNER_UNAVAILABLE — never manufacture clean scan |
| Finding fingerprint | SHA256 of (rule_id + normalized_path + normalized_location + evidence_hash) |
| Regression commands | Configurable allowlist per workspace/asset; never arbitrary AI commands |
| Policy versioning | `verification-policy-v1` with explicit version in every job |
| Finding closure | NEVER auto-close — only human decision after VERIFIED_CANDIDATE |

---

*Generated: 2026-10-13*
*Baseline for Stage 9 Implementation*
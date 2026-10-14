# KNOWN LIMITATIONS — ShadowOps

**Version:** 1.0
**Status:** Documented as of Stage 12
**Purpose:** Transparent disclosure of unimplemented, partially implemented, or consciously deferred capabilities

---

## 1. Authentication & Identity

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **No MFA enforcement** | Single-factor auth only; credential theft = full access | Documented; recommend external IdP (Okta/Auth0) for production | Post-pilot |
| **No session management UI** | Users cannot view/revoke active sessions | Firebase Console can revoke; no self-service | Pilot |
| **No password policy** | Relies on Firebase/IdP | N/A (Firebase handles) | N/A |
| **No SSO/SAML/OIDC** | Enterprise integration blocked | Firebase supports but not configured | Post-pilot |
| **Email verification not enforced** | Unverified emails can access if Firebase allows | Configurable in Firebase Console | Pre-pilot |

---

## 2. Authorization & Access Control

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **RLS bypassed by service role** | Backend has full DB access; app-layer bugs = data leak | Defense-in-depth: app-layer checks on every query; audit logging | Pilot (separate service roles) |
| **No attribute-based access control (ABAC)** | Cannot restrict by asset criticality, finding severity, etc. | Role-based only; labels/tags unused | Post-pilot |
| **No temporary/elevated access** | No "break-glass" or time-limited admin | Manual role assignment only | Post-pilot |
| **Viewer role cannot export reports** | Intentional but limiting | Workaround: Member role for export | Documented |

---

## 3. Scanning & Detection

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **No container sandbox for Semgrep** | Scanner runs in API process; escape risk | Path validation, size limits, timeout; ephemeral workspace | CRITICAL — Pre-pilot |
| **No private registry scanning** | Cannot scan images in private ECR/GHCR/Artifactory | Not implemented | Post-pilot |
| **No DAST/IAST** | Only SAST/SCA via Semgrep | Architecture supports plugins | Post-pilot |
| **No incremental scanning** | Full scan every time | Semgrep caching helps | Post-pilot |
| **No custom rule support (UI)** | Rules only via config; no rule editor | API accepts custom rulesets | Post-pilot |
| **Scan targets limited to demo fixtures** | No real repo integration (GitHub/GitLab/Bitbucket) | Manual asset config only | Pilot |
| **No secret scanning beyond Semgrep** | No TruffleHog, GitLeaks, detect-secrets integration | Semgrep `p/secrets` ruleset only | Post-pilot |

---

## 4. Findings & Evidence

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **No finding deduplication across scans** | Same finding re-reported each scan | Dedupe within scan only | Pilot |
| **No finding suppression/exception workflow** | Cannot mark "accepted risk" with expiration | `risk_accepted` status exists but no workflow | Pilot |
| **Evidence not signed/immutable** | JSONB in DB; mutable by service role | Audit log tracks changes | Post-pilot (WORM storage) |
| **No evidence attachment upload** | Only inline JSON/content; no file uploads | `storage_object_id` field reserved | Pilot |

---

## 5. AI Security Analyst

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Single provider at a time** | Cannot compare Gemini vs Grok for same finding | Config switch only | Post-pilot |
| **No fine-tuning/custom models** | Uses base models only | Prompt engineering only | Post-pilot |
| **No human feedback loop for AI** | Cannot correct AI to improve future runs | `recommended_next_steps` only | Post-pilot |
| **AI cost not tracked per workspace** | Only per-run estimation | `estimated_cost_usd` field exists | Pilot |
| **Prompt injection defense = delimiters only** | Not robust against sophisticated attacks | Structured output validation; sanitization | CRITICAL — Pre-pilot |

---

## 6. Attack Paths & Risk Scoring

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Risk model v1 only** | No model versioning/comparison | `risk_model_version` field reserved | Pilot |
| **No MITRE ATT&CK mapping** | Findings not tagged with TTPs | CWE/CVE/OWASP only | Post-pilot |
| **Attack paths not auto-generated** | Manual/assisted only | `SecurityTeamRun` orchestration exists | Pilot |
| **No blast radius visualization** | Graph data exists but no UI | API returns nodes/edges | Pilot (frontend) |

---

## 7. AI Security Team Orchestration

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Agents run sequentially** | No parallel agent execution | `SecurityTeamRun` orchestrates linearly | Post-pilot |
| **No agent timeout enforcement** | Stuck agent blocks entire run | Per-agent timeout not implemented | Pre-pilot |
| **Agent outputs not cross-validated** | Each agent independent | `SecurityReviewer` agent reviews all | Pilot |
| **No custom agent registration** | Fixed 5 agents only | Registry exists but not exposed | Post-pilot |

---

## 8. Remediation & Verification

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Patch application not implemented** | `PatchApplicationAdapter` is stub; no `git apply` | Manual patch application only | CRITICAL — Pre-pilot |
| **No isolated git worktree** | Patches would apply to production repo | Not implemented | CRITICAL — Pre-pilot |
| **Rollback not tested end-to-end** | `RollbackService` exists but untested | Checkpoint_ref stored but unused | CRITICAL — Pre-pilot |
| **Verification not independent** | Re-scan runs in same process | Separate worker planned | CRITICAL — Pre-pilot |
| **No test execution in verification** | `suggested_tests` stored but not run | `RegressionAnalysisService` placeholder | Pilot |
| **Missing baseline → INCONCLUSIVE not BLOCKED** | Policy allows missing baseline | Configurable in `VerificationPolicy` | Pilot |

---

## 9. Reports & Exports

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **PDF generation untested** | `weasyprint` (headless Chromium) not validated | JSON export works | Pre-pilot |
| **Storage bucket not configured** | `reports` bucket placeholder only | Local filesystem fallback | Pre-pilot |
| **No scheduled/recurring reports** | Manual generation only | API supports period filters | Post-pilot |
| **No report templates/customization** | Fixed sections per report type | Section-based architecture ready | Post-pilot |
| **No compliance report mappings** | No SOC2, ISO27001, NIST templates | Generic executive/technical only | Post-pilot |

---

## 10. Notifications & Workflows

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Outbox processor not implemented** | Events written but never delivered | Synchronous delivery for critical paths | CRITICAL — Pre-pilot |
| **Email delivery untested** | `EmailAdapter` exists but no SMTP config | Log-only mode | Pre-pilot |
| **n8n integration disabled** | `N8N_WEBHOOK_URL` not configured | Workflow engine works without n8n | Post-pilot |
| **No webhook retry with exponential backoff** | Fixed retry count only | `max_attempts=5` | Pilot |
| **No notification digest/batching** | Every event = notification | `deduplication_window_minutes` helps | Pilot |

---

## 11. Platform & Infrastructure

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **No Railway deployment config** | `Dockerfile`, `railway.json` missing | Documented in `RAILWAY_DEPLOYMENT.md` | Pre-pilot |
| **No Kubernetes/Helm charts** | Railway only; no self-host option | Dockerfiles portable | Post-pilot |
| **No disaster recovery tested** | PITR not drilled | Documented in `BACKUP_AND_RECOVERY.md` | Pre-pilot |
| **No secret rotation automation** | Manual rotation only | Documented schedule | Post-pilot |
| **No distributed tracing** | Request ID only; no OpenTelemetry | Structured logs only | Post-pilot |
| **No SLA/SLO definitions** | No uptime/latency targets | To be defined | Pilot |

---

## 12. Frontend

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Test environment not runnable** | Node.js/npm not in CI; Firebase/Supabase mocks incomplete | Manual E2E testing | Pre-pilot |
| **No real-time updates** | Polling only; no WebSockets/SSE | `react-query` refetch | Pilot |
| **No offline support** | Requires network | N/A for SaaS | N/A |
| **Accessibility not audited** | WCAG 2.1 AA not verified | Semantic HTML, ARIA labels | Post-pilot |

---

## 13. Compliance & Audit

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **No SOC2 Type II evidence** | Controls not continuously monitored | Audit logs, RLS, policies documented | Post-pilot (after 6 months) |
| **No FedRAMP/IL4** | Not architected for gov cloud | Commercial only | N/A |
| **No data residency controls** | Supabase region fixed at provisioning | Choose region at setup | Documented |

---

## 14. Performance & Scale

| Limitation | Impact | Mitigation | Target Resolution |
|------------|--------|------------|-------------------|
| **Single-region only** | No multi-region HA | Supabase + Railway single region | Post-pilot |
| **Scan concurrency limit = 3/workspace** | Hardcoded in config | `MAX_CONCURRENT_SCANS_PER_WORKSPACE` | Pilot (configurable) |
| **AI daily limit = 100 analyses** | Hardcoded in config | `AI_DAILY_ANALYSIS_LIMIT` | Pilot (configurable) |
| **No horizontal scan worker scaling** | Single worker process | Celery concurrency only | Post-pilot |

---

## 15. Accepted Risks (Documented)

| Risk ID | Description | Compensating Control | Expiration | Owner |
|---------|-------------|---------------------|------------|-------|
| AR-2026-001 | Service role bypasses RLS | App-layer checks on every query; audit logging | Pilot launch | Security Lead |
| AR-2026-002 | Scanner runs in API container | Path validation, size limits, timeout | Pilot launch | Security Lead |
| AR-2026-003 | Patch application stub | Manual patch review + apply for pilot | Pilot launch | Security Lead |
| AR-2026-004 | Verification not independent | Human review required for all verifications | Pilot launch | Security Lead |
| AR-2026-005 | Outbox processor not implemented | Synchronous delivery for approvals/verifications | Pilot launch | Engineering Lead |
| AR-2026-006 | Frontend tests not runnable | Manual E2E test plan for pilot | Pilot launch | Engineering Lead |

---

## 16. Deferred Features (Explicitly Out of Scope)

| Feature | Reason | Revisit |
|---------|--------|---------|
| Chat/AI Assistant (Stages 4+) | Scope creep; core scanning priority | v2.0 |
| Compliance report templates | No customer demand yet | Post-pilot |
| Multi-tenancy (single DB) | Supabase project per customer | v2.0 |
| On-premise / air-gapped | Not target market | v2.0 |
| Mobile app | Web-first | v2.0 |
| Plugin marketplace | Core stability first | v2.0 |

---

## 17. References

- `docs/STAGE_12_BASELINE.md` — Baseline audit matrix
- `docs/SECURITY_AUDIT.md` — Detailed security findings
- `docs/RELEASE_READINESS.md` — Release criteria
- `docs/RAILWAY_DEPLOYMENT.md` — Deployment gaps
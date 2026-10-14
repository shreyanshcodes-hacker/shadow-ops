# RELEASE READINESS POLICY — ShadowOps

**Version:** 1.0
**Effective:** Stage 12
**Authority:** Security Engineering Lead

---

## 1. Purpose

This policy defines the explicit criteria for three release readiness outcomes. It prevents premature deployment by requiring evidence-based verification of security boundaries, not just successful builds or unit tests.

---

## 2. Release Outcomes

### NOT READY
**Default state.** Any of the following conditions result in NOT READY:

| Category | Condition |
|----------|-----------|
| Authentication | Live Firebase token verification not tested; revoked/expired token handling unverified |
| Authorization | Workspace isolation (RLS) not verified with anon key; service role usage undocumented |
| Scanner Safety | Semgrep executes in API process; no container/sandbox isolation demonstrated |
| Patch Execution | Remediation patches apply without isolated git worktree; rollback not tested end-to-end |
| Verification Integrity | Independent re-scan runs in same process/binary; not independent |
| Database | Migrations not tested on clean DB; numbering gaps exist; no rollback scripts |
| Secrets | No secret scanning in CI; production credentials in repo history or unrotated |
| Observability | No structured log shipping; no distributed tracing; health checks expose internals |
| Backup/Recovery | No restore drill documented or tested; RLS restore procedure undefined |
| Deployment | Railway config missing (Dockerfile, railway.json); migration strategy undefined |

### READY FOR CONTROLLED PILOT
**All CRITICAL findings resolved.** All of the following must be evidenced:

| Requirement | Evidence Required |
|-------------|-------------------|
| Live Firebase Auth | Integration test passing against dedicated test Firebase project |
| Live Supabase RLS | Queries with anon key enforce workspace isolation; service role documented as backend-only |
| Scanner Isolation | Semgrep runs in dedicated container (Docker/gVisor); resource limits enforced; path traversal blocked |
| Patch Isolation | Patches apply in isolated git worktree; checkpoint created; rollback verified to restore exact state |
| Verification Independence | Re-scan executes in separate worker process/container; different binary version optional |
| Migrations | Clean DB migration test passes; numbering sequential; downgrade scripts exist for last 3 migrations |
| Rate Limiting | Per-workspace limits on scan creation, AI analysis, report generation, auth endpoints |
| Secrets | `trufflehog`/`detect-secrets` in CI; no secrets in history; rotation procedure documented |
| Health/Readiness | `/health` (liveness) and `/ready` (readiness) separate; readiness checks DB, scanner, AI provider |
| Deployment Config | `Dockerfile`, `railway.json` committed; Railway project configured; env vars set in Railway UI |
| Backup Strategy | Documented backup schedule, retention, restore procedure; restore drill completed once |

**Pilot Constraints:**
- Single workspace, invite-only
- Admin approval required for each scan
- All AI analysis logged for review
- Daily manual log review
- Rollback procedure tested weekly

### READY FOR PRODUCTION
**All HIGH findings resolved + Pilot success metrics met.** All CONTROLLED PILOT requirements plus:

| Requirement | Evidence Required |
|-------------|-------------------|
| Pilot Duration | Minimum 30 days controlled pilot with ≥3 workspaces |
| Incident History | Zero CRITICAL/HIGH security incidents during pilot |
| Uptime | ≥99.5% API availability during pilot (excluding planned maintenance) |
| Performance | P95 scan latency <10 min for 500MB repo; AI analysis <60s per finding |
| Recovery | Restore drill completed <4 hours RTO; RPO <1 hour |
| Scaling | Horizontal worker scaling verified (3+ concurrent scans) |
| Compliance | SOC2 Type II readiness documented; audit logs tamper-evident |
| Monitoring | Alerting on: auth failures, scan failures, AI errors, queue backlog, disk space |
| Documentation | Runbooks for: incident response, backup restore, migration, scaling, secret rotation |

---

## 3. Decision Process

### Authority
- **NOT READY → CONTROLLED PILOT:** Security Engineering Lead + CTO approval
- **CONTROLLED PILOT → PRODUCTION:** Security Engineering Lead + CTO + Legal/Compliance approval

### Evidence Package Required
Each transition requires a signed evidence package containing:
1. Test reports (automated + manual)
2. Live integration test results (screenshots/logs)
3. Architecture decision records for any accepted risks
4. Rollback/recovery drill results
4. Pilot metrics (if applicable)

### No Automatic Promotion
- Successful CI build ≠ readiness
- Unit test pass ≠ readiness
- Staging deployment ≠ readiness

---

## 4. Exception Handling

### Accepted Risks
Any deviation from criteria must be documented as an **Accepted Risk** with:
- Risk ID (e.g., AR-2026-001)
- Description
- Compensating control
- Expiration date (max 90 days)
- Owner responsible for remediation
- Approval signatures

### Emergency Override
Production deployment without full criteria requires:
- Written incident declaration
- CTO + Security Lead + Legal sign-off
- 72-hour remediation plan attached
- Post-deployment audit within 7 days

---

## 5. Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-10-14 | Stage 12 Implementation | Initial policy |

---
# INCIDENT RESPONSE GUIDE — ShadowOps

**Version:** 1.0
**Classification:** Internal — Security Team
**Effective:** Stage 12

---

## 1. Incident Classification

| Severity | Definition | Response Time | Escalation |
|----------|------------|---------------|------------|
| **SEV-1 (Critical)** | Active security breach, data exfiltration, RCE, auth bypass | 15 min | Security Lead → CTO → Legal |
| **SEV-2 (High)** | Service degradation affecting security operations, scanner failure, AI provider outage | 1 hour | Security Lead → Engineering Lead |
| **SEV-3 (Medium)** | Non-security bug, performance issue, partial feature degradation | 4 hours | On-call Engineer |
| **SEV-4 (Low)** | Cosmetic issue, documentation, minor enhancement | Next sprint | Backlog |

---

## 2. Response Team Roles

| Role | Responsibilities | Contact |
|------|------------------|---------|
| **Incident Commander (IC)** | Overall coordination, decisions, communication | Security Lead |
| **Technical Lead** | Root cause analysis, fix implementation | Senior Engineer |
| **Communications** | Stakeholder updates, status page, customer comms | Product Manager |
| **Security Analyst** | Forensics, evidence preservation, threat intel | Security Engineer |
| **Database Admin** | DB recovery, query analysis, backup restore | DevOps/Platform |

---

## 3. Incident Response Phases

### Phase 1: Detection & Triage (0-15 min)

**Triggers:**
- Alert: Auth failure spike, scan failure rate >50%, AI error rate >20%
- Customer report: Unauthorized access, data leak
- Internal: Suspicious audit log entries, failed verification jobs

**Actions:**
1. Acknowledge alert in monitoring system
2. Create incident channel (`#incident-<date>-<short-desc>`)
3. Assign IC, Technical Lead, Communications
4. Determine severity (SEV-1/2/3/4)
5. Start timeline document

**Decision Point:** Is this a security incident (SEV-1/2) or operational (SEV-3/4)?

### Phase 2: Containment (15 min - 1 hour)

**SEV-1 (Security Breach) — Immediate Actions:**
| Threat | Containment Action |
|--------|-------------------|
| Compromised API key | Rotate key in Railway/Supabase/Firebase immediately |
| Compromised service account | Revoke Firebase service account; generate new |
| Database breach | Enable Supabase read-only mode; snapshot DB |
| Active scanner escape | Stop all scan workers; isolate scan workspace volume |
| Malicious patch applied | Rollback via Supabase PITR; audit all workspaces |

**SEV-2 (Service Degradation):**
| Issue | Containment |
|-------|-------------|
| Scanner down | Disable scan creation; queue scans for retry |
| AI provider down | Fail fast with cached analysis; disable AI features |
| Queue backlog | Scale workers; pause non-critical jobs |
| DB connection pool exhausted | Increase pool; kill long-running queries |

**Evidence Preservation (ALL SEV-1/2):**
- Export audit logs for affected workspace(s)
- Snapshot affected DB tables
- Preserve scanner/verification job artifacts
- Do NOT delete logs or restart services without snapshot

### Phase 3: Eradication (1-4 hours)

**Root Cause Analysis:**
1. Review audit logs, application logs, scan events
2. Identify attack vector: auth bypass, injection, supply chain, insider
3. Check for lateral movement: other workspaces, admin accounts
4. Verify fix addresses root cause, not symptom

**Fix Deployment:**
- Hotfix branch from `main`
- Security review required for SEV-1 fixes
- Deploy to staging first (if time permits)
- Railway deploy with migration lock

### Phase 4: Recovery (4-24 hours)

**Service Restoration:**
1. Verify fix in staging
2. Deploy to production
3. Gradual traffic restore (canary if possible)
4. Monitor key metrics: auth success, scan completion, AI latency

**Data Recovery (if needed):**
- Supabase PITR: Restore to pre-incident timestamp
- Verify RLS policies intact after restore
- Re-run failed verification jobs
- Notify affected workspaces

### Phase 5: Post-Incident (24-72 hours)

**Required Artifacts:**
1. **Incident Report** — Timeline, root cause, impact, fix
2. **Action Items** — Preventive measures with owners/dates
3. **Customer Communication** — If data exposed (GDPR/CCPA)
4. **Security Review** — Update threat model, detection rules

**Blameless Postmortem:**
- Focus on systems, not people
- Identify systemic gaps
- Update runbooks and detection

---

## 4. Specific Scenario Playbooks

### 4.1 Authentication Bypass / Token Forgery

**Detection:** Unusual `auth.uid()` in audit logs, cross-workspace access attempts

**Containment:**
1. Rotate `SUPABASE_JWT_SECRET` and `SECRET_KEY` immediately
2. Invalidate all Firebase sessions: Firebase Console → Authentication → Users → "Revoke all sessions"
3. Rotate `FIREBASE_PRIVATE_KEY` (generate new service account)
4. Audit all `audit_logs` for anomalous `user_id` / `workspace_id` combinations

**Investigation:**
- Check for JWT algorithm confusion (HS256 vs RS256)
- Verify `check_revoked=True` in `verify_firebase_token`
- Review token expiry handling

### 4.2 Scanner Container Escape

**Detection:** Unexpected processes in scan worker, filesystem access outside `/scan-workspace`

**Containment:**
1. Stop all scan workers: `celery -A app.workers.celery_app control shutdown`
2. Isolate scan workspace volume (unmount if possible)
3. Review Semgrep version for known CVEs
4. Audit `scan_events` for `SCAN_FAILED` with unusual error codes

**Investigation:**
- Check `_prepare_scan_target` symlink resolution
- Verify resource limits (cgroups) on scan subprocess
- Review repository content for malicious payloads

### 4.3 AI Provider Compromise / Prompt Injection

**Detection:** Anomalous AI analysis outputs, unexpected findings, cost spikes

**Containment:**
1. Disable AI analysis: Set `AI_PROVIDER=none` or rotate API keys
2. Review all `finding_ai_analysis` from last 24h
3. Check `ai_runs` for unusual `input_hash` patterns
4. Audit `remediation_proposals` for malicious patches

**Investigation:**
- Test prompt injection vectors against `build_safe_prompt`
- Verify `sanitize_evidence_dict` removes all secret patterns
- Check structured output validation prevents schema bypass

### 4.4 Malicious Remediation Patch

**Detection:** Unapproved `remediation_applications`, rollback requests, verification failures

**Containment:**
1. Disable patch application: Set feature flag or revoke admin sessions
2. Audit all `remediation_approvals` — verify `patch_hash` matches `patch_versions`
3. Check `remediation_verification_handoff` for anomalies
4. Review `patch_versions.unified_diff` for path traversal, disallowed files

**Investigation:**
- Verify `PatchProcessor` path allowlist enforcement
- Check `ApprovalService` binds approval to exact `patch_hash`
- Test rollback restores exact pre-patch state

### 4.5 Database / Supabase Incident

**Detection:** Supabase status page, connection errors, RLS policy failures

**Containment:**
1. Check Supabase status page / Discord
2. If RLS failure: Enable read-only mode, audit cross-workspace access
3. If PITR needed: Restore to last known good timestamp
4. Verify migration state: `alembic current` vs `alembic heads`

---

## 5. Communication Templates

### 5.1 Internal Status Update (Every 30 min for SEV-1/2)

```
**INCIDENT UPDATE #<n> — <SEV> — <Title>**
Time: <ISO timestamp>
Status: Investigating / Contained / Recovering / Resolved
Impact: <Workspaces affected, features down>
Root Cause (if known): <One sentence>
Actions Taken: <Bullets>
Next Steps: <Bullets>
ETA for Resolution: <Time or "Unknown">
IC: @<name>
```

### 5.2 Customer Notification (If data exposed)

```
Subject: Security Incident Notification — ShadowOps

We detected a security incident affecting your workspace (<workspace_name>) on <date>.
Impact: <What data was accessed/modified>
Root Cause: <Non-technical summary>
Actions Taken: <What we did>
Remediation: <What you should do (rotate keys, review access)>
Contact: security@shadowops.io
```

---

## 6. Monitoring & Alerting Rules

### 6.1 Required Alerts (To Be Configured)

| Alert | Query | Threshold | Severity |
|-------|-------|-----------|----------|
| Auth failure rate | `rate(auth_failures[5m])` | >10/min | SEV-2 |
| Scan failure rate | `rate(scan_failures[5m])` | >50% | SEV-2 |
| AI error rate | `rate(ai_errors[5m])` | >20% | SEV-3 |
| Queue backlog | `celery_queue_length` | >100 | SEV-3 |
| Verification failure | `rate(verification_failed[1h])` | >5 | SEV-2 |
| Cross-workspace audit | `audit_logs where workspace_id != user_workspace` | >0 | SEV-1 |
| Patch apply without approval | `remediation_applications where approval_id IS NULL` | >0 | SEV-1 |
| Secret in logs | `logs where message matches secret_pattern` | >0 | SEV-1 |

### 6.2 Dashboard Panels (Grafana)

- Auth success rate (5m)
- Scan throughput (completed/min)
- AI analysis latency (p50, p95, p99)
- Worker queue depth by type
- Verification outcome distribution
- Audit log volume by action
- Error rate by endpoint

---

## 7. Forensic Evidence Collection

### 7.1 Log Sources

| Source | Location | Retention |
|--------|----------|-----------|
| Application logs | Railway stdout / log drain | 30 days |
| Audit logs | `audit_logs` table | 7 years |
| Scan events | `scan_events` table | 2 years |
| AI runs | `ai_runs` table | 2 years |
| Verification jobs | `verification_jobs` table | 2 years |
| Supabase logs | Supabase Dashboard → Logs | 7 days |
| Firebase auth logs | Firebase Console → Auth → Activity | 30 days |

### 7.2 Evidence Preservation Commands

```bash
# Export audit logs for workspace
psql $DATABASE_URL -c "\COPY (SELECT * FROM audit_logs WHERE workspace_id = 'xxx') TO '/tmp/audit_export.csv' CSV HEADER"

# Snapshot verification job
psql $DATABASE_URL -c "\COPY (SELECT * FROM verification_jobs WHERE id = 'xxx') TO '/tmp/verification_snapshot.csv' CSV HEADER"

# Supabase PITR restore point
# Supabase Dashboard → Database → Backups → Create manual backup
```

---

## 8. Legal & Compliance

### 8.1 Breach Notification Timeline

| Regulation | Notification Deadline | Authority |
|------------|----------------------|-----------|
| GDPR | 72 hours | DPA |
| CCPA | "Without unreasonable delay" | CA AG |
| SOC2 | Per customer contract | Auditor |

### 8.2 Evidence Handling

- Chain of custody for all exported data
- Encrypt exports at rest (GPG)
- Limit access to Security Lead + Legal
- Document all access in incident timeline

---

## 9. Runbook Maintenance

| Task | Frequency | Owner |
|------|-----------|-------|
| Review alert thresholds | Monthly | Security Lead |
| Test PITR restore | Quarterly | DevOps |
| Update contact list | Quarterly | Security Lead |
| Tabletop exercise | Semi-annually | All responders |
| Review runbook accuracy | After each incident | IC |

---

## 10. Contacts

| Role | Name | Phone | Email | Slack |
|------|------|-------|-------|-------|
| Security Lead | TBD | TBD | security@shadowops.io | @security-lead |
| CTO | TBD | TBD | cto@shadowops.io | @cto |
| Engineering Lead | TBD | TBD | eng@shadowops.io | @eng-lead |
| Legal | TBD | TBD | legal@shadowops.io | @legal |
| Supabase Support | — | — | support@supabase.io | — |
| Firebase Support | — | — | firebase-support@google.com | — |

---

## 11. References

- `docs/SECURITY_AUDIT.md` — Security findings that may trigger incidents
- `docs/BACKUP_AND_RECOVERY.md` — Recovery procedures
- `docs/RAILWAY_DEPLOYMENT.md` — Deployment rollback
- NIST SP 800-61 Rev. 2 — Computer Security Incident Handling Guide
# BACKUP & RECOVERY — ShadowOps

**Version:** 1.0
**Scope:** Data protection, retention, and disaster recovery
**Effective:** Stage 12

---

## 1. Backup Strategy Overview

| Data Layer | Backup Method | Frequency | Retention | RPO | RTO |
|------------|---------------|-----------|-----------|-----|-----|
| **PostgreSQL (Supabase)** | Supabase PITR (WAL-G) | Continuous | 7 days (default) | <1 min | <30 min |
| **PostgreSQL (Supabase)** | Daily logical dump | Daily 02:00 UTC | 30 days | 24 hours | <2 hours |
| **Supabase Storage (Reports)** | S3 versioning + Cross-region replication | On write | 1 year | 0 | <1 hour |
| **Application Code** | Git (GitHub) | On commit | Forever | 0 | <15 min |
| **Configuration** | Railway secrets + `.env.example` | On change | Forever | 0 | <10 min |
| **Scan Workspace Volume** | Railway volume snapshot | Daily | 7 days | 24 hours | <1 hour |

---

## 2. Supabase Database Backup

### 2.1 Point-in-Time Recovery (PITR)

**Default:** Enabled on all Supabase projects (Pro plan+)
- Continuous WAL archiving to S3
- Restore to any second within 7-day window
- Access: Supabase Dashboard → Database → Backups

**Verification:**
```bash
# Test restore (run quarterly)
# 1. Create test project from backup
# 2. Verify schema integrity
# 3. Verify RLS policies enforced
# 4. Verify audit_logs, findings, scans accessible
```

### 2.2 Logical Backups (pg_dump)

**Schedule:** Daily 02:00 UTC via Supabase or custom cron

**Format:** Custom (`-Fc`) for parallel restore
```bash
pg_dump -Fc -h <host> -U postgres -d postgres > shadowops_$(date +%Y%m%d).dump
```

**Restore:**
```bash
pg_restore -h <host> -U postgres -d postgres -j 4 shadowops_20261014.dump
```

### 2.3 Backup Exclusions

**Do NOT backup (rebuildable):**
- `scan_events` (high volume, append-only, can truncate)
- `agent_runs` (reproducible from scans)
- `verification_checks` (reproducible)
- `workflow_run_events` (reproducible)

**Must backup (source of truth):**
- `profiles`, `workspaces`, `workspace_members`
- `assets`, `asset_authorizations`
- `scans`, `findings`, `finding_evidence`
- `attack_paths`, `risk_snapshots`
- `remediation_proposals`, `patch_versions`, `remediation_approvals`
- `verification_jobs`, `verification_baselines`, `evidence_comparisons`
- `reports`, `report_sections`, `report_exports`
- `audit_logs` (compliance)
- `notifications`, `notification_preferences`, `notification_rules`
- `event_outbox`, `notification_deliveries`
- `verification_policies`, `verification_reviews`

---

## 3. Supabase Storage Backup

### 3.1 Report Artifacts

**Bucket:** `reports` (private, not public)
**Configuration:**
```sql
-- Enable versioning
-- Enable cross-region replication (if multi-region)
-- Lifecycle: Transition to IA after 30 days, Glacier after 365 days
```

**Backup Verification:**
- Monthly: Download 5 random reports, verify checksum
- Quarterly: Full bucket sync to secondary region

---

## 4. Scan Workspace Volume Backup

### 4.1 What to Backup

- Cloned repositories (temporary, can re-clone)
- Semgrep cache (can rebuild)
- **Exception:** If using local git mirrors, backup mirror

### 4.2 Strategy

**Option A: Ephemeral (Recommended)**
- No backup needed
- Re-clone on scan start
- Cost: Bandwidth + time per scan

**Option B: Persistent Volume + Snapshots**
- Railway volume snapshot daily
- Restore: Attach snapshot to new volume
- Cost: Storage + snapshot fees

---

## 5. Recovery Procedures

### 5.1 Scenario: Single Table Corruption

**Example:** `findings` table has bad data from bug

**Recovery:**
```bash
# 1. Identify affected rows (by workspace, time range)
# 2. Restore from logical dump (single table)
pg_restore -t findings -d postgres backup.dump

# 3. Verify RLS policies still enforce
# 4. Re-run affected scans/verifications
```

### 5.2 Scenario: Schema Migration Failure

**Example:** `alembic upgrade head` fails halfway

**Recovery:**
```bash
# 1. Check migration state
alembic current

# 2. If partial: Manual cleanup or Supabase PITR to pre-migration
# 3. Fix migration script
# 4. Retry: alembic upgrade head
```

**Prevention:**
- Test migrations on staging Supabase project first
- Use `alembic upgrade head --sql` to review SQL first
- Advisory lock during migration (see `RAILWAY_DEPLOYMENT.md`)

### 5.3 Scenario: Full Database Loss (Region Outage)

**Recovery:**
1. Provision new Supabase project in different region
2. Restore from latest PITR snapshot
3. Update `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_*` secrets in Railway
4. Redeploy API/Worker services
4. Verify DNS/CDN updated
5. Run smoke tests

**RTO Target:** <2 hours (depends on Supabase restore speed)

### 5.4 Scenario: Ransomware / Malicious Deletion

**Detection:** Unusual `DELETE FROM` in audit logs, mass `dropped_at` timestamps

**Recovery:**
1. **Immediately:** Enable Supabase read-only mode (if available) or revoke service role key
2. Identify last known good timestamp from audit logs
3. Supabase PITR restore to that timestamp
4. Audit all workspaces for data integrity
5. Rotate ALL secrets (DB, Firebase, AI, SMTP)
6. Force re-auth for all users (revoke Firebase sessions)

### 5.5 Scenario: Cross-Workspace Data Leak (RLS Failure)

**Detection:** Audit logs show `workspace_id` mismatch

**Recovery:**
1. Identify affected workspaces and time window
2. Export affected data for forensic analysis
3. If data corrupted: Restore affected tables from backup
4. Root cause: Service role misuse? Migration gap? App bug?
5. Implement additional app-layer validation

---

## 6. Retention Policies

### 6.1 Data Retention Schedule

| Data Category | Retention | Legal Basis | Disposal Method |
|---------------|-----------|-------------|-----------------|
| Audit logs | 7 years | SOC2, GDPR Art. 30 | Hard delete |
| Security findings & evidence | 3 years | Security trend analysis | Anonymize → delete |
| Scan artifacts (raw output) | 90 days | Operational | Delete |
| Remediation patches | 3 years | Audit trail | Anonymize → delete |
| Verification baselines | 1 year | Regression analysis | Delete |
| Reports (generated) | 1 year | Compliance | Delete from storage |
| Event outbox (processed) | 30 days | Debugging | Delete |
| Notification deliveries | 90 days | Delivery proof | Delete |
| AI analysis outputs | 2 years | Model improvement | Anonymize → delete |
| User PII (profiles) | Account lifetime + 30 days | GDPR Art. 17 | Anonymize on delete |

### 6.2 Automated Retention Enforcement

**To Be Implemented:** Scheduled job (pg_cron or Celery beat)

```sql
-- Example: Delete old scan_events
DELETE FROM scan_events
WHERE created_at < NOW() - INTERVAL '2 years'
AND scan_id IN (SELECT id FROM scans WHERE status IN ('completed', 'failed', 'cancelled'));

-- Example: Anonymize old findings
UPDATE findings SET
    code_snippet = '[REDACTED]',
    location = '{}',
    description = 'Finding from ' || EXTRACT(YEAR FROM created_at)::text
WHERE created_at < NOW() - INTERVAL '3 years'
AND status IN ('fixed', 'false_positive', 'wont_fix', 'risk_accepted');
```

---

## 7. Recovery Testing

### 7.1 Test Schedule

| Test | Frequency | Method | Success Criteria |
|------|-----------|--------|------------------|
| Supabase PITR restore | Quarterly | New project from backup | Schema valid, RLS works, data consistent |
| Logical dump restore | Monthly | `pg_restore` to test DB | All tables restored, FKs valid |
| Volume snapshot restore | Quarterly | Attach snapshot to test worker | Scanner runs, finds test fixtures |
| Report storage sync | Monthly | `aws s3 sync` to test bucket | 100% objects, checksums match |
| Full DR drill | Semi-annually | New region, new project | RTO <2 hours, RPO <1 hour |

### 7.2 Test Documentation

Each test must produce:
- Test plan (scenario, steps, expected outcome)
- Execution log (timestamp, commands, output)
- Result (PASS/FAIL)
- Issues found and remediation tickets
- Sign-off by Security Lead

---

## 8. Responsibilities

| Role | Responsibility |
|------|----------------|
| **Security Lead** | Define retention policies, approve recovery tests, incident evidence preservation |
| **DevOps/Platform** | Configure Supabase backups, Railway volumes, test restores |
| **Backend Engineers** | Implement retention jobs, ensure migrations are reversible |
| **Compliance/Legal** | Validate retention against regulations, approve disposal |

---

## 9. Disaster Recovery Runbook

### 9.1 Quick Reference Card

```
DR TRIGGER: Supabase region down / Data corruption / Ransomware

1. ASSESS (5 min)
   - Confirm scope: Single workspace? All workspaces? Schema? Data?
   - Check Supabase status page
   - Check audit_logs for malicious activity

2. CONTAIN (10 min)
   - Revoke SUPABASE_SERVICE_ROLE_KEY (rotate in Railway)
   - Enable read-only if possible
   - Snapshot current state (even if corrupted) for forensics

3. RECOVER (30-120 min)
   - Option A: PITR restore (preferred, <1 hour)
     → Supabase Dashboard → Backups → Restore to timestamp
   - Option B: New project + logical dump (if PITR unavailable)
     → Create project → pg_restore → Update secrets → Redeploy

4. VERIFY (15 min)
   - Run smoke tests: auth, scan, AI, verification
   - Check RLS: SELECT * FROM findings WHERE workspace_id = 'other_ws' → 0 rows
   - Verify audit_logs writing

5. COMMUNICATE
   - Internal: #incident channel, status page
   - Customers: If data exposed (GDPR 72h)

6. POST-INCIDENT (24-72h)
   - Root cause analysis
   - Update runbook
   - Schedule preventive work
```

---

## 10. Compliance Mapping

| Requirement | Implementation | Evidence |
|-------------|----------------|----------|
| SOC2 CC6.1 (Logical Access) | RLS + App-layer auth | Audit logs, RLS policies |
| SOC2 CC7.2 (System Monitoring) | Structured logs, alerts | Log samples, alert config |
| SOC2 CC8.1 (Change Management) | Migration review, CI/CD | PR approvals, migration logs |
| GDPR Art. 32 (Security) | Encryption at rest/transit | Supabase TLS, Railway TLS |
| GDPR Art. 17 (Right to Erasure) | Profile anonymization job | Anonymization script, audit |
| GDPR Art. 30 (Records of Processing) | Audit logs, data inventory | `audit_logs` table, this doc |

---

## 11. References

- `docs/SECURITY_AUDIT.md` — Security findings affecting backup
- `docs/INCIDENT_RESPONSE.md` — Incident procedures
- `docs/RAILWAY_DEPLOYMENT.md` — Deployment rollback
- Supabase Backup Docs: https://supabase.com/docs/guides/platform/backups
- Railway Volume Docs: https://docs.railway.app/guides/volumes
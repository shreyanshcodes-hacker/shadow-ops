# SECURITY METRICS METHODOLOGY

## 1. Overview

This document defines the precise methodology for all security metrics displayed in the ShadowOps executive dashboard and reports. Each metric is derived from actual persisted records with explicit data sources, time windows, and aggregation methods.

---

## 2. Metric Definitions

### 2.1 Asset Metrics

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Total Assets** | Count of non-deleted assets in workspace | `Asset` table (`deleted_at IS NULL`) | Current | `COUNT(*)` |
| **Assets with Authorization** | Assets with valid `AssetAuthorization` (status=VERIFIED, not expired) | `AssetAuthorization` join `Asset` | Current | `COUNT(DISTINCT asset_id)` WHERE `status=VERIFIED AND (expires_at IS NULL OR expires_at > NOW())` |
| **Assets by Criticality** | Distribution of assets by `criticality` enum | `Asset.criticality` | Current | `GROUP BY criticality` |
| **Assets by Type** | Distribution of assets by `type` enum | `Asset.type` | Current | `GROUP BY type` |
| **Assets by Status** | Distribution of assets by `status` enum | `Asset.status` | Current | `GROUP BY status` |

**Authorization Validity**: An authorization is valid iff:
- `status = VERIFIED`
- `expires_at IS NULL OR expires_at > NOW()`

---

### 2.2 Scan Metrics

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Total Scans** | All scans in workspace | `Scan` table | Current | `COUNT(*)` |
| **Scans Completed** | Scans with `status = COMPLETED` | `Scan.status` | Current | `COUNT(*) WHERE status=COMPLETED` |
| **Scans Failed** | Scans with `status = FAILED` | `Scan.status` | Current | `COUNT(*) WHERE status=FAILED` |
| **Scans Running** | Scans with `status = RUNNING` | `Scan.status` | Current | `COUNT(*) WHERE status=RUNNING` |
| **Latest Completed Scan** | Most recent `completed_at` among completed scans | `Scan.completed_at` | Current | `MAX(completed_at) WHERE status=COMPLETED` |

**Note**: Scans with `status = QUEUED`, `PARTIAL`, `CANCELLED` are not counted in completed/failed/running.

---

### 2.3 Finding Metrics

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Total Findings** | All findings in workspace | `Finding` table | Current | `COUNT(*)` |
| **Open Findings by Severity** | Findings with `status = OPEN` grouped by `severity` | `Finding` WHERE `status=OPEN` | Current | `GROUP BY severity` |
| **Findings by Status** | Distribution of all findings by `status` | `Finding.status` | Current | `GROUP BY status` |
| **Findings by Source** | Distribution of all findings by `source` | `Finding.source` | Current | `GROUP BY source` |

**Severity Levels**: `critical`, `high`, `medium`, `low`, `info` (all enum values always present in output, zero if none)

**Status Values**: `open`, `triaged`, `in_progress`, `fixed`, `false_positive`, `wont_fix`, `risk_accepted`

**Source Values**: `semgrep`, `recon`, `dependency`, `ai_analysis`, `manual`

---

### 2.4 Risk Metrics

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Current Risk Score** | Maximum `risk_score` among active attack paths (status=ACTIVE or DRAFT) | `AttackPath.risk_score` | Current | `MAX(risk_score) WHERE status IN (ACTIVE, DRAFT)` |
| **Risk Model Version** | `risk_model_version` from latest attack path | `AttackPath.risk_model_version` | Current | First non-null |
| **Attack Paths by Status** | Distribution of attack paths by `status` | `AttackPath.status` | Current | `GROUP BY status` |
| **Attack Paths by Severity/Risk Band** | Distribution by `severity` / `risk_band` | `AttackPath.severity`, `risk_band` | Current | `GROUP BY` |

**Risk Bands**: `informational`, `low`, `medium`, `high`, `critical` (from deterministic risk engine v1)

**Attack Path Status**: `draft`, `active`, `dismissed`, `resolved`

**Risk Score Calculation**: Deterministic risk engine (v1) based on attack path topology, finding severities, exploitability, and asset criticality. See `RISK_ENGINE.md`.

---

### 2.5 Remediation Metrics

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Total Proposals** | All remediation proposals | `RemediationProposal` | Current | `COUNT(*)` |
| **Proposals by Status** | Distribution by `status` enum | `RemediationProposal.status` | Current | `GROUP BY status` |
| **Approved Count** | Approvals with `decision = approved` | `RemediationApproval` | Current | `COUNT(*) WHERE decision=approved` |
| **Applied Count** | Applications with `status = PATCH_APPLIED` | `RemediationApplication` | Current | `COUNT(*) WHERE status=PATCH_APPLIED` |
| **Rejected Count** | Approvals with `decision = rejected` | `RemediationApproval` | Current | `COUNT(*) WHERE decision=rejected` |

**Remediation Status Flow**: `DRAFT → GENERATING → PROPOSED → VALIDATING → VALIDATION_FAILED|AWAITING_APPROVAL → APPROVED → APPLYING → APPLIED|FAILED → VERIFIED`

**Approval Decision**: `approved` or `rejected`

**Application Status**: `PENDING`, `CHECKPOINT_CREATED`, `PATCH_APPLIED`, `VERIFIED`, `FAILED`, `ROLLED_BACK`

---

### 2.6 Verification Metrics (Stage 9)

| Metric | Definition | Data Source | Time Window | Aggregation |
|--------|------------|-------------|-------------|-------------|
| **Jobs by Status** | Verification jobs by `status` | `VerificationJob.status` | Current | `GROUP BY status` |
| **Outcomes** | Jobs with `overall_outcome` | `VerificationJob.overall_outcome` | Current | `GROUP BY overall_outcome` |
| **Regression Failures** | Checks of type REGRESSION_ANALYSIS or TEST_EXECUTION with `status = FAILED` | `VerificationCheck` JOIN `VerificationJob` | Current | `COUNT(*) WHERE check_type IN (REGRESSION_ANALYSIS, TEST_EXECUTION) AND status=FAILED` |
| **Pending Review** | Jobs with `status = PASSED_PENDING_REVIEW` | `VerificationJob.status` | Current | `COUNT(*) WHERE status=PASSED_PENDING_REVIEW` |

**Verification Status**: `QUEUED`, `RUNNING`, `BASELINE_CHECK`, `RESCANNING`, `REGRESSION_CHECK`, `COMPARING_EVIDENCE`, `PASSED_PENDING_REVIEW`, `VERIFIED`, `FAILED`, `INCONCLUSIVE`, `BLOCKED`, `CANCELED`

**Verification Outcome**: `VERIFIED_CANDIDATE`, `FAILED`, `INCONCLUSIVE`, `BLOCKED`

**Check Types**: `ORIGINAL_VULNERABILITY`, `REGRESSION_ANALYSIS`, `SCANNER_EXECUTION`, `TEST_EXECUTION`, `EVIDENCE_COMPARISON`

**Check Status**: `PENDING`, `RUNNING`, `PASSED`, `FAILED`, `SKIPPED`, `BLOCKED`, `ERROR`

---

## 3. Historical Trend Methodology

### 3.1 Time Bucketing

- **Default**: 30 buckets across the selected period
- **Minimum bucket size**: 1 hour
- **Period presets**: 7d, 30d, 90d, 1y
- **Timezone**: UTC (all timestamps stored as UTC)

### 3.2 Finding Count Trends

**Total Findings Over Time**:
- A finding is "active" in a bucket if: `first_seen_at ≤ bucket_end` AND (`fixed_at IS NULL OR fixed_at ≥ bucket_start`) AND (`last_seen_at ≥ bucket_start OR fixed_at IS NULL`)
- Uses `first_seen_at`, `last_seen_at`, `fixed_at` from `Finding` table

**Open Findings Over Time**:
- Same as total but filtered to `status = OPEN` at bucket time
- Note: Finding status history not stored; approximates using current status + timestamps

**New vs Resolved**:
- **New**: `first_seen_at` falls within bucket
- **Resolved**: `fixed_at` falls within bucket (status changed to FIXED)

**By Severity**: Filtered by `Finding.severity` before bucket assignment

### 3.3 Risk Score Trends

**Source**: `RiskSnapshot` table (one row per attack path per calculation)
- Each snapshot has `calculated_at` and `score`
- Per bucket: Average of latest score per attack path within bucket
- If no snapshots in period: Returns empty with limitation notice

### 3.4 Scan Trends

**Completed**: `Scan.completed_at` in bucket, `status = COMPLETED`
**Failed**: `Scan.failed_at` in bucket, `status = FAILED`

### 3.5 Remediation Trends

**Proposed**: `RemediationProposal.created_at` in bucket
**Approved**: `RemediationApproval.approved_at` in bucket, `decision = approved`
**Applied**: `RemediationApplication.applied_at` in bucket, `status = PATCH_APPLIED`

### 3.6 Verification Trends

**Verified**: `VerificationJob.completed_at` in bucket, `overall_outcome = VERIFIED_CANDIDATE`
**Failed**: `VerificationJob.completed_at` in bucket, `overall_outcome = FAILED`
**Inconclusive**: `VerificationJob.completed_at` in bucket, `overall_outcome = INCONCLUSIVE`

---

## 4. Data Quality & Limitations

### 4.1 Explicit Limitations

| Limitation | Affected Metrics | Disclosure |
|------------|------------------|------------|
| No historical finding status | Open findings over time | "Open findings trend approximated from timestamps" |
| No asset-level risk history | Asset risk trends | "Risk trends only available per attack path" |
| Finding status not historized | New vs resolved accuracy | "Resolved count based on fixed_at timestamp" |
| Stage 9 data only since implementation | Verification trends | "Verification data only available since Stage 9 deployment" |

### 4.2 Missing Data vs Zero

**Critical Distinction**: The dashboard explicitly distinguishes:
- **No data available** → Shows "N/A" or "No data" with explanation
- **Zero count** → Shows "0" with context

Example: A workspace with 0 scans shows "0 scans completed" (not "no scan data").

### 4.3 Incomplete Data Handling

| Scenario | Handling |
|----------|----------|
| No scans completed | `scans: false` in completeness; "No scans completed" in limitations |
| No risk snapshots | Risk trend returns empty with "No risk snapshots available" |
| Insufficient trend points (< 2) | Limitation: "Insufficient data points for trend calculation" |
| AI unavailable | Narrative omitted; metrics unchanged; "AI narrative unavailable" noted |

---

## 5. Report-Specific Methodology

### 5.1 Executive Summary Posture Calculation

```
IF critical_findings > 0 OR risk_score ≥ 70:
    posture = "Critical"
ELIF high_findings > 2 OR risk_score ≥ 50:
    posture = "High Risk"
ELIF high_findings > 0 OR risk_score ≥ 30:
    posture = "Medium Risk"
ELSE:
    posture = "Low Risk"
```

**Based on**: Deterministic risk engine (risk-v1) + open critical/high findings count

### 5.2 Completeness Calculation

Each domain `true` iff at least one record exists in reporting period:
- `assets`: `COUNT(Asset) > 0`
- `scans`: `COUNT(Scan WHERE completed_at IN period) > 0`
- `findings`: `COUNT(Finding WHERE first_seen_at IN period) > 0`
- `risk`: `COUNT(RiskSnapshot WHERE calculated_at IN period) > 0`
- `remediation`: `COUNT(RemediationProposal WHERE created_at IN period) > 0`
- `verification`: `COUNT(VerificationJob WHERE created_at IN period) > 0`

---

## 6. API Response Formats

### 6.1 Dashboard Metrics
```typescript
interface DashboardMetrics {
  workspace_id: string;
  assets: { total_assets, assets_with_authorization, assets_by_criticality, assets_by_type, assets_by_status };
  scans: { total_scans, scans_completed, scans_failed, scans_running, latest_completed_scan_at };
  findings: { total_findings, open_findings_by_severity, findings_by_status, findings_by_source };
  risk: { current_risk_score, risk_model_version, attack_paths_by_status, attack_paths_by_severity, total_attack_paths };
  remediation: { total_proposals, remediation_proposals_by_status, remediation_approved, remediation_applied, remediation_rejected };
  verification: { verification_jobs_by_status, verification_outcomes, regression_failures, latest_verification_at };
  activity: { latest_scan_at, latest_finding_at, latest_remediation_at };
  metadata: { workspace_id, generated_at, data_cutoff };
}
```

### 6.2 Trend Response
```typescript
interface TrendResponse {
  trends: TrendSeries[];
  generated_at: ISO8601;
  data_cutoff: ISO8601;
}

interface TrendSeries {
  metric_name: string;
  metric_label: string;
  unit: string;
  data_points: { timestamp: ISO8601; value: number; label: string }[];
  data_source: string;
  aggregation_method: string;
  time_window: string;
  limitations: string|null;
}
```

---

## 7. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-10-13 | Initial methodology documentation |

---

*Methodology Version: 1.0*
*Last Updated: 2026-10-13*
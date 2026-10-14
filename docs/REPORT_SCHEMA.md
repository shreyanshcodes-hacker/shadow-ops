# REPORT SCHEMA

## 1. Overview

This document defines the stable JSON schema for ShadowOps security reports (version `report-v1`). The schema is used for:
- JSON exports
- API responses
- Report storage snapshots
- Programmatic consumption

---

## 2. Root Report Object

```json
{
  "report": {
    "id": "uuid",
    "workspace_id": "uuid",
    "report_type": "executive_summary|technical_vulnerability|remediation_progress|verification_regression|asset_security_posture",
    "title": "string",
    "description": "string|null",
    "format": "pdf|json",
    "schema_version": "report-v1",
    "risk_engine_version": "risk-v1",
    "verification_policy_version": "verification-policy-v1",
    "period_start": "ISO8601|null",
    "period_end": "ISO8601|null",
    "data_cutoff": "ISO8601",
    "generated_by": "uuid",
    "created_at": "ISO8601",
    "started_at": "ISO8601|null",
    "completed_at": "ISO8601|null",
    "expires_at": "ISO8601|null",
    "status": "pending|generating|ready|failed|expired",
    "storage_path": "string|null",
    "file_size_bytes": "int|null",
    "checksum": "sha256_hex|null",
    "error_message": "string|null"
  },
  "sections": [
    {
      "section_key": "string",
      "section_title": "string",
      "section_order": "int",
      "content": {},
      "data_references": {}
    }
  ],
  "completeness": {
    "assets": "bool",
    "scans": "bool",
    "findings": "bool",
    "risk": "bool",
    "remediation": "bool",
    "verification": "bool"
  },
  "limitations": ["string"],
  "source_record_references": {}
}
```

---

## 3. Section Schemas by Report Type

### 3.1 Executive Security Summary (`executive_summary`)

| Section Key | Title | Content Structure |
|-------------|-------|-------------------|
| `executive_overview` | Executive Overview | `{summary, period, key_metrics}` |
| `security_posture` | Overall Security Posture | `{overall_posture, methodology, risk_score, risk_model_version, contributing_factors}` |
| `critical_risks` | Most Important Current Risks | `{risks: [{title, count, impact}]}` |
| `critical_findings` | Critical and High-Severity Findings | `{count, findings: [{id, title, severity, asset_id, source, source_rule_id, location, first_seen_at, risk_score, has_ai_analysis, remediation_status}]}` |
| `attack_paths` | Important Attack Paths | `{count, paths: [{id, title, risk_score, severity, risk_band, status, node_count}]}` |
| `remediation_progress` | Remediation Progress | `{summary, by_status, approval_rate, application_rate}` |
| `verification_outcomes` | Verification Outcomes | `{summary, outcomes, regression_failures, pending_review}` |
| `unresolved_risks` | Unresolved Risks | `{open_critical_findings, open_high_findings, unverified_remediations, regression_failures, unauthorized_assets}` |
| `recommended_actions` | Recommended Next Actions | `{actions: [{priority, action, details}]}` |
| `scope_limitations` | Scope, Date Range & Limitations | `{report_scope, limitations, completeness}` |

**Finding Object (in critical_findings):**
```json
{
  "id": "uuid",
  "title": "string",
  "severity": "critical|high|medium|low|info",
  "asset_id": "uuid",
  "source": "semgrep|recon|dependency|ai_analysis|manual",
  "source_rule_id": "string|null",
  "location": "object|null",
  "first_seen_at": "ISO8601|null",
  "risk_score": "float|null",
  "has_ai_analysis": "bool",
  "remediation_status": "string|null"
}
```

**Attack Path Object:**
```json
{
  "id": "uuid",
  "title": "string",
  "risk_score": "int|null",
  "severity": "string",
  "risk_band": "informational|low|medium|high|critical",
  "status": "draft|active|dismissed|resolved",
  "node_count": "int"
}
```

### 3.2 Technical Vulnerability Report (`technical_vulnerability`)

| Section Key | Content |
|-------------|---------|
| `executive_summary` | Brief overview |
| `findings` | Array of detailed finding objects |
| `evidence` | Evidence references per finding |
| `ai_analysis` | AI analysis per finding (advisory) |
| `remediation_status` | Proposal/approval/application per finding |
| `verification_outcomes` | Verification job results per finding |
| `methodology` | Data sources, limitations |

**Detailed Finding Object:**
```json
{
  "id": "uuid",
  "fingerprint": "sha256_hex",
  "title": "string",
  "description": "string",
  "severity": "critical|high|medium|low|info",
  "confidence": "low|medium|high",
  "source": "semgrep|recon|dependency|ai_analysis|manual",
  "source_rule_id": "string|null",
  "asset_id": "uuid",
  "asset_name": "string",
  "location": "object|null",
  "code_snippet": "string|null",
  "cwe_ids": ["string"],
  "cve_ids": ["string"],
  "owasp_categories": ["string"],
  "remediation_guidance": "string|null",
  "status": "open|triaged|in_progress|fixed|false_positive|wont_fix|risk_accepted",
  "risk_score": "float|null",
  "risk_factors": "object",
  "first_seen_at": "ISO8601",
  "last_seen_at": "ISO8601",
  "fixed_at": "ISO8601|null",
  "evidence": [
    {
      "id": "uuid",
      "type": "code_snippet|screenshot|log|request_response|config|dependency_tree|ai_reasoning|static_analysis|source_location|rule_match|scan_output",
      "title": "string",
      "content": "object",
      "file_path": "string|null",
      "line_start": "int|null",
      "line_end": "int|null"
    }
  ],
  "ai_analysis": {
    "summary": "string",
    "vulnerability_type": "string",
    "severity_assessment": "string",
    "confidence": "float",
    "exploitability": "string",
    "impact": "string",
    "affected_component": "string",
    "attack_preconditions": "string",
    "evidence_interpretation": "string",
    "reasoning": "string",
    "recommended_next_steps": ["string"],
    "uncertainty": "string",
    "advisory": "AI-generated — advisory only"
  } | null,
  "remediation": {
    "proposal_id": "uuid|null",
    "status": "DRAFT|GENERATING|PROPOSED|VALIDATING|VALIDATION_FAILED|AWAITING_APPROVAL|APPROVED|APPLYING|APPLIED|REJECTED|EXPIRED|ROLLED_BACK|FAILED",
    "fix_type": "code_change|config_change|dependency_update|infrastructure_change|waf_rule|network_policy|secret_rotation",
    "approval_status": "approved|rejected|null",
    "applied_at": "ISO8601|null",
    "verification_outcome": "VERIFIED_CANDIDATE|FAILED|INCONCLUSIVE|BLOCKED|null"
  } | null
}
```

### 3.3 Remediation Progress Report (`remediation_progress`)

| Section Key | Content |
|-------------|---------|
| `summary` | Counts by status, rates |
| `proposals` | Array of remediation proposals with full lifecycle |
| `approvals` | Approval decisions with justifications |
| `applications` | Patch applications with results |
| `rollbacks` | Rollback history |
| `validation_results` | Per-proposal validation outcomes |

**Remediation Proposal Object:**
```json
{
  "id": "uuid",
  "title": "string",
  "fix_type": "code_change|config_change|dependency_update|infrastructure_change|waf_rule|network_policy|secret_rotation",
  "finding_id": "uuid",
  "finding_title": "string",
  "severity": "critical|high|medium|low|info",
  "status": "DRAFT|GENERATING|PROPOSED|VALIDATING|VALIDATION_FAILED|AWAITING_APPROVAL|APPROVED|APPLYING|APPLIED|REJECTED|EXPIRED|ROLLED_BACK|FAILED",
  "created_at": "ISO8601",
  "approved_at": "ISO8601|null",
  "applied_at": "ISO8601|null",
  "validation_results": {"patch_integrity": "PASSED", "semgrep_rescan": "BLOCKED", ...},
  "approval": {
    "decision": "approved|rejected",
    "approved_by": "uuid",
    "approved_at": "ISO8601",
    "justification": "string"
  } | null,
  "application": {
    "applied_by": "uuid",
    "applied_at": "ISO8601",
    "result_diff": "string|null",
    "changed_files": ["string"]
  } | null,
  "verification": {
    "job_id": "uuid",
    "outcome": "VERIFIED_CANDIDATE|FAILED|INCONCLUSIVE|BLOCKED",
    "human_decision": "accept|reject|rerun_requested|null"
  } | null
}
```

### 3.4 Verification & Regression Report (`verification_regression`)

| Section Key | Content |
|-------------|---------|
| `summary` | Verification job counts by status/outcome |
| `verification_jobs` | Array of verification job details |
| `evidence_comparisons` | Comparison results (STILL_PRESENT, NO_LONGER_DETECTED, etc.) |
| `regression_checks` | Check results (PASSED/FAILED/SKIPPED/BLOCKED/ERROR) |
| `human_reviews` | Review decisions with justifications |

**Verification Job Object:**
```json
{
  "id": "uuid",
  "finding_id": "uuid",
  "finding_title": "string",
  "status": "QUEUED|RUNNING|BASELINE_CHECK|RESCANNING|REGRESSION_CHECK|COMPARING_EVIDENCE|PASSED_PENDING_REVIEW|VERIFIED|FAILED|INCONCLUSIVE|BLOCKED|CANCELED",
  "overall_outcome": "VERIFIED_CANDIDATE|FAILED|INCONCLUSIVE|BLOCKED|null",
  "checks": [
    {
      "check_type": "ORIGINAL_VULNERABILITY|REGRESSION_ANALYSIS|SCANNER_EXECUTION|TEST_EXECUTION|EVIDENCE_COMPARISON",
      "name": "string",
      "status": "PENDING|RUNNING|PASSED|FAILED|SKIPPED|BLOCKED|ERROR",
      "duration_ms": "int|null",
      "command": "string|null"
    }
  ],
  "comparisons": [
    {
      "rule_id": "string",
      "file_path": "string",
      "category": "STILL_PRESENT|NO_LONGER_DETECTED|MODIFIED_OR_MOVED|POSSIBLE_REGRESSION|NEW_FINDING|UNCOMPARABLE",
      "match_confidence": "float|null",
      "rationale": "string"
    }
  ],
  "review": {
    "decision": "accept|reject|rerun_requested",
    "reviewed_by": "uuid",
    "reviewed_at": "ISO8601",
    "justification": "string"
  } | null,
  "completed_at": "ISO8601|null"
}
```

### 3.5 Asset Security Posture Report (`asset_security_posture`)

| Section Key | Content |
|-------------|---------|
| `summary` | Asset counts, authorization coverage |
| `assets` | Per-asset detail |
| `scan_coverage` | Scan history per asset |
| `finding_distribution` | Findings by asset |

**Asset Detail Object:**
```json
{
  "id": "uuid",
  "name": "string",
  "type": "repository|api|infrastructure|application|container",
  "criticality": "low|medium|high|critical",
  "status": "active|archived|error",
  "authorization": {
    "status": "pending|verified|rejected|expired",
    "type": "ownership|written_permission|bug_bounty|internal",
    "expires_at": "ISO8601|null"
  },
  "scans": {
    "total": "int",
    "last_scan_at": "ISO8601|null",
    "last_status": "completed|failed|running|null"
  },
  "findings": {
    "total": "int",
    "open": "int",
    "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
  },
  "risk_score": "int|null",
  "risk_band": "informational|low|medium|high|critical|null"
}
```

---

## 4. Common Objects

### 4.1 Completeness Object
```json
{
  "assets": true,
  "scans": true,
  "findings": true,
  "risk": true,
  "remediation": true,
  "verification": true
}
```
Each boolean indicates whether that data domain has any records in the reporting period.

### 4.2 Limitations Array
```json
[
  "Report reflects data as of the data cutoff timestamp.",
  "AI analysis requires configured API keys (may be unavailable).",
  "Scanner results require completed scans.",
  "Historical trends limited to available snapshot data.",
  "No scans completed in this workspace; vulnerability data may be incomplete."
]
```

### 4.3 Source Record References
```json
{
  "metrics_timestamp": "ISO8601",
  "asset_count": 10,
  "scan_count": 25,
  "finding_count": 142,
  "attack_path_count": 5,
  "remediation_count": 12,
  "verification_count": 8
}
```

### 4.4 Data References (Per Section)
```json
{
  "findings": ["uuid1", "uuid2", ...],
  "attack_paths": ["uuid1", "uuid2", ...],
  "remediation_proposals": ["uuid1", ...],
  "verification_jobs": ["uuid1", ...]
}
```

---

## 5. Export File Naming

### 5.1 JSON Export
```
{workspace_id}/{report_id}/report.json
```

### 5.2 PDF Export
```
{workspace_id}/{report_id}/report.pdf
```

---

## 6. Schema Versioning

| Version | Date | Changes |
|---------|------|---------|
| `report-v1` | 2026-10-13 | Initial release |

**Versioning Policy**:
- Minor changes (new optional fields): Same version
- Breaking changes: Increment version (`report-v2`)
- Version included in every report and export

---

## 7. Validation Rules

| Field | Rule |
|-------|------|
| `report.id` | Valid UUID v4 |
| `report.workspace_id` | Valid UUID, matches export path |
| `report.report_type` | One of 5 defined types |
| `report.format` | `pdf` or `json` |
| `report.status` | One of 5 statuses |
| `report.data_cutoff` | Valid ISO8601, <= generated_at |
| `section.section_order` | Positive integer, unique per report |
| `checksum` | SHA256 of file content (64 hex chars) |
| `file_size_bytes` | Matches actual file size |

---

## 8. Example Minimal Report

```json
{
  "report": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "workspace_id": "550e8400-e29b-41d4-a716-446655440001",
    "report_type": "executive_summary",
    "title": "Q4 2024 Security Summary",
    "description": "Quarterly executive security report",
    "format": "pdf",
    "schema_version": "report-v1",
    "risk_engine_version": "risk-v1",
    "verification_policy_version": "verification-policy-v1",
    "period_start": "2024-10-01T00:00:00Z",
    "period_end": "2024-12-31T23:59:59Z",
    "data_cutoff": "2025-01-15T10:30:00Z",
    "generated_by": "550e8400-e29b-41d4-a716-446655440002",
    "created_at": "2025-01-15T10:30:00Z",
    "started_at": "2025-01-15T10:30:05Z",
    "completed_at": "2025-01-15T10:30:45Z",
    "expires_at": "2025-02-14T10:30:00Z",
    "status": "ready",
    "storage_path": "reports/550e8400-e29b-41d4-a716-446655440001/550e8400-e29b-41d4-a716-446655440000/report.pdf",
    "file_size_bytes": 245760,
    "checksum": "a1b2c3d4e5f6...",
    "error_message": null
  },
  "sections": [
    {
      "section_key": "executive_overview",
      "section_title": "Executive Overview",
      "section_order": 1,
      "content": {
        "summary": "Security assessment for workspace covering 10 assets, 25 scans, and 142 findings.",
        "period": {"start": "2024-10-01T00:00:00Z", "end": "2024-12-31T23:59:59Z"},
        "key_metrics": {
          "assets_monitored": 10,
          "authorized_assets": 8,
          "open_findings": 23,
          "critical_findings": 2,
          "high_findings": 5,
          "active_attack_paths": 2,
          "pending_remediations": 3,
          "verification_pending": 1
        }
      },
      "data_references": {"assets": ["..."], "scans": ["..."]}
    }
  ],
  "completeness": {
    "assets": true,
    "scans": true,
    "findings": true,
    "risk": true,
    "remediation": true,
    "verification": true
  },
  "limitations": [
    "Report reflects data as of the data cutoff timestamp.",
    "AI analysis requires configured API keys (may be unavailable)."
  ],
  "source_record_references": {
    "metrics_timestamp": "2025-01-15T10:30:00Z",
    "asset_count": 10,
    "scan_count": 25,
    "finding_count": 142,
    "attack_path_count": 5,
    "remediation_count": 12,
    "verification_count": 8
  }
}
```

---

*Schema Version: report-v1*
*Last Updated: 2026-10-13*
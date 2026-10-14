# EVENT CATALOG

## 1. Overview

This document defines all supported event types in the ShadowOps notification system. Each event type has a versioned schema and is used to trigger notifications and workflows.

Events are emitted via the `emit_event()` function and stored in the `event_outbox` table for reliable processing.

---

## 2. Event Envelope Schema

All events share a common envelope structure:

```json
{
  "event_id": "uuid",
  "event_type": "finding.created",
  "event_version": "1.0",
  "correlation_id": "uuid",
  "occurred_at": "2026-10-14T10:30:00Z",
  "workspace_id": "uuid",
  "actor_id": "uuid",
  "resource_type": "finding",
  "resource_id": "uuid",
  "payload": { ... }
}
```

**Fields**:
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| event_id | UUID | Yes | Unique event identifier |
| event_type | string | Yes | Event type from allowlist |
| event_version | string | Yes | Schema version (semver) |
| correlation_id | UUID | No | Links related events |
| occurred_at | ISO8601 | Yes | Event timestamp |
| workspace_id | UUID | Yes | Workspace context |
| actor_id | UUID | No | User who triggered event |
| resource_type | string | No | Resource type (finding, scan, etc.) |
| resource_id | UUID | No | Resource identifier |
| payload | object | Yes | Event-specific data |

---

## 3. Event Types

### 3.1 Scan Events

#### `scan.completed` (v1.0)
Emitted when a scan completes successfully.

**Payload**:
```json
{
  "scan_id": "uuid",
  "asset_id": "uuid",
  "scan_type": "code",
  "findings_count": 42,
  "critical": 2,
  "high": 5,
  "medium": 15,
  "low": 12,
  "info": 8,
  "duration_ms": 125000
}
```

#### `scan.failed` (v1.0)
Emitted when a scan fails.

**Payload**:
```json
{
  "scan_id": "uuid",
  "asset_id": "uuid",
  "scan_type": "code",
  "error_message": "Semgrep timeout after 300s",
  "error_code": "TIMEOUT",
  "phase": "semgrep_scan",
  "duration_ms": 300000
}
```

#### `scan.cancelled` (v1.0)
Emitted when a scan is cancelled by user.

**Payload**:
```json
{
  "scan_id": "uuid",
  "asset_id": "uuid",
  "cancelled_by": "uuid",
  "reason": "User requested cancellation",
  "phase": "semgrep_scan"
}
```

---

### 3.2 Finding Events

#### `finding.created` (v1.0)
Emitted when a new finding is created (from scan or manual).

**Payload**:
```json
{
  "finding_id": "uuid",
  "scan_id": "uuid",
  "asset_id": "uuid",
  "title": "SQL Injection in login endpoint",
  "severity": "critical",
  "confidence": "high",
  "source": "semgrep",
  "source_rule_id": "sql-injection",
  "cwe_ids": ["CWE-89"],
  "location": {"path": "src/auth/login.py", "start_line": 42},
  "risk_score": 95.5
}
```

#### `finding.severity_changed` (v1.0)
Emitted when a finding's severity is updated.

**Payload**:
```json
{
  "finding_id": "uuid",
  "old_severity": "high",
  "new_severity": "critical",
  "changed_by": "uuid",
  "reason": "Re-evaluated after manual review"
}
```

#### `finding.status_changed` (v1.0)
Emitted when a finding's status changes.

**Payload**:
```json
{
  "finding_id": "uuid",
  "old_status": "open",
  "new_status": "triaged",
  "changed_by": "uuid"
}
```

#### `finding.triaged` (v1.0)
Emitted when a finding is triaged by a user.

**Payload**:
```json
{
  "finding_id": "uuid",
  "triaged_by": "uuid",
  "status": "triaged",
  "notes": "Confirmed valid, assigning to team"
}
```

---

### 3.3 Attack Path Events

#### `attack_path.created` (v1.0)
Emitted when a new attack path is generated.

**Payload**:
```json
{
  "attack_path_id": "uuid",
  "scan_id": "uuid",
  "asset_id": "uuid",
  "title": "Path from web server to database",
  "risk_score": 87.5,
  "node_count": 5,
  "entry_point": "web-server-01",
  "target_asset": "prod-db-01"
}
```

#### `attack_path.status_changed` (v1.0)
Emitted when attack path status changes.

**Payload**:
```json
{
  "attack_path_id": "uuid",
  "old_status": "active",
  "new_status": "mitigated",
  "changed_by": "uuid",
  "reason": "Applied WAF rules to block entry point"
}
```

---

### 3.4 Risk Events

#### `risk_score.changed` (v1.0)
Emitted when an attack path's risk score changes significantly (>10 points).

**Payload**:
```json
{
  "attack_path_id": "uuid",
  "old_score": 75.0,
  "new_score": 88.5,
  "change_reason": "New finding added to path",
  "triggered_by": "finding.created"
}
```

---

### 3.5 Remediation Events

#### `remediation.proposed` (v1.0)
Emitted when an AI remediation proposal is generated.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "finding_id": "uuid",
  "title": "Add parameterized query",
  "fix_type": "code_change",
  "risk_level": "high",
  "proposed_by": "ai"
}
```

#### `remediation.awaiting_approval` (v1.0)
Emitted when a proposal is validated and ready for human approval.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "finding_id": "uuid",
  "title": "Add parameterized query",
  "proposed_by": "ai",
  "validation_passed": true,
  "approvers": ["uuid1", "uuid2"]
}
```

#### `remediation.approved` (v1.0)
Emitted when a remediation proposal is approved.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "approved_by": "uuid",
  "approved_at": "2026-10-14T10:30:00Z",
  "conditions": ["Deploy to staging first"]
}
```

#### `remediation.rejected` (v1.0)
Emitted when a remediation proposal is rejected.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "rejected_by": "uuid",
  "rejected_at": "2026-10-14T10:30:00Z",
  "justification": "Fix introduces breaking change"
}
```

#### `remediation.applied` (v1.0)
Emitted when a remediation patch is applied.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "application_id": "uuid",
  "applied_by": "uuid",
  "applied_at": "2026-10-14T10:35:00Z",
  "changed_files": ["src/auth/login.py"],
  "checkpoint_ref": "stash-abc123"
}
```

#### `remediation.failed` (v1.0)
Emitted when remediation application fails.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "application_id": "uuid",
  "failed_at": "2026-10-14T10:35:00Z",
  "error_message": "Git apply failed: patch does not apply",
  "error_code": "PATCH_APPLY_FAILED"
}
```

#### `remediation.rolled_back` (v1.0)
Emitted when a remediation is rolled back.

**Payload**:
```json
{
  "proposal_id": "uuid",
  "rollback_id": "uuid",
  "rolled_back_by": "uuid",
  "rolled_back_at": "2026-10-14T11:00:00Z",
  "reason": "Introduced regression in tests"
}
```

---

### 3.6 Verification Events

#### `verification.completed` (v1.0)
Emitted when a verification job completes (any outcome).

**Payload**:
```json
{
  "verification_job_id": "uuid",
  "finding_id": "uuid",
  "proposal_id": "uuid",
  "application_id": "uuid",
  "outcome": "VERIFIED_CANDIDATE",
  "checks": {
    "original_vulnerability": "PASSED",
    "scanner_execution": "PASSED",
    "evidence_comparison": "PASSED",
    "regression_analysis": "SKIPPED",
    "test_execution": "PASSED"
  },
  "completed_at": "2026-10-14T10:45:00Z"
}
```

#### `verification.failed` (v1.0)
Emitted when verification outcome is FAILED.

**Payload**:
```json
{
  "verification_job_id": "uuid",
  "finding_id": "uuid",
  "outcome": "FAILED",
  "failed_check": "original_vulnerability",
  "failure_reason": "Original vulnerability still detected in post-patch scan"
}
```

#### `verification.inconclusive` (v1.0)
Emitted when verification outcome is INCONCLUSIVE.

**Payload**:
```json
{
  "verification_job_id": "uuid",
  "finding_id": "uuid",
  "outcome": "INCONCLUSIVE",
  "reason": "Scanner unavailable for re-scan",
  "blocked_checks": ["scanner_execution"]
}
```

#### `verification.review_submitted` (v1.0)
Emitted when a human reviewer submits a decision.

**Payload**:
```json
{
  "verification_job_id": "uuid",
  "reviewed_by": "uuid",
  "decision": "accept",
  "reviewed_at": "2026-10-14T11:00:00Z",
  "justification": "Fix verified in staging environment"
}
```

---

### 3.6 Report Events

#### `report.generated` (v1.0)
Emitted when a report is successfully generated.

**Payload**:
```json
{
  "report_id": "uuid",
  "report_type": "executive_summary",
  "format": "pdf",
  "generated_by": "uuid",
  "period_start": "2026-10-01T00:00:00Z",
  "period_end": "2026-10-31T23:59:59Z",
  "file_size_bytes": 245760
}
```

#### `report.generation_failed` (v1.0)
Emitted when report generation fails.

**Payload**:
```json
{
  "report_id": "uuid",
  "report_type": "technical_vulnerability",
  "error_message": "PDF generation timeout",
  "error_code": "GENERATION_TIMEOUT"
}
```

#### `report.exported` (v1.0)
Emitted when a report export is downloaded.

**Payload**:
```json
{
  "report_id": "uuid",
  "export_id": "uuid",
  "format": "pdf",
  "downloaded_by": "uuid",
  "downloaded_at": "2026-10-14T11:00:00Z"
}
```

---

### 3.7 Security Team Events

#### `security_team.completed` (v1.0)
Emitted when a Security Team run completes.

**Payload**:
```json
{
  "team_run_id": "uuid",
  "asset_id": "uuid",
  "scan_id": "uuid",
  "status": "succeeded",
  "confidence": 0.87,
  "key_findings_count": 3,
  "key_attack_paths_count": 2,
  "completed_at": "2026-10-14T10:30:00Z"
}
```

#### `security_team.review_submitted` (v1.0)
Emitted when a human reviews a Security Team assessment.

**Payload**:
```json
{
  "team_run_id": "uuid",
  "reviewed_by": "uuid",
  "reviewed_at": "2026-10-14T11:00:00Z",
  "notes": "Assessment accurate, proceeding with remediation"
}
```

---

## 3. Event Versioning

| Event Type | Current Version | Notes |
|------------|-----------------|-------|
| scan.completed | 1.0 | |
| scan.failed | 1.0 | |
| scan.cancelled | 1.0 | |
| finding.created | 1.0 | |
| finding.severity_changed | 1.0 | |
| finding.status_changed | 1.0 | |
| finding.triaged | 1.0 | |
| attack_path.created | 1.0 | |
| attack_path.status_changed | 1.0 | |
| risk_score.changed | 1.0 | |
| remediation.proposed | 1.0 | |
| remediation.awaiting_approval | 1.0 | |
| remediation.approved | 1.0 | |
| remediation.rejected | 1.0 | |
| remediation.applied | 1.0 | |
| remediation.failed | 1.0 | |
| remediation.rolled_back | 1.0 | |
| verification.completed | 1.0 | |
| verification.failed | 1.0 | |
| verification.inconclusive | 1.0 | |
| verification.review_submitted | 1.0 | |
| report.generated | 1.0 | |
| report.generation_failed | 1.0 | |
| report.exported | 1.0 | |
| security_team.completed | 1.0 | |
| security_team.review_submitted | 1.0 | |

---

## 4. Versioning Policy

- **Patch version** (1.x → 1.y): Additive changes only (new optional fields)
- **Minor version** (1.x → 2.x): Breaking changes (field removal, type change)
- All consumers MUST handle unknown fields gracefully
- Event processors MUST check `event_version` before processing

---

## 5. Reserved Event Types

The following prefixes are reserved for future use:
- `ai_analysis.*`
- `compliance.*`
- `integration.*`
- `system.*`

---

*Catalog Version: 1.0*
*Last Updated: 2026-10-14*
# HUMAN APPROVAL WORKFLOW

## Overview

The human approval workflow is a critical security boundary in the ShadowOps remediation system. It ensures that no AI-generated remediation can be applied without explicit human authorization.

## Approval Principles

1. **AI Proposes, Human Decides** - AI generates proposals; humans approve/reject
2. **Explicit Authorization** - Each approval requires authenticated human action
3. **Patch Hash Binding** - Approval binds to exact patch content (SHA256)
4. **Immutable Record** - Approvals cannot be modified after creation
5. **Role-Based Access** - Only workspace owners/admins can approve
6. **Audit Trail** - All decisions logged with full context

## Approval Lifecycle

```
PROPOSED
    │
    ├─► VALIDATION PIPELINE
    │     ├─► Patch Integrity (hash verification)
    │     ├─► Diff Parsing (format validity)
    │     ├─► Path Allowlist (security)
    │     ├─► Syntax Validation (language)
    │     ├─► Semgrep Re-scan (BLOCKED)
    │     └─► Regression Check (BLOCKED)
    │
    ├─► AWAITING_APPROVAL  (all required validations PASSED)
    │     │
    │     ├─► APPROVE  ──────► APPROVED
    │     │       │
    │     │       └─► Records: approver, timestamp, conditions, patch_hash, proposal_version
    │     │
    │     └─► REJECT  ──────► REJECTED
    │           │
    │           └─► Requires justification
    │
    ▼
APPROVED
    │
    └─► APPLY (admin/owner + idempotency key)
```

## Approval Requirements

### Who Can Approve
| Role | Can Approve |
|------|-------------|
| Owner | ✅ |
| Admin | ✅ |
| Member | ❌ |
| Viewer | ❌ |

### Required Validations (Must Pass)
1. **Patch Integrity** - Hash matches stored value
2. **Diff Parsing** - Valid unified diff format
3. **Path Allowlist** - No traversal, no disallowed files

### Optional Validations (BLOCKED in Stage 8)
- Syntax Validation
- Semgrep Re-scan
- Regression Check
- Existing Tests

> **Note**: If optional validations are BLOCKED, approval can still proceed. The human approver accepts the risk.

## Approval Record

Each approval creates an immutable `RemediationApproval` record:

```json
{
  "id": "uuid",
  "proposal_id": "uuid",
  "patch_version_id": "uuid",
  "workspace_id": "uuid",
  "approved_by": "uuid",
  "decision": "approved|rejected",
  "justification": "string (required for rejection)",
  "conditions": ["string array"],
  "patch_hash": "sha256",
  "proposal_version": 1,
  "validation_snapshot": {
    "patch_integrity": {"status": "passed"},
    "diff_parsing": {"status": "passed"},
    "path_allowlist": {"status": "passed"}
  },
  "approved_at": "timestamp",
  "expires_at": "timestamp|null"
}
```

### Hash Binding
- `patch_hash` MUST match `PatchVersion.patch_hash` at approval time
- If patch changes after approval, hash mismatch invalidates approval
- New patch version requires new approval

### Conditions
Approvers may add conditions:
```json
{
  "conditions": [
    "Test in staging environment first",
    "Deploy during maintenance window",
    "Notify on-call engineer"
  ]
}
```
Conditions are advisory - not enforced by system but logged for audit.

## Rejection Requirements

Rejections require explicit justification:
- Minimum 10 characters
- Stored in `justification` field
- Included in audit log
- Notifies proposal creator

## Approval Expiration

- Default: 30 days from proposal creation
- Configurable via `RemediationProposal.expires_at`
- Expired approvals cannot be applied
- New patch version required after expiration

## Version Control

### Proposal Versioning
- Each proposal has `version` field (optimistic locking)
- Incremented on each status change
- Approval records `proposal_version` at time of approval

### Patch Versioning
- Each proposal can have multiple `PatchVersion` records
- `version` field increments with each AI generation
- `is_current` flag marks active patch
- `superseded_by` links to replacement

### Approval Invalidation
If any of these change after approval:
- Patch content (hash mismatch)
- Proposal version incremented
- Proposal status changes to REJECTED/EXPIRED

The approval becomes invalid and new approval required.

## UI Workflow

### Approval Dashboard (`/remediations/[id]`)

**Overview Tab**:
- Proposal summary with status badge
- Action buttons based on current status:
  - `PROPOSED` → "Run Validation"
  - `AWAITING_APPROVAL` → "Approve" / "Reject"
  - `APPROVED` → "Apply Patch" (with idempotency key)
  - `APPLIED` → "Request Verification" / "Rollback"

**Approvals Tab**:
- List of all approval attempts
- Shows: decision, approver, timestamp, patch hash, conditions
- Expired/rejected approvals clearly marked

### Approval Modal

**Approve**:
```
┌─────────────────────────────────────┐
│ Approve Remediation Proposal        │
├─────────────────────────────────────┤
│ Patch Hash: abc123... (click to copy)│
│ Proposal Version: 3                 │
├─────────────────────────────────────┤
│ Justification (optional):           │
│ [________________________________]  │
├─────────────────────────────────────┤
│ Conditions (one per line):          │
│ [________________________________]  │
│ [________________________________]  │
├─────────────────────────────────────┤
│ [Cancel]                    [Approve]│
└─────────────────────────────────────┘
```

**Reject**:
```
┌─────────────────────────────────────┐
│ Reject Remediation Proposal         │
├─────────────────────────────────────┤
│ ⚠️ Rejection requires justification │
├─────────────────────────────────────┤
│ Justification (required):           │
│ [________________________________]  │
│ [________________________________]  │
├─────────────────────────────────────┤
│ [Cancel]                     [Reject]│
└─────────────────────────────────────┘
```

## Security Controls

### No AI Self-Approval
- AI agents cannot call approval endpoints
- Requires authenticated human session
- Firebase token validation on every request

### No Cross-Workspace Approval
- `workspace_id` verified on every request
- RLS policies prevent cross-workspace access
- `require_workspace_member` dependency on all endpoints

### No Patch Modification After Approval
- Patch hash stored at approval time
- Application verifies hash match
- Hash mismatch → application rejected

### Idempotent Application
- Client provides `idempotency_key`
- Duplicate requests return existing result
- Prevents accidental double-application

## Audit Logging

All approval actions logged:
```json
{
  "action": "remediation.approval.granted|rejected",
  "resource_type": "remediation_approval",
  "resource_id": "uuid",
  "new_state": {
    "proposal_id": "uuid",
    "patch_version_id": "uuid",
    "patch_hash": "sha256",
    "approver_id": "uuid",
    "conditions": ["string"],
    "validation_snapshot": {}
  },
  "user_id": "uuid"
}
```

## Future Enhancements

1. **Multi-party Approval** - Require N-of-M approvers
2. **Conditional Approval** - Auto-apply when conditions met
3. **Approval Delegation** - Temporary approval authority
4. **Policy Engine** - OPA-based approval policies
5. **Slack/Email Integration** - Approval notifications
6. **Time-limited Approval** - Auto-expire after N hours
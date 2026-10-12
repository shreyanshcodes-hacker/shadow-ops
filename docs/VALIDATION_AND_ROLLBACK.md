# VALIDATION PIPELINE & ROLLBACK DESIGN

## Overview

This document describes the validation pipeline and rollback mechanisms for the ShadowOps remediation system. These systems ensure that patches are safe to apply and can be safely reverted if issues arise.

## Validation Pipeline

### Architecture

The validation pipeline runs a series of checks on each patch version. Checks are executed sequentially, with critical checks stopping the pipeline on failure.

```
PATCH VERSION
     │
     ▼
┌─────────────────────────────────────────┐
│ 1. PATCH INTEGRITY                      │
│    SHA256 hash verification             │
│    (CRITICAL - stops on failure)        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 2. DIFF PARSING                         │
│    Unified diff format validation       │
│    (CRITICAL - stops on failure)        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 3. PATH ALLOWLIST                       │
│    Path traversal detection             │
│    Disallowed file patterns             │
│    File extension whitelist             │
│    (CRITICAL - stops on failure)        │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 4. SYNTAX VALIDATION                    │
│    Language-specific linters            │
│    (WARNING on failure - non-blocking)  │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 5. SEMGREP RE-SCAN                      │
│    Verify finding resolved              │
│    (BLOCKED - requires isolation)       │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 6. REGRESSION CHECK                     │
│    Run existing test suite              │
│    (BLOCKED - requires test runner)     │
└─────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────┐
│ 7. EXISTING TESTS                       │
│    Run tests relevant to changed files  │
│    (BLOCKED - requires test runner)     │
└─────────────────────────────────────────┘
```

### Check Definitions

| Check | Type | Critical | Description |
|-------|------|----------|-------------|
| `patch_integrity` | Integrity | Yes | SHA256 hash matches stored value |
| `diff_parsing` | Format | Yes | Valid unified diff, parseable |
| `path_allowlist` | Security | Yes | No traversal, allowed extensions, no disallowed files |
| `syntax_validation` | Quality | No | Language-specific syntax check |
| `semgrep_rescan` | Verification | N/A | BLOCKED - Semgrep on patched code |
| `regression_check` | Verification | N/A | BLOCKED - Full test suite |
| `existing_tests` | Verification | N/A | BLOCKED - Relevant tests only |

### Execution Model

```python
async def run_all_validations(proposal_id, patch_version_id, workspace_id):
    checks = [
        ValidationCheckType.PATCH_INTEGRITY,
        ValidationCheckType.DIFF_PARSING,
        ValidationCheckType.PATH_ALLOWLIST,
        ValidationCheckType.SYNTAX_VALIDATION,
        ValidationCheckType.SEMGREP_RESCAN,
        ValidationCheckType.REGRESSION_CHECK,
        ValidationCheckType.EXISTING_TESTS,
    ]
    
    results = []
    for check_type in checks:
        result = await run_validation(proposal_id, patch_version_id, check_type, workspace_id)
        results.append(result)
        
        # Stop on critical failures
        if check_type in CRITICAL_CHECKS and not result.passed:
            break
    
    return results
```

### Validation Statuses

| Status | Meaning |
|--------|---------|
| `PENDING` | Not yet started |
| `RUNNING` | Currently executing |
| `PASSED` | Check completed successfully |
| `FAILED` | Check completed with failures |
| `BLOCKED` | Cannot execute (missing infrastructure) |
| `ERROR` | Unexpected execution error |

### BLOCKED Handling

In Stage 8, several checks are BLOCKED due to missing execution infrastructure:

```python
async def _check_semgrep_rescan(self, patch_version, validation_run):
    if not self.semgrep_scanner:
        return ValidationResult(
            check_type=ValidationCheckType.SEMGREP_RESCAN,
            passed=False,
            message="Semgrep re-scan requires isolated working copy execution (BLOCKED in Stage 8)",
            metadata={
                "status": "BLOCKED",
                "reason": "Isolated patch execution environment not available in Stage 8 deployment",
                "files_to_scan": self.patch_processor.extract_file_paths(patch_version.unified_diff),
            },
            duration_ms=0,
        )
```

**Impact**: BLOCKED checks do not prevent approval but are logged for transparency.

### Validation Snapshots

At approval time, a snapshot of all validation results is stored:

```json
{
  "patch_integrity": {"status": "passed", "duration_ms": 5},
  "diff_parsing": {"status": "passed", "duration_ms": 3, "file_count": 2},
  "path_allowlist": {"status": "passed", "warnings": ["Unusual extension: .tf"]},
  "syntax_validation": {"status": "passed", "note": "Placeholder"},
  "semgrep_rescan": {"status": "BLOCKED", "reason": "Isolated execution unavailable"},
  "regression_check": {"status": "BLOCKED", "reason": "Test runner unavailable"}
}
```

## Patch Application

### Pre-Application Checks

Before applying a patch, the system verifies:

1. **Proposal exists** and belongs to workspace
2. **Patch version** exists and belongs to proposal
3. **Approval** exists, is "approved", matches patch hash
4. **Proposal status** is APPROVED
5. **Proposal version** matches approval version
6. **Approval not expired**
6. **Applier has admin/owner role**
7. **Idempotency key** not already used

### Application Process

```python
async def apply_patch(proposal_id, patch_version_id, approval_id, applier_id, workspace_id, idempotency_key):
    # 1. Verify all preconditions
    precondition_check = await verify_preconditions(...)
    
    # 2. Create application record
    application = RemediationApplication(
        idempotency_key=idempotency_key,
        status=ApplicationStatus.PENDING
    )
    
    # 3. Create checkpoint (git stash)
    await application_repo.update(application.id, {"status": ApplicationStatus.CHECKPOINT_CREATED})
    checkpoint_ref = await create_checkpoint()
    
    # 4. Apply patch
    await application_repo.update(application.id, {"status": ApplicationStatus.PATCH_APPLIED})
    result_diff, changed_files = await apply_patch(patch_version.unified_diff)
    
    # 5. Verify applied diff matches expected
    if not verify_applied_diff(expected_diff, result_diff):
        raise ApplicationError("Applied diff does not match expected patch")
    
    # 6. Post-application validation (if available)
    validation_results = await run_post_application_validation(changed_files)
    
    # 7. Update records
    await application_repo.update(application.id, {
        "status": ApplicationStatus.VERIFIED,
        "checkpoint_ref": checkpoint_ref,
        "result_diff": result_diff,
        "changed_files": changed_files,
        "validation_results": validation_results,
    })
    
    # 8. Update proposal
    await proposal_repo.update(proposal_id, {
        "status": RemediationStatus.APPLIED,
        "applied_by": applier_id,
        "applied_at": now(),
    })
    
    # 9. Create verification handoff
    await create_verification_handoff(...)
```

### Checkpoint Creation

```python
async def create_checkpoint():
    """Create git stash checkpoint."""
    result = subprocess.run(
        ['git', 'stash', 'push', '-m', f'shadowops-checkpoint-{int(time.time())}'],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode == 0:
        # Get latest stash reference
        result = subprocess.run(
            ['git', 'stash', 'list'],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip().split('\n')[0]  # Latest stash
    return "checkpoint_failed"
```

### Idempotency

Client provides `idempotency_key` with apply request:
- Key stored in `RemediationApplication.idempotency_key` (UNIQUE)
- Duplicate requests return existing application
- Prevents accidental double-application

```python
existing = await application_repo.get_by_idempotency_key(idempotency_key)
if existing:
    return existing  # Return existing result
```

## Rollback Mechanism

### Rollback Triggers

1. **Manual** - Human requests rollback via UI/API
2. **Automatic** - Verification fails (future stage)
3. **Health Check** - Post-deploy monitoring alerts (future)

### Rollback Process

```python
async def rollback(application_id, requester_id, workspace_id, reason):
    # 1. Verify application was VERIFIED
    application = await get_application(application_id)
    if application.status != ApplicationStatus.VERIFIED:
        raise RollbackError("Can only rollback verified applications")
    
    # 2. Verify requester permissions (admin/owner)
    await verify_rollback_permission(requester_id, workspace_id)
    
    # 3. Check checkpoint exists
    if not application.checkpoint_ref or application.checkpoint_ref in ["stash_failed", "checkpoint_failed"]:
        raise RollbackError("No valid checkpoint available")
    
    # 4. Create rollback record
    rollback = RemediationRollback(
        status=RollbackStatus.IN_PROGRESS,
        checkpoint_ref=application.checkpoint_ref,
    )
    
    # 5. Check repository divergence
    divergence = await check_repository_divergence(application)
    if divergence["diverged"]:
        await record_rollback_failure(rollback, divergence["reason"])
        raise RollbackError(f"Repository diverged: {divergence['reason']}", "REPOSITORY_DIVERGED")
    
    # 6. Perform rollback (git stash pop)
    verification_diff = await perform_rollback(application.checkpoint_ref)
    
    # 7. Update statuses
    await rollback_repo.update(rollback.id, {
        "status": RollbackStatus.COMPLETED,
        "verification_diff": verification_diff,
    })
    
    await application_repo.update(application_id, {"status": ApplicationStatus.ROLLED_BACK})
    await proposal_repo.update(proposal_id, {"status": RemediationStatus.ROLLED_BACK})
```

### Divergence Detection

Before rollback, the system checks for unsafe conditions:

```python
async def check_repository_divergence(application):
    # 1. Check current revision matches target
    current = get_current_revision()
    if current != application.target_revision:
        return {"diverged": True, "reason": f"Revision changed from {application.target_revision} to {current}"}
    
    # 2. Check for uncommitted changes
    status = subprocess.run(['git', 'status', '--porcelain'], ...)
    if status.stdout.strip():
        return {"diverged": True, "reason": f"Uncommitted changes: {status.stdout[:200]}"}
    
    # 3. Check stash exists
    stash_list = subprocess.run(['git', 'stash', 'list'], ...)
    if application.checkpoint_ref not in stash_list.stdout:
        return {"diverged": True, "reason": "Checkpoint stash not found"}
    
    return {"diverged": False, "reason": "No divergence detected"}
```

### Safe Failure

If divergence detected:
- Rollback status: `BLOCKED_DIVERGED`
- No destructive action taken
- Manual intervention required
- Audit log records the blocked attempt

### Rollback Statuses

| Status | Meaning |
|--------|---------|
| `PENDING` | Requested, not started |
| `IN_PROGRESS` | Executing |
| `COMPLETED` | Successfully rolled back |
| `FAILED` | Execution error |
| `BLOCKED_DIVERGED` | Repository diverged, manual recovery needed |

## Verification Handoff

After successful application, a handoff record is created for future verification:

```json
{
  "proposal_id": "uuid",
  "application_id": "uuid",
  "workspace_id": "uuid",
  "finding_id": "uuid",
  "asset_id": "uuid",
  "patch_hash": "sha256",
  "repository_revision": "abc123",
  "changed_files": [{"file_path": "app/auth/login.py", "additions": 1, "deletions": 1}],
  "validation_results": {...},
  "original_finding_snapshot": {"id": "...", "title": "...", "status": "open"},
  "applied_at": "timestamp",
  "applied_by": "uuid",
  "status": "PENDING_VERIFICATION"
}
```

### Future Verification Flow

When verification stage is implemented:

```
APPLIED
    │
    ▼
REQUEST VERIFICATION (API: POST /applications/{id}/request-verification)
    │
    ▼
VERIFICATION_REQUESTED
    │
    ▼
VERIFICATION WORKER (isolated environment)
    │
    ├─► Apply patch to isolated copy
    ├─► Run Semgrep re-scan
    ├─► Run regression tests
    ├─► Run reproduction test (if available)
    │
    ▼
VERIFIED ──────────────► Finding status = FIXED
    │
    ▼
VERIFICATION_FAILED ──► Finding stays OPEN, alert raised
```

## Configuration

### Timeouts
| Operation | Timeout |
|-----------|---------|
| Patch validation | 30 seconds |
| Single validation check | 60 seconds |
| Semgrep re-scan | 120 seconds |
| Patch application | 30 seconds |
| Rollback execution | 30 seconds |

### Resource Limits
| Resource | Limit |
|----------|-------|
| Max memory | 512 MB |
| Max CPU | 50% |
| Max patch size | 50 KB |
| Max files | 10 |

## Monitoring & Alerting

### Metrics to Track
- Validation pass/fail rates by check type
- Approval-to-application latency
- Rollback frequency and reasons
- Divergence detection rate
- Verification completion rate

### Alert Conditions
- Rollback rate > 5% of applications
- Divergence detected on > 1% of rollback attempts
- Validation BLOCKED rate > 50% (infrastructure gap)
- Proposal expiration without action > 80%

## Future Enhancements

1. **Parallel Validation** - Run independent checks concurrently
2. **Incremental Validation** - Only re-run checks affected by patch changes
3. **Policy-as-Code** - OPA rules for validation requirements per fix type
4. **Automated Verification** - Full isolated execution pipeline
5. **Canary Deployment** - Gradual rollout with automated rollback
6. **Drift Detection** - Continuous monitoring for post-application drift
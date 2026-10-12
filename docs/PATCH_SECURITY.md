# PATCH SECURITY MODEL

## Overview

This document describes the security model for patch processing in the ShadowOps remediation system. The model ensures that AI-generated patches cannot escape their authorized boundaries or modify sensitive files.

## Threat Model

### Attacker Capabilities
- AI model generates malicious patch content
- Prompt injection attempts to manipulate patch output
- Path traversal to access files outside workspace
- Modification of sensitive configuration files

### Defenses
1. **Input Validation** - All patches validated before application
2. **Path Containment** - Patches restricted to workspace root
3. **File Type Restrictions** - Disallowed file patterns
4. **Hash Integrity** - Patch hash binds approval to exact content
5. **Checkpoint Recovery** - Git stash enables safe rollback

## Patch Validation Pipeline

### 1. Patch Integrity Check
- Verifies SHA256 hash of unified diff matches stored hash
- Detects any post-approval modifications

### 2. Diff Parsing Validation
- Ensures diff conforms to unified diff format
- Extracts file paths, additions, deletions
- Rejects malformed diffs

### 3. Path Allowlist Validation
- **Path Traversal Detection**:
  - `os.path.isabs()` - Rejects absolute paths
  - `os.path.normpath()` + `startswith('..')` - Rejects parent directory traversal
  - `'..' in Path().parts` - Rejects any parent directory components
- **Disallowed File Patterns** (30+ patterns):
  - Environment files: `.env`, `.env.*`, `secrets.*`, `credentials.*`
  - Authentication: `auth.*`, `authorization.*`
  - Database: `migration*.*`, `*.sql` (migrations only)
  - Deployment: `Dockerfile*`, `docker-compose*`, `*.tf`, `helm/`, `kubernetes/`
  - CI/CD: `.github/`, `.gitlab/`, `Jenkinsfile`, `.circleci/`
  - Infrastructure: `ansible/`, `playbook*.yml`
- **Allowed Extensions Whitelist**: 30+ code/config extensions only

### 4. Syntax Validation (Planned)
- Language-specific linters (py_compile, tsc, go vet, etc.)
- Currently BLOCKED - requires isolated execution

### 5. Semgrep Re-scan (BLOCKED)
- Re-run Semgrep on patched code
- Verify original finding resolved
- Requires isolated working copy execution

### 6. Regression Testing (BLOCKED)
- Run existing test suite
- Requires test execution environment

## Patch Hash Binding

### Approval Binding
When a human approves a remediation:
1. System records `patch_hash` (SHA256 of unified diff)
2. System records `proposal_version`
3. System records `validation_snapshot`

### Application Verification
Before applying:
1. Verify approval exists for exact `patch_hash`
2. Verify `proposal_version` matches current
3. Verify proposal status is APPROVED
4. Verify approval not expired

If any check fails, application is rejected.

## Checkpoint & Rollback

### Checkpoint Creation
Before applying patch:
```bash
git stash push -m "shadowops-checkpoint-{timestamp}"
```
Stores reference in `checkpoint_ref` field.

### Rollback Process
1. Verify application was VERIFIED
2. Check requester has admin/owner role
3. **Divergence Detection**:
   - Current revision matches `target_revision`
   - No uncommitted changes (`git status --porcelain` empty)
   - Checkpoint stash exists and accessible
2. Apply checkpoint: `git stash pop {checkpoint_ref}`
3. Verify rollback with `git diff HEAD@{1}`

### Safe Failure
If divergence detected:
- Status: `BLOCKED_DIVERGED`
- No destructive recovery attempted
- Manual intervention required

## Workspace Isolation

### Repository Workspace
- Each asset has authorized workspace root
- `PatchProcessor` initialized with server-resolved path
- Never accepts client-supplied paths

### Cross-Workspace Prevention
- All database queries filtered by `workspace_id`
- RLS policies enforce isolation at database level
- API endpoints verify workspace membership

## File Size & Complexity Limits

| Limit | Value | Rationale |
|-------|-------|-----------|
| Total patch size | 50 KB | Prevents resource exhaustion |
| Max files per patch | 10 | Limits blast radius |
| Max diff lines per file | 500 | Prevents massive changes |
| Max path length | 500 chars | Prevents path manipulation |

## Disallowed Operations

The following are explicitly NOT supported in Stage 8:
- ❌ Modifying `.env`, secrets, credentials files
- ❌ Modifying authentication/authorization code
- ❌ Modifying database migrations
- ❌ Modifying deployment configuration (Docker, K8s, Terraform)
- ❌ Modifying CI/CD pipelines
- ❌ Binary file changes
- ❌ Creating new files outside workspace
- ❌ Symlink manipulation
- ❌ Automatic commit/PR/merge/deploy

## Audit Trail

All patch operations logged:
| Event | Fields |
|-------|--------|
| `remediation.proposal.generated` | proposal_id, finding_id, patch_version_id, fix_type |
| `remediation.proposal.validated` | proposal_id, validation_results |
| `remediation.approval.granted` | proposal_id, patch_hash, approver_id, conditions |
| `remediation.approval.rejected` | proposal_id, patch_hash, rejecter_id, justification |
| `remediation.applied` | proposal_id, patch_hash, applier_id, checkpoint_ref |
| `remediation.rolled_back` | application_id, checkpoint_ref, requester_id |

## Configuration

Environment variables:
```bash
REMEDIATION_WORKSPACE_ROOT=/workspace  # Server-resolved workspace root
```

## Future Enhancements (Post-Stage 8)

1. **Container Isolation** - Run patch apply in gVisor/Firecracker
2. **Syntax Validation** - Integrate language servers
3. **Semgrep Integration** - Isolated scanner worker
4. **Test Execution** - Isolated test runner
5. **Policy Engine** - OPA-based patch admission control
5. **Multi-repo Support** - Per-asset workspace roots
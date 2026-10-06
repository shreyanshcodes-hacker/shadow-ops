# SCANNER SECURITY

## Security Architecture

The ShadowOps scanner follows a defense-in-depth approach with multiple security boundaries:

```
User Request
    ↓
Firebase Auth (Identity)
    ↓
FastAPI (Authorization)
    ↓
Workspace Membership Check
    ↓
Asset Authorization Check (NO AUTHORIZATION → NO SCAN)
    ↓
ScanJobRunner (Execution Boundary)
    ↓
Controlled Target Validation
    ↓
Semgrep Execution (Isolated)
    ↓
Result Persistence
```

## Critical Security Invariant

**NO AUTHORIZATION → NO SCAN**

This invariant is enforced at multiple layers:

1. **API Layer**: `create_scan` endpoint validates authorization before creating scan record
2. **Service Layer**: `ScanService.create_scan()` validates authorization before queuing
3. **Runner Layer**: `ScanJobRunner.execute_scan()` re-validates authorization before execution
4. **Database Layer**: RLS policies prevent cross-workspace access

## Allowed Targets

### Stage 3: Controlled Demo Targets Only

- Local filesystem paths within `/scan-workspace/`
- Explicitly created demo fixtures
- No external repository cloning
- No arbitrary URL fetching
- No network scanning

### Future Stages: Production Targets

- Authorized Git repositories (with credentials from vault)
- Container registry images (with credentials from vault)
- Cloud infrastructure (with credentials from vault)
- All targets must have `asset_authorizations.status = 'verified'`

## Filesystem Restrictions

### Working Directory

```
SCAN_WORKSPACE_ROOT = /scan-workspace
├── {workspace_id}/
│   └── {asset_id}/          # Per-asset working directory
└── demo-target/             # Stage 3 controlled fixture
```

### Path Validation

All target paths are validated to ensure they remain within `SCAN_WORKSPACE_ROOT`:

```python
try:
    target_path.resolve().relative_to(scan_workspace_root.resolve())
except ValueError:
    raise ScanExecutionError("Target path escapes scan workspace")
```

### Prohibited Paths

- `/` (root filesystem)
- `/etc`, `/var`, `/usr`, `/home` (system directories)
- `/proc`, `/sys`, `/dev` (virtual filesystems)
- Parent directory traversal (`../`)
- Symlinks pointing outside workspace

## Command Restrictions

### Semgrep Execution

```python
# ALLOWED: Argument array (no shell)
cmd = [
    "semgrep",
    "scan",
    "--json",
    "--max-target-bytes", "10485760",
    "--config", "p/security-audit",
    target_path
]

# NEVER ALLOWED
# subprocess.run("semgrep scan " + user_input, shell=True)
# os.system(user_controlled_command)
```

### Security Measures

- `shell=False` always (uses `asyncio.create_subprocess_exec`)
- Argument validation before execution
- Timeout enforcement (default 30 minutes)
- Resource limits via `ulimit` / cgroups (future)
- Non-root execution user

## Timeouts

| Operation | Timeout | Config |
|-----------|---------|--------|
| Semgrep scan | 30 min | `SCAN_TIMEOUT_SECONDS=1800` |
| Target preparation | 5 min | `PREP_TIMEOUT_SECONDS=300` |
| Result parsing | 2 min | `PARSE_TIMEOUT_SECONDS=120` |

## Resource Limits

| Resource | Limit | Enforcement |
|----------|-------|-------------|
| Max target size | 1 GB | `MAX_TARGET_SIZE_MB=1000` |
| Max file size | 10 MB | Semgrep `--max-target-bytes` |
| Memory | 2 GB | Container/cgroup (future) |
| CPU | 2 cores | Container/cgroup (future) |
| Concurrent scans | 3/workspace | Application-level queue |

## No Repository Execution

**CRITICAL**: The scanner NEVER executes code from the target repository.

- Semgrep performs **static analysis only**
- No `npm install`, `pip install`, `make`, `./configure`
- No test execution
- No build processes
- No dynamic analysis

## Authorization Boundary

### Pre-Execution Checks

Every scan execution performs:

1. **Asset exists** and belongs to workspace
2. **Authorization record exists** for asset
3. **Authorization status = VERIFIED**
4. **Authorization not expired**
5. **User is workspace member** (OWNER, ADMIN, or MEMBER)
6. **Asset not deleted/archived**

### Audit Logging

All authorization decisions are logged:

```python
await audit_log(
    action="scan.blocked",
    resource_type="scan",
    resource_id=asset_id,
    new_state={
        "reason": "missing_authorization|authorization_status_pending|authorization_expired|workspace_access_denied",
        "asset_id": str(asset_id)
    },
    user_id=current_user.id
)
```

## Logging Rules

### Allowed in Logs

- Scan IDs, Asset IDs, Workspace IDs
- User IDs (for audit)
- Timing information
- Finding counts (aggregated)
- Error codes (sanitized)

### NEVER in Logs

- Firebase tokens
- Supabase service keys
- Git credentials / tokens
- API keys
- Passwords
- Repository contents
- File contents (except truncated snippets in findings)

### Finding Snippets

Code snippets in findings are:
- Limited to 10 lines max
- Truncated at 500 characters
- Scanned for credential patterns before storage
- Redacted if credentials detected

## Failure Behavior

### Scan Failures

| Failure Type | Scan Status | Retry | User Action |
|--------------|-------------|-------|-------------|
| Target missing | FAILED | No | Re-prepare target |
| Semgrep timeout | FAILED | No | Reduce target size |
| Semgrep crash | FAILED | Yes (max 2) | Check target validity |
| Authorization lost | FAILED | No | Re-authorize asset |
| Workspace deleted | FAILED | No | N/A |
| Disk full | FAILED | No | Admin intervention |

### Graceful Degradation

- Partial results saved if parsing fails
- Events logged up to failure point
- Scan marked FAILED with error code
- No silent success on partial failure

## Future: Container Isolation

### Planned Architecture

```
┌─────────────────────────────────────┐
│         Scan Coordinator            │
│  (FastAPI - validates, queues)      │
└──────────────┬──────────────────────┘
               │ gRPC/Queue
               ▼
┌─────────────────────────────────────┐
│        Scanner Worker Pool          │
│  ┌─────────────────────────────┐   │
│  │ Container: semgrep:latest   │   │
│  │ - Read-only root fs         │   │
│  │ - Non-root user (1000)      │   │
│  │ - No network                │   │
│  │ - CPU/Memory limits         │   │
│  │ - Mounted target (ro)       │   │
│  │ - Ephemeral output volume   │   │
│  └─────────────────────────────┘   │
│         (K8s Job / Railway)         │
└─────────────────────────────────────┘
```

### Security Properties

- **No host access**: Container cannot access host filesystem
- **No network**: Cannot exfiltrate data or phone home
- **Resource limits**: Cannot DoS the host
- **Ephemeral**: No persistence between scans
- **Auditable**: Container image digest recorded

## Secret Handling

### Credential Storage

- Credentials stored in **Supabase Vault** / **Railway Secrets**
- Referenced by `credentials_ref` (e.g., `vault:secret/github/token`)
- Never in database, never in logs, never in frontend

### Runtime Injection

```python
# At scan time (future)
credentials = await vault.get_secret(asset.credentials_ref)
# Injected as environment variables for semgrep
env = {**os.environ, "GITHUB_TOKEN": credentials.token}
```

### Credential Redaction

Before any finding storage:

```python
def redact_secrets(text: str) -> str:
    patterns = [
        (r'(api[_-]?key|secret|token|password)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})', r'\1=***REDACTED***'),
        (r'(github[_-]?token)["\']?\s*[:=]\s*["\']?([a-zA-Z0-9]{35,})', r'\1=***REDACTED***'),
    ]
    for pattern, replacement in patterns:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text
```

## Compliance

### SOC 2 Type II Alignment

- **CC6.1**: Logical access controls (workspace isolation)
- **CC6.7**: Data transmission (TLS for all scanner comms)
- **CC7.2**: System monitoring (audit logs for all scan actions)

### GDPR Considerations

- No PII in scan targets (code only)
- Right to deletion: cascade deletes scan data
- Data minimization: only security-relevant findings stored

## Incident Response

### Suspicious Activity Detection

- Scan targeting system paths → Alert
- Scan with oversized target → Alert
- Repeated authorization failures → Alert
- Semgrep output anomalies → Alert

### Containment

1. Cancel running scan
2. Revoke asset authorization
3. Isolate workspace (if compromised)
4. Rotate affected credentials
5. Forensic analysis of scan artifacts

## Configuration

### Environment Variables

```bash
# Scanner
SCAN_WORKSPACE_ROOT=/scan-workspace
SCAN_TIMEOUT_SECONDS=1800
MAX_TARGET_SIZE_MB=1000
SEM_BINARY=semgrep

# Security
SCANNER_USER=scanner
SCANNER_UID=1000
SCANNER_GID=1000

# Limits
MAX_CONCURRENT_SCANS_PER_WORKSPACE=3
MAX_FILE_SIZE_MB=10
```

### Semgrep Version Pinning

```dockerfile
# Production must pin exact version
FROM returntocorp/semgrep:1.45.0
```

Never use `latest` tag in production.

---

**Document Version**: 1.0  
**Last Updated**: Stage 3 Implementation  
**Classification**: Internal - Security Architecture
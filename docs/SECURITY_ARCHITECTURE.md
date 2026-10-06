# SECURITY ARCHITECTURE

## Security Principles (Non-Negotiable)

1. **Authentication Required** — Every API request authenticated via Firebase ID token
2. **Backend Authorization Mandatory** — Frontend never makes security decisions
3. **Workspace Isolation** — Zero data access across workspaces (enforced by RLS)
4. **Asset Authorization** — Scan only with verified `asset_authorizations.status = 'verified'`
5. **Secrets Never in Browser** — All secrets server-side only (Supabase Vault / Railway secrets)
6. **AI Output Validated** — Schema validation, confidence gates, hallucination detection
7. **Human-in-the-Loop** — AI proposes, human approves, system executes (for remediation)
8. **Audit Everything** — Immutable audit logs for all security-relevant actions
9. **Evidence Provenance** — Every finding traces to evidence with tool/version metadata
10. **No Unauthorized External Scans** — External targets require explicit authorization proof

---

## Authentication Flow

```
User → Firebase Auth (Email/Password, OAuth, SSO)
         │
         ▼
Firebase ID Token (JWT, 1hr expiry)
         │
         ▼
Frontend → Backend API (Authorization: Bearer <token>)
         │
         ▼
Backend: Firebase Admin SDK verifyIdToken()
         │
         ├── Invalid/Expired → 401
         ├── Valid → Extract uid, email, claims
         │
         ▼
Lookup/Create Profile (profiles table)
         │
         ▼
Attach User Context to Request
         │
         ▼
Workspace Middleware: Verify Membership
```

### Token Handling

| Aspect | Implementation |
|--------|----------------|
| Storage | HttpOnly Secure cookie (preferred) OR memory (SPA) |
| Refresh | Frontend handles via Firebase SDK `getIdToken(true)` |
| Backend Verification | Every request via FastAPI dependency |
| Clock Skew | Tolerate 60s |
| Revocation | Firebase handles; backend checks `revoked` claim |

---

## Authorization Model

### Resource Hierarchy

```
Workspace (Root)
├── Members (with Roles)
├── Assets
│   └── Authorizations
├── Scans
│   ├── Events
│   └── Agent Runs
├── Findings
│   ├── Evidence
│   └── Risk Assessments
├── Attack Paths
│   ├── Nodes
│   └── Edges
├── Remediations
│   ├── Proposals
│   ├── Approvals
│   └── Verifications
├── Reports
├── Chat Conversations
└── Audit Logs
```

### Role Permissions Matrix

| Action | Owner | Admin | Member | Viewer |
|--------|-------|-------|--------|--------|
| Workspace: Delete | ✅ | ❌ | ❌ | ❌ |
| Workspace: Settings | ✅ | ✅ | ❌ | ❌ |
| Members: Invite | ✅ | ✅ | ❌ | ❌ |
| Members: Remove | ✅ | ✅ | ❌ | ❌ |
| Members: Change Role | ✅ | ✅* | ❌ | ❌ |
| Assets: Create | ✅ | ✅ | ✅ | ❌ |
| Assets: Delete | ✅ | ✅ | ✅** | ❌ |
| Assets: Manage Auth | ✅ | ✅ | ✅ | ❌ |
| Scans: Start | ✅ | ✅ | ✅ | ❌ |
| Scans: Cancel | ✅ | ✅ | ✅** | ❌ |
| Findings: View | ✅ | ✅ | ✅ | ✅ |
| Findings: Triage | ✅ | ✅ | ✅ | ❌ |
| Findings: Delete | ✅ | ❌ | ❌ | ❌ |
| Remediation: Propose | ✅ | ✅ | ✅ | ❌ |
| Remediation: Approve | ✅ | ✅ | ❌ | ❌ |
| Remediation: Apply | ✅ | ✅ | ❌ | ❌ |
| Reports: Generate | ✅ | ✅ | ✅ | ❌ |
| Reports: View | ✅ | ✅ | ✅ | ✅ |
| Audit Logs: View | ✅ | ✅ | ❌ | ❌ |
| Settings: Integrations | ✅ | ✅ | ❌ | ❌ |

* Admin cannot change Owner role
** Only if they created the asset/scan

### Backend Enforcement

```python
# FastAPI Dependency
async def require_workspace_role(
    workspace_id: UUID,
    required_roles: list[str],
    current_user: User = Depends(get_current_user),
    db: DatabaseSession = Depends(get_db),
) -> WorkspaceMember:
    member = await db.get_workspace_member(workspace_id, current_user.id)
    if not member or member.joined_at is None:
        raise Forbidden("Not a workspace member")
    if member.role not in required_roles:
        raise Forbidden(f"Requires role: {required_roles}")
    return member

# Usage
@router.post("/scans")
async def start_scan(
    scan_in: ScanCreate,
    member: WorkspaceMember = Depends(require_workspace_role("member", ["owner", "admin", "member"])),
    # ...
):
    # Authorization check for asset
    auth = await db.get_asset_authorization(scan_in.asset_id)
    if not auth or auth.status != "verified" or (auth.expires_at and auth.expires_at < now()):
        raise Forbidden("Asset authorization not verified or expired")
    # ...
```

---

## Workspace Isolation (RLS)

### Supabase RLS Policy Pattern

```sql
-- Enable RLS on all workspace-scoped tables
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
-- ... all tables

-- Helper function: current user's workspace IDs
CREATE OR REPLACE FUNCTION current_user_workspace_ids()
RETURNS uuid[] LANGUAGE sql STABLE AS $$
  SELECT array_agg(workspace_id) FROM workspace_members
  WHERE user_id = auth.uid() AND joined_at IS NOT NULL;
$$;

-- Policy: Members can SELECT
CREATE POLICY "workspace_member_select" ON assets
  FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Policy: Admins/Owners can INSERT/UPDATE/DELETE
CREATE POLICY "workspace_admin_write" ON assets
  FOR ALL USING (
    workspace_id = ANY(current_user_workspace_ids()) AND
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = assets.workspace_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
      AND joined_at IS NOT NULL
    )
  );

-- Special: Audit logs only for admins
CREATE POLICY "workspace_admin_audit" ON audit_logs
  FOR SELECT USING (
    workspace_id = ANY(current_user_workspace_ids()) AND
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = audit_logs.workspace_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
      AND joined_at IS NOT NULL
    )
  );
```

### Backend RLS Context

```python
# Every request sets the RLS context
@app.middleware("http")
async def set_rls_context(request: Request, call_next):
    user = request.state.user  # Set by auth middleware
    if user:
        # Set Postgres session variable for RLS
        async with db.acquire() as conn:
            await conn.execute(
                "SET LOCAL app.current_user_id = $1", user.id
            )
            await conn.execute(
                "SET LOCAL app.current_workspace_id = $1", 
                request.state.workspace_id or "00000000-0000-0000-0000-000000000000"
            )
    response = await call_next(request)
    return response
```

---

## Secrets Management

### What Are Secrets
- Cloud provider credentials (AWS keys, GCP service accounts)
- Git tokens (GitHub PAT, GitLab token)
- API keys (Semgrep, third-party scanners)
- Database passwords
- Webhook secrets
- Encryption keys

### Storage Strategy

| Secret Type | Storage | Access |
|-------------|---------|--------|
| Cloud credentials | Supabase Vault / AWS Secrets Manager | Backend only, per-asset |
| Git tokens | Supabase Vault | Backend only, per-asset |
| API keys | Railway Environment Variables | Backend service |
| Database URL | Railway Environment Variables | Backend service |
| Firebase Admin Key | Railway Environment Variables | Backend service |
| AI API Keys | Railway Environment Variables | Backend service |
| Webhook secrets | Railway Environment Variables | Backend service |

### Secret Reference Pattern

```python
# In asset.connection_config
{
  "type": "github",
  "url": "https://github.com/org/repo",
  "credentials_ref": "vault:secret/github/org-repo"  # Reference, not value
}

# Backend resolves at scan time
async def resolve_credentials(ref: str) -> dict:
    if ref.startswith("vault:secret/"):
        return await supabase_vault.get_secret(ref[len("vault:secret/"):])
    elif ref.startswith("railway:env/"):
        return {"token": os.environ[ref[len("railway:env/"):]]}
    raise ValueError(f"Unknown secret ref: {ref}")
```

**Never**: Store secrets in `assets.connection_config` directly. Never log secrets. Never return secrets in API responses.

---

## AI Safety Controls

### Output Validation Pipeline

```python
class AIOutputValidator:
    def __init__(self, schema: type[BaseModel], min_confidence: float = 0.6):
        self.schema = schema
        self.min_confidence = min_confidence
    
    async def validate(self, output: dict, context: ValidationContext) -> ValidationResult:
        # 1. Schema validation
        try:
            validated = self.schema(**output)
        except ValidationError as e:
            return ValidationResult(valid=False, errors=[str(e)])
        
        # 2. Confidence gate
        if validated.metadata.confidence < self.min_confidence:
            return ValidationResult(
                valid=False, 
                errors=[f"Confidence {validated.metadata.confidence} below threshold {self.min_confidence}"]
            )
        
        # 3. Hallucination detection (basic)
        if await self._detect_hallucination(validated, context):
            return ValidationResult(valid=False, errors=["Potential hallucination detected"])
        
        # 4. Scope validation (workspace isolation)
        if not self._validate_scope(validated, context):
            return ValidationResult(valid=False, errors=["Output references unauthorized resources"])
        
        return ValidationResult(valid=True, data=validated)
    
    async def _detect_hallucination(self, data: BaseModel, context: ValidationContext) -> bool:
        # Cross-reference finding IDs, asset IDs against database
        # Check for impossible claims (e.g., "CVE-2024-99999" doesn't exist)
        # Flag if AI references non-existent evidence
        pass
    
    def _validate_scope(self, data: BaseModel, context: ValidationContext) -> bool:
        # Ensure all resource IDs belong to context.workspace_id
        pass
```

### Model Safety Settings

```python
MODEL_SAFETY_CONFIG = {
    "gemini": {
        "safety_settings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        ],
        "generation_config": {
            "temperature": 0.1,  # Low for structured output
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }
    },
    "grok": {
        "temperature": 0.2,
        "max_tokens": 4096,
    }
}
```

### AI Action Restrictions

| Action | Allowed? | Control |
|--------|----------|---------|
| Read workspace data | ✅ | Via validated tools |
| Write findings/evidence | ✅ | Via validated schema |
| Propose remediation | ✅ | Human approval required |
| Execute code changes | ❌ | Never |
| Modify infrastructure | ❌ | Never |
| Access external APIs | ❌ | Only via approved integrations (n8n) |
| Store secrets | ❌ | Never |
| Self-modify prompts | ❌ | Fixed system prompts |

---

## Audit Logging

### Events That Must Be Audited

| Category | Actions |
|----------|---------|
| Authentication | Login, logout, token refresh, MFA change |
| Workspace | Create, delete, settings change, plan change |
| Membership | Invite, join, leave, role change, remove |
| Assets | Create, update, delete, authorization change |
| Authorization | Submit, verify, reject, expire, revoke |
| Scans | Start, cancel, complete, fail, config change |
| Findings | Create, triage, status change, delete, bulk update |
| Remediation | Propose, approve, reject, apply, verify |
| Reports | Generate, download, share |
| Chat | New conversation, message (metadata only) |
| Settings | Integrations, notifications, retention, secrets |
| Admin | User impersonation, data export, compliance actions |

### Audit Log Entry

```python
class AuditLogEntry(BaseModel):
    workspace_id: UUID
    user_id: UUID | None  # None for system actions
    action: str  # Standardized: "asset.create", "scan.start", "finding.triage"
    resource_type: str  # "asset", "scan", "finding", etc.
    resource_id: UUID | None
    old_state: dict | None  # For updates
    new_state: dict | None  # For creates/updates
    ip_address: IPvAnyAddress | None
    user_agent: str | None
    request_id: UUID  # Correlation ID
    timestamp: datetime = Field(default_factory=datetime.utcnow)
```

### Implementation

```python
async def audit_log(
    db: DatabaseSession,
    workspace_id: UUID,
    action: str,
    resource_type: str,
    resource_id: UUID | None = None,
    old_state: dict | None = None,
    new_state: dict | None = None,
    user_id: UUID | None = None,
    request: Request | None = None,
):
    entry = AuditLogEntry(
        workspace_id=workspace_id,
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        old_state=old_state,
        new_state=new_state,
        ip_address=request.client.host if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        request_id=request.state.request_id if request else uuid4(),
    )
    await db.insert(entry)
    # Also emit to SIEM/webhook if configured
```

---

## Network Security

### TLS
- All external traffic: TLS 1.2+ (Railway terminates)
- Internal service-to-service: mTLS (future) or Railway private network

### CORS
```python
CORS_CONFIG = {
    "allow_origins": [os.environ["FRONTEND_URL"]],  # Single origin
    "allow_credentials": True,
    "allow_methods": ["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    "allow_headers": ["Authorization", "Content-Type", "X-Requested-With"],
    "max_age": 3600,
}
```

### Rate Limiting
```python
RATE_LIMITS = {
    "auth": "10/minute",
    "scan_start": "5/minute per workspace",
    "chat": "30/minute per user",
    "api_default": "100/minute per user",
    "webhook": "1000/minute per source",
}
```

### Security Headers
```
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://*.supabase.co wss://*.supabase.co https://*.firebaseapp.com;
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

---

## Data Protection

### Encryption
| Data | At Rest | In Transit |
|------|---------|------------|
| Database | Supabase (AES-256) | TLS 1.3 |
| Storage | Supabase Storage (AES-256) | TLS 1.3 |
| Secrets | Vault (AES-256) | TLS 1.3 |
| Backups | Supabase (AES-256) | TLS 1.3 |

### PII Handling
- Minimal PII: email, name, avatar only
- No SSN, credit card, health data
- Right to deletion: `profiles` + `workspace_members` cascade
- Data export: JSON via API (GDPR Art. 20)

### Retention
| Data | Retention | Deletion |
|------|-----------|----------|
| Scan events | 90 days | Auto-purge job |
| Agent runs | 1 year | Auto-purge job |
| Findings | Until deleted | Manual/Retention policy |
| Evidence | Until finding deleted | Cascade |
| Audit logs | 7 years | Never (compliance) |
| Chat messages | 2 years | Auto-purge job |
| Reports | 3 years | Manual |

---

## Vulnerability Management (Self)

### Dependency Scanning
- `pip-audit` / `safety` in CI for Python backend
- `npm audit` / `pnpm audit` for Next.js frontend
- Automated PRs for updates (Dependabot/Renovate)

### Container Security
- Base images: `python:3.11-slim`, `node:20-alpine`
- No root user in containers
- Read-only filesystem where possible
- Distroless for production (future)

### Penetration Testing
- Annual third-party pen test
- Bug bounty program (post-launch)
- Internal red team exercises quarterly

---

## Incident Response

### Security Incident Classification

| Severity | Examples | Response Time |
|----------|----------|---------------|
| Critical | Data breach, RCE, auth bypass | < 1 hour |
| High | Privilege escalation, major info leak | < 4 hours |
| Medium | XSS, CSRF, info disclosure | < 24 hours |
| Low | Minor config issues | < 1 week |

### Response Plan
1. **Detect** → Alerting (Sentry, logs, user reports)
2. **Triage** → Classify severity, assign owner
3. **Contain** → Revoke tokens, disable features, WAF rules
4. **Eradicate** → Patch, rotate secrets, deploy fix
5. **Recover** → Verify fix, monitor, restore service
6. **Postmortem** → Root cause, timeline, action items (blameless)

---

## Compliance Considerations

| Standard | Relevance | Implementation |
|----------|-----------|----------------|
| SOC 2 Type II | Target | Audit logs, access control, encryption, monitoring |
| GDPR | EU customers | Data minimization, deletion, export, DPA |
| ISO 27001 | Future | ISMS, risk assessment, controls |
| NIST CSF | Framework | Identify, Protect, Detect, Respond, Recover |
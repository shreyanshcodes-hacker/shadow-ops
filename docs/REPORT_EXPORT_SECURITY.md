# REPORT EXPORT SECURITY

## 1. Overview

This document describes the security controls for report generation, export, storage, and download in the ShadowOps platform.

---

## 2. Threat Model

### 2.1 Assets Protected
- Report content (security findings, evidence, remediation details)
- Finding fingerprints and evidence hashes
- Remediation patches and verification results
- Workspace membership and authorization data
- AI-generated narratives (if enabled)

### 2.2 Threat Actors
| Actor | Capabilities | Motivation |
|-------|--------------|------------|
| Unauthorized user | Network access, API access | Data exfiltration, reconnaissance |
| Malicious workspace member | Legitimate access to one workspace | Cross-workspace data access |
| Compromised API key | Full API access as service account | Bulk data extraction |
| Insider threat | Legitimate access + elevated privileges | Data theft, sabotage |

### 2.3 Attack Vectors
| Vector | Impact | Likelihood |
|--------|--------|------------|
| IDOR (Insecure Direct Object Reference) | Cross-workspace report access | Medium |
| Signed URL leakage | Unauthorized report download | Medium |
| Storage bucket misconfiguration | Public report access | Low |
| Secret exposure in exports | Credential compromise | High |
| AI prompt injection | Narrative manipulation | Low |
| Path traversal in storage | Arbitrary file read | Low |

---

## 3. Security Controls

### 3.1 Access Control

#### 3.1.1 API Endpoint Authorization
- All `/reports/*` endpoints require valid Firebase JWT
- `require_workspace_member` dependency validates workspace membership
- Role-based: `OWNER`, `ADMIN`, `MEMBER`, `VIEWER` for reads; `OWNER`, `ADMIN` for generation
- Workspace ID validated against user's memberships on every request

#### 3.1.2 Database Row Level Security (RLS)
```sql
-- Reports table
CREATE POLICY reports_workspace_isolation ON reports
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Report sections
CREATE POLICY report_sections_workspace_isolation ON report_sections
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Report exports
CREATE POLICY report_exports_workspace_isolation ON report_exports
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));
```

#### 3.1.3 Report ID Isolation
- Report UUIDs are v4 (random), not sequential
- Cross-workspace access attempt returns 404 (not 403) to prevent enumeration
- Report detail endpoint validates workspace membership before returning data

### 3.2 Export Security

#### 3.2.1 PDF Generation
- **Library**: `reportlab` (server-side only)
- **Input**: Structured data only (no HTML rendering)
- **No**: Browser rendering, JavaScript execution, external resource loading
- **Output**: Binary PDF written to bytes buffer

#### 3.2.2 JSON Export
- **Serialization**: Standard `json.dumps()` with `default=str`
- **Sanitization**: No HTML/script tags in structured data
- **Schema**: Fixed `report-v1` schema, no dynamic fields

#### 3.2.3 Secret Redaction
**Applied during export generation** (both PDF and JSON):

| Pattern Category | Examples |
|------------------|----------|
| API Keys | `api_key`, `apikey`, `api-key`, `secret_key`, `access_token` |
| Passwords | `password`, `passwd`, `pwd`, `secret` |
| Tokens | `bearer`, `jwt`, `oauth`, `ssh-rsa`, `ssh-ed25519` |
| Cloud Credentials | `aws_access_key_id`, `aws_secret_access_key`, `gcp_service_account` |
| Database | `postgresql://`, `mongodb://`, `mysql://` with credentials |
| Private Keys | `-----BEGIN PRIVATE KEY-----`, `-----BEGIN RSA PRIVATE KEY-----` |

**Implementation**: Recursive traversal of all string values in report data; matches replaced with `[REDACTED]`

#### 3.2.4 Code Snippet Handling
- Finding code snippets included but truncated to 500 chars
- No full source files embedded
- Evidence references point to finding IDs, not inline content

### 3.3 Storage Security

#### 3.3.1 Supabase Storage (Primary)
- **Bucket**: `reports` (private, not public)
- **Path Structure**: `{workspace_id}/{report_id}/report.{pdf|json}`
- **RLS Policies**: Enforced at Supabase level
- **Upload**: Service role key (server-side only)
- **Download**: Signed URLs only

#### 3.3.2 Signed URL Generation
```python
# Server-side only
response = supabase.storage.from_('reports').create_signed_url(
    path=storage_path,
    expires_in=3600  # 1 hour default
)
```
- **Expiry**: 1 hour default (configurable)
- **Single-use**: Not enforced but short expiry limits exposure
- **Audit**: Download logged with `report.downloaded` event

#### 3.3.3 Local Fallback
- **Path**: `/tmp/reports/{workspace_id}/{report_id}/`
- **Access**: `file://` URLs only when Supabase unavailable
- **Cleanup**: Manual (tmp cleaner) or application-managed

#### 3.3.4 Export Metadata
```sql
-- report_exports table
storage_path: "{workspace_id}/{report_id}/report.pdf"
file_size_bytes: 245760
checksum: "sha256_hex"
expires_at: timestamp with time zone
generated_by: uuid (user)
```

### 3.4 Transport Security

- **HTTPS Only**: All API endpoints served over TLS 1.2+
- **HSTS**: Enforced via infrastructure
- **CORS**: Restricted to configured frontend origin
- **Cookies**: `Secure`, `HttpOnly`, `SameSite=Strict` for auth

---

## 4. Audit Logging

### 4.1 Events Logged

| Event | Actor | Resource | Details |
|-------|-------|----------|---------|
| `report.requested` | User | Report | report_type, format, period |
| `report.generation_started` | System | Report | - |
| `report.generated` | System | Report | format, file_size_bytes |
| `report.generation_failed` | System | Report | error |
| `report.exported` | User | ReportExport | format, file_size_bytes |
| `report.downloaded` | User | ReportExport | export_id, format |

### 4.2 Log Fields
```json
{
  "workspace_id": "uuid",
  "user_id": "uuid",
  "action": "string",
  "resource_type": "report|report_export",
  "resource_id": "uuid",
  "old_state": "object|null",
  "new_state": "object",
  "ip_address": "string|null",
  "user_agent": "string|null",
  "request_id": "uuid",
  "created_at": "timestamp with time zone"
}
```

### 4.3 Data Not Logged
- Report content (findings, evidence, narratives)
- Export file content
- Signed URLs
- Secret values (redacted before any log)

---

## 5. AI Narrative Security

### 5.1 Data Minimization
- Only aggregated metrics sent to AI (no raw findings/evidence)
- Finding descriptions treated as untrusted input
- Context sanitized via `TRUSTED_SYSTEM_INSTRUCTIONS` / `UNTRUSTED_SECURITY_EVIDENCE` delimiters

### 5.2 Provider Controls
- Uses existing `AIManager` with `AIProvider` abstraction
- Timeouts: 30s per call
- Retries: 2 max
- Output validation: Strict schema, length limits

### 5.3 Output Handling
- **Label**: "AI-Assisted — Advisory Only" prefix
- **No Override**: Narrative never modifies metrics, statuses, or findings
- **Fallback**: Graceful degradation if AI unavailable
- **Audit**: `ai.narrative_generated` event logged

---

## 6. Configuration & Hardening

### 6.1 Environment Variables
```bash
# Required
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# Optional (for AI narrative)
GEMINI_API_KEY=xxx
GROK_API_KEY=xxx

# Export Settings
EXPORT_URL_EXPIRY_SECONDS=3600
DEFAULT_REPORT_TIMEOUT=300
MAX_REPORT_SIZE_MB=50
```

### 6.2 Feature Flags
```python
ENABLE_AI_NARRATIVE = True        # Can disable globally
ENABLE_PDF_GENERATION = True      # Can disable if reportlab issues
ENABLE_JSON_EXPORT = True         # Always enabled
ENABLE_SUPABASE_STORAGE = True    # False = local-only mode
```

### 6.3 Size Limits
- Max report size: 50 MB (configurable)
- Max export URL expiry: 24 hours
- Max concurrent generations: 1 per workspace (recommended)

---

## 7. Incident Response

### 7.1 Suspected Export Leakage
1. **Identify**: Check audit logs for `report.downloaded` events
2. **Revoke**: Delete export record → signed URL becomes invalid
3. **Rotate**: If API keys in report, rotate immediately
4. **Notify**: Inform workspace owners per policy

### 7.2 Storage Compromise
1. **Detect**: Unusual download patterns, unauthorized access logs
2. **Contain**: Disable Supabase Storage bucket, switch to local fallback
3. **Investigate**: Review audit logs, check for data exfiltration
4. **Remediate**: Rotate service role key, rebuild bucket policies

### 7.3 Cross-Workspace Access Attempt
1. **Detect**: 404 responses for report IDs (not 403)
2. **Alert**: Multiple failed access attempts from same user
3. **Action**: Rate limit, review user permissions, potential account compromise

---

## 8. Compliance Considerations

| Requirement | Implementation |
|-------------|----------------|
| Data Minimization | Only aggregated metrics in AI; findings by reference |
| Purpose Limitation | Exports only for authorized workspace members |
| Storage Limitation | Signed URLs expire; exports auto-expire after 30 days |
| Integrity | SHA256 checksums on all exports |
| Confidentiality | TLS in transit; RLS at rest; encryption at rest (Supabase) |
| Availability | Local fallback for storage; graceful AI degradation |

---

## 9. Penetration Testing Checklist

| Test | Expected Result |
|------|-----------------|
| Access report from another workspace | 404 Not Found |
| Access export without workspace membership | 404 Not Found |
| Use expired signed URL | 403 Forbidden / URL expired |
| Guess report UUID | 404 (not 403) |
| Inject script in report title | Escaped in PDF/JSON |
| Extract secrets from export | `[REDACTED]` in output |
| Access report during generation | Status shows `generating` |
| Download without audit log | Audit log entry created |
| Exceed rate limit | 429 Too Many Requests |

---

## 10. Future Enhancements

| Enhancement | Priority | Description |
|-------------|----------|-------------|
| Encryption at rest (application-level) | Medium | Encrypt exports before storage |
| Watermarking | Low | User-specific watermarks on PDF |
| DRM / Access expiry | Low | Time-based access revocation |
| Export approval workflow | Medium | Require admin approval for sensitive exports |
| SIEM integration | High | Stream audit logs to SIEM |

---

*Security Version: 1.0*
*Last Updated: 2026-10-13*
*Classification: Internal - Security Documentation*
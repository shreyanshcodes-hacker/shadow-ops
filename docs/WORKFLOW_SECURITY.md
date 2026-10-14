# WORKFLOW SECURITY

## 1. Overview

This document describes the security model for the ShadowOps workflow automation system. The workflow system enables controlled automation of security operations while maintaining strict security boundaries.

---

## 2. Security Principles

### 2.1 Core Principles

| Principle | Implementation |
|-----------|----------------|
| **Explicit Allowlist** | Only registered actions can execute; no dynamic code |
| **No Arbitrary Execution** | No shell commands, eval(), or arbitrary URLs |
| **Input Validation** | All action parameters validated against schema |
| **Output Sanitization** | Action outputs sanitized before storage |
| **Timeout Enforcement** | Hard timeout per workflow (default 30 min) |
| **Idempotency** | Every workflow run has unique idempotency key |
| **Audit Trail** | Every action execution logged with input/output |
| **Failure Isolation** | Workflow failure never affects source security event |

### 2.2 Threat Model

| Threat | Mitigation |
|--------|------------|
| Arbitrary code execution | No eval/exec; only registered actions |
| Command injection | No shell commands; typed parameters |
| SQL injection | Parameterized queries only |
| Path traversal | No filesystem access in actions |
| SSRF | No arbitrary URL fetch; n8n allowlisted only |
| Privilege escalation | Actions run with workflow context, not elevated |
| Data exfiltration | Action outputs sanitized; no secrets in outputs |
| DoS via workflows | Timeout + rate limits + concurrency limits |
| Replay attacks | Idempotency keys + event deduplication |

---

## 3. Workflow Registry

### 3.1 Action Registry (`WorkflowRegistry`)

All actions must be explicitly registered in the `WorkflowRegistry`:

```python
registry = WorkflowRegistry()
registry.register("create_notification", handler)
registry.register("send_email", handler)
# ... etc
```

**Built-in Actions** (immutable, cannot be overridden):
| Action | Description | Parameters |
|--------|-------------|------------|
| `create_notification` | Create in-app notification | title, message, user_id, channels, etc. |
| `send_email` | Send email via DeliveryService | to, subject, html, text |
| `request_human_review` | Request human review | resource_id, reviewers, etc. |
| `generate_report` | Trigger report generation | report_type, period, etc. |
| `n8n_dispatch` | Dispatch to n8n workflow | workflow_id, payload |
| `wait_for_event` | Wait for event (placeholder) | event_type, timeout |

**Adding Custom Actions**:
```python
# Only in controlled deployment, not at runtime
registry.register("custom_action", async_handler)
```

**Security**: Actions can ONLY be registered at startup, never at runtime via API.

---

## 4. Workflow Execution Model

### 4.1 Execution Flow

```
1. Trigger Event → EventOutbox
2. Background worker creates WorkflowRun (PENDING)
3. Worker executes workflow (RUNNING)
   ├── For each action:
   │   ├── Resolve params with context
   │   ├── Execute action handler
   │   │   ├── Validate input schema
   │   │   ├── Execute with timeout
   │   │   ├── Sanitize output
   │   │   └── Record WorkflowRunEvent
   │   └── Check status → continue or fail
   └── Complete → COMPLETED/FAILED
```

### 4.2 Idempotency

Every workflow run has a unique `idempotency_key`:
```
{workflow_id}:{workspace_id}:{timestamp}
```

- Prevents duplicate execution on retry
- Client can safely retry API calls
- Database unique constraint enforces

### 4.3 Timeout Enforcement

- Default timeout: 30 minutes (configurable per workflow)
- Per-action timeout: 5 minutes (hard limit)
- On timeout: workflow marked FAILED, actions stop

### 4.4 Failure Handling

| Failure Type | Handling |
|--------------|----------|
| Action validation error | Workflow FAILED, error logged |
| Action timeout | Workflow FAILED, partial results saved |
| Action exception | Workflow FAILED, error logged |
| Workflow timeout | Workflow FAILED, actions stop |
| System crash | On restart: PENDING runs resume |

---

## 5. Action Security

### 5.1 Parameter Validation

Each action validates input against a schema:

```python
async def _action_create_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
    # Validate required fields
    required = ["title", "message", "user_id"]
    for field in required:
        if field not in params:
            return {"status": "failed", "error": f"Missing required field: {field}"}
    
    # Sanitize inputs
    params["title"] = sanitize(params["title"])
    params["message"] = sanitize(params["message"])
    ...
```

### 5.2 Output Sanitization

All action outputs sanitized before storage:

```python
def sanitize_output(output: Any) -> Any:
    if isinstance(output, dict):
        return {k: sanitize(v) for k, v in output.items()}
    elif isinstance(output, str):
        # Remove potential secrets
        return redact_secrets(output)
    return output
```

### 5.3 Secret Redaction

Action outputs automatically redacted:
- API keys, tokens, passwords
- Connection strings
- Private keys
- JWT tokens
- AWS/GCP credentials

### 5.4 No Secrets in Action Context

Actions receive only the workflow `input_payload` - no database credentials, API keys, or service credentials.

---

## 6. n8n Integration Security

### 6.1 Security Boundaries

| Boundary | Control |
|----------|---------|
| **Default State** | Disabled (`N8N_ENABLED=false`) |
| **Workflow Allowlist** | Only configured workflow IDs allowed |
| **Authentication** | API key + webhook secret |
| **Payload Minimization** | Only event data, no credentials |
| **Network Isolation** | n8n runs in separate network/VPC |
| **No DB Access** | n8n cannot query ShadowOps DB directly |
| **No Security Bypass** | Cannot approve remediation, close findings, modify risk |

### 6.2 Dispatch Flow

```
Workflow Action: n8n_dispatch
    ↓
Validate workflow_id in allowlist
    ↓
Create signed webhook payload
    ↓
POST to n8n webhook URL with:
  - X-Webhook-Secret header
  - Minimal event payload
    ↓
n8n validates secret, executes workflow
    ↓
Result logged, not used for security decisions
```

### 6.3 Payload Sanitization

Only these fields sent to n8n:
```json
{
  "event": "finding.created",
  "timestamp": "2026-10-14T10:30:00Z",
  "correlation_id": "uuid",
  "payload": {
    "finding_id": "uuid",
    "severity": "critical",
    "asset_name": "web-server-01"
  }
}
```

**Never sent**:
- User emails, credentials
- Database IDs (except resource IDs)
- Internal system URLs
- API keys, secrets, tokens
- Full finding descriptions with code snippets

### 6.4 Allowlist Configuration

```bash
N8N_ALLOWED_WORKFLOWS=notify_slack,create_jira_ticket,notify_pagerduty
```

Only explicitly listed workflow IDs can be triggered. Empty allowlist = no workflows allowed.

### 6.5 Webhook Security

```http
POST /webhook/notify_slack
X-Webhook-Secret: secret-from-config
Content-Type: application/json

{...payload}
```

- Secret validated before processing
- Replay protection via timestamp
- Idempotency via event_id

---

## 7. Audit & Compliance

### 7.1 Audit Events

All workflow activities logged:

| Event | Fields |
|-------|--------|
| `workflow.run_created` | workflow_id, version, trigger_event |
| `workflow.run_completed` | workflow_id, status, duration, error |
| `workflow.action_executed` | action_name, params, result, duration |
| `workflow.run_retried` | original_run_id, new_run_id |
| `workflow.run_cancelled` | run_id, reason |

### 7.2 Data Retention

| Data | Retention |
|------|-----------|
| WorkflowRun | 1 year |
| WorkflowRunEvent | 1 year |
| EventOutbox | 90 days (completed), 1 year (dead letter) |

### 7.3 Access Control

| Role | Workflow Permissions |
|------|---------------------|
| Owner | Create, view, retry, cancel all workflows |
| Admin | Create, view, retry, cancel all workflows |
| Member | View own workspace workflows |
| Viewer | View only |

---

## 8. Configuration

### Environment Variables

```bash
# Workflow settings
DEFAULT_WORKFLOW_TIMEOUT_MINUTES=30
MAX_WORKFLOW_ACTIONS=50
WORKFLOW_ACTION_TIMEOUT_SECONDS=300

# n8n (optional)
N8N_ENABLED=false
N8N_BASE_URL=https://n8n.example.com
N8N_API_KEY=your-api-key
N8N_WEBHOOK_SECRET=webhook-secret
N8N_ALLOWED_WORKFLOWS=notify_slack,create_jira_ticket
```

### Feature Flags

```python
ENABLE_WORKFLOW_AUTOMATION = True
ENABLE_N8N_INTEGRATION = False  # Disabled by default
MAX_CONCURRENT_WORKFLOWS_PER_WORKSPACE = 10
```

---

## 8. Incident Response

### 8.1 Suspected Malicious Workflow

1. **Identify**: Check audit logs for `workflow.run_created` with suspicious params
2. **Contain**: Cancel run via `POST /notifications/workflows/{id}/cancel`
3. **Investigate**: Review `workflow_run_events` for action details
4. **Remediate**: Disable workflow definition, revoke API keys if compromised
5. **Notify**: Alert workspace owners

### 8.2 Runaway Workflow

1. **Detect**: Monitor `workflow_runs` with `status=RUNNING` exceeding timeout
2. **Cancel**: Automatic timeout enforcement + manual cancel endpoint
3. **Alert**: Audit log `workflow.run_timeout`

### 8.3 Compromised n8n

1. **Detect**: Unexpected workflow dispatches, unknown execution IDs
2. **Contain**: Set `N8N_ENABLED=false`, revoke webhook secret
3. **Investigate**: Check n8n execution logs
4. **Rotate**: Rotate `N8N_API_KEY` and `N8N_WEBHOOK_SECRET`

---

## 9. Testing Requirements

### 9.1 Security Tests Required

| Test | Description |
|------|-------------|
| Action allowlist enforcement | Unregistered action fails |
| Parameter validation | Invalid params rejected |
| Output sanitization | Secrets redacted in outputs |
| Timeout enforcement | Long-running action times out |
| Idempotency | Duplicate run prevented |
| n8n allowlist | Non-allowlisted workflow rejected |
| Secret redaction | No secrets in action outputs |
| Audit logging | All actions logged |

### 9.2 Chaos Testing

| Scenario | Expected Behavior |
|----------|-------------------|
| Worker crash mid-workflow | Run resumes on restart |
| Database connection lost | Graceful retry with backoff |
| n8n unavailable | Dispatch fails, workflow continues |
| Email provider down | Retry with backoff, then fail |
| Action timeout | Workflow fails, partial results saved |

---

## 10. Compliance

### 9.1 Data Protection

- No PII in workflow payloads (only UUIDs)
- Email addresses only in delivery service, not workflow actions
- User consent for email via preferences

### 9.2 Audit Requirements

- All workflow executions auditable
- Immutable action execution log
- Tamper-evident audit trail

---

*Security Version: 1.0*
*Last Updated: 2026-10-14*
*Classification: Internal - Security Documentation*
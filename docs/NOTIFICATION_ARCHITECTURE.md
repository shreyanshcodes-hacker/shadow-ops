# NOTIFICATION ARCHITECTURE

## 1. Overview

This document describes the architecture of the ShadowOps notification system (Stage 11), including the event processing pipeline, notification delivery, workflow automation, and integration points.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Security Event Sources                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐     │
│  │  Scans   │ │ Findings │ │Remediation│ │Verification│ │Security Team │     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬───────┘     │
└───────┼─────────────┼────────────┼────────────┼─────────────┼──────────────┘
        │             │            │            │             │
        ▼             ▼            ▼            ▼             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Event Outbox (Transactional)                           │
│  event_outbox table: event_type, payload, status, attempts, retry logic    │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Event Processor (Background Worker)                      │
│  • Polls pending events                                                      │
│  • Matches against NotificationRules                                         │
│  • Resolves recipients via RulesService                                      │
│  • Creates Notification records                                             │
│  • Creates NotificationDelivery records per channel                         │
│  • Marks event COMPLETED or schedules retry                                 │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Delivery Service                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ In-App Delivery │  │ Email Delivery  │  │ n8n Dispatch (Optional)     │  │
│  │ (Instant)       │  │ (SMTP/SendGrid/ │  │ • Webhook or API trigger    │  │
│  │                 │  │  Resend/SMTP)   │  │ • Allowlisted workflows     │  │
│  │                 │  │ • Template      │  │ • Signed webhooks           │  │
│  │                 │  │ • Retry/backoff │  │ • Audit logged              │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Notification Center (Frontend)                           │
│  • /notifications - List with filters, pagination                           │
│  • /settings/notifications - Preferences & Rules                            │
│  • Sidebar bell with unread count                                           │
│  • Mark read / mark all read                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details

### 3.1 Event Outbox Service (`app/services/event_outbox.py`)

**Purpose**: Reliable event ingestion using the transactional outbox pattern.

**Key Features**:
- Events written within the same transaction as the source operation
- Status tracking: PENDING → PROCESSING → COMPLETED / FAILED / DEAD_LETTER
- Exponential backoff retry (1min, 2min, 4min, 8min, 16min...)
- Max attempts configurable (default 5)
- Correlation ID for tracing related events

**Event Types** (defined in `EventTypes` class):
- Scan: `scan.completed`, `scan.failed`, `scan.cancelled`
- Finding: `finding.created`, `finding.severity_changed`, `finding.status_changed`, `finding.triaged`
- Attack Path: `attack_path.created`, `attack_path.status_changed`
- Risk: `risk_score.changed`
- Remediation: `remediation.proposed`, `remediation.awaiting_approval`, `remediation.approved`, `remediation.rejected`, `remediation.applied`, `remediation.failed`, `remediation.rolled_back`
- Verification: `verification.completed`, `verification.failed`, `verification.inconclusive`, `verification.review_submitted`
- Report: `report.generated`, `report.generation_failed`, `report.exported`

**Usage**:
```python
from app.services.event_outbox import emit_event, EventTypes

await emit_event(
    db=db,
    workspace_id=workspace_id,
    event_type=EventTypes.FINDING_CREATED,
    payload={"finding_id": str(finding.id), "severity": finding.severity.value},
    actor_id=user_id,
    resource_type="finding",
    resource_id=finding.id,
)
```

### 3.2 Notification Service (`app/services/notification.py`)

**Purpose**: Create and manage in-app notifications.

**Key Features**:
- Deduplication via `deduplication_key` (24-hour window)
- User preference checking (in-app/email per category)
- Priority levels: low, normal, high, critical
- Action URL/label for deep linking
- Expiration support
- Read/unread tracking

**Recipient Resolution**: Delegated to RulesService.

### 3.3 Preferences Service (`app/services/notification.py`)

**Purpose**: Manage user notification preferences per category and channel.

**Categories** (18 total):
- `finding_critical_high`, `finding_severity_changed`
- `scan_failed`, `scan_completed`
- `attack_path_created`, `risk_score_changed`
- `remediation_awaiting_approval`, `remediation_approved`, `remediation_rejected`, `remediation_applied`, `remediation_failed`, `remediation_rolled_back`
- `verification_completed`, `verification_failed`, `verification_inconclusive`
- `report_generated`, `report_generation_failed`
- `security_team_completed`

**Defaults**: In-app enabled, email disabled for all categories.

### 3.4 Rules Service (`app/services/rules.py`)

**Purpose**: Define and evaluate notification routing rules.

**Rule Configuration**:
- Event type filter (exact match on event_type)
- Recipient policy: `asset_owners`, `asset_members`, `workspace_admins`, `workspace_owners`, `specific_users`, `finding_assignees`, `remediation_approvers`
- Severity/status filters
- Enabled channels (in_app, email)
- Deduplication window (minutes)
- Rate limit (per hour)
- Priority override
- Action URL/label templates with `{{variable}}` substitution
- Acknowledgement requirement

**Recipient Resolution**:
- `asset_owners`: Asset creator + authorization verifiers
- `asset_members`: All workspace members with access
- `workspace_admins`/`workspace_owners`: Role-based
- `specific_users`: Explicit user IDs
- `finding_assignees`: Finding's `triaged_by`
- `remediation_approvers`: Workspace admins/owners

**Safety Features**:
- Per-rule rate limiting (per hour)
- Deduplication windows
- Only enabled rules processed
- Rule versioning via `event_version`

### 3.5 Delivery Service (`app/services/delivery.py`)

**Purpose**: Execute notification delivery across channels.

**Channels**:
1. **In-App**: Instant, creates Notification record
2. **Email**: Via pluggable providers (SMTP, SendGrid, Resend)
3. **n8n**: Optional webhook/API dispatch

**Retry Logic**:
- Exponential backoff: 1min, 2min, 4min, 8min, 16min... (max 60min)
- Max 5 attempts by default
- Error categorization: network, auth, rate_limit, validation, unknown
- Permanent failures (auth, validation) don't retry
- Dead letter after max attempts

**Email Providers** (priority order):
1. Resend (modern, good deliverability)
2. SendGrid (enterprise)
3. SMTP (fallback)

**Security**:
- Secret redaction in email content
- Safe template rendering (no script execution)
- Validated recipient addresses
- No secrets in email content

### 3.6 Workflow Service (`app/services/workflow.py`)

**Purpose**: Controlled automation with explicit action allowlist.

**Architecture**:
- Workflow runs triggered by events (via EventOutbox)
- Action registry with explicit allowlist
- Idempotency via idempotency keys
- Timeout enforcement (default 30 min)
- Action execution audit trail

**Built-in Actions** (allowlisted):
- `create_notification` - Create in-app notification
- `send_email` - Send email via DeliveryService
- `request_human_review` - Request human review
- `generate_report` - Trigger report generation
- `n8n_dispatch` - Dispatch to n8n workflow
- `wait_for_event` - Placeholder for async patterns

**Safety**:
- Only registered actions executable
- No arbitrary code/command execution
- Input validation per action
- Execution timeout
- Full audit trail in `workflow_run_events`

### 3.7 n8n Adapter (`app/services/n8n_adapter.py`)

**Purpose**: Optional external workflow automation integration.

**Security Model**:
- **Disabled by default** (`N8N_ENABLED=false`)
- Allowlisted workflow IDs only (`N8N_ALLOWED_WORKFLOWS`)
- Webhook secret validation (`N8N_WEBHOOK_SECRET`)
- API key authentication for direct execution
- Minimal event payloads (no sensitive data)
- No direct database access
- No approval/remediation bypass capabilities

**Configuration**:
```bash
N8N_ENABLED=true
N8N_BASE_URL=https://n8n.example.com
N8N_API_KEY=your-api-key
N8N_WEBHOOK_SECRET=webhook-secret
N8N_ALLOWED_WORKFLOWS=workflow1,workflow2
```

**Fallback**: Core notification system works independently if n8n unavailable.

---

## 4. Data Flow Examples

### 4.1 Finding Created → Notification

```
1. FindingService.create_finding() 
   → emit_event(FINDING_CREATED, {finding_id, severity, ...})
   → EventOutbox record created (transactional)

2. Background worker picks up event
   → Matches rule: event_type="finding.created"
   → Resolves recipients (asset_owners)
   → Creates Notification for each recipient
   → Creates NotificationDelivery for each channel
   → Marks event COMPLETED

3. DeliveryService processes deliveries
   → In-app: already created, marks SENT
   → Email: sends via provider, marks SENT/FAILED
   → n8n: dispatches if workflow allowlisted

4. User sees notification in:
   - Sidebar bell (unread count)
   - /notifications page
   - Email (if enabled)
```

### 4.2 Remediation Approval Workflow

```
1. RemediationService.approve_remediation()
   → emit_event(REMEDIATION_AWAITING_APPROVAL, {proposal_id, ...})
   → EventOutbox record

2. Workflow "remediation_approval_requested" triggered
   → Action: create_notification to remediation_approvers
   → Notification with action_url="/remediations/{id}"

3. Approver clicks link → /remediations/{id}
   → Reviews → Clicks "Approve"
   → RemediationService.approve_remediation()
   → emit_event(REMEDIATION_APPROVED)
   → Creates notification for proposer
```

---

## 5. Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Workspace Isolation | All tables have RLS; queries filtered by workspace_id |
| Authorization | `require_workspace_member` on all endpoints |
| Event Validation | Allowlisted event types; schema validation |
| Recipient Isolation | Rules resolve to specific user IDs; no broadcast |
| Secret Redaction | 32+ patterns in email content; no secrets in payloads |
| Webhook Auth | n8n webhook secret + allowlisted workflows |
| Audit Trail | All mutations logged to audit_logs |
| No Auto-Approval | n8n cannot approve remediation or bypass verification |
| Failure Isolation | Notification failure never affects source operation |

---

## 5. Configuration

### Environment Variables

```bash
# Email (at least one provider required for email delivery)
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@shadowops
SMTP_PASSWORD=***
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=alerts@shadowops.io
SMTP_FROM_NAME="ShadowOps Security"

SENDGRID_API_KEY=SG.***
SENDGRID_FROM_EMAIL=alerts@shadowops.io
SENDGRID_FROM_NAME="ShadowOps Security"

RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=alerts@shadowops.io
RESEND_FROM_NAME="ShadowOps Security"

# n8n (optional)
N8N_ENABLED=false
N8N_BASE_URL=https://n8n.example.com
N8N_API_KEY=your-api-key
N8N_WEBHOOK_SECRET=webhook-secret
N8N_ALLOWED_WORKFLOWS=workflow1,workflow2

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 6. Monitoring & Observability

### Key Metrics
- Event processing latency (p50, p95, p99)
- Delivery success rate by channel
- Queue depth (pending events)
- Retry count distribution
- Dead letter queue size
- Notification read rates

### Audit Events
- `event.received`, `event.rejected`
- `notification.created`, `notification.read`
- `delivery.attempted`, `delivery.succeeded`, `delivery.failed`
- `workflow.started`, `workflow.completed`, `workflow.failed`
- `n8n.dispatched`, `n8n.blocked`

---

*Architecture Version: 1.0*
*Last Updated: 2026-10-14*
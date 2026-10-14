# STAGE 11 BASELINE — Existing Architecture Audit (Stages 0–10)

## 1. Overview

This document audits the current ShadowOps codebase (Stages 0–10) to identify reusable services, verify existing functionality, and catalog gaps before implementing Stage 11: Notifications, Event Processing & Controlled Workflow Automation.

---

## 2. Stage-by-Stage Summary

| Stage | Area | Status | Key Artifacts |
|-------|------|--------|---------------|
| 0 | Project Foundation | ✅ Complete | Next.js 15, FastAPI, Supabase, Railway config |
| 1 | Workspace & Auth | ✅ Complete | Firebase Auth, profiles, workspaces, members |
| 2 | Asset & Authorization | ✅ Complete | Assets, authorization workflow, RLS |
| 3 | Scanning Foundation | ✅ Complete | Semgrep runner, scan targets, scan events |
| 4 | AI Security Manager | ✅ Complete | AI providers, structured analysis, prompt injection defense |
| 5 | Attack Path & Risk | ✅ Complete | Correlation engine, attack paths, deterministic risk |
| 6 | Evidence & Relationships | ✅ Complete | Finding evidence, relationship confirmation |
| 7 | AI Security Team | ✅ Complete | 5 agents, orchestration, human review |
| 8 | Remediation & Patch | ✅ Complete | AI proposals, validation, approval, application, rollback |
| 9 | Verification & Regression | ✅ Complete | Independent verification, baseline capture, evidence comparison, policy engine, human review |
| 10 | Security Reports & Executive Dashboard | ✅ Complete | Dashboard, reports (5 types), PDF/JSON export, trends |

---

## 3. Existing Event/Audit Infrastructure

### 3.1 Audit Logging (`app/security/audit.py`)

- **AuditLog Model**: Immutable append-only table with workspace_id, user_id, action, resource_type, resource_id, old_state, new_state, ip_address, user_agent, request_id, created_at
- **AuditService**: Logs actions with workspace/user context, request metadata
- **Global `audit_log` function**: Convenience wrapper for services
- **Used throughout**: Scans, findings, remediation, verification, reports, approvals

### 3.2 Database Events

- **scan_events table**: Immutable append-only scan lifecycle events (phase, event_type, message, data)
- **agent_runs table**: AI agent execution tracking
- **No centralized event bus**: Events logged directly to audit_logs and domain-specific tables

### 3.3 Existing Event Types (from audit_log actions)

| Domain | Actions |
|--------|---------|
| Scan | scan.created, scan.started, scan.completed, scan.failed, scan.cancelled |
| Finding | finding.created, finding.triaged, finding.fixed |
| Remediation | remediation.proposal.generated, remediation.proposal.approved, remediation.proposal.rejected, remediation.applied, remediation.rolled_back |
| Verification | verification.requested, verification.started, verification.completed, verification.failed, verification.reviewed |
| Report | report.requested, report.generation_started, report.generated, report.generation_failed, report.exported, report.downloaded |
| Security Team | security_team.run_started, security_team.run_completed, security_team.review_submitted |

### 3.4 Supabase Realtime

- **Not configured**: No realtime subscriptions in frontend
- **Database supports it**: PostgreSQL with RLS, but not enabled in Supabase config

### 3.5 Existing Notifications Table (Schema Only)

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    reference_type TEXT,
    reference_id UUID,
    channels TEXT[] DEFAULT '{in_app}',
    read_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);
```

**Status**: Table exists in migration 001, but **no backend service, API, or frontend integration exists**.

---

## 4. Missing for Stage 11

### 4.1 Event Contracts (MISSING)
- No typed, versioned event envelope
- No documented allowlist of supported event types
- No correlation_id for tracing

### 4.2 Reliable Event Delivery (MISSING)
- No transactional outbox pattern
- Events written directly to audit_logs (no async processing guarantee)
- No duplicate detection, retries, backoff, poison event handling

### 4.3 In-App Notification Center (MISSING)
- Table exists but **no service, API, or UI**
- `/notifications` route not implemented
- No unread count, read/unread states, mark-as-read

### 4.4 Notification Preferences (MISSING)
- No preferences table/model
- No settings UI (`/settings/notifications`)
- No category/channel control

### 4.5 Email Delivery (MISSING)
- No email adapter/service
- No provider configuration
- No template system

### 4.6 Notification Rules (MISSING)
- No rule engine
- No recipient resolution logic
- No deduplication, rate limiting

### 4.5 Workflow Automation (MISSING)
- No workflow registry
- No action allowlist
- No n8n integration (planned but not implemented)

### 4.6 Frontend Integration (MISSING)
- No notification bell in layout
- No `/notifications` page
- No `/settings/notifications` page
- No real-time unread indicator

---

## 5. Reusable Services & Infrastructure

### 5.1 Audit Logging (`app/security/audit.py`)
- **Reuse**: Extend for notification audit events
- **Pattern**: `audit_log(db, workspace_id, action, resource_type, ...)`

### 5.2 Database & Repository Layer
- **Repositories**: Pattern established for all entities
- **RLS**: All tables have workspace isolation policies
- **Migrations**: 8 migrations (001–008), next is 009

### 5.3 API Layer (`app/api/v1/`)
- **Conventions**: FastAPI, dependency injection, workspace membership validation
- **Auth**: `get_current_user`, `require_workspace_member`

### 5.4 Frontend (`frontend/app/`)
- **Auth**: Firebase integration with token refresh
- **API Client**: `lib/api.ts` with typed methods
- **UI Components**: Card, Badge, Skeleton, EmptyState, Button, Select, Popover, Tabs
- **State Management**: React Query (TanStack Query)

### 5.5 Settings Page (`frontend/app/(dashboard)/settings/`)
- **Pattern**: Workspace settings with tabs
- **Can extend**: Add notifications tab

---

## 6. Security Boundaries to Preserve

| Boundary | Current Enforcement | Stage 11 Must Maintain |
|----------|---------------------|------------------------|
| Workspace Isolation | RLS + query filtering | All new tables, event delivery |
| Authorization | `require_workspace_member` | All notification endpoints |
| Audit Trail | All mutations logged | All notification events |
| No Data Fabrication | Deterministic engines only | Notifications only for real events |
| Secret Redaction | 32+ patterns in AI | Notification content, email content |
| No Arbitrary Actions | Agents analytical only | Workflow actions allowlisted only |

---

## 7. Key Files to Extend/Create for Stage 11

### New Backend Files
```
app/models/notification.py          # New models (or extend __init__.py)
app/schemas/notification.py         # Pydantic schemas
app/services/event_outbox.py        # Transactional outbox
app/services/notification.py        # NotificationService
app/services/delivery.py            # DeliveryService (email, in-app)
app/services/preferences.py         # PreferencesService
app/services/rules.py               # RulesService (recipient resolution)
app/services/workflow.py            # WorkflowService (registry, execution)
app/services/email_adapter.py       # EmailAdapter (provider abstraction)
app/services/n8n_adapter.py         # N8nAdapter (optional, disabled by default)
app/api/v1/notifications.py         # API endpoints
app/api/v1/preferences.py           # Preferences endpoints
```

### New Frontend Files
```
app/(dashboard)/notifications/page.tsx
app/(dashboard)/settings/notifications/page.tsx
components/notifications/NotificationBell.tsx
components/notifications/NotificationCenter.tsx
components/notifications/NotificationItem.tsx
```

### Database Migration
```
supabase/migrations/009_stage11_notifications.sql
```

### Documentation
```
docs/NOTIFICATION_ARCHITECTURE.md
docs/EVENT_CATALOG.md
docs/WORKFLOW_SECURITY.md
docs/EMAIL_AND_N8N_SETUP.md
docs/DELIVERY_FAILURE_RECOVERY.md
docs/STAGE_11_REPORT.md
```

---

## 8. Implementation Priority for Stage 11

1. **Database Migration & Models** — Foundation for all else
2. **Event Contracts & Outbox** — Reliable event ingestion
3. **Notification Service & In-App Delivery** — Core notification creation
3. **Preferences Service & API** — User control
4. **Rules Service** — Recipient resolution, deduplication
5. **Email Adapter** — External delivery (optional)
6. **Workflow Service & Registry** — Controlled automation
7. **n8n Adapter** — Optional, disabled by default
8. **API Endpoints** — All notification operations
9. **Frontend Notification Center** — In-app UX
10. **Frontend Settings** — Preferences management
11. **Notification Bell** — Global unread indicator
12. **Tests** — Unit + integration
13. **Documentation** — Architecture, events, workflows, security

---

## 9. Critical Decisions for Stage 11

| Decision | Recommendation |
|----------|----------------|
| Event envelope format | JSON with versioned schema, correlation_id, allowlisted event types |
| Outbox pattern | Transactional outbox table with async processor (no Redis) |
| Duplicate prevention | Stable event_id + rule_id composite unique constraints |
| Retry policy | Exponential backoff (max 5), bounded, distinguish retryable vs permanent |
| Email provider | Abstract interface, optional config, graceful degradation |
| n8n integration | Optional adapter, disabled by default, allowlisted workflows only |
| Real-time | Not required initially; polling with React Query sufficient |
| Workflow actions | Explicit allowlist: notify, request_review, generate_report |
| Rate limiting | Per-workspace, per-recipient, per-event-type |

---

*Generated: 2026-10-14*
*Baseline for Stage 11 Implementation*
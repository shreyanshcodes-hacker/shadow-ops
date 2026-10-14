# DELIVERY FAILURE RECOVERY

## 1. Overview

This document describes the failure recovery mechanisms for the ShadowOps notification delivery system, including retry logic, dead letter handling, manual intervention procedures, and monitoring.

---

## 2. Delivery Lifecycle

```
PENDING → SENT → DELIVERED
    ↓
RETRYING (on transient failure)
    ↓
FAILED (after max attempts)
    ↓
DEAD LETTER (manual intervention required)
```

---

## 2. Retry Logic

### 2.1 Retry Policy

| Attempt | Delay | Cumulative |
|---------|-------|------------|
| 1 | Immediate | 0s |
| 2 | 1 minute | 1m |
| 3 | 2 minutes | 3m |
| 4 | 4 minutes | 7m |
| 5 | 8 minutes | 15m |
| 6+ | 16 minutes (capped at 60m) | - |

**Formula**: `delay = min(2^(attempt-1), 60) minutes`

### 2.2 Retryable vs Permanent Errors

| Category | Errors | Retry? |
|----------|--------|--------|
| **Network** | Timeout, connection reset, DNS failure | Yes |
| **Rate Limit** | 429 Too Many Requests, quota exceeded | Yes (with backoff) |
| **Server Error** | 5xx, upstream service unavailable | Yes |
| **Auth** | 401, 403, invalid credentials | No |
| **Validation** | 400, malformed request, invalid email | No |
| **Not Found** | 404, resource deleted | No |
| **Permanent Failure** | Bounced email, blocked domain | No |

### 2.3 Error Categorization

```python
def categorize_error(error: Exception) -> str:
    error_str = str(error).lower()
    if "timeout" in error_str or "connection" in error_str:
        return "network"
    elif "auth" in error_str or "credential" in error_str or "unauthorized" in error_str:
        return "auth"
    elif "rate limit" in error_str or "quota" in error_str:
        return "rate_limit"
    elif "invalid" in error_str or "malformed" in error_str:
        return "validation"
    return "unknown"
```

---

## 3. Delivery Status Transitions

```
PENDING → SENT → DELIVERED (success)
    ↓
RETRYING → PENDING (after backoff) → SENT → DELIVERED
    ↓ (permanent error or max attempts)
FAILED
    ↓
DEAD LETTER (manual intervention)
```

**Status Definitions**:
| Status | Meaning |
|--------|---------|
| PENDING | Queued, not yet attempted |
| SENT | Successfully handed to provider |
| DELIVERED | Confirmed delivered (email: provider confirmation) |
| RETRYING | Transient failure, will retry |
| FAILED | Permanent failure or max attempts reached |
| BOUNCED | Email bounced (permanent) |

---

## 3. Dead Letter Handling

### 3.1 Dead Letter Criteria

A delivery enters dead letter state when:
1. `attempt_count >= max_attempts` (default 5)
2. Error category is permanent (auth, validation, bounced)
3. Manual move by operator

### 3.2 Dead Letter Queue

Dead letter deliveries are visible in:
- Admin API: `GET /notifications/deliveries?status=dead_letter`
- Dashboard: Notification detail page shows failed deliveries

### 3.3 Recovery Procedures

#### 3.2.1 Network/Transient Failures
```bash
# Retry via API
curl -X POST http://localhost:8000/api/v1/notifications/deliveries/{delivery_id}/retry \
  -H "Authorization: Bearer <token>"
```

Or bulk retry:
```sql
UPDATE notification_deliveries 
SET status = 'pending', attempt_count = 0, last_error = NULL, next_retry_at = NULL
WHERE status = 'failed' 
  AND last_error_category IN ('network', 'rate_limit')
  AND created_at > NOW() - INTERVAL '24 hours';
```

#### 3.2.2 Configuration Errors (Auth, Validation)
1. Fix root cause (update API key, fix email template, etc.)
2. Retry manually via API or SQL
3. Monitor for recurrence

#### 3.2.3 Permanent Failures (Bounced, Blocked)
1. Mark recipient as unavailable
2. Update user preferences: disable email for affected categories
3. Notify user via in-app to update email
4. Do NOT retry automatically

```sql
-- Disable email for bounced recipients
UPDATE notification_preferences 
SET email_enabled = false 
WHERE user_id IN (
    SELECT recipient_id FROM notification_deliveries 
    WHERE status = 'bounced' 
    AND created_at > NOW() - INTERVAL '7 days'
);
```

---

## 4. Monitoring & Alerting

### 4.1 Key Metrics

| Metric | Warning | Critical |
|--------|---------|----------|
| Delivery failure rate | > 5% | > 15% |
| Retry queue depth | > 100 | > 1000 |
| Dead letter count | > 10/day | > 100/day |
| Max retry attempts reached | > 5/hour | > 20/hour |

### 4.2 Alert Queries

```sql
-- High failure rate alert
SELECT 
  COUNT(*) FILTER (WHERE status IN ('failed', 'bounced')) * 100.0 / COUNT(*) as failure_rate
FROM notification_deliveries 
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Dead letter accumulation
SELECT COUNT(*) FROM notification_deliveries 
WHERE status = 'failed' AND attempt_count >= max_attempts
  AND created_at > NOW() - INTERVAL '24 hours';

-- Stuck in retrying
SELECT COUNT(*) FROM notification_deliveries 
WHERE status = 'retrying' AND next_retry_at < NOW() - INTERVAL '1 hour';
```

### 4.3 Dashboard Panels

Recommended Grafana/Prometheus panels:
- Delivery success rate (1h, 24h)
- Retry queue depth over time
- Dead letter count by error category
- Delivery latency (P50, P95, P99)
- Channel-specific failure rates

---

## 4. Recovery Procedures

### 4.1 Mass Retry After Provider Outage

```bash
# 1. Identify affected deliveries
SELECT id FROM notification_deliveries 
WHERE status IN ('failed', 'retrying')
  AND last_error_category IN ('network', 'rate_limit')
  AND created_at > NOW() - INTERVAL '4 hours';

# 2. Bulk retry (via admin script)
# Or via API for each delivery
for id in $(psql -t -c "SELECT id FROM ..."); do
  curl -X POST "http://localhost:8000/api/v1/notifications/deliveries/$id/retry" \
    -H "Authorization: Bearer $TOKEN"
done
```

### 4.2 Email Provider Migration

```bash
# 1. Configure new provider (e.g., switch from SMTP to Resend)
# 2. Test with single delivery
curl -X POST /api/v1/notifications/test-email ...

# 2. Retry failed email deliveries
UPDATE notification_deliveries 
SET status = 'pending', attempt_count = 0, next_retry_at = NULL
WHERE channel = 'email' AND status IN ('failed', 'retrying');

# 3. Monitor
watch -n 30 'psql -c "SELECT status, COUNT(*) FROM notification_deliveries WHERE channel='\''email'\'' GROUP BY status"'
```

### 4.3 Corrupted Delivery Records

```sql
-- Fix orphaned deliveries (notification deleted but delivery exists)
DELETE FROM notification_deliveries 
WHERE notification_id NOT IN (SELECT id FROM notifications);

-- Fix duplicate deliveries (same notification, channel, recipient, created_at minute)
WITH dupes AS (
  SELECT id, ROW_NUMBER() OVER (
    PARTITION BY notification_id, channel, recipient_id, date_trunc('minute', created_at)
    ORDER BY created_at
  ) as rn
  FROM notification_deliveries
)
DELETE FROM notification_deliveries WHERE id IN (SELECT id FROM dupes WHERE rn > 1);
```

---

## 5. Manual Intervention Procedures

### 5.1 Accessing Failed Deliveries

```bash
# List failed deliveries needing attention
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/notifications/deliveries/stats?workspace_id=<ws_id>"
```

### 5.2 Inspecting a Delivery

```bash
# Get delivery details
curl -H "Authorization: Bearer <token>" \
  "http://localhost:8000/api/v1/notifications/<notification_id>/deliveries"
```

Response includes:
- Attempt history
- Last error and category
- Provider response
- Next retry time

### 5.3 Manual Retry

```bash
# Retry single delivery
curl -X POST "http://localhost:8000/api/v1/notifications/deliveries/{delivery_id}/retry" \
  -H "Authorization: Bearer <token>"
```

### 5.4 Forcing Delivery Status

```sql
-- Force mark as delivered (if confirmed via other means)
UPDATE notification_deliveries 
SET status = 'delivered', delivered_at = NOW() 
WHERE id = '<delivery_id>';

-- Force mark as sent (if provider accepted but no confirmation)
UPDATE notification_deliveries 
SET status = 'sent', sent_at = NOW() 
WHERE id = '<delivery_id>';
```

---

## 6. Prevention Best Practices

### 6.1 Email Deliverability

| Practice | Implementation |
|----------|----------------|
| **Domain Authentication** | SPF, DKIM, DMARC on sender domain |
| **Dedicated Subdomain** | alerts.yourdomain.com (not @gmail.com) |
| **Consistent From** | Same From address for all notifications |
| **List Hygiene** | Auto-disable email on bounce |
| **Unsubscribe** | Include unsubscribe link (legal requirement) |
| **Reputation Monitoring** | Use provider dashboards (SendGrid, Resend) |

### 6.2 Rate Limiting

```python
# Per-workspace rate limit (configurable per rule)
rate_limit_per_hour = 100  # default

# Per-recipient rate limit
MAX_NOTIFICATIONS_PER_USER_PER_HOUR = 20
```

### 6.3 Deduplication

```python
# Per-rule deduplication window
deduplication_window_minutes = 60  # default

# Key: f"{rule_id}:{event.event_id}:{user_id}"
```

---

## 7. Disaster Recovery

### 7.1 Provider Failure

| Scenario | Recovery |
|----------|----------|
| Primary provider down | Automatic fallback to next provider |
| All providers down | Queue deliveries, retry when restored |
| Provider API changed | Update adapter, deploy fix |

### 7.2 Data Loss Prevention

- All deliveries persisted before sending
- Provider response stored for audit
- Idempotency keys prevent duplicate sends

### 7.2 Backup

```bash
# Backup notification_deliveries table daily
pg_dump -t notification_deliveries shadowops > deliveries_backup_$(date +%Y%m%d).sql

# Restore
psql shadowops < deliveries_backup_20261014.sql
```

---

## 8. Runbook: Common Incidents

### INC-001: Email Provider Down

**Symptoms**: Spike in `delivery.failed` with `network` or `auth` errors

**Runbook**:
1. Check provider status page (SendGrid, Resend, AWS SES)
2. If confirmed outage: wait for provider recovery
3. Monitor retry queue depth
4. If > 1 hour: consider manual retry after recovery
5. Post-incident: Review if fallback provider should be prioritized

### INC-002: Sudden Spike in Bounces

**Symptoms**: `delivery.failed` with `bounced` status, `validation` category

**Runbook**:
1. Identify affected recipients
2. Disable email for those recipients: `UPDATE notification_preferences SET email_enabled=false WHERE user_id IN (...)`
3. Check if sender domain reputation degraded
4. Contact email provider support
5. Review sender reputation (SenderScore, Google Postmaster)

### INC-003: n8n Dispatch Failures

**Symptoms**: `n8n.dispatch_failed` audit events, workflow not executing

**Runbook**:
1. Check n8n health: `curl https://n8n.yourdomain.com/healthz`
2. Verify webhook secret matches
3. Check n8n execution logs for workflow errors
4. If n8n down: Set `N8N_ENABLED=false` to prevent queue buildup
5. When restored: Retry failed dispatches

---

## 9. Testing Recovery Procedures

### 9.1 Chaos Engineering

| Experiment | Expected Result |
|------------|-----------------|
| Kill email provider connection | Retries with backoff, succeeds when restored |
| Kill n8n mid-dispatch | Delivery fails, marked for retry, succeeds when n8n up |
| Network partition | Deliveries queued, processed when connectivity restored |
| Invalid API key | Permanent failure, no retry, alert on auth error |
| Database connection lost | Workers pause, resume on reconnect |

### 9.2 Load Testing

```bash
# Simulate 1000 concurrent deliveries
for i in {1..1000}; do
  curl -X POST http://localhost:8000/api/v1/notifications/test-delivery &
done
wait

# Monitor
watch -n 5 'psql -c "SELECT status, COUNT(*) FROM notification_deliveries GROUP BY status"'
```

---

## 10. Contact & Escalation

| Severity | Response Time | Contacts |
|----------|---------------|----------|
| Critical (all delivery failed) | 15 min | Platform team, DevOps |
| High (failure rate > 15%) | 1 hour | Platform team |
| Medium (failure rate > 5%) | 4 hours | Platform team |
| Low (dead letter > 10/day) | 24 hours | Platform team |

---

*Recovery Guide Version: 1.0*
*Last Updated: 2026-10-14*
*Classification: Internal - Operations*
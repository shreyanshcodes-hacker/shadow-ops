# EMAIL AND N8N SETUP

## 1. Overview

This document describes how to configure email delivery and optional n8n workflow automation for the ShadowOps notification system.

---

## 2. Email Configuration

### 2.1 Provider Selection

The email adapter supports multiple providers with automatic fallback:

| Priority | Provider | Use Case |
|----------|----------|----------|
| 1 | **Resend** | Modern, best deliverability, generous free tier |
| 2 | **SendGrid** | Enterprise, high volume, advanced analytics |
| 3 | **SMTP** | Fallback, self-hosted, custom providers |

The adapter automatically detects configured providers and uses the first available.

### 2.2 Resend (Recommended)

**Setup**:
1. Create account at https://resend.com
2. Verify domain
2. Create API key

**Environment Variables**:
```bash
RESEND_API_KEY=re_XXXXXXXXXXXXXXXX
RESEND_FROM_EMAIL=alerts@yourdomain.com
RESEND_FROM_NAME="ShadowOps Security"
```

**Limits**: 3,000 emails/month free, then $20/month for 50,000

### 2.3 SendGrid

**Setup**:
1. Create account at https://sendgrid.com
2. Verify sender identity
3. Create API key with Mail Send permissions

**Environment Variables**:
```bash
SENDGRID_API_KEY=SG.XXXXXXXXXXXXXXXX
SENDGRID_FROM_EMAIL=alerts@yourdomain.com
SENDGRID_FROM_NAME="ShadowOps Security"
```

**Limits**: 100 emails/day free, paid plans from $19.95/month

### 2.4 SMTP (Fallback)

**Configuration**:
```bash
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=alerts@yourdomain.com
SMTP_PASSWORD=your-smtp-password
SMTP_USE_TLS=true
SMTP_FROM_EMAIL=alerts@yourdomain.com
SMTP_FROM_NAME="ShadowOps Security"
```

**Common Providers**:
| Provider | Host | Port | TLS |
|----------|------|------|-----|
| Gmail | smtp.gmail.com | 587 | Yes |
| Outlook | smtp.office365.com | 587 | Yes |
| AWS SES | email-smtp.region.amazonaws.com | 587 | Yes |
| Mailgun | smtp.mailgun.org | 587 | Yes |
| Postmark | smtp.postmarkapp.com | 587 | Yes |

**Note**: For Gmail, use App Password (not account password). Enable 2FA first.

### 2.5 Testing Email Configuration

```bash
# Test via API
curl -X POST http://localhost:8000/api/v1/notifications/test-email \
  -H "Authorization: Bearer <token>" \
  -d '{"to": "test@example.com"}'
```

Or run the test script:
```bash
cd backend
python -m app.services.email_adapter_test
```

---

## 3. n8n Setup

### 3.1 What is n8n?

n8n is a workflow automation tool that can extend ShadowOps with custom integrations (Slack, Jira, PagerDuty, custom webhooks, etc.).

**Key Point**: n8n integration is **optional and disabled by default**. The core notification system works completely without n8n.

### 3.2 n8n Deployment Options

| Option | Description | Best For |
|--------|-------------|----------|
| **n8n Cloud** | Managed SaaS, starts at €20/month | Quick start, no infrastructure |
| **Self-hosted (Docker)** | Self-managed, full control | Production, data sovereignty |
| **Self-hosted (Kubernetes)** | Scalable, HA | Enterprise |

### 3.3 n8n Cloud Setup (Easiest)

1. Sign up at https://cloud.n8n.io
2. Create workflow(s) for your integrations
3. Get workflow IDs from URLs: `https://app.n8n.io/workflow/{workflowId}`
4. Configure webhook URLs: `https://your-subdomain.app.n8n.io/webhook/{workflowId}`

### 3.4 Self-hosted n8n (Docker)

```yaml
# docker-compose.yml
version: '3.8'
services:
  n8n:
    image: n8nio/n8n:latest
    ports:
      - "5678:5678"
    environment:
      - N8N_BASIC_AUTH_ACTIVE=true
      - N8N_BASIC_AUTH_USER=admin
      - N8N_BASIC_AUTH_PASSWORD=secure-password
      - N8N_HOST=your-n8n-domain.com
      - N8N_PROTOCOL=https
      - WEBHOOK_URL=https://your-n8n-domain.com/
      - GENERIC_TIMEZONE=UTC
    volumes:
      - n8n_data:/home/node/.n8n
    restart: unless-stopped

volumes:
  n8n_data:
```

**Reverse Proxy** (nginx example):
```nginx
server {
    listen 443 ssl;
    server_name n8n.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://localhost:5678;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 3.4 ShadowOps n8n Configuration

**Environment Variables**:
```bash
# Enable n8n integration (disabled by default)
N8N_ENABLED=true

# n8n instance URL
N8N_BASE_URL=https://n8n.yourdomain.com

# API key for direct workflow execution (from n8n settings)
N8N_API_KEY=your-n8n-api-key

# Webhook secret for signature verification
N8N_WEBHOOK_SECRET=your-webhook-secret-min-32-chars

# Comma-separated list of ALLOWED workflow IDs
N8N_ALLOWED_WORKFLOWS=notify_slack,create_jira_ticket,notify_pagerduty
```

**Generating Webhook Secret**:
```bash
openssl rand -hex 32
```

### 3.5 Creating n8n Workflows for ShadowOps

#### Example: Slack Notification Workflow

1. Create new workflow in n8n
2. Add **Webhook** trigger node:
   - Webhook URL: `/webhook/notify_slack`
   - HTTP Method: POST
3. Add **Slack** node:
   - Resource: Message
   - Operation: Post
   - Channel: #security-alerts
   - Text: `{{ $json.payload.message }}`
   - Blocks: (optional rich formatting)
4. Save and activate workflow
5. Copy workflow ID from URL
6. Add to `N8N_ALLOWED_WORKFLOWS`

#### Example: Jira Ticket Creation Workflow

1. Webhook trigger: `/webhook/create_jira_ticket`
2. Jira node: Create Issue
   - Project: SEC
   - Issue Type: Task
   - Summary: `{{ $json.payload.title }}`
   - Description: `{{ $json.payload.message }}\n\nFinding: {{ $json.payload.finding_id }}`
3. Activate and add to allowlist

#### Example: PagerDuty Alert Workflow

1. Webhook trigger: `/webhook/notify_pagerduty`
2. PagerDuty node: Create Incident
   - Service: Security Alerts
   - Summary: `{{ $json.payload.title }}`
   - Severity: `{{ $json.payload.priority }}` (map: critical→critical, high→high, etc.)
   - Details: `{{ $json.payload.message }}`
3. Activate and add to allowlist

### 3.6 Webhook Payload Format

ShadowOps sends this payload to n8n webhooks:

```json
{
  "event": "finding.created",
  "timestamp": "2026-10-14T10:30:00Z",
  "correlation_id": "uuid",
  "payload": {
    "finding_id": "uuid",
    "title": "SQL Injection in login endpoint",
    "severity": "critical",
    "asset_name": "web-server-01",
    "asset_id": "uuid",
    "source": "semgrep"
  }
}
```

**Available payload fields** (varies by event type):
| Field | Type | Description |
|-------|------|-------------|
| finding_id | UUID | Finding identifier |
| title | string | Finding title |
| severity | string | critical/high/medium/low/info |
| asset_name | string | Asset display name |
| asset_id | UUID | Asset identifier |
| source | string | semgrep/recon/dependency/ai_analysis/manual |
| proposal_id | UUID | Remediation proposal ID |
| verification_job_id | UUID | Verification job ID |
| report_id | UUID | Report ID |

### 3.7 n8n Workflow Security Checklist

- [ ] Workflow ID added to `N8N_ALLOWED_WORKFLOWS`
- [ ] Webhook secret configured in n8n (Header: `X-Webhook-Secret`)
- [ ] No sensitive data in workflow (no DB credentials, API keys)
- [ ] Workflow only performs allowed actions (notify, create ticket, etc.)
- [ ] Workflow cannot approve remediation or modify findings
- [ ] Error handling configured (retry, alert on failure)
- [ ] Workflow tested in staging before production

---

## 4. Testing Integration

### 4.1 Test Email Delivery

```bash
# Via API
curl -X POST http://localhost:8000/api/v1/notifications/test-email \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"to": "test@example.com", "subject": "Test", "body": "Test email"}'
```

### 4.2 Test n8n Webhook

```bash
# Send test webhook
curl -X POST https://n8n.yourdomain.com/webhook/notify_slack \
  -H "Content-Type: application/json" \
  -H "X-Webhook-Secret: your-webhook-secret" \
  -d '{
    "event": "finding.created",
    "timestamp": "2026-10-14T10:30:00Z",
    "correlation_id": "test-correlation-id",
    "payload": {
      "finding_id": "test-finding-id",
      "title": "Test Finding",
      "severity": "critical",
      "asset_name": "test-asset"
    }
  }'
```

### 4.3 Verify End-to-End

1. Create a critical finding in ShadowOps
2. Verify notification appears in `/notifications`
3. Check email delivery (if enabled)
4. Check n8n execution log (if configured)
5. Verify audit log entries: `notification.created`, `delivery.attempted`, `n8n.dispatched`

---

## 5. Troubleshooting

### 5.1 Email Not Sending

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Email adapter not configured" | No provider env vars set | Set at least one provider's env vars |
| "SMTP authentication failed" | Wrong credentials | Check SMTP_USERNAME/PASSWORD |
| "Recipient refused" | Invalid email | Validate recipient email format |
| "Rate limited" | Too many sends | Implement rate limiting, use Resend/SendGrid |
| "Timeout" | Slow SMTP server | Increase timeout, check network |

### 5.2 n8n Webhook Not Triggering

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Workflow not allowed" | Workflow ID not in allowlist | Add to `N8N_ALLOWED_WORKFLOWS` |
| "Invalid webhook secret" | Secret mismatch | Check `N8N_WEBHOOK_SECRET` matches n8n |
| "404 Not Found" | Wrong webhook URL | Check workflow webhook path |
| "Timeout" | n8n slow/unavailable | Increase timeout, check n8n health |

### 5.3 n8n Workflow Not Executing

| Symptom | Cause | Solution |
|---------|-------|----------|
| Workflow not activating | Not saved/activated | Save and activate in n8n UI |
| Node errors | Invalid config | Check node configuration |
| Authentication failed | Wrong credentials | Update n8n credentials |
| Rate limited | Too many executions | Add rate limiting in n8n |

---

## 6. Monitoring & Alerting

### 6.1 Key Metrics to Monitor

| Metric | Alert Threshold |
|--------|-----------------|
| Email delivery failure rate | > 5% in 1 hour |
| n8n dispatch failure rate | > 10% in 1 hour |
| Email queue depth | > 1000 pending |
| n8n dispatch latency | > 30 seconds p95 |

### 6.2 Log Queries

```sql
-- Failed email deliveries in last hour
SELECT * FROM notification_deliveries 
WHERE status = 'failed' AND created_at > NOW() - INTERVAL '1 hour';

-- n8n dispatch failures
SELECT * FROM audit_logs 
WHERE action = 'n8n.dispatch_failed' AND created_at > NOW() - INTERVAL '1 hour';

-- Pending notifications
SELECT COUNT(*) FROM notifications 
WHERE read_at IS NULL AND created_at > NOW() - INTERVAL '24 hours';
```

---

## 7. Security Checklist

- [ ] Email provider credentials stored in environment variables (not code)
- [ ] n8n webhook secret is 32+ random characters
- [ ] n8n API key has minimal required permissions
- [ ] `N8N_ALLOWED_WORKFLOWS` contains only necessary workflow IDs
- [ ] n8n instance behind authentication (basic auth or SSO)
- [ ] n8n instance accessible only from ShadowOps network
- [ ] Email sender domain authenticated (SPF/DKIM/DMARC)
- [ ] Email unsubscribe link included (if marketing)
- [ ] Secrets rotated quarterly
- [ ] Audit logs reviewed monthly

---

*Setup Guide Version: 1.0*
*Last Updated: 2026-10-14*
# REPORTING ARCHITECTURE

## 1. Overview

This document describes the architecture of the ShadowOps reporting system (Stage 10), including data flow, component interactions, and design decisions.

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │Dashboard │  │ Reports  │  │New Report│  │Report Detail │   │
│  │  Page    │  │  List    │  │  Wizard  │  │   Page       │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘   │
└───────┼──────────────┼────────────┼─────────────┼─────────────┘
        │              │            │             │
        ▼              ▼            ▼             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │/reports/     │  │/reports/     │  │/reports/dashboard    │  │
│  │dashboard     │  │dashboard/    │  │/reports/...          │  │
│  │/trends       │  │              │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
└─────────┼─────────────────┼─────────────────────┼───────────────┘
          │                 │                     │
          ▼                 ▼                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Service Layer                               │
│  ┌─────────────────┐ ┌─────────────┐ ┌─────────────────────┐  │
│  │DashboardMetrics │ │ TrendService│ │   ReportService     │  │
│  │Service          │ │             │ │                     │  │
│  └────────┬────────┘ └──────┬──────┘ └──────────┬──────────┘  │
└───────────┼─────────────────┼────────────────────┼─────────────┘
            │                 │                    │
            ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Data Layer (PostgreSQL/Supabase)            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │ Assets   │ │ Scans    │ │ Findings │ │ Risk     │ │Report │ │
│  │ Auth     │ │ Findings │ │ Remed.   │ │ Verify   │ │Tables │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │
└─────────────────────────────────────────────────────────────────┘
            │                                        │
            ▼                                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   External Services                             │
│  ┌──────────────────┐    ┌──────────────────────────────────┐  │
│  │ Supabase Storage │    │ AI Providers (Gemini/Grok)       │  │
│  │ (Reports bucket) │    │ (Optional narrative generation)  │  │
│  └──────────────────┘    └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Component Details

### 3.1 DashboardMetricsService

**Purpose**: Aggregate real-time workspace security metrics.

**Data Sources**: 
- `Asset` + `AssetAuthorization` → Asset metrics
- `Scan` → Scan metrics  
- `Finding` → Finding metrics
- `AttackPath` + `RiskSnapshot` → Risk metrics
- `RemediationProposal` + `Approval` + `Application` → Remediation metrics
- `VerificationJob` + `Check` + `Review` → Verification metrics

**Output**: `DashboardMetrics` typed object with all metric categories.

**Performance**: Single queries per metric group, workspace-scoped, ~50-100ms.

### 3.2 TrendService

**Purpose**: Calculate time-series trends from historical snapshots.

**Supported Trends**:
- Finding counts (total, open, by severity, new vs resolved)
- Risk scores (from RiskSnapshot per attack path)
- Scan activity (completed/failed per bucket)
- Remediation progress (proposed/approved/applied)
- Verification outcomes (verified/failed/inconclusive)

**Methodology**:
- Time buckets auto-generated (30 buckets default, min 1 hour)
- Only uses timestamped historical records (no reconstruction)
- Returns `TrendSeries` with data points, source, aggregation method, limitations

**Limitations Explicitly Returned**:
- "Insufficient data points" when < 2 buckets have data
- "No risk snapshots available" when RiskSnapshot table empty
- Severity filter noted in limitations

### 3.3 ReportService

**Purpose**: Orchestrate report generation lifecycle.

**Flow**:
1. Validate request (workspace access, asset ownership)
2. Create `Report` record (PENDING)
3. Compute data cutoff timestamp
4. Generate report sections based on type
5. Create `ReportSection` records
6. Generate exports (PDF + JSON)
7. Store exports via `ReportStorageService`
8. Update `Report` with export metadata (READY)
9. Audit log throughout

**Report Types & Sections**:
- Executive: 10 sections (overview, posture, risks, findings, paths, remediation, verification, unresolved, actions, scope)
- Technical: Detailed findings with evidence, AI analysis, remediation, verification
- Remediation: Proposal lifecycle, validation, application, rollback
- Verification: Jobs, baselines, comparisons, checks, reviews
- Asset Posture: Per-asset scan coverage, findings, risk, authorization

**AI Narrative** (Optional):
- Uses `AIManager` with sanitized context
- Labeled "AI-Assisted — Advisory Only"
- Never overrides deterministic metrics
- Graceful degradation if AI unavailable

### 3.4 ReportExportService

**PDF Generation** (`reportlab`):
- Cover page with metadata table
- Table of contents
- Sections rendered as flowable content
- Methodology & limitations appendix
- Page numbers, professional styling

**JSON Export**:
- Stable schema (`report-v1`)
- Full report metadata + sections
- Completeness + limitations
- Source record references

### 3.5 ReportStorageService

**Primary**: Supabase Storage (`reports` bucket, private)
- Path: `{workspace_id}/{report_id}/report.{pdf|json}`
- Signed URLs (1 hour default expiry)
- Workspace-isolated via RLS

**Fallback**: Local filesystem (`/tmp/reports/{workspace_id}/{report_id}/`)

---

## 4. Data Flow Examples

### 4.1 Dashboard Load
```
GET /reports/dashboard?workspace_id=xxx
  → DashboardMetricsService.get_workspace_metrics()
    → 6 parallel metric queries
    → Returns DashboardMetrics
  → Frontend renders cards + charts
```

### 4.2 Trend Data Load
```
GET /reports/dashboard/trends?workspace_id=xxx&period_start=...&period_end=...
  → TrendService.get_all_trends()
    → 5 parallel trend computations
    → Each uses timestamped historical tables
    → Returns TrendResponse with limitations
  → Frontend renders Recharts visualizations
```

### 4.3 Report Generation
```
POST /reports {report_type, title, format, period, filters...}
  → ReportService.create_report()
    → Validates assets belong to workspace
    → Creates Report (PENDING)
    → Calls _generate_report()
      → DashboardMetricsService for metrics
      → TrendService for trends (if needed)
      → Builds sections per report type
      → Creates ReportSection records
      → ReportExportService.generate_pdf() + JSON
      → ReportStorageService.store_report() × 2
      → Creates ReportExport records
      → Updates Report (READY, export metadata)
    → Returns GenerateReportResponse with report
```

### 4.4 Export Download
```
GET /reports/{id}/download?export_id=xxx
  → ReportService.get_download_url()
    → Verifies workspace access
    → Checks expiration
    → ReportStorageService.get_download_url()
      → Supabase signed URL (1hr) OR file:// local
    → Returns {download_url, expires_in}
  → Frontend opens in new tab
```

---

## 5. Security Boundaries

| Boundary | Enforcement |
|----------|-------------|
| Workspace Isolation | All queries filtered by `workspace_id`; RLS on all tables |
| Authorization | `require_workspace_member` dependency on all endpoints |
| Report Access | Report IDs scoped to workspace; cross-workspace access blocked |
| Export Access | Signed URLs with expiry; workspace verified on download |
| AI Safety | Sanitized context; TRUSTED/UNTRUSTED delimiters; output labeled |
| Secret Redaction | 32+ patterns in export generation |
| Audit Trail | All report lifecycle events logged with actor, workspace, resource |

---

## 6. Error Handling & Resilience

| Scenario | Handling |
|----------|----------|
| AI Provider Unavailable | Graceful degradation; narrative omitted; metrics preserved |
| Supabase Storage Down | Local filesystem fallback; export still works |
| Reportlab Missing | Minimal PDF fallback generated |
| Insufficient Trend Data | Explicit "insufficient data" limitation returned |
| Long Generation | Synchronous (should be async worker in production) |
| Partial Data | Completeness indicators + explicit limitations |

---

## 7. Scalability Considerations

| Concern | Current Approach | Production Recommendation |
|---------|------------------|---------------------------|
| Long-running generation | Synchronous | Background worker (Celery/RQ) with status polling |
| Large report exports | In-memory PDF | Streaming response; chunked upload |
| Concurrent generations | No limit | Queue with concurrency control |
| Historical trend queries | Full table scans | Materialized views / pre-aggregated tables |
| Storage costs | Local fallback | Lifecycle policies on Supabase Storage |

---

## 8. Extensibility

### Adding New Report Types
1. Add to `ReportType` enum (model + schema)
2. Add section builder in `ReportService._generate_report()`
3. Add frontend type card in `/reports/new`
4. Update `REPORT_TYPE_LABELS` in frontend

### Adding New Trend Metrics
1. Add method to `TrendService`
2. Register in `get_all_trends()`
3. Add frontend chart component
4. Document data source & aggregation

### Adding New Export Formats
1. Add to `ReportFormat` enum
2. Implement in `ReportExportService`
3. Add storage handling in `ReportStorageService`
4. Add frontend format selector

---

## 9. Configuration

### Environment Variables
```bash
# Supabase Storage
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# AI (optional for narrative)
GEMINI_API_KEY=xxx
GROK_API_KEY=xxx

# Report settings
REPORT_SCHEMA_VERSION=report-v1
RISK_ENGINE_VERSION=risk-v1
VERIFICATION_POLICY_VERSION=verification-policy-v1
DEFAULT_REPORT_TIMEOUT=300
EXPORT_URL_EXPIRY_SECONDS=3600
```

### Feature Flags
```python
# In ReportService
ENABLE_AI_NARRATIVE = True  # Can be disabled
ENABLE_PDF_GENERATION = True
ENABLE_JSON_EXPORT = True
ENABLE_SUPABASE_STORAGE = True  # False for local-only
```

---

## 10. Monitoring & Observability

### Key Metrics to Track
- Report generation latency (p50, p95, p99)
- Export generation latency
- Generation success/failure rate
- Export download rate
- AI narrative usage rate
- Storage usage (bytes, object count)

### Audit Events to Monitor
- `report.generation_failed` (alert if > 5%)
- `report.exported` without subsequent `report.downloaded` (orphaned exports)
- Storage quota approaching limits

---

*Architecture Version: 1.0*
*Last Updated: 2026-10-13*
# STAGE 10 BASELINE — Existing Architecture Audit (Stages 0–9)

## 1. Overview

This document audits the current ShadowOps codebase (Stages 0–9) to identify reusable services, verify existing functionality, and catalog gaps before implementing Stage 10: Security Reports & Executive Dashboard.

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

---

## 3. Reusable Services & Infrastructure for Reporting

### 3.1 Data Models (from `app/models/__init__.py`)
- **Workspace/Profile/Member**: 3 models with workspace isolation
- **Asset/Authorization**: 2 models for asset inventory
- **Scan/ScanEvent/ScanTarget**: 3 models for scan execution
- **Finding/FindingEvidence**: 2 models for vulnerability findings
- **FindingRelationship/AttackPath/AttackPathNode/AttackPathEdge/RiskSnapshot**: 5 models for attack paths
- **AiRun/FindingAiAnalysis**: 2 models for AI analysis
- **SecurityTeamRun/AgentRun/TeamAssessment/TeamReview**: 4 models for security team
- **RemediationProposal/PatchVersion/ValidationRun/RemediationApproval/RemediationApplication/RemediationRollback/RemediationVerificationHandoff**: 7 models for remediation
- **VerificationJob/VerificationBaseline/VerificationCheck/EvidenceComparison/VerificationPolicy/VerificationReview**: 6 models for verification

### 3.2 Repository Layer (`app/repositories/__init__.py`)
All entities have repositories with CRUD + query methods, workspace-scoped queries

### 3.3 Service Layer (`app/services/`)
- **Scanning**: `ScanService`, `SemgrepRunner`
- **AI**: `AIManager`, 5 agent services, `SecurityTeamOrchestrator`
- **Attack Paths**: `CorrelationEngine`, `AttackPathService`, `RiskEngine`
- **Remediation**: `RemediationService`, `PatchProcessor`, `ValidationPipeline`, `ApprovalService`, `PatchApplicationAdapter`, `RollbackService`
- **Verification**: `BaselineCaptureService`, `EvidenceComparisonService`, `RegressionAnalysisService`, `VerificationPolicyEngine`, `VerificationService`

### 3.4 API Layer (`app/api/v1/`)
- **Endpoints**: Workspaces, Assets, Scans, Findings, AI, Attack Paths, Security Team, Remediations, Verifications
- **Auth**: `get_current_user`, `require_workspace_member` dependency injection
- **Pagination/Filtering**: Standard patterns with query params

### 3.5 Frontend (`frontend/app/`)
- **Pages**: Dashboard, Assets, Scans, Findings, Attack Paths, Security Team, Remediations, Verifications
- **API Client** (`lib/api.ts`): Typed methods for all endpoints
- **UI Components**: Card, Badge, Skeleton, EmptyState, Button, StatusBadge
- **State Management**: React Query (TanStack Query) for server state

### 3.6 Existing Report Infrastructure (Partial)
- **Report Model** (in `lib/api.ts`): `Report` interface with types: executive, technical, scan, compliance, custom
- **GenerateReportRequest**: report_type, title, scan_id, period_start, period_end, format
- **API Methods**: `listReports`, `generateReport` in api.ts
- **No backend models, services, or API endpoints for reports yet** (only frontend types and placeholder API calls)

---

## 4. Available Data for Reporting

### 4.1 Workspace-Level Metrics (Fully Available)
| Metric | Source | Status |
|--------|--------|--------|
| Total assets | `Asset` table | ✅ |
| Assets with current authorization | `AssetAuthorization` (status=VERIFIED, not expired) | ✅ |
| Assets by criticality/type/status | `Asset` fields | ✅ |
| Total workspace members | `WorkspaceMember` | ✅ |

### 4.2 Scan Metrics (Fully Available)
| Metric | Source | Status |
|--------|--------|--------|
| Scans completed/failed/running | `Scan` (status field) | ✅ |
| Scans by type/profile | `Scan` fields | ✅ |
| Latest completed scan timestamp | `Scan.completed_at` | ✅ |
| Scan duration, phases | `Scan.duration_ms`, `phases_completed` | ✅ |
| Scan authorization confirmation | `Scan.authorization_confirmed_at` | ✅ |

### 4.3 Finding Metrics (Fully Available)
| Metric | Source | Status |
|--------|--------|--------|
| Open findings by severity | `Finding.severity` + `status=OPEN` | ✅ |
| Findings by lifecycle status | `Finding.status` | ✅ |
| Findings by source (semgrep, ai, manual) | `Finding.source` | ✅ |
| First/last observed timestamps | `Finding.first_seen_at`, `last_seen_at` | ✅ |
| Fixed findings | `Finding.status=FIXED`, `fixed_at` | ✅ |
| Risk scores | `Finding.risk_score` | ✅ |

### 4.4 Attack Path & Risk Metrics (Fully Available)
| Metric | Source | Status |
|--------|--------|--------|
| Attack paths by status | `AttackPath.status` | ✅ |
| Attack paths by severity/risk_band | `AttackPath.severity`, `risk_band` | ✅ |
| Current risk score per path | `AttackPath.risk_score` | ✅ |
| Risk snapshots history | `RiskSnapshot` table | ✅ |
| Risk factors per snapshot | `RiskSnapshot.factors` (JSONB) | ✅ |
| Risk model version | `AttackPath.risk_model_version` | ✅ |

### 4.5 AI Analysis Metrics (Available, Needs API Keys)
| Metric | Source | Status |
|--------|--------|--------|
| AI finding analyses | `FindingAiAnalysis` | ⚠️ Needs keys |
| AI scan analyses | `AiRun` (operation=scan_analysis) | ⚠️ Needs keys |
| Security team runs | `SecurityTeamRun` | ⚠️ Needs keys |
| Team assessments | `TeamAssessment` | ⚠️ Needs keys |

### 4.6 Remediation Metrics (Fully Available)
| Metric | Source | Status |
|--------|--------|--------|
| Proposals by status | `RemediationProposal.status` | ✅ |
| Proposals by fix_type | `RemediationProposal.fix_type` | ✅ |
| Approved/applied/rejected counts | `RemediationApproval`, `RemediationApplication` | ✅ |
| Validation results | `ValidationRun` | ✅ |
| Rollback history | `RemediationRollback` | ✅ |

### 4.7 Verification Metrics (Fully Available - Stage 9)
| Metric | Source | Status |
|--------|--------|--------|
| Verification jobs by status | `VerificationJob.status` | ✅ |
| Verification outcomes | `VerificationJob.overall_outcome` | ✅ |
| Check results by type | `VerificationCheck.check_type`, `status` | ✅ |
| Evidence comparisons | `EvidenceComparison.category` | ✅ |
| Human reviews | `VerificationReview.decision` | ✅ |
| Regression check failures | `VerificationCheck` (check_type=REGRESSION_ANALYSIS, TEST_EXECUTION) | ✅ |

---

## 5. Historical Data Availability for Trends

### 5.1 Reliable Historical Records (Time-Series Capable)
| Data Point | Table | Timestamp Field | Granularity |
|------------|-------|-----------------|-------------|
| Scan completion | `Scan` | `completed_at` | Per scan |
| Finding first/last seen | `Finding` | `first_seen_at`, `last_seen_at` | Per finding |
| Finding status changes | `Finding` | `updated_at` (limited) | Per update |
| Risk snapshots | `RiskSnapshot` | `calculated_at` | Per calculation |
| Remediation proposal creation | `RemediationProposal` | `created_at` | Per proposal |
| Remediation approval | `RemediationApproval` | `approved_at` | Per approval |
| Remediation application | `RemediationApplication` | `applied_at` | Per application |
| Verification job completion | `VerificationJob` | `completed_at` | Per verification |
| Verification review | `VerificationReview` | `reviewed_at` | Per review |

### 5.2 Missing Historical Data (Cannot Reliably Trend)
| Metric | Reason |
|--------|--------|
| Finding severity over time | No finding history table, only current state |
| Risk score per asset over time | Only per attack path, not per asset aggregate |
| Open findings count over time | Requires reconstructing from first_seen/last_seen/status |
| Verification outcomes over time | Only available since Stage 9 implementation |

---

## 6. Frontend Components Available

### 6.1 UI Components (`frontend/components/ui/`)
- `Card`, `CardContent`, `CardHeader`, `CardTitle`
- `Badge`, `StatusBadge` (with severity/status variants)
- `Skeleton`, `CardSkeleton`
- `EmptyState`
- `Button` (variants: default, secondary, outline, success, error, info)
- Charts: **None currently** (need to add chart library)

### 6.2 Existing Patterns
- React Query for data fetching with `staleTime`, `enabled`
- Loading states with `Skeleton` components
- Empty states with `EmptyState` component
- Role-based UI (owner/admin/member/viewer)
- Date formatting with `date-fns` (`formatDistanceToNow`, `format`)

---

## 7. PDF/Export Libraries

### 7.1 Current Status
- **No PDF library installed** in frontend or backend
- **No JSON export utilities** beyond standard `JSON.stringify`

### 7.2 Recommended Libraries
- **Frontend PDF**: `@react-pdf/renderer` (React-native, no browser dependencies) or `jspdf` + `html2canvas`
- **Backend PDF**: `reportlab` (Python) or `weasyprint` (HTML to PDF)
- **JSON**: Native `json` module (Python), `JSON.stringify` (TypeScript)

---

## 8. Storage Integration

### 8.1 Supabase Storage
- **Configured**: Supabase client exists in `app/db/`
- **Verified**: Storage bucket creation not confirmed in migrations
- **RLS**: Storage policies would need to be added

---

## 9. Gaps & Missing for Stage 10

### 9.1 Backend Models (MISSING)
- [ ] `Report` model with metadata, filters, status, versioning
- [ ] `ReportSection` or snapshot tables for reproducibility
- [ ] Migration `0008_stage10_reports.sql`

### 9.2 Backend Services (MISSING)
- [ ] `ReportService` - report generation orchestration
- [ ] `DashboardMetricsService` - aggregated workspace metrics
- [ ] `TrendService` - time-series calculations from historical data
- [ ] `ReportExportService` - PDF/JSON generation
- [ ] `ReportStorageService` - Supabase Storage integration

### 9.3 API Endpoints (MISSING)
- [ ] `GET /reports/dashboard` - workspace dashboard metrics
- [ ] `GET /reports/dashboard/trends` - time-series data
- [ ] `POST /reports` - create/generate report
- [ ] `GET /reports` - list reports
- [ ] `GET /reports/{id}` - get report detail
- [ ] `POST /reports/{id}/export` - generate export
- [ ] `GET /reports/{id}/download` - download file

### 9.4 Frontend Pages (MISSING)
- [ ] `/dashboard` - enhanced executive dashboard
- [ ] `/reports` - report list/history
- [ ] `/reports/new` - report creation wizard
- [ ] `/reports/[id]` - report detail/preview/export
- [ ] Chart components for trends

### 9.5 Documentation (MISSING)
- [ ] `docs/STAGE_10_REPORT.md`
- [ ] `docs/REPORTING_ARCHITECTURE.md`
- [ ] `docs/REPORT_SCHEMA.md`
- [ ] `docs/SECURITY_METRICS_METHODOLOGY.md`
- [ ] `docs/REPORT_EXPORT_SECURITY.md`

---

## 10. Security Boundaries to Preserve

| Boundary | Current Enforcement | Stage 10 Must Maintain |
|----------|---------------------|------------------------|
| Workspace Isolation | RLS + query filtering | All report tables, storage paths |
| Authorization | `require_workspace_member` | All report endpoints |
| No Data Fabrication | Deterministic engines only | Reports must reflect actual persisted data |
| Audit Trail | All mutations logged | Report generation, export, download |
| Secret Redaction | 32+ patterns in AI | Report exports must redact secrets |
| No Public Access | Private by default | Report downloads must be authorized |
| AI Safety | TRUSTED/UNTRUSTED delimiters | AI narrative must not override metrics |

---

## 11. Implementation Priority for Stage 10

1. **Database Migration & Models** — Report, ReportSection, ReportExport tables
2. **Dashboard Metrics Service** — Aggregated workspace queries
3. **Dashboard API & Frontend** — Enhanced dashboard with real metrics
4. **Trend Service** — Time-series from historical records
5. **Report Generation Service** — Orchestration with snapshots
6. **Report API Endpoints** — CRUD + generation
7. **PDF Export Service** — Backend PDF generation
8. **JSON Export** — Structured schema with versioning
9. **Storage Integration** — Supabase Storage for report files
10. **Frontend Report Pages** — Creation, list, detail, export
11. **AI Narrative (Optional)** — Advisory summary using existing AI
12. **Tests** — Unit + integration for all new components
13. **Documentation** — Architecture, schema, methodology, security

---

## 12. Critical Decisions for Stage 10

| Decision | Recommendation |
|----------|----------------|
| Report snapshot vs references | Store snapshot for immutability; reference live data for drill-down |
| PDF generation location | Backend (server-side) for security, consistency, library options |
| Chart library | Recharts (React, accessible, lightweight) or Chart.js |
| Trend calculation | Only from reliable history tables; explicit "insufficient data" state |
| AI narrative | Optional, advisory-only, labeled, fallback to deterministic text |
| Report storage | Supabase Storage with signed URLs; fallback to direct download |
| Report versioning | Schema version in every report; immutable once generated |

---

*Generated: 2026-10-13*
*Baseline for Stage 10 Implementation*
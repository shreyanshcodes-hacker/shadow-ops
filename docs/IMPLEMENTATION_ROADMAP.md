# IMPLEMENTATION ROADMAP

## Stage Overview

| Stage | Name | Duration | Dependencies |
|-------|------|----------|--------------|
| 0 | Architecture & Ingestion | 1 week | — |
| 1 | Foundation | 1 week | 0 |
| 2 | UI/UX Foundation | 2 weeks | 1 |
| 3 | Authentication | 1 week | 1 |
| 4 | Workspace Management | 1 week | 3 |
| 5 | Assets & Authorization | 2 weeks | 4 |
| 6 | Scan Engine Core | 2 weeks | 5 |
| 7 | Semgrep Integration | 2 weeks | 6 |
| 8 | AI Manager Core | 2 weeks | 6 |
| 9 | Security Agents | 3 weeks | 8 |
| 10 | Findings Management | 2 weeks | 7, 9 |
| 11 | Risk Engine | 1 week | 10 |
| 12 | Attack Path Engine | 2 weeks | 10, 11 |
| 13 | Remediation System | 2 weeks | 10, 11 |
| 14 | Verification System | 2 weeks | 13 |
| 15 | Reporting | 2 weeks | 10, 11, 12 |
| 16 | AI Security Chat | 2 weeks | 10, 15 |
| 17 | Automation (n8n) | 2 weeks | 6, 13 |
| 18 | Integrations | 2 weeks | 5, 6 |
| 19 | Security Hardening | 1 week | All |
| 20 | Testing & QA | 2 weeks | All |
| 21 | Railway Deployment | 1 week | 19 |
| 22 | Documentation | 1 week | All |
| 23 | AI Usage Report | 1 week | 8, 9 |
| 24 | Final QA & Hackathon Demo | 1 week | All |

**Total Estimated: ~38 weeks (~9.5 months)**

---

## Stage 0: Architecture & Ingestion ✅ COMPLETE

**Objective**: Complete product understanding, architecture design, and implementation planning

**Deliverables** (All Created):
- `docs/PROJECT_SOURCE_OF_TRUTH.md`
- `docs/PRODUCT_ARCHITECTURE.md`
- `docs/SYSTEM_ARCHITECTURE.md`
- `docs/DATABASE_ARCHITECTURE.md`
- `docs/AI_ARCHITECTURE.md`
- `docs/AGENT_ARCHITECTURE.md`
- `docs/SECURITY_ARCHITECTURE.md`
- `docs/SCAN_ARCHITECTURE.md`
- `docs/RISK_ARCHITECTURE.md`
- `docs/REMEDIATION_ARCHITECTURE.md`
- `docs/VERIFICATION_ARCHITECTURE.md`
- `docs/RAILWAY_DEPLOYMENT_ARCHITECTURE.md`
- `docs/IMPLEMENTATION_ROADMAP.md`
- `docs/STAGE_0_ACCEPTANCE.md`
- `docs/STAGE_0_REPORT.md`

**Acceptance**: All documents reviewed and approved. No coding started.

---

## Stage 1: Foundation

**Objective**: Project scaffolding, development environment, CI/CD pipeline

**Dependencies**: Stage 0

### Database Changes
- Enable PostgreSQL extensions: `uuid-ossp`, `pgcrypto`, `pgvector` (for future)
- Create `profiles`, `workspaces`, `workspace_members`, `roles` tables
- RLS policies for workspace isolation
- Triggers for `updated_at`

### Backend Changes
- FastAPI project structure
- SQLAlchemy 2.0 + Alembic setup
- Pydantic v2 models
- Firebase Admin SDK integration
- Supabase client setup
- Redis client setup
- Structured logging (structlog)
- Health check endpoint
- CORS middleware
- Request ID middleware
- Error handling middleware

### Frontend Changes
- Next.js 14 App Router setup
- TypeScript strict config
- Tailwind CSS + ShadowOps design system
- ESLint + Prettier + Husky
- Firebase Auth client SDK
- React Query setup
- Component library (Radix UI primitives)
- Layout: Sidebar, Header, Theme provider

### AI Changes
- Model router abstraction (Gemini/Grok)
- Structured output validation framework
- Cost tracking infrastructure

### Security
- All middleware tests
- RLS policy tests
- Secret scanning in CI

### Testing
- Unit tests for utilities
- Integration test harness
- CI pipeline: lint, typecheck, test, build

### Acceptance Criteria
- [ ] `npm run dev` / `uvicorn` starts successfully
- [ ] Health checks pass
- [ ] CI passes on main branch
- [ ] Docker builds work locally
- [ ] Database migrations run cleanly

---

## Stage 2: UI/UX Foundation

**Objective**: Implement ShadowOps visual identity and core navigation

**Dependencies**: Stage 1

### Database Changes
- None

### Backend Changes
- Theme/preferences API (per user/workspace)

### Frontend Changes
- **Design System**:
  - Colors: Black/Charcoal base, Crimson accent, White/Cool-gray text
  - Typography: Inter (UI), JetBrains Mono (code)
  - Glassmorphism cards, thin borders, subtle red glow
  - Dark mode only (no light mode)
- **Layout**:
  - Collapsible sidebar navigation
  - Top bar: Workspace switcher, User menu, Notifications
  - Responsive (desktop ≥1024px, tablet, mobile)
- **Pages** (Skeleton):
  - Dashboard (empty state)
  - Scans list
  - Findings table
  - Attack Paths (placeholder)
  - Agents (placeholder)
  - Remediation (placeholder)
  - Reports (placeholder)
  - AI Security Chat (placeholder)
  - Assets list
  - Team management
  - Settings
- **Components**:
  - Data Table (sortable, filterable, paginated)
  - Stat Cards
  - Severity Badges
  - Progress Indicators
  - Modal/Dialog system
  - Toast notifications
  - Loading skeletons

### Acceptance Criteria
- [ ] All 10 navigation pages render
- [ ] Design system documented in Storybook
- [ ] Responsive breakpoints work
- [ ] Theme consistent across pages
- [ ] Accessibility: WCAG AA (contrast, keyboard nav)

---

## Stage 3: Authentication

**Objective**: Firebase Auth integration with workspace onboarding

**Dependencies**: Stage 1

### Database Changes
- `profiles` table sync from Firebase
- `workspaces` with owner
- `workspace_members` with roles
- Firebase Auth webhook handler (user.create, user.delete)

### Backend Changes
- Firebase token verification dependency
- `get_current_user` dependency
- Workspace membership middleware
- Role-based access control dependencies
- Auth API routes:
  - `POST /auth/verify` - Verify token, return session
  - `GET /auth/me` - Current user profile
  - `POST /workspaces` - Create workspace (onboarding)
  - `GET /workspaces` - List user workspaces

### Frontend Changes
- Auth pages: Login, Register, Forgot Password, Email Verification
- Onboarding flow: Create workspace → Invite team
- Protected routes (redirect to login)
- Auth state management (React Context)
- Token refresh handling

### Security
- Rate limiting on auth endpoints
- Secure cookie storage option
- Audit logs for auth events

### Acceptance Criteria
- [ ] User can register, verify email, login
- [ ] User can create workspace
- [ ] User can invite members (email)
- [ ] Role enforcement works (Owner/Admin/Member/Viewer)
- [ ] Token refresh seamless
- [ ] Logout clears session

---

## Stage 4: Workspace Management

**Objective**: Full workspace CRUD, member management, settings

**Dependencies**: Stage 3

### Database Changes
- Workspace settings JSONB (notifications, retention, scan config)
- Workspace invitations table (token, expires, role)

### Backend Changes
- Workspace CRUD API
- Member management API (invite, update role, remove, resend)
- Invitation acceptance flow
- Workspace settings API
- Plan enforcement (Free/Pro/Enterprise limits)
- Audit logging for all workspace actions

### Frontend Changes
- Workspace switcher (top bar)
- Workspace settings page:
  - General (name, slug, avatar)
  - Members (table with role actions)
  - Invitations (pending, resend, revoke)
  - Plan & Billing (placeholder)
  - Integrations (placeholder)
  - Security (session management, audit log access)
  - Retention policies
- Delete workspace flow (confirmation, owner only)

### Acceptance Criteria
- [ ] Create/read/update/delete workspaces
- [ ] Invite/remove members, change roles
- [ ] Invitation email sent (via n8n/Firebase)
- [ ] Settings persist
- [ ] Owner cannot be removed
- [ ] Audit log captures all changes

---

## Stage 5: Assets & Authorization

**Objective**: Asset registry with authorization enforcement

**Dependencies**: Stage 4

### Database Changes
- `assets` table (all types: repository, api, infrastructure, application, container)
- `asset_authorizations` table (enforces NO AUTH → NO SCAN)
- Asset tags, criticality, scan_frequency
- Supabase Vault integration for credentials

### Backend Changes
- Asset CRUD API
- Asset type-specific validation
- Credential reference resolution (Vault)
- Authorization API:
  - `POST /assets/{id}/authorization` - Submit authorization
  - `GET /assets/{id}/authorization` - View status
  - `PATCH /assets/{id}/authorization` - Admin verify/reject
- Authorization validation service (used by Scan Engine)
- Asset connectivity validation (pre-scan)
- Scheduled scan configuration

### Frontend Changes
- Assets page: List, filter by type/status, search
- Add Asset Wizard (multi-step by type):
  - Repository: Git URL, branch, credentials ref
  - API: Base URL, auth type, spec file
  - Infrastructure: Cloud provider, account, region
  - Application: URL, tech stack
  - Container: Registry, image, tag
- Authorization tab per asset:
  - Upload evidence (screenshots, docs)
  - Record authorization type
  - Set expiration
  - Status badge (Pending/Verified/Rejected/Expired)
- Admin authorization review queue

### Security
- Credentials NEVER in frontend
- Vault access only via backend
- Authorization check enforced in Scan Service

### Acceptance Criteria
- [ ] Add all 5 asset types
- [ ] Submit authorization with evidence
- [ ] Admin can verify/reject
- [ ] Expired authorizations block scans
- [ ] Credentials stored in Vault, not DB
- [ ] Connectivity test works

---

## Stage 6: Scan Engine Core

**Objective**: Scan orchestration, state machine, event streaming

**Dependencies**: Stage 5

### Database Changes
- `scans` table
- `scan_events` table (immutable, realtime)
- `agent_runs` table
- Scan config JSONB

### Backend Changes
- Celery app configuration
- Scan Orchestrator (DAG execution)
- Scan state machine (QUEUED→RUNNING→COMPLETED/FAILED/PARTIAL/CANCELLED)
- Phase definitions and dependencies
- Real-time event emission (Redis pub/sub → SSE)
- Scan API:
  - `POST /scans` - Start scan (auth check!)
  - `GET /scans` - List with filters
  - `GET /scans/{id}` - Detail
  - `GET /scans/{id}/events` - SSE stream
  - `POST /scans/{id}/cancel` - Cancel
- Progress calculation
- Cancellation handling (graceful + force)
- Cost tracking per scan
- Scan summary aggregation

### Frontend Changes
- Scan list page (table with status, progress, actions)
- Scan detail page:
  - Real-time progress bar (phase-by-phase)
  - Event log (live updates via SSE)
  - Phase status cards
  - Cancel button
- Start Scan modal (asset selection, scan type, config)

### Testing
- Unit tests for orchestrator
- Integration test: full scan flow (mocked phases)
- Cancellation test
- Concurrent scan limits

### Acceptance Criteria
- [ ] Start scan → queued → running → completed
- [ ] Real-time progress updates in UI
- [ ] Phases execute in correct order
- [ ] Cancellation works mid-scan
- [ ] Failed phase → PARTIAL/FAILED state
- [ ] Scan events persisted and queryable
- [ ] Cost tracked per scan

---

## Stage 7: Semgrep Integration

**Objective**: Code and dependency analysis via Semgrep

**Dependencies**: Stage 6

### Database Changes
- Findings from Semgrep stored in `findings` table
- Evidence in `finding_evidence` (code snippets, Semgrep raw output)

### Backend Changes
- `SemgrepRunner` service:
  - Language detection
  - Ruleset selection (security-audit, secrets, OWASP, custom)
  - Repository cloning (shallow, sparse checkout)
  - Semgrep execution with timeout
  - JSON output parsing
  - Finding normalization (dedup, enrich)
- SCA Runner:
  - Lockfile detection
  - Dependency parsing
  - OSV/GHSA vulnerability lookup
  - Reachability analysis (call graphs)
- Code Analysis Phase integration
- Dependency Analysis Phase integration
- Finding Normalization Phase

### Frontend Changes
- Findings table (from Semgrep)
- Finding detail: code snippet, location, rule info
- Semgrep rule reference links

### Testing
- Semgrep ruleset validation
- Finding normalization accuracy
- Performance: large repo scan < 30 min
- False positive rate measurement

### Acceptance Criteria
- [ ] Semgrep SAST scan runs in Code Analysis phase
- [ ] Semgrep SCA scan runs in Dependency Analysis phase
- [ ] Findings normalized and stored
- [ ] Evidence linked (code snippets, raw output)
- [ ] Deduplication works across runs
- [ ] Custom rulesets supported

---

## Stage 8: AI Manager Core

**Objective**: AI orchestration framework, model routing, validation

**Dependencies**: Stage 6

### Database Changes
- `agent_runs` table (enhanced with AI metadata)
- AI usage tracking

### Backend Changes
- `BaseAgent` abstract class
- `AgentRegistry` and `AgentContext`
- Model Router (Gemini Pro/Flash, Grok)
- Structured Output Validator (Pydantic schemas)
- Hallucination Detector (basic)
- Cost Governor (per-scan, per-agent, daily)
- Retry Logic with exponential backoff
- AI Manager Coordinator (plans, delegates, synthesizes)
- Agent execution sandbox (timeouts, resource limits)

### Frontend Changes
- Agent status in Scan detail (which agents ran, cost, tokens)

### Testing
- Schema validation for each agent output
- Model routing logic tests
- Cost tracking accuracy
- Hallucination detection test cases

### Acceptance Criteria
- [ ] Agent framework executes agents in order
- [ ] Model selection works per agent config
- [ ] Output validation catches schema errors
- [ ] Retries on transient failures
- [ ] Cost tracked and enforced
- [ ] Agent runs visible in scan detail

---

## Stage 9: Security Agents

**Objective**: Implement all 8 specialized security agents

**Dependencies**: Stage 8

### Agents to Implement

| Agent | Model | Key Output |
|-------|-------|------------|
| Recon | Flash + Tools | Endpoints, subdomains, tech stack |
| Code Security | Pro | Enriched findings, FP flags, exploitability |
| Dependency | Flash + Grok | Reachable vulns, upgrade paths |
| Threat Analyst | Grok + Pro | Attack scenarios, MITRE mappings |
| Risk Analyst | Flash | Risk assessments with explanations |
| Remediation | Pro | Code diffs, config patches, test plans |
| Verification | Flash | Test designs, verification criteria |
| Reporting | Pro + Flash | Structured report sections |

### For Each Agent
- Input/Output Pydantic schemas
- System prompts (version controlled)
- Few-shot examples
- Execution logic
- Evidence persistence
- Cost tracking

### Testing
- Golden set evaluation (50+ cases per agent)
- Regression tests on prompt changes
- Cost per agent benchmark

### Acceptance Criteria
- [ ] All 8 agents execute in scan pipeline
- [ ] Outputs pass schema validation
- [ ] Evidence stored for each agent
- [ ] Costs within budgets
- [ ] Agent outputs used by downstream phases

---

## Stage 10: Findings Management

**Objective**: Complete finding lifecycle, triage, evidence, search

**Dependencies**: Stage 7, Stage 9

### Database Changes
- `findings` table (all fields)
- `finding_evidence` table
- Finding tags, status workflow

### Backend Changes
- Findings API:
  - List with filters (severity, status, source, asset, date range)
  - Get detail with evidence
  - Bulk status update
  - Triage workflow (open → triaged → in_progress → fixed/false_positive)
  - Assign to user
  - Add comments
- Evidence API:
  - List/download evidence for finding
  - Evidence viewer (code, images, logs)
- Search API (full-text on findings)
- Export findings (CSV, JSON)

### Frontend Changes
- Findings page:
  - Advanced filters (saved filters)
  - Bulk actions
  - Keyboard navigation
- Finding Detail Drawer/Page:
  - Evidence carousel
  - Risk score breakdown
  - Attack path links
  - Remediation proposals
  - Verification history
  - Comments/activity
- Triage workflow UI

### Acceptance Criteria
- [ ] Findings list loads < 2s (10k findings)
- [ ] Filters work correctly
- [ ] Evidence viewer renders all types
- [ ] Triage workflow enforced
- [ ] Bulk operations work
- [ ] Search returns relevant results

---

## Stage 11: Risk Engine

**Objective**: Deterministic, explainable risk scoring

**Dependencies**: Stage 10

### Database Changes
- `risk_assessments` table (one per finding)
- Workspace risk model config

### Backend Changes
- Risk Engine Service:
  - Factor calculation (6 factors)
  - Weighted formula (configurable)
  - Explanation generation
  - Formula versioning
- Risk API:
  - `GET /findings/{id}/risk` - Assessment detail
  - `POST /workspaces/{id}/risk-model` - Update weights (Admin)
- Background job: Recalculate on finding/asset changes

### Frontend Changes
- Risk Score badge on findings (color-coded)
- Risk breakdown modal (factor contributions)
- Workspace risk model config (Enterprise)

### Testing
- Golden cases (10 scenarios with expected scores)
- Weight change impact tests
- Explanation quality review

### Acceptance Criteria
- [ ] Risk scores calculated for all findings
- [ ] Scores deterministic (same input = same output)
- [ ] Explanations generated and accurate
- [ ] Weights configurable per workspace
- [ ] Recalculation triggered correctly

---

## Stage 12: Attack Path Engine

**Objective**: Graph-based attack path construction and visualization

**Dependencies**: Stage 10, Stage 11

### Database Changes
- `attack_paths` table
- `attack_path_nodes` table
- `attack_path_edges` table

### Backend Changes
- Graph Builder:
  - Node types: asset, vulnerability, network_zone, trust_boundary, data_store, attacker
  - Edge types: exploits, accesses, trusts, contains, lateral_movement, privilege_escalation
  - Risk propagation algorithm
  - Path scoring
- Attack Path API:
  - List paths for workspace
  - Get path graph (nodes + edges)
  - Path detail with evidence
- Integration with Risk Engine (attack_path_impact factor)

### Frontend Changes
- Attack Paths page: List with risk scores
- Graph Visualization (Cytoscape.js / React Flow):
  - Nodes colored by type/risk
  - Edges labeled with type
  - Click node → finding/asset detail
  - Path highlight on hover
  - Export as image
- Mini-graph on Finding Detail

### Acceptance Criteria
- [ ] Attack paths generated from findings + recon
- [ ] Graph renders performantly (100+ nodes)
- [ ] Risk propagation logical
- [ ] Evidence links work
- [ ] Paths update on new findings

---

## Stage 13: Remediation System

**Objective**: AI proposals, human approval, authorized execution

**Dependencies**: Stage 10, Stage 11

### Database Changes
- `remediation_proposals` table
- `remediation_approvals` table
- `remediation_tracking` table

### Backend Changes
- Remediation Agent (Stage 9) integration
- Remediation API:
  - `POST /findings/{id}/remediation` - Generate proposal
  - `GET /remediations` - List proposals
  - `POST /remediations/{id}/approve` - Approve (with conditions)
  - `POST /remediations/{id}/reject` - Reject (with justification)
  - `POST /remediations/{id}/apply` - Trigger execution
- Execution Adapters:
  - Git PR Creator (GitHub/GitLab/Bitbucket)
  - n8n Workflow Trigger (config/infra)
  - Dependency Update PR
- Approval workflow enforcement

### Frontend Changes
- Remediation page: Proposals table
- Proposal Detail:
  - Diff viewer (code/config)
  - Test plan
  - Risk assessment
  - Approve/Reject/Request Changes buttons
- Approval modal with conditions
- Execution status tracking (PR link, n8n status)

### Acceptance Criteria
- [ ] AI generates proposals for prioritized findings
- [ ] Human approval required before execution
- [ ] Git PR created for code changes
- [ ] n8n workflow triggered for config/infra
- [ ] Approval audit trail complete
- [ ] Rejection requires justification

---

## Stage 14: Verification System

**Objective**: Empirical fix verification

**Dependencies**: Stage 13

### Database Changes
- `verification_runs` table

### Backend Changes
- Verification Orchestrator
- Checkers:
  - Reproduction Test
  - Semgrep Rescan
  - Dependency Check
  - Config Audit
  - Regression Check
- Verification API:
  - `POST /findings/{id}/verify` - Trigger
  - `GET /verifications/{id}` - Result
- Auto-trigger on PR merge / n8n completion
- Finding status update on pass (→ FIXED)
- Regression detection on re-verify

### Frontend Changes
- Verification tab on Finding Detail
- Verification run history
- Check results with evidence
- Retry failed checks button

### Acceptance Criteria
- [ ] Verification runs automatically post-remediation
- [ ] All 5 check types implemented
- [ ] Evidence captured for each check
- [ ] Finding status updates to FIXED on pass
- [ ] Regression alerts work

---

## Stage 15: Reporting

**Objective**: Executive, Technical, and Scan reports

**Dependencies**: Stage 10, Stage 11, Stage 12

### Database Changes
- `reports` table
- Report templates (JSONB)

### Backend Changes
- Reporting Agent (Stage 9) integration
- Report Generator Service:
  - Executive Report (summary, trends, score)
  - Technical Report (findings, evidence, attack paths)
  - Scan Report (single scan detail)
  - Compliance Report (framework mapping)
- Report API:
  - `POST /reports` - Generate
  - `GET /reports` - List
  - `GET /reports/{id}` - Detail
  - `GET /reports/{id}/download` - PDF/HTML
- PDF Generation (WeasyPrint/Playwright)
- Scheduled reports (via Celery Beat)

### Frontend Changes
- Reports page: List with type, period, status
- Report Viewer (HTML)
- Download buttons (PDF, HTML, JSON)
- Report scheduling UI

### Acceptance Criteria
- [ ] All 3 report types generate
- [ ] Reports accurate to stored data
- [ ] PDF renders correctly
- [ ] Scheduled reports work
- [ ] Download works

---

## Stage 16: AI Security Chat

**Objective**: Contextual AI chat with workspace-scoped knowledge

**Dependencies**: Stage 10, Stage 15

### Database Changes
- `chat_conversations` table
- `chat_messages` table
- pgvector index for embeddings (future)

### Backend Changes
- Chat Service:
  - Intent Classifier
  - Context Retriever (SQL + Vector)
  - Response Generator (with citations)
  - Citation Validator
- Chat API:
  - `POST /chat/conversations` - New
  - `GET /chat/conversations` - List
  - `POST /conversations/{id}/messages` - Send
  - `GET /conversations/{id}/messages` - History
- Workspace-scoped data access only
- Refusal for out-of-scope queries

### Frontend Changes
- AI Security Chat page (full-screen or sidebar)
- Conversation list
- Message streaming (SSE)
- Citation links (click → finding/evidence)
- Context chips (finding, asset, scan, report)
- Prompt suggestions

### Acceptance Criteria
- [ ] Chat answers questions about findings, assets, risk
- [ ] Citations link to actual data
- [ ] No hallucinated findings
- [ ] Workspace isolation enforced
- [ ] Streaming responses

---

## Stage 17: Automation (n8n)

**Objective**: Operational automation workflows

**Dependencies**: Stage 6, Stage 13

### n8n Workflows to Build
1. **Notifications**: Slack, Email, PagerDuty on critical findings
2. **Scheduled Scans**: Daily/weekly per asset frequency
3. **Remediation Execution**: Config/infra apply with approval
4. **Weekly Reports**: Generate and email
5. **License Compliance**: Check dependency licenses
6. **Cleanup**: Old scan events, temp files
7. **Health Monitoring**: Service checks, alerting
8. **Integration Sync**: GitHub/GitLab webhook → scan trigger

### Backend Changes
- n8n client wrapper
- Webhook endpoints for n8n callbacks
- Workflow management API

### Frontend Changes
- Automation page: Workflow status, logs
- Manual trigger buttons

### Acceptance Criteria
- [ ] All 8 workflows operational
- [ ] Notifications deliver reliably
- [ ] Scheduled scans run on time
- [ ] Remediation execution auditable
- [ ] Webhook security verified

---

## Stage 18: Integrations

**Objective**: Third-party integrations for workflow

**Dependencies**: Stage 5, Stage 6

### Integrations
| Integration | Features |
|-------------|----------|
| GitHub | Webhook → scan, PR creation, status checks |
| GitLab | Webhook → scan, MR creation |
| Bitbucket | Webhook → scan, PR creation |
| Jira | Finding → ticket, sync status |
| Slack | Notifications, /shadowops commands |
| PagerDuty | Critical finding alerts |
| Teams | Notifications |
| Webhook | Generic outgoing |

### Implementation
- OAuth flows where needed
- Webhook signature verification
- Configuration UI in Settings
- Connection testing

### Acceptance Criteria
- [ ] GitHub/GitLab/Bitbucket repo import
- [ ] Scan on push/PR
- [ ] Jira ticket creation from finding
- [ ] Slack notifications formatted
- [ ] Webhook signatures validated

---

## Stage 19: Security Hardening

**Objective**: Production-grade security

**Dependencies**: All previous stages

### Tasks
- [ ] Penetration testing (internal)
- [ ] Dependency audit (all services)
- [ ] Secret scanning (truffleHog, git-secrets)
- [ ] CSP headers strict
- [ ] Rate limiting tuned
- [ ] RLS policies reviewed
- [ ] Audit log completeness verified
- [ ] Encryption at rest verified
- [ ] Backup/restore tested
- [ ] Incident response drill
- [ ] Access review (least privilege)
- [ ] Vulnerability management process documented

---

## Stage 20: Testing & QA

**Objective**: Comprehensive test coverage

**Dependencies**: All previous stages

### Test Types
| Type | Target | Tool |
|------|--------|------|
| Unit | > 80% coverage | pytest, vitest |
| Integration | All API endpoints | pytest, httpx |
| E2E | Critical user flows | Playwright |
| Load | Scan pipeline, API | Locust/k6 |
| Security | SAST, DAST, SCA | Semgrep, OWASP ZAP |
| Chaos | Failure injection | Custom |

### Test Suites
- Authentication flows
- Workspace isolation (RLS)
- Scan pipeline (success, partial, fail, cancel)
- Finding lifecycle
- Remediation approval + execution
- Verification accuracy
- Chat accuracy (golden set)
- Report generation

### Acceptance Criteria
- [ ] CI passes all test suites
- [ ] Load test: 100 concurrent scans
- [ ] Security scan: 0 critical/high
- [ ] E2E: All primary flows pass

---

## Stage 21: Railway Deployment

**Objective**: Production deployment on Railway

**Dependencies**: Stage 19

### Tasks
- [ ] Railway project setup (prod + staging)
- [ ] All services deployed
- [ ] Custom domains configured (TLS)
- [ ] Environment variables set
- [ ] Health checks passing
- [ ] Scaling policies configured
- [ ] Log drains configured
- [ ] Monitoring alerts configured
- [ ] Backup verified
- [ ] Rollback procedure tested
- [ ] DNS cutover

---

## Stage 22: Documentation

**Objective**: Complete documentation for users and developers

**Dependencies**: All previous stages

### Deliverables
- **User Docs**: Getting started, Asset setup, Scanning, Findings, Remediation, Reports, Chat
- **Admin Docs**: Workspace management, Integrations, Security, Billing
- **API Docs**: OpenAPI spec, Authentication, Rate limits, Examples
- **Developer Docs**: Architecture, Contributing, Local dev, Testing, Deployment
- **Runbooks**: Incident response, Scaling, Backup/restore, Secret rotation

---

## Stage 23: AI Usage Report

**Objective**: Transparent AI cost and usage tracking

**Dependencies**: Stage 8, Stage 9

### Features
- Per-workspace AI usage dashboard
- Cost breakdown by model, agent, scan
- Token usage trends
- Budget alerts
- Model performance metrics (latency, success rate)
- Optimization recommendations

### Implementation
- Aggregate `agent_runs` data
- Daily/hourly rollups
- API + UI

---

## Stage 24: Final QA & Hackathon Demo

**Objective**: Production-ready demo

**Dependencies**: All previous stages

### Demo Narrative (Scripted)
1. **LOGIN** → Firebase Auth
2. **DASHBOARD** → Security score, recent activity
3. **ADD AUTHORIZED ASSET** → GitHub repo + authorization evidence
4. **START SCAN** → Full scan type
5. **AI SECURITY MANAGER** → Shows agents executing in real-time
6. **AGENTS EXECUTE** → Recon, Code, Dependency, Threat, Risk, Path, Remediation
7. **FINDINGS** → Table with risk scores
8. **EVIDENCE** → Code snippets, logs
9. **RISK SCORE** → Breakdown explanation
10. **ATTACK PATH** → Graph visualization
11. **AI REMEDIATION** → Proposal with diff
12. **HUMAN APPROVAL** → Approve with conditions
13. **VERIFICATION** → Auto-triggered, passes
14. **FIX VERIFIED** → Finding status → FIXED
15. **SECURITY SCORE IMPROVES** → Dashboard updates
16. **REPORT** → Executive PDF download

### Demo Environment
- Controlled target: Purpose-built vulnerable app (DVWA/Juice Shop variant)
- Pre-configured workspace
- Pre-recorded authorization
- Known findings for consistent demo

### Final Checks
- [ ] Demo runs end-to-end without errors
- [ ] All UI interactions smooth
- [ ] No console errors
- [ ] Performance acceptable
- [ ] Backup demo recording ready

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Semgrep performance on large repos | High | Medium | Incremental scans, sparse checkout, parallel |
| AI hallucination in findings | Medium | High | Schema validation, confidence gates, human review |
| AI cost overruns | Medium | High | Hard budgets, Flash preference, caching |
| Railway scaling limits | Low | High | Monitor, request limit increases, multi-region |
| Supabase RLS misconfiguration | Low | Critical | Automated RLS tests, audit |
| Firebase Auth vendor lock-in | Low | Medium | Abstract auth interface |
| n8n reliability | Medium | Medium | Health checks, dead letter queues |
| Third-party API changes | Medium | Medium | Version pinning, adapter pattern |
| Team velocity | Medium | High | Prioritize ruthlessly, cut scope |

---

## Success Metrics (Post-Launch)

| Metric | Target |
|--------|--------|
| Scan success rate | > 95% |
| Median scan time (full) | < 20 min |
| Finding false positive rate | < 10% |
| Remediation proposal acceptance | > 70% |
| Verification pass rate | > 90% |
| AI cost per scan | < $5 |
| API P99 latency | < 500ms |
| Uptime | 99.9% |
| Customer NPS | > 50 |
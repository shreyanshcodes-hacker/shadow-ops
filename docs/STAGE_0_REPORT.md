# STAGE 0 FINAL REPORT

## Executive Summary

Stage 0 (Architecture & Ingestion) for **ShadowOps** — an AI-native cybersecurity SaaS platform — is **COMPLETE**.

All 15 required architecture documents have been created, covering the full system design from product definition through Railway deployment. No implementation code has been written. The project is ready to proceed to Stage 1: Foundation.

---

## Product Understanding

### What is ShadowOps?
An **AI Security Team** for startups and engineering organizations that continuously:
- **Discovers** vulnerabilities across authorized applications, repositories, APIs, and infrastructure
- **Analyzes** findings with specialized AI agents
- **Correlates** findings into attack paths
- **Prioritizes** risk via deterministic, explainable scoring
- **Explains** results through contextual AI chat
- **Remediates** with AI-generated, human-approved fixes
- **Verifies** fixes empirically
- **Reports** security posture to stakeholders

### Core Constraint
> **NO AUTHORIZATION → NO SCAN**
> Enforced at the backend layer. Frontend is never a security boundary.

### Target Users
1. **Startup Founders** — Executive visibility, investor reports
2. **CTOs** — Strategic risk view, resource allocation
3. **Engineering Teams** — Actionable findings in workflow
4. **Security Engineers** — Deep analysis, custom rules, hunt
5. **Developers** — Contextual explanations, guided fixes
6. **DevOps Teams** — Pipeline integration, deployment gates
7. **Security Consultants** — Multi-client, professional reporting

---

## Source Documents Inspected

| Category | Status |
|----------|--------|
| PRD / SRS | NOT FOUND (greenfield) |
| Architecture docs | NOT FOUND |
| UI designs | NOT FOUND |
| Existing code | NOT FOUND (empty repo) |
| Assets/logos | NOT FOUND |
| Documentation | NOT FOUND |
| Configuration files | NOT FOUND |

**Source of Truth**: The Stage 0 task specification itself serves as the single canonical source.

---

## Architecture Summary

### High-Level Architecture

```
USER → NEXT.JS FRONTEND → FIREBASE AUTH → PYTHON BACKEND (FastAPI)
                                        │
                    ┌───────────────────┼───────────────────┐
                    ▼                   ▼                   ▼
              SERVICES            AGENT SYSTEM         SECURITY CONTROLS
                    │                   │                   │
                    ▼                   ▼                   ▼
             SUPABASE PG          GEMINI/GROK           SEMGREP
                    │
                    ▼
            SUPABASE STORAGE
                    │
                    ▼
                   N8N (Automation)
```

### Deployment Target: Railway
- **Frontend**: Next.js (2-10 replicas)
- **Backend**: FastAPI (2-20 replicas)
- **Workers**: Celery (1-10 replicas, KEDA scaled)
- **Beat**: Celery Beat (1 replica)
- **n8n**: Workflow automation (1 replica)
- **Redis**: Managed (Celery broker, cache, rate limit)
- **Database**: Supabase PostgreSQL (external, managed)

---

## Technical Stack (Locked)

| Layer | Technology | Version Constraint |
|-------|------------|-------------------|
| Frontend Framework | Next.js | 14+ (App Router) |
| Frontend Language | TypeScript | Strict mode |
| Frontend Styling | Tailwind CSS | Custom design system |
| Backend Framework | FastAPI | Python 3.11+ |
| ORM | SQLAlchemy | 2.0 (async) |
| Database | Supabase PostgreSQL | 16+ |
| Storage | Supabase Storage | S3-compatible |
| Authentication | Firebase Auth | Admin SDK + Client SDK |
| AI Models | Gemini 1.5 Pro/Flash, Grok | API |
| Code Analysis | Semgrep | Latest |
| Automation | n8n | Self-hosted on Railway |
| Deployment | Railway | Container-based |
| CI/CD | GitHub Actions | Railway deploy |

**No substitutions permitted without documented blocker.**

---

## Data Model (23 Tables)

### Core Tables
1. `profiles` — User profiles (synced from Firebase)
2. `workspaces` — Top-level containers
3. `workspace_members` — Many-to-many with roles
4. `roles` — Reference (owner, admin, member, viewer)

### Asset & Authorization
5. `assets` — Targets (repo, API, infra, app, container)
6. `asset_authorizations` — **Enforces NO AUTH → NO SCAN**

### Scan & Execution
7. `scans` — Scan records with state machine
8. `scan_events` — Immutable event log (realtime)
9. `agent_runs` — AI agent execution tracking

### Findings & Evidence
10. `findings` — Normalized security findings
11. `finding_evidence` — Provenance (code, logs, screenshots)

### Risk & Attack Paths
12. `risk_assessments` — Deterministic scores with factors
13. `attack_paths` — Graph containers
14. `attack_path_nodes` — Graph nodes
15. `attack_path_edges` — Graph edges

### Remediation & Verification
16. `remediation_proposals` — AI-generated fixes
17. `remediation_approvals` — Human approval audit trail
18. `verification_runs` — Empirical verification results

### Reporting & Chat
19. `reports` — Generated reports (executive, technical, scan)
20. `chat_conversations` — AI Security Chat sessions
21. `chat_messages` — Messages with citations

### Audit & Operations
22. `audit_logs` — Immutable security audit trail (7-year retention)
23. `notifications` — In-app + multi-channel alerts

**All workspace-scoped tables enforce Row Level Security (RLS).**

---

## AI Architecture

### AI Security Manager
Coordinates 8 specialized agents via structured workflows:

| Agent | Primary Model | Purpose |
|-------|---------------|---------|
| Recon | Flash + Tools | External reconnaissance |
| Code Security | Pro | SAST finding enrichment |
| Dependency | Flash + Grok | SCA reachability analysis |
| Threat Analyst | Grok + Pro | Adversarial attack scenarios |
| Risk Analyst | Flash | Deterministic risk scoring |
| Remediation | Pro | Code/config diffs + test plans |
| Verification | Flash | Test design + criteria |
| Reporting | Pro + Flash | Structured report generation |

### Model Routing
- **Gemini 1.5 Pro**: Deep reasoning, large context (attack paths, remediation)
- **Gemini 1.5 Flash**: High-volume, structured output (classification, chat)
- **Grok**: Security expertise, alternative reasoning (threat analysis)

### Safety Controls
- All outputs schema-validated (Pydantic)
- Confidence gates per agent
- Hallucination detection (cross-reference finding IDs)
- Workspace scope enforcement
- Cost budgets (per-scan, per-agent, daily)

### AI Security Chat
- Retrieval-augmented (SQL + future vector)
- Citation-required responses
- Workspace-scoped data only
- Refusal on out-of-scope queries

---

## Agent Architecture

### Orchestration
- **Celery** for distributed task execution
- **DAG-based workflow** (9 phases with dependencies)
- **Agent Runner** pattern (validation → execution → evidence → cost tracking)
- **State machine**: QUEUED → RUNNING → COMPLETED/PARTIAL/FAILED/CANCELLED
- **Cooperative cancellation** with force timeout

### Execution Order
```
RECON → CODE_ANALYSIS + DEPENDENCY_ANALYSIS (parallel)
  → FINDING_NORMALIZATION
  → THREAT_ANALYSIS
  → RISK_ANALYSIS
  → ATTACK_PATH_CONSTRUCTION
  → REMEDIATION_GENERATION
  → REPORT_GENERATION
```

---

## Security Model

### Principles (14 Non-Negotiable)
1. Authentication required
2. Backend authorization mandatory
3. Frontend state never trusted
4. Workspace isolation mandatory
5. Assets belong to workspaces
6. Scan requests validate authorization server-side
7. No authorization = no scan
8. Secrets never reach browser
9. AI output validated before use
10. AI never performs uncontrolled destructive actions
11. Human approval required for sensitive remediation
12. All security actions auditable
13. Evidence must have provenance
14. External targets never scanned without explicit authorization

### Authorization Flow
```
Scan Request
    → Auth Middleware (Firebase token)
    → Workspace Middleware (membership + role)
    → AuthZ Service (asset_authorizations.status = 'verified')
    → Scan Created
```

### Secrets Management
- **Railway Variables**: Service-level secrets (API keys, DB URLs)
- **Supabase Vault**: Per-asset credentials (Git tokens, cloud keys)
- **Never in code, never in frontend, never logged**

---

## Scan Pipeline

### 11 Phases
1. **AUTHORIZATION_CHECK** — Blocking, synchronous
2. **ASSET_VALIDATION** — Connectivity probe
3. **SCAN_CREATED** — Queued with Celery
4. **RECON** — Subdomains, ports, tech, SSL, headers
5. **CODE_ANALYSIS** — Semgrep SAST + secrets
6. **DEPENDENCY_ANALYSIS** — Semgrep SCA + OSV/GHSA
7. **FINDING_NORMALIZATION** — Dedupe, enrich, store
8. **AI_ANALYSIS** — Threat, Risk, Attack Path, Remediation
9. **RISK_ANALYSIS** — Deterministic scoring
10. **ATTACK_PATH_CORRELATION** — Graph construction
11. **SCAN_COMPLETED** — Summary, notifications, reports

### Failure Handling
- Critical phases (auth, normalization, risk) → SCAN_FAILED
- Non-critical phases → SCAN_PARTIAL
- Retry policies per error category
- Graceful cancellation (SIGTERM → 30s → SIGKILL)

---

## Risk Engine

### Deterministic Formula (6 Factors)
```
Final Score = Σ (factor_value × weight)

Weights (default, configurable):
  Base Severity:        30%
  Exploitability:       20%
  Exposure:             15%
  Asset Criticality:    15%
  Confidence:           10%
  Attack Path Impact:   10%
```

### Key Properties
- **Deterministic**: Same inputs = same score
- **Explainable**: Full factor breakdown stored
- **Auditable**: Formula versioned
- **AI-Augmented**: AI provides exploitability/exposure analysis; engine computes

### Risk Levels
- 90-100: Critical (immediate)
- 70-89: High (7 days)
- 40-69: Medium (30 days)
- 15-39: Low (next sprint)
- 0-14: Informational

---

## Remediation & Verification

### Remediation Workflow
```
Finding → AI Proposal → Human Review → Approval → Authorized Execution → Verification → Fixed
```

### Execution Methods
| Fix Type | Method | Approval |
|----------|--------|----------|
| Code change | Git PR | Code review |
| Config change | n8n (Terraform/K8s/Cloud) | Admin in n8n |
| Dependency | Git PR | Code review |
| Infrastructure | n8n (Terraform/Pulumi) | Admin in n8n |
| WAF rule | n8n → WAF API | Security admin |

### Verification Types (Empirical)
1. **Reproduction Test** — Original PoC fails
2. **Semgrep Rescan** — Rule no longer matches
3. **Dependency Check** — CVE resolved in lockfile
4. **Config Audit** — Live state matches desired
5. **Regression Check** — No new critical findings

---

## Railway Deployment

### Services
| Service | Image | Replicas | Resources |
|---------|-------|----------|-----------|
| frontend | Custom (Next.js) | 2-10 | 1 vCPU / 2GB |
| backend | Custom (FastAPI) | 2-20 | 2 vCPU / 4GB |
| celery-worker | Custom | 1-10 (KEDA) | 2 vCPU / 4GB |
| celery-beat | Custom | 1 | 0.5 vCPU / 1GB |
| n8n | n8nio/n8n | 1 | 1 vCPU / 2GB |
| redis | Railway Managed | 1 | 2GB HA |

### Networking
- Internal: `.railway.internal` DNS
- External: Custom domains (app.shadowops.io, api.shadowops.io)
- CORS: Single origin only
- TLS: Railway managed

### Secrets
All in Railway Variables. Rotation procedure documented.

### Estimated Cost
- **Typical**: $150-500/month
- **Peak**: $900-1200/month
- Plus Supabase ($25+) and AI API costs

---

## Implementation Roadmap

### 24 Stages (38 weeks / ~9.5 months)

| Phase | Stages | Focus |
|-------|--------|-------|
| Foundation | 1-4 | Scaffolding, UI, Auth, Workspace |
| Assets & Scan | 5-7 | Assets, AuthZ, Scan Engine, Semgrep |
| AI Core | 8-9 | AI Manager, 8 Agents |
| Findings & Risk | 10-12 | Findings, Risk, Attack Paths |
| Remediation | 13-14 | Proposals, Approval, Verification |
| Reporting & Chat | 15-16 | Reports, AI Chat |
| Automation | 17-18 | n8n, Integrations |
| Hardening | 19-21 | Security, Testing, Deploy |
| Documentation | 22-24 | Docs, AI Report, Demo |

### Per-Stage Definition
Each stage specifies:
- Objective
- Dependencies
- Database/Backend/Frontend/AI changes
- Security considerations
- Testing approach
- Acceptance criteria

---

## Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Semgrep performance on large repos | High | Medium | Incremental scans, sparse checkout |
| AI hallucination in findings | Medium | High | Schema validation, confidence gates, human review |
| AI cost overruns | Medium | High | Hard budgets, Flash preference, caching |
| Railway scaling limits | Low | High | Monitor, multi-region future |
| Supabase RLS misconfiguration | Low | Critical | Automated RLS tests, audit |
| n8n reliability | Medium | Medium | Health checks, DLQ |
| Third-party API changes | Medium | Medium | Adapter pattern, version pinning |

---

## Unresolved Questions

1. **pgvector for Chat**: Enable now or Stage 16? (Defer to Stage 16)
2. **Custom Semgrep Rules**: UI for rule authoring? (Stage 18)
3. **Multi-region Railway**: Required for launch? (Post-launch)
4. **Compliance Frameworks**: SOC2 Type II timeline? (Post-launch)
5. **Pricing Model**: Per-seat vs per-asset vs per-scan? (Business decision)
6. **Free Tier Limits**: Scan count, retention, AI budget? (Stage 4)

---

## Acceptance Status

| Area | Status |
|------|--------|
| Product Understanding | ✅ COMPLETE |
| Architecture | ✅ COMPLETE |
| Database Design | ✅ COMPLETE |
| AI Architecture | ✅ COMPLETE |
| Agent Architecture | ✅ COMPLETE |
| Security Architecture | ✅ COMPLETE |
| Scan Architecture | ✅ COMPLETE |
| Railway Architecture | ✅ COMPLETE |
| Implementation Roadmap | ✅ COMPLETE |

---

## Next Steps

1. **Stage 1: Foundation** (Week 1)
   - Initialize Next.js + FastAPI projects
   - Configure CI/CD (GitHub Actions → Railway)
   - Provision Supabase + Firebase
   - Set up Docker Compose for local dev

2. **Stage 2: UI/UX** (Weeks 2-3)
   - Implement ShadowOps design system
   - Build all 10 navigation pages (skeleton)
   - Component library in Storybook

3. **Stage 3: Authentication** (Week 4)
   - Firebase Auth integration
   - Workspace onboarding flow

---

## Conclusion

Stage 0 has produced a comprehensive, implementation-ready architecture for ShadowOps. All technical decisions are documented, justified, and cross-referenced. The system is designed for security-first operation, AI-augmented analysis, and scalable deployment on Railway.

**Ready to proceed to Stage 1.**
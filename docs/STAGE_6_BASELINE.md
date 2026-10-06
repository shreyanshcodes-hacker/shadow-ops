# STAGE 6 BASELINE — Stage 5 Architecture Audit

## 1. Stage 5 Architecture Summary

ShadowOps Stage 5 implements an AI Security Analyst that consumes normalized findings and trusted evidence from Stage 4 and produces structured security analysis for human review.

### Core Components

**Database Models** (`backend/app/models/__init__.py`):
- `Finding` — Normalized security findings from scanners (Semgrep, recon, dependency)
- `FindingEvidence` — Structured evidence attached to findings (code snippets, logs, configs, rule matches)
- `FindingAiAnalysis` — Persisted AI analysis results per finding with full SecurityAnalysis schema
- `AiRun` — AI execution tracking (provider, model, tokens, cost, status, input_hash for deduplication)
- `Scan` — Scan execution with lifecycle events
- Workspace isolation enforced at database level via `workspace_id` foreign keys

**AI Provider Abstraction** (`backend/app/ai/providers/`):
- `AIProvider` abstract base class with structured output support (`generate_structured`)
- `GeminiProvider` — Google Gemini 1.5 Pro/Flash with native JSON schema validation
- `GrokProvider` — xAI Grok with JSON schema via response_format
- Registry pattern for provider selection via `AI_PROVIDER` env var
- Health checks, cost estimation, error categorization (auth, rate limit, timeout, server)

**AI Schemas** (`backend/app/ai/schemas.py`):
- `SecurityAnalysis` — Strict typed output for finding analysis with:
  - summary, vulnerability_type, severity_assessment, confidence
  - exploitability_assessment, impact_assessment, affected_component
  - attack_preconditions, evidence_interpretation, reasoning
  - recommended_next_steps, uncertainty, supporting_evidence (with OBSERVED/INFERRED/UNCERTAIN certainty)
- `ScanAnalysis` — Batch scan-level analysis
- Enums: `VulnerabilityType`, `SeverityAssessment`, `ExploitabilityAssessment`, `EvidenceCertainty`

**Prompt Injection Defense** (`backend/app/ai/safety.py`):
- Explicit delimiters: `<TRUSTED_SYSTEM_INSTRUCTIONS>` / `</TRUSTED_SYSTEM_INSTRUCTIONS>` and `<UNTRUSTED_SECURITY_EVIDENCE>` / `</UNTRUSTED_SECURITY_EVIDENCE>`
- `build_safe_prompt()` enforces separation
- System prompt explicitly states evidence is untrusted data

**Data Minimization & Secret Redaction** (`backend/app/ai/safety.py`):
- `redact_secrets()` — Regex patterns for API keys, tokens, private keys, passwords, JWTs, DB URLs
- `sanitize_for_ai()` — Redacts secrets, truncates to max_chars, normalizes whitespace
- `sanitize_evidence_dict()` — Recursive sanitization of evidence content

**AI Manager** (`backend/app/ai/manager.py`):
- `AIManager.analyze_finding()` — Main entry point
- Context building: loads finding + evidence, sanitizes, builds prompt
- Deduplication via `input_hash` (SHA256 of finding + evidence)
- Retry logic with error categorization (retryable vs non-retryable)
- Output validation against schema + evidence ID verification
- Persistence to `FindingAiAnalysis` and `AiRun`
- Audit logging for completed/failed analyses

**API Endpoints** (`backend/app/api/v1/ai.py`):
- `POST /findings/{finding_id}/ai-analysis` — Start analysis (returns AiRun)
- `GET /findings/{finding_id}/ai-analysis` — Get latest analysis
- `GET /ai-analyses/{analysis_id}` — Get analysis by ID
- `GET /findings/{finding_id}/ai-analyses` — Get all analyses (history)
- `GET /ai/scans/{scan_id}/ai-runs` — List AI runs for scan
- `GET /ai/ai-runs/{run_id}` — Get AI run status
- `GET /ai/providers/status` — Provider configuration status
- `GET /ai/scans/{scan_id}/ai-analysis-status` — Per-finding analysis status

**Frontend** (`frontend/app/(dashboard)/findings/[id]/page.tsx`):
- Finding detail page with full AI analysis display
- Scanner Facts section (authoritative, read-only)
- AI Analysis panel with all SecurityAnalysis fields
- Evidence section with expandable content
- Analysis History sidebar (version comparison)
- Clear "Advisory Only" labeling on AI content

**Security Controls**:
- All AI provider calls backend-only (no browser-to-model)
- Workspace authorization on every API endpoint
- Finding access verified before analysis
- No AI output triggers actions (read-only advisory)
- Input hash deduplication prevents duplicate calls on page refresh

---

## 2. Existing Finding Model

**Finding** (`models/__init__.py:377-425`):
- Links to workspace, scan, asset
- Source: SEMGREP, RECON, DEPENDENCY, AI_ANALYSIS, MANUAL
- Severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), Confidence (LOW/MEDIUM/HIGH)
- Location (file, line_start, line_end), code_snippet
- CWE/CVE/OWASP tags
- Status workflow (OPEN → TRIAGED → IN_PROGRESS → FIXED/FALSE_POSITIVE/WONT_FIX/RISK_ACCEPTED)
- `risk_score` (nullable float), `risk_factors` (JSONB)

**FindingEvidence** (`models/__init__.py:442-469`):
- Types: CODE_SNIPPET, SCREENSHOT, LOG, REQUEST_RESPONSE, CONFIG, DEPENDENCY_TREE, AI_REASONING, STATIC_ANALYSIS, SOURCE_LOCATION, RULE_MATCH, SCAN_OUTPUT
- Content as JSONB, file_path, line range
- Storage object reference for large files

---

## 3. Existing AI Analysis Model

**FindingAiAnalysis** (`models/__init__.py:562-600`):
- finding_id (FK), ai_run_id (FK), workspace_id (FK)
- All SecurityAnalysis fields persisted:
  - summary, vulnerability_type, severity_assessment, confidence
  - exploitability_assessment, impact_assessment, affected_component
  - attack_preconditions, evidence_interpretation, reasoning
  - recommended_next_steps (JSONB), uncertainty
  - supporting_evidence (JSONB with certainty)
- model, provider, prompt_version
- Timestamps

**AiRun** (`models/__init__.py:517-559`):
- workspace_id, scan_id, finding_id (nullable), requested_by
- provider, model, operation (FINDING_ANALYSIS/SCAN_ANALYSIS)
- status (QUEUED/RUNNING/COMPLETED/FAILED)
- prompt_version, input_hash (for deduplication)
- Token usage, cost tracking, error tracking

---

## 4. Existing Database Relationships

- Workspace → Assets (1:N)
- Workspace → Scans (1:N)
- Workspace → Findings (1:N)
- Workspace → AiRuns (1:N)
- Workspace → FindingAiAnalyses (1:N)
- Scan → Findings (1:N)
- Finding → FindingEvidence (1:N)
- Finding → FindingAiAnalysis (1:N)
- AiRun → FindingAiAnalysis (1:1)
- Asset → Scans (1:N)
- Asset → Findings (1:N)

All relationships enforce workspace isolation via `workspace_id` on child tables.

---

## 5. Existing Frontend Finding UI

**Finding Detail Page** (`/findings/[id]`):
- Header with severity badge, source, rule, CWE, OWASP
- Scanner Facts section (authoritative)
- AI Analysis section (collapsible, clearly labeled "Advisory Only")
- Evidence section with expandable content
- Sidebar with metadata + Analysis History (version comparison)
- "Analyze with AI" / "Re-analyze" / "View AI Analysis" actions

---

## 6. Existing API Patterns

- All endpoints require authentication + workspace membership
- Workspace authorization verified via `WorkspaceMember` join table
- Pydantic schemas for request/response validation
- Repository pattern for database access
- Audit logging via `security/audit.py`
- Error handling with structured error codes

---

## 7. What Stage 6 Needs to Add

### New Database Models
1. **FindingRelationship** — Normalized relationships between findings
2. **AttackPath** — Attack path containers
3. **AttackPathNode** — Ordered nodes in attack path
4. **AttackPathEdge** — Relationships between nodes
5. **RiskSnapshot** — Persisted risk calculations with model version

### New AI Task
- `SECURITY_RELATIONSHIP_ANALYSIS` — AI suggests relationships between findings

### Deterministic Services
- `CorrelationEngine` — Deterministic relationship detection (same file, component, entry point, etc.)
- `AttackPathBuilder` — Graph construction from validated relationships
- `RiskEngine` — Deterministic risk scoring (0-100) with explainable factors

### New API Endpoints
- `GET /attack-paths` — List attack paths
- `GET /attack-paths/{id}` — Attack path detail
- `GET /attack-paths/{id}/nodes` — Path nodes
- `GET /attack-paths/{id}/relationships` — Path edges
- `POST /attack-paths/{id}/recalculate-risk` — Recalculate risk score
- `GET /findings/{id}/relationships` — Finding relationships
- `POST /relationships/{id}/confirm` — Human confirm AI suggestion
- `POST /relationships/{id}/dismiss` — Human dismiss AI suggestion

### Frontend Pages
- `/attack-paths` — Attack path list
- `/attack-paths/[id]` — Attack path detail with graph visualization
- Finding detail page: "Security Relationships" section
- Dashboard: Attack path metrics

### Security Controls
- AI suggestions clearly marked as `AI_SUGGESTED` (not authoritative)
- Human confirmation required for `HUMAN_CONFIRMED` relationships
- Risk engine completely deterministic (no AI in final score)
- Workspace isolation on all new endpoints
- Cycle detection, max path length, graph safety
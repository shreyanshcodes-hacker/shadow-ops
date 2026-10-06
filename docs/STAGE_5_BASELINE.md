# STAGE 5 BASELINE — Stage 4 Architecture Audit

## 1. Stage 4 Architecture Summary

ShadowOps Stage 4 implements a complete security scanning pipeline with AI-ready infrastructure:

### Core Components

**Database Models** (`backend/app/models/__init__.py`):
- `Finding` - Normalized security findings from scanners (Semgrep, recon, dependency)
- `FindingEvidence` - Structured evidence attached to findings (code snippets, logs, configs, rule matches)
- `Scan` - Scan execution with lifecycle events
- `ScanEvent` - Detailed phase-by-phase scan timeline
- `AiRun` - AI execution tracking (provider, model, tokens, cost, status)
- `FindingAiAnalysis` - Persisted AI analysis results per finding
- Workspace isolation enforced at database level

**AI Provider Abstraction** (`backend/app/ai/providers/`):
- `AIProvider` abstract base class with structured output support
- `GeminiProvider` - Google Gemini 1.5 Pro/Flash with JSON schema validation
- `GrokProvider` - xAI Grok with JSON schema via response_format
- Registry pattern for provider selection via `AI_PROVIDER` env var
- Health checks, cost estimation, error categorization (auth, rate limit, timeout, server)

**AI Schemas** (`backend/app/ai/schemas.py`):
- `SecurityAnalysis` - Strict typed output for finding analysis with:
  - summary, vulnerability_type, severity_assessment, confidence
  - exploitability_assessment, impact_assessment, affected_component
  - attack_preconditions, evidence_interpretation, reasoning
  - recommended_next_steps, uncertainty, supporting_evidence (with OBSERVED/INFERRED/UNCERTAIN certainty)
- `ScanAnalysis` - Batch scan-level analysis
- Enums: `VulnerabilityType`, `SeverityAssessment`, `ExploitabilityAssessment`, `EvidenceCertainty`

**Prompt Injection Defense** (`backend/app/ai/safety.py`):
- Explicit delimiters: `<TRUSTED_SYSTEM_INSTRUCTIONS>` / `</TRUSTED_SYSTEM_INSTRUCTIONS>` and `<UNTRUSTED_SECURITY_EVIDENCE>` / `</UNTRUSTED_SECURITY_EVIDENCE>`
- `build_safe_prompt()` enforces separation
- System prompt explicitly states evidence is untrusted data

**Data Minimization & Secret Redaction** (`backend/app/ai/safety.py`):
- `redact_secrets()` - Regex patterns for API keys, tokens, private keys, passwords, JWTs, DB URLs
- `sanitize_for_ai()` - Redacts secrets, truncates to max_chars, normalizes whitespace
- `sanitize_evidence_dict()` - Recursive sanitization of evidence content
- 32+ secret pattern types covered

**AI Manager** (`backend/app/ai/manager.py`):
- `AIManager.analyze_finding()` - Main entry point
- Context building: loads finding + evidence, sanitizes, builds prompt
- Deduplication via `input_hash` (SHA256 of finding + evidence)
- Retry logic with error categorization (retryable vs non-retryable)
- Output validation against schema + evidence ID verification
- Persistence to `FindingAiAnalysis` and `AiRun`
- Audit logging for completed/failed analyses

**API Endpoints** (`backend/app/api/v1/ai.py`):
- `POST /ai/scans/{scan_id}/analyze-finding` - Start analysis (returns AiRun)
- `GET /ai/findings/{finding_id}/ai-analysis` - Get latest analysis
- `GET /ai/scans/{scan_id}/ai-runs` - List AI runs for scan
- `GET /ai/ai-runs/{run_id}` - Get AI run status
- `GET /ai/providers/status` - Provider configuration status
- `GET /ai/scans/{scan_id}/ai-analysis-status` - Per-finding analysis status

**Frontend** (`frontend/app/(dashboard)/scans/[id]/page.tsx`):
- Findings tab with AI analysis status badges (Not Analyzed, Analyzing, Available, Failed)
- "Analyze with AI" button triggers backend analysis
- Expandable AI analysis panel showing summary, explanation, impact, classification, confidence
- Clear "AI-Generated Analysis / Advisory Only" labeling
- Polling for analysis status updates

**Security Controls**:
- All AI provider calls backend-only (no browser-to-model)
- Workspace authorization on every API endpoint
- Finding access verified before analysis
- No AI output triggers actions (read-only advisory)
- Input hash deduplication prevents duplicate calls on page refresh

---

## 2. Current AI Provider Abstraction

**Strengths**:
- Clean interface with `generate_structured()` for typed output
- Provider-agnostic error handling with retryable classification
- Cost estimation per provider/model
- Configuration-driven provider selection

**Gaps for Stage 5**:
- No `AI_PROMPT_VERSION` config variable (used in AIManager but not defined in config)
- Grok provider doesn't support native JSON schema (uses prompt injection approach)
- No explicit token budget enforcement in manager

---

## 3. Current Finding/Evidence Structure

**Finding** (`models/__init__.py:377-425`):
- Links to workspace, scan, asset
- Source: SEMGREP, RECON, DEPENDENCY, AI_ANALYSIS, MANUAL
- Severity (CRITICAL/HIGH/MEDIUM/LOW/INFO), Confidence (LOW/MEDIUM/HIGH)
- Location (file, line_start, line_end), code_snippet
- CWE/CVE/OWASP tags
- Status workflow (OPEN → TRIAGED → IN_PROGRESS → FIXED/FALSE_POSITIVE/WONT_FIX/RISK_ACCEPTED)

**FindingEvidence** (`models/__init__.py:442-469`):
- Types: CODE_SNIPPET, SCREENSHOT, LOG, REQUEST_RESPONSE, CONFIG, DEPENDENCY_TREE, AI_REASONING, STATIC_ANALYSIS, SOURCE_LOCATION, RULE_MATCH, SCAN_OUTPUT
- Content as JSONB, file_path, line range
- Storage object reference for large files

---

## 4. Reusable Services

| Service | Location | Stage 5 Reuse |
|---------|----------|---------------|
| AI Provider Registry | `ai/providers/__init__.py` | ✅ Full reuse |
| GeminiProvider | `ai/providers/gemini.py` | ✅ Full reuse |
| GrokProvider | `ai/providers/grok.py` | ✅ Full reuse |
| AIManager | `ai/manager.py` | ✅ Core logic reusable |
| Secret Redaction | `ai/safety.py` | ✅ Full reuse |
| Prompt Injection Defense | `ai/safety.py` | ✅ Full reuse |
| Schema Validation | `ai/validation.py` | ✅ Full reuse |
| Audit Logging | `security/audit.py` | ✅ Full reuse |
| Workspace Auth | `security/auth.py` | ✅ Full reuse |

---

## 5. Missing Pieces for Stage 5

### API Endpoint Alignment
**Required by spec** → **Current implementation**:
- `POST /findings/{finding_id}/ai-analysis` → `POST /ai/scans/{scan_id}/analyze-finding`
- `GET /findings/{finding_id}/ai-analysis` → `GET /ai/findings/{finding_id}/ai-analysis` ✅
- `GET /ai-analyses/{analysis_id}` → **MISSING**

### Schema Alignment
**SecurityAnalysis output** → **FindingAiAnalysis storage**:
- `evidence_interpretation` → **MISSING** (stored as `technical_explanation`)
- `attack_preconditions` → **MISSING**
- `reasoning` → **MISSING**
- `vulnerability_type` → **MISSING**
- `severity_assessment` → **MISSING**
- `exploitability_assessment` → **MISSING**
- `affected_component` → **MISSING**
- `supporting_evidence` with certainty → Partially stored (as JSON without certainty enum)

### Frontend Display
Current FindingRow shows placeholder "Analysis available - click to view details" instead of actual analysis fields.

### Configuration
- `AI_PROMPT_VERSION` not in config.py (hardcoded fallback in AIManager)
- No per-workspace daily analysis limit (cost protection)

### Tests
- No automated tests for AI analysis flow
- No provider test double (FakeAIProvider)
- No prompt injection test cases

### Documentation
- No STAGE_5_REPORT.md
- No AI_ARCHITECTURE.md
- No AI_PROMPT_INJECTION_DEFENSE.md
- No AI_PROVIDER_CONFIGURATION.md
- No AI_SECURITY_BOUNDARY.md

---

## 6. Implementation Plan

### Phase 1: Schema & Model Alignment
1. Add missing fields to `FindingAiAnalysis` model
2. Update `FindingAiAnalysisResponse` schema
3. Update AIManager persistence to store all SecurityAnalysis fields

### Phase 2: API Endpoint Compliance
1. Add `POST /findings/{finding_id}/ai-analysis` endpoint
2. Add `GET /ai-analyses/{analysis_id}` endpoint
2. Keep existing endpoints for backward compatibility

### Phase 3: Frontend Enhancement
1. Create dedicated Finding Detail page (`/findings/[id]`) with full AI analysis display
2. Update scan detail page to link to finding detail
3. Display all SecurityAnalysis fields with OBSERVED/INFERRED/UNCERTAIN badges

### Phase 4: Configuration & Hardening
1. Add `AI_PROMPT_VERSION` to config
2. Add per-workspace daily analysis limit
3. Add request timeout enforcement

### Phase 5: Testing
1. Create FakeAIProvider for tests
2. Test authorization, context building, prompt injection, schema validation
3. Test provider failures, deduplication, persistence

### Phase 6: Documentation
1. Create all required documentation files

---

## 7. Verification Checklist (Definition of Done)

- [ ] Stage 4 remains functional
- [ ] AI provider abstraction reused
- [ ] Structured AI analysis schema complete
- [ ] Context builder exists
- [ ] Data minimization exists
- [ ] Secret redaction exists
- [ ] Prompt-injection defenses exist
- [ ] Gemini adapter works when configured
- [ ] Grok adapter works when configured
- [ ] Provider failures handled
- [ ] AI output schema validated
- [ ] AI analyses persisted with all fields
- [ ] Historical analyses preserved
- [ ] Duplicate requests controlled
- [ ] Workspace isolation works
- [ ] Finding detail contains AI analysis
- [ ] No direct browser-to-provider requests
- [ ] No AI output can trigger actions
- [ ] Audit logging exists
- [ ] Tests pass
- [ ] TypeScript passes
- [ ] Lint passes
- [ ] Production build passes
- [ ] Documentation complete
- [ ] No fake AI results
- [ ] No autonomous remediation
- [ ] No exploitation
- [ ] No attack-path analysis
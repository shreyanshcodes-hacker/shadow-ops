# STAGE 7 BASELINE — Stage 6 Architecture Audit

## 1. Stage 6 Architecture Summary

ShadowOps Stage 6 implements Attack Path Intelligence and a Deterministic Risk Engine that correlates findings, builds attack paths from validated relationships, and calculates auditable risk scores.

### Core Components

**Database Models** (`backend/app/models/__init__.py`):
- `FindingRelationship` — Normalized finding-to-finding relationships with type, confidence, source (DETERMINISTIC/AI_SUGGESTED/HUMAN_CONFIRMED)
- `AttackPath` — Attack path containers with status, confidence, severity, risk_score, risk_model_version
- `AttackPathNode` — Ordered nodes in attack path (ENTRY/FINDING/BOUNDARY/IMPACT) with rationale
- `AttackPathEdge` — Relationships between nodes with type, confidence, source, rationale
- `RiskSnapshot` — Immutable historical risk calculations with factors breakdown

**Correlation Engine** (`backend/app/services/correlation.py`):
- `CorrelationEngine` — Deterministic relationship detection (same file, component, entry point, CWE, OWASP, vulnerability chains)
- `AIRelationshipAnalyzer` — AI-powered pairwise relationship analysis using Stage 5 AIManager
- Creates `AI_SUGGESTED` relationships requiring human confirmation

**Attack Path Builder** (`backend/app/services/attack_path.py`):
- `AttackPathBuilder` — Graph construction from validated relationships
- DFS with cycle detection, max 8 nodes, 20 edges
- Entry point detection, deduplication by finding sequence signature
- `AttackPathManager` — High-level operations (list, update, dismiss, recalculate)

**Risk Engine** (`backend/app/services/risk.py`):
- `RiskEngine` — Deterministic risk scoring (0-100) with 6 weighted factors
- `RiskManager` — Calculation, persistence, history
- Risk bands: INFORMATIONAL (0-19), LOW (20-39), MEDIUM (40-59), HIGH (60-79), CRITICAL (80-100)
- Factors: Severity (30%), Exploitability (20%), Impact (20%), Confidence (15%), Exposure (10%), Path Complexity (5%)

**AI Provider Abstraction** (reused from Stage 5):
- `AIProvider` abstract base with `generate_structured` for typed output
- `GeminiProvider`, `GrokProvider` adapters
- Registry pattern via `AI_PROVIDER` env var
- Health checks, cost estimation, error categorization

**AI Schemas** (reused from Stage 5):
- `SecurityAnalysis` — Finding-level structured output
- `ScanAnalysis` — Scan-level structured output
- Enums: `VulnerabilityType`, `SeverityAssessment`, `ExploitabilityAssessment`, `EvidenceCertainty`

**Prompt Injection Defense** (reused from Stage 5):
- Delimiters: `<TRUSTED_SYSTEM_INSTRUCTIONS>` / `</TRUSTED_SYSTEM_INSTRUCTIONS>` and `<UNTRUSTED_SECURITY_EVIDENCE>` / `</UNTRUSTED_SECURITY_EVIDENCE>`
- `build_safe_prompt()` enforces separation
- System prompt explicitly states evidence is untrusted data

**Data Minimization & Secret Redaction** (reused from Stage 5):
- `redact_secrets()` — 32+ regex patterns for keys, tokens, passwords, JWTs
- `sanitize_for_ai()` — Redacts, truncates (50k chars), normalizes whitespace
- `sanitize_evidence_dict()` — Recursive sanitization

**API Endpoints** (`backend/app/api/v1/attack_paths.py`):
- 20+ endpoints for attack paths, relationships, correlation, risk
- All require auth + workspace membership
- Human confirmation: `POST /relationships/{id}/confirm` → `HUMAN_CONFIRMED`

**Frontend Pages**:
- `/attack-paths` — List with stats, filters, generation actions
- `/attack-paths/[id]` — Detail with graph visualization, risk breakdown, history
- `/findings/[id]` — "Security Relationships" section + "Run Correlation" action

---

## 2. Existing AI Architecture

### Provider Abstraction
```
AIProvider (abstract)
├── generate_structured(prompt, output_schema, model, temperature, max_tokens, system_prompt) → AIResponse[OutputT]
├── generate_text(prompt, model, temperature, max_tokens, system_prompt) → str
├── health_check() → bool
└── estimate_cost(model, input_tokens, output_tokens) → float

AIProviderRegistry (global)
├── register(provider)
├── get(provider_type) → AIProvider
├── get_by_model(model) → AIProvider
└── health_check_all() → Dict[AIProviderType, bool]
```

### AI Manager (Stage 5)
```
AIManager(db)
├── analyze_finding(finding_id, user_id, workspace_id, force_reanalyze) → FindingAiAnalysis
├── _prepare_evidence_for_ai(evidence_list) → List[Dict]
├── _compute_input_hash(finding, evidence_data) → str
├── _build_finding_prompt(finding, evidence_data) → str
├── _call_provider_with_retries(prompt, evidence_ids) → SecurityAnalysis
├── _persist_analysis(ai_run, finding, analysis, evidence_ids) → FindingAiAnalysis
└── get_finding_analysis(finding_id, workspace_id) → FindingAiAnalysis
```

### Agent Base (Stage 5 - minimal)
```
BaseAgent (abstract)
├── name, description, model, input_schema, output_schema
├── max_retries = 2, timeout_seconds = 300, cost_cap_usd = 5.0
├── execute(input, context) → AIResponse[OutputT]
├── validate_input(data) → InputT
├── validate_output(data) → OutputT
└── run_with_retry(input, context) → AIResponse[OutputT]

AgentRegistry (global)
├── register(agent_class)
├── get(name) → type[BaseAgent]
└── all() → Dict[str, type[BaseAgent]]
```

---

## 3. Existing Finding/Evidence Architecture

### Finding Model
- Workspace, scan, asset foreign keys
- Source: SEMGREP, RECON, DEPENDENCY, AI_ANALYSIS, MANUAL
- Severity, confidence, CWE/CVE/OWASP tags
- Location (file, line_start, line_end), code_snippet
- Status workflow: OPEN → TRIAGED → IN_PROGRESS → FIXED/FALSE_POSITIVE/WONT_FIX/RISK_ACCEPTED
- risk_score (nullable), risk_factors (JSONB)

### FindingEvidence Model
- Types: CODE_SNIPPET, SCREENSHOT, LOG, REQUEST_RESPONSE, CONFIG, DEPENDENCY_TREE, AI_REASONING, STATIC_ANALYSIS, SOURCE_LOCATION, RULE_MATCH, SCAN_OUTPUT
- Content as JSONB, file_path, line range
- Metadata JSONB

### FindingAiAnalysis Model
- finding_id, ai_run_id, workspace_id FKs
- All SecurityAnalysis fields persisted
- model, provider, prompt_version
- supporting_evidence as JSONB array of {evidence_id, reason, certainty}

### AiRun Model
- workspace_id, scan_id, finding_id (nullable), requested_by
- provider, model, operation (FINDING_ANALYSIS/SCAN_ANALYSIS)
- status: QUEUED/RUNNING/COMPLETED/FAILED
- prompt_version, input_hash (deduplication)
- Token usage, cost, error tracking

---

## 4. Existing Attack Path Architecture

### Models
| Model | Purpose |
|-------|---------|
| `FindingRelationship` | Source/target finding, type (8), confidence, source (3), rationale |
| `AttackPath` | asset_id, title, description, status (DRAFT/ACTIVE/DISMISSED/RESOLVED), confidence, severity, risk_score, risk_model_version |
| `AttackPathNode` | attack_path_id, finding_id (nullable), sequence, node_type (ENTRY/FINDING/BOUNDARY/IMPACT), rationale |
| `AttackPathEdge` | attack_path_id, source/target node_id, relationship_type, confidence, source, rationale |
| `RiskSnapshot` | attack_path_id, score, risk_band, model_version, factors (JSONB), calculated_at |

### Graph Construction (`AttackPathBuilder`)
1. Load relationships meeting criteria (workspace, asset, min_confidence, include_ai_suggested)
2. Build adjacency graph
3. Find entry points (nodes with no incoming edges)
4. DFS with cycle detection (max depth = 8)
5. Deduplicate by finding sequence signature
6. Create AttackPath with nodes (typed by position) and edges (from relationships)

### Safety Constraints
- `MAX_PATH_NODES = 8`
- `MAX_PATH_EDGES = 20`
- Cycle detection prevents infinite recursion
- Workspace isolation on all queries
- Asset isolation (paths within single asset)

---

## 5. Existing Risk Engine

### Deterministic Formula (risk-v1)
```
Score = Σ (weight × value × 100)
```

| Factor | Weight | Source |
|--------|--------|--------|
| Severity | 30% | Max finding severity in path |
| Exploitability | 20% | Edge confidences (relationship strength) |
| Impact | 20% | Node types (IMPACT/BOUNDARY nodes) |
| Confidence | 15% | Path confidence + edge confidences |
| Exposure | 10% | Entry point nodes |
| Path Complexity | 5% | Path length (inverse) |

### Guarantees
- **Deterministic**: Same inputs → same score
- **Explainable**: Full factor breakdown with contributions
- **Versioned**: `risk_model_version` stored with every snapshot
- **AI-free**: No LLM in final score calculation

### Persistence
- `RiskSnapshot` created on every calculation
- Never overwrites - enables trend analysis
- Audit logged: `risk.calculated`

---

## 6. Existing Background Job Infrastructure

### Scan Runner (`backend/app/scanning/runner.py`)
- `ScanRunner` executes scans in phases
- Phase-based with events: QUEUED → RUNNING → COMPLETED/FAILED
- Async execution with proper error handling
- Integrates Semgrep scanner

### AI Runs (existing)
- `AiRun` model tracks individual AI analysis executions
- Status: QUEUED/RUNNING/COMPLETED/FAILED
- Retry logic in `AIManager._call_provider_with_retries`

### Audit Logs
- Immutable `audit_logs` table (BIGSERIAL)
- Actions: scan.*, ai.analysis.*, attack_path.*, risk.calculated
- Workspace-scoped, user-attributed

---

## 7. Reusable Components for Stage 7

| Component | Location | Reuse Strategy |
|-----------|----------|----------------|
| `AIProvider` abstraction | `app/ai/providers/` | Direct reuse for all 5 agents |
| `AIProviderRegistry` | `app/ai/providers.py` | Single provider for all agents |
| `AIManager` context building | `app/ai/manager.py` | Extend context builders per agent |
| `sanitize_*` functions | `app/ai/safety.py` | All agent inputs sanitized |
| `build_safe_prompt` | `app/ai/safety.py` | All agent prompts use delimiters |
| `SecurityAnalysis` schema | `app/ai/schemas.py` | Extend for agent outputs |
| `BaseAgent` / `AgentRegistry` | `app/agents/base.py` | **Extend** for team agents |
| `AiRun` model | `app/models/__init__.py` | **Extend** to `AgentRun` model |
| `Finding` / `FindingEvidence` | `app/models/__init__.py` | Context sources |
| `AttackPath` / `RiskSnapshot` | `app/models/__init__.py` | Context sources |
| `CorrelationEngine` | `app/services/correlation.py` | Recon agent input |
| `RiskEngine` | `app/services/risk.py` | Risk analyst agent input |
| Database repositories | `app/repositories/` | Extend for new models |
| Audit logging | `app/security/audit.py` | All team/agent events |

---

## 8. Stage 7 Additions Required

### New Database Models
1. **SecurityTeamRun** — Team run orchestration record
2. **AgentRun** — Individual agent execution record (extends AiRun pattern)
3. **TeamAssessment** — Final security reviewer output (or extend SecurityTeamRun)

### New Agents (5)
1. **RECON_AGENT** — Asset structure analysis
2. **VULNERABILITY_ANALYST_AGENT** — Deep finding analysis
3. **ATTACK_PATH_AGENT** — Relationship/path analysis
4. **RISK_ANALYST_AGENT** — Risk interpretation
5. **SECURITY_REVIEWER_AGENT** — Final assessment synthesis

### Orchestration Layer
1. **Agent Registry** — Centralized agent discovery
2. **SecurityTeamOrchestrator** — Dependency-aware scheduling
3. **Context Builders** — Per-agent minimal context
4. **Output Validators** — Schema + evidence reference validation

### API Endpoints
- `POST /security-team/runs` — Create team run
- `GET /security-team/runs` — List runs
- `GET /security-team/runs/{id}` — Run detail
- `GET /security-team/runs/{id}/agents` — Agent runs
- `GET /security-team/runs/{id}/assessment` — Final assessment
- `POST /security-team/runs/{id}/review` — Human review

### Frontend Pages
- `/security-team` — Team status dashboard
- `/security-team/[id]` — Run detail with agent outputs

### Security Controls
- Prompt injection defenses for all agents
- Data minimization per agent
- Cost/rate limits (per-run agent limits, timeouts, max retries)
- No autonomous actions (advisory only)
- Human review boundary (AI ANALYSIS COMPLETE → HUMAN REVIEW REQUIRED)

---

## 9. Database Migration Strategy

Next sequential migration: `0005_stage7_security_team.sql`

Required tables:
```sql
security_team_runs (
    id, workspace_id, asset_id, scan_id, status, requested_by,
    started_at, completed_at, orchestration_version, team_summary,
    confidence, created_at, updated_at
)

agent_runs (
    id, team_run_id, agent_name, status, input_reference,
    output, confidence, provider, model, started_at, completed_at,
    error_code, attempt, created_at
)

team_assessments (optional, or embed in security_team_runs)
    team_run_id, executive_summary, key_findings, key_attack_paths,
    risk_interpretation, uncertainties, conflicting_assessments,
    recommended_human_actions, overall_confidence, created_at
```

Indexes on workspace_id, team_run_id, agent_name, status.
Foreign keys with CASCADE.
RLS policies matching existing patterns.
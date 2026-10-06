# ShadowOps AI Architecture

## Overview

This document describes the AI architecture for ShadowOps Stage 4, implementing the AI Security Manager as a centralized service for structured security analysis of scanner findings.

## Design Principles

1. **Trusted Evidence → AI Interpretation**: AI never generates security facts; only interprets verified scanner output
2. **Advisory Only**: AI output is informational; deterministic backend remains authoritative
3. **Workspace Isolation**: All AI data scoped to workspace via RLS and application-layer checks
4. **Auditability**: Every AI interaction logged with metadata (no secrets)
5. **Cost Control**: Hard limits on input size, output tokens, retries, and timeouts
6. **Security First**: Prompt injection defenses, secret redaction, evidence validation

## Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │ Scan Detail │  │ Finding Row │  │ AI Analysis Panel       │ │
│  │ Page        │──│ Component   │──│ (Summary, Explanation,  │ │
│  └──────┬──────┘  └─────────────┘  │  Impact, Confidence)    │ │
└─────────┼──────────────────────────┴───────────┬──────────────┘
          │                                     │
          ▼                                     ▼
┌─────────────────────────────────────────────────────────────────┐
│                      API Layer (FastAPI)                        │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ POST /ai/scans/{id}/analyze-finding                       │  │
│  │ GET  /ai/findings/{id}/ai-analysis                        │  │
│  │ GET  /ai/ai-runs/{id}                                     │  │
│  │ GET  /ai/scans/{id}/ai-analysis-status                    │  │
│  │ GET  /ai/providers/status                                 │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AI Security Manager                           │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ analyze_finding(finding_id, user_id, workspace_id)        │  │
│  │   1. Validate access (user → ws → scan → finding → evidence)│  │
│  │   2. Retrieve evidence (server-side)                      │  │
│  │   3. Sanitize (secrets, size, minimization)               │  │
│  │   4. Build prompt (system + untrusted evidence delimiters) │  │
│  │   5. Call provider (with retries)                         │  │
│  │   6. Validate output (schema, evidence IDs, confidence)   │  │
│  │   7. Persist analysis + update AI run                     │  │
│  │   8. Audit log                                            │  │
│  └───────────────────────────┬───────────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────────┘
                               │
          ┌────────────────────┼────────────────────┐
          ▼                    ▼                    ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  GeminiProvider  │ │   GrokProvider   │ │  Provider Base   │
│  (google-genai)  │ │  (xAI API)       │ │  (AIProvider)    │
└────────┬─────────┘ └────────┬─────────┘ └────────┬─────────┘
         │                    │                    │
         └────────────────────┴────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Database (Supabase)                        │
│  ┌─────────────┐  ┌──────────────────────┐  ┌──────────────┐   │
│  │ ai_runs     │  │ finding_ai_analysis  │  │ findings/    │   │
│  │ (tracking)  │  │ (structured output)  │  │ evidence     │   │
│  └─────────────┘  └──────────────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Finding Analysis Request

```
1. User clicks "Analyze with AI" on finding
   ↓
2. Frontend: POST /ai/scans/{scan_id}/analyze-finding {finding_id}
   ↓
3. API: Validate auth, workspace membership, scan ownership, finding ownership
   ↓
4. API: Instantiate AIManager(db)
   ↓
5. AIManager.analyze_finding(finding_id, user_id, workspace_id)
   ↓
6. FindingRepository.get_by_id(finding_id) → verify workspace_id match
   ↓
7. FindingEvidenceRepository.get_by_finding(finding_id) → trusted evidence
   ↓
8. Sanitize evidence (redact_secrets, sanitize_for_ai, size limits)
   ↓
9. Compute input_hash (SHA256 of normalized finding + evidence)
   ↓
10. Check existing: SELECT * FROM finding_ai_analysis 
                    JOIN ai_runs ON ... 
                    WHERE finding_id = ? AND input_hash = ? AND status = COMPLETED
    → If exists: return existing analysis (deduplication)
   ↓
11. Create AiRun (QUEUED, input_hash, prompt_version, provider, model)
   ↓
12. Update AiRun → RUNNING, started_at = now()
   ↓
13. Build prompt: FINDING_ANALYSIS_SYSTEM_PROMPT + FINDING_ANALYSIS_USER_PROMPT_TEMPLATE
   ↓
14. Call provider.generate_structured(prompt, FindingAnalysis, system_prompt=...)
   ↓
15. Validate response:
    - JSON structure matches FindingAnalysis
    - Required fields present
    - confidence ∈ [0.0, 1.0]
    - classification ∈ FindingClassification enum
    - All supporting_evidence.evidence_id exist in provided evidence
    - certainty ∈ EvidenceCertainty enum
   ↓
16. If valid: sanitize_output (truncate long fields)
    Create FindingAiAnalysis record
    Update AiRun → COMPLETED, tokens, cost
    Audit log: ai.analysis.completed
   ↓
17. If invalid: Update AiRun → FAILED, error_code, error_message
    Audit log: ai.analysis.failed
    Raise AIManagerError
   ↓
18. Return FindingAiAnalysis to API → Frontend
```

## Provider Abstraction

### Base Interface (`AIProvider`)

```python
class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_type(self) -> AIProviderType: ...
    
    @property
    @abstractmethod
    def default_model(self) -> AIModel: ...
    
    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        output_schema: type[OutputT],
        model: Optional[AIModel] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> AIResponse[OutputT]: ...
    
    @abstractmethod
    async def generate_text(...) -> str: ...
    
    @abstractmethod
    async def health_check() -> bool: ...
    
    @abstractmethod
    def estimate_cost(model: AIModel, input_tokens: int, output_tokens: int) -> float: ...
```

### Error Hierarchy

```
AIProviderError (base)
├── AIProviderAuthError (non-retryable)
├── AIProviderRateLimitError (retryable)
├── AIProviderTimeoutError (retryable)
├── AIProviderServerError (retryable)
└── AIProviderValidationError (non-retryable)
```

### Retry Policy

```python
max_retries = 3 (configurable via AI_MAX_RETRIES)

for attempt in range(max_retries):
    try:
        response = await provider.generate_structured(...)
        if response.success:
            validate_and_return(response.data)
        elif validation_error:
            raise AIManagerError  # Non-retryable
        else:
            raise AIProviderError  # Retryable
    except AIProviderAuthError:
        raise  # Non-retryable
    except AIProviderError as e:
        if not e.retryable or attempt == max_retries - 1:
            raise
        wait_exponential_backoff(attempt)
```

## Database Schema

### ai_runs

```sql
CREATE TABLE ai_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    scan_id UUID NOT NULL REFERENCES scans(id),
    finding_id UUID REFERENCES findings(id),
    requested_by UUID NOT NULL REFERENCES profiles(id),
    provider ai_provider_type NOT NULL,  -- 'gemini' | 'grok'
    model TEXT NOT NULL,
    operation ai_operation_type NOT NULL,  -- 'finding_analysis' | 'scan_analysis'
    status ai_run_status NOT NULL DEFAULT 'queued',  -- 'queued' | 'running' | 'completed' | 'failed'
    prompt_version TEXT NOT NULL DEFAULT '1.0',
    input_hash TEXT NOT NULL,  -- SHA256 for deduplication
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    input_tokens INT,
    output_tokens INT,
    estimated_cost_usd NUMERIC(10,6),
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### finding_ai_analysis

```sql
CREATE TABLE finding_ai_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(id),
    ai_run_id UUID NOT NULL REFERENCES ai_runs(id),
    workspace_id UUID NOT NULL REFERENCES workspaces(id),
    summary TEXT NOT NULL,
    technical_explanation TEXT NOT NULL,
    impact TEXT NOT NULL,
    confidence NUMERIC(3,2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    classification TEXT,
    uncertainty TEXT,
    supporting_evidence JSONB NOT NULL DEFAULT '[]',
    model TEXT NOT NULL,
    provider ai_provider_type NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

### RLS Policies

```sql
-- ai_runs
CREATE POLICY "ai_run_select" ON ai_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- finding_ai_analysis
CREATE POLICY "finding_ai_analysis_select" ON finding_ai_analysis
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));
```

## Structured Output Schema

### FindingAnalysis (Pydantic)

```python
class FindingAnalysis(BaseModel):
    summary: str = Field(min_length=10, max_length=500)
    technical_explanation: str = Field(min_length=20, max_length=2000)
    impact: str = Field(min_length=20, max_length=2000)
    classification: FindingClassification = FindingClassification.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: str = Field(default="", max_length=1000)
    supporting_evidence: List[SupportingEvidenceRef] = Field(default_factory=list)

class SupportingEvidenceRef(BaseModel):
    evidence_id: str
    reason: str
    certainty: EvidenceCertainty = EvidenceCertainty.OBSERVED
```

### FindingClassification Enum

```
INJECTION
AUTHENTICATION
AUTHORIZATION
CRYPTOGRAPHY
DATA_EXPOSURE
CONFIGURATION
DEPENDENCY
DENIAL_OF_SERVICE
BUSINESS_LOGIC
UNKNOWN
```

### EvidenceCertainty Enum

```
OBSERVED    # Directly seen in evidence
INFERRED    # Reasonable deduction
UNCERTAIN   # Cannot determine from evidence
```

## Configuration

### Environment Variables

```bash
# Provider Selection
AI_PROVIDER=gemini  # or 'grok'

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

# Grok
GROK_API_KEY=
GROK_MODEL=grok-1

# Cost Controls
AI_MAX_FINDINGS_PER_RUN=10
AI_MAX_INPUT_CHARS=50000
AI_MAX_OUTPUT_TOKENS=4096
AI_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=3
```

### Defaults

| Setting | Default | Description |
|---------|---------|-------------|
| AI_PROVIDER | gemini | Active provider |
| GEMINI_MODEL | gemini-1.5-flash | Cost-optimized default |
| GROK_MODEL | grok-1 | Default Grok model |
| AI_MAX_FINDINGS_PER_RUN | 10 | Limit findings per batch |
| AI_MAX_INPUT_CHARS | 50000 | Input truncation limit |
| AI_MAX_OUTPUT_TOKENS | 4096 | Output token limit |
| AI_TIMEOUT_SECONDS | 60 | Request timeout |
| AI_MAX_RETRIES | 3 | Max retry attempts |

## Security Boundaries

### What AI CANNOT Do

- ❌ Modify infrastructure, repos, databases, production systems
- ❌ Override scanner severity (HIGH/CRITICAL remain authoritative)
- ❌ Calculate CVSS, risk scores, security scores
- ❌ Generate attack paths
- ❌ Execute remediation (code changes, patches, PRs, deployments)
- ❌ Operate autonomously (no agent loops)
- ❌ Access secrets (API keys, DB passwords, private keys)

### What AI CAN Do

- ✅ Explain vulnerability root cause
- ✅ Assess potential impact
- ✅ Classify vulnerability type
- ✅ Express confidence in analysis
- ✅ Identify uncertainty areas
- ✅ Reference specific evidence
- ✅ Suggest remediation approaches (advisory)

## Observability

### Metrics Tracked Per AI Run

- Provider & model
- Operation type
- Prompt version
- Duration (ms)
- Input/output tokens
- Estimated cost (USD)
- Status (completed/failed)
- Error code (if failed)

### Audit Events

| Event | When |
|-------|------|
| `ai.analysis.requested` | User triggers analysis |
| `ai.analysis.started` | Provider call begins |
| `ai.analysis.completed` | Valid output persisted |
| `ai.analysis.failed` | Error during analysis |

## Future Extensibility (Stage 5+)

The architecture supports:

1. **Specialist Agents**: New agents can use `AIProvider` abstraction
2. **Multi-Provider Orchestration**: Registry pattern allows fallback/routing
3. **Scan-Level Analysis**: `SCAN_ANALYSIS` operation type scaffolded
4. **Agent Communication**: Structured schemas enable agent-to-agent handoff
5. **Budget Management**: Per-run cost tracking enables budget enforcement
6. **Prompt Versioning**: `prompt_version` field supports A/B testing
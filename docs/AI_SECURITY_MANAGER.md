# ShadowOps AI Security Manager

## Purpose

The AI Security Manager is the central service in Stage 4 responsible for analyzing trusted scanner evidence and producing structured security analysis. It acts as the bridge between deterministic scanner output (Semgrep) and AI-powered interpretation.

## Responsibilities

1. **Evidence Retrieval**: Fetch findings and evidence from database (server-side only)
2. **Sanitization**: Redact secrets, enforce size limits, minimize data
3. **Prompt Construction**: Build injection-safe prompts with clear delimiters
4. **Provider Orchestration**: Call AI provider with structured output, handle retries
5. **Output Validation**: Validate JSON structure, evidence references, confidence ranges
6. **Persistence**: Store analysis results with full traceability
7. **Audit Logging**: Record all AI interactions for compliance
8. **Cost Tracking**: Monitor token usage and estimated costs

## Interface

```python
class AIManager:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.provider = get_active_provider()
        # Repositories initialized here
    
    async def analyze_finding(
        self,
        finding_id: UUID,
        user_id: UUID,
        workspace_id: UUID,
    ) -> FindingAiAnalysis:
        """
        Main entry point for finding analysis.
        
        Raises:
            AIManagerError: On validation, provider, or persistence failures
        """
    
    async def get_finding_analysis(
        self,
        finding_id: UUID,
        workspace_id: UUID,
    ) -> Optional[FindingAiAnalysis]:
        """Get existing analysis for a finding."""
    
    async def get_ai_run(
        self,
        run_id: UUID,
        workspace_id: UUID,
    ) -> Optional[AiRun]:
        """Get AI run status."""
    
    async def list_ai_runs_for_scan(
        self,
        scan_id: UUID,
        workspace_id: UUID,
    ) -> List[AiRun]:
        """List all AI runs for a scan."""
```

## Analysis Flow

```
analyze_finding(finding_id, user_id, workspace_id)
    │
    ├─► _get_finding_for_analysis()
    │     └─ FindingRepository.get_by_id()
    │         └─ Verify: finding.workspace_id == workspace_id
    │
    ├─► FindingEvidenceRepository.get_by_finding()
    │     └─ Returns trusted evidence (server-side only)
    │
    ├─► _prepare_evidence_for_ai()
    │     └─ sanitize_evidence_dict() for each evidence
    │         ├─ redact_secrets()
    │         ├─ sanitize_for_ai() (truncate)
    │         └─ Normalize structure
    │
    ├─► _compute_input_hash()
    │     └─ SHA256 of normalized finding + evidence
    │
    ├─► _find_existing_analysis()
    │     └─ Query: finding_id + input_hash + COMPLETED status
    │         └─ If found: return existing (deduplication)
    │
    ├─► _create_ai_run()
    │     └─ AiRun(QUEUED, input_hash, provider, model, operation)
    │
    ├─► _update_ai_run(RUNNING, started_at)
    │
    ├─► _build_finding_prompt()
    │     └─ FINDING_ANALYSIS_SYSTEM_PROMPT + USER_PROMPT_TEMPLATE
    │         └─ Evidence IDs embedded for reference validation
    │
    ├─► _call_provider_with_retries()
    │     └─ provider.generate_structured(FindingAnalysis)
    │         └─ Retry on: RateLimit, Timeout, ServerError
    │         └─ No retry on: AuthError, ValidationError
    │
    ├─► validate_finding_analysis()
    │     ├─ Required fields, lengths
    │     ├─ confidence ∈ [0.0, 1.0]
    │     ├─ classification ∈ FindingClassification
    │     ├─ evidence_ids ⊆ provided_evidence_ids
    │     └─ certainty ∈ EvidenceCertainty
    │
    ├─► sanitize_analysis_output()
    │     └─ Truncate long fields to limits
    │
    ├─► _persist_analysis()
    │     └─ FindingAiAnalysis + AiRun(COMPLETED)
    │
    ├─► audit_log(ai.analysis.completed)
    │
    └─► Return FindingAiAnalysis
```

## Error Handling

### Error Codes

| Code | Meaning | Retryable |
|------|---------|-----------|
| `AI_AUTH_ERROR` | Provider API key invalid/missing | No |
| `AI_RATE_LIMIT` | Provider 429 | Yes |
| `AI_TIMEOUT` | Request timeout | Yes |
| `AI_SERVER_ERROR` | Provider 5xx | Yes |
| `AI_VALIDATION_ERROR` | Output schema/evidence validation failed | No |
| `FINDING_NOT_FOUND` | Finding doesn't exist or access denied | No |
| `ANALYSIS_FAILED` | Unexpected error | No |

### Failure Behavior

1. **Mark AiRun FAILED** with error_code, error_message, failed_at
2. **Audit log** `ai.analysis.failed` with sanitized error info
3. **Raise AIManagerError** with error_code for API layer
4. **Never modify** original Finding or FindingEvidence
5. **Frontend** shows "AI Analysis Failed" with error message

## Security Guarantees

### Access Control

```python
# Every analysis request validates:
1. User authenticated (Firebase JWT)
2. User is workspace member (member+ role)
3. Finding belongs to workspace
4. Finding belongs to scan
5. Scan is completed/eligible
6. Evidence retrieved server-side (not from browser)
```

### Evidence Integrity

- Browser sends only `finding_id` (or `scan_id`)
- Backend retrieves ALL evidence from database
- AI never receives browser-supplied evidence text
- Evidence IDs in AI output validated against provided set

### Severity Immutability

```python
# Finding.severity (from Semgrep) is NEVER modified by AI
# AI provides:
#   - classification (vulnerability type)
#   - confidence (analysis certainty 0.0-1.0)
#   - explanation/impact (advisory)
# Finding.severity remains authoritative
```

## Deduplication

### Input Hash

```python
def _compute_input_hash(finding, evidence_data):
    content = {
        "finding_id": str(finding.id),
        "source_rule_id": finding.source_rule_id,
        "title": finding.title,
        "description": finding.description,
        "severity": finding.severity.value,
        "location": finding.location,
        "code_snippet": finding.code_snippet,
        "evidence": evidence_data,  # Already sanitized
    }
    serialized = json.dumps(content, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode()).hexdigest()[:32]
```

### Reuse Logic

```python
existing = await db.execute(
    select(FindingAiAnalysis)
    .join(AiRun)
    .where(
        FindingAiAnalysis.finding_id == finding_id,
        AiRun.input_hash == input_hash,
        AiRun.status == AiRunStatus.COMPLETED,
    )
    .order_by(AiRun.created_at.desc())
    .limit(1)
)
if existing:
    return existing  # Reuse, no new provider call
```

## Prompt Versioning

- `prompt_version` field tracks prompt template version
- Default: "1.0"
- New versions → new analyses (different input_hash)
- Enables A/B testing and rollback

## Cost Tracking

```python
# Per run (from provider metadata):
input_tokens = response.usage_metadata.prompt_token_count
output_tokens = response.usage_metadata.candidates_token_count
estimated_cost = provider.estimate_cost(model, input_tokens, output_tokens)

# Persisted in AiRun:
ai_run.input_tokens = input_tokens
ai_run.output_tokens = output_tokens
ai_run.estimated_cost_usd = estimated_cost
```

## Testing Strategy

### Unit Tests (Mocked)

- Provider adapters (config, auth, success, errors)
- Schema validation (valid/invalid inputs)
- Safety functions (redaction, sanitization, prompt building)
- Validation logic (evidence IDs, confidence, classification)

### Integration Tests (Mocked Provider)

- Full analysis flow
- Deduplication
- Error handling paths
- Workspace isolation
- Cost controls

### Security Tests

- Cross-workspace access denied
- Fake evidence ID rejected
- Scanner severity immutable
- Prompt injection attempts contained
- Secret redaction verified

## Configuration

```python
# In AIManager.__init__
self.max_retries = settings.AI_MAX_RETRIES  # 3
self.max_input_chars = settings.AI_MAX_INPUT_CHARS  # 50000
self.max_output_tokens = settings.AI_MAX_OUTPUT_TOKENS  # 4096
```

## Limitations

1. **Single finding at a time**: No batch analysis yet
2. **Scan-level analysis**: Scaffolded but not fully implemented
3. **No cost budgets**: Only tracking, no enforcement
4. **Provider fallback**: Manual config switch only
5. **Prompt versioning**: Manual, not automated
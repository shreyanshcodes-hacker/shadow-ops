# ShadowOps AI Testing Guide

## Test Organization

```
backend/tests/
├── test_ai.py              # Comprehensive Stage 4 tests
├── test_scans.py           # Stage 3 tests (must still pass)
├── test_services.py        # Stage 1-2 tests
└── test_api.py             # API tests
```

## Test Categories

### 1. Provider Tests

#### Gemini Adapter

| Test | Description |
|------|-------------|
| `test_gemini_provider_configuration_with_key` | Provider initializes with valid API key |
| `test_gemini_provider_missing_key` | Provider reports unavailable without key |
| `test_gemini_provider_default_model` | Correct default model (Flash) |
| `test_gemini_provider_pro_model` | Pro model when configured |
| `test_gemini_generate_structured_not_configured` | Graceful failure without key |
| `test_gemini_health_check_not_configured` | Health check returns False without key |

#### Grok Adapter

| Test | Description |
|------|-------------|
| `test_grok_provider_configuration_with_key` | Provider initializes with valid API key |
| `test_grok_provider_missing_key` | Provider reports unavailable without key |
| `test_grok_provider_default_model` | Correct default model |
| `test_grok_generate_structured_not_configured` | Graceful failure without key |
| `test_grok_health_check_not_configured` | Health check returns False without key |

#### Provider Selection

| Test | Description |
|------|-------------|
| `test_provider_registry_registration` | Providers registered in registry |
| `test_get_active_provider_fallback` | Correct provider selected via config |

### 2. Schema Validation Tests

| Test | Description |
|------|-------------|
| `test_valid_finding_analysis` | Valid FindingAnalysis passes |
| `test_invalid_confidence_too_high` | Confidence > 1.0 rejected |
| `test_invalid_confidence_too_low` | Confidence < 0.0 rejected |
| `test_invalid_classification` | Invalid enum value rejected |
| `test_summary_too_short` | Min length enforced |
| `test_validate_finding_analysis_valid` | Full validation passes |
| `test_validate_finding_analysis_missing_evidence_ref` | Fake evidence ID rejected |
| `test_validate_finding_analysis_invalid_confidence` | Range validation works |
| `test_sanitize_analysis_output_truncates_long_fields` | Truncation enforced |

### 3. Safety Tests (Secret Redaction & Prompt Injection)

| Test | Description |
|------|-------------|
| `test_redact_api_key` | Generic API key pattern |
| `test_redact_aws_keys` | AWS access/secret keys |
| `test_redact_github_token` | GitHub token formats |
| `test_redact_supabase_key` | Supabase JWT keys |
| `test_redact_private_key` | PEM private keys |
| `test_redact_database_url` | DB URLs with credentials |
| `test_sanitize_for_ai_truncates` | Size limit enforcement |
| `test_sanitize_evidence_dict` | Recursive dict sanitization |
| `test_build_safe_prompt_contains_delimiters` | Prompt structure correct |
| `test_validate_ai_output_references_valid` | Valid references pass |
| `test_validate_ai_output_references_invalid_id` | Fake ID rejected |
| `test_validate_ai_output_references_missing_field` | Missing field caught |

### 4. Security Tests

| Test | Description |
|------|-------------|
| `test_cross_workspace_ai_request_denied` | Workspace isolation enforced |
| `test_browser_cannot_supply_arbitrary_evidence` | Server-side evidence retrieval |

#### Prompt Injection Scenarios

| Test | Description |
|------|-------------|
| `test_malicious_source_comment_treated_as_untrusted` | Comment injection contained |
| `test_malicious_readme_content` | README injection contained |
| `test_malicious_finding_message` | Scanner message injection contained |

### 5. Persistence Tests

| Test | Description |
|------|-------------|
| `test_ai_run_created` | Run created with QUEUED status |
| `test_ai_run_transitions_queued_to_running_to_completed` | Valid transitions |
| `test_ai_run_transitions_queued_to_failed` | Failure transition |
| `test_successful_analysis_persisted` | Analysis stored correctly |
| `test_failed_analysis_persisted_correctly` | Error info stored |
| `test_duplicate_analysis_prevented` | Input hash deduplication |
| `test_workspace_isolation` | RLS + backend checks |

### 6. Cost Control Tests

| Test | Description |
|------|-------------|
| `test_ai_max_findings_per_run_config` | Config value respected |
| `test_ai_max_input_chars_config` | Config value respected |
| `test_ai_max_output_tokens_config` | Config value respected |
| `test_ai_timeout_seconds_config` | Config value respected |
| `test_ai_max_retries_config` | Config value respected |
| `test_sanitize_respects_max_chars` | Truncation works |
| `test_retry_limit_enforced` | Max 3 retries |

### 7. Critical Security Tests

| Test | Description |
|------|-------------|
| `test_ai_cannot_override_trusted_security_facts` | Scanner severity immutable |
| `test_ai_fake_evidence_id_rejected` | Fabricated evidence IDs rejected |

### 8. Negative Tests (Stage 4 Must NOT Implement)

| Test | Description |
|------|-------------|
| `test_no_autonomous_agents` | No specialist agent modules |
| `test_no_remediation_execution` | No code modification methods |
| `test_no_risk_engine` | No CVSS/risk fields in schemas |
| `test_no_attack_path_generation` | No attack path fields |
| `test_no_ai_chat` | No chat endpoints |
| `test_no_n8n_workflows` | No n8n integration in AI |
| `test_no_railway_deployment` | Not deployed |

## Running Tests

### Backend Tests

```bash
cd /mnt/d/Shreyanshcodes/shadow-ops/backend

# Install test dependencies
pip install pytest pytest-asyncio httpx google-generativeai

# Run all AI tests
python -m pytest tests/test_ai.py -v

# Run with coverage
python -m pytest tests/test_ai.py -v --cov=app.ai --cov-report=term-missing

# Run specific test class
python -m pytest tests/test_ai.py::TestGeminiProvider -v

# Run specific test
python -m pytest tests/test_ai.py::TestAICannotOverrideTrustedFacts::test_ai_cannot_override_scanner_severity -v

# Run Stage 3 tests (regression)
python -m pytest tests/test_scans.py -v
```

### Test Configuration

```python
# pytest.ini or pyproject.toml
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
```

### Mocking Strategy

#### Provider Mocks

```python
# Mock provider for integration tests
with patch('app.ai.manager.get_active_provider') as mock_provider:
    mock_provider.return_value.provider_type = AiProviderType.GEMINI
    mock_provider.return_value.default_model = AIModel.GEMINI_FLASH
    mock_provider.return_value.generate_structured = AsyncMock(return_value=MagicMock(
        success=True,
        data=FindingAnalysis(...),
        metadata=MagicMock(tokens_input=100, tokens_output=200, latency_ms=500)
    ))
```

#### Database Mocks

```python
# AsyncMock for all repository methods
mock_finding_repo = AsyncMock()
mock_finding_repo.get_by_id.return_value = sample_finding
mock_evidence_repo = AsyncMock()
mock_evidence_repo.get_by_finding.return_value = sample_evidence
```

### Test Fixtures

```python
# conftest.py or test_ai.py
@pytest.fixture
def mock_db():
    return AsyncMock()

@pytest.fixture
def sample_workspace():
    return MagicMock(id=uuid4(), name="Test Workspace")

@pytest.fixture
def sample_finding(sample_workspace, sample_scan, sample_asset):
    return Finding(
        id=uuid4(),
        workspace_id=sample_workspace.id,
        scan_id=sample_scan.id,
        asset_id=sample_asset.id,
        source=FindingSource.SEMGREP,
        source_rule_id="test-rule-123",
        title="SQL Injection",
        description="Potential SQL injection vulnerability",
        severity=FindingSeverity.HIGH,
        confidence=FindingConfidence.HIGH,
        cwe_ids=["CWE-89"],
        cve_ids=[],
        owasp_categories=["A03:2021"],
        location={"file": "app.py", "line_start": 42, "line_end": 45},
        code_snippet="query = f'SELECT * FROM users WHERE id = {user_id}'",
        remediation_guidance="Use parameterized queries",
        status=FindingStatus.OPEN,
        risk_factors={},
    )
```

## Live Provider Testing

### Prerequisites

```bash
# Set environment variables
export GEMINI_API_KEY="your-gemini-key"
export GROK_API_KEY="your-grok-key"

# Or use .env file
echo "GEMINI_API_KEY=your-key" >> .env
echo "GROK_API_KEY=your-key" >> .env
```

### Controlled Integration Test

```python
# tests/test_ai_live.py (not committed, for manual verification)
import pytest
from app.ai.providers import get_active_provider
from app.ai.schemas import FindingAnalysis

@pytest.mark.live
@pytest.mark.asyncio
async def test_gemini_live_analysis():
    """Run against real Gemini with controlled fixture."""
    provider = get_active_provider()
    assert provider.provider_type == AIProviderType.GEMINI
    
    # Simple test prompt
    response = await provider.generate_structured(
        prompt="Analyze: eval(user_input) in Python",
        output_schema=FindingAnalysis,
        system_prompt="You are a security analyst. Be concise.",
    )
    
    assert response.success
    assert response.data.summary
    assert 0.0 <= response.data.confidence <= 1.0
    print(f"Tokens: {response.metadata.tokens_input}/{response.metadata.tokens_output}")
    print(f"Cost: ${response.metadata.cost_usd:.6f}")

@pytest.mark.live
@pytest.mark.asyncio
async def test_grok_live_analysis():
    """Run against real Grok with controlled fixture."""
    # Similar structure
    pass
```

### Running Live Tests

```bash
# Only run with explicit flag
pytest tests/test_ai_live.py -v -m live

# Or set environment
LIVE_TESTS=1 pytest tests/test_ai_live.py -v
```

### Live Test Checklist

- [ ] Gemini API key valid and has quota
- [ ] Grok API key valid and has quota
- [ ] Controlled fixture finding (known vulnerability)
- [ ] Expected output structure verified
- [ ] Token counts reasonable
- [ ] Cost within expected range
- [ ] Latency acceptable (< 30s)

## CI/CD Integration

### GitHub Actions Example

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio httpx google-generativeai
      - name: Run tests
        run: |
          cd backend
          python -m pytest tests/test_ai.py tests/test_scans.py -v
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
          GROK_API_KEY: ${{ secrets.GROK_API_KEY }}
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}
```

## Test Data Management

### Fixture Findings

Create controlled test fixtures in `tests/fixtures/`:

```
tests/fixtures/
├── sql_injection.py          # Known SQLi pattern
├── xss_vulnerability.js      # Known XSS pattern
├── hardcoded_secret.py       # Secret pattern (will be redacted)
├── path_traversal.py         # Path traversal
└── README.md                 # Documentation for fixtures
```

### Test Scan Target

Use Stage 3 demo target (`/scan-workspace/demo-target`) with known vulnerabilities.

## Debugging Test Failures

### Common Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| `AsyncMock` not awaited | Missing `await` in test | Add `await` |
| Provider not configured | Missing env var in test | Set `monkeypatch.setattr` |
| Validation error | Schema mismatch | Check FindingAnalysis fields |
| Foreign key violation | Missing FK in mock | Ensure all IDs exist |

### Debug Output

```python
# Add to test for debugging
import logging
logging.basicConfig(level=logging.DEBUG)

# Or in specific test
@pytest.fixture(autouse=True)
def debug_logging(caplog):
    caplog.set_level(logging.DEBUG)
```

## Performance Testing

### Load Test (Manual)

```python
# tests/test_ai_performance.py
@pytest.mark.performance
@pytest.mark.asyncio
async def test_analysis_latency():
    """Measure end-to-end analysis latency."""
    import time
    start = time.time()
    analysis = await manager.analyze_finding(...)
    elapsed = time.time() - start
    assert elapsed < 30  # seconds
    print(f"Latency: {elapsed:.2f}s")
```

## Regression Testing

### Stage 3 Compatibility

```bash
# Ensure Stage 3 tests still pass
python -m pytest tests/test_scans.py -v

# Key Stage 3 tests that must not break:
# - test_unauthorized_asset_never_reaches_scanner
# - test_pending_authorization_blocks_scanner
# - test_revoked_authorization_blocks_scanner
# - test_expired_authorization_blocks_scanner
# - test_valid_authorization_allows_scanner
# - test_user_cannot_scan_another_workspace_asset
# - test_viewer_cannot_create_scan
# - test_findings_persisted_with_correct_links
# - test_summary_calculated_from_actual_results
```

## Test Coverage Goals

| Module | Target | Current |
|--------|--------|---------|
| `app/ai/manager.py` | 90% | ~85% |
| `app/ai/providers/base.py` | 80% | ~75% |
| `app/ai/providers/gemini.py` | 80% | ~70% |
| `app/ai/providers/grok.py` | 80% | ~70% |
| `app/ai/safety.py` | 95% | ~90% |
| `app/ai/validation.py` | 95% | ~90% |
| `app/ai/schemas.py` | 90% | ~85% |
| `app/ai/prompts.py` | 70% | ~60% |

## Test Documentation

### Adding New Tests

1. Identify test category (provider, schema, safety, security, persistence, cost)
2. Add to appropriate `Test*` class in `test_ai.py`
3. Use descriptive names: `test_<what>_<expected_behavior>`
4. Include docstring explaining the security property tested
5. Use fixtures for common setup
6. Mock external dependencies (providers, database)

### Test Naming Convention

```
test_<component>_<scenario>_<expected_result>

Examples:
test_gemini_provider_missing_key_returns_unavailable
test_validate_finding_analysis_fake_evidence_id_rejected
test_ai_manager_cross_workspace_request_denied
test_redact_secrets_aws_keys_detected_and_redacted
```

## Troubleshooting

### Tests Hang

- Check for missing `await` on async mocks
- Verify `asyncio_mode = auto` in pytest config
- Ensure no infinite retry loops in code

### Provider Import Errors

```bash
# Install required packages
pip install google-generativeai httpx
```

### Database Connection Errors

- Tests use `AsyncMock`, not real database
- Ensure all repository methods are mocked
- Check `patch` targets match import paths

## Continuous Improvement

1. **Add tests for new attack vectors** as discovered
2. **Expand schema validation tests** for edge cases
3. **Add property-based tests** for sanitization functions
4. **Include mutation testing** for critical security functions
5. **Regular live provider tests** in staging environment
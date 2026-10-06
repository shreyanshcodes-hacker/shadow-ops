# AI Provider Configuration

## Overview

ShadowOps supports multiple AI providers through a unified abstraction layer. Configuration is entirely backend-only; no API keys or provider details reach the frontend.

## Supported Providers

| Provider | Models | Configuration |
|----------|--------|---------------|
| **Gemini** (Google) | `gemini-1.5-pro`, `gemini-1.5-flash` | `GEMINI_API_KEY` |
| **Grok** (xAI) | `grok-1` | `GROK_API_KEY` |

## Environment Variables

### Required (At least one provider)
```bash
# Gemini (recommended default)
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-1.5-flash  # or gemini-1.5-pro

# Grok (alternative)
GROK_API_KEY=your-grok-api-key
GROK_MODEL=grok-1
```

### Provider Selection
```bash
# Active provider (gemini or grok)
AI_PROVIDER=gemini
```

### Model Configuration
```bash
# Token limits
AI_MAX_INPUT_CHARS=50000        # Max characters sent to model
AI_MAX_OUTPUT_TOKENS=4096       # Max tokens in response
AI_TIMEOUT_SECONDS=60           # Request timeout

# Retry behavior
AI_MAX_RETRIES=3                # Max retries for transient failures

# Cost control
AI_DAILY_ANALYSIS_LIMIT=100     # Max analyses per workspace per day

# Prompt versioning (MUST change when prompt logic changes)
AI_PROMPT_VERSION=security-finding-analysis-v1
```

### Complete Example
```bash
# .env file
ENVIRONMENT=production
AI_PROVIDER=gemini
GEMINI_API_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GEMINI_MODEL=gemini-1.5-flash
GROK_API_KEY=xai-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
GROK_MODEL=grok-1
AI_MAX_INPUT_CHARS=50000
AI_MAX_OUTPUT_TOKENS=4096
AI_TIMEOUT_SECONDS=60
AI_MAX_RETRIES=3
AI_DAILY_ANALYSIS_LIMIT=100
AI_PROMPT_VERSION=security-finding-analysis-v1
```

## Provider Initialization

### Startup Sequence
```python
# app/ai/providers/__init__.py
def initialize_providers():
    gemini = GeminiProvider()  # Reads GEMINI_API_KEY from settings
    ai_provider_registry.register(gemini)
    
    grok = GrokProvider()      # Reads GROK_API_KEY from settings
    ai_provider_registry.register(grok)

# Called on module import
initialize_providers()

# Active provider resolution
def get_active_provider() -> AIProvider:
    provider_type = AIProviderType(settings.AI_PROVIDER.lower())
    provider = ai_provider_registry.get(provider_type)
    
    if not provider:
        # Fallback to any available provider
        for p in ai_provider_registry._providers.values():
            return p
        raise ValueError("No AI providers available")
    
    return provider
```

### Health Checks
```python
# Each provider implements health_check()
async def health_check(self) -> bool:
    # Gemini: Generate "Health check" with max_output_tokens=10
    # Grok: POST /chat/completions with max_tokens=10
    
# Startup verification
results = await ai_provider_registry.health_check_all()
# Returns: {"gemini": True, "grok": False}
```

## Frontend Status API

Frontend can check provider configuration **without secrets**:

```bash
GET /api/v1/ai/providers/status
```

Response:
```json
[
  {
    "provider": "gemini",
    "configured": true,
    "model": "gemini-1.5-flash"
  },
  {
    "provider": "grok",
    "configured": false,
    "model": null
  }
]
```

## Cost Estimation

Each provider implements `estimate_cost()`:

```python
# Gemini pricing (per 1M tokens)
GEMINI_PRO:     input=$3.50,  output=$10.50
GEMINI_FLASH:   input=$0.075, output=$0.30

# Grok pricing (per 1M tokens)
GROK:           input=$5.00,  output=$15.00
```

Cost tracked in `ai_runs` table:
```sql
input_tokens    INT
output_tokens   INT
estimated_cost_usd  FLOAT
```

## Error Handling

### Provider Error Types
```python
class AIProviderError(Exception):
    def __init__(self, message: str, error_code: str, retryable: bool)

AIProviderAuthError      # Invalid API key, permissions (retryable=False)
AIProviderRateLimitError # 429, quota exceeded (retryable=True)
AIProviderTimeoutError   # Request timeout (retryable=True)
AIProviderServerError    # 5xx from provider (retryable=True)
AIProviderValidationError # Schema validation failed (retryable=False)
```

### Retry Logic
```python
async def _call_provider_with_retries(self, prompt, evidence_ids) -> SecurityAnalysis:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await self.provider.generate_structured(...)
            if response.success:
                return response.data
            # Non-retryable validation errors
            if "validation" in str(response.errors).lower():
                raise AIManagerError("AI output validation failed", "AI_VALIDATION_ERROR")
            raise AIProviderError("Provider error", "AI_PROVIDER_ERROR")
        except AIProviderAuthError:
            raise  # Never retry auth errors
        except AIProviderError as e:
            if not e.retryable or attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)  # Exponential backoff
```

## Switching Providers

### Runtime (requires restart)
```bash
# Change in .env and restart backend
AI_PROVIDER=grok
GROK_API_KEY=...
```

### Per-Request (future enhancement)
```python
# Not currently supported; would require API changes
# POST /ai/analyze?provider=grok
```

## Monitoring & Observability

### Logged Metrics (per analysis)
- Provider + model
- Request/response latency (ms)
- Input/output tokens
- Estimated cost (USD)
- Success/failure status
- Error code (if failed)

### Audit Events
- `ai.analysis.completed` - Includes provider, model, confidence, cost
- `ai.analysis.failed` - Includes error_code, error_message (no secrets)

### Cost Alerts (Recommended)
```bash
# Monitor daily cost per workspace
# Alert if > $10/day or > $100/month
```

## Security

### API Key Protection
- Keys only in backend `.env` / Railway variables
- Never logged (except masked: `AIzaSy****`)
- Never sent to frontend
- Rotated via Railway dashboard

### Network
- Backend → Provider APIs only (HTTPS)
- No inbound connections to AI providers
- Timeout prevents hanging connections

## Troubleshooting

### Provider Not Configured
```
Error: "AI provider not configured" (503)
Fix: Set GEMINI_API_KEY or GROK_API_KEY in environment
```

### Authentication Failed
```
Error: "AI provider authentication failed" (503)
Fix: Verify API key is valid and has correct permissions
```

### Rate Limited
```
Error: "AI rate limit exceeded" (429)
Fix: Wait and retry; consider upgrading provider plan
```

### Timeout
```
Error: "AI request timed out" (504)
Fix: Increase AI_TIMEOUT_SECONDS; reduce input size
```

### Schema Validation Failed
```
Error: "AI output validation failed" (500)
Fix: Check prompt version matches schema; may need prompt update
```

## Migration Guide

### Adding a New Provider
1. Create `app/ai/providers/newprovider.py` implementing `AIProvider`
2. Add to `AIProviderType` enum in `base.py`
3. Register in `providers/__init__.py`
4. Add config vars to `core/config.py`
5. Add pricing to `estimate_cost()`
6. Update `health_check()` implementation

### Updating Prompt Version
1. Modify `SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT` or template
2. **Increment version**: `AI_PROMPT_VERSION=security-finding-analysis-v2`
3. Deploy - old analyses remain queryable with their version
4. New analyses use new prompt version
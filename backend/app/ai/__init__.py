from app.ai.providers import (
    AIProvider,
    AIProviderType,
    AIModel,
    AIResponse,
    AIResponseMetadata,
    AIProviderError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderServerError,
    AIProviderValidationError,
    AIProviderRegistry,
    ai_provider_registry,
    get_ai_provider,
    get_ai_provider_for_model,
    get_active_provider,
    is_provider_available,
    initialize_providers,
)

# Lazy imports for provider classes
def _get_gemini_provider():
    from app.ai.providers.gemini import GeminiProvider
    return GeminiProvider

def _get_grok_provider():
    from app.ai.providers.grok import GrokProvider
    return GrokProvider

# Only import base classes and functions, not the concrete provider classes
# This avoids config validation at import time
GeminiProvider = None  # type: ignore
GrokProvider = None  # type: ignore

from app.ai.manager import AIManager, AIManagerError
from app.ai.schemas import (
    SecurityAnalysis as FindingAnalysis,
    ScanAnalysis,
    EvidenceCertainty,
    SupportingEvidenceRef,
)
from app.ai.prompts import (
    SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT as FINDING_ANALYSIS_SYSTEM_PROMPT,
    SECURITY_FINDING_ANALYSIS_USER_PROMPT_TEMPLATE as FINDING_ANALYSIS_USER_PROMPT_TEMPLATE,
    SCAN_ANALYSIS_SYSTEM_PROMPT,
    SCAN_ANALYSIS_USER_PROMPT_TEMPLATE,
    build_finding_analysis_prompt,
    build_scan_analysis_prompt,
)
from app.ai.validation import (
    validate_security_analysis as validate_finding_analysis,
    validate_scan_analysis,
    sanitize_analysis_output,
    AIValidationError,
)
from app.ai.safety import (
    redact_secrets,
    sanitize_for_ai,
    sanitize_evidence_dict,
    build_safe_prompt,
    validate_ai_output_references,
    is_provider_configured,
    RedactionResult,
    TRUSTED_SYSTEM_START,
    TRUSTED_SYSTEM_END,
    UNTRUSTED_EVIDENCE_START,
    UNTRUSTED_EVIDENCE_END,
)
from app.ai.team_schemas import (
    AgentName, AgentStatus, SecurityTeamRunStatus,
    AgentRequest, AgentResponse, EvidenceReference,
    ReconAgentOutput, ReconAgentResponse,
    VulnerabilityAnalystOutput, VulnerabilityAnalystResponse,
    AttackPathAnalystOutput, AttackPathAnalystResponse,
    RiskAnalystOutput, RiskAnalystResponse,
    SecurityReviewerOutput, SecurityReviewerResponse,
    TeamAssessment,
    SecurityTeamRunRequest, SecurityTeamRunResponse,
    AgentRunResponse, TeamAssessmentResponse, TeamReviewResponse,
)

__all__ = [
    # Providers
    "AIProvider",
    "AIProviderType",
    "AIModel",
    "AIResponse",
    "AIResponseMetadata",
    "AIProviderError",
    "AIProviderAuthError",
    "AIProviderRateLimitError",
    "AIProviderTimeoutError",
    "AIProviderServerError",
    "AIProviderValidationError",
    "AIProviderRegistry",
    "ai_provider_registry",
    "get_ai_provider",
    "get_ai_provider_for_model",
    "get_active_provider",
    "is_provider_available",
    "initialize_providers",
    # Manager
    "AIManager",
    "AIManagerError",
    # Schemas
    "FindingAnalysis",
    "ScanAnalysis",
    "FindingClassification",
    "EvidenceCertainty",
    "SupportingEvidenceRef",
    # Prompts
    "FINDING_ANALYSIS_SYSTEM_PROMPT",
    "FINDING_ANALYSIS_USER_PROMPT_TEMPLATE",
    "SCAN_ANALYSIS_SYSTEM_PROMPT",
    "SCAN_ANALYSIS_USER_PROMPT_TEMPLATE",
    "build_finding_analysis_prompt",
    "build_scan_analysis_prompt",
    # Validation
    "validate_finding_analysis",
    "validate_scan_analysis",
    "sanitize_analysis_output",
    "AIValidationError",
    # Safety
    "redact_secrets",
    "sanitize_for_ai",
    "sanitize_evidence_dict",
    "build_safe_prompt",
    "validate_ai_output_references",
    "is_provider_configured",
    "RedactionResult",
    "TRUSTED_SYSTEM_START",
    "TRUSTED_SYSTEM_END",
    "UNTRUSTED_EVIDENCE_START",
    "UNTRUSTED_EVIDENCE_END",
    # Team Schemas
    "AgentName",
    "AgentStatus",
    "SecurityTeamRunStatus",
    "AgentRequest",
    "AgentResponse",
    "EvidenceReference",
    "ReconAgentOutput",
    "ReconAgentResponse",
    "VulnerabilityAnalystOutput",
    "VulnerabilityAnalystResponse",
    "AttackPathAnalystOutput",
    "AttackPathAnalystResponse",
    "RiskAnalystOutput",
    "RiskAnalystResponse",
    "SecurityReviewerOutput",
    "SecurityReviewerResponse",
    "TeamAssessment",
    "SecurityTeamRunRequest",
    "SecurityTeamRunResponse",
    "AgentRunResponse",
    "TeamAssessmentResponse",
    "TeamReviewResponse",
]

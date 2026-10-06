from typing import Optional, Type, TypeVar
from unittest.mock import AsyncMock

from app.ai.providers.base import (
    AIProvider,
    AIProviderType,
    AIModel,
    AIResponse,
    AIResponseMetadata,
    AIProviderError,
    AIProviderAuthError,
)

from app.ai.schemas import SecurityAnalysis, ScanAnalysis

OutputT = TypeVar("OutputT")


class FakeAIProvider(AIProvider):
    """
    Deterministic AI provider for testing only.
    
    NEVER enable in production. Returns predictable structured responses
    for unit testing the AI analysis pipeline.
    """
    
    def __init__(self, should_fail: bool = False, fail_with: Optional[Exception] = None):
        self._configured = True
        self._should_fail = should_fail
        self._fail_with = fail_with
        self.call_count = 0
        self.last_prompt = None
        self.last_schema = None
        
    @property
    def provider_type(self) -> AIProviderType:
        return AIProviderType.GEMINI
    
    @property
    def default_model(self) -> AIModel:
        return AIModel.GEMINI_FLASH
    
    def _create_mock_security_analysis(self) -> SecurityAnalysis:
        return SecurityAnalysis(
            summary="Mock SQL injection vulnerability detected in user authentication module.",
            vulnerability_type="injection",
            severity_assessment="high",
            confidence=0.85,
            exploitability_assessment="medium",
            impact_assessment="An attacker could potentially execute arbitrary SQL commands, leading to data theft, modification, or deletion. The vulnerability affects user authentication and could compromise all user accounts.",
            affected_component="app/auth/login.py",
            attack_preconditions="Attacker must be able to send crafted input to the login endpoint. No authentication required.",
            evidence_interpretation="OBSERVED: Semgrep detected string concatenation in SQL query at line 42. INFERRED: User-controlled input from request.form reaches the query without parameterization. UNCERTAIN: Cannot confirm if input validation exists upstream without broader codebase context.",
            reasoning="The scanner identified a pattern where user input is directly concatenated into a SQL query string. This pattern is a classic SQL injection vector. The evidence shows the vulnerable code pattern but does not show the full request handling flow.",
            recommended_next_steps=[
                "Verify if input validation/sanitization exists upstream",
                "Replace string concatenation with parameterized queries",
                "Add integration test for SQL injection attempt",
                "Review similar patterns in other database queries"
            ],
            uncertainty="Full request flow not visible in evidence. Cannot confirm if WAF or input validation mitigates the issue.",
            supporting_evidence=[]
        )
    
    def _create_mock_scan_analysis(self) -> ScanAnalysis:
        return ScanAnalysis(
            executive_summary="Mock scan analysis: 3 critical findings including SQL injection and XSS vulnerabilities.",
            key_findings=[self._create_mock_security_analysis()],
            overall_risk_assessment="High risk due to multiple injection vulnerabilities in authentication module.",
            recommended_priorities=[
                "Fix SQL injection in login endpoint",
                "Add input validation middleware",
                "Implement parameterized queries across codebase"
            ],
            confidence=0.8
        )
    
    async def generate_structured(
        self,
        prompt: str,
        output_schema: Type[OutputT],
        model: Optional[AIModel] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> AIResponse[OutputT]:
        self.call_count += 1
        self.last_prompt = prompt
        self.last_schema = output_schema
        
        if self._should_fail:
            if self._fail_with:
                raise self._fail_with
            raise AIProviderError("Fake provider configured to fail", "FAKE_ERROR")
        
        # Determine which mock to return based on schema
        if output_schema == SecurityAnalysis:
            mock_data = self._create_mock_security_analysis()
        elif output_schema == ScanAnalysis:
            mock_data = self._create_mock_scan_analysis()
        else:
            mock_data = output_schema()
        
        return AIResponse(
            success=True,
            data=mock_data,
            metadata=AIResponseMetadata(
                model=model or self.default_model,
                tokens_input=100,
                tokens_output=200,
                latency_ms=50,
                confidence=0.8,
                cost_usd=0.001,
            ),
            errors=[]
        )
    
    async def generate_text(
        self,
        prompt: str,
        model: Optional[AIModel] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        self.call_count += 1
        return "Mock AI response"
    
    async def health_check(self) -> bool:
        return self._configured and not self._should_fail
    
    def estimate_cost(self, model: AIModel, input_tokens: int, output_tokens: int) -> float:
        return 0.001


def get_fake_provider(should_fail: bool = False, fail_with: Optional[Exception] = None) -> FakeAIProvider:
    """Get a fake AI provider for testing. NEVER use in production."""
    return FakeAIProvider(should_fail=should_fail, fail_with=fail_with)
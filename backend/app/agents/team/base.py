import json
import logging
from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Dict, Any, List, Set
from pydantic import BaseModel, ValidationError
from uuid import UUID
from datetime import datetime

from app.ai.providers import AIProvider, AIModel, AIResponse, AIResponseMetadata
from app.ai.safety import (
    TRUSTED_SYSTEM_START,
    TRUSTED_SYSTEM_END,
    UNTRUSTED_EVIDENCE_START,
    UNTRUSTED_EVIDENCE_END,
    build_safe_prompt,
    validate_ai_output_references,
    sanitize_for_ai,
)
from app.ai.team_schemas import (
    AgentName, AgentStatus, AgentRequest, AgentResponse, EvidenceReference,
    ReconAgentOutput, ReconAgentResponse,
    VulnerabilityAnalystOutput, VulnerabilityAnalystResponse,
    AttackPathAnalystOutput, AttackPathAnalystResponse,
    RiskAnalystOutput, RiskAnalystResponse,
    SecurityReviewerOutput, SecurityReviewerResponse,
)

logger = logging.getLogger(__name__)


InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class TeamAgentContext(BaseModel):
    """Context passed to team agents."""
    team_run_id: UUID
    workspace_id: UUID
    asset_id: UUID
    scan_id: UUID
    user_id: UUID
    db: Any = None
    event_emitter: Any = None
    cost_tracker: Any = None
    logger: Any = None
    provided_evidence_ids: Set[str] = set()
    provided_finding_ids: Set[str] = set()
    provided_attack_path_ids: Set[str] = set()


class TeamBaseAgent(ABC, Generic[InputT, OutputT]):
    """Base class for all Security Team agents."""

    name: AgentName
    description: str
    model: AIModel
    input_schema: type[InputT]
    output_schema: type[OutputT]
    response_schema: type[AgentResponse]
    max_retries: int = 2
    timeout_seconds: int = 300
    cost_cap_usd: float = 5.0
    prompt_version: str

    def __init__(self, provider: AIProvider):
        self.provider = provider

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt with injection defenses."""
        pass

    @abstractmethod
    async def build_prompt(self, input: InputT, context: TeamAgentContext) -> str:
        """Build the user prompt with untrusted evidence."""
        pass

    @abstractmethod
    def validate_output_references(self, output: OutputT, context: TeamAgentContext) -> tuple[bool, List[str]]:
        """Validate that output references only provided evidence/finding/path IDs."""
        pass

    def validate_input(self, data: Dict[str, Any]) -> InputT:
        return self.input_schema(**data)

    def validate_output(self, data: Dict[str, Any]) -> OutputT:
        return self.output_schema(**data)

    async def execute(self, input: InputT, context: TeamAgentContext) -> AIResponse[OutputT]:
        """Execute the agent with prompt injection defenses."""
        # Build prompt with safety delimiters
        prompt = await self.build_prompt(input, context)
        
        # Call provider
        response = await self.provider.generate_structured(
            prompt=prompt,
            output_schema=self.output_schema,
            model=self.model,
            temperature=0.1,
            system_prompt=self.system_prompt,
        )
        
        if not response.success:
            return response
        
        # Validate output references
        is_valid, errors = self.validate_output_references(response.data, context)
        if not is_valid:
            return AIResponse(
                success=False,
                data=None,
                metadata=AIResponseMetadata(
                    model=self.model,
                    tokens_input=0,
                    tokens_output=0,
                    latency_ms=0,
                    confidence=0.0,
                ),
                errors=[f"Reference validation failed: {e}" for e in errors],
            )
        
        return response

    async def run_with_retry(
        self,
        input: InputT,
        context: TeamAgentContext,
    ) -> AgentResponse:
        """Run agent with retry logic and produce standardized response."""
        start_time = datetime.utcnow()
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                response = await self.execute(input, context)
                if response.success:
                    duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                    
                    # Build standardized response
                    agent_response = self._build_agent_response(
                        response.data, duration_ms, context
                    )
                    return agent_response
                
                last_error = "; ".join(response.errors) if response.errors else "Unknown error"
                logger.warning(f"Agent {self.name} attempt {attempt + 1} failed: {last_error}")
                
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Agent {self.name} attempt {attempt + 1} error: {e}")
            
            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(2 ** attempt)
        
        # All retries failed
        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        return self._build_error_response(last_error or "Max retries exceeded", duration_ms, context)

    def _build_agent_response(self, output: OutputT, duration_ms: int, context: TeamAgentContext) -> AgentResponse:
        """Build standardized agent response from successful output."""
        # This will be overridden by subclasses to provide agent-specific response
        raise NotImplementedError

    def _build_error_response(self, error: str, duration_ms: int, context: TeamAgentContext) -> AgentResponse:
        """Build standardized error response."""
        # This will be overridden by subclasses
        raise NotImplementedError


def validate_agent_output_schema(output: Dict[str, Any], schema_class: type[BaseModel]) -> tuple[bool, List[str], Optional[BaseModel]]:
    """Validate agent output against schema."""
    try:
        validated = schema_class(**output)
        return True, [], validated
    except ValidationError as e:
        errors = []
        for err in e.errors():
            loc = ".".join(str(x) for x in err["loc"])
            errors.append(f"{loc}: {err['msg']}")
        return False, errors, None
    except Exception as e:
        return False, [str(e)], None


def extract_evidence_ids_from_context(context: TeamAgentContext) -> Set[str]:
    """Extract all evidence IDs available in context."""
    return context.provided_evidence_ids.copy()


def extract_finding_ids_from_context(context: TeamAgentContext) -> Set[str]:
    """Extract all finding IDs available in context."""
    return context.provided_finding_ids.copy()


def extract_attack_path_ids_from_context(context: TeamAgentContext) -> Set[str]:
    """Extract all attack path IDs available in context."""
    return context.provided_attack_path_ids.copy()

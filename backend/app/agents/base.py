from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Optional, Dict, Any, List
from pydantic import BaseModel, Field
from uuid import UUID
from datetime import datetime
from enum import Enum

from app.schemas import BaseSchema
from app.ai.providers import AIProvider, AIModel, AIResponse, AIResponseMetadata


# Type variables
InputT = TypeVar("InputT", bound=BaseSchema)
OutputT = TypeVar("OutputT", bound=BaseSchema)


class AgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class AgentRun(BaseSchema):
    id: UUID
    scan_id: UUID
    workspace_id: UUID
    agent_name: str
    model_used: Optional[AIModel] = None
    status: AgentStatus = AgentStatus.QUEUED
    input_summary: Optional[Dict[str, Any]] = None
    output_summary: Optional[Dict[str, Any]] = None
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime


class AgentContext(BaseSchema):
    scan_id: UUID
    workspace_id: UUID
    asset_id: Optional[UUID] = None
    user_id: UUID
    secrets: Dict[str, str] = Field(default_factory=dict)
    db: Any = None
    event_emitter: Any = None
    cost_tracker: Any = None
    logger: Any = None


class BaseAgent(ABC, Generic[InputT, OutputT]):
    """Base class for all security agents."""

    name: str
    description: str
    model: AIModel
    input_schema: type[InputT]
    output_schema: type[OutputT]
    max_retries: int = 2
    timeout_seconds: int = 300
    cost_cap_usd: float = 5.0

    def __init__(self, provider: AIProvider):
        self.provider = provider

    @abstractmethod
    async def execute(self, input: InputT, context: AgentContext) -> AIResponse[OutputT]:
        pass

    def validate_input(self, data: Dict[str, Any]) -> InputT:
        return self.input_schema(**data)

    def validate_output(self, data: Dict[str, Any]) -> OutputT:
        return self.output_schema(**data)

    async def run_with_retry(
        self,
        input: InputT,
        context: AgentContext,
    ) -> AIResponse[OutputT]:
        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                result = await self.execute(input, context)
                if result.success:
                    return result
                last_error = "; ".join(result.errors) if result.errors else "Unknown error"
            except Exception as e:
                last_error = str(e)

            if attempt < self.max_retries:
                import asyncio
                await asyncio.sleep(2 ** attempt)

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
            errors=[last_error or "Max retries exceeded"],
        )


class AgentRegistry:
    """Registry for managing security agents."""

    def __init__(self):
        self._agents: Dict[str, type[BaseAgent]] = {}

    def register(self, agent_class: type[BaseAgent]) -> None:
        self._agents[agent_class.name] = agent_class

    def get(self, name: str) -> Optional[type[BaseAgent]]:
        return self._agents.get(name)

    def all(self) -> Dict[str, type[BaseAgent]]:
        return self._agents.copy()


# Global agent registry
agent_registry = AgentRegistry()


def get_agent_class(name: str) -> type[BaseAgent]:
    agent = agent_registry.get(name)
    if not agent:
        raise ValueError(f"Agent {name} not registered")
    return agent
# Agent Architecture

## Agent Design Principles

1. **Single Responsibility** - Each agent has one clearly defined purpose
2. **Typed Contracts** - All agents share common request/response schemas
3. **Traceability** - Every agent output includes confidence, evidence references, prompt version
4. **No Autonomous Actions** - Agents are analytical workers only
5. **Deterministic Dependencies** - Execution order is fixed and explicit

## Agent Registry

```python
class TeamAgentRegistry:
    def register(agent_class: Type[TeamBaseAgent]) -> None
    def get_class(name: AgentName) -> Optional[Type[TeamBaseAgent]]
    def get_instance(name: AgentName, provider: AIProvider) -> TeamBaseAgent
    def all_names() -> List[AgentName]
    def execution_order() -> List[AgentName]
    def dependencies() -> Dict[AgentName, List[AgentName]]
    def can_run_parallel(agent_a, agent_b) -> bool
```

## Base Agent Class

```python
class TeamBaseAgent(ABC, Generic[InputT, OutputT]):
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
    
    @property
    @abstractmethod
    def system_prompt(self) -> str
    
    @abstractmethod
    async def build_prompt(self, input: InputT, context: TeamAgentContext) -> str
    
    @abstractmethod
    def validate_output_references(self, output: OutputT, context: TeamAgentContext) -> tuple[bool, List[str]]
    
    async def execute(self, input: InputT, context: TeamAgentContext) -> AIResponse[OutputT]
    async def run_with_retry(self, input: InputT, context: TeamAgentContext) -> AgentResponse
```

## Context Builders

Each agent has a dedicated context builder providing minimal relevant data:

```python
class ReconContextBuilder:
    async def build(team_run_id, workspace_id, asset_id, scan_id, user_id) -> TeamAgentContext

class VulnerabilityContextBuilder:
    async def build(...) -> TeamAgentContext

class AttackPathContextBuilder:
    async def build(...) -> TeamAgentContext

class RiskContextBuilder:
    async def build(...) -> TeamAgentContext

class ReviewerContextBuilder:
    async def build(...) -> TeamAgentContext
```

## Evidence Reference Validation

All agents must reference only provided evidence IDs:

```python
def validate_ai_output_references(supporting_evidence, provided_evidence_ids) -> tuple[bool, List[str]]
```

If an agent references an unknown evidence ID, output is marked invalid.

## Agent Disagreement Handling

- Agents may disagree (different confidence levels on same finding)
- Security Reviewer preserves disagreements in `conflicting_assessments`
- No forced artificial consensus
- Uncertainty explicitly documented

## Output Validation

Every agent output validated against:
- Required fields
- Types
- Confidence bounds (0.0-1.0)
- Allowed enums
- Maximum lengths
- Evidence references exist in provided context

Invalid outputs are rejected; agent marked FAILED.

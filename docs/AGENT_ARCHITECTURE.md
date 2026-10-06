# AGENT ARCHITECTURE

## Overview

The Agent System is a **structured workflow orchestration layer** built in Python. It is not an autonomous agent framework (no ReAct, no tool-use loops). Each agent is a **deterministic function** with defined inputs, outputs, and side effects.

```
┌─────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR (Celery)                        │
│  - Workflow DAG definition                                      │
│  - Task dispatch & monitoring                                   │
│  - Retry / compensation logic                                   │
│  - State persistence (agent_runs table)                         │
└─────────────────────────────────────────────────────────────────┘
                                      │
        ┌─────────────────────────────┼─────────────────────────────┐
        ▼                             ▼                             ▼
┌───────────────────┐       ┌───────────────────┐       ┌───────────────────┐
│   AGENT RUNNER    │       │   AGENT RUNNER    │       │   AGENT RUNNER    │
│   (Process Pool)  │       │   (Process Pool)  │       │   (Process Pool)  │
│                   │       │                   │       │                   │
│ • Input Validation│       │ • Input Validation│       │ • Input Validation│
│ • Model Call      │       │ • Model Call      │       │ • Model Call      │
│ • Output Validate │       │ • Output Validate │       │ • Output Validate │
│ • Evidence Store  │       │ • Evidence Store  │       │ • Evidence Store  │
│ • Cost Tracking   │       │ • Cost Tracking   │       │ • Cost Tracking   │
└───────────────────┘       └───────────────────┘       └───────────────────┘
```

---

## Agent Interface Contract

Every agent implements this interface:

```python
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Generic, TypeVar
from dataclasses import dataclass

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)

class AgentMetadata(BaseModel):
    model: str
    tokens_input: int
    tokens_output: int
    latency_ms: int
    confidence: float  # 0.0 - 1.0
    cost_usd: float

class AgentResult(BaseModel, Generic[OutputT]):
    success: bool
    data: OutputT | None = None
    metadata: AgentMetadata
    errors: list[str] = []

class BaseAgent(ABC, Generic[InputT, OutputT]):
    name: str
    model: str
    input_schema: type[InputT]
    output_schema: type[OutputT]
    max_retries: int = 2
    timeout_seconds: int = 300
    cost_cap_usd: float = 5.0
    
    @abstractmethod
    async def execute(self, input: InputT, context: AgentContext) -> AgentResult[OutputT]:
        pass
    
    def validate_input(self, data: dict) -> InputT:
        return self.input_schema(**data)
    
    def validate_output(self, data: dict) -> OutputT:
        return self.output_schema(**data)
```

---

## Agent Context

```python
@dataclass
class AgentContext:
    scan_id: UUID
    workspace_id: UUID
    asset_id: UUID
    user_id: UUID  # Who triggered
    secrets: SecretResolver  # Access to credentials (never logged)
    storage: EvidenceStorage  # Write evidence to Supabase Storage
    db: DatabaseSession  # Read/write workspace data
    event_emitter: ScanEventEmitter  # Emit realtime events
    cost_tracker: CostTracker  # Track per-agent costs
    logger: StructuredLogger
```

---

## Agent Registry

```python
AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "recon": ReconAgent,
    "code_security": CodeSecurityAgent,
    "dependency": DependencyAgent,
    "threat_analyst": ThreatAnalystAgent,
    "risk_analyst": RiskAnalystAgent,
    "remediation": RemediationAgent,
    "verification": VerificationAgent,
    "reporting": ReportingAgent,
}
```

---

## Workflow Definition (DAG)

```python
from enum import Enum

class ScanPhase(str, Enum):
    RECON = "recon"
    CODE_ANALYSIS = "code_analysis"
    DEPENDENCY_ANALYSIS = "dependency_analysis"
    FINDING_NORMALIZATION = "finding_normalization"
    THREAT_ANALYSIS = "threat_analysis"
    RISK_ANALYSIS = "risk_analysis"
    ATTACK_PATH_CONSTRUCTION = "attack_path_construction"
    REMEDIATION_GENERATION = "remediation_generation"
    REPORT_GENERATION = "report_generation"

SCAN_WORKFLOW = {
    ScanPhase.RECON: {
        "agent": "recon",
        "depends_on": [],
        "parallel_group": "initial",
    },
    ScanPhase.CODE_ANALYSIS: {
        "agent": "code_security",
        "depends_on": [ScanPhase.FINDING_NORMALIZATION],
        "parallel_group": "analysis",
    },
    ScanPhase.DEPENDENCY_ANALYSIS: {
        "agent": "dependency",
        "depends_on": [ScanPhase.FINDING_NORMALIZATION],
        "parallel_group": "analysis",
    },
    ScanPhase.FINDING_NORMALIZATION: {
        "agent": "normalizer",  # Not an AI agent - deterministic
        "depends_on": [ScanPhase.RECON],
    },
    ScanPhase.THREAT_ANALYSIS: {
        "agent": "threat_analyst",
        "depends_on": [ScanPhase.CODE_ANALYSIS, ScanPhase.DEPENDENCY_ANALYSIS],
    },
    ScanPhase.RISK_ANALYSIS: {
        "agent": "risk_analyst",
        "depends_on": [ScanPhase.THREAT_ANALYSIS],
    },
    ScanPhase.ATTACK_PATH_CONSTRUCTION: {
        "agent": "attack_path_builder",  # Hybrid: deterministic + AI
        "depends_on": [ScanPhase.RISK_ANALYSIS],
    },
    ScanPhase.REMEDIATION_GENERATION: {
        "agent": "remediation",
        "depends_on": [ScanPhase.RISK_ANALYSIS],
    },
    ScanPhase.REPORT_GENERATION: {
        "agent": "reporting",
        "depends_on": [
            ScanPhase.ATTACK_PATH_CONSTRUCTION,
            ScanPhase.REMEDIATION_GENERATION,
        ],
    },
}
```

---

## Orchestrator Implementation

```python
class ScanOrchestrator:
    def __init__(self, db: DatabaseSession, celery_app: Celery):
        self.db = db
        self.celery = celery_app
        self.phase_order = self._topological_sort(SCAN_WORKFLOW)
    
    async def execute_scan(self, scan_id: UUID) -> ScanResult:
        scan = await self.db.get_scan(scan_id)
        context = AgentContext.from_scan(scan)
        
        # Initialize scan state
        await self._update_scan_status(scan_id, "running")
        await self._emit_event(scan_id, "scan_started", {})
        
        phase_results: dict[ScanPhase, AgentResult] = {}
        
        for phase in self.phase_order:
            config = SCAN_WORKFLOW[phase]
            
            # Check dependencies
            if not self._deps_met(config["depends_on"], phase_results):
                await self._handle_dependency_failure(scan_id, phase, config["depends_on"])
                break
            
            # Execute phase
            result = await self._execute_phase(scan_id, phase, config, context, phase_results)
            phase_results[phase] = result
            
            # Check for critical failure
            if not result.success and config.get("critical", True):
                await self._handle_critical_failure(scan_id, phase, result)
                break
            
            # Update progress
            await self._update_progress(scan_id, phase)
        
        # Finalize
        final_status = self._determine_final_status(phase_results)
        await self._update_scan_status(scan_id, final_status)
        await self._emit_completion_events(scan_id, phase_results)
        
        return ScanResult(scan_id=scan_id, status=final_status, phases=phase_results)
    
    async def _execute_phase(
        self, 
        scan_id: UUID, 
        phase: ScanPhase, 
        config: dict, 
        context: AgentContext,
        prior_results: dict
    ) -> AgentResult:
        agent_class = AGENT_REGISTRY[config["agent"]]
        agent = agent_class()
        
        # Build input from prior results
        input_data = self._build_input(phase, prior_results, context)
        
        # Create agent run record
        run_id = await self.db.create_agent_run(
            scan_id=scan_id,
            workspace_id=context.workspace_id,
            agent_name=config["agent"],
            status="running",
        )
        
        start_time = time.time()
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                agent.execute(input_data, context),
                timeout=config.get("timeout", agent.timeout_seconds)
            )
            
            # Validate output schema
            if result.success:
                validated = agent.validate_output(result.data.model_dump())
                result.data = validated
            
            # Persist evidence
            await self._persist_evidence(run_id, result, context)
            
            # Update run record
            await self.db.update_agent_run(run_id, {
                "status": "completed" if result.success else "failed",
                "output_summary": result.data.model_dump() if result.success else None,
                "error_message": "; ".join(result.errors) if result.errors else None,
                "tokens_input": result.metadata.tokens_input,
                "tokens_output": result.metadata.tokens_output,
                "cost_usd": result.metadata.cost_usd,
                "completed_at": datetime.utcnow(),
            })
            
            # Emit event for realtime UI
            await self._emit_event(scan_id, f"phase_{phase.value}_complete", {
                "success": result.success,
                "summary": result.data.model_dump() if result.success else None,
            })
            
            return result
            
        except asyncio.TimeoutError:
            await self.db.update_agent_run(run_id, {"status": "timeout"})
            return AgentResult(success=False, errors=[f"Timeout after {agent.timeout_seconds}s"])
        except Exception as e:
            await self.db.update_agent_run(run_id, {"status": "failed", "error_message": str(e)})
            return AgentResult(success=False, errors=[str(e)])
```

---

## State Management

### Scan States

```
QUEUED → RUNNING → COMPLETED
                │
                ├──→ FAILED (critical phase failed)
                │
                ├──→ PARTIAL (non-critical phases failed)
                │
                └──→ CANCELLED (user requested)
```

### Agent Run States

```
PENDING → RUNNING → COMPLETED
                 │
                 ├──→ FAILED
                 │
                 └──→ TIMEOUT
```

### Phase Transition Rules

| From | To | Condition |
|------|-----|-----------|
| QUEUED | RUNNING | Orchestrator starts |
| RUNNING | COMPLETED | All critical phases succeeded |
| RUNNING | PARTIAL | ≥1 non-critical phase failed |
| RUNNING | FAILED | Critical phase failed |
| RUNNING | CANCELLED | User/API cancellation |
| * | CANCELLED | Cancellation signal received |

---

## Cancellation Handling

```python
async def cancel_scan(scan_id: UUID, user_id: UUID) -> bool:
    scan = await db.get_scan(scan_id)
    
    # Authorization check
    if not await user_can_cancel(user_id, scan):
        raise AuthorizationError()
    
    # Mark scan as cancelling
    await db.update_scan(scan_id, {"status": "cancelling"})
    
    # Signal running agents (via Redis pub/sub)
    await redis.publish(f"scan:{scan_id}:cancel", json.dumps({"reason": "user_requested"}))
    
    # Wait for graceful shutdown (max 30s)
    for _ in range(30):
        scan = await db.get_scan(scan_id)
        if scan.status in ("cancelled", "completed", "failed"):
            break
        await asyncio.sleep(1)
    
    # Force terminate if needed
    if scan.status == "cancelling":
        await force_terminate_scan(scan_id)
        await db.update_scan(scan_id, {"status": "cancelled"})
    
    return True
```

**Agent Cooperation**: Agents check `context.cancellation_token.is_cancelled()` at checkpoints (between findings, after each model call).

---

## Evidence Persistence

```python
class EvidenceStorage:
    def __init__(self, supabase: Client, workspace_id: UUID):
        self.supabase = supabase
        self.workspace_id = workspace_id
    
    async def store(self, evidence: FindingEvidenceCreate) -> UUID:
        # 1. Upload content to Supabase Storage
        object_id = await self._upload_to_storage(evidence.content)
        
        # 2. Create finding_evidence record
        record = FindingEvidence(
            workspace_id=self.workspace_id,
            finding_id=evidence.finding_id,
            evidence_type=evidence.type,
            title=evidence.title,
            description=evidence.description,
            content_ref=object_id,
            metadata=evidence.metadata,
        )
        await self.db.insert(record)
        
        return record.id
    
    async def _upload_to_storage(self, content: bytes | str | dict) -> UUID:
        # Serialize to JSON if dict
        # Upload to Supabase Storage bucket: workspace-{id}/evidence/
        # Return storage object ID
        pass
```

**Evidence Types**:
- `code_snippet` — Source code with line numbers
- `screenshot` — PNG/WebP from recon
- `log` — Tool output (Semgrep, nmap, etc.)
- `request_response` — HTTP request/response pairs
- `config` — Configuration files (redacted)
- `dependency_tree` — Package dependency graph
- `ai_reasoning` — Model reasoning trace
- `attack_path_graph` — Serialized graph

---

## Cost Tracking

```python
class CostTracker:
    def __init__(self, workspace_id: UUID, scan_id: UUID, db: DatabaseSession):
        self.workspace_id = workspace_id
        self.scan_id = scan_id
        self.db = db
        self.agent_costs: dict[str, float] = {}
    
    def record(self, agent_name: str, model: str, tokens_in: int, tokens_out: int):
        cost = calculate_cost(model, tokens_in, tokens_out)
        self.agent_costs[agent_name] = self.agent_costs.get(agent_name, 0) + cost
        
        # Check limits
        scan_budget = await self._get_scan_budget()
        total = sum(self.agent_costs.values())
        if total > scan_budget * 0.9:
            logger.warning(f"Scan {self.scan_id} at 90% budget")
        if total > scan_budget:
            raise BudgetExceededError(f"Scan budget ${scan_budget} exceeded")
    
    async def finalize(self):
        await self.db.update_scan(self.scan_id, {
            "cost_breakdown": self.agent_costs,
            "total_cost_usd": sum(self.agent_costs.values()),
        })
```

**Pricing** (estimated, update per provider):
- Gemini 1.5 Pro: $3.50/1M in, $10.50/1M out
- Gemini 1.5 Flash: $0.075/1M in, $0.30/1M out
- Grok: $5.00/1M in, $15.00/1M out

---

## Testing Strategy

### Unit Tests (Per Agent)
- Input validation (valid, invalid, edge cases)
- Output schema compliance
- Mock model responses → verify parsing
- Cost calculation accuracy

### Integration Tests
- Full scan workflow with mocked external services
- Cancellation mid-scan
- Partial failure recovery
- Budget enforcement

### Golden Set Evaluation
- 50+ test cases per agent with expected outputs
- Measure: accuracy, schema compliance, cost, latency
- Regression detection on prompt/model changes

### Chaos Testing
- Model API failures
- Network partitions
- Storage failures
- Concurrent scan limits
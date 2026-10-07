# Agent Orchestration

## Orchestration Flow

```
TEAM RUN CREATED
       ↓
   RECON AGENT
       ↓
VULNERABILITY ANALYST
       ↓
 ATTACK PATH ANALYST
       ↓
   RISK ANALYST
       ↓
 SECURITY REVIEWER
       ↓
  TEAM ASSESSMENT
       ↓
HUMAN REVIEW REQUIRED
```

## SecurityTeamOrchestrator

```python
class SecurityTeamOrchestrator:
    MAX_AGENT_RETRIES = 2
    MAX_TEAM_DURATION_SECONDS = 1800
    AGENT_TIMEOUT_SECONDS = 300
    ORCHESTRATION_VERSION = "security-team-v1"
    
    async def start_team_run(workspace_id, asset_id, scan_id, user_id, analysis_mode)
    async def _run_orchestration(team_run_id, user_id)
    async def _execute_agent(team_run, agent_name, user_id, previous_outputs)
    async def cancel_team_run(team_run_id, user_id)
    async def submit_human_review(team_run_id, workspace_id, reviewer_id, notes)
```

## Idempotency

Prevents duplicate team runs:

```python
# Unique constraint in database
UniqueConstraint("workspace_id", "asset_id", "scan_id", "orchestration_version", 
                 name="uq_security_team_run_active", 
                 postgresql_where=status.in_([QUEUED, RUNNING]))
```

If same workspace+asset+scan+version has active run, returns existing run.

## Dependency Management

```python
dependencies = {
    AgentName.RECON: [],
    AgentName.VULNERABILITY_ANALYST: [AgentName.RECON],
    AgentName.ATTACK_PATH_ANALYST: [AgentName.RECON, AgentName.VULNERABILITY_ANALYST],
    AgentName.RISK_ANALYST: [AgentName.RECON, AgentName.VULNERABILITY_ANALYST, AgentName.ATTACK_PATH_ANALYST],
    AgentName.SECURITY_REVIEWER: [AgentName.RECON, AgentName.VULNERABILITY_ANALYST, AgentName.ATTACK_PATH_ANALYST, AgentName.RISK_ANALYST],
}
```

Agents only execute when all dependencies are SUCCEEDED. Failed dependencies → BLOCKED status.

## Failure Handling

| Scenario | Behavior |
|----------|----------|
| Agent fails | Mark FAILED, log error, audit |
| Dependency fails | Dependent agents marked BLOCKED |
| Some agents fail | If ≥3 succeed → PARTIAL; else FAILED |
| Timeout | Agent marked FAILED with TIMEOUT error |
| Cancellation | Pending agents CANCELED, completed preserved |

## Retry Logic

```python
for attempt in range(max_retries + 1):
    try:
        result = await execute(input, context)
        if result.success:
            return result
    except TransientError:
        if attempt < max_retries:
            await asyncio.sleep(2 ** attempt)
            continue
    except NonRetryableError:
        raise  # Don't retry

return FAILED
```

**Retryable**: Provider errors, timeouts, network issues
**Non-retryable**: Validation errors, auth errors, malformed data, prompt construction failure

## Cancellation

```python
async def cancel_team_run(team_run_id, user_id):
    # Stop scheduling new agents
    # Mark pending agents CANCELED
    # Preserve completed outputs
    # Update team run status to CANCELED
    # Audit log
```

## Audit Logging

Events logged:
- `security_team.started` - Team run created
- `security_team.running` - Orchestration began
- `security_team.succeeded` - All agents completed
- `security_team.partial` - Some agents failed but ≥3 succeeded
- `security_team.failed` - Insufficient agents succeeded
- `security_team.canceled` - User cancelled
- `agent.{name}.started` - Agent execution began
- `agent.{name}.succeeded` - Agent completed successfully
- `agent.{name}.failed` - Agent failed
- `agent.{name}.blocked` - Agent blocked by failed dependency
- `security_team.reviewed` - Human review submitted

## Context Passing

Previous agent outputs passed to downstream agents via `previous_outputs` dict:

```python
agent_outputs = {
    "recon": {...},
    "vulnerability_analyst": {...},
    "attack_path_analyst": {...},
    "risk_analyst": {...},
}
```

Reviewer receives all; earlier agents receive minimal context.

## Team Summary

Aggregated from all agent outputs:

```json
{
  "completed_agents": ["recon", "vulnerability_analyst", ...],
  "failed_agents": ["risk_analyst"],
  "agent_summaries": {
    "recon": "Identified 5 components, 3 entry points...",
    "vulnerability_analyst": "Analyzed 12 findings..."
  }
}
```

## Overall Confidence

Weighted average of completed agent confidences:

```python
confidences = [output.confidence for output in agent_outputs.values() if output.confidence]
overall = sum(confidences) / len(confidences) if confidences else 0.5
```

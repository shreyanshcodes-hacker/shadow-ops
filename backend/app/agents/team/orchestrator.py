import asyncio
import json
import logging
from typing import Dict, Any, List, Optional, Set
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models import (
    SecurityTeamRun, SecurityTeamRunStatus,
    AgentRun, AgentName, AgentRunStatus,
    TeamAssessment, TeamReview,
    Scan, Asset, Finding, FindingAiAnalysis, AttackPath, RiskSnapshot,
)
from app.repositories import (
    SecurityTeamRunRepository, AgentRunRepository, TeamAssessmentRepository, TeamReviewRepository,
    FindingRepository, FindingAiAnalysisRepository, AttackPathRepository, RiskSnapshotRepository,
)
from app.agents.team.registry import team_agent_registry
from app.agents.team.context_builders import (
    ReconContextBuilder, VulnerabilityContextBuilder,
    AttackPathContextBuilder, RiskContextBuilder, ReviewerContextBuilder,
)
from app.ai.providers import get_active_provider
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class OrchestrationError(Exception):
    def __init__(self, message: str, error_code: str = "ORCHESTRATION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


@dataclass
class AgentExecutionResult:
    agent_name: AgentName
    status: AgentRunStatus
    response: Any  # AgentResponse
    error: Optional[str] = None


class SecurityTeamOrchestrator:
    """
    Orchestrates the AI Security Team multi-agent analysis.
    
    Responsibilities:
    1. Create team run
    2. Validate workspace access
    3. Validate target scope
    4. Load approved context
    5. Schedule appropriate agents
    6. Track dependencies
    7. Collect outputs
    8. Validate outputs
    9. Handle failures
    10. Produce final team assessment
    11. Persist run history
    12. Write audit events
    """
    
    # Configuration
    MAX_AGENT_RETRIES = 2
    MAX_TEAM_DURATION_SECONDS = 1800  # 30 minutes
    AGENT_TIMEOUT_SECONDS = 300
    MAX_CONTEXT_SIZE_CHARS = 100000
    ORCHESTRATION_VERSION = "security-team-v1"
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.team_run_repo = SecurityTeamRunRepository(db)
        self.agent_run_repo = AgentRunRepository(db)
        self.assessment_repo = TeamAssessmentRepository(db)
        self.review_repo = TeamReviewRepository(db)
        self.provider = get_active_provider()
        
        # Context builders
        self.recon_builder = ReconContextBuilder(db)
        self.vuln_builder = VulnerabilityContextBuilder(db)
        self.attack_path_builder = AttackPathContextBuilder(db)
        self.risk_builder = RiskContextBuilder(db)
        self.reviewer_builder = ReviewerContextBuilder(db)
        
        # Context builder mapping
        self.context_builders = {
            AgentName.RECON: self.recon_builder,
            AgentName.VULNERABILITY_ANALYST: self.vuln_builder,
            AgentName.ATTACK_PATH_ANALYST: self.attack_path_builder,
            AgentName.RISK_ANALYST: self.risk_builder,
            AgentName.SECURITY_REVIEWER: self.reviewer_builder,
        }
    
    async def start_team_run(
        self,
        workspace_id: UUID,
        asset_id: UUID,
        scan_id: UUID,
        user_id: UUID,
        analysis_mode: str = "standard",
    ) -> SecurityTeamRun:
        """
        Start a new Security Team analysis run.
        
        Implements idempotency: returns existing active run if one exists
        for the same workspace+asset+scan+version.
        """
        # Check for existing active run (idempotency)
        existing = await self.team_run_repo.get_active_by_workspace_asset_scan(
            workspace_id, asset_id, scan_id, self.ORCHESTRATION_VERSION
        )
        if existing:
            logger.info(f"Returning existing active team run {existing.id}")
            return existing
        
        # Verify workspace access and asset/scan ownership
        asset_result = await self.db.execute(select(Asset).where(Asset.id == asset_id, Asset.workspace_id == workspace_id))
        asset = asset_result.scalar_one_or_none()
        if not asset:
            raise OrchestrationError("Asset not found or access denied", "ASSET_NOT_FOUND")
        
        scan_result = await self.db.execute(select(Scan).where(Scan.id == scan_id, Scan.workspace_id == workspace_id))
        scan = scan_result.scalar_one_or_none()
        if not scan:
            raise OrchestrationError("Scan not found or access denied", "SCAN_NOT_FOUND")
        
        if scan.asset_id != asset_id:
            raise OrchestrationError("Scan does not belong to asset", "SCAN_ASSET_MISMATCH")
        
        if scan.status.value not in ["completed", "partial"]:
            raise OrchestrationError("Scan must be completed before team analysis", "SCAN_NOT_COMPLETED")
        
        # Create team run
        team_run = SecurityTeamRun(
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            status=SecurityTeamRunStatus.QUEUED,
            requested_by=user_id,
            orchestration_version=self.ORCHESTRATION_VERSION,
            team_summary={},
        )
        team_run = await self.team_run_repo.create(team_run)
        
        # Create agent run records (all queued)
        for agent_name in team_agent_registry.execution_order():
            agent_run = AgentRun(
                team_run_id=team_run.id,
                agent_name=agent_name,
                status=AgentRunStatus.QUEUED,
                input_reference={},
                output={},
                attempt=0,
            )
            await self.agent_run_repo.create(agent_run)
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="security_team.started",
            resource_type="security_team_run",
            resource_id=team_run.id,
            new_state={
                "asset_id": str(asset_id),
                "scan_id": str(scan_id),
                "orchestration_version": self.ORCHESTRATION_VERSION,
                "requested_by": str(user_id),
            },
            user_id=user_id,
        )
        
        # Start orchestration in background
        asyncio.create_task(self._run_orchestration(team_run.id, user_id))
        
        return team_run
    
    async def _run_orchestration(self, team_run_id: UUID, user_id: UUID) -> None:
        """Main orchestration loop - runs agents in dependency order."""
        try:
            # Update team run status to RUNNING
            await self.team_run_repo.update(team_run_id, {
                "status": SecurityTeamRunStatus.RUNNING,
                "started_at": datetime.utcnow(),
            })
            
            # Get team run
            team_run = await self.team_run_repo.get_by_id(team_run_id)
            if not team_run:
                logger.error(f"Team run {team_run_id} not found")
                return
            
            # Execute agents in dependency order
            execution_order = team_agent_registry.execution_order()
            completed_agents: Set[AgentName] = set()
            failed_agents: Set[AgentName] = set()
            agent_outputs: Dict[str, Any] = {}
            
            for agent_name in execution_order:
                # Check dependencies
                deps = team_agent_registry.dependencies().get(agent_name, [])
                if not all(dep in completed_agents for dep in deps):
                    # Dependencies not met - mark as blocked
                    await self._mark_agent_blocked(team_run_id, agent_name, "Dependencies not met")
                    failed_agents.add(agent_name)
                    continue
                
                # Execute agent
                result = await self._execute_agent(team_run, agent_name, user_id, agent_outputs)
                
                if result.status == AgentRunStatus.SUCCEEDED:
                    completed_agents.add(agent_name)
                    agent_outputs[agent_name.value] = result.response.output if hasattr(result.response, 'output') else result.response.structured_output.model_dump() if hasattr(result.response, 'structured_output') else {}
                else:
                    failed_agents.add(agent_name)
                    logger.warning(f"Agent {agent_name} failed: {result.error}")
                    
                    # Check if this agent is required for downstream agents
                    # Security Reviewer requires all previous agents
                    if agent_name == AgentName.SECURITY_REVIEWER:
                        break
            
            # Determine final status
            if len(failed_agents) == 0:
                final_status = SecurityTeamRunStatus.SUCCEEDED
            elif len(completed_agents) >= 3:  # At least recon, vuln, attack_path
                final_status = SecurityTeamRunStatus.PARTIAL
            else:
                final_status = SecurityTeamRunStatus.FAILED
            
            # Build team summary
            team_summary = self._build_team_summary(agent_outputs, completed_agents, failed_agents)
            
            # Calculate overall confidence
            overall_confidence = self._calculate_overall_confidence(agent_outputs)
            
            # Update team run
            await self.team_run_repo.update(team_run_id, {
                "status": final_status,
                "completed_at": datetime.utcnow(),
                "team_summary": team_summary,
                "confidence": overall_confidence,
            })
            
            # Create assessment if reviewer succeeded
            if AgentName.SECURITY_REVIEWER in completed_agents:
                await self._create_assessment(team_run_id, agent_outputs[AgentName.SECURITY_REVIEWER.value], overall_confidence)
            
            # Audit log completion
            await audit_log(
                db=self.db,
                workspace_id=team_run.workspace_id,
                action=f"security_team.{final_status.value}",
                resource_type="security_team_run",
                resource_id=team_run_id,
                new_state={
                    "status": final_status.value,
                    "completed_agents": [a.value for a in completed_agents],
                    "failed_agents": [a.value for a in failed_agents],
                    "confidence": overall_confidence,
                },
                user_id=user_id,
            )
            
        except Exception as e:
            logger.exception(f"Orchestration failed for team run {team_run_id}: {e}")
            await self.team_run_repo.update(team_run_id, {
                "status": SecurityTeamRunStatus.FAILED,
                "completed_at": datetime.utcnow(),
                "team_summary": {"error": str(e)},
            })
    
    async def _execute_agent(
        self,
        team_run: SecurityTeamRun,
        agent_name: AgentName,
        user_id: UUID,
        previous_outputs: Dict[str, Any],
    ) -> AgentExecutionResult:
        """Execute a single agent with context building and persistence."""
        # Get agent run record
        agent_run = await self.agent_run_repo.get_by_team_run_and_agent(team_run.id, agent_name)
        if not agent_run:
            raise OrchestrationError(f"Agent run record not found for {agent_name}", "AGENT_RUN_NOT_FOUND")
        
        # Update agent run status to RUNNING
        await self.agent_run_repo.update(agent_run.id, {
            "status": AgentRunStatus.RUNNING,
            "started_at": datetime.utcnow(),
        })
        
        # Build context
        context_builder = self.context_builders.get(agent_name)
        if not context_builder:
            raise OrchestrationError(f"No context builder for {agent_name}", "NO_CONTEXT_BUILDER")
        
        context = await context_builder.build(
            team_run_id=team_run.id,
            workspace_id=team_run.workspace_id,
            asset_id=team_run.asset_id,
            scan_id=team_run.scan_id,
            user_id=user_id,
        )
        
        # Add previous agent outputs to context for reviewer
        if agent_name == AgentName.SECURITY_REVIEWER:
            context.context["agent_outputs"] = previous_outputs
        
        # Store input reference for persistence
        input_reference = {
            "finding_ids": list(context.provided_finding_ids),
            "evidence_ids": list(context.provided_evidence_ids),
            "attack_path_ids": list(context.provided_attack_path_ids),
        }
        await self.agent_run_repo.update(agent_run.id, {"input_reference": input_reference})
        
        # Get agent instance
        agent_instance = team_agent_registry.get_instance(agent_name, self.provider)
        
        # Prepare input (empty for all current agents)
        agent_input = agent_instance.input_schema()
        
        # Execute with timeout
        try:
            response = await asyncio.wait_for(
                agent_instance.run_with_retry(agent_input, context),
                timeout=self.AGENT_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            error_msg = f"Agent {agent_name} timed out after {self.AGENT_TIMEOUT_SECONDS}s"
            await self._mark_agent_failed(agent_run.id, error_msg, "TIMEOUT")
            return AgentExecutionResult(agent_name, AgentRunStatus.FAILED, None, error_msg)
        
        # Persist agent output
        output_dict = {}
        if hasattr(response, 'structured_output'):
            output_dict = response.structured_output.model_dump()
        elif hasattr(response, 'model_dump'):
            output_dict = response.model_dump()
        
        await self.agent_run_repo.update(agent_run.id, {
            "status": AgentRunStatus.SUCCEEDED if response.status == AgentStatus.SUCCEEDED else AgentRunStatus.FAILED,
            "completed_at": datetime.utcnow(),
            "output": output_dict,
            "confidence": response.confidence if hasattr(response, 'confidence') else None,
            "provider": response.provider if hasattr(response, 'provider') else self.provider.provider_type.value,
            "model": response.model if hasattr(response, 'model') else self.provider.default_model.value,
            "prompt_version": response.prompt_version if hasattr(response, 'prompt_version') else agent_instance.prompt_version,
        })
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=team_run.workspace_id,
            action=f"agent.{agent_name.value}.{response.status.value.lower()}",
            resource_type="agent_run",
            resource_id=agent_run.id,
            new_state={
                "team_run_id": str(team_run.id),
                "agent_name": agent_name.value,
                "status": response.status.value,
                "confidence": response.confidence if hasattr(response, 'confidence') else None,
                "duration_ms": response.duration_ms if hasattr(response, 'duration_ms') else None,
            },
            user_id=user_id,
        )
        
        return AgentExecutionResult(agent_name, AgentRunStatus.SUCCEEDED, response, None)
    
    async def _mark_agent_failed(self, agent_run_id: UUID, error: str, error_code: str) -> None:
        await self.agent_run_repo.update(agent_run_id, {
            "status": AgentRunStatus.FAILED,
            "completed_at": datetime.utcnow(),
            "error_code": error_code,
            "error_message": error[:1000],
        })
    
    async def _mark_agent_blocked(self, team_run_id: UUID, agent_name: AgentName, reason: str) -> None:
        agent_run = await self.agent_run_repo.get_by_team_run_and_agent(team_run_id, agent_name)
        if agent_run:
            await self.agent_run_repo.update(agent_run.id, {
                "status": AgentRunStatus.BLOCKED,
                "completed_at": datetime.utcnow(),
                "error_code": "DEPENDENCY_BLOCKED",
                "error_message": reason,
            })
    
    def _build_team_summary(
        self,
        agent_outputs: Dict[str, Any],
        completed: Set[AgentName],
        failed: Set[AgentName],
    ) -> Dict[str, Any]:
        return {
            "completed_agents": [a.value for a in completed],
            "failed_agents": [a.value for a in failed],
            "agent_summaries": {
                name: output.get("summary", "") if isinstance(output, dict) else str(output)[:200]
                for name, output in agent_outputs.items()
            },
        }
    
    def _calculate_overall_confidence(self, agent_outputs: Dict[str, Any]) -> float:
        confidences = []
        for output in agent_outputs.values():
            if isinstance(output, dict) and "confidence" in output:
                confidences.append(output["confidence"])
        return sum(confidences) / len(confidences) if confidences else 0.5
    
    async def _create_assessment(self, team_run_id: UUID, reviewer_output: Dict[str, Any], overall_confidence: float) -> None:
        """Create TeamAssessment from Security Reviewer output."""
        assessment = TeamAssessment(
            team_run_id=team_run_id,
            workspace_id=reviewer_output.get("workspace_id", ""),  # Will be set from team_run
            executive_summary=reviewer_output.get("executive_summary", ""),
            key_findings=reviewer_output.get("key_findings", []),
            key_attack_paths=reviewer_output.get("key_attack_paths", []),
            risk_interpretation=reviewer_output.get("risk_interpretation", ""),
            uncertainties=reviewer_output.get("uncertainties", []),
            conflicting_assessments=reviewer_output.get("conflicting_assessments", []),
            recommended_human_actions=reviewer_output.get("recommended_human_actions", []),
            overall_confidence=overall_confidence,
        )
        await self.assessment_repo.create(assessment)
    
    async def cancel_team_run(self, team_run_id: UUID, user_id: UUID) -> bool:
        """Cancel a running team run."""
        team_run = await self.team_run_repo.get_by_id(team_run_id)
        if not team_run:
            return False
        
        if team_run.status not in [SecurityTeamRunStatus.QUEUED, SecurityTeamRunStatus.RUNNING]:
            return False
        
        # Mark team run as canceled
        await self.team_run_repo.update(team_run_id, {
            "status": SecurityTeamRunStatus.CANCELED,
            "completed_at": datetime.utcnow(),
        })
        
        # Mark pending agent runs as canceled
        agent_runs = await self.agent_run_repo.get_by_team_run(team_run_id)
        for ar in agent_runs:
            if ar.status in [AgentRunStatus.QUEUED, AgentRunStatus.RUNNING]:
                await self.agent_run_repo.update(ar.id, {
                    "status": AgentRunStatus.CANCELED,
                    "completed_at": datetime.utcnow(),
                    "error_code": "TEAM_CANCELED",
                    "error_message": "Team run canceled by user",
                })
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=team_run.workspace_id,
            action="security_team.canceled",
            resource_type="security_team_run",
            resource_id=team_run_id,
            new_state={"canceled_by": str(user_id)},
            user_id=user_id,
        )
        
        return True
    
    async def submit_human_review(
        self,
        team_run_id: UUID,
        workspace_id: UUID,
        reviewer_id: UUID,
        notes: Optional[str] = None,
    ) -> TeamReview:
        """Record human review of the team assessment."""
        team_run = await self.team_run_repo.get_by_id(team_run_id)
        if not team_run or team_run.workspace_id != workspace_id:
            raise OrchestrationError("Team run not found or access denied", "TEAM_RUN_NOT_FOUND")
        
        # Check if already reviewed
        existing = await self.review_repo.get_by_team_run(team_run_id)
        if existing:
            raise OrchestrationError("Team run already reviewed", "ALREADY_REVIEWED")
        
        review = TeamReview(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            reviewed_by=reviewer_id,
            notes=notes,
        )
        review = await self.review_repo.create(review)
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="security_team.reviewed",
            resource_type="team_review",
            resource_id=review.id,
            new_state={
                "team_run_id": str(team_run_id),
                "reviewed_by": str(reviewer_id),
                "notes": notes,
            },
            user_id=reviewer_id,
        )
        
        return review

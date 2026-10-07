from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from uuid import UUID
from enum import Enum


class AgentStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELED = "canceled"


class AgentName(str, Enum):
    RECON = "recon"
    VULNERABILITY_ANALYST = "vulnerability_analyst"
    ATTACK_PATH_ANALYST = "attack_path_analyst"
    RISK_ANALYST = "risk_analyst"
    SECURITY_REVIEWER = "security_reviewer"


class SecurityTeamRunStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


# =============================================================================
# Agent Request/Response Contracts
# =============================================================================

class AgentRequest(BaseModel):
    """Base request for all agents."""
    run_id: UUID
    workspace_id: UUID
    scope: Dict[str, Any] = Field(default_factory=dict)
    context: Dict[str, Any] = Field(default_factory=dict)
    task: str
    constraints: Dict[str, Any] = Field(default_factory=dict)


class EvidenceReference(BaseModel):
    """Reference to existing evidence."""
    evidence_id: str
    reason: str
    certainty: Literal["observed", "inferred", "uncertain"] = "observed"


class AgentResponse(BaseModel):
    """Base response for all agents."""
    agent: AgentName
    status: AgentStatus
    summary: str = Field(min_length=10, max_length=500)
    structured_output: Dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: str = Field(default="", max_length=1000)
    evidence_references: List[EvidenceReference] = Field(default_factory=list, max_length=50)
    warnings: List[str] = Field(default_factory=list, max_length=20)
    duration_ms: int
    provider: str
    model: str
    prompt_version: str


# =============================================================================
# Recon Agent Schemas
# =============================================================================

class ReconComponent(BaseModel):
    name: str
    type: str
    description: str
    entry_points: List[str] = Field(default_factory=list)
    boundaries: List[str] = Field(default_factory=list)


class ReconExposedArea(BaseModel):
    component: str
    exposure_type: str
    description: str
    evidence_refs: List[str] = Field(default_factory=list)


class ReconAgentOutput(BaseModel):
    """Structured output for Recon Agent."""
    relevant_components: List[ReconComponent] = Field(default_factory=list, max_length=30)
    entry_points: List[str] = Field(default_factory=list, max_length=20)
    security_boundaries: List[str] = Field(default_factory=list, max_length=20)
    exposed_areas: List[ReconExposedArea] = Field(default_factory=list, max_length=20)
    observations: List[str] = Field(default_factory=list, max_length=30)
    uncertainty: str = Field(default="", max_length=1000)


class ReconAgentResponse(AgentResponse):
    agent: Literal[AgentName.RECON] = AgentName.RECON
    structured_output: ReconAgentOutput


# =============================================================================
# Vulnerability Analyst Agent Schemas
# =============================================================================

class VulnerabilityInterpretation(BaseModel):
    finding_id: str
    interpretation: str
    preconditions: str
    potential_impact: str
    confidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: List[str] = Field(default_factory=list, max_length=10)
    recommended_investigation: List[str] = Field(default_factory=list, max_length=10)
    evidence_refs: List[EvidenceReference] = Field(default_factory=list, max_length=20)


class VulnerabilityAnalystOutput(BaseModel):
    """Structured output for Vulnerability Analyst Agent."""
    findings_analyzed: List[str] = Field(default_factory=list, max_length=50)
    interpretations: List[VulnerabilityInterpretation] = Field(default_factory=list, max_length=50)
    overall_uncertainty: str = Field(default="", max_length=1000)


class VulnerabilityAnalystResponse(AgentResponse):
    agent: Literal[AgentName.VULNERABILITY_ANALYST] = AgentName.VULNERABILITY_ANALYST
    structured_output: VulnerabilityAnalystOutput


# =============================================================================
# Attack Path Agent Schemas
# =============================================================================

class CandidateRelationship(BaseModel):
    source_finding_id: str
    target_finding_id: str
    relationship_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str
    evidence_refs: List[str] = Field(default_factory=list)


class AttackPathObservation(BaseModel):
    path_id: Optional[str] = None
    finding_sequence: List[str]
    observation: str
    confidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: List[str] = Field(default_factory=list)


class AttackPathAnalystOutput(BaseModel):
    """Structured output for Attack Path Agent."""
    candidate_relationships: List[CandidateRelationship] = Field(default_factory=list, max_length=30)
    path_observations: List[AttackPathObservation] = Field(default_factory=list, max_length=20)
    confidence: float = Field(ge=0.0, le=1.0)
    missing_evidence: List[str] = Field(default_factory=list, max_length=20)
    explanation: str = Field(default="", max_length=2000)


class AttackPathAnalystResponse(AgentResponse):
    agent: Literal[AgentName.ATTACK_PATH_ANALYST] = AgentName.ATTACK_PATH_ANALYST
    structured_output: AttackPathAnalystOutput


# =============================================================================
# Risk Analyst Agent Schemas
# =============================================================================

class RiskFactorInterpretation(BaseModel):
    factor_name: str
    contribution: float
    interpretation: str
    importance: Literal["primary", "secondary", "minor"]


class RiskAnalystOutput(BaseModel):
    """Structured output for Risk Analyst Agent."""
    attack_path_id: str
    risk_score: int
    risk_band: str
    explanation: str = Field(min_length=20, max_length=2000)
    important_factors: List[RiskFactorInterpretation] = Field(default_factory=list, max_length=10)
    uncertainty: str = Field(default="", max_length=1000)
    recommended_review_priorities: List[str] = Field(default_factory=list, max_length=10)
    deterministic_score_authoritative: bool = True


class RiskAnalystResponse(AgentResponse):
    agent: Literal[AgentName.RISK_ANALYST] = AgentName.RISK_ANALYST
    structured_output: RiskAnalystOutput


# =============================================================================
# Security Reviewer Agent Schemas
# =============================================================================

class KeyFinding(BaseModel):
    finding_id: str
    title: str
    severity: str
    ai_confidence: float
    reason: str


class KeyAttackPath(BaseModel):
    attack_path_id: str
    title: str
    risk_score: int
    risk_band: str
    reason: str


class ConflictingAssessment(BaseModel):
    agent_a: str
    agent_b: str
    finding_or_path_id: str
    agent_a_confidence: float
    agent_b_confidence: float
    description: str


class SecurityReviewerOutput(BaseModel):
    """Structured output for Security Reviewer Agent (final assessment)."""
    executive_summary: str = Field(min_length=50, max_length=2000)
    key_security_concerns: List[str] = Field(default_factory=list, max_length=10)
    highest_priority_findings: List[KeyFinding] = Field(default_factory=list, max_length=10)
    highest_priority_attack_paths: List[KeyAttackPath] = Field(default_factory=list, max_length=10)
    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: str = Field(default="", max_length=1000)
    conflicting_assessments: List[ConflictingAssessment] = Field(default_factory=list, max_length=10)
    recommended_human_actions: List[str] = Field(default_factory=list, max_length=15)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    deterministic_risk_score_referenced: Optional[int] = None
    human_review_required: bool = True


class SecurityReviewerResponse(AgentResponse):
    agent: Literal[AgentName.SECURITY_REVIEWER] = AgentName.SECURITY_REVIEWER
    structured_output: SecurityReviewerOutput


# =============================================================================
# Team Assessment (Final Output)
# =============================================================================

class TeamAssessment(BaseModel):
    """Final team assessment combining all agent outputs."""
    executive_summary: str
    key_findings: List[KeyFinding]
    key_attack_paths: List[KeyAttackPath]
    risk_interpretation: str
    uncertainties: List[str]
    conflicting_assessments: List[ConflictingAssessment]
    recommended_human_actions: List[str]
    overall_confidence: float
    agent_outputs: Dict[str, AgentResponse]  # All agent responses by name
    orchestration_version: str
    team_run_id: UUID


# =============================================================================
# Orchestration Schemas
# =============================================================================

class SecurityTeamRunRequest(BaseModel):
    """Request to create a security team run."""
    asset_id: UUID
    scan_id: UUID
    analysis_mode: Literal["standard", "deep"] = "standard"


class SecurityTeamRunResponse(BaseModel):
    """Response for security team run."""
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    scan_id: UUID
    status: SecurityTeamRunStatus
    requested_by: UUID
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    orchestration_version: str
    team_summary: Dict[str, Any]
    confidence: Optional[float] = None
    created_at: str
    updated_at: str


class AgentRunResponse(BaseModel):
    """Response for individual agent run."""
    id: UUID
    team_run_id: UUID
    agent_name: AgentName
    status: AgentStatus
    input_reference: Dict[str, Any]
    output: Dict[str, Any]
    confidence: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempt: int
    created_at: str


class TeamAssessmentResponse(BaseModel):
    """Response for team assessment."""
    id: UUID
    team_run_id: UUID
    workspace_id: UUID
    executive_summary: str
    key_findings: List[KeyFinding]
    key_attack_paths: List[KeyAttackPath]
    risk_interpretation: str
    uncertainties: List[str]
    conflicting_assessments: List[ConflictingAssessment]
    recommended_human_actions: List[str]
    overall_confidence: float
    created_at: str
    updated_at: str


class TeamReviewResponse(BaseModel):
    """Response for team review."""
    id: UUID
    team_run_id: UUID
    workspace_id: UUID
    reviewed_by: UUID
    reviewed_at: str
    notes: Optional[str] = None
    created_at: str

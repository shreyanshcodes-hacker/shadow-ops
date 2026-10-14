from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class WorkspaceRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"


class AssetType(str, enum.Enum):
    REPOSITORY = "repository"
    API = "api"
    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    CONTAINER = "container"


class AssetStatus(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    ERROR = "error"


class AssetCriticality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuthorizationStatus(str, enum.Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"


class AuthorizationType(str, enum.Enum):
    OWNERSHIP = "ownership"
    WRITTEN_PERMISSION = "written_permission"
    BUG_BOUNTY = "bug_bounty"
    INTERNAL = "internal"


class ScanType(str, enum.Enum):
    FULL = "full"
    RECON = "recon"
    CODE = "code"
    DEPENDENCY = "dependency"
    TARGETED = "targeted"


class ScanStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"


class ScanProfile(str, enum.Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    CODE_SECURITY = "CODE_SECURITY"


class ScanEventType(str, enum.Enum):
    SCAN_CREATED = "SCAN_CREATED"
    AUTHORIZATION_CONFIRMED = "AUTHORIZATION_CONFIRMED"
    SCAN_QUEUED = "SCAN_QUEUED"
    SCAN_STARTED = "SCAN_STARTED"
    ANALYSIS_STARTED = "ANALYSIS_STARTED"
    SEMGREP_STARTED = "SEMGREP_STARTED"
    SEMGREP_COMPLETED = "SEMGREP_COMPLETED"
    RESULTS_PARSED = "RESULTS_PARSED"
    EVIDENCE_STORED = "EVIDENCE_STORED"
    SCAN_COMPLETED = "SCAN_COMPLETED"
    SCAN_FAILED = "SCAN_FAILED"
    SCAN_CANCELLED = "SCAN_CANCELLED"


class FindingSource(str, enum.Enum):
    SEMGREP = "semgrep"
    RECON = "recon"
    DEPENDENCY = "dependency"
    AI_ANALYSIS = "ai_analysis"
    MANUAL = "manual"


class FindingSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class FindingConfidence(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingStatus(str, enum.Enum):
    OPEN = "open"
    TRIAGED = "triaged"
    IN_PROGRESS = "in_progress"
    FIXED = "fixed"
    FALSE_POSITIVE = "false_positive"
    WONT_FIX = "wont_fix"
    RISK_ACCEPTED = "risk_accepted"


class FindingEvidenceType(str, enum.Enum):
    CODE_SNIPPET = "code_snippet"
    SCREENSHOT = "screenshot"
    LOG = "log"
    REQUEST_RESPONSE = "request_response"
    CONFIG = "config"
    DEPENDENCY_TREE = "dependency_tree"
    AI_REASONING = "ai_reasoning"
    STATIC_ANALYSIS = "static_analysis"
    SOURCE_LOCATION = "source_location"
    RULE_MATCH = "rule_match"
    SCAN_OUTPUT = "scan_output"


# Base schemas
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


# Profile schemas
class ProfileBase(BaseSchema):
    email: EmailStr
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class ProfileCreate(ProfileBase):
    firebase_uid: str


class ProfileUpdate(BaseSchema):
    display_name: Optional[str] = None
    avatar_url: Optional[str] = None


class ProfileResponse(ProfileBase):
    id: UUID
    firebase_uid: str
    role: UserRole
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


# Workspace schemas
class WorkspaceBase(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    slug: Optional[str] = Field(default=None, min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    settings: Optional[Dict[str, Any]] = None


class WorkspaceResponse(WorkspaceBase):
    id: UUID
    slug: str
    owner_id: UUID
    plan: str
    settings: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class WorkspaceListResponse(BaseSchema):
    id: UUID
    name: str
    slug: str
    plan: str
    role: WorkspaceRole
    created_at: datetime


# Workspace Member schemas
class WorkspaceMemberBase(BaseSchema):
    user_id: UUID
    role: WorkspaceRole


class WorkspaceMemberCreate(BaseSchema):
    email: EmailStr
    role: WorkspaceRole = WorkspaceRole.MEMBER


class WorkspaceMemberUpdate(BaseSchema):
    role: WorkspaceRole


class WorkspaceMemberResponse(WorkspaceMemberBase):
    id: UUID
    workspace_id: UUID
    invited_by: Optional[UUID] = None
    invited_at: datetime
    joined_at: Optional[datetime] = None
    created_at: datetime
    user: Optional[ProfileResponse] = None


# Asset schemas
class AssetBase(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    type: AssetType
    subtype: Optional[str] = None
    connection_config: Dict[str, Any] = Field(default_factory=dict)
    credentials_ref: Optional[str] = None
    criticality: AssetCriticality = AssetCriticality.MEDIUM
    tags: List[str] = Field(default_factory=list)


class AssetCreate(AssetBase):
    pass


class AssetUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    connection_config: Optional[Dict[str, Any]] = None
    credentials_ref: Optional[str] = None
    criticality: Optional[AssetCriticality] = None
    status: Optional[AssetStatus] = None
    scan_frequency: Optional[str] = None
    tags: Optional[List[str]] = None


class AssetResponse(AssetBase):
    id: UUID
    workspace_id: UUID
    status: AssetStatus
    last_scanned_at: Optional[datetime] = None
    scan_frequency: str
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


# Authorization schemas
class AuthorizationBase(BaseSchema):
    authorization_type: AuthorizationType
    evidence_files: List[str] = Field(default_factory=list)
    evidence_urls: List[str] = Field(default_factory=list)
    authorized_by: Optional[str] = None
    authorized_at: datetime
    expires_at: Optional[datetime] = None
    notes: Optional[str] = None


class AuthorizationCreate(AuthorizationBase):
    pass


class AuthorizationUpdate(BaseSchema):
    status: Optional[AuthorizationStatus] = None
    verified_by: Optional[UUID] = None
    verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class AuthorizationResponse(AuthorizationBase):
    id: UUID
    asset_id: UUID
    workspace_id: UUID
    status: AuthorizationStatus
    verified_by: Optional[UUID] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# Health schemas
class HealthResponse(BaseSchema):
    status: str
    timestamp: datetime
    checks: Optional[Dict[str, str]] = None


# Error schemas
class ErrorDetail(BaseSchema):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ErrorResponse(BaseSchema):
    error: ErrorDetail


# Scan schemas
class ScanBase(BaseSchema):
    asset_id: UUID
    scan_type: ScanType = ScanType.CODE
    scan_profile: ScanProfile = ScanProfile.CODE_SECURITY
    scan_config: Dict[str, Any] = Field(default_factory=dict)


class ScanCreate(ScanBase):
    pass


class ScanUpdate(BaseSchema):
    status: Optional[ScanStatus] = None
    current_phase: Optional[str] = None
    progress_percent: Optional[int] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    scan_config: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None


class ScanResponse(ScanBase):
    id: UUID
    workspace_id: UUID
    status: ScanStatus
    triggered_by: UUID
    triggered_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    authorization_confirmed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    phases_completed: List[str]
    current_phase: Optional[str] = None
    progress_percent: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    scan_config: Dict[str, Any]
    summary: Dict[str, Any]
    target_type: Optional[str] = None
    target_reference: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ScanListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    scan_type: ScanType
    scan_profile: ScanProfile
    status: ScanStatus
    triggered_by: UUID
    triggered_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    progress_percent: int
    error_message: Optional[str] = None
    created_at: datetime


# Scan Event schemas
class ScanEventBase(BaseSchema):
    scan_id: UUID
    workspace_id: UUID
    phase: str
    event_type: str
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class ScanEventCreate(ScanEventBase):
    pass


class ScanEventResponse(ScanEventBase):
    id: int
    created_at: datetime


# Finding schemas
class FindingBase(BaseSchema):
    scan_id: UUID
    asset_id: UUID
    source: FindingSource
    source_rule_id: Optional[str] = None
    title: str
    description: str
    severity: FindingSeverity
    confidence: FindingConfidence = FindingConfidence.MEDIUM
    cwe_ids: List[str] = Field(default_factory=list)
    cve_ids: List[str] = Field(default_factory=list)
    owasp_categories: List[str] = Field(default_factory=list)
    location: Optional[Dict[str, Any]] = None
    code_snippet: Optional[str] = None
    remediation_guidance: Optional[str] = None


class FindingCreate(FindingBase):
    pass


class FindingUpdate(BaseSchema):
    status: Optional[FindingStatus] = None
    triaged_by: Optional[UUID] = None
    triaged_at: Optional[datetime] = None
    risk_score: Optional[float] = None
    risk_factors: Optional[Dict[str, Any]] = None


class FindingResponse(FindingBase):
    id: UUID
    workspace_id: UUID
    status: FindingStatus
    triaged_by: Optional[UUID] = None
    triaged_at: Optional[datetime] = None
    risk_score: Optional[float] = None
    risk_factors: Dict[str, Any]
    first_seen_at: datetime
    last_seen_at: datetime
    fixed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class FindingListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    scan_id: UUID
    asset_id: UUID
    source: FindingSource
    source_rule_id: Optional[str] = None
    title: str
    severity: FindingSeverity
    confidence: FindingConfidence
    status: FindingStatus
    first_seen_at: datetime
    created_at: datetime


# Finding Evidence schemas
class FindingEvidenceBase(BaseSchema):
    finding_id: UUID
    workspace_id: UUID
    evidence_type: FindingEvidenceType
    title: str
    description: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    storage_object_id: Optional[UUID] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FindingEvidenceCreate(FindingEvidenceBase):
    pass


class FindingEvidenceResponse(FindingEvidenceBase):
    id: UUID
    created_at: datetime


# Scan Target schemas
class ScanTargetBase(BaseSchema):
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    target_path: str
    target_type: str = "repository"
    is_demo: bool = False
    is_active: bool = True


class ScanTargetCreate(ScanTargetBase):
    pass


class ScanTargetUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    target_path: Optional[str] = None
    target_type: Optional[str] = None
    is_demo: Optional[bool] = None
    is_active: Optional[bool] = None


class ScanTargetResponse(ScanTargetBase):
    id: UUID
    workspace_id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime


# Scan Summary schemas
class ScanSummary(BaseSchema):
    total_findings: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    info: int = 0


class AiProviderType(str, enum.Enum):
    GEMINI = "gemini"
    GROK = "grok"


class AiOperationType(str, enum.Enum):
    FINDING_ANALYSIS = "finding_analysis"
    SCAN_ANALYSIS = "scan_analysis"


class AiRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# AI Run schemas
class AiRunBase(BaseSchema):
    scan_id: UUID
    finding_id: Optional[UUID] = None
    provider: AiProviderType
    model: str
    operation: AiOperationType
    prompt_version: str = "1.0"
    input_hash: str


class AiRunCreate(AiRunBase):
    pass


class AiRunUpdate(BaseSchema):
    status: Optional[AiRunStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class AiRunResponse(AiRunBase):
    id: UUID
    workspace_id: UUID
    requested_by: UUID
    status: AiRunStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# Finding AI Analysis schemas
class SupportingEvidenceRef(BaseSchema):
    evidence_id: UUID
    reason: str
    certainty: str = "observed"


class FindingAiAnalysisBase(BaseSchema):
    finding_id: UUID
    ai_run_id: UUID
    summary: str
    vulnerability_type: str
    severity_assessment: str
    confidence: float = Field(ge=0.0, le=1.0)
    exploitability_assessment: str
    impact_assessment: str
    affected_component: str
    attack_preconditions: str
    evidence_interpretation: str
    reasoning: str
    recommended_next_steps: List[str] = Field(default_factory=list)
    uncertainty: str
    supporting_evidence: List[SupportingEvidenceRef] = Field(default_factory=list)
    model: str
    provider: AiProviderType
    prompt_version: str = "1.0"


class FindingAiAnalysisCreate(FindingAiAnalysisBase):
    pass


class FindingAiAnalysisResponse(FindingAiAnalysisBase):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime


# AI Analysis Request schemas
class StartFindingAnalysisRequest(BaseSchema):
    finding_id: UUID


class StartScanAnalysisRequest(BaseSchema):
    scan_id: UUID
    max_findings: Optional[int] = Field(default=10, ge=1, le=50)


# AI Provider Status schemas
class AiProviderStatus(BaseSchema):
    provider: AiProviderType
    configured: bool
    model: Optional[str] = None


class RelationshipSource(str, enum.Enum):
    DETERMINISTIC = "deterministic"
    AI_SUGGESTED = "ai_suggested"
    HUMAN_CONFIRMED = "human_confirmed"


class RelationshipType(str, enum.Enum):
    DEPENDS_ON = "depends_on"
    ENABLES = "enables"
    EXPOSES = "exposes"
    LEADS_TO = "leads_to"
    SHARES_COMPONENT = "shares_component"
    SHARES_ENTRY_POINT = "shares_entry_point"
    SHARES_DATA_FLOW = "shares_data_flow"
    AMPLIFIES = "amplifies"


class AttackPathStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class AttackPathNodeType(str, enum.Enum):
    ENTRY = "entry"
    FINDING = "finding"
    BOUNDARY = "boundary"
    IMPACT = "impact"


class RiskBand(str, enum.Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# Finding Relationship schemas
class FindingRelationshipBase(BaseSchema):
    source_finding_id: UUID
    target_finding_id: UUID
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    source: RelationshipSource
    rationale: str
    evidence_reference: Optional[str] = None


class FindingRelationshipCreate(FindingRelationshipBase):
    pass


class FindingRelationshipResponse(FindingRelationshipBase):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime
    source_finding: Optional["FindingListResponse"] = None
    target_finding: Optional["FindingListResponse"] = None


# Attack Path schemas
class AttackPathBase(BaseSchema):
    asset_id: UUID
    title: str
    description: str = ""
    status: AttackPathStatus = AttackPathStatus.DRAFT
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    severity: str = "unknown"
    risk_score: Optional[int] = Field(default=None, ge=0, le=100)
    risk_model_version: str = "risk-v1"


class AttackPathCreate(AttackPathBase):
    pass


class AttackPathUpdate(BaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[AttackPathStatus] = None
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    severity: Optional[str] = None


class AttackPathNodeBase(BaseSchema):
    finding_id: Optional[UUID] = None
    sequence: int
    node_type: AttackPathNodeType
    rationale: str = ""


class AttackPathNodeCreate(AttackPathNodeBase):
    pass


class AttackPathNodeResponse(AttackPathNodeBase):
    id: UUID
    attack_path_id: UUID
    created_at: datetime
    updated_at: datetime
    finding: Optional["FindingListResponse"] = None


class AttackPathEdgeBase(BaseSchema):
    source_node_id: UUID
    target_node_id: UUID
    relationship_type: RelationshipType
    confidence: float = Field(ge=0.0, le=1.0)
    source: RelationshipSource
    rationale: str


class AttackPathEdgeCreate(AttackPathEdgeBase):
    pass


class AttackPathEdgeResponse(AttackPathEdgeBase):
    id: UUID
    attack_path_id: UUID
    created_at: datetime
    source_node: Optional["AttackPathNodeResponse"] = None
    target_node: Optional["AttackPathNodeResponse"] = None


class AttackPathResponse(AttackPathBase):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    updated_at: datetime
    nodes: List["AttackPathNodeResponse"] = Field(default_factory=list)
    edges: List["AttackPathEdgeResponse"] = Field(default_factory=list)
    asset: Optional["AssetResponse"] = None


class AttackPathListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    title: str
    status: AttackPathStatus
    confidence: float
    severity: str
    risk_score: Optional[int] = None
    risk_band: Optional[RiskBand] = None
    node_count: int = 0
    created_at: datetime
    updated_at: datetime


# Risk Snapshot schemas
class RiskSnapshotBase(BaseSchema):
    attack_path_id: UUID
    score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    model_version: str
    factors: Dict[str, Any]


class RiskSnapshotCreate(RiskSnapshotBase):
    pass


class RiskSnapshotResponse(RiskSnapshotBase):
    id: UUID
    workspace_id: UUID
    calculated_at: datetime


# Risk Calculation schemas
class RiskFactor(BaseSchema):
    name: str
    weight: float
    value: float
    contribution: float
    description: str


class RiskCalculationResult(BaseSchema):
    score: int = Field(ge=0, le=100)
    risk_band: RiskBand
    model_version: str
    factors: List[RiskFactor]
    explanation: str


# Relationship Confirmation schemas
class RelationshipConfirmRequest(BaseSchema):
    pass


class RelationshipDismissRequest(BaseSchema):
    pass


# =============================================================================
# Stage 8: Remediation Schemas
# =============================================================================

class RemediationStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    PROPOSED = "PROPOSED"
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class RemediationFixType(str, enum.Enum):
    CODE_CHANGE = "code_change"
    CONFIG_CHANGE = "config_change"
    DEPENDENCY_UPDATE = "dependency_update"
    INFRASTRUCTURE_CHANGE = "infrastructure_change"
    WAF_RULE = "waf_rule"
    NETWORK_POLICY = "network_policy"
    SECRET_ROTATION = "secret_rotation"


class ValidationStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class ValidationCheckType(str, enum.Enum):
    PATCH_INTEGRITY = "patch_integrity"
    DIFF_PARSING = "diff_parsing"
    PATH_ALLOWLIST = "path_allowlist"
    SYNTAX_VALIDATION = "syntax_validation"
    SEMGREP_RESCAN = "semgrep_rescan"
    REGRESSION_CHECK = "regression_check"
    EXISTING_TESTS = "existing_tests"


class ApplicationStatus(str, enum.Enum):
    PENDING = "PENDING"
    CHECKPOINT_CREATED = "CHECKPOINT_CREATED"
    PATCH_APPLIED = "PATCH_APPLIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class RollbackStatus(str, enum.Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED_DIVERGED = "BLOCKED_DIVERGED"


class VerificationHandoffStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFICATION_REQUESTED = "VERIFICATION_REQUESTED"
    VERIFIED = "VERIFIED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class AffectedFile(BaseSchema):
    file_path: str
    language: Optional[str] = None
    change_type: str  # "modify", "create", "delete"


class SuggestedTest(BaseSchema):
    test_type: str  # "unit", "integration", "security", "regression"
    description: str
    command: Optional[str] = None


class FileChange(BaseSchema):
    file_path: str
    old_hash: Optional[str] = None
    new_hash: Optional[str] = None
    additions: int = 0
    deletions: int = 0


# Remediation Proposal schemas
class RemediationProposalBase(BaseSchema):
    workspace_id: UUID
    asset_id: UUID
    finding_id: UUID
    source_scan_id: UUID
    proposal_title: str = Field(min_length=1, max_length=255)
    problem_summary: str = Field(min_length=10)
    proposed_solution: str = Field(min_length=10)
    rationale: str = Field(min_length=10)
    affected_files: List[AffectedFile] = Field(default_factory=list)
    fix_type: RemediationFixType = RemediationFixType.CODE_CHANGE
    expected_security_benefit: Optional[str] = None
    compatibility_risks: Optional[str] = None
    assumptions: Optional[str] = None
    limitations: Optional[str] = None
    suggested_tests: List[SuggestedTest] = Field(default_factory=list)


class RemediationProposalCreate(RemediationProposalBase):
    pass


class RemediationProposalUpdate(BaseSchema):
    status: Optional[RemediationStatus] = None
    proposal_title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    problem_summary: Optional[str] = None
    proposed_solution: Optional[str] = None
    rationale: Optional[str] = None
    affected_files: Optional[List[AffectedFile]] = None
    validation_results: Optional[Dict[str, Any]] = None
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    applied_by: Optional[UUID] = None
    applied_at: Optional[datetime] = None
    failure_reason: Optional[str] = None


class RemediationProposalResponse(RemediationProposalBase):
    id: UUID
    status: RemediationStatus
    validation_results: Dict[str, Any]
    patch_reference: Optional[UUID] = None
    created_by: UUID
    created_at: datetime
    updated_at: datetime
    approved_by: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    applied_by: Optional[UUID] = None
    applied_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    version: int
    expires_at: Optional[datetime] = None
    finding: Optional["FindingListResponse"] = None
    asset: Optional["AssetResponse"] = None


class RemediationProposalListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    finding_id: UUID
    source_scan_id: UUID
    proposal_title: str
    status: RemediationStatus
    fix_type: RemediationFixType
    created_by: UUID
    created_at: datetime
    approved_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None


# Patch Version schemas
class PatchVersionBase(BaseSchema):
    proposal_id: UUID
    version: int = Field(ge=1)
    unified_diff: str
    file_changes: List[FileChange] = Field(default_factory=list)
    patch_hash: str
    base_revision: Optional[str] = None


class PatchVersionCreate(PatchVersionBase):
    pass


class PatchVersionResponse(PatchVersionBase):
    id: UUID
    workspace_id: UUID
    created_by: UUID
    created_at: datetime
    is_current: bool
    superseded_by: Optional[UUID] = None


# Validation Run schemas
class ValidationRunBase(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    check_type: ValidationCheckType
    command: Optional[str] = None


class ValidationRunCreate(ValidationRunBase):
    pass


class ValidationRunUpdate(BaseSchema):
    status: Optional[ValidationStatus] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ValidationRunResponse(ValidationRunBase):
    id: UUID
    workspace_id: UUID
    status: ValidationStatus
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime


# Approval schemas
class RemediationApprovalBase(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    decision: str  # "approved" or "rejected"
    justification: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)
    patch_hash: str
    proposal_version: int
    validation_snapshot: Dict[str, Any] = Field(default_factory=dict)


class RemediationApprovalCreate(RemediationApprovalBase):
    pass


class RemediationApprovalResponse(RemediationApprovalBase):
    id: UUID
    workspace_id: UUID
    approved_by: UUID
    approved_at: datetime
    expires_at: Optional[datetime] = None
    approver: Optional["ProfileResponse"] = None


# Application schemas
class RemediationApplicationBase(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    approval_id: UUID
    asset_id: UUID
    target_revision: str
    checkpoint_ref: Optional[str] = None
    idempotency_key: str


class RemediationApplicationCreate(RemediationApplicationBase):
    pass


class RemediationApplicationResponse(RemediationApplicationBase):
    id: UUID
    workspace_id: UUID
    status: ApplicationStatus
    applied_by: UUID
    applied_at: datetime
    completed_at: Optional[datetime] = None
    result_diff: Optional[str] = None
    changed_files: List[FileChange] = Field(default_factory=list)
    validation_results: Dict[str, Any]
    failure_reason: Optional[str] = None
    applier: Optional["ProfileResponse"] = None


# Rollback schemas
class RemediationRollbackBase(BaseSchema):
    proposal_id: UUID
    application_id: UUID
    asset_id: UUID
    reason: str
    checkpoint_ref: str


class RemediationRollbackCreate(RemediationRollbackBase):
    pass


class RemediationRollbackResponse(RemediationRollbackBase):
    id: UUID
    workspace_id: UUID
    status: RollbackStatus
    requested_by: UUID
    verification_diff: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    failure_reason: Optional[str] = None
    requester: Optional["ProfileResponse"] = None


# Verification Handoff schemas
class RemediationVerificationHandoffBase(BaseSchema):
    proposal_id: UUID
    application_id: UUID
    finding_id: UUID
    asset_id: UUID
    patch_hash: str
    repository_revision: str
    changed_files: List[FileChange] = Field(default_factory=list)
    validation_results: Dict[str, Any] = Field(default_factory=dict)
    original_finding_snapshot: Dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime
    applied_by: UUID


class RemediationVerificationHandoffCreate(RemediationVerificationHandoffBase):
    pass


class RemediationVerificationHandoffResponse(RemediationVerificationHandoffBase):
    id: UUID
    workspace_id: UUID
    verification_requested: bool
    verification_requested_at: Optional[datetime] = None
    verification_completed_at: Optional[datetime] = None
    verification_result: Optional[Dict[str, Any]] = None
    status: VerificationHandoffStatus
    finding: Optional["FindingListResponse"] = None
    asset: Optional["AssetResponse"] = None


# API Request/Response schemas
class GenerateRemediationRequest(BaseSchema):
    finding_id: UUID


class ValidateRemediationRequest(BaseSchema):
    proposal_id: UUID


class ApproveRemediationRequest(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    justification: Optional[str] = None
    conditions: List[str] = Field(default_factory=list)


class RejectRemediationRequest(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    justification: str  # Required for rejection


class ApplyRemediationRequest(BaseSchema):
    proposal_id: UUID
    patch_version_id: UUID
    approval_id: UUID
    idempotency_key: str


class RollbackRemediationRequest(BaseSchema):
    application_id: UUID
    reason: str


class RequestVerificationRequest(BaseSchema):
    application_id: UUID


# Response schemas for API
class RemediationDetailResponse(BaseSchema):
    proposal: RemediationProposalResponse
    patch_versions: List[PatchVersionResponse] = Field(default_factory=list)
    validations: List[ValidationRunResponse] = Field(default_factory=list)
    approvals: List[RemediationApprovalResponse] = Field(default_factory=list)
    applications: List[RemediationApplicationResponse] = Field(default_factory=list)
    rollbacks: List[RemediationRollbackResponse] = Field(default_factory=list)
    verification_handoff: Optional[RemediationVerificationHandoffResponse] = None


# =============================================================================
# Stage 9: Verification Schemas
# =============================================================================

class VerificationStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    BASELINE_CHECK = "BASELINE_CHECK"
    RESCANNING = "RESCANNING"
    REGRESSION_CHECK = "REGRESSION_CHECK"
    COMPARING_EVIDENCE = "COMPARING_EVIDENCE"
    PASSED_PENDING_REVIEW = "PASSED_PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"
    CANCELED = "CANCELED"


class VerificationOutcome(str, enum.Enum):
    VERIFIED_CANDIDATE = "VERIFIED_CANDIDATE"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    BLOCKED = "BLOCKED"


class CheckStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


class CheckType(str, enum.Enum):
    ORIGINAL_VULNERABILITY = "original_vulnerability"
    REGRESSION_ANALYSIS = "regression_analysis"
    SCANNER_EXECUTION = "scanner_execution"
    TEST_EXECUTION = "test_execution"
    EVIDENCE_COMPARISON = "evidence_comparison"


class ComparisonCategory(str, enum.Enum):
    STILL_PRESENT = "STILL_PRESENT"
    NO_LONGER_DETECTED = "NO_LONGER_DETECTED"
    MODIFIED_OR_MOVED = "MODIFIED_OR_MOVED"
    POSSIBLE_REGRESSION = "POSSIBLE_REGRESSION"
    NEW_FINDING = "NEW_FINDING"
    UNCOMPARABLE = "UNCOMPARABLE"


class ReviewDecision(str, enum.Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    RERUN_REQUESTED = "rerun_requested"


class VerificationJobBase(BaseSchema):
    workspace_id: UUID
    asset_id: UUID
    finding_id: UUID
    remediation_proposal_id: UUID
    remediation_application_id: UUID
    patch_hash: str
    source_revision: str
    target_revision: str
    verification_engine_version: str = "verification-v1"
    policy_version: str = "verification-policy-v1"
    idempotency_key: str


class VerificationJobCreate(VerificationJobBase):
    pass


class VerificationJobUpdate(BaseSchema):
    status: Optional[VerificationStatus] = None
    overall_outcome: Optional[VerificationOutcome] = None
    original_vulnerability_outcome: Optional[CheckStatus] = None
    regression_analysis_outcome: Optional[CheckStatus] = None
    scanner_execution_outcome: Optional[CheckStatus] = None
    test_execution_outcome: Optional[CheckStatus] = None
    evidence_comparison_outcome: Optional[CheckStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class VerificationJobResponse(VerificationJobBase):
    id: UUID
    status: VerificationStatus
    overall_outcome: Optional[VerificationOutcome] = None
    original_vulnerability_outcome: Optional[CheckStatus] = None
    regression_analysis_outcome: Optional[CheckStatus] = None
    scanner_execution_outcome: Optional[CheckStatus] = None
    test_execution_outcome: Optional[CheckStatus] = None
    evidence_comparison_outcome: Optional[CheckStatus] = None
    requested_by: UUID
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    finding: Optional["FindingListResponse"] = None
    asset: Optional["AssetResponse"] = None


class VerificationJobListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    finding_id: UUID
    remediation_proposal_id: UUID
    remediation_application_id: UUID
    patch_hash: str
    status: VerificationStatus
    overall_outcome: Optional[VerificationOutcome] = None
    requested_by: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None


class VerificationBaselineBase(BaseSchema):
    verification_job_id: UUID
    finding_id: UUID
    original_finding_snapshot: Dict[str, Any]
    original_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    scanner_version: str
    scanner_config: Dict[str, Any] = Field(default_factory=dict)
    rule_ids: List[str] = Field(default_factory=list)
    finding_fingerprint: str
    evidence_hashes: List[str] = Field(default_factory=list)
    repository_revision: str
    scan_id: Optional[UUID] = None
    pre_patch_scan_results: Optional[Dict[str, Any]] = None
    capture_method: str = "handoff"


class VerificationBaselineCreate(VerificationBaselineBase):
    pass


class VerificationBaselineResponse(VerificationBaselineBase):
    id: UUID
    workspace_id: UUID
    captured_at: datetime
    captured_by: UUID
    finding: Optional["FindingListResponse"] = None
    scan: Optional["ScanListResponse"] = None


class VerificationCheckBase(BaseSchema):
    verification_job_id: UUID
    check_type: CheckType
    check_name: str
    check_version: Optional[str] = None


class VerificationCheckCreate(VerificationCheckBase):
    pass


class VerificationCheckUpdate(BaseSchema):
    status: Optional[CheckStatus] = None
    command: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class VerificationCheckResponse(VerificationCheckBase):
    id: UUID
    workspace_id: UUID
    status: CheckStatus
    command: Optional[str] = None
    exit_code: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    duration_ms: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime


class EvidenceComparisonBase(BaseSchema):
    verification_job_id: UUID
    baseline_finding_id: Optional[UUID] = None
    post_patch_finding_id: Optional[UUID] = None
    baseline_fingerprint: str
    post_patch_fingerprint: Optional[str] = None
    scanner_rule_id: str
    normalized_file_path: str
    baseline_location: Optional[Dict[str, Any]] = None
    post_patch_location: Optional[Dict[str, Any]] = None
    baseline_evidence_hash: str
    post_patch_evidence_hash: Optional[str] = None
    category: ComparisonCategory
    match_confidence: Optional[float] = None
    match_rationale: Optional[str] = None
    relationship_to_original: Optional[str] = None


class EvidenceComparisonCreate(EvidenceComparisonBase):
    pass


class EvidenceComparisonResponse(EvidenceComparisonBase):
    id: UUID
    workspace_id: UUID
    created_at: datetime
    baseline_finding: Optional["FindingListResponse"] = None
    post_patch_finding: Optional["FindingListResponse"] = None


class VerificationPolicyBase(BaseSchema):
    version: str
    name: str
    description: Optional[str] = None
    policy_config: Dict[str, Any]
    is_active: bool = False


class VerificationPolicyCreate(VerificationPolicyBase):
    pass


class VerificationPolicyUpdate(BaseSchema):
    name: Optional[str] = None
    description: Optional[str] = None
    policy_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class VerificationPolicyResponse(VerificationPolicyBase):
    id: UUID
    created_by: UUID
    created_at: datetime
    updated_at: datetime


class VerificationReviewBase(BaseSchema):
    verification_job_id: UUID
    decision: ReviewDecision
    justification: str
    notes: Optional[str] = None
    policy_version: str
    baseline_snapshot: Dict[str, Any]
    comparison_snapshot: Dict[str, Any]
    check_results_snapshot: Dict[str, Any]


class VerificationReviewCreate(VerificationReviewBase):
    pass


class VerificationReviewResponse(VerificationReviewBase):
    id: UUID
    workspace_id: UUID
    reviewed_by: UUID
    reviewed_at: datetime
    created_at: datetime
    reviewer: Optional["ProfileResponse"] = None


# API Request/Response schemas
class StartVerificationRequest(BaseSchema):
    remediation_application_id: UUID
    idempotency_key: str


class VerificationReviewRequest(BaseSchema):
    verification_job_id: UUID
    decision: ReviewDecision
    justification: str
    notes: Optional[str] = None


class RerunVerificationRequest(BaseSchema):
    verification_job_id: UUID
    idempotency_key: str


class VerificationDetailResponse(BaseSchema):
    job: VerificationJobResponse
    baseline: Optional[VerificationBaselineResponse] = None
    checks: List[VerificationCheckResponse] = Field(default_factory=list)
    comparisons: List[EvidenceComparisonResponse] = Field(default_factory=list)
    reviews: List[VerificationReviewResponse] = Field(default_factory=list)
    policy: Optional[VerificationPolicyResponse] = None


# =============================================================================
# Stage 10: Report Schemas
# =============================================================================

class ReportType(str, enum.Enum):
    EXECUTIVE_SUMMARY = "executive_summary"
    TECHNICAL_VULNERABILITY = "technical_vulnerability"
    REMEDIATION_PROGRESS = "remediation_progress"
    VERIFICATION_REGRESSION = "verification_regression"
    ASSET_SECURITY_POSTURE = "asset_security_posture"


class ReportFormat(str, enum.Enum):
    PDF = "pdf"
    JSON = "json"


class ReportStatus(str, enum.Enum):
    PENDING = "pending"
    GENERATING = "generating"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


class ReportBase(BaseSchema):
    workspace_id: UUID
    report_type: ReportType
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    format: ReportFormat = ReportFormat.PDF
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    included_asset_ids: List[UUID] = Field(default_factory=list)
    severity_filters: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)


class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseSchema):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[ReportStatus] = None
    error_message: Optional[str] = None
    storage_object_id: Optional[UUID] = None
    storage_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    expires_at: Optional[datetime] = None


class ReportResponse(ReportBase):
    id: UUID
    status: ReportStatus
    schema_version: str
    risk_engine_version: Optional[str] = None
    verification_policy_version: Optional[str] = None
    data_cutoff: datetime
    source_record_references: Dict[str, Any]
    completeness: Dict[str, Any]
    limitations: List[str]
    generated_by: UUID
    storage_object_id: Optional[UUID] = None
    storage_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    updated_at: datetime
    generator: Optional["ProfileResponse"] = None


class ReportListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    report_type: ReportType
    title: str
    format: ReportFormat
    status: ReportStatus
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    generated_by: UUID
    created_at: datetime
    completed_at: Optional[datetime] = None


class ReportSectionBase(BaseSchema):
    report_id: UUID
    section_key: str
    section_title: str
    section_order: int = 0
    content: Dict[str, Any] = Field(default_factory=dict)
    data_references: Dict[str, Any] = Field(default_factory=dict)


class ReportSectionCreate(ReportSectionBase):
    pass


class ReportSectionResponse(ReportSectionBase):
    id: UUID
    workspace_id: UUID
    created_at: datetime


class ReportExportBase(BaseSchema):
    report_id: UUID
    format: ReportFormat


class ReportExportCreate(ReportExportBase):
    pass


class ReportExportResponse(ReportExportBase):
    id: UUID
    workspace_id: UUID
    storage_object_id: Optional[UUID] = None
    storage_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    generated_by: UUID
    expires_at: Optional[datetime] = None
    created_at: datetime


# Dashboard Metrics Schemas
class DashboardMetrics(BaseSchema):
    workspace_id: UUID
    # Asset metrics
    total_assets: int
    assets_with_authorization: int
    assets_by_criticality: Dict[str, int]
    assets_by_type: Dict[str, int]
    assets_by_status: Dict[str, int]
    # Scan metrics
    total_scans: int
    scans_completed: int
    scans_failed: int
    scans_running: int
    latest_completed_scan_at: Optional[datetime] = None
    # Finding metrics
    open_findings_by_severity: Dict[str, int]
    findings_by_status: Dict[str, int]
    findings_by_source: Dict[str, int]
    total_findings: int
    # Risk metrics
    current_risk_score: Optional[int] = None
    risk_model_version: Optional[str] = None
    attack_paths_by_status: Dict[str, int]
    attack_paths_by_severity: Dict[str, int]
    # Remediation metrics
    remediation_proposals_by_status: Dict[str, int]
    remediation_approved: int
    remediation_applied: int
    remediation_rejected: int
    # Verification metrics
    verification_jobs_by_status: Dict[str, int]
    verification_outcomes: Dict[str, int]
    regression_failures: int
    # Timestamps
    latest_verification_at: Optional[datetime] = None


class TrendPoint(BaseSchema):
    timestamp: datetime
    value: float
    label: Optional[str] = None


class TrendData(BaseSchema):
    metric_name: str
    metric_label: str
    unit: str
    data_points: List[TrendPoint]
    data_source: str
    aggregation_method: str
    time_window: str
    limitations: Optional[str] = None


class TrendResponse(BaseSchema):
    trends: List[TrendData]
    generated_at: datetime
    data_cutoff: datetime


# Report Generation Request
class GenerateReportRequest(BaseSchema):
    report_type: ReportType
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    format: ReportFormat = ReportFormat.PDF
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    included_asset_ids: List[UUID] = Field(default_factory=list)
    severity_filters: List[str] = Field(default_factory=list)
    filters: Dict[str, Any] = Field(default_factory=dict)
    include_ai_narrative: bool = False


class GenerateReportResponse(BaseSchema):
    report: ReportResponse
    estimated_completion_seconds: Optional[int] = None


# Report Detail Response
class ReportDetailResponse(BaseSchema):
    report: ReportResponse
    sections: List[ReportSectionResponse] = Field(default_factory=list)
    exports: List[ReportExportResponse] = Field(default_factory=list)


# =============================================================================
# Stage 11: Notification Schemas
# =============================================================================

class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"


class NotificationPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationBase(BaseSchema):
    workspace_id: UUID
    user_id: UUID
    type: str
    title: str
    message: str
    reference_type: Optional[str] = None
    reference_id: Optional[UUID] = None
    channels: List[str] = Field(default_factory=lambda: ["in_app"])
    read_at: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    created_at: datetime
    priority: str = "normal"
    action_url: Optional[str] = None
    action_label: Optional[str] = None
    deduplication_key: Optional[str] = None
    expires_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    id: UUID
    event_outbox_id: Optional[UUID] = None
    rule_id: Optional[UUID] = None
    is_read: bool = False


class NotificationListResponse(NotificationBase):
    id: UUID
    is_read: bool = False


class MarkReadRequest(BaseSchema):
    notification_id: UUID


class MarkAllReadRequest(BaseSchema):
    workspace_id: UUID


# Notification Preferences
class NotificationPreferenceCategory(str, enum.Enum):
    FINDING_CRITICAL_HIGH = "finding_critical_high"
    FINDING_SEVERITY_CHANGED = "finding_severity_changed"
    SCAN_FAILED = "scan_failed"
    SCAN_COMPLETED = "scan_completed"
    ATTACK_PATH_CREATED = "attack_path_created"
    RISK_SCORE_CHANGED = "risk_score_changed"
    REMEDIATION_AWAITING_APPROVAL = "remediation_awaiting_approval"
    REMEDIATION_APPROVED = "remediation_approved"
    REMEDIATION_REJECTED = "remediation_rejected"
    REMEDIATION_APPLIED = "remediation_applied"
    REMEDIATION_FAILED = "remediation_failed"
    REMEDIATION_ROLLED_BACK = "remediation_rolled_back"
    VERIFICATION_COMPLETED = "verification_completed"
    VERIFICATION_FAILED = "verification_failed"
    VERIFICATION_INCONCLUSIVE = "verification_inconclusive"
    REPORT_GENERATED = "report_generated"
    REPORT_GENERATION_FAILED = "report_generation_failed"
    SECURITY_TEAM_COMPLETED = "security_team_completed"


class NotificationPreferenceBase(BaseSchema):
    workspace_id: UUID
    user_id: UUID
    category: str
    in_app_enabled: bool = True
    email_enabled: bool = False


class NotificationPreferenceCreate(NotificationPreferenceBase):
    pass


class NotificationPreferenceUpdate(BaseSchema):
    in_app_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None


class NotificationPreferenceResponse(NotificationPreferenceBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


# Notification Rules
class RuleRecipientPolicy(str, enum.Enum):
    ASSET_OWNERS = "asset_owners"
    ASSET_MEMBERS = "asset_members"
    WORKSPACE_ADMINS = "workspace_admins"
    WORKSPACE_OWNERS = "workspace_owners"
    SPECIFIC_USERS = "specific_users"
    FINDING_ASSIGNEES = "finding_assignees"
    REMEDIATION_APPROVERS = "remediation_approvers"


class NotificationRuleBase(BaseSchema):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: str
    event_version: str = "1.0"
    is_enabled: bool = True
    recipient_policy: RuleRecipientPolicy = RuleRecipientPolicy.ASSET_OWNERS
    specific_recipient_ids: List[UUID] = Field(default_factory=list)
    severity_filter: List[str] = Field(default_factory=lambda: ["critical", "high", "medium", "low", "info"])
    status_filter: List[str] = Field(default_factory=lambda: ["open", "triaged", "in_progress"])
    enabled_channels: List[str] = Field(default_factory=lambda: ["in_app"])
    deduplication_window_minutes: int = 60
    rate_limit_per_hour: int = 100
    require_acknowledgement: bool = False
    acknowledgement_timeout_hours: Optional[int] = None
    priority: str = "normal"
    action_url_template: Optional[str] = None
    action_label_template: Optional[str] = None
    description: Optional[str] = None


class NotificationRuleCreate(NotificationRuleBase):
    pass


class NotificationRuleUpdate(BaseSchema):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    event_type: Optional[str] = None
    event_version: Optional[str] = None
    is_enabled: Optional[bool] = None
    recipient_policy: Optional[RuleRecipientPolicy] = None
    specific_recipient_ids: Optional[List[UUID]] = None
    severity_filter: Optional[List[str]] = None
    status_filter: Optional[List[str]] = None
    enabled_channels: Optional[List[str]] = None
    deduplication_window_minutes: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    require_acknowledgement: Optional[bool] = None
    acknowledgement_timeout_hours: Optional[int] = None
    priority: Optional[str] = None
    action_url_template: Optional[str] = None
    action_label_template: Optional[str] = None


class NotificationRuleResponse(NotificationRuleBase):
    id: UUID
    is_enabled: bool
    created_by: UUID
    created_at: datetime
    updated_at: datetime


# Notification Deliveries
class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    RETRYING = "retrying"


class NotificationDeliveryBase(BaseSchema):
    notification_id: UUID
    workspace_id: UUID
    channel: str
    recipient_id: UUID
    status: DeliveryStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_category: Optional[str] = None
    provider_message_id: Optional[str] = None
    provider_response: Optional[Dict[str, Any]] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None


class NotificationDeliveryResponse(NotificationDeliveryBase):
    id: UUID
    created_at: datetime
    updated_at: datetime


# Workflow Runs
class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowRunBase(BaseSchema):
    workspace_id: UUID
    workflow_id: str
    workflow_version: str
    input_payload: Dict[str, Any] = Field(default_factory=dict)
    trigger_event_outbox_id: Optional[UUID] = None
    trigger_event_type: Optional[str] = None
    trigger_resource_type: Optional[str] = None
    trigger_resource_id: Optional[UUID] = None
    timeout_minutes: int = 30


class WorkflowRunCreate(WorkflowRunBase):
    pass


class WorkflowRunResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    workflow_id: str
    workflow_version: str
    trigger_event_outbox_id: Optional[UUID] = None
    trigger_event_type: Optional[str] = None
    trigger_resource_type: Optional[str] = None
    trigger_resource_id: Optional[UUID] = None
    input_payload: Dict[str, Any]
    status: WorkflowStatus
    current_action_index: int
    actions_executed: List[Dict[str, Any]]
    output_payload: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    timeout_at: Optional[datetime] = None
    idempotency_key: str
    created_by: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    workflow_id: str
    workflow_version: str
    status: WorkflowStatus
    created_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowRunEventResponse(BaseSchema):
    id: UUID
    workflow_run_id: UUID
    workspace_id: UUID
    action_type: str
    action_name: str
    action_input: Dict[str, Any]
    action_output: Optional[Dict[str, Any]] = None
    status: str
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    executed_at: datetime


class WorkflowRunDetailResponse(BaseSchema):
    run: WorkflowRunResponse
    events: List[WorkflowRunEventResponse] = Field(default_factory=list)


class WorkflowRunRetryRequest(BaseSchema):
    pass


class WorkflowRunRetryResponse(BaseSchema):
    run: WorkflowRunResponse


# Event Outbox
class EventProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class EventOutboxResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    event_type: str
    event_version: str
    event_id: UUID
    correlation_id: Optional[UUID] = None
    occurred_at: datetime
    actor_id: Optional[UUID] = None
    resource_type: Optional[str] = None
    resource_id: Optional[UUID] = None
    payload: Dict[str, Any]
    status: EventProcessingStatus
    attempt_count: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_error_category: Optional[str] = None
    processed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class EventOutboxListResponse(BaseSchema):
    events: List[EventOutboxResponse]
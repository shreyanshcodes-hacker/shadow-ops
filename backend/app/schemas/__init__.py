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
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
    Enum as SQLEnum,
    JSON,
    ARRAY,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.db.base import Base


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


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    firebase_uid: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    owned_workspaces: Mapped[List["Workspace"]] = relationship("Workspace", back_populates="owner", foreign_keys="Workspace.owner_id")
    workspace_memberships: Mapped[List["WorkspaceMember"]] = relationship("WorkspaceMember", back_populates="user", foreign_keys="WorkspaceMember.user_id")
    created_assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="creator", foreign_keys="Asset.created_by")
    approved_authorizations: Mapped[List["AssetAuthorization"]] = relationship("AssetAuthorization", back_populates="verifier", foreign_keys="AssetAuthorization.verified_by")

    def __repr__(self) -> str:
        return f"<Profile(id={self.id}, email={self.email}, firebase_uid={self.firebase_uid})>"


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="free", nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    owner: Mapped["Profile"] = relationship("Profile", back_populates="owned_workspaces", foreign_keys=[owner_id])
    members: Mapped[List["WorkspaceMember"]] = relationship("WorkspaceMember", back_populates="workspace", cascade="all, delete-orphan")
    assets: Mapped[List["Asset"]] = relationship("Asset", back_populates="workspace", cascade="all, delete-orphan")
    authorizations: Mapped[List["AssetAuthorization"]] = relationship("AssetAuthorization", back_populates="workspace", cascade="all, delete-orphan")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="workspace", cascade="all, delete-orphan")
    scan_targets: Mapped[List["ScanTarget"]] = relationship("ScanTarget", back_populates="workspace", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_workspaces_owner_id", "owner_id"),
        Index("idx_workspaces_slug", "slug"),
    )

    def __repr__(self) -> str:
        return f"<Workspace(id={self.id}, name={self.name}, slug={self.slug})>"


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[WorkspaceRole] = mapped_column(SQLEnum(WorkspaceRole), nullable=False)
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    invited_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="members")
    user: Mapped["Profile"] = relationship("Profile", back_populates="workspace_memberships", foreign_keys=[user_id])
    inviter: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[invited_by])

    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", name="uq_ws_members_ws_user"),
        Index("idx_ws_members_ws_id", "workspace_id"),
        Index("idx_ws_members_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<WorkspaceMember(workspace_id={self.workspace_id}, user_id={self.user_id}, role={self.role})>"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[AssetType] = mapped_column(SQLEnum(AssetType), nullable=False, index=True)
    subtype: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    connection_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    credentials_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    criticality: Mapped[AssetCriticality] = mapped_column(SQLEnum(AssetCriticality), default=AssetCriticality.MEDIUM, nullable=False)
    status: Mapped[AssetStatus] = mapped_column(SQLEnum(AssetStatus), default=AssetStatus.ACTIVE, nullable=False, index=True)
    last_scanned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    scan_frequency: Mapped[str] = mapped_column(String(50), default="24 hours", nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="assets")
    creator: Mapped["Profile"] = relationship("Profile", back_populates="created_assets", foreign_keys=[created_by])
    authorization: Mapped[Optional["AssetAuthorization"]] = relationship("AssetAuthorization", back_populates="asset", uselist=False, cascade="all, delete-orphan")
    scans: Mapped[List["Scan"]] = relationship("Scan", back_populates="asset", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_assets_ws_id", "workspace_id"),
        Index("idx_assets_type", "type"),
        Index("idx_assets_status", "status"),
        Index("idx_assets_last_scanned", "last_scanned_at"),
    )

    def __repr__(self) -> str:
        return f"<Asset(id={self.id}, name={self.name}, type={self.type})>"


class AssetAuthorization(Base):
    __tablename__ = "asset_authorizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    authorization_type: Mapped[AuthorizationType] = mapped_column(SQLEnum(AuthorizationType), nullable=False)
    evidence_files: Mapped[List[str]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    evidence_urls: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    authorized_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[AuthorizationStatus] = mapped_column(SQLEnum(AuthorizationStatus), default=AuthorizationStatus.PENDING, nullable=False, index=True)
    verified_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    asset: Mapped["Asset"] = relationship("Asset", back_populates="authorization")
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="authorizations")
    verifier: Mapped[Optional["Profile"]] = relationship("Profile", back_populates="approved_authorizations", foreign_keys=[verified_by])

    __table_args__ = (
        Index("idx_asset_auth_asset_id", "asset_id", unique=True),
        Index("idx_asset_auth_ws_id", "workspace_id"),
        Index("idx_asset_auth_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<AssetAuthorization(id={self.id}, asset_id={self.asset_id}, status={self.status})>"

    @property
    def is_valid(self) -> bool:
        if self.status != AuthorizationStatus.VERIFIED:
            return False
        if self.expires_at and self.expires_at < datetime.utcnow():
            return False
        return True


class ScanProfile(str, enum.Enum):
    QUICK = "QUICK"
    STANDARD = "STANDARD"
    CODE_SECURITY = "CODE_SECURITY"


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


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_type: Mapped[ScanType] = mapped_column(SQLEnum(ScanType), nullable=False)
    scan_profile: Mapped[ScanProfile] = mapped_column(SQLEnum(ScanProfile), default=ScanProfile.CODE_SECURITY, nullable=False)
    status: Mapped[ScanStatus] = mapped_column(SQLEnum(ScanStatus), default=ScanStatus.QUEUED, nullable=False, index=True)
    triggered_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    authorization_confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    phases_completed: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    current_phase: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_percent: Mapped[int] = mapped_column(default=0, nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scan_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="scans")
    asset: Mapped["Asset"] = relationship("Asset")
    triggerer: Mapped["Profile"] = relationship("Profile", foreign_keys=[triggered_by])
    events: Mapped[List["ScanEvent"]] = relationship("ScanEvent", back_populates="scan", cascade="all, delete-orphan")
    findings: Mapped[List["Finding"]] = relationship("Finding", back_populates="scan", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_scans_ws_id", "workspace_id"),
        Index("idx_scans_asset_id", "asset_id"),
        Index("idx_scans_status", "status"),
        Index("idx_scans_triggered_at", "triggered_at"),
        Index("idx_scans_scan_profile", "scan_profile"),
        Index("idx_scans_authorization_confirmed", "authorization_confirmed_at"),
        Index("idx_scans_failed_at", "failed_at"),
        Index("idx_scans_cancelled_at", "cancelled_at"),
    )

    def __repr__(self) -> str:
        return f"<Scan(id={self.id}, asset_id={self.asset_id}, status={self.status}, profile={self.scan_profile})>"


class ScanEvent(Base):
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    phase: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="events")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_scan_events_scan_id_created", "scan_id", "created_at"),
        Index("idx_scan_events_ws_id", "workspace_id"),
        Index("idx_scan_events_event_type", "event_type"),
        Index("idx_scan_events_phase", "phase"),
    )

    def __repr__(self) -> str:
        return f"<ScanEvent(scan_id={self.scan_id}, event_type={self.event_type}, phase={self.phase})>"


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


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    source: Mapped[FindingSource] = mapped_column(SQLEnum(FindingSource), nullable=False)
    source_rule_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(SQLEnum(FindingSeverity), nullable=False, index=True)
    confidence: Mapped[FindingConfidence] = mapped_column(SQLEnum(FindingConfidence), default=FindingConfidence.MEDIUM, nullable=False)
    cwe_ids: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    cve_ids: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    owasp_categories: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    location: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    code_snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    remediation_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[FindingStatus] = mapped_column(SQLEnum(FindingStatus), default=FindingStatus.OPEN, nullable=False, index=True)
    triaged_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    triaged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    risk_factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fixed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    scan: Mapped["Scan"] = relationship("Scan", back_populates="findings")
    asset: Mapped["Asset"] = relationship("Asset")
    triager: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[triaged_by])
    evidence: Mapped[List["FindingEvidence"]] = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_findings_ws_id", "workspace_id"),
        Index("idx_findings_scan_id", "scan_id"),
        Index("idx_findings_asset_id", "asset_id"),
        Index("idx_findings_severity", "severity"),
        Index("idx_findings_status", "status"),
        Index("idx_findings_risk_score", "risk_score"),
        Index("idx_findings_source_rule", "source", "source_rule_id"),
    )

    def __repr__(self) -> str:
        return f"<Finding(id={self.id}, title={self.title}, severity={self.severity})>"


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


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    evidence_type: Mapped[FindingEvidenceType] = mapped_column(SQLEnum(FindingEvidenceType), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    line_start: Mapped[Optional[int]] = mapped_column(nullable=True)
    line_end: Mapped[Optional[int]] = mapped_column(nullable=True)
    storage_object_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_finding_evidence_finding_id", "finding_id"),
        Index("idx_finding_evidence_type", "evidence_type"),
    )

    def __repr__(self) -> str:
        return f"<FindingEvidence(finding_id={self.finding_id}, type={self.evidence_type})>"


class ScanTarget(Base):
    __tablename__ = "scan_targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_path: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), default="repository", nullable=False)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["Profile"] = relationship("Profile", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_scan_targets_ws_id", "workspace_id"),
        Index("idx_scan_targets_is_demo", "is_demo"),
    )

    def __repr__(self) -> str:
        return f"<ScanTarget(id={self.id}, name={self.name}, path={self.target_path}, is_demo={self.is_demo})>"


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


class AiRun(Base):
    __tablename__ = "ai_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    provider: Mapped[AiProviderType] = mapped_column(SQLEnum(AiProviderType), nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    operation: Mapped[AiOperationType] = mapped_column(SQLEnum(AiOperationType), nullable=False)
    status: Mapped[AiRunStatus] = mapped_column(SQLEnum(AiRunStatus), default=AiRunStatus.QUEUED, nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(Text, default="1.0", nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(nullable=True)
    estimated_cost_usd: Mapped[Optional[float]] = mapped_column(nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    scan: Mapped["Scan"] = relationship("Scan")
    finding: Mapped[Optional["Finding"]] = relationship("Finding")
    requester: Mapped["Profile"] = relationship("Profile", foreign_keys=[requested_by])

    __table_args__ = (
        Index("idx_ai_runs_ws_id", "workspace_id"),
        Index("idx_ai_runs_scan_id", "scan_id"),
        Index("idx_ai_runs_finding_id", "finding_id"),
        Index("idx_ai_runs_status", "status"),
        Index("idx_ai_runs_requested_by", "requested_by"),
        Index("idx_ai_runs_input_hash", "input_hash"),
        Index("idx_ai_runs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AiRun(id={self.id}, provider={self.provider}, model={self.model}, status={self.status})>"


class FindingAiAnalysis(Base):
    __tablename__ = "finding_ai_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    ai_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    vulnerability_type: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    severity_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    confidence: Mapped[float] = mapped_column(nullable=False)
    exploitability_assessment: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    impact_assessment: Mapped[str] = mapped_column(Text, nullable=False)
    affected_component: Mapped[str] = mapped_column(Text, nullable=False)
    attack_preconditions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_next_steps: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    uncertainty: Mapped[str] = mapped_column(Text, nullable=False, default="")
    supporting_evidence: Mapped[dict] = mapped_column(JSONB, default=list, nullable=False)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[AiProviderType] = mapped_column(SQLEnum(AiProviderType), nullable=False)
    prompt_version: Mapped[str] = mapped_column(Text, default="1.0", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    finding: Mapped["Finding"] = relationship("Finding")
    ai_run: Mapped["AiRun"] = relationship("AiRun")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_finding_ai_analysis_finding_id", "finding_id"),
        Index("idx_finding_ai_analysis_ai_run_id", "ai_run_id"),
        Index("idx_finding_ai_analysis_workspace_id", "workspace_id"),
    )

    def __repr__(self) -> str:
        return f"<FindingAiAnalysis(finding_id={self.finding_id}, confidence={self.confidence})>"


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


class FindingRelationship(Base):
    __tablename__ = "finding_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    source_finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    target_finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[RelationshipType] = mapped_column(SQLEnum(RelationshipType), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[RelationshipSource] = mapped_column(SQLEnum(RelationshipSource), nullable=False, default=RelationshipSource.DETERMINISTIC, index=True)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    source_finding: Mapped["Finding"] = relationship("Finding", foreign_keys=[source_finding_id])
    target_finding: Mapped["Finding"] = relationship("Finding", foreign_keys=[target_finding_id])

    __table_args__ = (
        Index("idx_finding_rel_ws_id", "workspace_id"),
        Index("idx_finding_rel_source", "source_finding_id"),
        Index("idx_finding_rel_target", "target_finding_id"),
        Index("idx_finding_rel_source_type", "source"),
        UniqueConstraint("source_finding_id", "target_finding_id", "relationship_type", name="uq_finding_relationship"),
    )

    def __repr__(self) -> str:
        return f"<FindingRelationship({self.source_finding_id} -> {self.target_finding_id} [{self.relationship_type}])>"


class AttackPathStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class RiskBand(str, enum.Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AttackPath(Base):
    __tablename__ = "attack_paths"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[AttackPathStatus] = mapped_column(SQLEnum(AttackPathStatus), default=AttackPathStatus.DRAFT, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    severity: Mapped[str] = mapped_column(Text, nullable=False, default="unknown")
    risk_score: Mapped[Optional[int]] = mapped_column(nullable=True)
    risk_model_version: Mapped[str] = mapped_column(Text, default="risk-v1", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    nodes: Mapped[List["AttackPathNode"]] = relationship("AttackPathNode", back_populates="attack_path", cascade="all, delete-orphan", order_by="AttackPathNode.sequence")
    edges: Mapped[List["AttackPathEdge"]] = relationship("AttackPathEdge", back_populates="attack_path", cascade="all, delete-orphan")
    risk_snapshots: Mapped[List["RiskSnapshot"]] = relationship("RiskSnapshot", back_populates="attack_path", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_attack_path_ws_id", "workspace_id"),
        Index("idx_attack_path_asset_id", "asset_id"),
        Index("idx_attack_path_status", "status"),
        Index("idx_attack_path_risk_score", "risk_score"),
    )

    def __repr__(self) -> str:
        return f"<AttackPath(id={self.id}, title={self.title}, risk_score={self.risk_score})>"


class AttackPathNodeType(str, enum.Enum):
    ENTRY = "entry"
    FINDING = "finding"
    BOUNDARY = "boundary"
    IMPACT = "impact"


class AttackPathNode(Base):
    __tablename__ = "attack_path_nodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attack_path_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attack_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True, index=True)
    sequence: Mapped[int] = mapped_column(nullable=False)
    node_type: Mapped[AttackPathNodeType] = mapped_column(SQLEnum(AttackPathNodeType), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    attack_path: Mapped["AttackPath"] = relationship("AttackPath", back_populates="nodes")
    finding: Mapped[Optional["Finding"]] = relationship("Finding")

    __table_args__ = (
        Index("idx_attack_path_node_path_id", "attack_path_id"),
        Index("idx_attack_path_node_finding_id", "finding_id"),
        UniqueConstraint("attack_path_id", "sequence", name="uq_attack_path_node_sequence"),
    )

    def __repr__(self) -> str:
        return f"<AttackPathNode(path={self.attack_path_id}, seq={self.sequence}, type={self.node_type})>"


class AttackPathEdge(Base):
    __tablename__ = "attack_path_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attack_path_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attack_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    source_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_node_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attack_path_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_type: Mapped[RelationshipType] = mapped_column(SQLEnum(RelationshipType), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False)
    source: Mapped[RelationshipSource] = mapped_column(SQLEnum(RelationshipSource), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    attack_path: Mapped["AttackPath"] = relationship("AttackPath", back_populates="edges")
    source_node: Mapped["AttackPathNode"] = relationship("AttackPathNode", foreign_keys=[source_node_id])
    target_node: Mapped["AttackPathNode"] = relationship("AttackPathNode", foreign_keys=[target_node_id])

    __table_args__ = (
        Index("idx_attack_path_edge_path_id", "attack_path_id"),
        Index("idx_attack_path_edge_source", "source_node_id"),
        Index("idx_attack_path_edge_target", "target_node_id"),
    )

    def __repr__(self) -> str:
        return f"<AttackPathEdge({self.source_node_id} -> {self.target_node_id} [{self.relationship_type}])>"


class RiskSnapshot(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    attack_path_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attack_paths.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(nullable=False)
    risk_band: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    attack_path: Mapped["AttackPath"] = relationship("AttackPath", back_populates="risk_snapshots")

    __table_args__ = (
        Index("idx_risk_snapshot_ws_id", "workspace_id"),
        Index("idx_risk_snapshot_path_id", "attack_path_id"),
        Index("idx_risk_snapshot_calculated_at", "calculated_at"),
    )

    def __repr__(self) -> str:
        return f"<RiskSnapshot(path={self.attack_path_id}, score={self.score}, band={self.risk_band})>"


class SecurityTeamRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partial"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class AgentName(str, enum.Enum):
    RECON = "recon"
    VULNERABILITY_ANALYST = "vulnerability_analyst"
    ATTACK_PATH_ANALYST = "attack_path_analyst"
    RISK_ANALYST = "risk_analyst"
    SECURITY_REVIEWER = "security_reviewer"


class AgentRunStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELED = "canceled"


class SecurityTeamRun(Base):
    __tablename__ = "security_team_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[SecurityTeamRunStatus] = mapped_column(SQLEnum(SecurityTeamRunStatus), default=SecurityTeamRunStatus.QUEUED, nullable=False, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    orchestration_version: Mapped[str] = mapped_column(Text, default="security-team-v1", nullable=False)
    team_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    scan: Mapped["Scan"] = relationship("Scan")
    requester: Mapped["Profile"] = relationship("Profile", foreign_keys=[requested_by])
    agent_runs: Mapped[List["AgentRun"]] = relationship("AgentRun", back_populates="team_run", cascade="all, delete-orphan")
    assessment: Mapped[Optional["TeamAssessment"]] = relationship("TeamAssessment", back_populates="team_run", uselist=False, cascade="all, delete-orphan")
    review: Mapped[Optional["TeamReview"]] = relationship("TeamReview", back_populates="team_run", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_security_team_runs_ws_id", "workspace_id"),
        Index("idx_security_team_runs_asset_id", "asset_id"),
        Index("idx_security_team_runs_scan_id", "scan_id"),
        Index("idx_security_team_runs_status", "status"),
        Index("idx_security_team_runs_requested_by", "requested_by"),
        Index("idx_security_team_runs_created_at", "created_at"),
        Index(
            "uq_security_team_run_active",
            "workspace_id", "asset_id", "scan_id", "orchestration_version",
            unique=True,
            postgresql_where=status.in_([SecurityTeamRunStatus.QUEUED, SecurityTeamRunStatus.RUNNING]),
        ),
    )

    def __repr__(self) -> str:
        return f"<SecurityTeamRun(id={self.id}, asset_id={self.asset_id}, status={self.status}, version={self.orchestration_version})>"


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("security_team_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name: Mapped[AgentName] = mapped_column(SQLEnum(AgentName), nullable=False, index=True)
    status: Mapped[AgentRunStatus] = mapped_column(SQLEnum(AgentRunStatus), default=AgentRunStatus.QUEUED, nullable=False, index=True)
    input_reference: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    output: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    team_run: Mapped["SecurityTeamRun"] = relationship("SecurityTeamRun", back_populates="agent_runs")

    __table_args__ = (
        Index("idx_agent_runs_team_run_id", "team_run_id"),
        Index("idx_agent_runs_agent_name", "agent_name"),
        Index("idx_agent_runs_status", "status"),
        UniqueConstraint("team_run_id", "agent_name", name="uq_agent_run_team_agent"),
    )

    def __repr__(self) -> str:
        return f"<AgentRun(team_run={self.team_run_id}, agent={self.agent_name}, status={self.status})>"


class TeamAssessment(Base):
    __tablename__ = "team_assessments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("security_team_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_findings: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    key_attack_paths: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    risk_interpretation: Mapped[str] = mapped_column(Text, nullable=False)
    uncertainties: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    conflicting_assessments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommended_human_actions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    overall_confidence: Mapped[float] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    team_run: Mapped["SecurityTeamRun"] = relationship("SecurityTeamRun", back_populates="assessment")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_team_assessments_ws_id", "workspace_id"),
        Index("idx_team_assessments_team_run_id", "team_run_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<TeamAssessment(team_run={self.team_run_id}, confidence={self.overall_confidence})>"


class TeamReview(Base):
    __tablename__ = "team_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("security_team_runs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    team_run: Mapped["SecurityTeamRun"] = relationship("SecurityTeamRun", back_populates="review")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    reviewer: Mapped["Profile"] = relationship("Profile", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("idx_team_reviews_ws_id", "workspace_id"),
        Index("idx_team_reviews_team_run_id", "team_run_id", unique=True),
        Index("idx_team_reviews_reviewed_by", "reviewed_by"),
    )

    def __repr__(self) -> str:
        return f"<TeamReview(team_run={self.team_run_id}, reviewed_by={self.reviewed_by})>"


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


class RemediationProposal(Base):
    __tablename__ = "remediation_proposals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    source_scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[RemediationStatus] = mapped_column(SQLEnum(RemediationStatus), default=RemediationStatus.DRAFT, nullable=False, index=True)
    proposal_title: Mapped[str] = mapped_column(Text, nullable=False)
    problem_summary: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_solution: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    affected_files: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    patch_reference: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("patch_versions.id", ondelete="SET NULL"), nullable=True)
    validation_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    fix_type: Mapped[RemediationFixType] = mapped_column(SQLEnum(RemediationFixType), default=RemediationFixType.CODE_CHANGE, nullable=False)
    expected_security_benefit: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    compatibility_risks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assumptions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    limitations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_tests: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(default=1, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    finding: Mapped["Finding"] = relationship("Finding")
    source_scan: Mapped["Scan"] = relationship("Scan")
    creator: Mapped["Profile"] = relationship("Profile", foreign_keys=[created_by])
    approver: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[approved_by])
    applier: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[applied_by])
    patch_versions: Mapped[List["PatchVersion"]] = relationship("PatchVersion", back_populates="proposal", cascade="all, delete-orphan", order_by="PatchVersion.version", foreign_keys="PatchVersion.proposal_id")
    validations: Mapped[List["ValidationRun"]] = relationship("ValidationRun", back_populates="proposal", cascade="all, delete-orphan", foreign_keys="ValidationRun.proposal_id")
    approvals: Mapped[List["RemediationApproval"]] = relationship("RemediationApproval", back_populates="proposal", cascade="all, delete-orphan", foreign_keys="RemediationApproval.proposal_id")
    applications: Mapped[List["RemediationApplication"]] = relationship("RemediationApplication", back_populates="proposal", cascade="all, delete-orphan", foreign_keys="RemediationApplication.proposal_id")
    rollbacks: Mapped[List["RemediationRollback"]] = relationship("RemediationRollback", back_populates="proposal", cascade="all, delete-orphan", foreign_keys="RemediationRollback.proposal_id")
    verification_handoff: Mapped[Optional["RemediationVerificationHandoff"]] = relationship("RemediationVerificationHandoff", back_populates="proposal", uselist=False, cascade="all, delete-orphan", foreign_keys="RemediationVerificationHandoff.proposal_id")

    __table_args__ = (
        Index("idx_remediation_proposals_ws_id", "workspace_id"),
        Index("idx_remediation_proposals_asset_id", "asset_id"),
        Index("idx_remediation_proposals_finding_id", "finding_id"),
        Index("idx_remediation_proposals_scan_id", "source_scan_id"),
        Index("idx_remediation_proposals_status", "status"),
        Index("idx_remediation_proposals_created_by", "created_by"),
        Index("idx_remediation_proposals_approved_by", "approved_by"),
        Index("idx_remediation_proposals_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<RemediationProposal(id={self.id}, finding_id={self.finding_id}, status={self.status})>"


class PatchVersion(Base):
    __tablename__ = "patch_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    unified_diff: Mapped[str] = mapped_column(Text, nullable=False)
    file_changes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    patch_hash: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    base_revision: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    is_current: Mapped[bool] = mapped_column(default=False, nullable=False)
    superseded_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("patch_versions.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="patch_versions", foreign_keys="PatchVersion.proposal_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["Profile"] = relationship("Profile", foreign_keys=[created_by])
    validations: Mapped[List["ValidationRun"]] = relationship("ValidationRun", back_populates="patch_version", cascade="all, delete-orphan", foreign_keys="ValidationRun.patch_version_id")
    approvals: Mapped[List["RemediationApproval"]] = relationship("RemediationApproval", back_populates="patch_version", cascade="all, delete-orphan", foreign_keys="RemediationApproval.patch_version_id")
    applications: Mapped[List["RemediationApplication"]] = relationship("RemediationApplication", back_populates="patch_version", cascade="all, delete-orphan", foreign_keys="RemediationApplication.patch_version_id")

    __table_args__ = (
        UniqueConstraint("proposal_id", "version", name="uq_patch_version_proposal_version"),
        Index("idx_patch_versions_proposal_id", "proposal_id"),
        Index("idx_patch_versions_workspace_id", "workspace_id"),
        Index("idx_patch_versions_patch_hash", "patch_hash"),
    )

    def __repr__(self) -> str:
        return f"<PatchVersion(proposal_id={self.proposal_id}, version={self.version}, hash={self.patch_hash[:16]}...)>"


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patch_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ValidationStatus] = mapped_column(SQLEnum(ValidationStatus), default=ValidationStatus.PENDING, nullable=False, index=True)
    check_type: Mapped[ValidationCheckType] = mapped_column(SQLEnum(ValidationCheckType), nullable=False, index=True)
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="validations", foreign_keys="ValidationRun.proposal_id")
    patch_version: Mapped["PatchVersion"] = relationship("PatchVersion", back_populates="validations", foreign_keys="ValidationRun.patch_version_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_validation_runs_proposal_id", "proposal_id"),
        Index("idx_validation_runs_patch_version_id", "patch_version_id"),
        Index("idx_validation_runs_workspace_id", "workspace_id"),
        Index("idx_validation_runs_status", "status"),
        Index("idx_validation_runs_check_type", "check_type"),
    )

    def __repr__(self) -> str:
        return f"<ValidationRun(proposal_id={self.proposal_id}, check_type={self.check_type}, status={self.status})>"


class RemediationApproval(Base):
    __tablename__ = "remediation_approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patch_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    approved_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    conditions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    patch_hash: Mapped[str] = mapped_column(Text, nullable=False)
    proposal_version: Mapped[int] = mapped_column(nullable=False)
    validation_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="approvals", foreign_keys="RemediationApproval.proposal_id")
    patch_version: Mapped["PatchVersion"] = relationship("PatchVersion", back_populates="approvals", foreign_keys="RemediationApproval.patch_version_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    approver: Mapped["Profile"] = relationship("Profile", foreign_keys=[approved_by])

    __table_args__ = (
        Index("idx_remediation_approvals_proposal_id", "proposal_id"),
        Index("idx_remediation_approvals_patch_version_id", "patch_version_id"),
        Index("idx_remediation_approvals_workspace_id", "workspace_id"),
        Index("idx_remediation_approvals_approved_by", "approved_by"),
        Index("idx_remediation_approvals_decision", "decision"),
    )

    def __repr__(self) -> str:
        return f"<RemediationApproval(proposal_id={self.proposal_id}, decision={self.decision}, approved_by={self.approved_by})>"


class RemediationApplication(Base):
    __tablename__ = "remediation_applications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("patch_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    approval_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_approvals.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[ApplicationStatus] = mapped_column(SQLEnum(ApplicationStatus), default=ApplicationStatus.PENDING, nullable=False, index=True)
    target_revision: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    applied_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    result_diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_files: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    validation_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)

# Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="applications", foreign_keys="RemediationApplication.proposal_id")
    patch_version: Mapped["PatchVersion"] = relationship("PatchVersion", back_populates="applications", foreign_keys="RemediationApplication.patch_version_id")
    approval: Mapped["RemediationApproval"] = relationship("RemediationApproval", foreign_keys="RemediationApplication.approval_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    applier: Mapped["Profile"] = relationship("Profile", foreign_keys=[applied_by])
    rollbacks: Mapped[List["RemediationRollback"]] = relationship("RemediationRollback", back_populates="application", cascade="all, delete-orphan", foreign_keys="RemediationRollback.application_id")
    verification_handoff: Mapped[Optional["RemediationVerificationHandoff"]] = relationship("RemediationVerificationHandoff", back_populates="application", uselist=False, cascade="all, delete-orphan", foreign_keys="RemediationVerificationHandoff.application_id")

    __table_args__ = (
        Index("idx_remediation_applications_proposal_id", "proposal_id"),
        Index("idx_remediation_applications_patch_version_id", "patch_version_id"),
        Index("idx_remediation_applications_approval_id", "approval_id"),
        Index("idx_remediation_applications_workspace_id", "workspace_id"),
        Index("idx_remediation_applications_asset_id", "asset_id"),
        Index("idx_remediation_applications_applied_by", "applied_by"),
        Index("idx_remediation_applications_idempotency_key", "idempotency_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<RemediationApplication(proposal_id={self.proposal_id}, status={self.status}, applied_by={self.applied_by})>"


class RemediationRollback(Base):
    __tablename__ = "remediation_rollbacks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[RollbackStatus] = mapped_column(SQLEnum(RollbackStatus), default=RollbackStatus.PENDING, nullable=False, index=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    checkpoint_ref: Mapped[str] = mapped_column(Text, nullable=False)
    verification_diff: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="rollbacks", foreign_keys="RemediationRollback.proposal_id")
    application: Mapped["RemediationApplication"] = relationship("RemediationApplication", back_populates="rollbacks", foreign_keys="RemediationRollback.application_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    requester: Mapped["Profile"] = relationship("Profile", foreign_keys=[requested_by])

    __table_args__ = (
        Index("idx_remediation_rollbacks_proposal_id", "proposal_id"),
        Index("idx_remediation_rollbacks_application_id", "application_id"),
        Index("idx_remediation_rollbacks_workspace_id", "workspace_id"),
        Index("idx_remediation_rollbacks_requested_by", "requested_by"),
    )

    def __repr__(self) -> str:
        return f"<RemediationRollback(proposal_id={self.proposal_id}, status={self.status})>"


class RemediationVerificationHandoff(Base):
    __tablename__ = "remediation_verification_handoff"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_hash: Mapped[str] = mapped_column(Text, nullable=False)
    repository_revision: Mapped[str] = mapped_column(Text, nullable=False)
    changed_files: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    validation_results: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    original_finding_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    applied_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    verification_requested: Mapped[bool] = mapped_column(default=False, nullable=False)
    verification_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verification_result: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, default=VerificationHandoffStatus.PENDING_VERIFICATION.value, nullable=False, index=True)

    # Relationships
    proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", back_populates="verification_handoff", foreign_keys="RemediationVerificationHandoff.proposal_id")
    application: Mapped["RemediationApplication"] = relationship("RemediationApplication", back_populates="verification_handoff", foreign_keys="RemediationVerificationHandoff.application_id")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    finding: Mapped["Finding"] = relationship("Finding", foreign_keys="RemediationVerificationHandoff.finding_id")
    asset: Mapped["Asset"] = relationship("Asset", foreign_keys="RemediationVerificationHandoff.asset_id")
    applier: Mapped["Profile"] = relationship("Profile", foreign_keys=[applied_by])

    __table_args__ = (
        Index("idx_verification_handoff_proposal_id", "proposal_id"),
        Index("idx_verification_handoff_application_id", "application_id"),
        Index("idx_verification_handoff_workspace_id", "workspace_id"),
        Index("idx_verification_handoff_finding_id", "finding_id"),
        Index("idx_verification_handoff_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<RemediationVerificationHandoff(proposal_id={self.proposal_id}, status={self.status})>"


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


class VerificationJob(Base):
    __tablename__ = "verification_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    remediation_proposal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_proposals.id", ondelete="CASCADE"), nullable=False, index=True)
    remediation_application_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("remediation_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    patch_hash: Mapped[str] = mapped_column(Text, nullable=False)
    source_revision: Mapped[str] = mapped_column(Text, nullable=False)
    target_revision: Mapped[str] = mapped_column(Text, nullable=False)
    verification_engine_version: Mapped[str] = mapped_column(Text, default="verification-v1", nullable=False)
    policy_version: Mapped[str] = mapped_column(Text, default="verification-policy-v1", nullable=False)
    status: Mapped[VerificationStatus] = mapped_column(SQLEnum(VerificationStatus), default=VerificationStatus.QUEUED, nullable=False, index=True)
    overall_outcome: Mapped[Optional[VerificationOutcome]] = mapped_column(SQLEnum(VerificationOutcome), nullable=True, index=True)
    original_vulnerability_outcome: Mapped[Optional[CheckStatus]] = mapped_column(SQLEnum(CheckStatus), nullable=True)
    regression_analysis_outcome: Mapped[Optional[CheckStatus]] = mapped_column(SQLEnum(CheckStatus), nullable=True)
    scanner_execution_outcome: Mapped[Optional[CheckStatus]] = mapped_column(SQLEnum(CheckStatus), nullable=True)
    test_execution_outcome: Mapped[Optional[CheckStatus]] = mapped_column(SQLEnum(CheckStatus), nullable=True)
    evidence_comparison_outcome: Mapped[Optional[CheckStatus]] = mapped_column(SQLEnum(CheckStatus), nullable=True)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    canceled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    asset: Mapped["Asset"] = relationship("Asset")
    finding: Mapped["Finding"] = relationship("Finding")
    remediation_proposal: Mapped["RemediationProposal"] = relationship("RemediationProposal", foreign_keys="VerificationJob.remediation_proposal_id")
    remediation_application: Mapped["RemediationApplication"] = relationship("RemediationApplication", foreign_keys="VerificationJob.remediation_application_id")
    requester: Mapped["Profile"] = relationship("Profile", foreign_keys=[requested_by])
    baselines: Mapped[List["VerificationBaseline"]] = relationship("VerificationBaseline", back_populates="verification_job", cascade="all, delete-orphan")
    checks: Mapped[List["VerificationCheck"]] = relationship("VerificationCheck", back_populates="verification_job", cascade="all, delete-orphan")
    comparisons: Mapped[List["EvidenceComparison"]] = relationship("EvidenceComparison", back_populates="verification_job", cascade="all, delete-orphan")
    reviews: Mapped[List["VerificationReview"]] = relationship("VerificationReview", back_populates="verification_job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_verification_jobs_ws_id", "workspace_id"),
        Index("idx_verification_jobs_asset_id", "asset_id"),
        Index("idx_verification_jobs_finding_id", "finding_id"),
        Index("idx_verification_jobs_proposal_id", "remediation_proposal_id"),
        Index("idx_verification_jobs_application_id", "remediation_application_id"),
        Index("idx_verification_jobs_status", "status"),
        Index("idx_verification_jobs_requested_by", "requested_by"),
        Index("idx_verification_jobs_idempotency_key", "idempotency_key", unique=True),
    )

    def __repr__(self) -> str:
        return f"<VerificationJob(id={self.id}, finding_id={self.finding_id}, status={self.status}, outcome={self.overall_outcome})>"


class VerificationBaseline(Base):
    __tablename__ = "verification_baselines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    original_finding_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    original_evidence: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    scanner_version: Mapped[str] = mapped_column(Text, nullable=False)
    scanner_config: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    rule_ids: Mapped[list] = mapped_column(ARRAY(Text), default=list, nullable=False)
    finding_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    evidence_hashes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    repository_revision: Mapped[str] = mapped_column(Text, nullable=False)
    scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id", ondelete="SET NULL"), nullable=True)
    pre_patch_scan_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    capture_method: Mapped[str] = mapped_column(Text, default="handoff", nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    captured_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)

    # Relationships
    verification_job: Mapped["VerificationJob"] = relationship("VerificationJob", back_populates="baselines")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    finding: Mapped["Finding"] = relationship("Finding")
    scan: Mapped[Optional["Scan"]] = relationship("Scan")
    capturer: Mapped["Profile"] = relationship("Profile", foreign_keys=[captured_by])

    __table_args__ = (
        Index("idx_verification_baselines_job_id", "verification_job_id"),
        Index("idx_verification_baselines_finding_id", "finding_id"),
        Index("idx_verification_baselines_fingerprint", "finding_fingerprint"),
    )

    def __repr__(self) -> str:
        return f"<VerificationBaseline(job_id={self.verification_job_id}, fingerprint={self.finding_fingerprint[:16]}...)>"


class VerificationCheck(Base):
    __tablename__ = "verification_checks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    check_type: Mapped[CheckType] = mapped_column(SQLEnum(CheckType), nullable=False, index=True)
    check_name: Mapped[str] = mapped_column(Text, nullable=False)
    check_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[CheckStatus] = mapped_column(SQLEnum(CheckStatus), default=CheckStatus.PENDING, nullable=False, index=True)
    command: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    verification_job: Mapped["VerificationJob"] = relationship("VerificationJob", back_populates="checks")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_verification_checks_job_id", "verification_job_id"),
        Index("idx_verification_checks_type", "check_type"),
        Index("idx_verification_checks_status", "status"),
        Index("idx_verification_checks_name", "check_name"),
    )

    def __repr__(self) -> str:
        return f"<VerificationCheck(job_id={self.verification_job_id}, type={self.check_type}, name={self.check_name}, status={self.status})>"


class EvidenceComparison(Base):
    __tablename__ = "evidence_comparisons"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    baseline_finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    post_patch_finding_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("findings.id", ondelete="SET NULL"), nullable=True)
    baseline_fingerprint: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    post_patch_fingerprint: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    scanner_rule_id: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_file_path: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_location: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    post_patch_location: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    baseline_evidence_hash: Mapped[str] = mapped_column(Text, nullable=False)
    post_patch_evidence_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[ComparisonCategory] = mapped_column(SQLEnum(ComparisonCategory), nullable=False, index=True)
    match_confidence: Mapped[Optional[float]] = mapped_column(nullable=True)
    match_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    relationship_to_original: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    verification_job: Mapped["VerificationJob"] = relationship("VerificationJob", back_populates="comparisons")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    baseline_finding: Mapped[Optional["Finding"]] = relationship("Finding", foreign_keys=[baseline_finding_id])
    post_patch_finding: Mapped[Optional["Finding"]] = relationship("Finding", foreign_keys=[post_patch_finding_id])

    __table_args__ = (
        Index("idx_evidence_comparisons_job_id", "verification_job_id"),
        Index("idx_evidence_comparisons_category", "category"),
        Index("idx_evidence_comparisons_baseline_fp", "baseline_fingerprint"),
        Index("idx_evidence_comparisons_post_patch_fp", "post_patch_fingerprint"),
    )

    def __repr__(self) -> str:
        return f"<EvidenceComparison(job_id={self.verification_job_id}, rule={self.scanner_rule_id}, category={self.category})>"


class VerificationPolicy(Base):
    __tablename__ = "verification_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_config: Mapped[dict] = mapped_column(JSONB, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    creator: Mapped["Profile"] = relationship("Profile", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_verification_policies_version", "version"),
        Index("idx_verification_policies_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<VerificationPolicy(version={self.version}, active={self.is_active})>"


class VerificationReview(Base):
    __tablename__ = "verification_reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("verification_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    decision: Mapped[ReviewDecision] = mapped_column(SQLEnum(ReviewDecision), nullable=False, index=True)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    policy_version: Mapped[str] = mapped_column(Text, nullable=False)
    baseline_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    comparison_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    check_results_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    verification_job: Mapped["VerificationJob"] = relationship("VerificationJob", back_populates="reviews")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    reviewer: Mapped["Profile"] = relationship("Profile", foreign_keys=[reviewed_by])

    __table_args__ = (
        Index("idx_verification_reviews_job_id", "verification_job_id"),
        Index("idx_verification_reviews_workspace_id", "workspace_id"),
        Index("idx_verification_reviews_reviewed_by", "reviewed_by"),
        Index("idx_verification_reviews_decision", "decision"),
    )

    def __repr__(self) -> str:
        return f"<VerificationReview(job_id={self.verification_job_id}, decision={self.decision}, reviewed_by={self.reviewed_by})>"


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


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    report_type: Mapped[ReportType] = mapped_column(SQLEnum(ReportType), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[ReportFormat] = mapped_column(SQLEnum(ReportFormat), default=ReportFormat.PDF, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(SQLEnum(ReportStatus), default=ReportStatus.PENDING, nullable=False, index=True)
    schema_version: Mapped[str] = mapped_column(Text, default="report-v1", nullable=False)
    risk_engine_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    verification_policy_version: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    data_cutoff: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    included_asset_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    severity_filters: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    source_record_references: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    completeness: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    limitations: Mapped[List[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    storage_object_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    generator: Mapped["Profile"] = relationship("Profile", foreign_keys=[generated_by])
    sections: Mapped[List["ReportSection"]] = relationship("ReportSection", back_populates="report", cascade="all, delete-orphan", order_by="ReportSection.section_order")
    exports: Mapped[List["ReportExport"]] = relationship("ReportExport", back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_reports_workspace_id", "workspace_id"),
        Index("idx_reports_type", "report_type"),
        Index("idx_reports_status", "status"),
        Index("idx_reports_generated_by", "generated_by"),
        Index("idx_reports_created_at", "created_at"),
        Index("idx_reports_period", "period_start", "period_end"),
        Index("idx_reports_expires_at", "expires_at"),
    )

    def __repr__(self) -> str:
        return f"<Report(id={self.id}, type={self.report_type}, status={self.status})>"


class ReportSection(Base):
    __tablename__ = "report_sections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    section_key: Mapped[str] = mapped_column(Text, nullable=False)
    section_title: Mapped[str] = mapped_column(Text, nullable=False)
    section_order: Mapped[int] = mapped_column(default=0, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    data_references: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    report: Mapped["Report"] = relationship("Report", back_populates="sections")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_report_sections_report_id", "report_id"),
        Index("idx_report_sections_workspace_id", "workspace_id"),
        UniqueConstraint("report_id", "section_key", name="uq_report_section_key"),
    )

    def __repr__(self) -> str:
        return f"<ReportSection(report_id={self.report_id}, key={self.section_key})>"


class ReportExport(Base):
    __tablename__ = "report_exports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    format: Mapped[ReportFormat] = mapped_column(SQLEnum(ReportFormat), nullable=False)
    storage_object_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    storage_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(nullable=True)
    checksum: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    report: Mapped["Report"] = relationship("Report", back_populates="exports")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    generator: Mapped["Profile"] = relationship("Profile", foreign_keys=[generated_by])

    __table_args__ = (
        Index("idx_report_exports_report_id", "report_id"),
        Index("idx_report_exports_workspace_id", "workspace_id"),
        Index("idx_report_exports_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ReportExport(report_id={self.report_id}, format={self.format})>"


# =============================================================================
# Stage 11: Notification Models
# =============================================================================

class NotificationChannel(str, enum.Enum):
    IN_APP = "in_app"
    EMAIL = "email"


class NotificationPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    RETRYING = "retrying"


class EventProcessingStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class RuleRecipientPolicy(str, enum.Enum):
    ASSET_OWNERS = "asset_owners"
    ASSET_MEMBERS = "asset_members"
    WORKSPACE_ADMINS = "workspace_admins"
    WORKSPACE_OWNERS = "workspace_owners"
    SPECIFIC_USERS = "specific_users"
    FINDING_ASSIGNEES = "finding_assignees"
    REMEDIATION_APPROVERS = "remediation_approvers"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EventOutbox(Base):
    __tablename__ = "event_outbox"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_version: Mapped[str] = mapped_column(Text, default="1.0", nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True)
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    resource_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[EventProcessingStatus] = mapped_column(SQLEnum(EventProcessingStatus), default=EventProcessingStatus.PENDING, nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=5, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    actor: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[actor_id])

    __table_args__ = (
        Index("idx_event_outbox_workspace_status", "workspace_id", "status"),
        Index("idx_event_outbox_status_next_retry", "status", "next_retry_at", postgresql_where=status.in_([EventProcessingStatus.PENDING, EventProcessingStatus.PROCESSING])),
        Index("idx_event_outbox_correlation_id", "correlation_id"),
        Index("idx_event_outbox_event_type", "event_type"),
        Index("idx_event_outbox_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<EventOutbox(id={self.id}, type={self.event_type}, status={self.status})>"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    reference_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    channels: Mapped[List[str]] = mapped_column(ARRAY(Text), default=["in_app"], nullable=False)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Stage 11 additions
    event_outbox_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("event_outbox.id", ondelete="SET NULL"), nullable=True)
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    priority: Mapped[str] = mapped_column(Text, default="normal", nullable=False)
    action_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deduplication_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    user: Mapped["Profile"] = relationship("Profile", foreign_keys=[user_id])
    event_outbox: Mapped[Optional["EventOutbox"]] = relationship("EventOutbox")

    __table_args__ = (
        Index("idx_notifications_user_id_read", "user_id", "read_at"),
        Index("idx_notifications_ws_id_created", "workspace_id", "created_at"),
        Index("idx_notifications_event_outbox_id", "event_outbox_id"),
        Index("idx_notifications_rule_id", "rule_id"),
        Index("idx_notifications_deduplication_key", "deduplication_key"),
        Index("idx_notifications_priority", "priority"),
        Index("idx_notifications_expires_at", "expires_at", postgresql_where=expires_at.is_not(None)),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, type={self.type}, user_id={self.user_id})>"

    @property
    def is_read(self) -> bool:
        return self.read_at is not None


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


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    email_enabled: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    user: Mapped["Profile"] = relationship("Profile", foreign_keys=[user_id])

    __table_args__ = (
        UniqueConstraint("user_id", "category", name="uq_notification_prefs_user_category"),
        Index("idx_notification_prefs_workspace", "workspace_id"),
        Index("idx_notification_prefs_user", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<NotificationPreference(user_id={self.user_id}, category={self.category})>"


class RuleRecipientPolicy(str, enum.Enum):
    ASSET_OWNERS = "asset_owners"
    ASSET_MEMBERS = "asset_members"
    WORKSPACE_ADMINS = "workspace_admins"
    WORKSPACE_OWNERS = "workspace_owners"
    SPECIFIC_USERS = "specific_users"
    FINDING_ASSIGNEES = "finding_assignees"
    REMEDIATION_APPROVERS = "remediation_approvers"


class NotificationRule(Base):
    __tablename__ = "notification_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    event_version: Mapped[str] = mapped_column(Text, default="1.0", nullable=False)
    is_enabled: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    recipient_policy: Mapped[RuleRecipientPolicy] = mapped_column(SQLEnum(RuleRecipientPolicy), default=RuleRecipientPolicy.ASSET_OWNERS, nullable=False)
    specific_recipient_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    severity_filter: Mapped[List[str]] = mapped_column(ARRAY(Text), default=["critical", "high", "medium", "low", "info"], nullable=False)
    status_filter: Mapped[List[str]] = mapped_column(ARRAY(Text), default=["open", "triaged", "in_progress"], nullable=False)
    enabled_channels: Mapped[List[str]] = mapped_column(ARRAY(Text), default=["in_app"], nullable=False)
    deduplication_window_minutes: Mapped[int] = mapped_column(default=60, nullable=False)
    rate_limit_per_hour: Mapped[int] = mapped_column(default=100, nullable=False)
    require_acknowledgement: Mapped[bool] = mapped_column(default=False, nullable=False)
    acknowledgement_timeout_hours: Mapped[Optional[int]] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(Text, default="normal", nullable=False)
    action_url_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_label_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    creator: Mapped["Profile"] = relationship("Profile", foreign_keys=[created_by])

    __table_args__ = (
        Index("idx_notification_rules_workspace", "workspace_id"),
        Index("idx_notification_rules_event_type", "event_type"),
        Index("idx_notification_rules_enabled", "is_enabled", postgresql_where=is_enabled == True),
    )

    def __repr__(self) -> str:
        return f"<NotificationRule(id={self.id}, event_type={self.event_type})>"


class DeliveryStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    RETRYING = "retrying"


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[DeliveryStatus] = mapped_column(SQLEnum(DeliveryStatus), default=DeliveryStatus.PENDING, nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(default=5, nullable=False)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_error_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    provider_response: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    notification: Mapped["Notification"] = relationship("Notification", backref="deliveries")
    workspace: Mapped["Workspace"] = relationship("Workspace")
    recipient: Mapped["Profile"] = relationship("Profile", foreign_keys=[recipient_id])

    __table_args__ = (
        Index("idx_notification_deliveries_notification", "notification_id"),
        Index("idx_notification_deliveries_workspace_status", "workspace_id", "status"),
        Index("idx_notification_deliveries_status_next_retry", "status", "next_retry_at", postgresql_where=status.in_([DeliveryStatus.PENDING, DeliveryStatus.RETRYING])),
        Index("idx_notification_deliveries_recipient", "recipient_id"),
    )

    def __repr__(self) -> str:
        return f"<NotificationDelivery(id={self.id}, notification_id={self.notification_id}, channel={self.channel})>"


class WorkflowStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    workflow_version: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_event_outbox_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("event_outbox.id", ondelete="SET NULL"), nullable=True)
    trigger_event_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_resource_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    trigger_resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    status: Mapped[WorkflowStatus] = mapped_column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False, index=True)
    current_action_index: Mapped[int] = mapped_column(default=0, nullable=False)
    actions_executed: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_category: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    timeout_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True, index=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    workspace: Mapped["Workspace"] = relationship("Workspace")
    trigger_event_outbox: Mapped[Optional["EventOutbox"]] = relationship("EventOutbox")
    creator: Mapped[Optional["Profile"]] = relationship("Profile", foreign_keys=[created_by])
    events: Mapped[List["WorkflowRunEvent"]] = relationship("WorkflowRunEvent", back_populates="workflow_run", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_workflow_runs_idempotency_key"),
        Index("idx_workflow_runs_workspace", "workspace_id"),
        Index("idx_workflow_runs_status", "status"),
        Index("idx_workflow_runs_trigger_event", "trigger_event_outbox_id"),
        Index("idx_workflow_runs_workflow_id", "workflow_id"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowRun(id={self.id}, workflow_id={self.workflow_id}, status={self.status})>"


class WorkflowRunEvent(Base):
    __tablename__ = "workflow_run_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_input: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    action_output: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(nullable=True)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    workflow_run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="events")
    workspace: Mapped["Workspace"] = relationship("Workspace")

    __table_args__ = (
        Index("idx_workflow_run_events_run", "workflow_run_id"),
        Index("idx_workflow_run_events_workspace", "workspace_id"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowRunEvent(id={self.id}, run_id={self.workflow_run_id}, action={self.action_name})>"
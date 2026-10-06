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
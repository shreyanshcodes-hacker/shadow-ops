from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    ProfileRepository,
    WorkspaceRepository,
    WorkspaceMemberRepository,
    AssetRepository,
    AssetAuthorizationRepository,
    ScanRepository,
    ScanEventRepository,
    FindingRepository,
    FindingEvidenceRepository,
    ScanTargetRepository,
)
from app.models import (
    Workspace, WorkspaceMember, Asset, AssetAuthorization, 
    WorkspaceRole, AuthorizationStatus, AuthorizationType,
    Scan, ScanEvent, Finding, FindingEvidence, ScanTarget,
    ScanStatus, ScanProfile, ScanType, ScanEventType,
    FindingSource, FindingSeverity, FindingConfidence, FindingStatus, FindingEvidenceType
)
from app.schemas import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    AssetCreate,
    AssetUpdate,
    AuthorizationCreate,
    ScanCreate,
    ScanUpdate,
    ScanTargetCreate,
    ScanTargetUpdate,
)


class ProfileService:
    def __init__(self, db: AsyncSession):
        self.repo = ProfileRepository(db)

    async def get_or_create_from_firebase(self, firebase_uid: str, email: str, display_name: Optional[str] = None, avatar_url: Optional[str] = None):
        profile = await self.repo.get_by_firebase_uid(firebase_uid)
        if not profile:
            from app.models import Profile, UserRole
            profile = Profile(
                firebase_uid=firebase_uid,
                email=email,
                display_name=display_name,
                avatar_url=avatar_url,
                role=UserRole.USER,
            )
            profile = await self.repo.create(profile)
        return profile

    async def get_profile(self, profile_id: UUID):
        return await self.repo.get_by_id(profile_id)


class WorkspaceService:
    def __init__(self, db: AsyncSession):
        self.workspace_repo = WorkspaceRepository(db)
        self.member_repo = WorkspaceMemberRepository(db)

    async def create_workspace(self, owner_id: UUID, data: WorkspaceCreate) -> Workspace:
        # Generate slug if not provided
        slug = data.slug
        if not slug:
            base_slug = data.name.lower().replace(" ", "-")
            base_slug = "".join(c for c in base_slug if c.isalnum() or c == "-")
            slug = base_slug[:50]

        # Ensure slug is unique
        existing = await self.workspace_repo.get_by_slug(slug)
        counter = 1
        original_slug = slug
        while existing:
            slug = f"{original_slug}-{counter}"
            counter += 1
            existing = await self.workspace_repo.get_by_slug(slug)

        workspace = Workspace(
            name=data.name,
            slug=slug,
            owner_id=owner_id,
            plan="free",
            settings={},
        )
        workspace = await self.workspace_repo.create(workspace)

        # Add owner as member
        owner_member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
            invited_by=owner_id,
            joined_at=datetime.utcnow(),
        )
        await self.member_repo.create(owner_member)

        return workspace

    async def get_workspace(self, workspace_id: UUID) -> Optional[Workspace]:
        return await self.workspace_repo.get_by_id(workspace_id)

    async def list_user_workspaces(self, user_id: UUID) -> List[Workspace]:
        return await self.workspace_repo.get_user_workspaces(user_id)

    async def update_workspace(self, workspace_id: UUID, data: WorkspaceUpdate) -> Optional[Workspace]:
        update_data = data.model_dump(exclude_unset=True)
        return await self.workspace_repo.update(workspace_id, update_data)

    async def delete_workspace(self, workspace_id: UUID) -> bool:
        return await self.workspace_repo.soft_delete(workspace_id)

    async def get_member(self, workspace_id: UUID, user_id: UUID) -> Optional[WorkspaceMember]:
        return await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)

    async def list_members(self, workspace_id: UUID) -> List[WorkspaceMember]:
        return await self.member_repo.get_workspace_members(workspace_id)

    async def invite_member(self, workspace_id: UUID, inviter_id: UUID, data: WorkspaceMemberCreate) -> WorkspaceMember:
        # Check if user exists
        from app.repositories import ProfileRepository
        profile_repo = ProfileRepository(self.member_repo.db)
        user = await profile_repo.get_by_email(data.email)
        if not user:
            raise ValueError(f"User with email {data.email} not found")

        # Check if already a member
        existing = await self.member_repo.get_by_workspace_and_user(workspace_id, user.id)
        if existing:
            raise ValueError("User is already a member of this workspace")

        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user.id,
            role=data.role,
            invited_by=inviter_id,
        )
        return await self.member_repo.create(member)

    async def update_member_role(self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> Optional[WorkspaceMember]:
        return await self.member_repo.update_role(workspace_id, user_id, role)

    async def remove_member(self, workspace_id: UUID, user_id: UUID) -> bool:
        # Prevent removing owner
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if member and member.role == WorkspaceRole.OWNER:
            raise ValueError("Cannot remove workspace owner")
        return await self.member_repo.remove(workspace_id, user_id)

    async def accept_invitation(self, workspace_id: UUID, user_id: UUID) -> Optional[WorkspaceMember]:
        return await self.member_repo.set_joined_at(workspace_id, user_id)


class AssetService:
    def __init__(self, db: AsyncSession):
        self.repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)

    async def create_asset(self, workspace_id: UUID, creator_id: UUID, data: AssetCreate) -> Asset:
        asset = Asset(
            workspace_id=workspace_id,
            created_by=creator_id,
            name=data.name,
            type=data.type,
            subtype=data.subtype,
            connection_config=data.connection_config,
            credentials_ref=data.credentials_ref,
            criticality=data.criticality,
            tags=data.tags,
            status=Asset.Status.ACTIVE,
        )
        return await self.repo.create(asset)

    async def get_asset(self, asset_id: UUID) -> Optional[Asset]:
        return await self.repo.get_by_id(asset_id)

    async def list_assets(self, workspace_id: UUID) -> List[Asset]:
        return await self.repo.get_by_workspace(workspace_id)

    async def update_asset(self, asset_id: UUID, data: AssetUpdate) -> Optional[Asset]:
        update_data = data.model_dump(exclude_unset=True)
        return await self.repo.update(asset_id, update_data)

    async def delete_asset(self, asset_id: UUID) -> bool:
        return await self.repo.soft_delete(asset_id)

    async def get_authorization(self, asset_id: UUID) -> Optional[AssetAuthorization]:
        return await self.auth_repo.get_by_asset(asset_id)

    async def create_authorization(self, asset_id: UUID, data: AuthorizationCreate) -> AssetAuthorization:
        auth = AssetAuthorization(
            asset_id=asset_id,
            workspace_id=data.workspace_id,  # This will be validated
            authorization_type=data.authorization_type,
            evidence_files=data.evidence_files,
            evidence_urls=data.evidence_urls,
            authorized_by=data.authorized_by,
            authorized_at=data.authorized_at,
            expires_at=data.expires_at,
            notes=data.notes,
            status=AuthorizationStatus.PENDING,
        )
        return await self.auth_repo.create(auth)

    async def verify_authorization(self, asset_id: UUID, verified_by: UUID) -> Optional[AssetAuthorization]:
        return await self.auth_repo.verify(asset_id, verified_by)

    async def reject_authorization(self, asset_id: UUID, notes: Optional[str] = None) -> Optional[AssetAuthorization]:
        return await self.auth_repo.reject(asset_id, notes)

    async def is_authorized_for_scan(self, asset_id: UUID) -> bool:
        return await self.auth_repo.is_authorized_for_scan(asset_id)

    async def update_last_scanned(self, asset_id: UUID):
        await self.repo.update_last_scanned(asset_id)


from app.services.remediation import RemediationService
from app.services.patch import PatchProcessor
from app.services.validation import ValidationPipeline
from app.services.approval import ApprovalService
from app.services.application import PatchApplicationAdapter
from app.services.rollback import RollbackService
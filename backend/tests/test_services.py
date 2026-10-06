import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    Profile, Workspace, WorkspaceMember, Asset, AssetAuthorization,
    WorkspaceRole, AssetType, AssetCriticality, AuthorizationStatus, AuthorizationType
)
from app.schemas import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceMemberCreate, WorkspaceMemberUpdate,
    AssetCreate, AssetUpdate, AuthorizationCreate
)
from app.services import ProfileService, WorkspaceService, AssetService
from app.repositories import (
    ProfileRepository, WorkspaceRepository, WorkspaceMemberRepository,
    AssetRepository, AssetAuthorizationRepository
)


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def sample_profile():
    return Profile(
        id=uuid4(),
        firebase_uid="firebase-uid-123",
        email="test@example.com",
        display_name="Test User",
        avatar_url=None,
        role="user",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login_at=None,
    )


@pytest.fixture
def sample_workspace(sample_profile):
    return Workspace(
        id=uuid4(),
        name="Test Workspace",
        slug="test-workspace",
        owner_id=sample_profile.id,
        plan="free",
        settings={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        deleted_at=None,
    )


@pytest.fixture
def sample_workspace_member(sample_workspace, sample_profile):
    return WorkspaceMember(
        id=uuid4(),
        workspace_id=sample_workspace.id,
        user_id=sample_profile.id,
        role=WorkspaceRole.OWNER,
        invited_by=sample_profile.id,
        invited_at=datetime.utcnow(),
        joined_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )


class TestProfileService:
    @pytest.mark.asyncio
    async def test_get_or_create_from_firebase_creates_new(self, mock_db, sample_profile):
        mock_repo = AsyncMock(spec=ProfileRepository)
        mock_repo.get_by_firebase_uid.return_value = None
        mock_repo.create.return_value = sample_profile

        with patch('app.services.ProfileRepository', return_value=mock_repo):
            service = ProfileService(mock_db)
            result = await service.get_or_create_from_firebase(
                firebase_uid="firebase-uid-123",
                email="test@example.com",
                display_name="Test User"
            )

        assert result == sample_profile
        mock_repo.get_by_firebase_uid.assert_called_once_with("firebase-uid-123")
        mock_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_or_create_from_firebase_returns_existing(self, mock_db, sample_profile):
        mock_repo = AsyncMock(spec=ProfileRepository)
        mock_repo.get_by_firebase_uid.return_value = sample_profile

        with patch('app.services.ProfileRepository', return_value=mock_repo):
            service = ProfileService(mock_db)
            result = await service.get_or_create_from_firebase(
                firebase_uid="firebase-uid-123",
                email="test@example.com"
            )

        assert result == sample_profile
        mock_repo.get_by_firebase_uid.assert_called_once_with("firebase-uid-123")
        mock_repo.create.assert_not_called()


class TestWorkspaceService:
    @pytest.mark.asyncio
    async def test_create_workspace(self, mock_db, sample_profile, sample_workspace):
        mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
        mock_ws_repo.get_by_slug.return_value = None
        mock_ws_repo.create.return_value = sample_workspace

        mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
        mock_member_repo.create.return_value = AsyncMock()

        with patch('app.services.WorkspaceRepository', return_value=mock_ws_repo), \
             patch('app.services.WorkspaceMemberRepository', return_value=mock_member_repo):
            service = WorkspaceService(mock_db)
            result = await service.create_workspace(sample_profile.id, WorkspaceCreate(name="Test Workspace"))

        assert result == sample_workspace
        mock_ws_repo.create.assert_called_once()
        mock_member_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_workspace_generates_unique_slug(self, mock_db, sample_profile):
        existing_ws = MagicMock()
        existing_ws.slug = "test-workspace"
        
        mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
        mock_ws_repo.get_by_slug.side_effect = [existing_ws, None]
        
        created_ws = MagicMock()
        created_ws.id = uuid4()
        created_ws.name = "Test Workspace"
        created_ws.slug = "test-workspace-1"
        created_ws.owner_id = sample_profile.id
        mock_ws_repo.create.return_value = created_ws

        mock_member_repo = AsyncMock(spec=WorkspaceMemberRepository)
        mock_member_repo.create.return_value = AsyncMock()

        with patch('app.services.WorkspaceRepository', return_value=mock_ws_repo), \
             patch('app.services.WorkspaceMemberRepository', return_value=mock_member_repo):
            service = WorkspaceService(mock_db)
            result = await service.create_workspace(sample_profile.id, WorkspaceCreate(name="Test Workspace"))

        assert result.slug == "test-workspace-1"
        assert mock_ws_repo.get_by_slug.call_count == 2

    @pytest.mark.asyncio
    async def test_list_user_workspaces(self, mock_db, sample_profile, sample_workspace):
        mock_ws_repo = AsyncMock(spec=WorkspaceRepository)
        mock_ws_repo.get_user_workspaces.return_value = [sample_workspace]

        with patch('app.services.WorkspaceRepository', return_value=mock_ws_repo):
            service = WorkspaceService(mock_db)
            result = await service.list_user_workspaces(sample_profile.id)

        assert result == [sample_workspace]
        mock_ws_repo.get_user_workspaces.assert_called_once_with(sample_profile.id)


class TestAssetService:
    @pytest.mark.asyncio
    async def test_create_asset(self, mock_db, sample_workspace, sample_profile):
        mock_asset_repo = AsyncMock(spec=AssetRepository)
        created_asset = Asset(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            created_by=sample_profile.id,
            name="Test Repo",
            type=AssetType.REPOSITORY,
            subtype="github",
            connection_config={"url": "https://github.com/test/repo"},
            credentials_ref=None,
            criticality=AssetCriticality.MEDIUM,
            tags=[],
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_asset_repo.create.return_value = created_asset

        mock_auth_repo = AsyncMock(spec=AssetAuthorizationRepository)

        with patch('app.services.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.AssetAuthorizationRepository', return_value=mock_auth_repo):
            service = AssetService(mock_db)
            result = await service.create_asset(
                workspace_id=sample_workspace.id,
                creator_id=sample_profile.id,
                data=AssetCreate(
                    name="Test Repo",
                    type=AssetType.REPOSITORY,
                    subtype="github",
                    connection_config={"url": "https://github.com/test/repo"},
                    criticality=AssetCriticality.MEDIUM,
                    tags=[]
                )
            )

        assert result == created_asset
        mock_asset_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_authorized_for_scan_verified_not_expired(self, mock_db):
        mock_auth_repo = AsyncMock(spec=AssetAuthorizationRepository)
        auth = AssetAuthorization(
            id=uuid4(),
            asset_id=uuid4(),
            workspace_id=uuid4(),
            authorization_type=AuthorizationType.OWNERSHIP,
            evidence_files=[],
            evidence_urls=[],
            authorized_by="Test User",
            authorized_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(days=30),
            status=AuthorizationStatus.VERIFIED,
            verified_by=uuid4(),
            verified_at=datetime.utcnow(),
        )
        mock_auth_repo.is_authorized_for_scan.return_value = True

        with patch('app.services.AssetAuthorizationRepository', return_value=mock_auth_repo):
            service = AssetService(mock_db)
            result = await service.is_authorized_for_scan(uuid4())

        assert result is True

    @pytest.mark.asyncio
    async def test_is_authorized_for_scan_pending(self, mock_db):
        mock_auth_repo = AsyncMock(spec=AssetAuthorizationRepository)
        mock_auth_repo.is_authorized_for_scan.return_value = False

        with patch('app.services.AssetAuthorizationRepository', return_value=mock_auth_repo):
            service = AssetService(mock_db)
            result = await service.is_authorized_for_scan(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_is_authorized_for_scan_expired(self, mock_db):
        mock_auth_repo = AsyncMock(spec=AssetAuthorizationRepository)
        mock_auth_repo.is_authorized_for_scan.return_value = False

        with patch('app.services.AssetAuthorizationRepository', return_value=mock_auth_repo):
            service = AssetService(mock_db)
            result = await service.is_authorized_for_scan(uuid4())

        assert result is False

    @pytest.mark.asyncio
    async def test_is_authorized_for_scan_revoked(self, mock_db):
        mock_auth_repo = AsyncMock(spec=AssetAuthorizationRepository)
        mock_auth_repo.is_authorized_for_scan.return_value = False

        with patch('app.services.AssetAuthorizationRepository', return_value=mock_auth_repo):
            service = AssetService(mock_db)
            result = await service.is_authorized_for_scan(uuid4())

        assert result is False
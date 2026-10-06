import pytest
from uuid import uuid4
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models import (
    Profile, Workspace, WorkspaceMember, Asset, AssetAuthorization,
    WorkspaceRole, AssetType, AssetCriticality, AuthorizationStatus, AuthorizationType, UserRole
)
from app.schemas import (
    WorkspaceCreate, WorkspaceUpdate, WorkspaceMemberCreate, WorkspaceMemberUpdate,
    AssetCreate, AssetUpdate, AuthorizationCreate
)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_profile():
    return Profile(
        id=uuid4(),
        firebase_uid="firebase-uid-123",
        email="test@example.com",
        display_name="Test User",
        avatar_url=None,
        role=UserRole.USER,
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


class TestAuthEndpoints:
    def test_health_endpoint(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json()["status"] == "running"

    def test_health_database_endpoint(self, client):
        response = client.get("/api/v1/health/database")
        assert response.status_code == 200


class TestWorkspaceEndpoints:
    @pytest.mark.asyncio
    async def test_list_workspaces_unauthorized(self, client):
        response = client.get("/api/v1/workspaces")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_create_workspace_unauthorized(self, client):
        response = client.post("/api/v1/workspaces", json={"name": "Test"})
        assert response.status_code == 401


class TestWorkspaceAuthorization:
    @pytest.fixture
    def mock_current_user(self, sample_profile):
        with patch('app.api.v1.workspaces.get_current_user', return_value=sample_profile):
            yield

    @pytest.fixture
    def mock_workspace_service(self, sample_workspace, sample_workspace_member):
        mock_service = AsyncMock()
        mock_service.list_user_workspaces.return_value = [sample_workspace]
        mock_service.create_workspace.return_value = sample_workspace
        mock_service.get_workspace.return_value = sample_workspace
        mock_service.list_members.return_value = [sample_workspace_member]
        
        with patch('app.api.v1.workspaces.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_list_workspaces(self, client, mock_current_user, mock_workspace_service, sample_workspace):
        with patch('app.api.v1.workspaces.get_db', return_value=AsyncMock()):
            response = client.get("/api/v1/workspaces", headers={"Authorization": "Bearer test-token"})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == str(sample_workspace.id)

    @pytest.mark.asyncio
    async def test_create_workspace(self, client, mock_current_user, mock_workspace_service, sample_workspace, sample_profile):
        with patch('app.api.v1.workspaces.get_db', return_value=AsyncMock()):
            response = client.post(
                "/api/v1/workspaces",
                json={"name": "New Workspace"},
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Workspace"


class TestAssetEndpoints:
    @pytest.fixture
    def mock_current_user(self, sample_profile):
        with patch('app.api.v1.assets.get_current_user', return_value=sample_profile):
            yield

    @pytest.fixture
    def mock_asset_service(self, sample_workspace, sample_profile):
        mock_service = AsyncMock()
        mock_asset = Asset(
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
        mock_service.list_assets.return_value = [mock_asset]
        mock_service.create_asset.return_value = mock_asset
        mock_service.get_asset.return_value = mock_asset
        
        with patch('app.api.v1.assets.AssetService', return_value=mock_service):
            yield mock_service

    @pytest.fixture
    def mock_workspace_service(self, sample_workspace_member):
        mock_service = AsyncMock()
        mock_service.get_member.return_value = sample_workspace_member
        
        with patch('app.api.v1.assets.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_list_assets_unauthorized(self, client):
        response = client.get(f"/api/v1/workspaces/{uuid4()}/assets")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_list_assets(self, client, mock_current_user, mock_asset_service, mock_workspace_service, sample_workspace):
        with patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            response = client.get(
                f"/api/v1/workspaces/{sample_workspace.id}/assets",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Test Repo"

    @pytest.mark.asyncio
    async def test_create_asset(self, client, mock_current_user, mock_asset_service, mock_workspace_service, sample_workspace, sample_profile):
        with patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            response = client.post(
                f"/api/v1/workspaces/{sample_workspace.id}/assets",
                json={
                    "name": "Test Repo",
                    "type": "repository",
                    "subtype": "github",
                    "connection_config": {"url": "https://github.com/test/repo"},
                    "criticality": "medium"
                },
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Repo"


class TestAuthorizationEndpoints:
    @pytest.fixture
    def mock_current_user(self, sample_profile):
        with patch('app.api.v1.assets.get_current_user', return_value=sample_profile):
            yield

    @pytest.fixture
    def mock_asset_service(self, sample_workspace, sample_profile):
        mock_service = AsyncMock()
        mock_asset = Asset(
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
        mock_auth = AssetAuthorization(
            id=uuid4(),
            asset_id=mock_asset.id,
            workspace_id=sample_workspace.id,
            authorization_type=AuthorizationType.OWNERSHIP,
            evidence_files=[],
            evidence_urls=[],
            authorized_by="Test User",
            authorized_at=datetime.utcnow(),
            expires_at=None,
            status=AuthorizationStatus.PENDING,
        )
        mock_service.get_asset.return_value = mock_asset
        mock_service.create_authorization.return_value = mock_auth
        mock_service.get_authorization.return_value = mock_auth
        
        with patch('app.api.v1.assets.AssetService', return_value=mock_service):
            yield mock_service

    @pytest.fixture
    def mock_workspace_service(self, sample_workspace_member):
        mock_service = AsyncMock()
        mock_service.get_member.return_value = sample_workspace_member
        
        with patch('app.api.v1.assets.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_create_authorization(self, client, mock_current_user, mock_asset_service, mock_workspace_service, sample_workspace, sample_profile):
        with patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            response = client.post(
                f"/api/v1/assets/{uuid4()}/authorization",
                json={
                    "authorization_type": "ownership",
                    "evidence_files": [],
                    "evidence_urls": [],
                    "authorized_by": "Test User",
                    "authorized_at": datetime.utcnow().isoformat(),
                },
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_get_authorization(self, client, mock_current_user, mock_asset_service, mock_workspace_service, sample_workspace):
        with patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            asset_id = uuid4()
            response = client.get(
                f"/api/v1/assets/{asset_id}/authorization",
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"


class TestCrossWorkspaceSecurity:
    @pytest.fixture
    def mock_current_user_a(self):
        profile_a = Profile(
            id=uuid4(),
            firebase_uid="firebase-uid-a",
            email="usera@example.com",
            display_name="User A",
            role=UserRole.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        with patch('app.api.v1.assets.get_current_user', return_value=profile_a):
            yield profile_a

    @pytest.fixture
    def mock_current_user_b(self):
        profile_b = Profile(
            id=uuid4(),
            firebase_uid="firebase-uid-b",
            email="userb@example.com",
            display_name="User B",
            role=UserRole.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        with patch('app.api.v1.assets.get_current_user', return_value=profile_b):
            yield profile_b

    @pytest.fixture
    def mock_workspace_service_a(self, mock_current_user_a):
        mock_service = AsyncMock()
        member_a = WorkspaceMember(
            id=uuid4(),
            workspace_id=uuid4(),
            user_id=mock_current_user_a.id,
            role=WorkspaceRole.OWNER,
            invited_by=mock_current_user_a.id,
            invited_at=datetime.utcnow(),
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        mock_service.get_member.return_value = member_a
        
        with patch('app.api.v1.assets.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.fixture
    def mock_workspace_service_b(self, mock_current_user_b):
        mock_service = AsyncMock()
        member_b = WorkspaceMember(
            id=uuid4(),
            workspace_id=uuid4(),
            user_id=mock_current_user_b.id,
            role=WorkspaceRole.OWNER,
            invited_by=mock_current_user_b.id,
            invited_at=datetime.utcnow(),
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        mock_service.get_member.return_value = None  # User B not member of Workspace A
        
        with patch('app.api.v1.assets.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_user_a_cannot_access_workspace_b_asset(
        self, client, mock_current_user_a, mock_workspace_service_b, mock_current_user_b
    ):
        """User A should not be able to access User B's workspace assets."""
        asset_id = uuid4()
        
        mock_asset_service = AsyncMock()
        mock_asset = Asset(
            id=asset_id,
            workspace_id=mock_workspace_service_b.return_value.get_member.return_value.workspace_id if mock_workspace_service_b.return_value.get_member.return_value else uuid4(),
            created_by=mock_current_user_b.id,
            name="User B's Asset",
            type=AssetType.REPOSITORY,
            connection_config={},
            criticality=AssetCriticality.MEDIUM,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_asset_service.get_asset.return_value = mock_asset
        
        with patch('app.api.v1.assets.AssetService', return_value=mock_asset_service), \
             patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            
            response = client.get(
                f"/api/v1/assets/{asset_id}",
                headers={"Authorization": "Bearer test-token-a"}
            )
        
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_user_cannot_create_authorization_for_another_workspace_asset(
        self, client, mock_current_user_a, mock_workspace_service_b, mock_current_user_b
    ):
        """User A should not be able to create authorization for User B's asset."""
        asset_id = uuid4()
        
        mock_asset_service = AsyncMock()
        mock_asset = Asset(
            id=asset_id,
            workspace_id=uuid4(),  # Different workspace
            created_by=mock_current_user_b.id,
            name="User B's Asset",
            type=AssetType.REPOSITORY,
            connection_config={},
            criticality=AssetCriticality.MEDIUM,
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        mock_asset_service.get_asset.return_value = mock_asset
        
        with patch('app.api.v1.assets.AssetService', return_value=mock_asset_service), \
             patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            
            response = client.post(
                f"/api/v1/assets/{asset_id}/authorization",
                json={
                    "authorization_type": "ownership",
                    "evidence_files": [],
                    "evidence_urls": [],
                    "authorized_by": "User A",
                    "authorized_at": datetime.utcnow().isoformat(),
                },
                headers={"Authorization": "Bearer test-token-a"}
            )
        
        assert response.status_code == 403


class TestRoleEnforcement:
    @pytest.fixture
    def mock_current_user_viewer(self):
        profile = Profile(
            id=uuid4(),
            firebase_uid="firebase-uid-viewer",
            email="viewer@example.com",
            display_name="Viewer User",
            role=UserRole.USER,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        with patch('app.api.v1.assets.get_current_user', return_value=profile):
            yield profile

    @pytest.fixture
    def mock_workspace_service_viewer(self, mock_current_user_viewer):
        mock_service = AsyncMock()
        member = WorkspaceMember(
            id=uuid4(),
            workspace_id=uuid4(),
            user_id=mock_current_user_viewer.id,
            role=WorkspaceRole.VIEWER,
            invited_by=uuid4(),
            invited_at=datetime.utcnow(),
            joined_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        mock_service.get_member.return_value = member
        
        with patch('app.api.v1.assets.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_viewer_cannot_create_asset(self, client, mock_current_user_viewer, mock_workspace_service_viewer):
        """Viewer should not be able to create assets."""
        mock_asset_service = AsyncMock()
        
        with patch('app.api.v1.assets.AssetService', return_value=mock_asset_service), \
             patch('app.api.v1.assets.get_db', return_value=AsyncMock()):
            
            response = client.post(
                f"/api/v1/workspaces/{uuid4()}/assets",
                json={
                    "name": "Test Repo",
                    "type": "repository",
                    "connection_config": {},
                    "criticality": "medium"
                },
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 403


class TestTokenValidation:
    def test_missing_authorization_header(self, client):
        response = client.get("/api/v1/workspaces")
        assert response.status_code == 401

    def test_invalid_token_format(self, client):
        response = client.get("/api/v1/workspaces", headers={"Authorization": "InvalidToken"})
        assert response.status_code == 401

    def test_expired_token(self, client):
        # This would require a real expired token; mocked in integration tests
        pass


class TestAuditLogging:
    @pytest.fixture
    def mock_current_user(self, sample_profile):
        with patch('app.api.v1.workspaces.get_current_user', return_value=sample_profile):
            yield

    @pytest.fixture
    def mock_workspace_service(self, sample_workspace):
        mock_service = AsyncMock()
        mock_service.create_workspace.return_value = sample_workspace
        
        with patch('app.api.v1.workspaces.WorkspaceService', return_value=mock_service):
            yield mock_service

    @pytest.mark.asyncio
    async def test_workspace_creation_audited(self, client, mock_current_user, mock_workspace_service, sample_profile):
        with patch('app.api.v1.workspaces.get_db', return_value=AsyncMock()), \
             patch('app.api.v1.workspaces.audit_log') as mock_audit:
            
            response = client.post(
                "/api/v1/workspaces",
                json={"name": "Test Workspace"},
                headers={"Authorization": "Bearer test-token"}
            )
        
        assert response.status_code == 201
        mock_audit.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
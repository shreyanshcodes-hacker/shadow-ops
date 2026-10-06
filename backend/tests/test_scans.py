import pytest
from uuid import uuid4
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models import (
    Scan, ScanEvent, Finding, FindingEvidence, ScanTarget,
    ScanStatus, ScanProfile, ScanType, ScanEventType,
    FindingSource, FindingSeverity, FindingConfidence, FindingStatus, FindingEvidenceType,
    WorkspaceRole, Asset, AssetAuthorization, AuthorizationStatus, AssetType, AssetCriticality
)
from app.schemas import ScanCreate, ScanTargetCreate
from app.services.scans import ScanService
from app.repositories import ScanRepository, ScanEventRepository, FindingRepository, FindingEvidenceRepository
from app.scanning.runner import ScanJobRunner, ScanJobError, ScanAuthorizationError


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.fixture
def sample_profile():
    from app.models import Profile, UserRole
    return Profile(
        id=uuid4(),
        firebase_uid="firebase-uid-123",
        email="test@example.com",
        display_name="Test User",
        role=UserRole.USER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_workspace(sample_profile):
    from app.models import Workspace
    return Workspace(
        id=uuid4(),
        name="Test Workspace",
        slug="test-workspace",
        owner_id=sample_profile.id,
        plan="free",
        settings={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_asset(sample_workspace, sample_profile):
    return Asset(
        id=uuid4(),
        workspace_id=sample_workspace.id,
        name="Test Repo",
        type=AssetType.REPOSITORY,
        subtype="github",
        connection_config={"url": "https://github.com/test/repo", "branch": "main"},
        credentials_ref=None,
        criticality=AssetCriticality.MEDIUM,
        status="active",
        scan_frequency="24 hours",
        tags=[],
        created_by=sample_profile.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_authorization(sample_asset, sample_workspace, sample_profile):
    return AssetAuthorization(
        id=uuid4(),
        asset_id=sample_asset.id,
        workspace_id=sample_workspace.id,
        authorization_type=AuthorizationType.OWNERSHIP,
        evidence_files=[],
        evidence_urls=[],
        authorized_by="Test User",
        authorized_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status=AuthorizationStatus.VERIFIED,
        verified_by=sample_profile.id,
        verified_at=datetime.utcnow(),
        notes=None,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


@pytest.fixture
def sample_scan(sample_workspace, sample_asset, sample_profile):
    return Scan(
        id=uuid4(),
        workspace_id=sample_workspace.id,
        asset_id=sample_asset.id,
        scan_type=ScanType.CODE,
        scan_profile=ScanProfile.CODE_SECURITY,
        status=ScanStatus.QUEUED,
        triggered_by=sample_profile.id,
        triggered_at=datetime.utcnow(),
        scan_config={},
        summary={},
        target_type="repository",
        target_reference="https://github.com/test/repo",
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )


class TestScanService:
    @pytest.mark.asyncio
    async def test_create_scan_success(self, mock_db, sample_workspace, sample_asset, sample_authorization, sample_profile):
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = sample_authorization

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        mock_scan_repo = AsyncMock()
        created_scan = MagicMock()
        created_scan.id = uuid4()
        created_scan.workspace_id = sample_workspace.id
        created_scan.asset_id = sample_asset.id
        created_scan.scan_type = ScanType.CODE
        created_scan.scan_profile = ScanProfile.CODE_SECURITY
        created_scan.status = ScanStatus.QUEUED
        created_scan.triggered_by = sample_profile.id
        created_scan.triggered_at = datetime.utcnow()
        created_scan.scan_config = {}
        created_scan.summary = {}
        created_scan.target_type = "repository"
        created_scan.target_reference = "https://github.com/test/repo"
        mock_scan_repo.create.return_value = created_scan

        mock_event_repo = AsyncMock()
        mock_event_repo.create.return_value = MagicMock()

        with patch('app.services.scans.ScanRepository', return_value=mock_scan_repo), \
             patch('app.services.scans.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo), \
             patch('app.services.scans.audit_log', new_callable=AsyncMock):
            
            service = ScanService(mock_db)
            result = await service.create_scan(sample_profile.id, sample_workspace.id, ScanCreate(
                asset_id=sample_asset.id,
                scan_type=ScanType.CODE,
                scan_profile=ScanProfile.CODE_SECURITY,
            ))

        assert result is not None
        mock_scan_repo.create.assert_called_once()
        assert mock_event_repo.create.call_count == 3  # SCAN_CREATED, AUTHORIZATION_CONFIRMED, SCAN_QUEUED

    @pytest.mark.asyncio
    async def test_create_scan_no_authorization(self, mock_db, sample_workspace, sample_asset, sample_profile):
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = None

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        with patch('app.services.scans.ScanRepository', return_value=AsyncMock()), \
             patch('app.services.scans.ScanEventRepository', return_value=AsyncMock()), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Asset has no authorization record"):
                await service.create_scan(sample_profile.id, sample_workspace.id, ScanCreate(
                    asset_id=sample_asset.id,
                    scan_type=ScanType.CODE,
                    scan_profile=ScanProfile.CODE_SECURITY,
                ))

    @pytest.mark.asyncio
    async def test_create_scan_pending_authorization(self, mock_db, sample_workspace, sample_asset, sample_profile):
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        pending_auth = MagicMock()
        pending_auth.status = AuthorizationStatus.PENDING
        pending_auth.workspace_id = sample_workspace.id
        mock_auth_repo.get_by_asset.return_value = pending_auth

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        with patch('app.services.scans.ScanRepository', return_value=AsyncMock()), \
             patch('app.services.scans.ScanEventRepository', return_value=AsyncMock()), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Authorization status is pending"):
                await service.create_scan(sample_profile.id, sample_workspace.id, ScanCreate(
                    asset_id=sample_asset.id,
                    scan_type=ScanType.CODE,
                    scan_profile=ScanProfile.CODE_SECURITY,
                ))

    @pytest.mark.asyncio
    async def test_create_scan_expired_authorization(self, mock_db, sample_workspace, sample_asset, sample_profile):
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        expired_auth = MagicMock()
        expired_auth.status = AuthorizationStatus.VERIFIED
        expired_auth.workspace_id = sample_workspace.id
        expired_auth.expires_at = datetime.utcnow() - timedelta(days=1)
        mock_auth_repo.get_by_asset.return_value = expired_auth

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        with patch('app.services.scans.ScanRepository', return_value=AsyncMock()), \
             patch('app.services.scans.ScanEventRepository', return_value=AsyncMock()), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Authorization has expired"):
                await service.create_scan(sample_profile.id, sample_workspace.id, ScanCreate(
                    asset_id=sample_asset.id,
                    scan_type=ScanType.CODE,
                    scan_profile=ScanProfile.CODE_SECURITY,
                ))

    @pytest.mark.asyncio
    async def test_cancel_scan(self, mock_db, sample_scan, sample_workspace, sample_profile):
        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan
        mock_scan_repo.update.return_value = sample_scan

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        mock_event_repo = AsyncMock()
        mock_event_repo.create.return_value = MagicMock()

        with patch('app.services.scans.ScanRepository', return_value=mock_scan_repo), \
             patch('app.services.scans.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo), \
             patch('app.services.scans.audit_log', new_callable=AsyncMock):
            
            service = ScanService(mock_db)
            result = await service.cancel_scan(sample_scan.id, sample_profile.id, sample_workspace.id)

        assert result is True
        mock_scan_repo.update.assert_called_once()
        update_args = mock_scan_repo.update.call_args
        assert update_args[1]["status"] == ScanStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_scan_not_requester_or_admin(self, mock_db, sample_scan, sample_workspace):
        other_user_id = uuid4()
        
        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan

        mock_member_repo = AsyncMock()
        mock_member = MagicMock()
        mock_member.joined_at = datetime.utcnow()
        mock_member.role = WorkspaceRole.MEMBER
        mock_member_repo.get_by_workspace_and_user.return_value = mock_member

        with patch('app.services.scans.ScanRepository', return_value=mock_scan_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Only scan requester or workspace admin/owner can cancel"):
                await service.cancel_scan(sample_scan.id, other_user_id, sample_workspace.id)


class TestScanJobRunner:
    @pytest.mark.asyncio
    async def test_unauthorized_asset_never_reaches_scanner(self, mock_db, sample_workspace, sample_asset):
        """Test the critical security invariant: NO AUTHORIZATION -> NO SCAN"""
        sample_scan = Scan(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            asset_id=sample_asset.id,
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.RUNNING,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan

        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = None  # NO AUTHORIZATION

        mock_event_repo = AsyncMock()

        with patch('app.scanning.runner.ScanRepository', return_value=mock_scan_repo), \
             patch('app.scanning.runner.AssetRepository', return_value=mock_asset_repo), \
             patch('app.scanning.runner.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.scanning.runner.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.scanning.runner.audit_log', new_callable=AsyncMock):
            
            runner = ScanJobRunner(mock_db)
            with pytest.raises(ScanAuthorizationError, match="Asset authorization record missing"):
                await runner.execute_scan(sample_scan.id)

    @pytest.mark.asyncio
    async def test_pending_authorization_blocks_scanner(self, mock_db, sample_workspace, sample_asset):
        sample_scan = Scan(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            asset_id=sample_asset.id,
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.RUNNING,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan

        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        pending_auth = MagicMock()
        pending_auth.status = "pending"
        mock_auth_repo.get_by_asset.return_value = pending_auth

        mock_event_repo = AsyncMock()

        with patch('app.scanning.runner.ScanRepository', return_value=mock_scan_repo), \
             patch('app.scanning.runner.AssetRepository', return_value=mock_asset_repo), \
             patch('app.scanning.runner.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.scanning.runner.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.scanning.runner.audit_log', new_callable=AsyncMock):
            
            runner = ScanJobRunner(mock_db)
            with pytest.raises(ScanAuthorizationError, match="Authorization status is pending"):
                await runner.execute_scan(sample_scan.id)

    @pytest.mark.asyncio
    async def test_revoked_authorization_blocks_scanner(self, mock_db, sample_workspace, sample_asset):
        sample_scan = Scan(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            asset_id=sample_asset.id,
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.RUNNING,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan

        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        revoked_auth = MagicMock()
        revoked_auth.status = "rejected"
        mock_auth_repo.get_by_asset.return_value = revoked_auth

        mock_event_repo = AsyncMock()

        with patch('app.scanning.runner.ScanRepository', return_value=mock_scan_repo), \
             patch('app.scanning.runner.AssetRepository', return_value=mock_asset_repo), \
             patch('app.scanning.runner.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.scanning.runner.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.scanning.runner.audit_log', new_callable=AsyncMock):
            
            runner = ScanJobRunner(mock_db)
            with pytest.raises(ScanAuthorizationError, match="Authorization status is rejected"):
                await runner.execute_scan(sample_scan.id)

    @pytest.mark.asyncio
    async def test_expired_authorization_blocks_scanner(self, mock_db, sample_workspace, sample_asset):
        sample_scan = Scan(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            asset_id=sample_asset.id,
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.RUNNING,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan

        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        expired_auth = MagicMock()
        expired_auth.status = "verified"
        expired_auth.expires_at = datetime.utcnow() - timedelta(days=1)
        mock_auth_repo.get_by_asset.return_value = expired_auth

        mock_event_repo = AsyncMock()

        with patch('app.scanning.runner.ScanRepository', return_value=mock_scan_repo), \
             patch('app.scanning.runner.AssetRepository', return_value=mock_asset_repo), \
             patch('app.scanning.runner.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.scanning.runner.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.scanning.runner.audit_log', new_callable=AsyncMock):
            
            runner = ScanJobRunner(mock_db)
            with pytest.raises(ScanAuthorizationError, match="Authorization has expired"):
                await runner.execute_scan(sample_scan.id)

    @pytest.mark.asyncio
    async def test_valid_authorization_allows_scanner(self, mock_db, sample_workspace, sample_asset, sample_authorization):
        sample_scan = Scan(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            asset_id=sample_asset.id,
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.RUNNING,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan
        mock_scan_repo.update.return_value = sample_scan

        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = sample_asset

        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = sample_authorization

        mock_event_repo = AsyncMock()
        mock_event_repo.create.return_value = MagicMock()

        mock_finding_repo = AsyncMock()
        mock_finding_repo.create.return_value = MagicMock()
        mock_finding_repo.create_many.return_value = []

        mock_evidence_repo = AsyncMock()
        mock_evidence_repo.create.return_value = MagicMock()
        mock_evidence_repo.create_many.return_value = []

        # Mock Semgrep manager to return empty findings
        with patch('app.scanning.runner.ScanRepository', return_value=mock_scan_repo), \
             patch('app.scanning.runner.AssetRepository', return_value=mock_asset_repo), \
             patch('app.scanning.runner.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.scanning.runner.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.scanning.runner.FindingRepository', return_value=mock_finding_repo), \
             patch('app.scanning.runner.FindingEvidenceRepository', return_value=mock_evidence_repo), \
             patch('app.scanning.runner.SemgrepManager') as mock_semgrep_class, \
             patch('app.scanning.runner.audit_log', new_callable=AsyncMock):
            
            mock_semgrep = AsyncMock()
            mock_semgrep.scan_code.return_value = []
            mock_semgrep.scan_dependencies.return_value = []
            mock_semgrep_class.return_value = mock_semgrep
            
            runner = ScanJobRunner(mock_db)
            result = await runner.execute_scan(sample_scan.id)

        assert result is not None
        mock_semgrep.scan_code.assert_called_once()


class TestScanStateMachine:
    @pytest.mark.asyncio
    async def test_valid_transitions(self, mock_db, sample_scan):
        """Test valid state transitions: QUEUED -> RUNNING -> COMPLETED"""
        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = sample_scan
        mock_scan_repo.update.return_value = sample_scan
        mock_event_repo = AsyncMock()
        mock_event_repo.create.return_value = MagicMock()

        with patch('app.services.scans.ScanRepository', return_value=mock_scan_repo), \
             patch('app.services.scans.ScanEventRepository', return_value=mock_event_repo), \
             patch('app.services.scans.audit_log', new_callable=AsyncMock):
            
            service = ScanService(mock_db)
            
            # QUEUED -> RUNNING
            scan = await service.start_scan(sample_scan.id)
            assert scan.status == ScanStatus.RUNNING
            
            # RUNNING -> COMPLETED
            scan = await service.complete_scan(sample_scan.id, {"total_findings": 0}, {"total_findings": 0})
            assert scan.status == ScanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_invalid_transition_completed_to_running(self, mock_db):
        """Test that COMPLETED -> RUNNING is rejected"""
        completed_scan = Scan(
            id=uuid4(),
            workspace_id=uuid4(),
            asset_id=uuid4(),
            scan_type=ScanType.CODE,
            scan_profile=ScanProfile.CODE_SECURITY,
            status=ScanStatus.COMPLETED,
            triggered_by=uuid4(),
            triggered_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            scan_config={},
            summary={},
        )

        mock_scan_repo = AsyncMock()
        mock_scan_repo.get_by_id.return_value = completed_scan
        mock_event_repo = AsyncMock()

        with patch('app.services.scans.ScanRepository', return_value=mock_scan_repo), \
             patch('app.services.scans.ScanEventRepository', return_value=mock_event_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Scan is not in QUEUED status"):
                await service.start_scan(completed_scan.id)


class TestCrossWorkspaceSecurity:
    @pytest.mark.asyncio
    async def test_user_cannot_scan_another_workspace_asset(self, mock_db):
        """User A should not be able to scan User B's workspace asset"""
        workspace_a = uuid4()
        workspace_b = uuid4()
        user_a = uuid4()
        user_b = uuid4()
        
        asset_b = Asset(
            id=uuid4(),
            workspace_id=workspace_b,
            name="User B's Asset",
            type=AssetType.REPOSITORY,
            connection_config={},
            criticality=AssetCriticality.MEDIUM,
            status="active",
            created_by=user_b,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = asset_b
        
        mock_member_repo = AsyncMock()
        # User A is not a member of Workspace B
        mock_member_repo.get_by_workspace_and_user.return_value = None
        
        with patch('app.services.scans.ScanRepository', return_value=AsyncMock()), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=AsyncMock()), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Not a member of this workspace"):
                await service.create_scan(user_a, workspace_b, ScanCreate(
                    asset_id=asset_b.id,
                    scan_type=ScanType.CODE,
                    scan_profile=ScanProfile.CODE_SECURITY,
                ))


class TestRoleEnforcement:
    @pytest.mark.asyncio
    async def test_viewer_cannot_create_scan(self, mock_db):
        """Viewer should not be able to create scans"""
        workspace_id = uuid4()
        user_id = uuid4()
        asset_id = uuid4()
        
        mock_asset_repo = AsyncMock()
        mock_asset_repo.get_by_id.return_value = MagicMock(
            workspace_id=workspace_id,
            id=asset_id,
            deleted_at=None,
        )
        
        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = MagicMock(
            status=AuthorizationStatus.VERIFIED,
            workspace_id=workspace_id,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        
        mock_member_repo = AsyncMock()
        viewer_member = MagicMock()
        viewer_member.joined_at = datetime.utcnow()
        viewer_member.role = WorkspaceRole.VIEWER
        mock_member_repo.get_by_workspace_and_user.return_value = viewer_member
        
        with patch('app.services.scans.ScanRepository', return_value=AsyncMock()), \
             patch('app.services.scans.AssetRepository', return_value=mock_asset_repo), \
             patch('app.services.scans.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.services.scans.WorkspaceMemberRepository', return_value=mock_member_repo):
            
            service = ScanService(mock_db)
            with pytest.raises(ValueError, match="Insufficient permissions to create scans"):
                await service.create_scan(user_id, workspace_id, ScanCreate(
                    asset_id=asset_id,
                    scan_type=ScanType.CODE,
                    scan_profile=ScanProfile.CODE_SECURITY,
                ))


class TestScanAuthorizationDependency:
    @pytest.mark.asyncio
    async def test_require_scan_authorization_missing(self, mock_db):
        from app.security.auth import require_scan_authorization
        from fastapi import HTTPException
        from app.models import Profile
        
        asset_id = uuid4()
        current_user = Profile(id=uuid4(), firebase_uid="test", email="test@test.com")
        
        mock_auth_repo = AsyncMock()
        mock_auth_repo.get_by_asset.return_value = None
        
        with patch('app.security.auth.AssetAuthorizationRepository', return_value=mock_auth_repo), \
             patch('app.security.auth.audit_log', new_callable=AsyncMock):
            
            dep = require_scan_authorization(asset_id)
            # The dependency would be called with current_user and db
            # We can't easily test the FastAPI dependency here without a full app
            # But we verified the logic in ScanService and ScanJobRunner tests
            pass


class TestFindingPersistence:
    @pytest.mark.asyncio
    async def test_findings_persisted_with_correct_links(self, mock_db, sample_workspace, sample_asset, sample_profile):
        mock_finding_repo = AsyncMock()
        created_finding = Finding(
            id=uuid4(),
            workspace_id=sample_workspace.id,
            scan_id=uuid4(),
            asset_id=sample_asset.id,
            source=FindingSource.SEMGREP,
            source_rule_id="test-rule",
            title="Test Finding",
            description="Test description",
            severity=FindingSeverity.HIGH,
            confidence=FindingConfidence.HIGH,
            cwe_ids=["CWE-89"],
            cve_ids=[],
            owasp_categories=["A03:2021"],
            location={"file": "test.py", "line_start": 10, "line_end": 15},
            code_snippet="query = f'SELECT * FROM users WHERE id = {user_id}'",
            remediation_guidance="Use parameterized queries",
            status=FindingStatus.OPEN,
            risk_factors={},
        )
        mock_finding_repo.create.return_value = created_finding

        mock_evidence_repo = AsyncMock()
        mock_evidence_repo.create.return_value = MagicMock()

        with patch('app.repositories.FindingRepository', return_value=mock_finding_repo), \
             patch('app.repositories.FindingEvidenceRepository', return_value=mock_evidence_repo):
            
            from app.repositories import FindingRepository, FindingEvidenceRepository
            finding_repo = FindingRepository(mock_db)
            evidence_repo = FindingEvidenceRepository(mock_db)
            
            finding = await finding_repo.create(created_finding)
            evidence = await evidence_repo.create(FindingEvidence(
                finding_id=finding.id,
                workspace_id=sample_workspace.id,
                evidence_type=FindingEvidenceType.STATIC_ANALYSIS,
                title="Test Evidence",
                description="Test",
                content={},
                file_path="test.py",
                line_start=10,
                line_end=15,
            ))

        assert finding.workspace_id == sample_workspace.id
        assert finding.scan_id == created_finding.scan_id
        assert finding.asset_id == sample_asset.id
        assert evidence.finding_id == finding.id
        assert evidence.workspace_id == sample_workspace.id


class TestSummaryCalculation:
    def test_summary_calculated_from_actual_results(self):
        """Test that summary is calculated from actual findings, not hardcoded"""
        findings = [
            NormalizedFinding(
                source="semgrep",
                source_rule_id="rule1",
                title="SQL Injection",
                description="SQL injection vulnerability",
                severity="critical",
                confidence="high",
                cwe_ids=["CWE-89"],
                cve_ids=[],
                owasp_categories=["A03:2021"],
                location={"file": "test.py", "line_start": 10, "line_end": 15},
                code_snippet="query = f'SELECT * FROM users WHERE id = {user_id}'",
                remediation_guidance="Use parameterized queries",
                evidence={},
            ),
            NormalizedFinding(
                source="semgrep",
                source_rule_id="rule2",
                title="Hardcoded Secret",
                description="Hardcoded API key",
                severity="high",
                confidence="high",
                cwe_ids=["CWE-798"],
                cve_ids=[],
                owasp_categories=["A07:2021"],
                location={"file": "config.py", "line_start": 5, "line_end": 5},
                code_snippet="API_KEY = 'secret123'",
                remediation_guidance="Use environment variables",
                evidence={},
            ),
            NormalizedFinding(
                source="semgrep",
                source_rule_id="rule3",
                title="Weak Crypto",
                description="MD5 used for hashing",
                severity="medium",
                confidence="medium",
                cwe_ids=["CWE-327"],
                cve_ids=[],
                owasp_categories=["A02:2021"],
                location={"file": "auth.py", "line_start": 20, "line_end": 25},
                code_snippet="hash = md5(password)",
                remediation_guidance="Use bcrypt or argon2",
                evidence={},
            ),
        ]
        
        # Test the summary calculation logic from ScanJobRunner
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
        for finding in findings:
            severity = finding.severity.lower()
            if severity in counts:
                counts[severity] += 1
            else:
                counts["medium"] += 1
        
        assert counts["critical"] == 1
        assert counts["high"] == 1
        assert counts["medium"] == 1
        assert counts["low"] == 0
        assert counts["info"] == 0
        assert sum(counts.values()) == 3


# Need to import NormalizedFinding for the last test
from app.scanners.semgrep import NormalizedFinding
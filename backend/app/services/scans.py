from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.repositories import (
    ScanRepository,
    ScanEventRepository,
    FindingRepository,
    FindingEvidenceRepository,
    AssetRepository,
    AssetAuthorizationRepository,
    WorkspaceRepository,
    WorkspaceMemberRepository,
    ScanTargetRepository,
)
from app.models import (
    Scan, ScanEvent, Finding, FindingEvidence, ScanTarget,
    ScanStatus, ScanProfile, ScanType, ScanEventType,
    FindingSource, FindingSeverity, FindingConfidence, FindingStatus, FindingEvidenceType,
    WorkspaceRole, Asset, AssetAuthorization, AuthorizationStatus
)
from app.schemas import (
    ScanCreate, ScanUpdate, ScanTargetCreate, ScanTargetUpdate
)
from app.scanning.runner import ScanJobRunner, ScanJobError
from app.security.audit import audit_log


class ScanService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scan_repo = ScanRepository(db)
        self.event_repo = ScanEventRepository(db)
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.asset_repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)
        self.ws_repo = WorkspaceRepository(db)
        self.member_repo = WorkspaceMemberRepository(db)
        self.target_repo = ScanTargetRepository(db)

    async def _emit_event(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        phase: str,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> ScanEvent:
        event = ScanEvent(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase=phase,
            event_type=event_type,
            message=message,
            data=data or {},
        )
        return await self.event_repo.create(event)

    async def _validate_authorization(self, asset_id: UUID, workspace_id: UUID) -> AssetAuthorization:
        """Validate that the asset has a valid authorization for scanning."""
        auth = await self.auth_repo.get_by_asset(asset_id)
        if not auth:
            raise ValueError("Asset has no authorization record")
        if auth.workspace_id != workspace_id:
            raise ValueError("Authorization workspace mismatch")
        if auth.status != AuthorizationStatus.VERIFIED:
            raise ValueError(f"Authorization status is {auth.status.value}, must be VERIFIED")
        if auth.expires_at and auth.expires_at < datetime.utcnow():
            raise ValueError("Authorization has expired")
        return auth

    async def _validate_workspace_access(self, user_id: UUID, workspace_id: UUID) -> None:
        """Validate that the user is an active member of the workspace."""
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if not member or member.joined_at is None:
            raise ValueError("Not a member of this workspace")
        if member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER]:
            raise ValueError("Insufficient permissions to create scans")

    async def create_scan(
        self,
        user_id: UUID,
        workspace_id: UUID,
        data: ScanCreate
    ) -> Scan:
        """Create a new scan after validating authorization and workspace access."""
        # Validate workspace access
        await self._validate_workspace_access(user_id, workspace_id)

        # Validate asset exists and belongs to workspace
        asset = await self.asset_repo.get_by_id(data.asset_id)
        if not asset:
            raise ValueError("Asset not found")
        if asset.workspace_id != workspace_id:
            raise ValueError("Asset does not belong to this workspace")
        if asset.deleted_at is not None:
            raise ValueError("Asset has been deleted")

        # Validate authorization (NO AUTHORIZATION -> NO SCAN)
        auth = await self._validate_authorization(data.asset_id, workspace_id)

        # Create scan record
        scan = Scan(
            workspace_id=workspace_id,
            asset_id=data.asset_id,
            scan_type=data.scan_type,
            scan_profile=data.scan_profile,
            status=ScanStatus.QUEUED,
            triggered_by=user_id,
            triggered_at=datetime.utcnow(),
            scan_config=data.scan_config,
            target_type=asset.type.value,
            target_reference=asset.connection_config.get("url") if asset.connection_config else None,
        )
        scan = await self.scan_repo.create(scan)

        # Emit scan created event
        await self._emit_event(
            scan_id=scan.id,
            workspace_id=workspace_id,
            phase="initialization",
            event_type=ScanEventType.SCAN_CREATED.value,
            message="Scan created and queued",
            data={"scan_profile": data.scan_profile.value, "scan_type": data.scan_type.value}
        )

        # Emit authorization confirmed event
        await self._emit_event(
            scan_id=scan.id,
            workspace_id=workspace_id,
            phase="authorization",
            event_type=ScanEventType.AUTHORIZATION_CONFIRMED.value,
            message="Asset authorization verified",
            data={"authorization_id": str(auth.id), "authorization_type": auth.authorization_type.value}
        )
        # Update authorization confirmed timestamp
        await self.scan_repo.update(scan.id, {"authorization_confirmed_at": datetime.utcnow()})

        # Emit scan queued event
        await self._emit_event(
            scan_id=scan.id,
            workspace_id=workspace_id,
            phase="queued",
            event_type=ScanEventType.SCAN_QUEUED.value,
            message="Scan queued for execution",
            data={}
        )

        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="scan.requested",
            resource_type="scan",
            resource_id=scan.id,
            new_state={
                "scan_id": str(scan.id),
                "asset_id": str(data.asset_id),
                "scan_profile": data.scan_profile.value,
                "scan_type": data.scan_type.value,
            },
            user_id=user_id,
        )

        return scan

    async def get_scan(self, scan_id: UUID) -> Optional[Scan]:
        return await self.scan_repo.get_by_id_with_relations(scan_id)

    async def list_scans(
        self,
        workspace_id: UUID,
        status: Optional[ScanStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Scan]:
        return await self.scan_repo.get_by_workspace(workspace_id, status, limit, offset)

    async def get_asset_scans(self, asset_id: UUID, limit: int = 50, offset: int = 0) -> List[Scan]:
        return await self.scan_repo.get_by_asset(asset_id, limit, offset)

    async def cancel_scan(self, scan_id: UUID, user_id: UUID, workspace_id: UUID) -> bool:
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")
        if scan.workspace_id != workspace_id:
            raise ValueError("Scan does not belong to this workspace")

        # Check if user can cancel (requester or admin/owner)
        member = await self.member_repo.get_by_workspace_and_user(workspace_id, user_id)
        if not member or member.joined_at is None:
            raise ValueError("Not a member of this workspace")
        if scan.triggered_by != user_id and member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
            raise ValueError("Only scan requester or workspace admin/owner can cancel")

        # Check if scan can be cancelled
        if scan.status not in [ScanStatus.QUEUED, ScanStatus.RUNNING]:
            raise ValueError(f"Cannot cancel scan in status {scan.status.value}")

        # Update scan status
        update_data = {
            "status": ScanStatus.CANCELLED,
            "cancelled_at": datetime.utcnow(),
        }
        if scan.status == ScanStatus.RUNNING and scan.started_at:
            update_data["duration_ms"] = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)

        await self.scan_repo.update(scan_id, update_data)

        # Emit cancellation event
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase="cancellation",
            event_type=ScanEventType.SCAN_CANCELLED.value,
            message="Scan cancelled by user",
            data={"cancelled_by": str(user_id)}
        )

        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="scan.cancelled",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "cancelled"},
            user_id=user_id,
        )

        return True

    async def start_scan(self, scan_id: UUID) -> Scan:
        """Start scan execution - transitions from QUEUED to RUNNING."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")

        if scan.status != ScanStatus.QUEUED:
            raise ValueError(f"Scan is not in QUEUED status (current: {scan.status.value})")

        # Update status to RUNNING
        update_data = {
            "status": ScanStatus.RUNNING,
            "started_at": datetime.utcnow(),
            "current_phase": "initialization",
            "progress_percent": 5,
        }
        scan = await self.scan_repo.update(scan_id, update_data)

        # Emit scan started event
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=scan.workspace_id,
            phase="execution",
            event_type=ScanEventType.SCAN_STARTED.value,
            message="Scan execution started",
            data={"started_at": datetime.utcnow().isoformat()}
        )

        return scan

    async def complete_scan(self, scan_id: UUID, summary: Dict[str, Any], findings_count: Dict[str, int]) -> Scan:
        """Mark scan as completed with summary."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")

        if scan.status != ScanStatus.RUNNING:
            raise ValueError(f"Scan is not in RUNNING status (current: {scan.status.value})")

        duration_ms = None
        if scan.started_at:
            duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)

        update_data = {
            "status": ScanStatus.COMPLETED,
            "completed_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "progress_percent": 100,
            "current_phase": "completed",
            "phases_completed": list(set(scan.phases_completed + ["completed"])),
            "summary": summary,
        }
        scan = await self.scan_repo.update(scan_id, update_data)

        # Emit scan completed event
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=scan.workspace_id,
            phase="completion",
            event_type=ScanEventType.SCAN_COMPLETED.value,
            message="Scan completed successfully",
            data={"summary": summary, "duration_ms": duration_ms}
        )

        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=scan.workspace_id,
            action="scan.completed",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "completed", "summary": summary},
        )

        return scan

    async def fail_scan(self, scan_id: UUID, error_code: str, error_message: str) -> Scan:
        """Mark scan as failed."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")

        if scan.status not in [ScanStatus.QUEUED, ScanStatus.RUNNING]:
            raise ValueError(f"Scan is not in a fail-able status (current: {scan.status.value})")

        duration_ms = None
        if scan.started_at:
            duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)

        update_data = {
            "status": ScanStatus.FAILED,
            "failed_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "error_code": error_code,
            "error_message": error_message,
            "current_phase": "failed",
        }
        scan = await self.scan_repo.update(scan_id, update_data)

        # Emit scan failed event
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=scan.workspace_id,
            phase="failure",
            event_type=ScanEventType.SCAN_FAILED.value,
            message=f"Scan failed: {error_message}",
            data={"error_code": error_code, "error_message": error_message}
        )

        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=scan.workspace_id,
            action="scan.failed",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "failed", "error_code": error_code, "error_message": error_message},
        )

        return scan

    async def update_scan_progress(
        self,
        scan_id: UUID,
        phase: str,
        progress_percent: int,
        phases_completed: Optional[List[str]] = None
    ) -> Scan:
        """Update scan progress during execution."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")

        new_phases = list(scan.phases_completed)
        if phases_completed:
            for p in phases_completed:
                if p not in new_phases:
                    new_phases.append(p)

        update_data = {
            "current_phase": phase,
            "progress_percent": progress_percent,
            "phases_completed": new_phases,
        }
        return await self.scan_repo.update(scan_id, update_data)

    async def execute_scan(self, scan_id: UUID) -> Scan:
        """
        Execute a scan using the ScanJobRunner.
        
        This is the main entry point for scan execution.
        It creates a runner and delegates the execution.
        """
        runner = ScanJobRunner(self.db)
        return await runner.execute_scan(scan_id)

    async def get_scan_events(self, scan_id: UUID) -> List[ScanEvent]:
        return await self.event_repo.get_by_scan(scan_id)

    async def get_scan_summary(self, scan_id: UUID) -> Dict[str, Any]:
        """Get scan summary including finding counts by severity."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError("Scan not found")

        counts = await self.finding_repo.count_by_scan(scan_id)
        return {
            "scan_id": str(scan_id),
            "status": scan.status.value,
            "summary": scan.summary,
            "findings": counts,
        }

    # Scan Target methods
    async def create_scan_target(self, workspace_id: UUID, user_id: UUID, data: ScanTargetCreate) -> ScanTarget:
        await self._validate_workspace_access(user_id, workspace_id)

        target = ScanTarget(
            workspace_id=workspace_id,
            created_by=user_id,
            name=data.name,
            description=data.description,
            target_path=data.target_path,
            target_type=data.target_type,
            is_demo=data.is_demo,
            is_active=data.is_active,
        )
        return await self.target_repo.create(target)

    async def list_scan_targets(self, workspace_id: UUID, is_demo: Optional[bool] = None) -> List[ScanTarget]:
        return await self.target_repo.get_by_workspace(workspace_id, is_demo)

    async def get_active_scan_targets(self, workspace_id: UUID) -> List[ScanTarget]:
        return await self.target_repo.get_active_by_workspace(workspace_id)

    async def update_scan_target(self, target_id: UUID, data: ScanTargetUpdate) -> Optional[ScanTarget]:
        update_data = data.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        return await self.target_repo.update(target_id, update_data)

    async def delete_scan_target(self, target_id: UUID) -> bool:
        return await self.target_repo.soft_delete(target_id)
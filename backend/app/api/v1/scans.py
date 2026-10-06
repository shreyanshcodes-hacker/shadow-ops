from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.security.auth import (
    get_current_user,
    require_workspace_member,
    require_workspace_admin,
)
from app.services import ScanService
from app.schemas import (
    ScanCreate,
    ScanUpdate,
    ScanResponse,
    ScanListResponse,
    ScanEventResponse,
    ScanSummary,
    ScanTargetCreate,
    ScanTargetUpdate,
    ScanTargetResponse,
)
from app.models import WorkspaceMember, WorkspaceRole, ScanStatus

router = APIRouter()


@router.post("", response_model=ScanResponse, status_code=status.HTTP_201_CREATED)
async def create_scan(
    scan_in: ScanCreate,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scan for an authorized asset."""
    service = ScanService(db)
    try:
        scan = await service.create_scan(current_user.id, member.workspace_id, scan_in)
        return ScanResponse.model_validate(scan)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ScanListResponse])
async def list_scans(
    workspace_id: UUID,
    status: Optional[ScanStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    member: WorkspaceMember = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List scans for a workspace."""
    if member.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Workspace mismatch")

    service = ScanService(db)
    scans = await service.list_scans(workspace_id, status, limit, offset)
    return [ScanListResponse.model_validate(s) for s in scans]


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a scan by ID with full details."""
    service = ScanService(db)
    scan = await service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return ScanResponse.model_validate(scan)


@router.get("/{scan_id}/events", response_model=List[ScanEventResponse])
async def get_scan_events(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scan lifecycle events."""
    service = ScanService(db)
    scan = await service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    events = await service.get_scan_events(scan_id)
    return [ScanEventResponse.model_validate(e) for e in events]


@router.get("/{scan_id}/summary", response_model=ScanSummary)
async def get_scan_summary(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scan summary with finding counts."""
    service = ScanService(db)
    scan = await service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    summary = await service.get_scan_summary(scan_id)
    return ScanSummary(**summary)


@router.post("/{scan_id}/cancel", response_model=dict)
async def cancel_scan(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running or queued scan."""
    service = ScanService(db)
    scan = await service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    try:
        await service.cancel_scan(scan_id, current_user.id, scan.workspace_id)
        return {"status": "cancelled", "scan_id": str(scan_id)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/assets/{asset_id}/scans", response_model=List[ScanListResponse])
async def get_asset_scans(
    asset_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get scans for a specific asset."""
    from app.services import AssetService, WorkspaceService

    asset_service = AssetService(db)
    asset = await asset_service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check workspace membership
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    service = ScanService(db)
    scans = await service.get_asset_scans(asset_id, limit, offset)
    return [ScanListResponse.model_validate(s) for s in scans]


# Scan Targets
@router.post("/targets", response_model=ScanTargetResponse, status_code=status.HTTP_201_CREATED)
async def create_scan_target(
    target_in: ScanTargetCreate,
    member: WorkspaceMember = Depends(require_workspace_admin),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new scan target (admin+ only)."""
    service = ScanService(db)
    target = await service.create_scan_target(member.workspace_id, current_user.id, target_in)
    return ScanTargetResponse.model_validate(target)


@router.get("/targets", response_model=List[ScanTargetResponse])
async def list_scan_targets(
    workspace_id: UUID,
    is_demo: Optional[bool] = Query(None),
    member: WorkspaceMember = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """List scan targets for a workspace."""
    if member.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Workspace mismatch")

    service = ScanService(db)
    targets = await service.list_scan_targets(workspace_id, is_demo)
    return [ScanTargetResponse.model_validate(t) for t in targets]


@router.get("/targets/active", response_model=List[ScanTargetResponse])
async def get_active_scan_targets(
    workspace_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    """Get active scan targets for a workspace."""
    if member.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="Workspace mismatch")

    service = ScanService(db)
    targets = await service.get_active_scan_targets(workspace_id)
    return [ScanTargetResponse.model_validate(t) for t in targets]


@router.patch("/targets/{target_id}", response_model=ScanTargetResponse)
async def update_scan_target(
    target_id: UUID,
    target_in: ScanTargetUpdate,
    member: WorkspaceMember = Depends(require_workspace_admin),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a scan target (admin+ only)."""
    service = ScanService(db)
    target = await service.update_scan_target(target_id, target_in)
    if not target:
        raise HTTPException(status_code=404, detail="Scan target not found")
    return ScanTargetResponse.model_validate(target)


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scan_target(
    target_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    """Delete a scan target (admin+ only)."""
    service = ScanService(db)
    success = await service.delete_scan_target(target_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan target not found")
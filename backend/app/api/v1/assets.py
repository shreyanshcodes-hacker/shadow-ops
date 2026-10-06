from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.security.auth import (
    get_current_user,
    require_workspace_member,
    require_workspace_admin,
)
from app.schemas import (
    AssetCreate,
    AssetUpdate,
    AssetResponse,
    AuthorizationCreate,
    AuthorizationResponse,
)
from app.services import AssetService
from app.models import Asset, AssetAuthorization, AuthorizationStatus

router = APIRouter()


@router.get("/{workspace_id}/assets", response_model=List[AssetResponse])
async def list_assets(
    workspace_id: UUID,
    member = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    assets = await service.list_assets(workspace_id)
    return [AssetResponse.model_validate(a) for a in assets]


@router.post("/{workspace_id}/assets", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    workspace_id: UUID,
    asset_in: AssetCreate,
    member = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.create_asset(workspace_id, current_user.id, asset_in)
    return AssetResponse.model_validate(asset)


@router.get("/assets/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return AssetResponse.model_validate(asset)


@router.patch("/assets/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: UUID,
    asset_in: AssetUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check workspace membership and permissions
    from app.services import WorkspaceService
    from app.models import WorkspaceRole
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if ws_member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    updated = await service.update_asset(asset_id, asset_in)
    if not updated:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetResponse.model_validate(updated)


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check workspace membership and permissions
    from app.services import WorkspaceService
    from app.models import WorkspaceRole
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    # Only asset creator or workspace admin/owner can delete
    if ws_member.user_id != asset.created_by and ws_member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    success = await service.delete_asset(asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Asset not found")


# Authorization routes
@router.post("/assets/{asset_id}/authorization", response_model=AuthorizationResponse, status_code=status.HTTP_201_CREATED)
async def create_authorization(
    asset_id: UUID,
    auth_in: AuthorizationCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    asset = await service.get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    auth = await service.create_authorization(asset_id, auth_in)
    return AuthorizationResponse.model_validate(auth)


@router.get("/assets/{asset_id}/authorization", response_model=AuthorizationResponse)
async def get_authorization(
    asset_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    auth = await service.get_authorization(asset_id)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorization not found")

    # Check workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(auth.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return AuthorizationResponse.model_validate(auth)
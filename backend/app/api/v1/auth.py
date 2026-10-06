from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from pydantic import BaseModel

from app.db.session import get_db
from app.security.auth import get_current_user, require_workspace_admin
from app.services import AssetService
from app.models import WorkspaceMember

router = APIRouter()


class AuthorizationVerifyRequest(BaseModel):
    pass


class AuthorizationRejectRequest(BaseModel):
    notes: str | None = None


@router.post("/assets/{asset_id}/authorization/verify", response_model=dict)
async def verify_authorization(
    asset_id: UUID,
    request: AuthorizationVerifyRequest,
    member: WorkspaceMember = Depends(require_workspace_admin),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    auth = await service.verify_authorization(asset_id, current_user.id)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorization not found")
    return {"status": "verified", "authorization_id": str(auth.id)}


@router.post("/assets/{asset_id}/authorization/reject", response_model=dict)
async def reject_authorization(
    asset_id: UUID,
    request: AuthorizationRejectRequest,
    member: WorkspaceMember = Depends(require_workspace_admin),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AssetService(db)
    auth = await service.reject_authorization(asset_id, request.notes)
    if not auth:
        raise HTTPException(status_code=404, detail="Authorization not found")
    return {"status": "rejected", "authorization_id": str(auth.id)}
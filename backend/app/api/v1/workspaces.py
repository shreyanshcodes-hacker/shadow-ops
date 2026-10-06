from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.security.auth import (
    get_current_user,
    require_workspace_member,
    require_workspace_admin,
    require_workspace_owner,
)
from app.schemas import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceListResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberUpdate,
    WorkspaceMemberResponse,
)
from app.services import WorkspaceService
from app.models import WorkspaceMember, WorkspaceRole

router = APIRouter()


@router.get("", response_model=List[WorkspaceListResponse])
async def list_workspaces(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    workspaces = await service.list_user_workspaces(current_user.id)
    return [
        WorkspaceListResponse(
            id=ws.id,
            name=ws.name,
            slug=ws.slug,
            plan=ws.plan,
            role=WorkspaceRole.OWNER if ws.owner_id == current_user.id else WorkspaceRole.MEMBER,
            created_at=ws.created_at,
        )
        for ws in workspaces
    ]


@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    workspace = await service.create_workspace(current_user.id, workspace_in)
    return WorkspaceResponse.model_validate(workspace)


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    workspace = await service.get_workspace(workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(workspace)


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: UUID,
    workspace_in: WorkspaceUpdate,
    member: WorkspaceMember = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    workspace = await service.update_workspace(workspace_id, workspace_in)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return WorkspaceResponse.model_validate(workspace)


@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_owner),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    success = await service.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")


# Workspace Members
@router.get("/{workspace_id}/members", response_model=List[WorkspaceMemberResponse])
async def list_workspace_members(
    workspace_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    members = await service.list_members(workspace_id)
    return [WorkspaceMemberResponse.model_validate(m) for m in members]


@router.post("/{workspace_id}/members", response_model=WorkspaceMemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_member(
    workspace_id: UUID,
    member_in: WorkspaceMemberCreate,
    member: WorkspaceMember = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        new_member = await service.invite_member(workspace_id, member.user_id, member_in)
        return WorkspaceMemberResponse.model_validate(new_member)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{workspace_id}/members/{user_id}", response_model=WorkspaceMemberResponse)
async def update_member_role(
    workspace_id: UUID,
    user_id: UUID,
    member_in: WorkspaceMemberUpdate,
    member: WorkspaceMember = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    # Prevent changing owner role
    target_member = await service.get_member(workspace_id, user_id)
    if target_member and target_member.role == WorkspaceRole.OWNER:
        raise HTTPException(status_code=403, detail="Cannot change owner role")

    # Prevent non-owners from promoting to admin
    if member_in.role == WorkspaceRole.ADMIN and member.role != WorkspaceRole.OWNER:
        raise HTTPException(status_code=403, detail="Only owners can promote to admin")

    updated = await service.update_member_role(workspace_id, user_id, member_in.role)
    if not updated:
        raise HTTPException(status_code=404, detail="Member not found")
    return WorkspaceMemberResponse.model_validate(updated)


@router.delete("/{workspace_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(
    workspace_id: UUID,
    user_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_admin),
    db: AsyncSession = Depends(get_db),
):
    service = WorkspaceService(db)
    try:
        success = await service.remove_member(workspace_id, user_id)
        if not success:
            raise HTTPException(status_code=404, detail="Member not found")
    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
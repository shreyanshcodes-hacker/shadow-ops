from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.security.auth import get_current_user, require_workspace_member
from app.agents.team.orchestrator import SecurityTeamOrchestrator, OrchestrationError
from app.repositories import SecurityTeamRunRepository, AgentRunRepository, TeamAssessmentRepository, TeamReviewRepository
from app.models import WorkspaceMember, SecurityTeamRunStatus
from app.schemas import BaseSchema
from app.ai.team_schemas import (
    SecurityTeamRunRequest, SecurityTeamRunResponse,
    AgentRunResponse, TeamAssessmentResponse, TeamReviewResponse,
)

router = APIRouter(prefix="/security-team", tags=["Security Team"])


# =============================================================================
# Request/Response Models (inline for now, could move to schemas)
# =============================================================================

class SecurityTeamRunCreateRequest(BaseSchema):
    asset_id: UUID
    scan_id: UUID
    analysis_mode: str = "standard"


class SecurityTeamRunListResponse(BaseSchema):
    id: UUID
    workspace_id: UUID
    asset_id: UUID
    scan_id: UUID
    status: str
    requested_by: UUID
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    orchestration_version: str
    team_summary: dict
    confidence: Optional[float] = None
    created_at: str
    updated_at: str


class AgentRunDetailResponse(BaseSchema):
    id: UUID
    team_run_id: UUID
    agent_name: str
    status: str
    input_reference: dict
    output: dict
    confidence: Optional[float] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    prompt_version: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    attempt: int
    created_at: str


class TeamReviewCreateRequest(BaseSchema):
    notes: Optional[str] = None


# =============================================================================
# Team Run Endpoints
# =============================================================================

@router.post("/runs", response_model=SecurityTeamRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_team_run(
    request: SecurityTeamRunCreateRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start a Security Team analysis run.
    
    Accepts a safe scope (asset_id, scan_id) and begins multi-agent orchestration.
    Returns the team run ID for polling status.
    """
    # Verify asset belongs to workspace
    from app.repositories import AssetRepository, ScanRepository
    asset_repo = AssetRepository(db)
    asset = await asset_repo.get_by_id(request.asset_id)
    if not asset or asset.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Verify scan belongs to workspace and asset
    scan_repo = ScanRepository(db)
    scan = await scan_repo.get_by_id(request.scan_id)
    if not scan or scan.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Scan not found")
    if scan.asset_id != request.asset_id:
        raise HTTPException(status_code=400, detail="Scan does not belong to this asset")
    
    # Check scan is completed
    if scan.status.value not in ["completed", "partial"]:
        raise HTTPException(status_code=400, detail="Scan must be completed before team analysis")
    
    # Create orchestrator and start run
    orchestrator = SecurityTeamOrchestrator(db)
    try:
        team_run = await orchestrator.start_team_run(
            workspace_id=member.workspace_id,
            asset_id=request.asset_id,
            scan_id=request.scan_id,
            user_id=current_user.id,
            analysis_mode=request.analysis_mode,
        )
    except OrchestrationError as e:
        if e.error_code == "ASSET_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Asset not found")
        elif e.error_code == "SCAN_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Scan not found")
        elif e.error_code == "SCAN_ASSET_MISMATCH":
            raise HTTPException(status_code=400, detail="Scan does not belong to this asset")
        elif e.error_code == "SCAN_NOT_COMPLETED":
            raise HTTPException(status_code=400, detail="Scan must be completed before team analysis")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to start team run: {e.message}")
    
    return SecurityTeamRunResponse.model_validate(team_run)


@router.get("/runs", response_model=List[SecurityTeamRunListResponse])
async def list_team_runs(
    workspace_id: UUID = Query(...),
    status: Optional[str] = Query(None),
    asset_id: Optional[UUID] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List security team runs for a workspace."""
    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = SecurityTeamRunStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    repo = SecurityTeamRunRepository(db)
    runs = await repo.get_by_workspace(workspace_id, status_filter, limit, offset)
    
    return [SecurityTeamRunListResponse.model_validate(r) for r in runs]


@router.get("/runs/{run_id}", response_model=SecurityTeamRunResponse)
async def get_team_run(
    run_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get security team run detail."""
    repo = SecurityTeamRunRepository(db)
    team_run = await repo.get_by_id(run_id)
    if not team_run:
        raise HTTPException(status_code=404, detail="Team run not found")
    
    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(team_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    return SecurityTeamRunResponse.model_validate(team_run)


@router.get("/runs/{run_id}/agents", response_model=List[AgentRunDetailResponse])
async def get_team_run_agents(
    run_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all agent runs for a team run."""
    repo = SecurityTeamRunRepository(db)
    team_run = await repo.get_by_id(run_id)
    if not team_run:
        raise HTTPException(status_code=404, detail="Team run not found")
    
    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(team_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    agent_repo = AgentRunRepository(db)
    agent_runs = await agent_repo.get_by_team_run(run_id)
    
    return [AgentRunDetailResponse.model_validate(ar) for ar in agent_runs]


@router.get("/runs/{run_id}/assessment", response_model=TeamAssessmentResponse)
async def get_team_assessment(
    run_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the final team assessment."""
    repo = SecurityTeamRunRepository(db)
    team_run = await repo.get_by_id(run_id)
    if not team_run:
        raise HTTPException(status_code=404, detail="Team run not found")
    
    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(team_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    assessment_repo = TeamAssessmentRepository(db)
    assessment = await assessment_repo.get_by_team_run(run_id)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found (team run may not have completed)")
    
    return TeamAssessmentResponse.model_validate(assessment)


@router.post("/runs/{run_id}/review", response_model=TeamReviewResponse, status_code=status.HTTP_201_CREATED)
async def submit_team_review(
    run_id: UUID,
    request: TeamReviewCreateRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Mark a team run as reviewed by a human.
    
    This does NOT mean vulnerability fixed, risk accepted, or remediation approved.
    It only means a human has reviewed the AI assessment.
    """
    repo = SecurityTeamRunRepository(db)
    team_run = await repo.get_by_id(run_id)
    if not team_run:
        raise HTTPException(status_code=404, detail="Team run not found")
    
    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(team_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    
    # Verify team run is in a reviewable state
    if team_run.status not in [SecurityTeamRunStatus.SUCCEEDED, SecurityTeamRunStatus.PARTIAL]:
        raise HTTPException(status_code=400, detail="Team run must be completed before review")
    
    orchestrator = SecurityTeamOrchestrator(db)
    try:
        review = await orchestrator.submit_human_review(
            team_run_id=run_id,
            workspace_id=team_run.workspace_id,
            reviewer_id=current_user.id,
            notes=request.notes,
        )
    except OrchestrationError as e:
        if e.error_code == "TEAM_RUN_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Team run not found")
        elif e.error_code == "ALREADY_REVIEWED":
            raise HTTPException(status_code=409, detail="Team run already reviewed")
        else:
            raise HTTPException(status_code=500, detail=f"Failed to submit review: {e.message}")
    
    return TeamReviewResponse.model_validate(review)


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_team_run(
    run_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running team run."""
    repo = SecurityTeamRunRepository(db)
    team_run = await repo.get_by_id(run_id)
    if not team_run:
        raise HTTPException(status_code=404, detail="Team run not found")
    
    # Verify workspace membership (admin/owner required for cancel)
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(team_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")
    if ws_member.role not in ["owner", "admin"]:
        raise HTTPException(status_code=403, detail="Only workspace owners/admins can cancel team runs")
    
    orchestrator = SecurityTeamOrchestrator(db)
    success = await orchestrator.cancel_team_run(run_id, current_user.id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel team run (not in queued/running state)")

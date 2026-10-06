from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.security.auth import get_current_user, require_workspace_member
from app.ai.manager import AIManager, AIManagerError
from app.ai.schemas import (
    FindingAiAnalysisResponse,
    AiRunResponse,
    AiProviderStatus,
    StartFindingAnalysisRequest,
)
from app.models import WorkspaceMember, AiRunStatus, FindingAiAnalysis
from app.repositories import AiRunRepository, FindingAiAnalysisRepository, FindingRepository
from app.schemas import BaseSchema

router = APIRouter(prefix="/ai", tags=["AI Analysis"])


@router.post("/findings/{finding_id}/ai-analysis", response_model=AiRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_finding_analysis(
    finding_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Start AI analysis for a specific finding.

    This creates an AI run and begins the analysis.
    The response includes the AI run ID for polling status.
    """
    # Verify the finding belongs to the workspace
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    if finding.workspace_id != member.workspace_id:
        raise HTTPException(status_code=403, detail="Finding not in this workspace")

    # Check if scan is completed (eligible for analysis)
    if finding.scan.status not in ["completed", "partial"]:
        raise HTTPException(status_code=400, detail="Scan must be completed before AI analysis")

    # Create AI manager and start analysis
    manager = AIManager(db)
    try:
        analysis = await manager.analyze_finding(
            finding_id=finding_id,
            user_id=current_user.id,
            workspace_id=member.workspace_id,
        )
    except AIManagerError as e:
        if e.error_code == "AI_AUTH_ERROR":
            raise HTTPException(status_code=503, detail="AI provider not configured")
        elif e.error_code == "FINDING_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Finding not found")
        else:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e.message}")

    # Get the AI run for response
    ai_run = await manager.get_ai_run(analysis.ai_run_id, member.workspace_id)
    if not ai_run:
        raise HTTPException(status_code=500, detail="Analysis created but run not found")

    return AiRunResponse.model_validate(ai_run)


@router.post("/scans/{scan_id}/analyze-finding", response_model=AiRunResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_finding_analysis_legacy(
    scan_id: UUID,
    request: StartFindingAnalysisRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Legacy endpoint - Start AI analysis for a specific finding.

    Use POST /findings/{finding_id}/ai-analysis instead.
    """
    # Verify the finding belongs to the scan and workspace
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(request.finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")
    if finding.workspace_id != member.workspace_id:
        raise HTTPException(status_code=403, detail="Finding not in this workspace")
    if finding.scan_id != scan_id:
        raise HTTPException(status_code=400, detail="Finding does not belong to this scan")

    # Check if scan is completed (eligible for analysis)
    if finding.scan.status not in ["completed", "partial"]:
        raise HTTPException(status_code=400, detail="Scan must be completed before AI analysis")

    # Create AI manager and start analysis
    manager = AIManager(db)
    try:
        analysis = await manager.analyze_finding(
            finding_id=request.finding_id,
            user_id=current_user.id,
            workspace_id=member.workspace_id,
        )
    except AIManagerError as e:
        if e.error_code == "AI_AUTH_ERROR":
            raise HTTPException(status_code=503, detail="AI provider not configured")
        elif e.error_code == "FINDING_NOT_FOUND":
            raise HTTPException(status_code=404, detail="Finding not found")
        else:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {e.message}")

    # Get the AI run for response
    ai_run = await manager.get_ai_run(analysis.ai_run_id, member.workspace_id)
    if not ai_run:
        raise HTTPException(status_code=500, detail="Analysis created but run not found")

    return AiRunResponse.model_validate(ai_run)


@router.get("/ai-analyses/{analysis_id}", response_model=FindingAiAnalysisResponse)
async def get_ai_analysis_by_id(
    analysis_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI analysis by analysis ID."""
    analysis_repo = FindingAiAnalysisRepository(db)
    analysis = await analysis_repo.get_by_id(analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="AI analysis not found")

    # Verify workspace membership
    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(analysis.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return FindingAiAnalysisResponse.model_validate(analysis)


@router.get("/scans/{scan_id}/ai-runs", response_model=List[AiRunResponse])
async def list_scan_ai_runs(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all AI runs for a scan."""
    # Verify scan access
    from app.services import ScanService
    scan_service = ScanService(db)
    scan = await scan_service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    manager = AIManager(db)
    ai_runs = await manager.list_ai_runs_for_scan(scan_id, scan.workspace_id)
    return [AiRunResponse.model_validate(r) for r in ai_runs]


@router.get("/ai-runs/{run_id}", response_model=AiRunResponse)
async def get_ai_run(
    run_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI run status and details."""
    manager = AIManager(db)
    # We need to check workspace membership
    from app.repositories import AiRunRepository
    ai_run_repo = AiRunRepository(db)
    ai_run = await ai_run_repo.get_by_id(run_id)
    if not ai_run:
        raise HTTPException(status_code=404, detail="AI run not found")

    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(ai_run.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return AiRunResponse.model_validate(ai_run)


@router.get("/findings/{finding_id}/ai-analysis", response_model=FindingAiAnalysisResponse)
async def get_finding_ai_analysis(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI analysis for a specific finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    manager = AIManager(db)
    analysis = await manager.get_finding_analysis(finding_id, finding.workspace_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="AI analysis not found")

    return FindingAiAnalysisResponse.model_validate(analysis)


@router.get("/findings/{finding_id}/ai-analyses", response_model=List[FindingAiAnalysisResponse])
async def get_finding_ai_analyses(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all AI analyses for a finding (version history)."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    manager = AIManager(db)
    analyses = await manager.get_all_finding_analyses(finding_id, finding.workspace_id)
    return [FindingAiAnalysisResponse.model_validate(a) for a in analyses]


@router.get("/providers/status", response_model=List[AiProviderStatus])
async def get_ai_provider_status(
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get status of configured AI providers.

    Returns configuration status (not secrets) for each provider.
    """
    from app.ai.safety import is_provider_configured
    from app.core.config import settings

    configured = is_provider_configured()

    providers = [
        AiProviderStatus(
            provider="gemini",
            configured=configured.get("gemini", False),
            model=settings.GEMINI_MODEL if configured.get("gemini") else None,
        ),
        AiProviderStatus(
            provider="grok",
            configured=configured.get("grok", False),
            model=settings.GROK_MODEL if configured.get("grok") else None,
        ),
    ]

    return providers


class AiAnalysisStatusResponse(BaseSchema):
    finding_id: UUID
    has_analysis: bool
    ai_run_id: Optional[UUID] = None
    status: Optional[str] = None
    error: Optional[str] = None


@router.get("/scans/{scan_id}/ai-analysis-status", response_model=List[AiAnalysisStatusResponse])
async def get_scan_ai_analysis_status(
    scan_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get AI analysis status for all findings in a scan.

    Returns status for each finding: not_analyzed, analyzing, completed, failed.
    """
    # Verify scan access
    from app.services import ScanService
    scan_service = ScanService(db)
    scan = await scan_service.get_scan(scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    from app.services import WorkspaceService
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(scan.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    # Get all findings for the scan
    finding_repo = FindingRepository(db)
    findings = await finding_repo.get_by_scan(scan_id)

    # Get AI runs for the scan
    manager = AIManager(db)
    ai_runs = await manager.list_ai_runs_for_scan(scan_id, scan.workspace_id)

    # Build status map
    run_by_finding = {}
    for run in ai_runs:
        if run.finding_id and run.finding_id not in run_by_finding:
            run_by_finding[run.finding_id] = run
        # Keep the latest run per finding

    statuses = []
    for finding in findings:
        run = run_by_finding.get(finding.id)
        if run:
            statuses.append(AiAnalysisStatusResponse(
                finding_id=finding.id,
                has_analysis=run.status == AiRunStatus.COMPLETED,
                ai_run_id=run.id,
                status=run.status.value,
                error=run.error_message if run.status == AiRunStatus.FAILED else None,
            ))
        else:
            statuses.append(AiAnalysisStatusResponse(
                finding_id=finding.id,
                has_analysis=False,
                status="not_analyzed",
            ))

    return statuses
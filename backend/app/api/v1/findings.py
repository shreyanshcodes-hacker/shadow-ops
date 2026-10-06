from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from app.db.session import get_db
from app.security.auth import get_current_user
from app.services import WorkspaceService
from app.repositories import FindingRepository, FindingEvidenceRepository
from app.models import FindingEvidence

router = APIRouter(prefix="/findings", tags=["Findings"])


@router.get("/{finding_id}/evidence", response_model=List[dict])
async def list_finding_evidence(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all evidence for a finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    evidence_repo = FindingEvidenceRepository(db)
    evidence_list = await evidence_repo.get_by_finding(finding_id)

    return [
        {
            "id": str(e.id),
            "finding_id": str(e.finding_id),
            "workspace_id": str(e.workspace_id),
            "evidence_type": e.evidence_type.value if e.evidence_type else "unknown",
            "title": e.title,
            "description": e.description,
            "content": e.content,
            "file_path": e.file_path,
            "line_start": e.line_start,
            "line_end": e.line_end,
            "storage_object_id": str(e.storage_object_id) if e.storage_object_id else None,
            "metadata": e.metadata,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in evidence_list
    ]


@router.get("/{finding_id}/ai-analyses", response_model=List[dict])
async def list_finding_ai_analyses(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all AI analyses for a finding (version history)."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    from app.repositories import FindingAiAnalysisRepository
    analysis_repo = FindingAiAnalysisRepository(db)
    analyses = await analysis_repo.get_by_finding(finding_id)

    return [
        {
            "id": str(a.id),
            "finding_id": str(a.finding_id),
            "ai_run_id": str(a.ai_run_id),
            "workspace_id": str(a.workspace_id),
            "summary": a.summary,
            "vulnerability_type": a.vulnerability_type,
            "severity_assessment": a.severity_assessment,
            "confidence": a.confidence,
            "exploitability_assessment": a.exploitability_assessment,
            "impact_assessment": a.impact_assessment,
            "affected_component": a.affected_component,
            "attack_preconditions": a.attack_preconditions,
            "evidence_interpretation": a.evidence_interpretation,
            "reasoning": a.reasoning,
            "recommended_next_steps": a.recommended_next_steps,
            "uncertainty": a.uncertainty,
            "supporting_evidence": a.supporting_evidence,
            "model": a.model,
            "provider": a.provider.value if a.provider else None,
            "prompt_version": a.prompt_version,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        for a in analyses
    ]
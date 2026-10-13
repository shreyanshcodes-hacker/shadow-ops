from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.models import Profile, VerificationStatus, VerificationPolicy
from app.schemas import (
    VerificationJobListResponse,
    VerificationJobResponse,
    VerificationDetailResponse,
    StartVerificationRequest,
    VerificationReviewRequest,
    RerunVerificationRequest,
    VerificationPolicyCreate,
    VerificationPolicyResponse,
    VerificationBaselineResponse,
    VerificationCheckResponse,
    EvidenceComparisonResponse,
    VerificationReviewResponse,
)
from app.services.verification import VerificationService
from app.services.policy import VerificationPolicyEngine
from app.services.baseline import BaselineCaptureService
from app.services.comparison import EvidenceComparisonService


router = APIRouter(prefix="/verifications", tags=["verifications"])


def get_verification_service(db: AsyncSession = Depends(get_db)) -> VerificationService:
    return VerificationService(db)


def get_policy_engine(db: AsyncSession = Depends(get_db)) -> VerificationPolicyEngine:
    return VerificationPolicyEngine(db)


@router.post(
    "/start",
    response_model=VerificationJobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new verification job",
)
async def start_verification(
    request: StartVerificationRequest,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Create and start a verification job for a remediation application."""
    job = await service.create_verification_job(
        user_id=current_user.id,
        remediation_application_id=request.remediation_application_id,
        idempotency_key=request.idempotency_key,
    )

    job = await service.start_verification(job.id, current_user.id)
    return job


@router.get(
    "",
    response_model=List[VerificationJobListResponse],
    summary="List verification jobs",
)
async def list_verifications(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    status_filter: Optional[VerificationStatus] = Query(None, alias="status"),
    finding_id: Optional[UUID] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """List verification jobs for a workspace."""
    jobs = await service.list_verification_jobs(
        workspace_id=workspace_id,
        user_id=current_user.id,
        status=status_filter,
        finding_id=finding_id,
        limit=limit,
        offset=offset,
    )
    return jobs


@router.get(
    "/{job_id}",
    response_model=VerificationJobResponse,
    summary="Get verification job by ID",
)
async def get_verification(
    job_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Get verification job details."""
    job = await service.get_verification_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")

    await service._verify_workspace_access(current_user.id, job.workspace_id)
    return job


@router.get(
    "/{job_id}/detail",
    response_model=VerificationDetailResponse,
    summary="Get verification job with all related data",
)
async def get_verification_detail(
    job_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Get verification job with baseline, checks, comparisons, and reviews."""
    job = await service.get_verification_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Verification job not found")

    await service._verify_workspace_access(current_user.id, job.workspace_id)

    db = service.db
    baseline_service = BaselineCaptureService(db)
    comparison_service = EvidenceComparisonService(db)

    baseline = await baseline_service.get_baseline(job_id)

    result = await db.execute(
        select(VerificationCheck).where(VerificationCheck.verification_job_id == job_id)
    )
    checks = list(result.scalars().all())

    result = await db.execute(
        select(EvidenceComparison).where(EvidenceComparison.verification_job_id == job_id)
    )
    comparisons = list(result.scalars().all())

    result = await db.execute(
        select(VerificationReview).where(VerificationReview.verification_job_id == job_id)
    )
    reviews = list(result.scalars().all())

    result = await db.execute(
        select(VerificationPolicy).where(VerificationPolicy.version == job.policy_version)
    )
    policy = result.scalar_one_or_none()

    return VerificationDetailResponse(
        job=job,
        baseline=VerificationBaselineResponse.model_validate(baseline) if baseline else None,
        checks=[VerificationCheckResponse.model_validate(c) for c in checks],
        comparisons=[EvidenceComparisonResponse.model_validate(c) for c in comparisons],
        reviews=[VerificationReviewResponse.model_validate(r) for r in reviews],
        policy=VerificationPolicyResponse.model_validate(policy) if policy else None,
    )


@router.post(
    "/{job_id}/review",
    response_model=VerificationJobResponse,
    summary="Submit human review decision",
)
async def submit_review(
    job_id: UUID,
    request: VerificationReviewRequest,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Submit human review decision for a verification job."""
    job = await service.submit_review(
        job_id=job_id,
        user_id=current_user.id,
        decision=request.decision.value,
        justification=request.justification,
        notes=request.notes,
    )
    return job


@router.post(
    "/{job_id}/rerun",
    response_model=VerificationJobResponse,
    summary="Rerun a verification job",
)
async def rerun_verification(
    job_id: UUID,
    request: RerunVerificationRequest,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Rerun a verification job."""
    job = await service.rerun_verification(
        job_id=job_id,
        user_id=current_user.id,
        idempotency_key=request.idempotency_key,
    )
    return job


@router.post(
    "/{job_id}/cancel",
    response_model=VerificationJobResponse,
    summary="Cancel a verification job",
)
async def cancel_verification(
    job_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: VerificationService = Depends(get_verification_service),
):
    """Cancel a running verification job."""
    job = await service.cancel_verification(job_id, current_user.id)
    return job


@router.get(
    "/policies",
    response_model=List[VerificationPolicyResponse],
    summary="List verification policies",
)
async def list_policies(
    current_user: Profile = Depends(get_current_user),
    engine: VerificationPolicyEngine = Depends(get_policy_engine),
):
    """List all verification policies."""
    from app.models import VerificationPolicy
    result = await engine.db.execute(
        select(VerificationPolicy).order_by(VerificationPolicy.created_at.desc())
    )
    return list(result.scalars().all())


@router.post(
    "/policies",
    response_model=VerificationPolicyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create verification policy",
)
async def create_policy(
    request: VerificationPolicyCreate,
    current_user: Profile = Depends(get_current_user),
    engine: VerificationPolicyEngine = Depends(get_policy_engine),
):
    """Create a new verification policy."""
    policy = await engine.create_policy(
        version=request.version,
        name=request.name,
        description=request.description,
        policy_config=request.policy_config,
        creator_id=current_user.id,
        is_active=request.is_active,
    )
    return policy
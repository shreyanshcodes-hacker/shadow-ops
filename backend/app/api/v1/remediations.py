from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional

from app.db.session import get_db
from app.security.auth import get_current_user, require_workspace_member
from app.repositories import (
    RemediationProposalRepository, PatchVersionRepository, ValidationRunRepository,
    RemediationApprovalRepository, RemediationApplicationRepository,
    RemediationRollbackRepository, RemediationVerificationHandoffRepository,
    FindingRepository, AssetRepository
)
from app.models import (
    RemediationProposal, RemediationStatus, PatchVersion, ValidationRun,
    ValidationStatus, ValidationCheckType, RemediationApproval,
    RemediationApplication, ApplicationStatus, RemediationRollback,
    RollbackStatus, WorkspaceMember, WorkspaceRole, Finding
)
from app.schemas import (
    RemediationProposalResponse, RemediationProposalListResponse,
    PatchVersionResponse, ValidationRunResponse, RemediationApprovalResponse,
    RemediationApplicationResponse, RemediationRollbackResponse,
    RemediationVerificationHandoffResponse, RemediationDetailResponse,
    GenerateRemediationRequest, ValidateRemediationRequest,
    ApproveRemediationRequest, RejectRemediationRequest,
    ApplyRemediationRequest, RollbackRemediationRequest,
    RequestVerificationRequest,
)
from app.services.remediation import RemediationService
from app.services.validation import ValidationPipeline
from app.services.approval import ApprovalService
from app.services.application import PatchApplicationAdapter
from app.services.rollback import RollbackService
from app.services.patch import PatchProcessor

router = APIRouter(prefix="/remediations", tags=["Remediations"])


# =============================================================================
# Dependency: Get authorized workspace root
# =============================================================================
def get_workspace_root() -> str:
    """
    Get the authorized workspace root path.
    In production, this should be configured per workspace/asset.
    For Stage 8, we use a fixed path or environment variable.
    """
    import os
    return os.getenv("REMEDIATION_WORKSPACE_ROOT", "/workspace")


# =============================================================================
# Proposal Endpoints
# =============================================================================

@router.post("/findings/{finding_id}/remediations", response_model=RemediationProposalResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_remediation(
    finding_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate an AI remediation proposal for a finding.

    Returns the proposal ID for polling status.
    """
    # Verify finding belongs to workspace
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding or finding.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Finding not found")

    # Check finding is in a state that can be remediated
    if finding.status.value in ["fixed", "false_positive", "wont_fix", "risk_accepted"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot generate remediation for finding with status: {finding.status.value}"
        )

    # Generate remediation
    service = RemediationService(db)
    try:
        proposal = await service.generate_proposal(
            finding_id=finding_id,
            user_id=current_user.id,
            workspace_id=member.workspace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate remediation: {str(e)}")

    return RemediationProposalResponse.model_validate(proposal)


@router.get("", response_model=List[RemediationProposalListResponse])
async def list_remediations(
    workspace_id: UUID = Query(...),
    finding_id: Optional[UUID] = Query(None),
    asset_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List remediation proposals for a workspace."""
    # Verify workspace membership (already done by require_workspace_member)

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = RemediationStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    service = RemediationService(db)
    proposals = await service.list_proposals(
        workspace_id=workspace_id,
        status=status_filter,
        finding_id=finding_id,
        asset_id=asset_id,
        limit=limit,
        offset=offset,
    )

    return [RemediationProposalListResponse.model_validate(p) for p in proposals]


@router.get("/{proposal_id}", response_model=RemediationDetailResponse)
async def get_remediation(
    proposal_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full remediation detail with all related records."""
    service = RemediationService(db)
    detail = await service.get_proposal_detail(proposal_id, member.workspace_id)

    if not detail:
        raise HTTPException(status_code=404, detail="Remediation proposal not found")

    # Convert to response models
    return RemediationDetailResponse(
        proposal=RemediationProposalResponse.model_validate(detail["proposal"]),
        patch_versions=[PatchVersionResponse.model_validate(p) for p in detail["patch_versions"]],
        validations=[ValidationRunResponse.model_validate(v) for v in detail["validations"]],
        approvals=[RemediationApprovalResponse.model_validate(a) for a in detail["approvals"]],
        applications=[RemediationApplicationResponse.model_validate(a) for a in detail["applications"]],
        rollbacks=[RemediationRollbackResponse.model_validate(r) for r in detail["rollbacks"]],
        verification_handoff=RemediationVerificationHandoffResponse.model_validate(detail["verification_handoff"]) if detail["verification_handoff"] else None,
    )


# =============================================================================
# Validation Endpoints
# =============================================================================

@router.post("/{proposal_id}/validate", response_model=List[ValidationRunResponse])
async def validate_remediation(
    proposal_id: UUID,
    request: ValidateRemediationRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run validation pipeline for a remediation proposal."""
    # Verify proposal
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    if not proposal.patch_reference:
        raise HTTPException(status_code=400, detail="No patch version associated with proposal")

    # Run validation pipeline
    workspace_root = get_workspace_root()
    pipeline = ValidationPipeline(db, workspace_root)

    try:
        results = await pipeline.run_all_validations(
            proposal_id=proposal_id,
            patch_version_id=proposal.patch_reference,
            workspace_id=member.workspace_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

    # Update proposal status based on results
    all_passed = all(r.passed for r in results)
    if not all_passed:
        # Check if critical validations failed
        critical_failed = any(
            not r.passed and r.check_type in [
                ValidationCheckType.PATCH_INTEGRITY,
                ValidationCheckType.DIFF_PARSING,
                ValidationCheckType.PATH_ALLOWLIST,
            ]
            for r in results
        )
        new_status = RemediationStatus.VALIDATION_FAILED
    else:
        new_status = RemediationStatus.AWAITING_APPROVAL

    await proposal_repo.update(proposal_id, {
        "status": new_status,
        "validation_results": {r.check_type.value: {"passed": r.passed, "message": r.message} for r in results},
    })

    # Fetch updated validation runs
    validation_repo = ValidationRunRepository(db)
    validations = await validation_repo.get_by_proposal(proposal_id)

    return [ValidationRunResponse.model_validate(v) for v in validations]


@router.get("/{proposal_id}/validations", response_model=List[ValidationRunResponse])
async def get_validations(
    proposal_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all validation runs for a proposal."""
    validation_repo = ValidationRunRepository(db)
    validations = await validation_repo.get_by_proposal(proposal_id)

    # Verify workspace access
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return [ValidationRunResponse.model_validate(v) for v in validations]


# =============================================================================
# Approval Endpoints
# =============================================================================

@router.post("/{proposal_id}/approve", response_model=RemediationApprovalResponse)
async def approve_remediation(
    proposal_id: UUID,
    request: ApproveRemediationRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Approve a remediation proposal (admin/owner only)."""
    # Verify proposal
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Verify user has approval permission
    if member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only workspace owners and admins can approve remediations")

    # Verify patch version
    patch_repo = PatchVersionRepository(db)
    patch_version = await patch_repo.get_by_id(request.patch_version_id)
    if not patch_version or patch_version.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Invalid patch version")

    # Approve
    approval_service = ApprovalService(db)
    try:
        approval = await approval_service.approve(
            proposal_id=proposal_id,
            patch_version_id=request.patch_version_id,
            approver_id=current_user.id,
            workspace_id=member.workspace_id,
            justification=request.justification,
            conditions=request.conditions,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RemediationApprovalResponse.model_validate(approval)


@router.post("/{proposal_id}/reject", response_model=RemediationApprovalResponse)
async def reject_remediation(
    proposal_id: UUID,
    request: RejectRemediationRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reject a remediation proposal (admin/owner only)."""
    # Verify proposal
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Verify user has approval permission
    if member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only workspace owners and admins can reject remediations")

    # Verify patch version
    patch_repo = PatchVersionRepository(db)
    patch_version = await patch_repo.get_by_id(request.patch_version_id)
    if not patch_version or patch_version.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Invalid patch version")

    # Reject
    approval_service = ApprovalService(db)
    try:
        approval = await approval_service.reject(
            proposal_id=proposal_id,
            patch_version_id=request.patch_version_id,
            rejecter_id=current_user.id,
            workspace_id=member.workspace_id,
            justification=request.justification,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return RemediationApprovalResponse.model_validate(approval)


@router.get("/{proposal_id}/approvals", response_model=List[RemediationApprovalResponse])
async def get_approvals(
    proposal_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get approval history for a proposal."""
    approval_repo = RemediationApprovalRepository(db)
    approvals = await approval_repo.get_by_proposal(proposal_id)

    # Verify workspace access
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return [RemediationApprovalResponse.model_validate(a) for a in approvals]


# =============================================================================
# Application Endpoints
# =============================================================================

@router.post("/{proposal_id}/apply", response_model=RemediationApplicationResponse)
async def apply_remediation(
    proposal_id: UUID,
    request: ApplyRemediationRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Apply an approved remediation patch (admin/owner only)."""
    # Verify proposal
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Verify user has application permission
    if member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only workspace owners and admins can apply remediations")

    # Verify approval
    approval_repo = RemediationApprovalRepository(db)
    approval = await approval_repo.get_by_id(request.approval_id)
    if not approval or approval.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Invalid approval")

    if approval.decision != "approved":
        raise HTTPException(status_code=400, detail="Approval decision is not 'approved'")

    # Verify patch version
    patch_repo = PatchVersionRepository(db)
    patch_version = await patch_repo.get_by_id(request.patch_version_id)
    if not patch_version or patch_version.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Invalid patch version")

    if approval.patch_version_id != request.patch_version_id:
        raise HTTPException(status_code=400, detail="Approval is for different patch version")

    # Apply patch
    workspace_root = get_workspace_root()
    adapter = PatchApplicationAdapter(db, workspace_root)

    try:
        result = await adapter.apply_patch(
            proposal_id=proposal_id,
            patch_version_id=request.patch_version_id,
            approval_id=request.approval_id,
            applier_id=current_user.id,
            workspace_id=member.workspace_id,
            idempotency_key=request.idempotency_key,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Application failed: {str(e)}")

    # Fetch created application
    application_repo = RemediationApplicationRepository(db)
    application = await application_repo.get_by_id(result.application_id)

    return RemediationApplicationResponse.model_validate(application)


@router.get("/{proposal_id}/applications", response_model=List[RemediationApplicationResponse])
async def get_applications(
    proposal_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get application history for a proposal."""
    application_repo = RemediationApplicationRepository(db)
    applications = await application_repo.get_by_proposal(proposal_id)

    # Verify workspace access
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return [RemediationApplicationResponse.model_validate(a) for a in applications]


# =============================================================================
# Rollback Endpoints
# =============================================================================

@router.post("/{proposal_id}/rollback", response_model=RemediationRollbackResponse)
async def rollback_remediation(
    proposal_id: UUID,
    request: RollbackRemediationRequest,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rollback an applied remediation (admin/owner only)."""
    # Verify proposal
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    # Verify user has rollback permission
    if member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Only workspace owners and admins can rollback remediations")

    # Verify application
    application_repo = RemediationApplicationRepository(db)
    application = await application_repo.get_by_id(request.application_id)
    if not application or application.proposal_id != proposal_id:
        raise HTTPException(status_code=400, detail="Invalid application")

    # Rollback
    workspace_root = get_workspace_root()
    rollback_service = RollbackService(db, workspace_root)

    try:
        result = await rollback_service.rollback(
            application_id=request.application_id,
            requester_id=current_user.id,
            workspace_id=member.workspace_id,
            reason=request.reason,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

    # Fetch created rollback
    rollback_repo = RemediationRollbackRepository(db)
    rollback = await rollback_repo.get_by_id(result.rollback_id)

    return RemediationRollbackResponse.model_validate(rollback)


@router.get("/{proposal_id}/rollbacks", response_model=List[RemediationRollbackResponse])
async def get_rollbacks(
    proposal_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get rollback history for a proposal."""
    rollback_repo = RemediationRollbackRepository(db)
    rollbacks = await rollback_repo.get_by_proposal(proposal_id)

    # Verify workspace access
    proposal_repo = RemediationProposalRepository(db)
    proposal = await proposal_repo.get_by_id(proposal_id)
    if not proposal or proposal.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Proposal not found")

    return [RemediationRollbackResponse.model_validate(r) for r in rollbacks]


@router.get("/applications/{application_id}/rollback-status")
async def get_rollback_status(
    application_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if rollback is available for an application."""
    workspace_root = get_workspace_root()
    rollback_service = RollbackService(db, workspace_root)

    status = await rollback_service.get_rollback_status(application_id, member.workspace_id)
    return status


# =============================================================================
# Verification Handoff Endpoints
# =============================================================================

@router.post("/applications/{application_id}/request-verification")
async def request_verification(
    application_id: UUID,
    member: WorkspaceMember = Depends(require_workspace_member),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Request verification for an applied remediation (hands off to verification stage)."""
    application_repo = RemediationApplicationRepository(db)
    application = await application_repo.get_by_id(application_id)
    if not application or application.workspace_id != member.workspace_id:
        raise HTTPException(status_code=404, detail="Application not found")

    if application.status != ApplicationStatus.VERIFIED:
        raise HTTPException(status_code=400, detail="Application must be verified before requesting verification")

    handoff_repo = RemediationVerificationHandoffRepository(db)
    handoff = await handoff_repo.get_by_application(application_id)

    if not handoff:
        raise HTTPException(status_code=404, detail="Verification handoff not found")

    # Update handoff status
    await handoff_repo.update(handoff.id, {
        "verification_requested": True,
        "verification_requested_at": time.time(),
        "status": "VERIFICATION_REQUESTED",
    })

    # Audit log
    from app.security.audit import audit_log
    await audit_log(
        db=db,
        workspace_id=member.workspace_id,
        action="remediation.verification_requested",
        resource_type="remediation_verification_handoff",
        resource_id=handoff.id,
        new_state={
            "application_id": str(application_id),
            "proposal_id": str(application.proposal_id),
            "requested_by": str(current_user.id),
        },
        user_id=current_user.id,
    )

    return {"message": "Verification requested", "handoff_id": str(handoff.id)}


# Import time for timestamps
import time
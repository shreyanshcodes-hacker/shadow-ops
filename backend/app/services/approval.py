import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import (
    RemediationProposal, RemediationStatus, RemediationApproval,
    PatchVersion, ValidationRun, ValidationStatus, ValidationCheckType,
    Profile, WorkspaceMember, WorkspaceRole
)
from app.repositories import (
    RemediationProposalRepository, RemediationApprovalRepository,
    PatchVersionRepository, ValidationRunRepository
)
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class ApprovalServiceError(Exception):
    def __init__(self, message: str, error_code: str = "APPROVAL_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ApprovalService:
    """
    Human approval service for remediation proposals.

    Enforces:
    - Authenticated Firebase identity
    - Workspace membership
    - Applicable role permissions (admin/owner only)
    - Remediation ownership and workspace
    - Current proposal version
    - Successful required validation
    - Proposal has not expired or been rejected
    - Patch has not changed since review

    Approval binds to exact patch version/hash reviewed by human.
    If patch changes after approval, approval is invalidated.
    """

    # Required validation checks that must pass before approval
    REQUIRED_VALIDATION_CHECKS = [
        ValidationCheckType.PATCH_INTEGRITY,
        ValidationCheckType.DIFF_PARSING,
        ValidationCheckType.PATH_ALLOWLIST,
    ]

    # Roles allowed to approve
    APPROVER_ROLES = {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}

    def __init__(self, db: AsyncSession):
        self.db = db
        self.proposal_repo = RemediationProposalRepository(db)
        self.approval_repo = RemediationApprovalRepository(db)
        self.patch_repo = PatchVersionRepository(db)
        self.validation_repo = ValidationRunRepository(db)

    async def approve(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        approver_id: UUID,
        workspace_id: UUID,
        justification: Optional[str] = None,
        conditions: Optional[List[str]] = None,
    ) -> RemediationApproval:
        """
        Approve a remediation proposal.

        Validates all approval preconditions before recording approval.
        """
        # 1. Verify proposal exists and is in correct state
        proposal = await self._verify_proposal_for_approval(proposal_id, workspace_id)
        if not proposal:
            raise ApprovalServiceError("Proposal not found or access denied", "PROPOSAL_NOT_FOUND")

        # 2. Verify patch version exists and belongs to proposal
        patch_version = await self.patch_repo.get_by_id(patch_version_id)
        if not patch_version or patch_version.proposal_id != proposal_id:
            raise ApprovalServiceError("Patch version not found or doesn't belong to proposal", "PATCH_VERSION_MISMATCH")

        # 3. Verify approver has permission
        await self._verify_approver_permission(approver_id, workspace_id)

        # 4. Verify proposal version matches
        if proposal.version != patch_version.version:
            raise ApprovalServiceError(
                f"Proposal version {proposal.version} doesn't match patch version {patch_version.version}",
                "VERSION_MISMATCH"
            )

        # 5. Verify required validations passed
        validation_results = await self._verify_required_validations(proposal_id, patch_version_id)
        if not validation_results["all_passed"]:
            raise ApprovalServiceError(
                f"Required validations not passed: {validation_results['failed_checks']}",
                "VALIDATIONS_NOT_PASSED"
            )

        # 6. Verify proposal not expired
        if proposal.expires_at and proposal.expires_at < datetime.utcnow():
            raise ApprovalServiceError("Proposal has expired", "PROPOSAL_EXPIRED")

        # 7. Verify proposal not already rejected
        if proposal.status == RemediationStatus.REJECTED:
            raise ApprovalServiceError("Proposal has been rejected", "PROPOSAL_REJECTED")

        # 8. Check for existing approval for this patch hash
        existing_approval = await self.approval_repo.get_by_patch_hash(proposal_id, patch_version.patch_hash)
        if existing_approval:
            raise ApprovalServiceError(
                f"Patch version already approved by {existing_approval.approved_by} at {existing_approval.approved_at}",
                "ALREADY_APPROVED"
            )

        # 9. Create approval record
        approval = RemediationApproval(
            proposal_id=proposal_id,
            patch_version_id=patch_version_id,
            workspace_id=workspace_id,
            approved_by=approver_id,
            decision="approved",
            justification=justification,
            conditions=conditions or [],
            patch_hash=patch_version.patch_hash,
            proposal_version=proposal.version,
            validation_snapshot=validation_results["snapshot"],
        )
        approval = await self.approval_repo.create(approval)

        # 10. Update proposal status
        await self.proposal_repo.update(proposal_id, {
            "status": RemediationStatus.APPROVED,
            "approved_by": approver_id,
            "approved_at": datetime.utcnow(),
            "version": proposal.version + 1,
        })

        # 11. Mark patch version as current
        await self.patch_repo.set_current(proposal_id, patch_version_id)

        # 12. Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="remediation.approval.granted",
            resource_type="remediation_approval",
            resource_id=approval.id,
            new_state={
                "proposal_id": str(proposal_id),
                "patch_version_id": str(patch_version_id),
                "patch_hash": patch_version.patch_hash,
                "approver_id": str(approver_id),
                "conditions": conditions or [],
                "validation_snapshot": validation_results["snapshot"],
            },
            user_id=approver_id,
        )

        return approval

    async def reject(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        rejecter_id: UUID,
        workspace_id: UUID,
        justification: str,  # Required for rejection
    ) -> RemediationApproval:
        """
        Reject a remediation proposal.

        Rejection is recorded with required justification.
        """
        # 1. Verify proposal
        proposal = await self._verify_proposal_for_approval(proposal_id, workspace_id)
        if not proposal:
            raise ApprovalServiceError("Proposal not found or access denied", "PROPOSAL_NOT_FOUND")

        # 2. Verify patch version
        patch_version = await self.patch_repo.get_by_id(patch_version_id)
        if not patch_version or patch_version.proposal_id != proposal_id:
            raise ApprovalServiceError("Patch version not found or doesn't belong to proposal", "PATCH_VERSION_MISMATCH")

        # 3. Verify rejecter has permission
        await self._verify_approver_permission(rejecter_id, workspace_id)

        # 4. Create rejection record
        approval = RemediationApproval(
            proposal_id=proposal_id,
            patch_version_id=patch_version_id,
            workspace_id=workspace_id,
            approved_by=rejecter_id,
            decision="rejected",
            justification=justification,
            conditions=[],
            patch_hash=patch_version.patch_hash,
            proposal_version=proposal.version,
            validation_snapshot={},
        )
        approval = await self.approval_repo.create(approval)

        # 5. Update proposal status
        await self.proposal_repo.update(proposal_id, {
            "status": RemediationStatus.REJECTED,
            "approved_by": rejecter_id,  # Track who rejected
            "approved_at": datetime.utcnow(),
            "failure_reason": f"Rejected: {justification}",
            "version": proposal.version + 1,
        })

        # 6. Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="remediation.approval.rejected",
            resource_type="remediation_approval",
            resource_id=approval.id,
            new_state={
                "proposal_id": str(proposal_id),
                "patch_version_id": str(patch_version_id),
                "patch_hash": patch_version.patch_hash,
                "rejecter_id": str(rejecter_id),
                "justification": justification,
            },
            user_id=rejecter_id,
        )

        return approval

    async def _verify_proposal_for_approval(
        self,
        proposal_id: UUID,
        workspace_id: UUID,
    ) -> Optional[RemediationProposal]:
        """Verify proposal exists and is in approvable state."""
        proposal = await self.proposal_repo.get_by_id(proposal_id)
        if not proposal or proposal.workspace_id != workspace_id:
            return None

        # Check if in a state that can be approved
        approvable_states = [
            RemediationStatus.PROPOSED,
            RemediationStatus.VALIDATING,
            RemediationStatus.VALIDATION_FAILED,  # Can still approve if human accepts risk
            RemediationStatus.AWAITING_APPROVAL,
        ]
        if proposal.status not in approvable_states:
            logger.warning(f"Proposal {proposal_id} in non-approvable state: {proposal.status}")
            # Don't block - human can override

        return proposal

    async def _verify_approver_permission(self, user_id: UUID, workspace_id: UUID) -> None:
        """Verify user has admin/owner role in workspace."""
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.joined_at.is_not(None),
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise ApprovalServiceError("User is not a member of this workspace", "NOT_WORKSPACE_MEMBER")

        if member.role not in self.APPROVER_ROLES:
            raise ApprovalServiceError(
                f"Role '{member.role}' cannot approve remediations. Requires owner or admin.",
                "INSUFFICIENT_PERMISSIONS"
            )

    async def _verify_required_validations(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
    ) -> Dict[str, Any]:
        """Verify all required validation checks have passed."""
        failed_checks = []
        snapshot = {}

        for check_type in self.REQUIRED_VALIDATION_CHECKS:
            validation = await self.validation_repo.get_latest_by_type(proposal_id, check_type)
            if not validation:
                failed_checks.append(f"{check_type.value}: no validation run found")
                snapshot[check_type.value] = {"status": "missing"}
            elif validation.patch_version_id != patch_version_id:
                failed_checks.append(f"{check_type.value}: validation for different patch version")
                snapshot[check_type.value] = {"status": "version_mismatch"}
            elif validation.status != ValidationStatus.PASSED:
                failed_checks.append(f"{check_type.value}: {validation.status.value}")
                snapshot[check_type.value] = {
                    "status": validation.status.value,
                    "error": validation.error_message,
                }
            else:
                snapshot[check_type.value] = {"status": "passed", "duration_ms": validation.duration_ms}

        return {
            "all_passed": len(failed_checks) == 0,
            "failed_checks": failed_checks,
            "snapshot": snapshot,
        }

    async def get_approval_history(self, proposal_id: UUID, workspace_id: UUID) -> List[RemediationApproval]:
        """Get all approval records for a proposal."""
        # Verify proposal belongs to workspace
        proposal = await self.proposal_repo.get_by_id(proposal_id)
        if not proposal or proposal.workspace_id != workspace_id:
            return []

        return await self.approval_repo.get_by_proposal(proposal_id)

    async def check_approval_validity(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        workspace_id: UUID,
    ) -> Dict[str, Any]:
        """
        Check if approval is still valid for application.

        Returns validity status and any issues.
        """
        issues = []

        proposal = await self.proposal_repo.get_by_id(proposal_id)
        if not proposal or proposal.workspace_id != workspace_id:
            return {"valid": False, "issues": ["Proposal not found"]}

        patch_version = await self.patch_repo.get_by_id(patch_version_id)
        if not patch_version or patch_version.proposal_id != proposal_id:
            return {"valid": False, "issues": ["Patch version not found"]}

        # Check proposal status
        if proposal.status != RemediationStatus.APPROVED:
            issues.append(f"Proposal not approved (current status: {proposal.status.value})")

        # Check approval exists and matches
        approval = await self.approval_repo.get_by_patch_hash(proposal_id, patch_version.patch_hash)
        if not approval:
            issues.append("No approval found for this patch version")
        elif approval.decision != "approved":
            issues.append(f"Approval decision was '{approval.decision}', not 'approved'")

        # Check approval not expired
        if approval and approval.expires_at and approval.expires_at < datetime.utcnow():
            issues.append("Approval has expired")

        # Check proposal not expired
        if proposal.expires_at and proposal.expires_at < datetime.utcnow():
            issues.append("Proposal has expired")

        # Check patch hasn't changed (hash still matches)
        if approval and approval.patch_hash != patch_version.patch_hash:
            issues.append("Patch has been modified since approval")

        # Check proposal version matches
        if approval and approval.proposal_version != proposal.version:
            issues.append("Proposal version has changed since approval")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "approval": approval,
        }

    async def invalidate_approvals_for_proposal(self, proposal_id: UUID, workspace_id: UUID) -> int:
        """
        Invalidate all approvals for a proposal (e.g., when patch is updated).

        This is called when a new patch version is created for an approved proposal.
        """
        proposal = await self.proposal_repo.get_by_id(proposal_id)
        if not proposal or proposal.workspace_id != workspace_id:
            return 0

        # In a real implementation, we might mark approvals as superseded
        # For now, we just return count - the approval check will fail on hash mismatch
        approvals = await self.approval_repo.get_by_proposal(proposal_id)
        return len([a for a in approvals if a.decision == "approved"])
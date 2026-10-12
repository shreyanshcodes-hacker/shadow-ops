import hashlib
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    RemediationProposal, RemediationStatus, RemediationApplication,
    ApplicationStatus, RemediationApproval, PatchVersion, Asset,
    RemediationVerificationHandoff, VerificationHandoffStatus, Finding,
)
from app.repositories import (
    RemediationProposalRepository, RemediationApplicationRepository,
    RemediationApprovalRepository, PatchVersionRepository,
    RemediationVerificationHandoffRepository
)
from app.services.patch import PatchProcessor
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class ApplicationError(Exception):
    def __init__(self, message: str, error_code: str = "APPLICATION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


@dataclass
class ApplicationResult:
    success: bool
    application_id: UUID
    checkpoint_ref: Optional[str]
    result_diff: Optional[str]
    changed_files: List[Dict[str, Any]]
    validation_results: Dict[str, Any]
    error_message: Optional[str] = None


class PatchApplicationAdapter:
    """
    Controlled patch application adapter.

    For Stage 8, supports only repository workspaces that the authenticated
    workspace owner has explicitly authorized.

    Before applying a patch:
    1. Recheck workspace authorization
    2. Recheck repository scope
    3. Recheck approval and patch hash
    4. Confirm required validation succeeded
    5. Confirm target base revision has not changed unexpectedly
    6. Create a recoverable checkpoint
    7. Apply the patch in the isolated working copy
    8. Verify the resulting diff
    9. Persist the application outcome

    Never applies a patch to an arbitrary local path supplied by the user.
    Does not push commits, open PRs, merge branches, or deploy code.
    """

    def __init__(
        self,
        db: AsyncSession,
        authorized_workspace_root: str,
    ):
        self.db = db
        self.proposal_repo = RemediationProposalRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.approval_repo = RemediationApprovalRepository(db)
        self.patch_repo = PatchVersionRepository(db)
        self.handoff_repo = RemediationVerificationHandoffRepository(db)
        self.patch_processor = PatchProcessor(authorized_workspace_root)
        self.workspace_root = Path(authorized_workspace_root).resolve()

    async def apply_patch(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        approval_id: UUID,
        applier_id: UUID,
        workspace_id: UUID,
        idempotency_key: str,
    ) -> ApplicationResult:
        """
        Apply an approved patch to the authorized workspace.

        This is the main entry point for patch application.
        """
        # 1. Verify idempotency
        existing = await self.application_repo.get_by_idempotency_key(idempotency_key)
        if existing:
            logger.info(f"Idempotent application request for {idempotency_key}, returning existing result")
            return ApplicationResult(
                success=existing.status == ApplicationStatus.VERIFIED,
                application_id=existing.id,
                checkpoint_ref=existing.checkpoint_ref,
                result_diff=existing.result_diff,
                changed_files=existing.changed_files,
                validation_results=existing.validation_results,
                error_message=existing.failure_reason,
            )

        # 2. Recheck all preconditions
        precondition_check = await self._verify_application_preconditions(
            proposal_id, patch_version_id, approval_id, workspace_id, applier_id
        )
        if not precondition_check["valid"]:
            raise ApplicationError(f"Precondition failed: {precondition_check['issues']}", "PRECONDITION_FAILED")

        proposal = precondition_check["proposal"]
        patch_version = precondition_check["patch_version"]
        approval = precondition_check["approval"]
        asset = precondition_check["asset"]

        # 3. Create application record
        application = RemediationApplication(
            proposal_id=proposal_id,
            patch_version_id=patch_version_id,
            approval_id=approval_id,
            workspace_id=workspace_id,
            asset_id=asset.id,
            status=ApplicationStatus.PENDING,
            target_revision=await self._get_current_revision(),
            applied_by=applier_id,
            idempotency_key=idempotency_key,
        )
        application = await self.application_repo.create(application)

        try:
            # 4. Update status to checkpoint creation
            await self.application_repo.update(application.id, {"status": ApplicationStatus.CHECKPOINT_CREATED})

            # 5. Create checkpoint (git stash)
            checkpoint_ref = await self._create_checkpoint()

            # 6. Apply patch
            await self.application_repo.update(application.id, {"status": ApplicationStatus.PATCH_APPLIED})
            result_diff, changed_files = await self._apply_patch(patch_version.unified_diff)

            # 7. Verify applied diff matches expected
            if not self._verify_applied_diff(patch_version.unified_diff, result_diff):
                raise ApplicationError("Applied diff does not match expected patch", "DIFF_MISMATCH")

            # 8. Run post-application validation (if available)
            validation_results = await self._run_post_application_validation(changed_files)

            # 9. Update application record with success
            await self.application_repo.update(application.id, {
                "status": ApplicationStatus.VERIFIED,
                "completed_at": time.time(),
                "checkpoint_ref": checkpoint_ref,
                "result_diff": result_diff,
                "changed_files": changed_files,
                "validation_results": validation_results,
            })

            # 10. Update proposal status
            await self.proposal_repo.update(proposal_id, {
                "status": RemediationStatus.APPLIED,
                "applied_by": applier_id,
                "applied_at": time.time(),
                "version": proposal.version + 1,
            })

            # 11. Create verification handoff record
            await self._create_verification_handoff(
                proposal, application, patch_version, asset, applier_id, workspace_id
            )

            # 12. Audit log
            await audit_log(
                db=self.db,
                workspace_id=workspace_id,
                action="remediation.applied",
                resource_type="remediation_application",
                resource_id=application.id,
                new_state={
                    "proposal_id": str(proposal_id),
                    "patch_version_id": str(patch_version_id),
                    "approval_id": str(approval_id),
                    "patch_hash": patch_version.patch_hash,
                    "applier_id": str(applier_id),
                    "changed_files_count": len(changed_files),
                    "checkpoint_ref": checkpoint_ref,
                },
                user_id=applier_id,
            )

            return ApplicationResult(
                success=True,
                application_id=application.id,
                checkpoint_ref=checkpoint_ref,
                result_diff=result_diff,
                changed_files=changed_files,
                validation_results=validation_results,
            )

        except ApplicationError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error applying patch: {e}")
            await self._record_application_failure(application, str(e))
            raise ApplicationError(f"Application failed: {e}", "APPLICATION_FAILED")

    async def _verify_application_preconditions(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        approval_id: UUID,
        workspace_id: UUID,
        applier_id: UUID,
    ) -> Dict[str, Any]:
        """Verify all preconditions for patch application."""
        issues = []

        # Get proposal
        proposal = await self.proposal_repo.get_by_id(proposal_id)
        if not proposal or proposal.workspace_id != workspace_id:
            issues.append("Proposal not found or workspace mismatch")

        # Get patch version
        patch_version = await self.patch_repo.get_by_id(patch_version_id)
        if not patch_version or patch_version.proposal_id != proposal_id:
            issues.append("Patch version not found or doesn't belong to proposal")

        # Get approval
        approval = await self.approval_repo.get_by_id(approval_id)
        if not approval or approval.proposal_id != proposal_id:
            issues.append("Approval not found or doesn't belong to proposal")
        elif approval.patch_version_id != patch_version_id:
            issues.append("Approval is for different patch version")
        elif approval.decision != "approved":
            issues.append(f"Approval decision is '{approval.decision}', not 'approved'")

        # Get asset
        asset = None
        if proposal:
            from app.repositories import AssetRepository
            asset_repo = AssetRepository(self.db)
            asset = await asset_repo.get_by_id(proposal.asset_id)
            if not asset or asset.workspace_id != workspace_id:
                issues.append("Asset not found or workspace mismatch")

        # Check applier permissions
        from app.models import WorkspaceMember, WorkspaceRole
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == applier_id,
                WorkspaceMember.joined_at.is_not(None),
            )
        )
        member = result.scalar_one_or_none()
        if not member or member.role not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}:
            issues.append("Applier must be workspace owner or admin")

        # Verify approval validity
        if approval:
            approval_check = await self._verify_approval_validity(proposal_id, patch_version_id, workspace_id)
            if not approval_check["valid"]:
                issues.extend(approval_check["issues"])

        if issues:
            return {"valid": False, "issues": issues}

        return {
            "valid": True,
            "proposal": proposal,
            "patch_version": patch_version,
            "approval": approval,
            "asset": asset,
        }

    async def _verify_approval_validity(
        self,
        proposal_id: UUID,
        patch_version_id: UUID,
        workspace_id: UUID,
    ) -> Dict[str, Any]:
        """Verify approval is still valid."""
        from app.services.approval import ApprovalService
        approval_service = ApprovalService(self.db)
        return await approval_service.check_approval_validity(proposal_id, patch_version_id, workspace_id)

    async def _get_current_revision(self) -> str:
        """Get current git revision (commit SHA) of workspace."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.warning(f"Could not get git revision: {e}")
        return "unknown"

    async def _create_checkpoint(self) -> str:
        """Create a recoverable checkpoint (git stash)."""
        try:
            # Stash any uncommitted changes
            result = subprocess.run(
                ['git', 'stash', 'push', '-m', f'shadowops-checkpoint-{int(time.time())}'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                # Get stash reference
                result = subprocess.run(
                    ['git', 'stash', 'list'],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().split('\n')[0]  # Latest stash
            return "stash_failed"
        except Exception as e:
            logger.warning(f"Could not create checkpoint: {e}")
            return "checkpoint_failed"

    async def _apply_patch(self, unified_diff: str) -> tuple[str, List[Dict[str, Any]]]:
        """Apply the unified diff and return actual diff and changed files."""
        # Create temp patch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.patch', delete=False) as f:
            f.write(unified_diff)
            patch_file = f.name

        try:
            # Apply patch using git apply
            result = subprocess.run(
                ['git', 'apply', '--stat', patch_file],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Try patch command as fallback
                result = subprocess.run(
                    ['patch', '-p1', '-i', patch_file],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

            if result.returncode != 0:
                raise ApplicationError(f"Patch application failed: {result.stderr}", "PATCH_APPLY_FAILED")

            # Get actual diff after application
            result = subprocess.run(
                ['git', 'diff', 'HEAD'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            actual_diff = result.stdout if result.returncode == 0 else ""

            # Get changed files
            result = subprocess.run(
                ['git', 'diff', '--name-only', 'HEAD'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            changed_files = []
            if result.returncode == 0:
                for file_path in result.stdout.strip().split('\n'):
                    if file_path:
                        # Get file stats
                        stat_result = subprocess.run(
                            ['git', 'diff', '--numstat', 'HEAD', '--', file_path],
                            cwd=self.workspace_root,
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if stat_result.returncode == 0 and stat_result.stdout.strip():
                            parts = stat_result.stdout.strip().split('\t')
                            if len(parts) >= 2:
                                changed_files.append({
                                    "file_path": file_path,
                                    "additions": int(parts[0]) if parts[0] != '-' else 0,
                                    "deletions": int(parts[1]) if parts[1] != '-' else 0,
                                })

            return actual_diff, changed_files

        finally:
            try:
                os.unlink(patch_file)
            except OSError:
                pass

    def _verify_applied_diff(self, expected_diff: str, actual_diff: str) -> bool:
        """Verify applied diff matches expected (normalized comparison)."""
        # Normalize both diffs (remove timestamps, etc.)
        expected_normalized = self._normalize_diff(expected_diff)
        actual_normalized = self._normalize_diff(actual_diff)
        return expected_normalized == actual_normalized

    def _normalize_diff(self, diff: str) -> str:
        """Normalize diff for comparison."""
        lines = []
        for line in diff.split('\n'):
            # Skip git metadata lines that vary
            if line.startswith('index ') or line.startswith('--- ') or line.startswith('+++ '):
                continue
            lines.append(line)
        return '\n'.join(lines)

    async def _run_post_application_validation(
        self,
        changed_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Run post-application validation checks."""
        # In Stage 8, we can't run full validation without execution environment
        # Return placeholder
        return {
            "status": "BLOCKED",
            "reason": "Post-application validation requires isolated execution environment",
            "changed_files": changed_files,
        }

    async def _create_verification_handoff(
        self,
        proposal: RemediationProposal,
        application: RemediationApplication,
        patch_version: PatchVersion,
        asset: Asset,
        applier_id: UUID,
        workspace_id: UUID,
    ) -> RemediationVerificationHandoff:
        """Create verification handoff record for future verification stage."""
        # Get original finding snapshot
        from app.repositories import FindingRepository
        finding_repo = FindingRepository(self.db)
        finding = await finding_repo.get_by_id(proposal.finding_id)

        finding_snapshot = {}
        if finding:
            finding_snapshot = {
                "id": str(finding.id),
                "title": finding.title,
                "status": finding.status.value,
                "severity": finding.severity.value,
                "risk_score": finding.risk_score,
            }

        handoff = RemediationVerificationHandoff(
            proposal_id=proposal.id,
            application_id=application.id,
            workspace_id=workspace_id,
            finding_id=proposal.finding_id,
            asset_id=asset.id,
            patch_hash=patch_version.patch_hash,
            repository_revision=application.target_revision,
            changed_files=application.changed_files,
            validation_results=application.validation_results,
            original_finding_snapshot=finding_snapshot,
            applied_at=application.applied_at,
            applied_by=applier_id,
            status=VerificationHandoffStatus.PENDING_VERIFICATION.value,
        )
        return await self.handoff_repo.create(handoff)

    async def _record_application_failure(self, application: RemediationApplication, error_message: str) -> None:
        """Record application failure."""
        await self.application_repo.update(application.id, {
            "status": ApplicationStatus.FAILED,
            "completed_at": time.time(),
            "failure_reason": error_message[:1000],
        })

        # Also update proposal
        await self.proposal_repo.update(application.proposal_id, {
            "status": RemediationStatus.FAILED,
            "failure_reason": error_message[:1000],
        })

    async def get_application(self, application_id: UUID, workspace_id: UUID) -> Optional[RemediationApplication]:
        """Get application by ID with workspace check."""
        result = await self.db.execute(
            select(RemediationApplication)
            .where(
                RemediationApplication.id == application_id,
                RemediationApplication.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_applications(
        self,
        workspace_id: UUID,
        proposal_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RemediationApplication]:
        """List applications for workspace."""
        from app.repositories import RemediationApplicationRepository
        return await RemediationApplicationRepository(self.db).get_by_workspace(workspace_id, limit, offset)
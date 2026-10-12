import logging
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    RemediationRollback, RollbackStatus, RemediationApplication,
    ApplicationStatus, RemediationProposal, RemediationStatus, Asset,
)
from app.repositories import (
    RemediationRollbackRepository, RemediationApplicationRepository,
    RemediationProposalRepository
)
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class RollbackError(Exception):
    def __init__(self, message: str, error_code: str = "ROLLBACK_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


@dataclass
class RollbackResult:
    success: bool
    rollback_id: UUID
    verification_diff: Optional[str]
    error_message: Optional[str] = None


class RollbackService:
    """
    Safe rollback service for remediation applications.

    Rollback must:
    - Verify the affected repository and revision
    - Ensure no unexpected user changes would be overwritten
    - Restore only changes attributable to the approved patch
    - Record the actor and outcome
    - Fail safely if the repository has diverged

    Never blindly resets an entire repository or discards unrelated user work.
    If safe rollback cannot be guaranteed, stop and provide a recovery-required state.
    """

    def __init__(self, db: AsyncSession, authorized_workspace_root: str):
        self.db = db
        self.rollback_repo = RemediationRollbackRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.proposal_repo = RemediationProposalRepository(db)
        self.workspace_root = Path(authorized_workspace_root).resolve()

    async def rollback(
        self,
        application_id: UUID,
        requester_id: UUID,
        workspace_id: UUID,
        reason: str,
    ) -> RollbackResult:
        """
        Perform a safe rollback of an applied patch.

        This uses the checkpoint created during application to restore
        only the changes from the approved patch.
        """
        # 1. Verify application exists and is in correct state
        application = await self._verify_application_for_rollback(application_id, workspace_id)
        if not application:
            raise RollbackError("Application not found or access denied", "APPLICATION_NOT_FOUND")

        # 2. Verify requester has permission
        await self._verify_rollback_permission(requester_id, workspace_id)

        # 3. Verify application was successful
        if application.status != ApplicationStatus.VERIFIED:
            raise RollbackError(
                f"Can only rollback verified applications (current: {application.status.value})",
                "INVALID_APPLICATION_STATE"
            )

        # 4. Check checkpoint exists
        if not application.checkpoint_ref or application.checkpoint_ref in ["stash_failed", "checkpoint_failed"]:
            raise RollbackError("No valid checkpoint available for rollback", "CHECKPOINT_MISSING")

        # 5. Create rollback record
        rollback = RemediationRollback(
            proposal_id=application.proposal_id,
            application_id=application_id,
            workspace_id=workspace_id,
            asset_id=application.asset_id,
            status=RollbackStatus.IN_PROGRESS,
            requested_by=requester_id,
            reason=reason,
            checkpoint_ref=application.checkpoint_ref,
        )
        rollback = await self.rollback_repo.create(rollback)

        try:
            # 6. Check for repository divergence
            divergence_check = await self._check_repository_divergence(application)
            if divergence_check["diverged"]:
                await self._record_rollback_failure(rollback, divergence_check["reason"])
                raise RollbackError(
                    f"Repository has diverged, cannot safely rollback: {divergence_check['reason']}",
                    "REPOSITORY_DIVERGED"
                )

            # 7. Perform rollback using checkpoint
            verification_diff = await self._perform_rollback(application.checkpoint_ref)

            # 8. Update rollback record
            await self.rollback_repo.update(rollback.id, {
                "status": RollbackStatus.COMPLETED,
                "completed_at": time.time(),
                "verification_diff": verification_diff,
            })

            # 9. Update application status
            await self.application_repo.update(application_id, {
                "status": ApplicationStatus.ROLLED_BACK,
            })

            # 10. Update proposal status
            await self.proposal_repo.update(application.proposal_id, {
                "status": RemediationStatus.ROLLED_BACK,
            })

            # 11. Audit log
            await audit_log(
                db=self.db,
                workspace_id=workspace_id,
                action="remediation.rolled_back",
                resource_type="remediation_rollback",
                resource_id=rollback.id,
                new_state={
                    "application_id": str(application_id),
                    "proposal_id": str(application.proposal_id),
                    "requester_id": str(requester_id),
                    "reason": reason,
                    "checkpoint_ref": application.checkpoint_ref,
                },
                user_id=requester_id,
            )

            return RollbackResult(
                success=True,
                rollback_id=rollback.id,
                verification_diff=verification_diff,
            )

        except RollbackError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during rollback: {e}")
            await self._record_rollback_failure(rollback, str(e))
            raise RollbackError(f"Rollback failed: {e}", "ROLLBACK_FAILED")

    async def _verify_application_for_rollback(
        self,
        application_id: UUID,
        workspace_id: UUID,
    ) -> Optional[RemediationApplication]:
        """Verify application exists and belongs to workspace."""
        application = await self.application_repo.get_by_id(application_id)
        if not application or application.workspace_id != workspace_id:
            return None
        return application

    async def _verify_rollback_permission(self, user_id: UUID, workspace_id: UUID) -> None:
        """Verify user has admin/owner role in workspace."""
        from app.models import WorkspaceMember, WorkspaceRole
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.joined_at.is_not(None),
            )
        )
        member = result.scalar_one_or_none()

        if not member:
            raise RollbackError("User is not a member of this workspace", "NOT_WORKSPACE_MEMBER")

        if member.role not in {WorkspaceRole.OWNER, WorkspaceRole.ADMIN}:
            raise RollbackError(
                f"Role '{member.role}' cannot perform rollbacks. Requires owner or admin.",
                "INSUFFICIENT_PERMISSIONS"
            )

    async def _check_repository_divergence(self, application: RemediationApplication) -> Dict[str, Any]:
        """
        Check if repository has diverged in a way that makes rollback unsafe.

        We check:
        - Has the target revision changed?
        - Are there uncommitted changes that would be lost?
        - Has the stash been modified?
        """
        try:
            # Check if we're still at the same revision
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return {"diverged": True, "reason": "Cannot determine current revision"}

            current_revision = result.stdout.strip()
            if current_revision != application.target_revision:
                return {
                    "diverged": True,
                    "reason": f"Revision changed from {application.target_revision} to {current_revision}"
                }

            # Check for uncommitted changes
            result = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and result.stdout.strip():
                return {
                    "diverged": True,
                    "reason": f"Uncommitted changes present: {result.stdout.strip()[:200]}"
                }

            # Check stash exists and is accessible
            result = subprocess.run(
                ['git', 'stash', 'list'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0 or not result.stdout.strip():
                return {"diverged": True, "reason": "Stash list empty or inaccessible"}

            # Check if our checkpoint stash is still there
            if application.checkpoint_ref not in result.stdout:
                return {"diverged": True, "reason": "Checkpoint stash not found in stash list"}

            return {"diverged": False, "reason": "No divergence detected"}

        except Exception as e:
            return {"diverged": True, "reason": f"Error checking divergence: {e}"}

    async def _perform_rollback(self, checkpoint_ref: str) -> Optional[str]:
        """
        Perform the actual rollback by applying the stash.

        Returns the diff of what was restored.
        """
        try:
            # First, get the diff of what the stash will restore
            result = subprocess.run(
                ['git', 'stash', 'show', '-p', checkpoint_ref],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )
            stash_diff = result.stdout if result.returncode == 0 else ""

            # Apply the stash
            result = subprocess.run(
                ['git', 'stash', 'pop', checkpoint_ref],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                # Try to apply without popping (in case of conflicts)
                result = subprocess.run(
                    ['git', 'stash', 'apply', checkpoint_ref],
                    cwd=self.workspace_root,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode != 0:
                    raise RollbackError(f"Failed to apply stash: {result.stderr}", "STASH_APPLY_FAILED")

            # Get verification diff (what changed after rollback)
            result = subprocess.run(
                ['git', 'diff', 'HEAD@{1}'],
                cwd=self.workspace_root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            verification_diff = result.stdout if result.returncode == 0 else stash_diff

            return verification_diff

        except Exception as e:
            raise RollbackError(f"Rollback execution failed: {e}", "ROLLBACK_EXECUTION_FAILED")

    async def _record_rollback_failure(self, rollback: RemediationRollback, error_message: str) -> None:
        """Record rollback failure."""
        await self.rollback_repo.update(rollback.id, {
            "status": RollbackStatus.FAILED,
            "completed_at": time.time(),
            "failure_reason": error_message[:1000],
        })

    async def get_rollback(self, rollback_id: UUID, workspace_id: UUID) -> Optional[RemediationRollback]:
        """Get rollback by ID with workspace check."""
        result = await self.db.execute(
            select(RemediationRollback)
            .where(
                RemediationRollback.id == rollback_id,
                RemediationRollback.workspace_id == workspace_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_rollbacks(
        self,
        workspace_id: UUID,
        proposal_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RemediationRollback]:
        """List rollbacks for workspace."""
        if proposal_id:
            return await self.rollback_repo.get_by_proposal(proposal_id)

        query = select(RemediationRollback).where(
            RemediationRollback.workspace_id == workspace_id
        ).order_by(RemediationRollback.started_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_rollback_status(self, application_id: UUID, workspace_id: UUID) -> Dict[str, Any]:
        """Get rollback availability and status for an application."""
        application = await self.application_repo.get_by_id(application_id)
        if not application or application.workspace_id != workspace_id:
            return {"available": False, "reason": "Application not found"}

        if application.status != ApplicationStatus.VERIFIED:
            return {
                "available": False,
                "reason": f"Application not in verified state (current: {application.status.value})",
            }

        if not application.checkpoint_ref or application.checkpoint_ref in ["stash_failed", "checkpoint_failed"]:
            return {
                "available": False,
                "reason": "No valid checkpoint available",
            }

        # Check divergence
        divergence_check = await self._check_repository_divergence(application)
        if divergence_check["diverged"]:
            return {
                "available": False,
                "reason": divergence_check["reason"],
                "requires_manual_recovery": True,
            }

        return {
            "available": True,
            "checkpoint_ref": application.checkpoint_ref,
            "target_revision": application.target_revision,
        }
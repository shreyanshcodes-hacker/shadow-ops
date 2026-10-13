import hashlib
import json
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.repositories import (
    FindingRepository,
    FindingEvidenceRepository,
    ScanRepository,
    AssetRepository,
    ScanTargetRepository,
    RemediationProposalRepository,
    RemediationApplicationRepository,
    RemediationVerificationHandoffRepository,
)
from app.models import (
    Finding,
    Scan,
    Asset,
    ScanTarget,
    RemediationProposal,
    RemediationApplication,
    RemediationVerificationHandoff,
    VerificationJob,
    VerificationStatus,
    VerificationOutcome,
    VerificationHandoffStatus,
    Profile,
    WorkspaceMember,
    WorkspaceRole,
    VerificationCheck,
    VerificationReview,
    EvidenceComparison,
    VerificationPolicy,
    VerificationBaseline,
    CheckStatus,
    CheckType,
    ComparisonCategory,
    FindingStatus,
)
from app.services.baseline import BaselineCaptureService
from app.services.comparison import EvidenceComparisonService
from app.services.regression import RegressionAnalysisService
from app.services.policy import VerificationPolicyEngine
from app.security.audit import audit_log


class VerificationService:
    """Main service for orchestrating verification jobs."""

    VERIFICATION_ENGINE_VERSION = "verification-v1"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.scan_repo = ScanRepository(db)
        self.asset_repo = AssetRepository(db)
        self.scan_target_repo = ScanTargetRepository(db)
        self.proposal_repo = RemediationProposalRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.handoff_repo = RemediationVerificationHandoffRepository(db)
        self.baseline_service = BaselineCaptureService(db)
        self.comparison_service = EvidenceComparisonService(db)
        self.regression_service = RegressionAnalysisService(db)
        self.policy_engine = VerificationPolicyEngine(db)

    async def _verify_workspace_access(
        self,
        user_id: UUID,
        workspace_id: UUID,
        required_roles: List[WorkspaceRole] = None,
    ) -> WorkspaceMember:
        """Verify user has access to workspace."""
        if required_roles is None:
            required_roles = [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER]

        result = await self.db.execute(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                    WorkspaceMember.role.in_(required_roles),
                )
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            raise PermissionError("Insufficient permissions for workspace")
        return member

    async def create_verification_job(
        self,
        user_id: UUID,
        remediation_application_id: UUID,
        idempotency_key: str,
    ) -> VerificationJob:
        """Create a new verification job."""
        application = await self.application_repo.get_by_id(remediation_application_id)
        if not application:
            raise ValueError(f"Application {remediation_application_id} not found")

        await self._verify_workspace_access(user_id, application.workspace_id)

        existing = await self.db.execute(
            select(VerificationJob).where(
                VerificationJob.idempotency_key == idempotency_key
            )
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return existing_job

        proposal = await self.proposal_repo.get_by_id(application.proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {application.proposal_id} not found")

        finding = await self.finding_repo.get_by_id(proposal.finding_id)
        if not finding:
            raise ValueError(f"Finding {proposal.finding_id} not found")

        patch_version = proposal.patch_versions[-1] if proposal.patch_versions else None
        if not patch_version:
            raise ValueError("No patch version found for proposal")

        job = VerificationJob(
            id=uuid4(),
            workspace_id=application.workspace_id,
            asset_id=application.asset_id,
            finding_id=proposal.finding_id,
            remediation_proposal_id=proposal.id,
            remediation_application_id=application.id,
            patch_hash=patch_version.patch_hash,
            source_revision=application.target_revision,
            target_revision=application.target_revision,
            verification_engine_version=self.VERIFICATION_ENGINE_VERSION,
            policy_version="verification-policy-v1",
            status=VerificationStatus.QUEUED,
            requested_by=user_id,
            idempotency_key=idempotency_key,
        )

        self.db.add(job)
        await self.db.flush()

        await self.policy_engine.create_default_policy(user_id)

        await audit_log(
            self.db,
            workspace_id=application.workspace_id,
            user_id=user_id,
            action="verification.job_created",
            resource_type="verification_job",
            resource_id=job.id,
            new_state={
                "application_id": str(application.id),
                "proposal_id": str(proposal.id),
                "finding_id": str(proposal.finding_id),
                "patch_hash": patch_version.patch_hash[:16],
            },
        )

        return job

    async def get_verification_job(self, job_id: UUID) -> Optional[VerificationJob]:
        """Get verification job by ID."""
        result = await self.db.execute(
            select(VerificationJob).where(VerificationJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def list_verification_jobs(
        self,
        workspace_id: UUID,
        user_id: UUID,
        status: Optional[VerificationStatus] = None,
        finding_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[VerificationJob]:
        """List verification jobs for a workspace."""
        await self._verify_workspace_access(user_id, workspace_id)

        query = select(VerificationJob).where(VerificationJob.workspace_id == workspace_id)

        if status:
            query = query.where(VerificationJob.status == status)
        if finding_id:
            query = query.where(VerificationJob.finding_id == finding_id)

        query = query.order_by(VerificationJob.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def start_verification(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> VerificationJob:
        """Start the verification process for a job."""
        job = await self.get_verification_job(job_id)
        if not job:
            raise ValueError(f"Verification job {job_id} not found")

        await self._verify_workspace_access(user_id, job.workspace_id)

        if job.status != VerificationStatus.QUEUED:
            raise ValueError(f"Job is not in QUEUED status: {job.status}")

        job.status = VerificationStatus.RUNNING
        job.started_at = datetime.utcnow()

        await audit_log(
            self.db,
            workspace_id=job.workspace_id,
            user_id=user_id,
            action="verification.job_started",
            resource_type="verification_job",
            resource_id=job.id,
            details={"status": job.status.value},
        )

        await self.db.flush()

        try:
            await self._execute_verification(job, user_id)
        except Exception as e:
            job.status = VerificationStatus.FAILED
            job.failed_at = datetime.utcnow()
            job.error_message = str(e)
            await audit_log(
                self.db,
                workspace_id=job.workspace_id,
                user_id=user_id,
                action="verification.job_failed",
                resource_type="verification_job",
                resource_id=job.id,
                details={"error": str(e)},
            )
            await self.db.flush()
            raise

        return job

    async def _execute_verification(
        self,
        job: VerificationJob,
        user_id: UUID,
    ):
        """Execute the full verification workflow."""
        application = await self.application_repo.get_by_id(job.remediation_application_id)
        proposal = await self.proposal_repo.get_by_id(job.remediation_proposal_id)
        asset = await self.asset_repo.get_by_id(job.asset_id)
        scan_target = None
        if asset:
            scan_targets = await self.scan_target_repo.get_by_asset(asset.id)
            if scan_targets:
                scan_target = scan_targets[0]

        working_dir = asset.connection_config.get("local_path", "/workspace") if asset else "/workspace"

        await self._capture_baseline(job, user_id)

        job.status = VerificationStatus.BASELINE_CHECK
        await self.db.flush()

        await self._run_scanner_execution(job, asset, scan_target, working_dir)

        job.status = VerificationStatus.RESCANNING
        await self.db.flush()

        post_patch_findings = await self._run_post_patch_scan(job, asset, scan_target, working_dir)

        job.status = VerificationStatus.COMPARING_EVIDENCE
        await self.db.flush()

        await self._run_evidence_comparison(job, post_patch_findings)

        await self._run_original_vulnerability_check(job, post_patch_findings)

        job.status = VerificationStatus.REGRESSION_CHECK
        await self.db.flush()

        await self._run_regression_checks(job, asset, scan_target, working_dir, proposal)

        outcome = await self.policy_engine.evaluate_job(job)

        job.overall_outcome = outcome
        job.completed_at = datetime.utcnow()

        if outcome == VerificationOutcome.VERIFIED_CANDIDATE:
            job.status = VerificationStatus.PASSED_PENDING_REVIEW
        elif outcome == VerificationOutcome.FAILED:
            job.status = VerificationStatus.FAILED
            job.failed_at = datetime.utcnow()
        elif outcome == VerificationOutcome.BLOCKED:
            job.status = VerificationStatus.BLOCKED
        else:
            job.status = VerificationStatus.INCONCLUSIVE

        await audit_log(
            self.db,
            workspace_id=job.workspace_id,
            user_id=user_id,
            action="verification.job_completed",
            resource_type="verification_job",
            resource_id=job.id,
            details={
                "outcome": outcome.value,
                "status": job.status.value,
            },
        )

        await self.db.flush()

    async def _capture_baseline(self, job: VerificationJob, user_id: UUID):
        """Capture baseline from handoff or pre-patch scan."""
        handoff = await self.handoff_repo.get_by_proposal(job.remediation_proposal_id)
        if handoff and handoff.status == VerificationHandoffStatus.VERIFICATION_REQUESTED:
            await self.baseline_service.capture_baseline_from_handoff(job, handoff, user_id)
        else:
            proposal = await self.proposal_repo.get_by_id(job.remediation_proposal_id)
            if proposal and proposal.source_scan_id:
                await self.baseline_service.capture_baseline_from_scan(
                    job, proposal.source_scan_id, user_id
                )

    async def _run_scanner_execution(
        self,
        job: VerificationJob,
        asset: Optional[Asset],
        scan_target: Optional[ScanTarget],
        working_dir: str,
    ):
        """Run scanner execution check."""
        await self.regression_service.run_scanner_execution_check(job, asset, scan_target, working_dir)

    async def _run_post_patch_scan(
        self,
        job: VerificationJob,
        asset: Optional[Asset],
        scan_target: Optional[ScanTarget],
        working_dir: str,
    ) -> List[Any]:
        """Run post-patch scan and return findings."""
        from app.scanners.semgrep import SemgrepRunner
        runner = SemgrepRunner()

        try:
            result = await runner.run_scan(
                target_path=working_dir,
                config="auto",
                timeout=300,
            )
            if result.success:
                return result.findings
        except Exception:
            pass

        return []

    async def _run_evidence_comparison(
        self,
        job: VerificationJob,
        post_patch_findings: List[Any],
    ):
        """Run evidence comparison."""
        baseline = await self.baseline_service.get_baseline(job.id)
        if baseline:
            await self.comparison_service.compare_evidence(job, baseline, post_patch_findings)

    async def _run_original_vulnerability_check(
        self,
        job: VerificationJob,
        post_patch_findings: List[Any],
    ):
        """Run original vulnerability check."""
        baseline = await self.baseline_service.get_baseline(job.id)
        if baseline:
            await self.regression_service.run_original_vulnerability_check(job, baseline, post_patch_findings)

    async def _run_regression_checks(
        self,
        job: VerificationJob,
        asset: Optional[Asset],
        scan_target: Optional[ScanTarget],
        working_dir: str,
        proposal: RemediationProposal,
    ):
        """Run regression analysis checks."""
        suggested_tests = proposal.suggested_tests or []
        if suggested_tests:
            await self.regression_service.run_test_execution_check(
                job, asset, scan_target, working_dir, suggested_tests
            )

        await self.regression_service.run_regression_analysis(job)

    async def submit_review(
        self,
        job_id: UUID,
        user_id: UUID,
        decision: str,
        justification: str,
        notes: Optional[str] = None,
    ) -> VerificationJob:
        """Submit human review decision."""
        job = await self.get_verification_job(job_id)
        if not job:
            raise ValueError(f"Verification job {job_id} not found")

        await self._verify_workspace_access(
            user_id,
            job.workspace_id,
            [WorkspaceRole.OWNER, WorkspaceRole.ADMIN],
        )

        if job.status != VerificationStatus.PASSED_PENDING_REVIEW:
            raise ValueError(f"Job is not pending review: {job.status}")

        if job.overall_outcome != VerificationOutcome.VERIFIED_CANDIDATE:
            raise ValueError(f"Job outcome is not VERIFIED_CANDIDATE: {job.overall_outcome}")

        from app.models import VerificationReview, ReviewDecision

        review = VerificationReview(
            verification_job_id=job.id,
            workspace_id=job.workspace_id,
            reviewed_by=user_id,
            decision=ReviewDecision(decision),
            justification=justification,
            notes=notes,
            policy_version=job.policy_version,
            baseline_snapshot={},
            comparison_snapshot={},
            check_results_snapshot={},
        )
        self.db.add(review)

        if decision == "accept":
            job.status = VerificationStatus.VERIFIED
            finding = await self.finding_repo.get_by_id(job.finding_id)
            if finding:
                finding.status = FindingStatus.FIXED
                finding.fixed_at = datetime.utcnow()
        elif decision == "reject":
            job.status = VerificationStatus.FAILED
        elif decision == "rerun_requested":
            job.status = VerificationStatus.QUEUED
            job.overall_outcome = None
            job.completed_at = None

        await audit_log(
            self.db,
            workspace_id=job.workspace_id,
            user_id=user_id,
            action="verification.review_submitted",
            resource_type="verification_job",
            resource_id=job.id,
            new_state={
                "decision": decision,
                "new_status": job.status.value,
            },
        )

        await self.db.flush()
        return job

    async def rerun_verification(
        self,
        job_id: UUID,
        user_id: UUID,
        idempotency_key: str,
    ) -> VerificationJob:
        """Rerun a verification job."""
        job = await self.get_verification_job(job_id)
        if not job:
            raise NotFoundError(f"Verification job {job_id} not found")

        await self._verify_workspace_access(user_id, job.workspace_id)

        existing = await self.db.execute(
            select(VerificationJob).where(
                VerificationJob.idempotency_key == idempotency_key
            )
        )
        existing_job = existing.scalar_one_or_none()
        if existing_job:
            return existing_job

        await self.db.execute(
            select(VerificationCheck).where(
                VerificationCheck.verification_job_id == job.id
            ).delete()
        )
        await self.db.execute(
            select(EvidenceComparison).where(
                EvidenceComparison.verification_job_id == job.id
            ).delete()
        )
        await self.db.execute(
            select(VerificationBaseline).where(
                VerificationBaseline.verification_job_id == job.id
            ).delete()
        )

        job.status = VerificationStatus.QUEUED
        job.overall_outcome = None
        job.started_at = None
        job.completed_at = None
        job.failed_at = None
        job.canceled_at = None
        job.error_code = None
        job.error_message = None

        await audit_log(
            self.db,
            workspace_id=job.workspace_id,
            user_id=user_id,
            action="verification.job_rerun",
            resource_type="verification_job",
            resource_id=job.id,
            details={},
        )

        await self.db.flush()
        return await self.start_verification(job.id, user_id)

    async def cancel_verification(
        self,
        job_id: UUID,
        user_id: UUID,
    ) -> VerificationJob:
        """Cancel a running verification job."""
        job = await self.get_verification_job(job_id)
        if not job:
            raise ValueError(f"Verification job {job_id} not found")

        await self._verify_workspace_access(user_id, job.workspace_id)

        if job.status not in (VerificationStatus.QUEUED, VerificationStatus.RUNNING):
            raise ValueError(f"Cannot cancel job in status: {job.status}")

        job.status = VerificationStatus.CANCELED
        job.canceled_at = datetime.utcnow()

        await audit_log(
            self.db,
            workspace_id=job.workspace_id,
            user_id=user_id,
            action="verification.job_canceled",
            resource_type="verification_job",
            resource_id=job.id,
            details={},
        )

        await self.db.flush()
        return job
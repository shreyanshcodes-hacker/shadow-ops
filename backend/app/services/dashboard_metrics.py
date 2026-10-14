from typing import Dict, List, Optional, Any
from uuid import UUID
from datetime import datetime, timedelta
from collections import defaultdict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case
from sqlalchemy.orm import selectinload

from app.repositories import (
    AssetRepository,
    AssetAuthorizationRepository,
    ScanRepository,
    FindingRepository,
    AttackPathRepository,
    RiskSnapshotRepository,
    RemediationProposalRepository,
    RemediationApprovalRepository,
    RemediationApplicationRepository,
    VerificationJobRepository,
    VerificationCheckRepository,
    VerificationReviewRepository,
)
from app.models import (
    Asset,
    AssetAuthorization,
    AuthorizationStatus,
    Scan,
    ScanStatus,
    Finding,
    FindingSeverity,
    FindingStatus,
    FindingSource,
    AttackPath,
    AttackPathStatus,
    RiskSnapshot,
    RemediationProposal,
    RemediationStatus,
    RemediationApproval,
    RemediationApplication,
    ApplicationStatus,
    VerificationJob,
    VerificationStatus,
    VerificationOutcome,
    VerificationCheck,
    CheckType,
    VerificationReview,
    ReviewDecision,
)
from app.security.audit import audit_log


class DashboardMetricsService:
    """Service for computing workspace-scoped dashboard metrics."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.asset_repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)
        self.scan_repo = ScanRepository(db)
        self.finding_repo = FindingRepository(db)
        self.attack_path_repo = AttackPathRepository(db)
        self.risk_snapshot_repo = RiskSnapshotRepository(db)
        self.proposal_repo = RemediationProposalRepository(db)
        self.approval_repo = RemediationApprovalRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.verification_job_repo = VerificationJobRepository(db)
        self.verification_check_repo = VerificationCheckRepository(db)
        self.verification_review_repo = VerificationReviewRepository(db)

    async def get_workspace_metrics(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Dict[str, Any]:
        """Get all dashboard metrics for a workspace."""
        # Verify workspace access
        from app.services import WorkspaceService
        ws_service = WorkspaceService(self.db)
        member = await ws_service.get_member(workspace_id, user_id)
        if not member:
            from app.core.exceptions import AuthorizationError
            raise AuthorizationError("Insufficient permissions for workspace")

        metrics = {}

        # Asset metrics
        metrics["assets"] = await self._get_asset_metrics(workspace_id)

        # Scan metrics
        metrics["scans"] = await self._get_scan_metrics(workspace_id)

        # Finding metrics
        metrics["findings"] = await self._get_finding_metrics(workspace_id)

        # Risk/Attack Path metrics
        metrics["risk"] = await self._get_risk_metrics(workspace_id)

        # Remediation metrics
        metrics["remediation"] = await self._get_remediation_metrics(workspace_id)

        # Verification metrics
        metrics["verification"] = await self._get_verification_metrics(workspace_id)

        # Activity timestamps
        metrics["activity"] = await self._get_activity_timestamps(workspace_id)

        # Metadata
        metrics["metadata"] = {
            "workspace_id": str(workspace_id),
            "generated_at": datetime.utcnow().isoformat(),
            "data_cutoff": datetime.utcnow().isoformat(),
        }

        return metrics

    async def _get_asset_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get asset-related metrics."""
        assets_result = await self.db.execute(
            select(Asset).where(
                and_(
                    Asset.workspace_id == workspace_id,
                    Asset.deleted_at.is_(None),
                )
            )
        )
        assets = list(assets_result.scalars().all())

        # Authorization check
        auth_result = await self.db.execute(
            select(AssetAuthorization).where(
                and_(
                    AssetAuthorization.workspace_id == workspace_id,
                    AssetAuthorization.status == AuthorizationStatus.VERIFIED,
                )
            )
        )
        authorizations = list(auth_result.scalars().all())
        authorized_asset_ids = {a.asset_id for a in authorizations if a.is_valid}

        by_criticality = defaultdict(int)
        by_type = defaultdict(int)
        by_status = defaultdict(int)

        for asset in assets:
            by_criticality[asset.criticality.value] += 1
            by_type[asset.type.value] += 1
            by_status[asset.status.value] += 1

        return {
            "total_assets": len(assets),
            "assets_with_authorization": len(authorized_asset_ids),
            "assets_by_criticality": dict(by_criticality),
            "assets_by_type": dict(by_type),
            "assets_by_status": dict(by_status),
        }

    async def _get_scan_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get scan-related metrics."""
        scans_result = await self.db.execute(
            select(Scan).where(Scan.workspace_id == workspace_id)
        )
        scans = list(scans_result.scalars().all())

        completed_scans = [s for s in scans if s.status == ScanStatus.COMPLETED]
        failed_scans = [s for s in scans if s.status == ScanStatus.FAILED]
        running_scans = [s for s in scans if s.status == ScanStatus.RUNNING]

        latest_completed = None
        if completed_scans:
            latest = max(completed_scans, key=lambda s: s.completed_at or datetime.min)
            latest_completed = latest.completed_at

        return {
            "total_scans": len(scans),
            "scans_completed": len(completed_scans),
            "scans_failed": len(failed_scans),
            "scans_running": len(running_scans),
            "latest_completed_scan_at": latest_completed.isoformat() if latest_completed else None,
        }

    async def _get_finding_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get finding-related metrics."""
        findings_result = await self.db.execute(
            select(Finding).where(Finding.workspace_id == workspace_id)
        )
        findings = list(findings_result.scalars().all())

        open_findings = [f for f in findings if f.status == FindingStatus.OPEN]
        by_severity = defaultdict(int)
        by_status = defaultdict(int)
        by_source = defaultdict(int)

        for f in findings:
            by_status[f.status.value] += 1
            by_source[f.source.value] += 1
            if f.status == FindingStatus.OPEN:
                by_severity[f.severity.value] += 1

        # Ensure all severity levels present
        for sev in FindingSeverity:
            if sev.value not in by_severity:
                by_severity[sev.value] = 0

        return {
            "total_findings": len(findings),
            "open_findings_by_severity": dict(by_severity),
            "findings_by_status": dict(by_status),
            "findings_by_source": dict(by_source),
        }

    async def _get_risk_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get risk and attack path metrics."""
        # Latest risk snapshots per attack path
        paths_result = await self.db.execute(
            select(AttackPath).where(AttackPath.workspace_id == workspace_id)
        )
        paths = list(paths_result.scalars().all())

        by_path_status = defaultdict(int)
        by_severity = defaultdict(int)
        risk_scores = []

        for path in paths:
            by_path_status[path.status.value] += 1
            if path.severity:
                by_severity[path.severity] += 1
            if path.risk_score is not None:
                risk_scores.append(path.risk_score)

        # Get latest risk model version
        risk_model_version = None
        if paths:
            risk_model_version = paths[0].risk_model_version

        # Calculate current overall risk score (max of active paths)
        active_paths = [p for p in paths if p.status in (AttackPathStatus.ACTIVE, AttackPathStatus.DRAFT)]
        current_risk_score = max([p.risk_score for p in active_paths if p.risk_score], default=None)

        return {
            "current_risk_score": current_risk_score,
            "risk_model_version": risk_model_version,
            "attack_paths_by_status": dict(by_path_status),
            "attack_paths_by_severity": dict(by_severity),
            "total_attack_paths": len(paths),
        }

    async def _get_remediation_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get remediation metrics."""
        proposals_result = await self.db.execute(
            select(RemediationProposal).where(RemediationProposal.workspace_id == workspace_id)
        )
        proposals = list(proposals_result.scalars().all())

        by_status = defaultdict(int)
        for p in proposals:
            by_status[p.status.value] += 1

        # Count approvals
        approvals_result = await self.db.execute(
            select(RemediationApproval).where(RemediationApproval.workspace_id == workspace_id)
        )
        approvals = list(approvals_result.scalars().all())
        approved_count = sum(1 for a in approvals if a.decision == "approved")
        rejected_count = sum(1 for a in approvals if a.decision == "rejected")

        # Count applications
        apps_result = await self.db.execute(
            select(RemediationApplication).where(RemediationApplication.workspace_id == workspace_id)
        )
        applications = list(apps_result.scalars().all())
        applied_count = sum(1 for a in applications if a.status == ApplicationStatus.PATCH_APPLIED)

        return {
            "remediation_proposals_by_status": dict(by_status),
            "remediation_approved": approved_count,
            "remediation_applied": applied_count,
            "remediation_rejected": rejected_count,
            "total_proposals": len(proposals),
        }

    async def _get_verification_metrics(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get verification metrics (Stage 9)."""
        jobs_result = await self.db.execute(
            select(VerificationJob).where(VerificationJob.workspace_id == workspace_id)
        )
        jobs = list(jobs_result.scalars().all())

        by_status = defaultdict(int)
        by_outcome = defaultdict(int)
        regression_failures = 0
        latest_verification = None

        for job in jobs:
            by_status[job.status.value] += 1
            if job.overall_outcome:
                by_outcome[job.overall_outcome.value] += 1
            if job.completed_at and (not latest_verification or job.completed_at > latest_verification):
                latest_verification = job.completed_at

        # Check regression failures
        checks_result = await self.db.execute(
            select(VerificationCheck)
            .join(VerificationJob, VerificationCheck.verification_job_id == VerificationJob.id)
            .where(
                and_(
                    VerificationJob.workspace_id == workspace_id,
                    VerificationCheck.check_type.in_([
                        CheckType.REGRESSION_ANALYSIS,
                        CheckType.TEST_EXECUTION,
                    ]),
                    VerificationCheck.status == CheckStatus.FAILED,
                )
            )
        )
        regression_failures = len(list(checks_result.scalars().all()))

        return {
            "verification_jobs_by_status": dict(by_status),
            "verification_outcomes": dict(by_outcome),
            "regression_failures": regression_failures,
            "latest_verification_at": latest_verification.isoformat() if latest_verification else None,
        }

    async def _get_activity_timestamps(self, workspace_id: UUID) -> Dict[str, Any]:
        """Get latest activity timestamps."""
        timestamps = {}

        # Latest scan
        scan_result = await self.db.execute(
            select(Scan.completed_at)
            .where(
                and_(
                    Scan.workspace_id == workspace_id,
                    Scan.status == ScanStatus.COMPLETED,
                )
            )
            .order_by(Scan.completed_at.desc())
            .limit(1)
        )
        latest_scan = scan_result.scalar_one_or_none()
        if latest_scan:
            timestamps["latest_scan_at"] = latest_scan.isoformat()

        # Latest finding
        finding_result = await self.db.execute(
            select(Finding.last_seen_at)
            .where(Finding.workspace_id == workspace_id)
            .order_by(Finding.last_seen_at.desc())
            .limit(1)
        )
        latest_finding = finding_result.scalar_one_or_none()
        if latest_finding:
            timestamps["latest_finding_at"] = latest_finding.isoformat()

        # Latest remediation
        rem_result = await self.db.execute(
            select(RemediationProposal.created_at)
            .where(RemediationProposal.workspace_id == workspace_id)
            .order_by(RemediationProposal.created_at.desc())
            .limit(1)
        )
        latest_rem = rem_result.scalar_one_or_none()
        if latest_rem:
            timestamps["latest_remediation_at"] = latest_rem.isoformat()

        return timestamps
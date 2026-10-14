from typing import Dict, List, Optional, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, case, text
from sqlalchemy.dialects.postgresql import DATE

from app.repositories import (
    ScanRepository,
    FindingRepository,
    RiskSnapshotRepository,
    RemediationProposalRepository,
    RemediationApprovalRepository,
    RemediationApplicationRepository,
    VerificationJobRepository,
    VerificationCheckRepository,
    VerificationReviewRepository,
)
from app.models import (
    Scan,
    ScanStatus,
    Finding,
    FindingSeverity,
    FindingStatus,
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
    CheckStatus,
    VerificationReview,
    ReviewDecision,
)
from app.security.audit import audit_log


@dataclass
class TrendDataPoint:
    timestamp: datetime
    value: float
    label: Optional[str] = None


@dataclass
class TrendSeries:
    metric_name: str
    metric_label: str
    unit: str
    data_points: List[TrendDataPoint]
    data_source: str
    aggregation_method: str
    time_window: str
    limitations: Optional[str] = None


class TrendService:
    """Service for computing time-series trends from historical data."""

    MIN_DATA_POINTS = 2

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scan_repo = ScanRepository(db)
        self.finding_repo = FindingRepository(db)
        self.risk_snapshot_repo = RiskSnapshotRepository(db)
        self.proposal_repo = RemediationProposalRepository(db)
        self.approval_repo = RemediationApprovalRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.verification_job_repo = VerificationJobRepository(db)
        self.verification_check_repo = VerificationCheckRepository(db)
        self.verification_review_repo = VerificationReviewRepository(db)

    def _generate_time_buckets(
        self,
        start: datetime,
        end: datetime,
        bucket_count: int = 30,
    ) -> List[Tuple[datetime, datetime]]:
        """Generate time buckets for aggregation."""
        if start >= end:
            return []

        total_seconds = (end - start).total_seconds()
        bucket_seconds = max(total_seconds / bucket_count, 3600)  # Min 1 hour

        buckets = []
        current = start
        while current < end:
            next_bucket = min(current + timedelta(seconds=bucket_seconds), end)
            buckets.append((current, next_bucket))
            current = next_bucket

        return buckets

    def _check_data_sufficiency(self, data_points: List[TrendDataPoint]) -> Optional[str]:
        """Check if there's sufficient data for a reliable trend."""
        if len(data_points) < self.MIN_DATA_POINTS:
            return f"Insufficient data points ({len(data_points)}) for trend calculation. Minimum {self.MIN_DATA_POINTS} required."
        return None

    async def get_finding_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
        severity_filters: Optional[List[str]] = None,
    ) -> List[TrendSeries]:
        """Get finding count trends over time."""
        trends = []

        # Total findings over time (using first_seen_at)
        total_trend = await self._compute_finding_count_trend(
            workspace_id, period_start, period_end, "total_findings",
            "Total Findings", "count", severity_filters
        )
        trends.append(total_trend)

        # Open findings over time
        open_trend = await self._compute_finding_count_trend(
            workspace_id, period_start, period_end, "open_findings",
            "Open Findings", "count", severity_filters,
            status_filter=[FindingStatus.OPEN]
        )
        trends.append(open_trend)

        # Findings by severity
        for severity in FindingSeverity:
            if severity_filters and severity.value not in severity_filters:
                continue
            sev_trend = await self._compute_finding_count_trend(
                workspace_id, period_start, period_end,
                f"findings_{severity.value}",
                f"{severity.value.capitalize()} Findings",
                "count",
                severity_filters=[severity.value],
                status_filter=[FindingStatus.OPEN]
            )
            trends.append(sev_trend)

        # New vs resolved findings
        new_resolved = await self._compute_new_vs_resolved_trend(
            workspace_id, period_start, period_end
        )
        trends.extend(new_resolved)

        return trends

    async def _compute_finding_count_trend(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
        metric_name: str,
        metric_label: str,
        unit: str,
        severity_filters: Optional[List[str]] = None,
        status_filter: Optional[List[FindingStatus]] = None,
    ) -> TrendSeries:
        """Compute finding count trend using first_seen_at and last_seen_at."""
        # Query findings in period
        query = select(Finding).where(
            and_(
                Finding.workspace_id == workspace_id,
                Finding.first_seen_at <= period_end,
                or_(
                    Finding.last_seen_at >= period_start,
                    Finding.status != FindingStatus.FIXED,
                )
            )
        )

        if severity_filters:
            query = query.where(Finding.severity.in_([FindingSeverity(s) for s in severity_filters]))

        result = await self.db.execute(query)
        findings = list(result.scalars().all())

        # Generate time buckets
        buckets = self._generate_time_buckets(period_start, period_end)
        data_points = []

        for bucket_start, bucket_end in buckets:
            count = 0
            for f in findings:
                # Check if finding was active during this bucket
                finding_start = f.first_seen_at
                finding_end = f.fixed_at or f.last_seen_at or period_end

                if finding_start <= bucket_end and finding_end >= bucket_start:
                    if status_filter is None or f.status in status_filter:
                        count += 1

            data_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))

        limitations = self._check_data_sufficiency(data_points)
        if severity_filters:
            limitations = f"Filtered by severity: {', '.join(severity_filters)}. " + (limitations or "")

        return TrendSeries(
            metric_name=metric_name,
            metric_label=metric_label,
            unit=unit,
            data_points=data_points,
            data_source="Finding.first_seen_at / Finding.last_seen_at / Finding.fixed_at",
            aggregation_method="Count of findings active during each time bucket",
            time_window=f"{period_start.date()} to {period_end.date()}",
            limitations=limitations,
        )

    async def _compute_new_vs_resolved_trend(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TrendSeries]:
        """Compute new findings vs resolved findings trend."""
        buckets = self._generate_time_buckets(period_start, period_end)

        new_points = []
        resolved_points = []

        for bucket_start, bucket_end in buckets:
            # New findings in bucket
            new_result = await self.db.execute(
                select(func.count(Finding.id)).where(
                    and_(
                        Finding.workspace_id == workspace_id,
                        Finding.first_seen_at >= bucket_start,
                        Finding.first_seen_at < bucket_end,
                    )
                )
            )
            new_count = new_result.scalar() or 0

            # Resolved findings in bucket (status changed to FIXED)
            resolved_result = await self.db.execute(
                select(func.count(Finding.id)).where(
                    and_(
                        Finding.workspace_id == workspace_id,
                        Finding.fixed_at >= bucket_start,
                        Finding.fixed_at < bucket_end,
                    )
                )
            )
            resolved_count = resolved_result.scalar() or 0

            new_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(new_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            resolved_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(resolved_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))

        return [
            TrendSeries(
                metric_name="new_findings",
                metric_label="New Findings",
                unit="count",
                data_points=new_points,
                data_source="Finding.first_seen_at",
                aggregation_method="Count of findings first seen in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="resolved_findings",
                metric_label="Resolved Findings",
                unit="count",
                data_points=resolved_points,
                data_source="Finding.fixed_at",
                aggregation_method="Count of findings fixed in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
        ]

    async def get_risk_score_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TrendSeries]:
        """Get risk score trends from risk snapshots."""
        snapshots_result = await self.db.execute(
            select(RiskSnapshot)
            .join(RiskSnapshot.attack_path)
            .where(
                and_(
                    RiskSnapshot.workspace_id == workspace_id,
                    RiskSnapshot.calculated_at >= period_start,
                    RiskSnapshot.calculated_at <= period_end,
                )
            )
            .order_by(RiskSnapshot.calculated_at)
        )
        snapshots = list(snapshots_result.scalars().all())

        if not snapshots:
            return [TrendSeries(
                metric_name="risk_score",
                metric_label="Risk Score",
                unit="score (0-100)",
                data_points=[],
                data_source="RiskSnapshot",
                aggregation_method="Latest risk score per attack path per calculation",
                time_window=f"{period_start.date()} to {period_end.date()}",
                limitations="No risk snapshots available in the selected period",
            )]

        # Group by attack path and time bucket
        buckets = self._generate_time_buckets(period_start, period_end)
        path_scores = defaultdict(list)

        for snap in snapshots:
            path_scores[str(snap.attack_path_id)].append((snap.calculated_at, snap.score))

        # Compute average risk score per bucket across all paths
        data_points = []
        for bucket_start, bucket_end in buckets:
            bucket_scores = []
            for path_id, scores in path_scores.items():
                # Get latest score for this path in this bucket
                bucket_scores_for_path = [s for t, s in scores if bucket_start <= t < bucket_end]
                if bucket_scores_for_path:
                    path_scores[path_id].append((bucket_start, bucket_scores_for_path[-1]))

            if path_scores:
                avg_score = sum(s for _, s in path_scores[path_id] if bucket_start <= _ < bucket_end for path_id in path_scores) / len(path_scores)
                data_points.append(TrendDataPoint(
                    timestamp=bucket_start,
                    value=round(avg_score, 1),
                    label=bucket_start.strftime("%Y-%m-%d")
                ))

        limitations = self._check_data_sufficiency(data_points)

        return [TrendSeries(
            metric_name="risk_score",
            metric_label="Average Risk Score",
            unit="score (0-100)",
            data_points=data_points,
            data_source="RiskSnapshot.calculated_at / RiskSnapshot.score",
            aggregation_method="Average of latest risk score per attack path per time bucket",
            time_window=f"{period_start.date()} to {period_end.date()}",
            limitations=limitations,
        )]

    async def get_scan_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TrendSeries]:
        """Get scan completion/failure trends."""
        buckets = self._generate_time_buckets(period_start, period_end)

        completed_points = []
        failed_points = []

        for bucket_start, bucket_end in buckets:
            completed_result = await self.db.execute(
                select(func.count(Scan.id)).where(
                    and_(
                        Scan.workspace_id == workspace_id,
                        Scan.status == ScanStatus.COMPLETED,
                        Scan.completed_at >= bucket_start,
                        Scan.completed_at < bucket_end,
                    )
                )
            )
            completed_count = completed_result.scalar() or 0

            failed_result = await self.db.execute(
                select(func.count(Scan.id)).where(
                    and_(
                        Scan.workspace_id == workspace_id,
                        Scan.status == ScanStatus.FAILED,
                        Scan.failed_at >= bucket_start,
                        Scan.failed_at < bucket_end,
                    )
                )
            )
            failed_count = failed_result.scalar() or 0

            completed_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(completed_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            failed_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(failed_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))

        return [
            TrendSeries(
                metric_name="scans_completed",
                metric_label="Scans Completed",
                unit="count",
                data_points=completed_points,
                data_source="Scan.completed_at",
                aggregation_method="Count of scans completed in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="scans_failed",
                metric_label="Scans Failed",
                unit="count",
                data_points=failed_points,
                data_source="Scan.failed_at",
                aggregation_method="Count of scans failed in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
        ]

    async def get_remediation_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TrendSeries]:
        """Get remediation progress trends."""
        buckets = self._generate_time_buckets(period_start, period_end)

        proposed_points = []
        approved_points = []
        applied_points = []

        for bucket_start, bucket_end in buckets:
            proposed_result = await self.db.execute(
                select(func.count(RemediationProposal.id)).where(
                    and_(
                        RemediationProposal.workspace_id == workspace_id,
                        RemediationProposal.created_at >= bucket_start,
                        RemediationProposal.created_at < bucket_end,
                    )
                )
            )
            proposed_count = proposed_result.scalar() or 0

            approved_result = await self.db.execute(
                select(func.count(RemediationApproval.id)).where(
                    and_(
                        RemediationApproval.workspace_id == workspace_id,
                        RemediationApproval.decision == "approved",
                        RemediationApproval.approved_at >= bucket_start,
                        RemediationApproval.approved_at < bucket_end,
                    )
                )
            )
            approved_count = approved_result.scalar() or 0

            applied_result = await self.db.execute(
                select(func.count(RemediationApplication.id)).where(
                    and_(
                        RemediationApplication.workspace_id == workspace_id,
                        RemediationApplication.status == ApplicationStatus.PATCH_APPLIED,
                        RemediationApplication.applied_at >= bucket_start,
                        RemediationApplication.applied_at < bucket_end,
                    )
                )
            )
            applied_count = applied_result.scalar() or 0

            proposed_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(proposed_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            approved_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(approved_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            applied_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(applied_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))

        return [
            TrendSeries(
                metric_name="remediation_proposed",
                metric_label="Remediations Proposed",
                unit="count",
                data_points=proposed_points,
                data_source="RemediationProposal.created_at",
                aggregation_method="Count of proposals created in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="remediation_approved",
                metric_label="Remediations Approved",
                unit="count",
                data_points=approved_points,
                data_source="RemediationApproval.approved_at",
                aggregation_method="Count of approvals in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="remediation_applied",
                metric_label="Remediations Applied",
                unit="count",
                data_points=applied_points,
                data_source="RemediationApplication.applied_at",
                aggregation_method="Count of patches applied in each bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
        ]

    async def get_verification_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> List[TrendSeries]:
        """Get verification outcome trends."""
        buckets = self._generate_time_buckets(period_start, period_end)

        verified_points = []
        failed_points = []
        inconclusive_points = []

        for bucket_start, bucket_end in buckets:
            verified_result = await self.db.execute(
                select(func.count(VerificationJob.id)).where(
                    and_(
                        VerificationJob.workspace_id == workspace_id,
                        VerificationJob.overall_outcome == VerificationOutcome.VERIFIED_CANDIDATE,
                        VerificationJob.completed_at >= bucket_start,
                        VerificationJob.completed_at < bucket_end,
                    )
                )
            )
            verified_count = verified_result.scalar() or 0

            failed_result = await self.db.execute(
                select(func.count(VerificationJob.id)).where(
                    and_(
                        VerificationJob.workspace_id == workspace_id,
                        VerificationJob.overall_outcome == VerificationOutcome.FAILED,
                        VerificationJob.completed_at >= bucket_start,
                        VerificationJob.completed_at < bucket_end,
                    )
                )
            )
            failed_count = failed_result.scalar() or 0

            inconclusive_result = await self.db.execute(
                select(func.count(VerificationJob.id)).where(
                    and_(
                        VerificationJob.workspace_id == workspace_id,
                        VerificationJob.overall_outcome == VerificationOutcome.INCONCLUSIVE,
                        VerificationJob.completed_at >= bucket_start,
                        VerificationJob.completed_at < bucket_end,
                    )
                )
            )
            inconclusive_count = inconclusive_result.scalar() or 0

            verified_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(verified_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            failed_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(failed_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))
            inconclusive_points.append(TrendDataPoint(
                timestamp=bucket_start,
                value=float(inconclusive_count),
                label=bucket_start.strftime("%Y-%m-%d")
            ))

        return [
            TrendSeries(
                metric_name="verification_verified",
                metric_label="Verified Candidates",
                unit="count",
                data_points=verified_points,
                data_source="VerificationJob.completed_at",
                aggregation_method="Count of verifications with VERIFIED_CANDIDATE outcome per bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="verification_failed",
                metric_label="Verifications Failed",
                unit="count",
                data_points=failed_points,
                data_source="VerificationJob.completed_at",
                aggregation_method="Count of verifications with FAILED outcome per bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
            TrendSeries(
                metric_name="verification_inconclusive",
                metric_label="Verifications Inconclusive",
                unit="count",
                data_points=inconclusive_points,
                data_source="VerificationJob.completed_at",
                aggregation_method="Count of verifications with INCONCLUSIVE outcome per bucket",
                time_window=f"{period_start.date()} to {period_end.date()}",
            ),
        ]

    async def get_all_trends(
        self,
        workspace_id: UUID,
        period_start: datetime,
        period_end: datetime,
        severity_filters: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Get all available trends for a workspace."""
        all_trends = []

        # Finding trends
        finding_trends = await self.get_finding_trends(workspace_id, period_start, period_end, severity_filters)
        all_trends.extend(finding_trends)

        # Risk trends
        risk_trends = await self.get_risk_score_trends(workspace_id, period_start, period_end)
        all_trends.extend(risk_trends)

        # Scan trends
        scan_trends = await self.get_scan_trends(workspace_id, period_start, period_end)
        all_trends.extend(scan_trends)

        # Remediation trends
        remediation_trends = await self.get_remediation_trends(workspace_id, period_start, period_end)
        all_trends.extend(remediation_trends)

        # Verification trends
        verification_trends = await self.get_verification_trends(workspace_id, period_start, period_end)
        all_trends.extend(verification_trends)

        # Convert to dict for JSON serialization
        return {
            "trends": [
                {
                    "metric_name": t.metric_name,
                    "metric_label": t.metric_label,
                    "unit": t.unit,
                    "data_points": [
                        {
                            "timestamp": dp.timestamp.isoformat(),
                            "value": dp.value,
                            "label": dp.label,
                        }
                        for dp in t.data_points
                    ],
                    "data_source": t.data_source,
                    "aggregation_method": t.aggregation_method,
                    "time_window": t.time_window,
                    "limitations": t.limitations,
                }
                for t in all_trends
            ],
            "generated_at": datetime.utcnow().isoformat(),
            "data_cutoff": datetime.utcnow().isoformat(),
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
        }
import hashlib
import json
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func

from app.repositories import (
    AssetRepository,
    AssetAuthorizationRepository,
    ScanRepository,
    FindingRepository,
    FindingEvidenceRepository,
    AttackPathRepository,
    RiskSnapshotRepository,
    FindingRelationshipRepository,
    RemediationProposalRepository,
    RemediationApprovalRepository,
    RemediationApplicationRepository,
    RemediationRollbackRepository,
    VerificationJobRepository,
    VerificationCheckRepository,
    VerificationReviewRepository,
    VerificationPolicyRepository,
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
    FindingEvidence,
    AttackPath,
    AttackPathStatus,
    RiskSnapshot,
    FindingRelationship,
    RemediationProposal,
    RemediationStatus,
    RemediationApproval,
    RemediationApplication,
    ApplicationStatus,
    RemediationRollback,
    RollbackStatus,
    VerificationJob,
    VerificationStatus,
    VerificationOutcome,
    VerificationCheck,
    CheckType,
    CheckStatus,
    VerificationReview,
    ReviewDecision,
    VerificationPolicy,
    Profile,
    WorkspaceMember,
    WorkspaceRole,
    Report,
    ReportType,
    ReportFormat,
    ReportStatus,
    ReportSection,
    ReportExport,
)
from app.services.dashboard_metrics import DashboardMetricsService
from app.services.trends import TrendService
from app.services.report_export import ReportExportService
from app.services.report_storage import ReportStorageService
from app.security.audit import audit_log
from app.ai.manager import AIManager
from app.ai.schemas import SecurityAnalysis


class ReportService:
    """Service for generating and managing security reports."""

    SCHEMA_VERSION = "report-v1"
    DEFAULT_REPORT_TIMEOUT = 300  # 5 minutes

    def __init__(self, db: AsyncSession):
        self.db = db
        self.asset_repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)
        self.scan_repo = ScanRepository(db)
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.attack_path_repo = AttackPathRepository(db)
        self.risk_snapshot_repo = RiskSnapshotRepository(db)
        self.relationship_repo = FindingRelationshipRepository(db)
        self.proposal_repo = RemediationProposalRepository(db)
        self.approval_repo = RemediationApprovalRepository(db)
        self.application_repo = RemediationApplicationRepository(db)
        self.rollback_repo = RemediationRollbackRepository(db)
        self.verification_job_repo = VerificationJobRepository(db)
        self.verification_check_repo = VerificationCheckRepository(db)
        self.verification_review_repo = VerificationReviewRepository(db)
        self.policy_repo = VerificationPolicyRepository(db)
        self.dashboard_service = DashboardMetricsService(db)
        self.trend_service = TrendService(db)
        self.export_service = ReportExportService()
        self.storage_service = ReportStorageService()
        self.ai_manager = AIManager()

    async def _verify_workspace_access(
        self,
        user_id: UUID,
        workspace_id: UUID,
        required_roles: List[WorkspaceRole] = None,
    ) -> WorkspaceMember:
        """Verify user has access to workspace."""
        if required_roles is None:
            required_roles = [WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER, WorkspaceRole.VIEWER]

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
            raise AuthorizationError("Insufficient permissions for workspace")
        return member

    async def create_report(
        self,
        user_id: UUID,
        request,
    ) -> Report:
        """Create and start generating a report."""
        await self._verify_workspace_access(user_id, request.workspace_id)

        # Validate included assets belong to workspace
        if request.included_asset_ids:
            assets_result = await self.db.execute(
                select(Asset).where(
                    and_(
                        Asset.workspace_id == request.workspace_id,
                        Asset.id.in_(request.included_asset_ids),
                    )
                )
            )
            found_assets = list(assets_result.scalars().all())
            if len(found_assets) != len(request.included_asset_ids):
                raise ValidationError("Some assets not found or not in workspace")

        # Determine period
        period_end = request.period_end or datetime.utcnow()
        period_start = request.period_start or (period_end - timedelta(days=30))

        # Create report record
        report = Report(
            workspace_id=request.workspace_id,
            report_type=request.report_type,
            title=request.title,
            description=request.description,
            format=request.format,
            status=ReportStatus.PENDING,
            schema_version=self.SCHEMA_VERSION,
            risk_engine_version="risk-v1",
            verification_policy_version="verification-policy-v1",
            period_start=period_start,
            period_end=period_end,
            data_cutoff=datetime.utcnow(),
            filters=request.filters or {},
            included_asset_ids=request.included_asset_ids or [],
            severity_filters=request.severity_filters or [],
            source_record_references={},
            completeness={},
            limitations=[],
            generated_by=user_id,
        )

        self.db.add(report)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=request.workspace_id,
            user_id=user_id,
            action="report.requested",
            resource_type="report",
            resource_id=report.id,
            details={
                "report_type": request.report_type.value,
                "format": request.format.value,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
            },
        )

        # Start generation asynchronously (in production, use background task)
        # For now, generate synchronously
        await self._generate_report(report, user_id, request.include_ai_narrative)

        return report

    async def _generate_report(
        self,
        report: Report,
        user_id: UUID,
        include_ai_narrative: bool = False,
    ):
        """Generate the report content."""
        report.status = ReportStatus.GENERATING
        report.started_at = datetime.utcnow()
        await self.db.flush()

        try:
            if report.report_type == ReportType.EXECUTIVE_SUMMARY:
                await self._generate_executive_summary(report, include_ai_narrative)
            elif report.report_type == ReportType.TECHNICAL_VULNERABILITY:
                await self._generate_technical_vulnerability(report)
            elif report.report_type == ReportType.REMEDIATION_PROGRESS:
                await self._generate_remediation_progress(report)
            elif report.report_type == ReportType.VERIFICATION_REGRESSION:
                await self._generate_verification_regression(report)
            elif report.report_type == ReportType.ASSET_SECURITY_POSTURE:
                await self._generate_asset_security_posture(report)
            else:
                raise ValidationError(f"Unknown report type: {report.report_type}")

            # Generate exports
            await self._generate_exports(report)

            report.status = ReportStatus.READY
            report.completed_at = datetime.utcnow()

            await audit_log(
                self.db,
                workspace_id=report.workspace_id,
                user_id=user_id,
                action="report.generated",
                resource_type="report",
                resource_id=report.id,
                details={
                    "report_type": report.report_type.value,
                    "format": report.format.value,
                    "file_size_bytes": report.file_size_bytes,
                },
            )

        except Exception as e:
            report.status = ReportStatus.FAILED
            report.error_message = str(e)
            report.completed_at = datetime.utcnow()

            await audit_log(
                self.db,
                workspace_id=report.workspace_id,
                user_id=user_id,
                action="report.generation_failed",
                resource_type="report",
                resource_id=report.id,
                details={"error": str(e)},
            )
            raise

        finally:
            await self.db.flush()

    async def _generate_executive_summary(
        self,
        report: Report,
        include_ai_narrative: bool,
    ):
        """Generate Executive Security Summary report."""
        metrics = await self.dashboard_service.get_workspace_metrics(
            report.workspace_id, report.generated_by
        )

        # Build completeness info
        completeness = {
            "assets": True,
            "scans": metrics["scans"]["total_scans"] > 0,
            "findings": metrics["findings"]["total_findings"] > 0,
            "risk": metrics["risk"]["total_attack_paths"] > 0,
            "remediation": metrics["remediation"]["total_proposals"] > 0,
            "verification": metrics["verification"]["verification_jobs_by_status"],
        }

        limitations = [
            "Report reflects data as of the data cutoff timestamp.",
            "AI analysis requires configured API keys (may be unavailable).",
            "Scanner results require completed scans.",
            "Historical trends limited to available snapshot data.",
        ]

        if metrics["scans"]["total_scans"] == 0:
            limitations.append("No scans completed in this workspace; vulnerability data may be incomplete.")

        report.completeness = completeness
        report.limitations = limitations

        # Create sections
        sections_data = [
            ("executive_overview", "Executive Overview", 1, self._build_executive_overview(metrics)),
            ("security_posture", "Overall Security Posture", 2, self._build_security_posture(metrics)),
            ("critical_risks", "Most Important Current Risks", 3, self._build_critical_risks(metrics)),
            ("critical_findings", "Critical and High-Severity Findings", 4, self._build_critical_findings(report.workspace_id, report.included_asset_ids)),
            ("attack_paths", "Important Attack Paths", 5, self._build_attack_paths_summary(report.workspace_id)),
            ("remediation_progress", "Remediation Progress", 6, self._build_remediation_progress(metrics)),
            ("verification_outcomes", "Verification Outcomes", 7, self._build_verification_outcomes(metrics)),
            ("unresolved_risks", "Unresolved Risks", 8, self._build_unresolved_risks(metrics)),
            ("recommended_actions", "Recommended Next Actions", 9, self._build_recommended_actions(metrics)),
            ("scope_limitations", "Scope, Date Range & Limitations", 10, self._build_scope_limitations(report, metrics)),
        ]

        if include_ai_narrative:
            ai_narrative = await self._generate_ai_narrative(metrics, "executive_summary")
            if ai_narrative:
                sections_data.insert(1, ("ai_narrative", "AI-Generated Executive Narrative", 2, ai_narrative))
                # Renumber
                for i, (key, title, order, content) in enumerate(sections_data):
                    sections_data[i] = (key, title, i + 1, content)

        for key, title, order, content in sections_data:
            section = ReportSection(
                report_id=report.id,
                workspace_id=report.workspace_id,
                section_key=key,
                section_title=title,
                section_order=order,
                content=content,
                data_references=self._extract_data_references(content),
            )
            self.db.add(section)

        # Record source references
        report.source_record_references = {
            "metrics_timestamp": datetime.utcnow().isoformat(),
            "asset_count": metrics["assets"]["total_assets"],
            "scan_count": metrics["scans"]["total_scans"],
            "finding_count": metrics["findings"]["total_findings"],
            "attack_path_count": metrics["risk"]["total_attack_paths"],
            "remediation_count": metrics["remediation"]["total_proposals"],
            "verification_count": sum(metrics["verification"]["verification_jobs_by_status"].values()),
        }

    def _build_executive_overview(self, metrics: Dict) -> Dict:
        return {
            "summary": f"Security assessment for workspace covering {metrics['assets']['total_assets']} assets, "
                       f"{metrics['scans']['total_scans']} scans, and {metrics['findings']['total_findings']} findings.",
            "period": {
                "start": metrics.get("period_start"),
                "end": metrics.get("period_end"),
            },
            "key_metrics": {
                "assets_monitored": metrics["assets"]["total_assets"],
                "authorized_assets": metrics["assets"]["assets_with_authorization"],
                "open_findings": sum(metrics["findings"]["open_findings_by_severity"].values()),
                "critical_findings": metrics["findings"]["open_findings_by_severity"].get("critical", 0),
                "high_findings": metrics["findings"]["open_findings_by_severity"].get("high", 0),
                "active_attack_paths": metrics["risk"]["attack_paths_by_status"].get("active", 0),
                "pending_remediations": metrics["remediation"]["remediation_proposals_by_status"].get("AWAITING_APPROVAL", 0),
                "verification_pending": metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0),
            },
        }

    def _build_security_posture(self, metrics: Dict) -> Dict:
        # Calculate overall posture based on findings and risk
        critical = metrics["findings"]["open_findings_by_severity"].get("critical", 0)
        high = metrics["findings"]["open_findings_by_severity"].get("high", 0)
        risk_score = metrics["risk"]["current_risk_score"] or 0

        if critical > 0 or risk_score >= 70:
            posture = "Critical"
        elif high > 2 or risk_score >= 50:
            posture = "High Risk"
        elif high > 0 or risk_score >= 30:
            posture = "Medium Risk"
        else:
            posture = "Low Risk"

        return {
            "overall_posture": posture,
            "methodology": "Based on deterministic risk engine (risk-v1) considering open critical/high findings, "
                           "attack path risk scores, and remediation coverage.",
            "risk_score": risk_score,
            "risk_model_version": metrics["risk"]["risk_model_version"],
            "contributing_factors": {
                "critical_findings": critical,
                "high_findings": high,
                "unauthorized_assets": metrics["assets"]["total_assets"] - metrics["assets"]["assets_with_authorization"],
                "unverified_remediations": metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0),
            },
        }

    def _build_critical_risks(self, metrics: Dict) -> Dict:
        return {
            "summary": "Top risks requiring immediate attention",
            "risks": [
                {
                    "title": "Unpatched Critical Vulnerabilities",
                    "count": metrics["findings"]["open_findings_by_severity"].get("critical", 0),
                    "impact": "Immediate exploitability, potential data breach or system compromise",
                },
                {
                    "title": "High-Severity Findings Without Remediation",
                    "count": metrics["findings"]["open_findings_by_severity"].get("high", 0),
                    "impact": "Significant security exposure if exploited",
                },
                {
                    "title": "Assets Without Authorization",
                    "count": metrics["assets"]["total_assets"] - metrics["assets"]["assets_with_authorization"],
                    "impact": "Scanning and remediation cannot proceed without valid authorization",
                },
                {
                    "title": "Pending Verification of Fixes",
                    "count": metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0),
                    "impact": "Applied patches not yet independently verified as effective",
                },
            ],
        }

    async def _build_critical_findings(
        self,
        workspace_id: UUID,
        included_asset_ids: Optional[List[UUID]],
    ) -> Dict:
        query = select(Finding).where(
            and_(
                Finding.workspace_id == workspace_id,
                Finding.status == FindingStatus.OPEN,
                Finding.severity.in_([FindingSeverity.CRITICAL, FindingSeverity.HIGH]),
            )
        )

        if included_asset_ids:
            query = query.where(Finding.asset_id.in_(included_asset_ids))

        query = query.order_by(
            case((Finding.severity == FindingSeverity.CRITICAL, 0), else_=1),
            Finding.risk_score.desc().nullslast(),
            Finding.first_seen_at,
        ).limit(20)

        result = await self.db.execute(query)
        findings = list(result.scalars().all())

        return {
            "count": len(findings),
            "findings": [
                {
                    "id": str(f.id),
                    "title": f.title,
                    "severity": f.severity.value,
                    "asset_id": str(f.asset_id),
                    "source": f.source.value,
                    "source_rule_id": f.source_rule_id,
                    "location": f.location,
                    "first_seen_at": f.first_seen_at.isoformat() if f.first_seen_at else None,
                    "risk_score": f.risk_score,
                    "has_ai_analysis": False,  # Would check FindingAiAnalysis
                    "remediation_status": None,  # Would check RemediationProposal
                }
                for f in findings
            ],
        }

    async def _build_attack_paths_summary(self, workspace_id: UUID) -> Dict:
        paths_result = await self.db.execute(
            select(AttackPath).where(
                and_(
                    AttackPath.workspace_id == workspace_id,
                    AttackPath.status.in_([AttackPathStatus.ACTIVE, AttackPathStatus.DRAFT]),
                )
            ).order_by(AttackPath.risk_score.desc().nullslast()).limit(10)
        )
        paths = list(paths_result.scalars().all())

        return {
            "count": len(paths),
            "paths": [
                {
                    "id": str(p.id),
                    "title": p.title,
                    "risk_score": p.risk_score,
                    "severity": p.severity,
                    "risk_band": p.risk_band,
                    "status": p.status.value,
                    "node_count": len(p.nodes),
                }
                for p in paths
            ],
        }

    def _build_remediation_progress(self, metrics: Dict) -> Dict:
        return {
            "summary": f"{metrics['remediation']['remediation_approved']} approved, "
                       f"{metrics['remediation']['remediation_applied']} applied, "
                       f"{metrics['remediation']['remediation_rejected']} rejected out of "
                       f"{metrics['remediation']['total_proposals']} total proposals.",
            "by_status": metrics["remediation"]["remediation_proposals_by_status"],
            "approval_rate": (
                metrics["remediation"]["remediation_approved"] / max(metrics["remediation"]["total_proposals"], 1) * 100
            ),
            "application_rate": (
                metrics["remediation"]["remediation_applied"] / max(metrics["remediation"]["remediation_approved"], 1) * 100
            ),
        }

    def _build_verification_outcomes(self, metrics: Dict) -> Dict:
        outcomes = metrics["verification"]["verification_outcomes"]
        return {
            "summary": f"{outcomes.get('VERIFIED_CANDIDATE', 0)} verified candidates, "
                       f"{outcomes.get('FAILED', 0)} failed, "
                       f"{outcomes.get('INCONCLUSIVE', 0)} inconclusive.",
            "outcomes": outcomes,
            "regression_failures": metrics["verification"]["regression_failures"],
            "pending_review": metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0),
        }

    def _build_unresolved_risks(self, metrics: Dict) -> Dict:
        return {
            "open_critical_findings": metrics["findings"]["open_findings_by_severity"].get("critical", 0),
            "open_high_findings": metrics["findings"]["open_findings_by_severity"].get("high", 0),
            "unverified_remediations": metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0),
            "regression_failures": metrics["verification"]["regression_failures"],
            "unauthorized_assets": metrics["assets"]["total_assets"] - metrics["assets"]["assets_with_authorization"],
        }

    def _build_recommended_actions(self, metrics: Dict) -> Dict:
        actions = []

        if metrics["findings"]["open_findings_by_severity"].get("critical", 0) > 0:
            actions.append({
                "priority": "immediate",
                "action": "Remediate all critical-severity findings",
                "details": f"{metrics['findings']['open_findings_by_severity'].get('critical', 0)} critical findings open",
            })

        if metrics["verification"]["verification_jobs_by_status"].get("PASSED_PENDING_REVIEW", 0) > 0:
            actions.append({
                "priority": "high",
                "action": "Complete human review of verified candidate fixes",
                "details": f"{metrics['verification']['verification_jobs_by_status'].get('PASSED_PENDING_REVIEW', 0)} verifications awaiting review",
            })

        if metrics["verification"]["regression_failures"] > 0:
            actions.append({
                "priority": "high",
                "action": "Investigate regression test failures",
                "details": f"{metrics['verification']['regression_failures']} regression checks failed",
            })

        if metrics["assets"]["total_assets"] - metrics["assets"]["assets_with_authorization"] > 0:
            actions.append({
                "priority": "medium",
                "action": "Complete authorization for all assets",
                "details": f"{metrics['assets']['total_assets'] - metrics['assets']['assets_with_authorization']} assets lack valid authorization",
            })

        return {"actions": actions}

    def _build_scope_limitations(self, report: Report, metrics: Dict) -> Dict:
        return {
            "report_scope": {
                "workspace_id": str(report.workspace_id),
                "report_type": report.report_type.value,
                "period_start": report.period_start.isoformat() if report.period_start else None,
                "period_end": report.period_end.isoformat() if report.period_end else None,
                "data_cutoff": report.data_cutoff.isoformat(),
                "included_assets": len(report.included_asset_ids) if report.included_asset_ids else "All workspace assets",
                "severity_filters": report.severity_filters or "All severities",
            },
            "limitations": report.limitations,
            "completeness": report.completeness,
        }

    async def _generate_technical_vulnerability(self, report: Report):
        """Generate Technical Vulnerability Report."""
        # Implementation similar to executive summary but with detailed finding data
        pass

    async def _generate_remediation_progress(self, report: Report):
        """Generate Remediation Progress Report."""
        pass

    async def _generate_verification_regression(self, report: Report):
        """Generate Verification & Regression Report."""
        pass

    async def _generate_asset_security_posture(self, report: Report):
        """Generate Asset Security Posture Report."""
        pass

    def _extract_data_references(self, content: Dict) -> Dict:
        """Extract source record references from section content."""
        refs = {}
        if "findings" in content:
            refs["findings"] = [f.get("id") for f in content["findings"] if f.get("id")]
        if "paths" in content:
            refs["attack_paths"] = [p.get("id") for p in content["paths"] if p.get("id")]
        return refs

    async def _generate_ai_narrative(self, metrics: Dict, report_type: str) -> Optional[Dict]:
        """Generate AI-assisted narrative summary."""
        try:
            # Build context for AI
            context = {
                "report_type": report_type,
                "metrics": {
                    k: v for k, v in metrics.items()
                    if k not in ["activity"]  # Exclude timestamps
                },
            }

            # Sanitize context (remove sensitive data)
            sanitized = self._sanitize_for_ai(context)

            # Generate narrative using AI
            # Note: This would use the AI manager with a structured prompt
            # For now, return None to indicate AI unavailable
            return None
        except Exception:
            return None

    def _sanitize_for_ai(self, data: Dict) -> Dict:
        """Sanitize data before sending to AI provider."""
        # Remove any potential secrets, credentials, etc.
        sanitized = {}
        for k, v in data.items():
            if isinstance(v, dict):
                sanitized[k] = self._sanitize_for_ai(v)
            elif isinstance(v, list):
                sanitized[k] = [self._sanitize_for_ai(item) if isinstance(item, dict) else item for item in v]
            elif isinstance(v, str) and any(pattern in v.lower() for pattern in ["key", "secret", "token", "password"]):
                sanitized[k] = "[REDACTED]"
            else:
                sanitized[k] = v
        return sanitized

    async def _generate_exports(self, report: Report):
        """Generate PDF and JSON exports."""
        # Get report sections
        sections_result = await self.db.execute(
            select(ReportSection).where(ReportSection.report_id == report.id)
            .order_by(ReportSection.section_order)
        )
        sections = list(sections_result.scalars().all())

        # Prepare report data for export
        report_data = {
            "report": {
                "id": str(report.id),
                "workspace_id": str(report.workspace_id),
                "report_type": report.report_type.value,
                "title": report.title,
                "description": report.description,
                "format": report.format.value,
                "schema_version": report.schema_version,
                "risk_engine_version": report.risk_engine_version,
                "verification_policy_version": report.verification_policy_version,
                "period_start": report.period_start.isoformat() if report.period_start else None,
                "period_end": report.period_end.isoformat() if report.period_end else None,
                "data_cutoff": report.data_cutoff.isoformat(),
                "generated_by": str(report.generated_by),
                "created_at": report.created_at.isoformat(),
                "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            },
            "sections": [
                {
                    "section_key": s.section_key,
                    "section_title": s.section_title,
                    "section_order": s.section_order,
                    "content": s.content,
                    "data_references": s.data_references,
                }
                for s in sections
            ],
            "completeness": report.completeness,
            "limitations": report.limitations,
            "source_record_references": report.source_record_references,
        }

        # Generate JSON export
        json_content = json.dumps(report_data, indent=2, default=str).encode()
        json_checksum = hashlib.sha256(json_content).hexdigest()

        # Generate PDF export (placeholder - actual implementation in export_service)
        pdf_content = await self.export_service.generate_pdf(report_data)
        pdf_checksum = hashlib.sha256(pdf_content).hexdigest()

        # Store exports
        for fmt, content, checksum in [
            (ReportFormat.JSON, json_content, json_checksum),
            (ReportFormat.PDF, pdf_content, pdf_checksum),
        ]:
            # Store in storage
            storage_path = await self.storage_service.store_report(
                report.workspace_id, report.id, fmt.value, content
            )

            export = ReportExport(
                report_id=report.id,
                workspace_id=report.workspace_id,
                format=fmt,
                storage_object_id=uuid4(),  # Placeholder
                storage_path=storage_path,
                file_size_bytes=len(content),
                checksum=checksum,
                generated_by=report.generated_by,
                expires_at=datetime.utcnow() + timedelta(days=30),
            )
            self.db.add(export)

        # Update report with primary export info
        if report.format == ReportFormat.PDF:
            report.storage_path = f"reports/{report.workspace_id}/{report.id}.pdf"
            report.file_size_bytes = len(pdf_content)
            report.checksum = pdf_checksum
        else:
            report.storage_path = f"reports/{report.workspace_id}/{report.id}.json"
            report.file_size_bytes = len(json_content)
            report.checksum = json_checksum

    async def get_report(self, report_id: UUID, user_id: UUID) -> Optional[Report]:
        """Get report by ID with workspace access check."""
        result = await self.db.execute(
            select(Report).where(Report.id == report_id)
        )
        report = result.scalar_one_or_none()

        if not report:
            return None

        await self._verify_workspace_access(user_id, report.workspace_id)
        return report

    async def list_reports(
        self,
        workspace_id: UUID,
        user_id: UUID,
        report_type: Optional[ReportType] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Report]:
        """List reports for a workspace."""
        await self._verify_workspace_access(user_id, workspace_id)

        query = select(Report).where(Report.workspace_id == workspace_id)

        if report_type:
            query = query.where(Report.report_type == report_type)
        if status:
            query = query.where(Report.status == status)

        query = query.order_by(Report.created_at.desc()).limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_report_detail(self, report_id: UUID, user_id: UUID) -> Optional[Dict]:
        """Get full report detail with sections and exports."""
        report = await self.get_report(report_id, user_id)
        if not report:
            return None

        sections_result = await self.db.execute(
            select(ReportSection).where(ReportSection.report_id == report_id)
            .order_by(ReportSection.section_order)
        )
        sections = list(sections_result.scalars().all())

        exports_result = await self.db.execute(
            select(ReportExport).where(ReportExport.report_id == report_id)
        )
        exports = list(exports_result.scalars().all())

        return {
            "report": report,
            "sections": sections,
            "exports": exports,
        }

    async def export_report(
        self,
        report_id: UUID,
        user_id: UUID,
        format: ReportFormat,
    ) -> ReportExport:
        """Generate and store a new export for an existing report."""
        report = await self.get_report(report_id, user_id)
        if not report:
            raise NotFoundError(f"Report {report_id} not found")

        if report.status != ReportStatus.READY:
            raise ValidationError(f"Report not ready for export: {report.status}")

        # Get report data
        detail = await self.get_report_detail(report_id, user_id)
        if not detail:
            raise NotFoundError(f"Report {report_id} not found")

        report_data = {
            "report": {
                "id": str(report.id),
                "workspace_id": str(report.workspace_id),
                "report_type": report.report_type.value,
                "title": report.title,
                "description": report.description,
                "format": format.value,
                "schema_version": report.schema_version,
                "risk_engine_version": report.risk_engine_version,
                "verification_policy_version": report.verification_policy_version,
                "period_start": report.period_start.isoformat() if report.period_start else None,
                "period_end": report.period_end.isoformat() if report.period_end else None,
                "data_cutoff": report.data_cutoff.isoformat(),
                "generated_by": str(report.generated_by),
                "created_at": report.created_at.isoformat(),
                "completed_at": report.completed_at.isoformat() if report.completed_at else None,
            },
            "sections": [
                {
                    "section_key": s.section_key,
                    "section_title": s.section_title,
                    "section_order": s.section_order,
                    "content": s.content,
                    "data_references": s.data_references,
                }
                for s in detail["sections"]
            ],
            "completeness": report.completeness,
            "limitations": report.limitations,
            "source_record_references": report.source_record_references,
        }

        if format == ReportFormat.JSON:
            content = json.dumps(report_data, indent=2, default=str).encode()
        else:
            content = await self.export_service.generate_pdf(report_data)

        checksum = hashlib.sha256(content).hexdigest()
        storage_path = await self.storage_service.store_report(
            report.workspace_id, report.id, format.value, content
        )

        export = ReportExport(
            report_id=report.id,
            workspace_id=report.workspace_id,
            format=format,
            storage_object_id=uuid4(),
            storage_path=storage_path,
            file_size_bytes=len(content),
            checksum=checksum,
            generated_by=user_id,
            expires_at=datetime.utcnow() + timedelta(days=30),
        )
        self.db.add(export)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=report.workspace_id,
            user_id=user_id,
            action="report.exported",
            resource_type="report_export",
            resource_id=export.id,
            details={
                "report_id": str(report.id),
                "format": format.value,
                "file_size_bytes": len(content),
            },
        )

        return export

    async def get_download_url(
        self,
        export_id: UUID,
        user_id: UUID,
    ) -> Optional[str]:
        """Get signed download URL for a report export."""
        result = await self.db.execute(
            select(ReportExport).where(ReportExport.id == export_id)
        )
        export = result.scalar_one_or_none()

        if not export:
            return None

        # Verify workspace access
        await self._verify_workspace_access(user_id, export.workspace_id)

        # Check expiration
        if export.expires_at and export.expires_at < datetime.utcnow():
            return None

        # Generate signed URL (placeholder - actual implementation in storage_service)
        return await self.storage_service.get_download_url(export.storage_path)


from datetime import timedelta
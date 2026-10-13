import hashlib
import json
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.repositories import (
    FindingRepository,
    FindingEvidenceRepository,
    ScanRepository,
    ScanTargetRepository,
    RemediationVerificationHandoffRepository,
)
from app.models import (
    Finding,
    FindingEvidence,
    Scan,
    VerificationJob,
    VerificationBaseline,
    VerificationStatus,
    VerificationHandoffStatus,
)
from app.scanners.semgrep import SemgrepRunner
from app.security.audit import audit_log


class BaselineCaptureService:
    """Service for capturing and managing verification baselines."""

    FINDING_FINGERPRINT_VERSION = "v1"
    SCANNER_VERSION = "semgrep-1.0.0"

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.scan_repo = ScanRepository(db)
        self.scan_target_repo = ScanTargetRepository(db)
        self.handoff_repo = RemediationVerificationHandoffRepository(db)
        self.semgrep_runner = SemgrepRunner()

    def _compute_finding_fingerprint(
        self,
        finding: Finding,
        evidence: List[FindingEvidence],
        rule_ids: List[str],
    ) -> str:
        """Compute stable fingerprint for a finding."""
        normalized_path = (finding.location or {}).get("path", "") if finding.location else ""
        normalized_path = normalized_path.replace("\\", "/").lstrip("/")

        location = finding.location or {}
        location_str = json.dumps(location, sort_keys=True)

        evidence_hashes = sorted([e.metadata.get("content_hash", "") for e in evidence if e.metadata.get("content_hash")])

        fingerprint_data = {
            "version": self.FINDING_FINGERPRINT_VERSION,
            "rule_ids": sorted(rule_ids),
            "normalized_path": normalized_path,
            "location": location_str,
            "evidence_hashes": evidence_hashes,
            "source": finding.source.value,
            "severity": finding.severity.value,
        }

        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_json.encode()).hexdigest()

    def _compute_evidence_hash(self, evidence: FindingEvidence) -> str:
        """Compute hash of evidence content."""
        content = evidence.content or {}
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    async def capture_baseline_from_handoff(
        self,
        verification_job: VerificationJob,
        handoff,
        requester_id: UUID,
    ) -> VerificationBaseline:
        """Capture baseline from remediation verification handoff."""
        finding = await self.finding_repo.get_by_id(handoff.finding_id)
        if not finding:
            raise ValueError(f"Finding {handoff.finding_id} not found")

        evidence = await self.evidence_repo.get_by_finding(handoff.finding_id)

        rule_ids = [finding.source_rule_id] if finding.source_rule_id else []

        fingerprint = self._compute_finding_fingerprint(finding, evidence, rule_ids)
        evidence_hashes = [self._compute_evidence_hash(e) for e in evidence]

        original_snapshot = handoff.original_finding_snapshot or {}
        if not original_snapshot:
            original_snapshot = {
                "id": str(finding.id),
                "title": finding.title,
                "description": finding.description,
                "severity": finding.severity.value,
                "confidence": finding.confidence.value,
                "cwe_ids": finding.cwe_ids,
                "cve_ids": finding.cve_ids,
                "owasp_categories": finding.owasp_categories,
                "location": finding.location,
                "code_snippet": finding.code_snippet,
                "remediation_guidance": finding.remediation_guidance,
                "risk_score": finding.risk_score,
                "risk_factors": finding.risk_factors,
                "status": finding.status.value,
            }

        original_evidence = []
        for e in evidence:
            original_evidence.append({
                "id": str(e.id),
                "evidence_type": e.evidence_type.value,
                "title": e.title,
                "description": e.description,
                "content": e.content,
                "file_path": e.file_path,
                "line_start": e.line_start,
                "line_end": e.line_end,
                "metadata": e.metadata,
            })

        scanner_config = {}
        if handoff.validation_results:
            scanner_config = handoff.validation_results.get("scanner_config", {})

        baseline = VerificationBaseline(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            finding_id=finding.id,
            original_finding_snapshot=original_snapshot,
            original_evidence=original_evidence,
            scanner_version=self.SCANNER_VERSION,
            scanner_config=scanner_config,
            rule_ids=rule_ids,
            finding_fingerprint=fingerprint,
            evidence_hashes=evidence_hashes,
            repository_revision=handoff.repository_revision,
            scan_id=handoff.proposal.source_scan_id if handoff.proposal else None,
            pre_patch_scan_results=None,
            capture_method="handoff",
            captured_at=datetime.utcnow(),
            captured_by=requester_id,
        )

        self.db.add(baseline)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=verification_job.workspace_id,
            user_id=requester_id,
            action="verification.baseline_captured",
            resource_type="verification_baseline",
            resource_id=baseline.id,
            details={
                "verification_job_id": str(verification_job.id),
                "finding_id": str(finding.id),
                "fingerprint": fingerprint[:16],
                "capture_method": "handoff",
            },
        )

        return baseline

    async def capture_baseline_from_scan(
        self,
        verification_job: VerificationJob,
        scan_id: UUID,
        requester_id: UUID,
    ) -> VerificationBaseline:
        """Capture baseline from a pre-patch scan."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ValueError(f"Scan {scan_id} not found")

        finding = await self.finding_repo.get_by_id(verification_job.finding_id)
        if not finding:
            raise ValueError(f"Finding {verification_job.finding_id} not found")

        evidence = await self.evidence_repo.get_by_finding(finding.id)

        rule_ids = [finding.source_rule_id] if finding.source_rule_id else []

        fingerprint = self._compute_finding_fingerprint(finding, evidence, rule_ids)
        evidence_hashes = [self._compute_evidence_hash(e) for e in evidence]

        original_snapshot = {
            "id": str(finding.id),
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity.value,
            "confidence": finding.confidence.value,
            "cwe_ids": finding.cwe_ids,
            "cve_ids": finding.cve_ids,
            "owasp_categories": finding.owasp_categories,
            "location": finding.location,
            "code_snippet": finding.code_snippet,
            "remediation_guidance": finding.remediation_guidance,
            "risk_score": finding.risk_score,
            "risk_factors": finding.risk_factors,
            "status": finding.status.value,
        }

        original_evidence = []
        for e in evidence:
            original_evidence.append({
                "id": str(e.id),
                "evidence_type": e.evidence_type.value,
                "title": e.title,
                "description": e.description,
                "content": e.content,
                "file_path": e.file_path,
                "line_start": e.line_start,
                "line_end": e.line_end,
                "metadata": e.metadata,
            })

        pre_patch_scan_results = {
            "scan_id": str(scan.id),
            "scan_type": scan.scan_type.value,
            "scan_profile": scan.scan_profile.value,
            "summary": scan.summary,
            "phases_completed": scan.phases_completed,
        }

        scanner_config = scan.scan_config or {}

        baseline = VerificationBaseline(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            finding_id=finding.id,
            original_finding_snapshot=original_snapshot,
            original_evidence=original_evidence,
            scanner_version=self.SCANNER_VERSION,
            scanner_config=scanner_config,
            rule_ids=rule_ids,
            finding_fingerprint=fingerprint,
            evidence_hashes=evidence_hashes,
            repository_revision=scan.target_reference or "",
            scan_id=scan.id,
            pre_patch_scan_results=pre_patch_scan_results,
            capture_method="pre_patch_scan",
            captured_at=datetime.utcnow(),
            captured_by=requester_id,
        )

        self.db.add(baseline)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=verification_job.workspace_id,
            user_id=requester_id,
            action="verification.baseline_captured",
            resource_type="verification_baseline",
            resource_id=baseline.id,
            details={
                "verification_job_id": str(verification_job.id),
                "finding_id": str(finding.id),
                "scan_id": str(scan_id),
                "fingerprint": fingerprint[:16],
                "capture_method": "pre_patch_scan",
            },
        )

        return baseline

    async def get_baseline(self, verification_job_id: UUID) -> Optional[VerificationBaseline]:
        """Get the baseline for a verification job."""
        result = await self.db.execute(
            select(VerificationBaseline).where(
                VerificationBaseline.verification_job_id == verification_job_id
            )
        )
        return result.scalar_one_or_none()

    async def run_baseline_validation(
        self,
        verification_job: VerificationJob,
    ) -> Dict[str, Any]:
        """Validate that baseline is valid and complete."""
        baseline = await self.get_baseline(verification_job.id)
        if not baseline:
            return {"valid": False, "reason": "No baseline captured"}

        issues = []

        if not baseline.finding_fingerprint:
            issues.append("Missing finding fingerprint")

        if not baseline.evidence_hashes:
            issues.append("Missing evidence hashes")

        if not baseline.scanner_version:
            issues.append("Missing scanner version")

        if not baseline.repository_revision:
            issues.append("Missing repository revision")

        if baseline.capture_method == "handoff":
            handoff = await self.handoff_repo.get_by_proposal(verification_job.remediation_proposal_id)
            if not handoff:
                issues.append("Handoff not found for baseline")
            elif handoff.status != VerificationHandoffStatus.VERIFICATION_REQUESTED:
                issues.append(f"Handoff status not VERIFICATION_REQUESTED: {handoff.status}")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "baseline_id": str(baseline.id) if baseline else None,
            "fingerprint": baseline.finding_fingerprint[:16] if baseline and baseline.finding_fingerprint else None,
        }
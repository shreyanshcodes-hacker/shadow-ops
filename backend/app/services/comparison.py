import hashlib
import json
from typing import Optional, List, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.repositories import (
    FindingRepository,
    FindingEvidenceRepository,
    ScanRepository,
)
from app.models import (
    Finding,
    FindingEvidence,
    Scan,
    VerificationJob,
    VerificationBaseline,
    EvidenceComparison,
    ComparisonCategory,
    CheckStatus,
)
from app.scanners.semgrep import SemgrepRunner, SemgrepFinding
from app.security.audit import audit_log


class EvidenceComparisonService:
    """Service for comparing pre-patch and post-patch evidence."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.scan_repo = ScanRepository(db)
        self.semgrep_runner = SemgrepRunner()

    def _normalize_file_path(self, path: str) -> str:
        """Normalize file path for comparison."""
        return path.replace("\\", "/").lstrip("/")

    def _compute_evidence_hash(self, evidence: FindingEvidence) -> str:
        """Compute hash of evidence content."""
        content = evidence.content or {}
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _compute_semgrep_finding_fingerprint(
        self,
        finding: SemgrepFinding,
        rule_id: str,
    ) -> str:
        """Compute fingerprint from semgrep finding."""
        path = self._normalize_file_path(finding.path)
        location = {
            "path": finding.path,
            "start_line": finding.start_line,
            "end_line": finding.end_line,
            "start_col": finding.start_col,
            "end_col": finding.end_col,
        }
        location_str = json.dumps(location, sort_keys=True)

        evidence_hash = hashlib.sha256(
            (finding.extra.get("message", "") + finding.code_snippet).encode()
        ).hexdigest()

        fingerprint_data = {
            "version": "v1",
            "rule_id": rule_id,
            "normalized_path": path,
            "location": location_str,
            "evidence_hash": evidence_hash,
            "severity": finding.extra.get("severity", "UNKNOWN"),
        }

        fingerprint_json = json.dumps(fingerprint_data, sort_keys=True)
        return hashlib.sha256(fingerprint_json.encode()).hexdigest()

    async def run_post_patch_scan(
        self,
        verification_job: VerificationJob,
        asset_id: UUID,
        target_path: str,
    ) -> List[SemgrepFinding]:
        """Run semgrep scan on post-patch code."""
        scan_config = {
            "config": "auto",
            "target": target_path,
            "timeout": 300,
        }

        result = await self.semgrep_runner.run_scan(
            target_path=target_path,
            config="auto",
            timeout=300,
        )

        if not result.success:
            raise RuntimeError(f"Post-patch scan failed: {result.error}")

        return result.findings

    def _find_matching_post_patch_finding(
        self,
        baseline_fingerprint: str,
        baseline_rule_id: str,
        baseline_normalized_path: str,
        post_patch_findings: List[SemgrepFinding],
    ) -> Tuple[Optional[SemgrepFinding], Optional[str]]:
        """Find matching post-patch finding for baseline finding."""
        for post_finding in post_patch_findings:
            post_fingerprint = self._compute_semgrep_finding_fingerprint(
                post_finding,
                post_finding.rule_id,
            )

            if post_fingerprint == baseline_fingerprint:
                return post_finding, post_fingerprint

        for post_finding in post_patch_findings:
            if post_finding.rule_id == baseline_rule_id:
                post_path = self._normalize_file_path(post_finding.path)
                if post_path == baseline_normalized_path:
                    post_fingerprint = self._compute_semgrep_finding_fingerprint(
                        post_finding,
                        post_finding.rule_id,
                    )
                    return post_finding, post_fingerprint

        for post_finding in post_patch_findings:
            if post_finding.rule_id == baseline_rule_id:
                post_fingerprint = self._compute_semgrep_finding_fingerprint(
                    post_finding,
                    post_finding.rule_id,
                )
                return post_finding, post_fingerprint

        return None, None

    async def compare_evidence(
        self,
        verification_job: VerificationJob,
        baseline: VerificationBaseline,
        post_patch_findings: List[SemgrepFinding],
    ) -> List[EvidenceComparison]:
        """Compare baseline evidence with post-patch scan results."""
        comparisons = []

        baseline_fingerprint = baseline.finding_fingerprint
        baseline_rule_ids = baseline.rule_ids
        baseline_rule_id = baseline_rule_ids[0] if baseline_rule_ids else ""

        baseline_location = baseline.original_finding_snapshot.get("location", {})
        baseline_path = self._normalize_file_path(baseline_location.get("path", ""))

        post_finding, post_fingerprint = self._find_matching_post_patch_finding(
            baseline_fingerprint,
            baseline_rule_id,
            baseline_path,
            post_patch_findings,
        )

        baseline_evidence_hash = baseline.evidence_hashes[0] if baseline.evidence_hashes else ""

        if post_finding:
            post_evidence_hash = hashlib.sha256(
                (post_finding.extra.get("message", "") + post_finding.code_snippet).encode()
            ).hexdigest()

            post_location = {
                "path": post_finding.path,
                "start_line": post_finding.start_line,
                "end_line": post_finding.end_line,
                "start_col": post_finding.start_col,
                "end_col": post_finding.end_col,
            }

            if post_fingerprint == baseline_fingerprint:
                category = ComparisonCategory.NO_LONGER_DETECTED
                match_confidence = 1.0
                match_rationale = "Exact fingerprint match - finding no longer detected"
            elif post_finding.path == baseline_location.get("path"):
                category = ComparisonCategory.MODIFIED_OR_MOVED
                match_confidence = 0.7
                match_rationale = f"Same rule and file, but fingerprint differs (moved or modified)"
            else:
                category = ComparisonCategory.POSSIBLE_REGRESSION
                match_confidence = 0.5
                match_rationale = f"Same rule ID but different file - possible regression or new finding"

            comparison = EvidenceComparison(
                verification_job_id=verification_job.id,
                workspace_id=verification_job.workspace_id,
                baseline_finding_id=baseline.finding_id,
                post_patch_finding_id=None,
                baseline_fingerprint=baseline_fingerprint,
                post_patch_fingerprint=post_fingerprint,
                scanner_rule_id=baseline_rule_id,
                normalized_file_path=baseline_path,
                baseline_location=baseline_location,
                post_patch_location=post_location,
                baseline_evidence_hash=baseline_evidence_hash,
                post_patch_evidence_hash=post_evidence_hash,
                category=category,
                match_confidence=match_confidence,
                match_rationale=match_rationale,
                relationship_to_original="same_rule" if post_finding.rule_id == baseline_rule_id else "different_rule",
            )
        else:
            comparison = EvidenceComparison(
                verification_job_id=verification_job.id,
                workspace_id=verification_job.workspace_id,
                baseline_finding_id=baseline.finding_id,
                post_patch_finding_id=None,
                baseline_fingerprint=baseline_fingerprint,
                post_patch_fingerprint=None,
                scanner_rule_id=baseline_rule_id,
                normalized_file_path=baseline_path,
                baseline_location=baseline_location,
                post_patch_location=None,
                baseline_evidence_hash=baseline_evidence_hash,
                post_patch_evidence_hash=None,
                category=ComparisonCategory.NO_LONGER_DETECTED,
                match_confidence=1.0,
                match_rationale="No matching finding found in post-patch scan",
                relationship_to_original="resolved",
            )

        comparisons.append(comparison)

        for post_finding in post_patch_findings:
            post_fingerprint = self._compute_semgrep_finding_fingerprint(
                post_finding,
                post_finding.rule_id,
            )

            if post_fingerprint == baseline_fingerprint:
                continue

            post_path = self._normalize_file_path(post_finding.path)

            if post_finding.rule_id == baseline_rule_id:
                category = ComparisonCategory.NEW_FINDING
                match_rationale = f"New finding with same rule ID in different location"
                relationship = "same_rule_new_location"
            else:
                category = ComparisonCategory.NEW_FINDING
                match_rationale = f"New finding with different rule ID"
                relationship = "different_rule"

            comparison = EvidenceComparison(
                verification_job_id=verification_job.id,
                workspace_id=verification_job.workspace_id,
                baseline_finding_id=None,
                post_patch_finding_id=None,
                baseline_fingerprint="",
                post_patch_fingerprint=post_fingerprint,
                scanner_rule_id=post_finding.rule_id,
                normalized_file_path=post_path,
                baseline_location=None,
                post_patch_location={
                    "path": post_finding.path,
                    "start_line": post_finding.start_line,
                    "end_line": post_finding.end_line,
                    "start_col": post_finding.start_col,
                    "end_col": post_finding.end_col,
                },
                baseline_evidence_hash="",
                post_patch_evidence_hash=hashlib.sha256(
                    (post_finding.extra.get("message", "") + post_finding.code_snippet).encode()
                ).hexdigest(),
                category=category,
                match_confidence=None,
                match_rationale=match_rationale,
                relationship_to_original=relationship,
            )
            comparisons.append(comparison)

        for comp in comparisons:
            self.db.add(comp)

        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=verification_job.workspace_id,
            user_id=verification_job.requested_by,
            action="verification.evidence_compared",
            resource_type="verification_job",
            resource_id=verification_job.id,
            details={
                "comparisons_count": len(comparisons),
                "categories": [c.category.value for c in comparisons],
            },
        )

        return comparisons

    async def get_comparisons(self, verification_job_id: UUID) -> List[EvidenceComparison]:
        """Get all comparisons for a verification job."""
        result = await self.db.execute(
            select(EvidenceComparison).where(
                EvidenceComparison.verification_job_id == verification_job_id
            )
        )
        return list(result.scalars().all())

    def determine_overall_evidence_outcome(
        self,
        comparisons: List[EvidenceComparison],
    ) -> CheckStatus:
        """Determine overall evidence comparison outcome."""
        if not comparisons:
            return CheckStatus.BLOCKED

        has_still_present = any(
            c.category == ComparisonCategory.STILL_PRESENT for c in comparisons
        )
        has_no_longer_detected = any(
            c.category == ComparisonCategory.NO_LONGER_DETECTED for c in comparisons
        )
        has_modified = any(
            c.category == ComparisonCategory.MODIFIED_OR_MOVED for c in comparisons
        )
        has_possible_regression = any(
            c.category == ComparisonCategory.POSSIBLE_REGRESSION for c in comparisons
        )
        has_new_findings = any(
            c.category == ComparisonCategory.NEW_FINDING for c in comparisons
        )

        if has_still_present:
            return CheckStatus.FAILED

        if has_no_longer_detected and not has_modified and not has_possible_regression and not has_new_findings:
            return CheckStatus.PASSED

        if has_modified or has_possible_regression:
            return CheckStatus.FAILED

        if has_new_findings:
            return CheckStatus.FAILED

        return CheckStatus.INCONCLUSIVE
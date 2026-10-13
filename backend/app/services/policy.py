from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    VerificationJob,
    VerificationPolicy,
    VerificationBaseline,
    VerificationCheck,
    EvidenceComparison,
    VerificationStatus,
    VerificationOutcome,
    CheckStatus,
    CheckType,
    ComparisonCategory,
)
from app.security.audit import audit_log


class PolicyVersion(str, Enum):
    V1 = "verification-policy-v1"


DEFAULT_POLICY_CONFIG = {
    "version": PolicyVersion.V1.value,
    "rules": {
        "baseline_validity": {
            "required": True,
            "description": "Baseline must be valid and complete",
        },
        "scanner_execution": {
            "required": True,
            "description": "Scanner must execute successfully",
            "allow_blocked": False,
        },
        "original_vulnerability": {
            "required": True,
            "description": "Original vulnerability must not be detected",
            "required_outcome": "PASSED",
        },
        "evidence_comparison": {
            "required": True,
            "description": "Evidence comparison must pass",
            "required_outcome": "PASSED",
        },
        "regression_analysis": {
            "required": False,
            "description": "Regression tests must pass if configured",
            "required_outcome": "PASSED",
            "allow_skipped": True,
        },
        "test_execution": {
            "required": False,
            "description": "Test execution must pass if configured",
            "required_outcome": "PASSED",
            "allow_skipped": True,
        },
    },
    "outcome_mapping": {
        "all_passed": "VERIFIED_CANDIDATE",
        "any_failed": "FAILED",
        "any_blocked": "BLOCKED",
        "inconclusive": "INCONCLUSIVE",
    },
}


class VerificationPolicyEngine:
    """Engine for evaluating verification jobs against policy."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_policy(self) -> Optional[VerificationPolicy]:
        """Get the active verification policy."""
        result = await self.db.execute(
            select(VerificationPolicy).where(VerificationPolicy.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_policy(self, version: str) -> Optional[VerificationPolicy]:
        """Get policy by version."""
        result = await self.db.execute(
            select(VerificationPolicy).where(VerificationPolicy.version == version)
        )
        return result.scalar_one_or_none()

    async def create_default_policy(self, creator_id: UUID) -> VerificationPolicy:
        """Create default policy if none exists."""
        existing = await self.get_active_policy()
        if existing:
            return existing

        policy = VerificationPolicy(
            version=PolicyVersion.V1.value,
            name="Default Verification Policy v1",
            description="Default deterministic verification policy",
            policy_config=DEFAULT_POLICY_CONFIG,
            is_active=True,
            created_by=creator_id,
        )
        self.db.add(policy)
        await self.db.flush()
        return policy

    async def evaluate_job(
        self,
        verification_job: VerificationJob,
    ) -> VerificationOutcome:
        """Evaluate verification job against policy."""
        policy = await self.get_policy(verification_job.policy_version)
        if not policy:
            policy = await self.get_active_policy()
        if not policy:
            raise ValueError(f"No policy found for version {verification_job.policy_version}")

        config = policy.policy_config
        rules = config.get("rules", {})

        baseline = await self._get_baseline(verification_job.id)
        checks = await self._get_checks(verification_job.id)
        comparisons = await self._get_comparisons(verification_job.id)

        check_map = {c.check_type: c for c in checks}

        results = {
            "baseline_valid": False,
            "scanner_execution": None,
            "original_vulnerability": None,
            "evidence_comparison": None,
            "regression_analysis": None,
            "test_execution": None,
        }

        baseline_rule = rules.get("baseline_validity", {})
        if baseline_rule.get("required", True):
            baseline_validation = await self._validate_baseline(baseline)
            results["baseline_valid"] = baseline_validation["valid"]
            if not baseline_validation["valid"]:
                return VerificationOutcome.BLOCKED

        scanner_rule = rules.get("scanner_execution", {})
        if scanner_rule.get("required", True):
            scanner_check = check_map.get(CheckType.SCANNER_EXECUTION)
            if scanner_check:
                results["scanner_execution"] = scanner_check.status
                if scanner_check.status == CheckStatus.BLOCKED and not scanner_rule.get("allow_blocked", False):
                    return VerificationOutcome.BLOCKED
                if scanner_check.status in (CheckStatus.FAILED, CheckStatus.ERROR):
                    return VerificationOutcome.FAILED
            else:
                return VerificationOutcome.BLOCKED

        orig_rule = rules.get("original_vulnerability", {})
        if orig_rule.get("required", True):
            orig_check = check_map.get(CheckType.ORIGINAL_VULNERABILITY)
            if orig_check:
                results["original_vulnerability"] = orig_check.status
                required_outcome = orig_rule.get("required_outcome", "PASSED")
                if orig_check.status != CheckStatus(required_outcome):
                    return VerificationOutcome.FAILED
            else:
                return VerificationOutcome.BLOCKED

        evidence_rule = rules.get("evidence_comparison", {})
        if evidence_rule.get("required", True):
            evidence_check = check_map.get(CheckType.EVIDENCE_COMPARISON)
            if evidence_check:
                results["evidence_comparison"] = evidence_check.status
                required_outcome = evidence_rule.get("required_outcome", "PASSED")
                if evidence_check.status != CheckStatus(required_outcome):
                    return VerificationOutcome.FAILED
            else:
                return VerificationOutcome.BLOCKED

        regression_rule = rules.get("regression_analysis", {})
        if regression_rule.get("required", False):
            regression_check = check_map.get(CheckType.REGRESSION_ANALYSIS)
            if regression_check:
                results["regression_analysis"] = regression_check.status
                required_outcome = regression_rule.get("required_outcome", "PASSED")
                if regression_check.status != CheckStatus(required_outcome):
                    if regression_check.status == CheckStatus.SKIPPED and regression_rule.get("allow_skipped", True):
                        pass
                    else:
                        return VerificationOutcome.FAILED

        test_rule = rules.get("test_execution", {})
        if test_rule.get("required", False):
            test_check = check_map.get(CheckType.TEST_EXECUTION)
            if test_check:
                results["test_execution"] = test_check.status
                required_outcome = test_rule.get("required_outcome", "PASSED")
                if test_check.status != CheckStatus(required_outcome):
                    if test_check.status == CheckStatus.SKIPPED and test_rule.get("allow_skipped", True):
                        pass
                    else:
                        return VerificationOutcome.FAILED

        return self._determine_outcome(results, config.get("outcome_mapping", {}))

    def _determine_outcome(
        self,
        results: Dict[str, Any],
        outcome_mapping: Dict[str, str],
    ) -> VerificationOutcome:
        """Determine overall outcome from check results."""
        check_statuses = [v for v in results.values() if v is not None]

        # Convert boolean True/False to CheckStatus equivalents
        normalized_statuses = []
        for s in check_statuses:
            if s is True:
                normalized_statuses.append(CheckStatus.PASSED)
            elif s is False:
                normalized_statuses.append(CheckStatus.FAILED)
            else:
                normalized_statuses.append(s)

        if CheckStatus.FAILED in normalized_statuses:
            return VerificationOutcome.FAILED

        if CheckStatus.ERROR in normalized_statuses:
            return VerificationOutcome.FAILED

        if CheckStatus.BLOCKED in normalized_statuses:
            return VerificationOutcome.BLOCKED

        if all(s == CheckStatus.PASSED for s in normalized_statuses):
            return VerificationOutcome.VERIFIED_CANDIDATE

        non_passed = [s for s in normalized_statuses if s != CheckStatus.PASSED]
        if any(s in (CheckStatus.FAILED, CheckStatus.ERROR) for s in non_passed):
            return VerificationOutcome.FAILED
        if any(s == CheckStatus.BLOCKED for s in non_passed):
            return VerificationOutcome.BLOCKED
        if any(s == CheckStatus.SKIPPED for s in non_passed):
            return VerificationOutcome.INCONCLUSIVE

        return VerificationOutcome.INCONCLUSIVE

    async def _get_baseline(self, verification_job_id: UUID) -> Optional[VerificationBaseline]:
        result = await self.db.execute(
            select(VerificationBaseline).where(
                VerificationBaseline.verification_job_id == verification_job_id
            )
        )
        return result.scalar_one_or_none()

    async def _get_checks(self, verification_job_id: UUID) -> List[VerificationCheck]:
        result = await self.db.execute(
            select(VerificationCheck).where(
                VerificationCheck.verification_job_id == verification_job_id
            )
        )
        return list(result.scalars().all())

    async def _get_comparisons(self, verification_job_id: UUID) -> List[EvidenceComparison]:
        result = await self.db.execute(
            select(EvidenceComparison).where(
                EvidenceComparison.verification_job_id == verification_job_id
            )
        )
        return list(result.scalars().all())

    async def _validate_baseline(self, baseline: Optional[VerificationBaseline]) -> Dict[str, Any]:
        """Validate baseline completeness."""
        if not baseline:
            return {"valid": False, "reason": "No baseline found"}

        issues = []

        if not baseline.finding_fingerprint:
            issues.append("Missing finding fingerprint")

        if not baseline.evidence_hashes:
            issues.append("Missing evidence hashes")

        if not baseline.scanner_version:
            issues.append("Missing scanner version")

        if not baseline.repository_revision:
            issues.append("Missing repository revision")

        if not baseline.original_finding_snapshot:
            issues.append("Missing original finding snapshot")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
        }

    async def create_policy(
        self,
        version: str,
        name: str,
        description: Optional[str],
        policy_config: Dict[str, Any],
        creator_id: UUID,
        is_active: bool = False,
    ) -> VerificationPolicy:
        """Create a new verification policy."""
        if is_active:
            await self.db.execute(
                select(VerificationPolicy).where(VerificationPolicy.is_active == True)
            )
            existing = await self.db.execute(
                select(VerificationPolicy).where(VerificationPolicy.is_active == True)
            )
            for p in existing.scalars().all():
                p.is_active = False

        policy = VerificationPolicy(
            version=version,
            name=name,
            description=description,
            policy_config=policy_config,
            is_active=is_active,
            created_by=creator_id,
        )
        self.db.add(policy)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=None,
            user_id=creator_id,
            action="verification.policy_created",
            resource_type="verification_policy",
            resource_id=policy.id,
            details={
                "version": version,
                "name": name,
                "is_active": is_active,
            },
        )

        return policy

    async def update_policy(
        self,
        policy_id: UUID,
        name: Optional[str] = None,
        description: Optional[str] = None,
        policy_config: Optional[Dict[str, Any]] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[VerificationPolicy]:
        """Update an existing policy."""
        policy = await self.db.get(VerificationPolicy, policy_id)
        if not policy:
            return None

        if name is not None:
            policy.name = name
        if description is not None:
            policy.description = description
        if policy_config is not None:
            policy.policy_config = policy_config
        if is_active is not None:
            if is_active:
                existing = await self.db.execute(
                    select(VerificationPolicy).where(
                        and_(VerificationPolicy.is_active == True, VerificationPolicy.id != policy_id)
                    )
                )
                for p in existing.scalars().all():
                    p.is_active = False
            policy.is_active = is_active

        policy.updated_at = datetime.utcnow()
        await self.db.flush()
        return policy
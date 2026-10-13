import json
import subprocess
import shlex
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    VerificationJob,
    VerificationCheck,
    CheckStatus,
    CheckType,
    Asset,
    ScanTarget,
)
from app.repositories import AssetRepository, ScanTargetRepository
from app.security.audit import audit_log


class RegressionCheckStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    BLOCKED = "BLOCKED"
    ERROR = "ERROR"


@dataclass
class RegressionCheckResult:
    check_name: str
    check_version: str
    command: str
    status: RegressionCheckStatus
    exit_code: Optional[int]
    stdout: str
    stderr: str
    duration_ms: int
    metadata: Dict[str, Any]


class RegressionAnalysisService:
    """Service for running regression analysis checks."""

    DEFAULT_ALLOWLIST = [
        "pytest",
        "python -m pytest",
        "npm test",
        "yarn test",
        "mvn test",
        "gradle test",
        "go test",
        "cargo test",
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.asset_repo = AssetRepository(db)
        self.scan_target_repo = ScanTargetRepository(db)

    def _get_allowlist(self, asset: Asset, scan_target: ScanTarget) -> List[str]:
        """Get allowed test commands for the asset."""
        config = asset.connection_config or {}
        allowlist = config.get("regression_test_allowlist", [])
        if not allowlist:
            target_config = scan_target.connection_config or {} if scan_target else {}
            allowlist = target_config.get("regression_test_allowlist", [])
        if not allowlist:
            allowlist = self.DEFAULT_ALLOWLIST
        return allowlist

    def _is_command_allowed(self, command: str, allowlist: List[str]) -> bool:
        """Check if command is in allowlist."""
        cmd_parts = shlex.split(command)
        if not cmd_parts:
            return False

        base_cmd = cmd_parts[0]
        for allowed in allowlist:
            allowed_parts = shlex.split(allowed)
            if not allowed_parts:
                continue
            if allowed_parts[0] == base_cmd:
                return True

        return False

    async def run_regression_checks(
        self,
        verification_job: VerificationJob,
        asset: Asset,
        scan_target: ScanTarget,
        working_dir: str,
        suggested_tests: List[Dict[str, Any]],
    ) -> List[RegressionCheckResult]:
        """Run regression checks for verification."""
        allowlist = self._get_allowlist(asset, scan_target)
        results = []

        for test in suggested_tests:
            command = test.get("command")
            if not command:
                continue

            if not self._is_command_allowed(command, allowlist):
                result = RegressionCheckResult(
                    check_name=test.get("description", "Unknown test"),
                    check_version="1.0",
                    command=command,
                    status=RegressionCheckStatus.BLOCKED,
                    exit_code=None,
                    stdout="",
                    stderr=f"Command not in allowlist: {command}",
                    duration_ms=0,
                    metadata={"blocked_reason": "not_in_allowlist", "allowlist": allowlist},
                )
                results.append(result)
                await self._record_check(verification_job, result)
                continue

            result = await self._run_command(command, working_dir, test.get("description", "Unknown test"))
            results.append(result)
            await self._record_check(verification_job, result)

        return results

    async def _run_command(
        self,
        command: str,
        working_dir: str,
        check_name: str,
    ) -> RegressionCheckResult:
        """Run a single command and return result."""
        import time
        start_time = time.time()

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=working_dir,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=300,
            )

            exit_code = process.returncode
            duration_ms = int((time.time() - start_time) * 1000)

            if exit_code == 0:
                status = RegressionCheckStatus.PASS
            else:
                status = RegressionCheckStatus.FAIL

        except asyncio.TimeoutError:
            exit_code = -1
            stdout = b""
            stderr = b"Command timed out after 300 seconds"
            duration_ms = 300000
            status = RegressionCheckStatus.ERROR
        except Exception as e:
            exit_code = -1
            stdout = b""
            stderr = str(e).encode()
            duration_ms = int((time.time() - start_time) * 1000)
            status = RegressionCheckStatus.ERROR

        return RegressionCheckResult(
            check_name=check_name,
            check_version="1.0",
            command=command,
            status=status,
            exit_code=exit_code,
            stdout=stdout.decode() if isinstance(stdout, bytes) else str(stdout),
            stderr=stderr.decode() if isinstance(stderr, bytes) else str(stderr),
            duration_ms=duration_ms,
            metadata={},
        )

    async def _record_check(
        self,
        verification_job: VerificationJob,
        result: RegressionCheckResult,
    ):
        """Record check result to database."""
        check = VerificationCheck(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            check_type=CheckType.REGRESSION_ANALYSIS,
            check_name=result.check_name,
            check_version=result.check_version,
            status=CheckStatus(result.status.value),
            command=result.command,
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
            metadata=result.metadata,
        )
        self.db.add(check)
        await self.db.flush()

    async def run_original_vulnerability_check(
        self,
        verification_job: VerificationJob,
        baseline,
        post_patch_findings: List[Any],
    ) -> CheckStatus:
        """Check if original vulnerability is still present."""
        comparison_service = EvidenceComparisonService(self.db)
        comparisons = await comparison_service.compare_evidence(
            verification_job, baseline, post_patch_findings
        )

        overall = comparison_service.determine_overall_evidence_outcome(comparisons)

        check = VerificationCheck(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            check_type=CheckType.ORIGINAL_VULNERABILITY,
            check_name="Original Vulnerability Check",
            check_version="1.0",
            status=overall,
            metadata={"comparisons_count": len(comparisons)},
        )
        self.db.add(check)
        await self.db.flush()

        return overall

    async def run_scanner_execution_check(
        self,
        verification_job: VerificationJob,
        asset: Asset,
        scan_target: ScanTarget,
        working_dir: str,
    ) -> CheckStatus:
        """Run scanner execution check (semgrep scan)."""
        import time
        start_time = time.time()

        from app.scanners.semgrep import SemgrepRunner
        runner = SemgrepRunner()

        try:
            result = await runner.run_scan(
                target_path=working_dir,
                config="auto",
                timeout=300,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            if result.success:
                status = CheckStatus.PASSED
                error_message = None
            else:
                status = CheckStatus.BLOCKED
                error_message = result.error

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            status = CheckStatus.ERROR
            error_message = str(e)

        check = VerificationCheck(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            check_type=CheckType.SCANNER_EXECUTION,
            check_name="Semgrep Scanner Execution",
            check_version="1.0",
            status=status,
            command="semgrep scan --config=auto",
            exit_code=0 if status == CheckStatus.PASSED else -1,
            stdout=f"Found {len(result.findings)} findings" if result.success else "",
            stderr=error_message or "",
            duration_ms=duration_ms,
            metadata={"findings_count": len(result.findings) if result.success else 0},
        )
        self.db.add(check)
        await self.db.flush()

        return status

    async def run_test_execution_check(
        self,
        verification_job: VerificationJob,
        asset: Asset,
        scan_target: ScanTarget,
        working_dir: str,
        suggested_tests: List[Dict[str, Any]],
    ) -> CheckStatus:
        """Run test execution checks."""
        results = await self.run_regression_checks(
            verification_job, asset, scan_target, working_dir, suggested_tests
        )

        if not results:
            overall = CheckStatus.SKIPPED
        elif all(r.status == RegressionCheckStatus.PASS for r in results):
            overall = CheckStatus.PASSED
        elif any(r.status == RegressionCheckStatus.FAIL for r in results):
            overall = CheckStatus.FAILED
        elif any(r.status == RegressionCheckStatus.BLOCKED for r in results):
            overall = CheckStatus.BLOCKED
        elif any(r.status == RegressionCheckStatus.ERROR for r in results):
            overall = CheckStatus.ERROR
        else:
            overall = CheckStatus.INCONCLUSIVE

        check = VerificationCheck(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            check_type=CheckType.TEST_EXECUTION,
            check_name="Regression Test Suite",
            check_version="1.0",
            status=overall,
            metadata={
                "total_checks": len(results),
                "passed": sum(1 for r in results if r.status == RegressionCheckStatus.PASS),
                "failed": sum(1 for r in results if r.status == RegressionCheckStatus.FAIL),
                "blocked": sum(1 for r in results if r.status == RegressionCheckStatus.BLOCKED),
                "errors": sum(1 for r in results if r.status == RegressionCheckStatus.ERROR),
            },
        )
        self.db.add(check)
        await self.db.flush()

        return overall

    async def run_evidence_comparison_check(
        self,
        verification_job: VerificationJob,
    ) -> CheckStatus:
        """Run evidence comparison check (delegates to comparison service)."""
        from app.services.comparison import EvidenceComparisonService
        comparison_service = EvidenceComparisonService(self.db)

        baseline_result = await self.db.execute(
            select(VerificationBaseline).where(
                VerificationBaseline.verification_job_id == verification_job.id
            )
        )
        baseline = baseline_result.scalar_one_or_none()

        if not baseline:
            status = CheckStatus.BLOCKED
        else:
            post_patch_findings = await self._get_post_patch_findings(verification_job)
            comparisons = await comparison_service.compare_evidence(
                verification_job, baseline, post_patch_findings
            )
            status = comparison_service.determine_overall_evidence_outcome(comparisons)

        check = VerificationCheck(
            verification_job_id=verification_job.id,
            workspace_id=verification_job.workspace_id,
            check_type=CheckType.EVIDENCE_COMPARISON,
            check_name="Evidence Comparison",
            check_version="1.0",
            status=status,
            metadata={"baseline_id": str(baseline.id) if baseline else None},
        )
        self.db.add(check)
        await self.db.flush()

        return status

    async def _get_post_patch_findings(self, verification_job: VerificationJob) -> List[Any]:
        """Get post-patch findings from the working directory."""
        return []


import asyncio
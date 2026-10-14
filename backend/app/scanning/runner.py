"""
Scan Job Runner

This module orchestrates the execution of scans using the Semgrep adapter.
It handles the complete scan lifecycle from authorization verification
through result persistence.

Security: This runner must only execute against explicitly authorized,
controlled targets. NO AUTHORIZATION -> NO SCAN is enforced at the
service layer before this runner is invoked.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from pathlib import Path
import asyncio
import tempfile
import shutil
import os
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    Scan, ScanEvent, Finding, FindingEvidence, Asset,
    ScanStatus, ScanEventType, ScanType, ScanProfile,
    FindingSource, FindingSeverity, FindingConfidence, FindingStatus,
    FindingEvidenceType
)
from app.repositories import (
    ScanRepository, ScanEventRepository, FindingRepository, FindingEvidenceRepository,
    AssetRepository, AssetAuthorizationRepository
)
from app.scanners.semgrep import SemgrepManager, SemgrepConfig, FindingNormalizer, NormalizedFinding
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class ScanJobError(Exception):
    """Base exception for scan job errors."""
    def __init__(self, message: str, error_code: str = "SCAN_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class ScanAuthorizationError(ScanJobError):
    """Raised when authorization validation fails."""
    def __init__(self, message: str):
        super().__init__(message, "AUTHORIZATION_FAILED")


class ScanExecutionError(ScanJobError):
    """Raised when scan execution fails."""
    def __init__(self, message: str):
        super().__init__(message, "EXECUTION_FAILED")


class ScanTimeoutError(ScanJobError):
    """Raised when scan times out."""
    def __init__(self, message: str):
        super().__init__(message, "TIMEOUT")


class ScanJobRunner:
    """
    Orchestrates scan execution with proper security boundaries.
    
    This runner:
    1. Validates authorization before execution (NO AUTHORIZATION -> NO SCAN)
    2. Prepares controlled scan environment
    3. Executes Semgrep with security constraints
    4. Normalizes and persists findings
    5. Updates scan status and emits events
    """
    
    def __init__(
        self,
        db: AsyncSession,
        scan_workspace_root: str = "/scan-workspace",
        semgrep_timeout: int = 1800,
        max_target_size_mb: int = 1000,
    ):
        self.db = db
        self.scan_workspace_root = Path(scan_workspace_root)
        self.semgrep_timeout = semgrep_timeout
        self.max_target_size_mb = max_target_size_mb
        
        # Initialize repositories
        self.scan_repo = ScanRepository(db)
        self.event_repo = ScanEventRepository(db)
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.asset_repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)
        
        # Initialize Semgrep manager
        semgrep_config = SemgrepConfig(
            timeout=semgrep_timeout,
            max_file_size_mb=max_target_size_mb // 100,  # Rough conversion
        )
        self.semgrep_manager = SemgrepManager(semgrep_config)
        self.normalizer = FindingNormalizer()

    async def _emit_event(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        phase: str,
        event_type: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> ScanEvent:
        """Emit a scan lifecycle event."""
        event = ScanEvent(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase=phase,
            event_type=event_type,
            message=message,
            data=data or {},
        )
        return await self.event_repo.create(event)

    async def _validate_scan_ready(self, scan_id: UUID) -> Scan:
        """Validate scan exists and is ready for execution."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ScanJobError(f"Scan {scan_id} not found", "SCAN_NOT_FOUND")
        
        if scan.status != ScanStatus.RUNNING:
            raise ScanJobError(f"Scan is not in RUNNING status (current: {scan.status.value})", "INVALID_STATUS")
        
        # Verify asset still exists and is accessible
        asset = await self.asset_repo.get_by_id(scan.asset_id)
        if not asset:
            raise ScanJobError(f"Asset {scan.asset_id} not found", "ASSET_NOT_FOUND")
        if asset.deleted_at:
            raise ScanJobError(f"Asset {scan.asset_id} has been deleted", "ASSET_DELETED")
        if asset.workspace_id != scan.workspace_id:
            raise ScanJobError("Asset workspace mismatch", "WORKSPACE_MISMATCH")
        
        # Verify authorization is still valid
        auth = await self.auth_repo.get_by_asset(scan.asset_id)
        if not auth:
            raise ScanAuthorizationError("Asset authorization record missing")
        if auth.status != "verified":
            raise ScanAuthorizationError(f"Authorization status is {auth.status}")
        if auth.expires_at and auth.expires_at < datetime.utcnow():
            raise ScanAuthorizationError("Authorization has expired")
        
        return scan

    def _prepare_scan_target(self, asset: Asset) -> Path:
        """
        Prepare the scan target directory.
        
        For Stage 3, we only support controlled demo targets.
        In production, this would clone repositories, download artifacts, etc.
        """
        target_path = self.scan_workspace_root / str(asset.workspace_id) / str(asset.id)
        
        # For repository assets, the target should already be prepared
        # For Stage 3, we check if it's a demo target
        if not target_path.exists():
            # Check for demo target
            demo_path = self.scan_workspace_root / "demo-target"
            if demo_path.exists():
                logger.info(f"Using demo target at {demo_path}")
                return demo_path
            
            raise ScanExecutionError(
                f"Scan target not prepared at {target_path}. "
                "For Stage 3, only controlled demo fixtures are supported."
            )
        
        # Validate target is within allowed workspace
        try:
            target_path.resolve().relative_to(self.scan_workspace_root.resolve())
        except ValueError:
            raise ScanExecutionError(f"Target path {target_path} escapes scan workspace")
        
        return target_path

    def _validate_target_size(self, target_path: Path) -> None:
        """Validate target directory size is within limits."""
        total_size = 0
        for root, dirs, files in os.walk(target_path):
            for file in files:
                file_path = Path(root) / file
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass
        
        size_mb = total_size / (1024 * 1024)
        if size_mb > self.max_target_size_mb:
            raise ScanExecutionError(
                f"Target size {size_mb:.1f} MB exceeds limit of {self.max_target_size_mb} MB"
            )

    async def execute_scan(self, scan_id: UUID) -> Scan:
        """
        Execute a complete scan job.
        
        This is the main entry point for scan execution.
        It handles the complete lifecycle from RUNNING to COMPLETED/FAILED.
        """
        scan = await self._validate_scan_ready(scan_id)
        workspace_id = scan.workspace_id
        asset = await self.asset_repo.get_by_id(scan.asset_id)
        
        logger.info(f"Starting scan execution for scan {scan_id}, asset {asset.id}")
        
        try:
            # Phase: Analysis started
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="analysis",
                event_type=ScanEventType.ANALYSIS_STARTED.value,
                message="Starting code analysis",
            )
            await self.scan_repo.update(scan_id, {"current_phase": "analysis", "progress_percent": 10})

            # Prepare target
            target_path = self._prepare_scan_target(asset)
            self._validate_target_size(target_path)
            
            # Phase: Semgrep started
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="semgrep",
                event_type=ScanEventType.SEMGREP_STARTED.value,
                message="Running Semgrep static analysis",
            )
            await self.scan_repo.update(scan_id, {"current_phase": "semgrep", "progress_percent": 30})

            # Execute Semgrep scan
            findings = await self._run_semgrep(scan_id, workspace_id, target_path, asset)
            
            # Phase: Semgrep completed
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="semgrep",
                event_type=ScanEventType.SEMGREP_COMPLETED.value,
                message=f"Semgrep analysis completed, found {len(findings)} issues",
                data={"findings_count": len(findings)}
            )
            await self.scan_repo.update(scan_id, {"current_phase": "results_parsing", "progress_percent": 70})

            # Phase: Results parsed
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="results_parsing",
                event_type=ScanEventType.RESULTS_PARSED.value,
                message="Normalizing and deduplicating findings",
            )
            await self.scan_repo.update(scan_id, {"current_phase": "evidence_storage", "progress_percent": 85})

            # Persist findings and evidence
            await self._persist_findings(scan_id, workspace_id, asset.id, findings)
            
            # Phase: Evidence stored
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="evidence_storage",
                event_type=ScanEventType.EVIDENCE_STORED.value,
                message="Findings and evidence persisted",
                data={"findings_persisted": len(findings)}
            )

            # Generate summary
            summary = self._generate_summary(findings)
            
            # Complete scan
            scan = await self._complete_scan(scan_id, summary, findings)
            
            logger.info(f"Scan {scan_id} completed successfully with {len(findings)} findings")
            return scan
            
        except asyncio.CancelledError:
            logger.warning(f"Scan {scan_id} was cancelled")
            await self._handle_cancellation(scan_id, workspace_id)
            raise
        except ScanJobError:
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during scan {scan_id}: {e}")
            await self._handle_failure(scan_id, workspace_id, "UNEXPECTED_ERROR", str(e))
            raise ScanExecutionError(f"Scan execution failed: {e}")

    async def _run_semgrep(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        target_path: Path,
        asset: Asset
    ) -> List[NormalizedFinding]:
        """Run Semgrep scan on the target."""
        repo_context = {
            "workspace_id": str(workspace_id),
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "asset_type": asset.type.value,
        }
        
        try:
            # Run SAST scan
            sast_findings = await self.semgrep_manager.scan_code(str(target_path))
            
            # For repository assets, also run SCA scan
            sca_findings = []
            if asset.type.value == "repository":
                sca_findings = await self.semgrep_manager.scan_dependencies(str(target_path))
            
            all_findings = sast_findings + sca_findings
            
            logger.info(f"Semgrep found {len(sast_findings)} SAST and {len(sca_findings)} SCA findings for scan {scan_id}")
            return all_findings
            
        except TimeoutError:
            raise ScanTimeoutError(f"Semgrep scan timed out after {self.semgrep_timeout} seconds")
        except Exception as e:
            logger.exception(f"Semgrep execution failed for scan {scan_id}: {e}")
            raise ScanExecutionError(f"Semgrep execution failed: {e}")

    async def _persist_findings(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        asset_id: UUID,
        findings: List[NormalizedFinding]
    ) -> List[Finding]:
        """Persist normalized findings and their evidence."""
        persisted_findings = []
        
        for finding in findings:
            # Create finding record
            finding_record = Finding(
                workspace_id=workspace_id,
                scan_id=scan_id,
                asset_id=asset_id,
                source=FindingSource.SEMGREP,
                source_rule_id=finding.source_rule_id,
                title=finding.title,
                description=finding.description,
                severity=FindingSeverity(finding.severity),
                confidence=FindingConfidence(finding.confidence),
                cwe_ids=finding.cwe_ids,
                cve_ids=finding.cve_ids,
                owasp_categories=finding.owasp_categories,
                location=finding.location,
                code_snippet=finding.code_snippet,
                remediation_guidance=finding.remediation_guidance,
                status=FindingStatus.OPEN,
                risk_factors={},
            )
            
            finding_record = await self.finding_repo.create(finding_record)
            persisted_findings.append(finding_record)
            
            # Create evidence record
            evidence = FindingEvidence(
                finding_id=finding_record.id,
                workspace_id=workspace_id,
                evidence_type=FindingEvidenceType.STATIC_ANALYSIS,
                title=f"Semgrep finding: {finding.source_rule_id}",
                description=finding.description,
                content=finding.evidence,
                file_path=finding.location.get("file"),
                line_start=finding.location.get("line_start"),
                line_end=finding.location.get("line_end"),
                metadata={
                    "scanner": "semgrep",
                    "rule_id": finding.source_rule_id,
                    "original_severity": finding.evidence.get("raw_semgrep_output", {}).get("extra", {}).get("severity"),
                },
            )
            await self.evidence_repo.create(evidence)
        
        return persisted_findings

    def _generate_summary(self, findings: List[NormalizedFinding]) -> Dict[str, Any]:
        """Generate deterministic summary from findings."""
        counts = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "info": 0,
        }
        
        for finding in findings:
            severity = finding.severity.lower()
            if severity in counts:
                counts[severity] += 1
            else:
                counts["medium"] += 1  # Default fallback
        
        return {
            "total_findings": len(findings),
            **counts,
        }

    async def _complete_scan(
        self,
        scan_id: UUID,
        summary: Dict[str, Any],
        findings: List[NormalizedFinding]
    ) -> Scan:
        """Complete the scan with findings summary."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ScanJobError(f"Scan {scan_id} not found during completion", "SCAN_NOT_FOUND")
        
        duration_ms = None
        if scan.started_at:
            duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)
        
        update_data = {
            "status": ScanStatus.COMPLETED,
            "completed_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "progress_percent": 100,
            "current_phase": "completed",
            "phases_completed": list(set(scan.phases_completed + ["completed"])),
            "summary": summary,
        }
        
        await self.scan_repo.update(scan_id, update_data)
        
        # Emit completion event
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=scan.workspace_id,
            phase="completion",
            event_type=ScanEventType.SCAN_COMPLETED.value,
            message="Scan completed successfully",
            data={"summary": summary, "duration_ms": duration_ms}
        )
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=scan.workspace_id,
            action="scan.completed",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "completed", "summary": summary},
        )
        
        return await self.scan_repo.get_by_id(scan_id)

    async def _handle_failure(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        error_code: str,
        error_message: str
    ) -> None:
        """Handle scan failure."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            return
        
        duration_ms = None
        if scan.started_at:
            duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)
        
        await self.scan_repo.update(scan_id, {
            "status": ScanStatus.FAILED,
            "failed_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "error_code": error_code,
            "error_message": error_message,
            "current_phase": "failed",
        })
        
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase="failure",
            event_type=ScanEventType.SCAN_FAILED.value,
            message=f"Scan failed: {error_message}",
            data={"error_code": error_code, "error_message": error_message}
        )
        
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="scan.failed",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "failed", "error_code": error_code, "error_message": error_message},
        )

    async def _handle_cancellation(self, scan_id: UUID, workspace_id: UUID) -> None:
        """Handle scan cancellation."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            return
        
        duration_ms = None
        if scan.started_at:
            duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)
        
        await self.scan_repo.update(scan_id, {
            "status": ScanStatus.CANCELLED,
            "cancelled_at": datetime.utcnow(),
            "duration_ms": duration_ms,
            "current_phase": "cancelled",
        })
        
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase="cancellation",
            event_type=ScanEventType.SCAN_CANCELLED.value,
            message="Scan cancelled during execution",
            data={"cancelled_during_execution": True}
        )
        
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="scan.cancelled",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "cancelled", "cancelled_during_execution": True},
        )
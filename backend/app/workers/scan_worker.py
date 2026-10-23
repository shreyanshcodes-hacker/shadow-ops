"""
Scan Worker - Isolated Scanner Execution

This module contains the Celery tasks for executing security scans in an
isolated worker process. The worker runs in a separate container with
strict resource limits and security constraints.

Security Model:
- Worker runs as non-root user (UID 1000)
- No network access (--network=none in container)
- Read-only root filesystem
- Dropped Linux capabilities
- CPU, memory, and process limits enforced by container runtime
- No access to host paths, Docker socket, or cloud metadata
- No application secrets (Firebase, Supabase, AI keys) in environment
- Sanitized job payload with minimal required data
"""

import asyncio
import json
import logging
import os
import signal
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.core.config import settings
from app.workers.celery_app import celery_app
from app.models import (
    Scan, ScanEvent, Finding, FindingEvidence, Asset,
    ScanStatus, ScanEventType, ScanType, ScanProfile,
    FindingSource, FindingSeverity, FindingConfidence, FindingStatus,
    FindingEvidenceType, AssetAuthorization, AuthorizationStatus
)
from app.repositories import (
    ScanRepository, ScanEventRepository, FindingRepository, FindingEvidenceRepository,
    AssetRepository, AssetAuthorizationRepository
)
from app.scanners.semgrep import SemgrepManager, SemgrepConfig, FindingNormalizer, NormalizedFinding
from app.security.audit import audit_log

logger = logging.getLogger(__name__)

# Worker configuration
WORKER_SCAN_TIMEOUT = int(os.getenv("WORKER_SCAN_TIMEOUT", "1800"))  # 30 minutes
WORKER_MAX_TARGET_SIZE_MB = int(os.getenv("WORKER_MAX_TARGET_SIZE_MB", "1000"))
WORKER_MAX_FILE_SIZE_MB = int(os.getenv("WORKER_MAX_FILE_SIZE_MB", "10"))
WORKER_SEMGREP_TIMEOUT = int(os.getenv("WORKER_SEMGREP_TIMEOUT", "1800"))

# Semgrep configuration for worker (restricted)
WORKER_SEMGREP_CONFIG = SemgrepConfig(
    rulesets=["p/security-audit", "p/secrets", "p/owasp-top-ten"],
    custom_rules=[],
    timeout=WORKER_SEMGREP_TIMEOUT,
    max_file_size_mb=WORKER_MAX_FILE_SIZE_MB,
    excluded_paths=[
        "**/node_modules/**",
        "**/.git/**",
        "**/vendor/**",
        "**/dist/**",
        "**/build/**",
        "**/__pycache__/**",
        "**/*.min.js",
    ],
)

# Result payload size limit (10 MB)
MAX_RESULT_PAYLOAD_BYTES = 10 * 1024 * 1024


class ScanWorkerError(Exception):
    """Base exception for scan worker errors."""
    def __init__(self, message: str, error_code: str = "WORKER_ERROR", details: Dict = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class ScanAuthorizationError(ScanWorkerError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "AUTHORIZATION_FAILED", details)


class ScanExecutionError(ScanWorkerError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "EXECUTION_FAILED", details)


class ScanTimeoutError(ScanWorkerError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "TIMEOUT", details)


class ScanValidationError(ScanWorkerError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(message, "VALIDATION_FAILED", details)


async def get_worker_db_session() -> AsyncSession:
    """Create a database session for the worker.
    
    The worker uses its own database connection pool, separate from the API.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
    async_session_maker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    return async_session_maker()


class ScanWorkerRunner:
    """
    Isolated scan execution runner for worker environment.
    
    This runner is designed to run in an isolated container with:
    - No network access
    - Read-only root filesystem
    - Resource limits (CPU, memory, processes)
    - No access to host paths or secrets
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.scan_workspace_root = Path(settings.SCAN_WORKSPACE_ROOT)
        self.semgrep_timeout = WORKER_SEMGREP_TIMEOUT
        self.max_target_size_mb = WORKER_MAX_TARGET_SIZE_MB
        
        # Initialize repositories
        self.scan_repo = ScanRepository(db)
        self.event_repo = ScanEventRepository(db)
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.asset_repo = AssetRepository(db)
        self.auth_repo = AssetAuthorizationRepository(db)
        
        # Initialize Semgrep manager with restricted config
        self.semgrep_manager = SemgrepManager(WORKER_SEMGREP_CONFIG)
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

    async def _validate_job_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize job payload from queue.
        
        Only allow expected fields, reject any unexpected data.
        """
        required_fields = ["scan_id", "workspace_id", "asset_id", "idempotency_key"]
        for field in required_fields:
            if field not in payload:
                raise ScanValidationError(f"Missing required field: {field}")
        
        # Validate UUIDs
        try:
            scan_id = UUID(payload["scan_id"])
            workspace_id = UUID(payload["workspace_id"])
            asset_id = UUID(payload["asset_id"])
        except ValueError as e:
            raise ScanValidationError(f"Invalid UUID in payload: {e}")
        
        # Validate idempotency key format
        idempotency_key = payload["idempotency_key"]
        if not isinstance(idempotency_key, str) or len(idempotency_key) < 16:
            raise ScanValidationError("Invalid idempotency key")
        
        # Only allow expected optional fields
        allowed_optional = {"scan_profile", "scan_type", "priority"}
        for key in payload:
            if key not in required_fields and key not in allowed_optional:
                logger.warning(f"Ignoring unexpected field in job payload: {key}")
        
        return {
            "scan_id": scan_id,
            "workspace_id": workspace_id,
            "asset_id": asset_id,
            "idempotency_key": idempotency_key,
            "scan_profile": payload.get("scan_profile", "CODE_SECURITY"),
            "scan_type": payload.get("scan_type", "code"),
        }

    async def _check_idempotency(self, idempotency_key: str) -> Optional[Scan]:
        """Check if job was already processed (idempotency)."""
        # Check for existing scan with this idempotency key in recent scans
        # This is a simplified check; production would use a dedicated idempotency table
        result = await self.db.execute(
            select(Scan).where(Scan.scan_config.op("->>")("idempotency_key") == idempotency_key)
        )
        existing = result.scalar_one_or_none()
        if existing:
            logger.info(f"Idempotent job detected: {idempotency_key}, returning existing scan {existing.id}")
        return existing

    async def _validate_scan_ready(self, scan_id: UUID, validated_payload: Dict) -> Scan:
        """Validate scan exists and matches the job payload."""
        scan = await self.scan_repo.get_by_id(scan_id)
        if not scan:
            raise ScanWorkerError(f"Scan {scan_id} not found", "SCAN_NOT_FOUND")
        
        # Verify scan matches job payload
        if scan.workspace_id != validated_payload["workspace_id"]:
            raise ScanWorkerError("Scan workspace mismatch", "WORKSPACE_MISMATCH")
        if scan.asset_id != validated_payload["asset_id"]:
            raise ScanWorkerError("Scan asset mismatch", "ASSET_MISMATCH")
        if scan.status != ScanStatus.QUEUED:
            raise ScanWorkerError(f"Scan is not in QUEUED status (current: {scan.status.value})", "INVALID_STATUS")
        
        # Verify asset still exists and is accessible
        asset = await self.asset_repo.get_by_id(scan.asset_id)
        if not asset:
            raise ScanWorkerError(f"Asset {scan.asset_id} not found", "ASSET_NOT_FOUND")
        if asset.deleted_at:
            raise ScanWorkerError(f"Asset {scan.asset_id} has been deleted", "ASSET_DELETED")
        if asset.workspace_id != scan.workspace_id:
            raise ScanWorkerError("Asset workspace mismatch", "WORKSPACE_MISMATCH")
        
        # Verify authorization is still valid
        auth = await self.auth_repo.get_by_asset(scan.asset_id)
        if not auth:
            raise ScanAuthorizationError("Asset authorization record missing")
        if auth.status != AuthorizationStatus.VERIFIED:
            raise ScanAuthorizationError(f"Authorization status is {auth.status.value}")
        if auth.expires_at and auth.expires_at < datetime.utcnow():
            raise ScanAuthorizationError("Authorization has expired")
        
        return scan

    def _prepare_scan_target(self, asset: Asset) -> Path:
        """Prepare and validate the scan target directory.
        
        Security controls:
        - Path must be within scan workspace root
        - Symlinks resolved and validated
        - No host path escape possible
        """
        target_path = self.scan_workspace_root / str(asset.workspace_id) / str(asset.id)
        
        # Verify target exists
        if not target_path.exists():
            # Check for demo target (development only)
            if not settings.DEBUG:
                raise ScanExecutionError(
                    f"Scan target not prepared at {target_path}. "
                    "Production targets must be pre-staged."
                )
            demo_path = self.scan_workspace_root / "demo-target"
            if demo_path.exists():
                logger.info(f"Using demo target at {demo_path}")
                return demo_path
            raise ScanExecutionError(
                f"Scan target not prepared at {target_path}"
            )
        
        # Resolve symlinks and validate path containment
        try:
            resolved_target = target_path.resolve(strict=True)
            resolved_root = self.scan_workspace_root.resolve(strict=True)
            resolved_target.relative_to(resolved_root)
        except (ValueError, OSError) as e:
            raise ScanExecutionError(f"Target path validation failed: {e}")
        
        return resolved_target

    def _validate_target_size(self, target_path: Path) -> None:
        """Validate target directory size is within limits."""
        total_size = 0
        file_count = 0
        for root, dirs, files in os.walk(target_path):
            for file in files:
                file_path = Path(root) / file
                try:
                    total_size += file_path.stat().st_size
                    file_count += 1
                    if file_count > 100000:  # Hard limit on file count
                        raise ScanExecutionError("Target contains too many files")
                except OSError:
                    pass
        
        size_mb = total_size / (1024 * 1024)
        if size_mb > self.max_target_size_mb:
            raise ScanExecutionError(
                f"Target size {size_mb:.1f} MB exceeds limit of {self.max_target_size_mb} MB"
            )

    async def _run_semgrep(
        self,
        scan_id: UUID,
        workspace_id: UUID,
        target_path: Path,
        asset: Asset
    ) -> List[NormalizedFinding]:
        """Run Semgrep scan with security controls.
        
        The worker runs semgrep as a subprocess with:
        - Timeout enforcement
        - Output size limits
        - No network access (enforced by container)
        - Restricted filesystem (enforced by container)
        """
        repo_context = {
            "workspace_id": str(workspace_id),
            "asset_id": str(asset.id),
            "asset_name": asset.name,
            "asset_type": asset.type.value,
        }
        
        try:
            # Run SAST scan
            sast_findings = await asyncio.wait_for(
                self.semgrep_manager.scan_code(str(target_path)),
                timeout=self.semgrep_timeout
            )
            
            # For repository assets, also run SCA scan
            sca_findings = []
            if asset.type.value == "repository":
                sca_findings = await asyncio.wait_for(
                    self.semgrep_manager.scan_dependencies(str(target_path)),
                    timeout=self.semgrep_timeout
                )
            
            all_findings = sast_findings + sca_findings
            
            logger.info(f"Semgrep found {len(sast_findings)} SAST and {len(sca_findings)} SCA findings for scan {scan_id}")
            return all_findings
            
        except asyncio.TimeoutError:
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

    def _sanitize_result_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize result payload before returning to API.
        
        Removes sensitive data, limits size, ensures serializable.
        """
        # Remove any raw scanner output that might contain secrets
        sanitized = dict(payload)
        
        # Limit finding evidence size
        if "findings" in sanitized:
            for finding in sanitized["findings"]:
                if "evidence" in finding and isinstance(finding["evidence"], dict):
                    # Keep only safe fields
                    safe_evidence = {}
                    for k, v in finding["evidence"].items():
                        if k in ("rule_id", "scanner", "original_severity"):
                            safe_evidence[k] = v
                    finding["evidence"] = safe_evidence
        
        # Truncate large fields
        json_str = json.dumps(sanitized, default=str)
        if len(json_str.encode()) > MAX_RESULT_PAYLOAD_BYTES:
            # Truncate findings array if needed
            if "findings" in sanitized:
                sanitized["findings"] = sanitized["findings"][:100]
                sanitized["truncated"] = True
        
        return sanitized

    async def execute_scan_job(self, job_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a scan job from the queue.
        
        This is the main entry point for the worker task.
        Returns sanitized result payload for the API.
        """
        # Validate and sanitize job payload
        validated_payload = await self._validate_job_payload(job_payload)
        scan_id = validated_payload["scan_id"]
        workspace_id = validated_payload["workspace_id"]
        asset_id = validated_payload["asset_id"]
        idempotency_key = validated_payload["idempotency_key"]
        
        logger.info(f"Starting scan job {scan_id} (idempotency: {idempotency_key[:16]}...)")
        
        # Check idempotency
        existing = await self._check_idempotency(idempotency_key)
        if existing:
            return {
                "scan_id": str(existing.id),
                "status": existing.status.value,
                "idempotent": True,
                "message": "Job already processed"
            }
        
        try:
            # Validate scan is ready
            scan = await self._validate_scan_ready(scan_id, validated_payload)
            asset = await self.asset_repo.get_by_id(asset_id)
            
            # Transition to RUNNING
            await self.scan_repo.update(scan_id, {
                "status": ScanStatus.RUNNING,
                "started_at": datetime.utcnow(),
                "current_phase": "initialization",
                "progress_percent": 5,
            })
            
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="execution",
                event_type=ScanEventType.SCAN_STARTED.value,
                message="Scan execution started in isolated worker",
            )
            
            # Prepare target
            await self.scan_repo.update(scan_id, {"current_phase": "target_preparation", "progress_percent": 10})
            target_path = self._prepare_scan_target(asset)
            self._validate_target_size(target_path)
            
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="semgrep",
                event_type=ScanEventType.SEMGREP_STARTED.value,
                message="Running Semgrep static analysis in isolated worker",
            )
            await self.scan_repo.update(scan_id, {"current_phase": "semgrep", "progress_percent": 30})
            
            # Execute Semgrep scan
            findings = await self._run_semgrep(scan_id, workspace_id, target_path, asset)
            
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="semgrep",
                event_type=ScanEventType.SEMGREP_COMPLETED.value,
                message=f"Semgrep analysis completed, found {len(findings)} issues",
                data={"findings_count": len(findings)}
            )
            await self.scan_repo.update(scan_id, {"current_phase": "results_parsing", "progress_percent": 70})
            
            # Persist findings
            await self.scan_repo.update(scan_id, {"current_phase": "evidence_storage", "progress_percent": 85})
            await self._persist_findings(scan_id, workspace_id, asset_id, findings)
            
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
            duration_ms = None
            if scan.started_at:
                duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)
            
            await self.scan_repo.update(scan_id, {
                "status": ScanStatus.COMPLETED,
                "completed_at": datetime.utcnow(),
                "duration_ms": duration_ms,
                "progress_percent": 100,
                "current_phase": "completed",
                "phases_completed": list(set(scan.phases_completed + ["completed"])),
                "summary": summary,
            })
            
            await self._emit_event(
                scan_id=scan_id,
                workspace_id=workspace_id,
                phase="completion",
                event_type=ScanEventType.SCAN_COMPLETED.value,
                message="Scan completed successfully",
                data={"summary": summary, "duration_ms": duration_ms}
            )
            
            # Audit log
            await audit_log(
                db=self.db,
                workspace_id=workspace_id,
                action="scan.completed",
                resource_type="scan",
                resource_id=scan_id,
                new_state={"status": "completed", "summary": summary},
            )
            
            # Return sanitized result
            result = {
                "scan_id": str(scan_id),
                "status": ScanStatus.COMPLETED.value,
                "summary": summary,
                "duration_ms": duration_ms,
                "findings_count": len(findings),
            }
            return self._sanitize_result_payload(result)
            
        except ScanWorkerError:
            # Re-raise known worker errors
            raise
        except SoftTimeLimitExceeded:
            logger.warning(f"Scan {scan_id} exceeded soft time limit")
            await self._handle_timeout(scan_id, workspace_id)
            raise ScanTimeoutError("Scan exceeded time limit")
        except asyncio.CancelledError:
            logger.warning(f"Scan {scan_id} was cancelled")
            await self._handle_cancellation(scan_id, workspace_id)
            raise
        except Exception as e:
            logger.exception(f"Unexpected error during scan {scan_id}: {e}")
            await self._handle_failure(scan_id, workspace_id, "UNEXPECTED_ERROR", str(e))
            raise ScanExecutionError(f"Scan execution failed: {e}")

    async def _handle_failure(self, scan_id: UUID, workspace_id: UUID, error_code: str, error_message: str) -> None:
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
            "error_message": error_message[:1000],  # Truncate long messages
            "current_phase": "failed",
        })
        
        await self._emit_event(
            scan_id=scan_id,
            workspace_id=workspace_id,
            phase="failure",
            event_type=ScanEventType.SCAN_FAILED.value,
            message=f"Scan failed: {error_message}",
            data={"error_code": error_code, "error_message": error_message[:500]}
        )
        
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="scan.failed",
            resource_type="scan",
            resource_id=scan_id,
            new_state={"status": "failed", "error_code": error_code, "error_message": error_message[:500]},
        )

    async def _handle_timeout(self, scan_id: UUID, workspace_id: UUID) -> None:
        """Handle scan timeout."""
        await self._handle_failure(scan_id, workspace_id, "TIMEOUT", "Scan exceeded time limit")

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


# Celery Task Definition
class ScanWorkerTask(Task):
    """Base task class for scan worker with proper error handling."""
    
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 300
    retry_jitter = True
    max_retries = 2  # Limited retries for scan jobs
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(f"Scan task {task_id} failed: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry."""
        logger.warning(f"Scan task {task_id} retrying: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)


@celery_app.task(
    bind=True,
    base=ScanWorkerTask,
    name="app.workers.scan_worker.execute_scan_job",
    queue="scans",
    time_limit=1860,  # 31 minutes hard limit
    soft_time_limit=1800,  # 30 minutes soft limit
)
async def execute_scan_job(self, job_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute a scan job in the isolated worker.
    
    Job payload must contain:
    - scan_id: UUID of the scan record
    - workspace_id: UUID of the workspace
    - asset_id: UUID of the asset to scan
    - idempotency_key: Unique key for idempotent execution
    - scan_profile: (optional) Scan profile to use
    - scan_type: (optional) Scan type
    
    Returns sanitized result payload for API consumption.
    """
    # Create database session for this task
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=1,
        max_overflow=0,
        pool_pre_ping=True,
    )
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        try:
            runner = ScanWorkerRunner(db)
            result = await runner.execute_scan_job(job_payload)
            await db.commit()
            return result
        except Exception:
            await db.rollback()
            raise
        finally:
            await engine.dispose()


@celery_app.task(
    bind=True,
    name="app.workers.scan_worker.cancel_scan_job",
    queue="scans",
)
async def cancel_scan_job(self, scan_id: str) -> Dict[str, Any]:
    """Cancel a running scan job.
    
    This task attempts to cancel a scan by:
    1. Finding the scan record
    2. If RUNNING, sending cancellation signal
    3. Updating status to CANCELLED
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=1,
        max_overflow=0,
    )
    async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_maker() as db:
        try:
            scan_repo = ScanRepository(db)
            event_repo = ScanEventRepository(db)
            
            scan_uuid = UUID(scan_id)
            scan = await scan_repo.get_by_id(scan_uuid)
            
            if not scan:
                return {"status": "not_found", "scan_id": scan_id}
            
            if scan.status not in (ScanStatus.QUEUED, ScanStatus.RUNNING):
                return {"status": "invalid_state", "scan_id": scan_id, "current_status": scan.status.value}
            
            # Update status
            duration_ms = None
            if scan.started_at:
                duration_ms = int((datetime.utcnow() - scan.started_at).total_seconds() * 1000)
            
            await scan_repo.update(scan_uuid, {
                "status": ScanStatus.CANCELLED,
                "cancelled_at": datetime.utcnow(),
                "duration_ms": duration_ms,
                "current_phase": "cancelled",
            })
            
            # Emit cancellation event
            event = ScanEvent(
                scan_id=scan_uuid,
                workspace_id=scan.workspace_id,
                phase="cancellation",
                event_type=ScanEventType.SCAN_CANCELLED.value,
                message="Scan cancelled via worker task",
                data={"cancelled_via": "worker_task"},
            )
            await event_repo.create(event)
            
            await db.commit()
            
            return {"status": "cancelled", "scan_id": scan_id}
            
        except Exception as e:
            await db.rollback()
            logger.exception(f"Failed to cancel scan {scan_id}: {e}")
            return {"status": "error", "scan_id": scan_id, "error": str(e)}
        finally:
            await engine.dispose()
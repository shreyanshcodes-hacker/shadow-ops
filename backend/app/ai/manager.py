import hashlib
import json
import logging
from typing import List, Optional, Dict, Any, Set
from uuid import UUID, uuid4
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models import (
    AiRun, FindingAiAnalysis, Finding, FindingEvidence, Scan,
    AiProviderType, AiOperationType, AiRunStatus, FindingSeverity,
    Workspace, Asset
)
from app.repositories import FindingRepository, FindingEvidenceRepository, AiRunRepository, FindingAiAnalysisRepository
from app.ai.providers import get_active_provider, AIProviderError, AIProviderAuthError
from app.ai.schemas import SecurityAnalysis, ScanAnalysis
from app.ai.prompts import build_finding_analysis_prompt, SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT
from app.ai.validation import validate_security_analysis, sanitize_analysis_output
from app.ai.safety import sanitize_evidence_dict, sanitize_for_ai
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class AIManagerError(Exception):
    """Base exception for AI Manager errors."""

    def __init__(self, message: str, error_code: str = "AI_MANAGER_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AIManager:
    """
    AI Security Analyst - orchestrates AI analysis of security findings.

    Responsibilities:
    - Retrieve trusted scanner evidence from database
    - Sanitize evidence (secret redaction, size limits)
    - Build prompts with injection defenses
    - Call AI provider with structured output
    - Validate AI output against schema
    - Persist analysis results
    - Track AI runs for audit and cost control
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.ai_run_repo = AiRunRepository(db)
        self.analysis_repo = FindingAiAnalysisRepository(db)
        self.provider = get_active_provider()

    async def analyze_finding(
        self,
        finding_id: UUID,
        user_id: UUID,
        workspace_id: UUID,
        force_reanalyze: bool = False,
    ) -> FindingAiAnalysis:
        """
        Analyze a single finding with AI.

        This is the main entry point for finding analysis.
        """
        # 1. Verify access and retrieve finding
        finding = await self._get_finding_for_analysis(finding_id, workspace_id)
        if not finding:
            raise AIManagerError("Finding not found or access denied", "FINDING_NOT_FOUND")

        # 2. Retrieve and sanitize evidence
        evidence_list = await self.evidence_repo.get_by_finding(finding_id)
        evidence_data = self._prepare_evidence_for_ai(evidence_list)

        # 3. Check for duplicate analysis (same input hash) unless forced
        input_hash = self._compute_input_hash(finding, evidence_data)
        if not force_reanalyze:
            existing = await self._find_existing_analysis(finding_id, input_hash)
            if existing:
                logger.info(f"Reusing existing AI analysis for finding {finding_id}")
                return existing

        # 4. Create AI run record
        ai_run = await self._create_ai_run(
            workspace_id=workspace_id,
            scan_id=finding.scan_id,
            finding_id=finding_id,
            requested_by=user_id,
            operation=AiOperationType.FINDING_ANALYSIS,
            input_hash=input_hash,
        )

        try:
            # 5. Update run status to RUNNING
            await self._update_ai_run(ai_run.id, {"status": AiRunStatus.RUNNING, "started_at": datetime.utcnow()})

            # 6. Build prompt
            prompt = self._build_finding_prompt(finding, evidence_data)
            evidence_ids = {str(e.id) for e in evidence_list}

            # 7. Call AI provider with retries
            analysis = await self._call_provider_with_retries(prompt, evidence_ids)

            # 8. Validate and sanitize output
            analysis = sanitize_analysis_output(analysis)

            # 9. Persist analysis
            finding_analysis = await self._persist_analysis(ai_run, finding, analysis, evidence_ids)

            # 10. Update run status to COMPLETED
            await self._update_ai_run(ai_run.id, {
                "status": AiRunStatus.COMPLETED,
                "completed_at": datetime.utcnow(),
                "input_tokens": 0,  # Would come from provider metadata
                "output_tokens": 0,
                "estimated_cost_usd": 0.0,
            })

            # 11. Audit log
            await audit_log(
                db=self.db,
                workspace_id=workspace_id,
                action="ai.analysis.completed",
                resource_type="finding_ai_analysis",
                resource_id=finding_analysis.id,
                new_state={
                    "finding_id": str(finding_id),
                    "ai_run_id": str(ai_run.id),
                    "confidence": analysis.confidence,
                    "vulnerability_type": analysis.vulnerability_type.value,
                    "severity_assessment": analysis.severity_assessment.value,
                },
                user_id=user_id,
            )

            return finding_analysis

        except AIProviderAuthError as e:
            await self._handle_provider_error(ai_run, e, "AI_AUTH_ERROR")
            raise AIManagerError("AI provider authentication failed", "AI_AUTH_ERROR")
        except AIProviderError as e:
            await self._handle_provider_error(ai_run, e, e.error_code)
            raise AIManagerError(f"AI provider error: {e.message}", e.error_code)
        except Exception as e:
            logger.exception(f"Unexpected error analyzing finding {finding_id}: {e}")
            await self._handle_provider_error(ai_run, e, "UNEXPECTED_ERROR")
            raise AIManagerError(f"Analysis failed: {e}", "ANALYSIS_FAILED")

    async def _get_finding_for_analysis(
        self,
        finding_id: UUID,
        workspace_id: UUID,
    ) -> Optional[Finding]:
        """Retrieve finding and verify workspace access."""
        finding = await self.finding_repo.get_by_id(finding_id)
        if not finding:
            return None
        if finding.workspace_id != workspace_id:
            return None
        return finding

    def _prepare_evidence_for_ai(self, evidence_list: List[FindingEvidence]) -> List[Dict[str, Any]]:
        """Prepare and sanitize evidence for AI transmission."""
        evidence_data = []
        for evidence in evidence_list:
            # Sanitize content
            sanitized_content = sanitize_evidence_dict(evidence.content or {})
            sanitized_metadata = sanitize_evidence_dict(evidence.metadata or {})

            evidence_data.append({
                "evidence_id": str(evidence.id),
                "evidence_type": evidence.evidence_type.value if evidence.evidence_type else "unknown",
                "title": evidence.title,
                "description": sanitize_for_ai(evidence.description or ""),
                "content": sanitized_content,
                "file_path": evidence.file_path,
                "line_start": evidence.line_start,
                "line_end": evidence.line_end,
                "metadata": sanitized_metadata,
            })
        return evidence_data

    def _compute_input_hash(self, finding: Finding, evidence_data: List[Dict[str, Any]]) -> str:
        """Compute deterministic hash of input for deduplication."""
        content = {
            "finding_id": str(finding.id),
            "source_rule_id": finding.source_rule_id,
            "title": finding.title,
            "description": finding.description,
            "severity": finding.severity.value,
            "location": finding.location,
            "code_snippet": finding.code_snippet,
            "evidence": evidence_data,
        }
        serialized = json.dumps(content, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:32]

    async def _find_existing_analysis(
        self,
        finding_id: UUID,
        input_hash: str,
    ) -> Optional[FindingAiAnalysis]:
        """Check for existing completed analysis with same input hash."""
        result = await self.db.execute(
            select(FindingAiAnalysis)
            .join(AiRun, FindingAiAnalysis.ai_run_id == AiRun.id)
            .where(
                FindingAiAnalysis.finding_id == finding_id,
                AiRun.input_hash == input_hash,
                AiRun.status == AiRunStatus.COMPLETED,
            )
            .order_by(AiRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _create_ai_run(
        self,
        workspace_id: UUID,
        scan_id: UUID,
        finding_id: UUID,
        requested_by: UUID,
        operation: AiOperationType,
        input_hash: str,
    ) -> AiRun:
        """Create AI run record."""
        # Get prompt version from config
        from app.core.config import settings
        prompt_version = getattr(settings, 'AI_PROMPT_VERSION', 'security-finding-analysis-v1')
        
        ai_run = AiRun(
            workspace_id=workspace_id,
            scan_id=scan_id,
            finding_id=finding_id,
            requested_by=requested_by,
            provider=self.provider.provider_type,
            model=self.provider.default_model.value,
            operation=operation,
            status=AiRunStatus.QUEUED,
            prompt_version=prompt_version,
            input_hash=input_hash,
        )
        return await self.ai_run_repo.create(ai_run)

    async def _update_ai_run(self, run_id: UUID, data: Dict[str, Any]) -> None:
        """Update AI run record."""
        await self.ai_run_repo.update(run_id, data)

    def _build_finding_prompt(self, finding: Finding, evidence_data: List[Dict[str, Any]]) -> str:
        """Build the complete prompt for finding analysis."""
        # Build scanner evidence summary
        scanner_evidence = json.dumps(evidence_data, indent=2) if evidence_data else "No structured evidence available"

        # Build additional evidence
        additional_parts = []
        if finding.cwe_ids:
            additional_parts.append(f"CWE IDs: {', '.join(finding.cwe_ids)}")
        if finding.owasp_categories:
            additional_parts.append(f"OWASP Categories: {', '.join(finding.owasp_categories)}")
        if finding.remediation_guidance:
            additional_parts.append(f"Scanner Remediation Guidance: {finding.remediation_guidance}")
        additional_evidence = "\n".join(additional_parts) if additional_parts else "None"

        return build_finding_analysis_prompt(
            finding_id=str(finding.id),
            scanner=finding.source.value if finding.source else "unknown",
            rule_id=finding.source_rule_id or "unknown",
            severity=finding.severity.value,
            file_path=finding.location.get("file", "unknown") if finding.location else "unknown",
            line_start=finding.location.get("line_start", 0) if finding.location else 0,
            line_end=finding.location.get("line_end", 0) if finding.location else 0,
            cwe_ids=finding.cwe_ids or [],
            owasp_categories=finding.owasp_categories or [],
            code_snippet=finding.code_snippet or "Not available",
            scanner_evidence=scanner_evidence,
            additional_evidence=additional_evidence,
        )

    async def _call_provider_with_retries(
        self,
        prompt: str,
        evidence_ids: Set[str],
    ) -> SecurityAnalysis:
        """Call AI provider with retry logic for transient failures."""
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.provider.generate_structured(
                    prompt=prompt,
                    output_schema=SecurityAnalysis,
                    system_prompt=SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT,
                    temperature=0.1,
                )

                if not response.success:
                    # Check if validation error (non-retryable)
                    if any("validation" in err.lower() or "schema" in err.lower() for err in response.errors):
                        raise AIManagerError(f"AI output validation failed: {response.errors}", "AI_VALIDATION_ERROR")

                    # For other errors, retry
                    raise AIProviderError(f"AI provider returned error: {response.errors}", "AI_PROVIDER_ERROR")

                # Validate output against evidence IDs
                is_valid, errors = validate_security_analysis(response.data, evidence_ids)
                if not is_valid:
                    raise AIManagerError(f"AI output validation failed: {errors}", "AI_VALIDATION_ERROR")

                return response.data

            except AIProviderAuthError:
                raise  # Non-retryable
            except AIManagerError:
                raise  # Non-retryable (validation errors)
            except AIProviderError as e:
                last_error = e
                if not e.retryable or attempt == max_retries - 1:
                    raise
                logger.warning(f"AI provider error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                continue
            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                continue

        raise last_error or AIProviderError("Max retries exceeded", "MAX_RETRIES_EXCEEDED")

    async def _persist_analysis(
        self,
        ai_run: AiRun,
        finding: Finding,
        analysis: SecurityAnalysis,
        evidence_ids: Set[str],
    ) -> FindingAiAnalysis:
        """Persist the AI analysis to database."""
        finding_analysis = FindingAiAnalysis(
            finding_id=finding.id,
            ai_run_id=ai_run.id,
            workspace_id=finding.workspace_id,
            summary=analysis.summary,
            vulnerability_type=analysis.vulnerability_type.value,
            severity_assessment=analysis.severity_assessment.value,
            confidence=analysis.confidence,
            exploitability_assessment=analysis.exploitability_assessment.value,
            impact_assessment=analysis.impact_assessment,
            affected_component=analysis.affected_component,
            attack_preconditions=analysis.attack_preconditions,
            evidence_interpretation=analysis.evidence_interpretation,
            reasoning=analysis.reasoning,
            recommended_next_steps=analysis.recommended_next_steps,
            uncertainty=analysis.uncertainty,
            supporting_evidence=[ref.model_dump() for ref in analysis.supporting_evidence],
            model=self.provider.default_model.value,
            provider=self.provider.provider_type,
            prompt_version=ai_run.prompt_version,
        )
        return await self.analysis_repo.create(finding_analysis)

    async def _handle_provider_error(self, ai_run: AiRun, error: Exception, error_code: str) -> None:
        """Handle provider error by updating run status."""
        error_message = str(error)
        await self._update_ai_run(ai_run.id, {
            "status": AiRunStatus.FAILED,
            "failed_at": datetime.utcnow(),
            "error_code": error_code,
            "error_message": error_message[:1000],
        })

        await audit_log(
            db=self.db,
            workspace_id=ai_run.workspace_id,
            action="ai.analysis.failed",
            resource_type="ai_run",
            resource_id=ai_run.id,
            new_state={
                "error_code": error_code,
                "error_message": error_message[:500],
            },
        )

    async def get_finding_analysis(self, finding_id: UUID, workspace_id: UUID) -> Optional[FindingAiAnalysis]:
        """Get existing AI analysis for a finding (latest)."""
        result = await self.db.execute(
            select(FindingAiAnalysis)
            .where(
                FindingAiAnalysis.finding_id == finding_id,
                FindingAiAnalysis.workspace_id == workspace_id,
            )
            .order_by(FindingAiAnalysis.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_finding_analyses(self, finding_id: UUID, workspace_id: UUID) -> List[FindingAiAnalysis]:
        """Get all AI analyses for a finding (for version history)."""
        result = await self.db.execute(
            select(FindingAiAnalysis)
            .where(
                FindingAiAnalysis.finding_id == finding_id,
                FindingAiAnalysis.workspace_id == workspace_id,
            )
            .order_by(FindingAiAnalysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_ai_run(self, run_id: UUID, workspace_id: UUID) -> Optional[AiRun]:
        """Get AI run by ID with workspace check."""
        result = await self.db.execute(
            select(AiRun)
            .where(AiRun.id == run_id, AiRun.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def list_ai_runs_for_scan(self, scan_id: UUID, workspace_id: UUID) -> List[AiRun]:
        """List AI runs for a scan."""
        result = await self.db.execute(
            select(AiRun)
            .where(AiRun.scan_id == scan_id, AiRun.workspace_id == workspace_id)
            .order_by(AiRun.created_at.desc())
        )
        return list(result.scalars().all())
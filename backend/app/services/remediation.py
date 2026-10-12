import hashlib
import json
import logging
from typing import List, Optional, Dict, Any, Set
from uuid import UUID, uuid4
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    RemediationProposal, RemediationStatus, PatchVersion, ValidationRun,
    ValidationStatus, ValidationCheckType, Finding, FindingEvidence, Scan,
    Asset, Profile, AiRun, AiProviderType, AiOperationType, AiRunStatus,
    Workspace
)
from app.repositories import (
    RemediationProposalRepository, PatchVersionRepository, ValidationRunRepository,
    FindingRepository, FindingEvidenceRepository, AiRunRepository
)
from app.ai.manager import AIManager
from app.ai.schemas import SecurityAnalysis
from app.ai.providers import get_active_provider, AIProviderError
from app.security.audit import audit_log
from app.core.config import settings

logger = logging.getLogger(__name__)


class RemediationServiceError(Exception):
    def __init__(self, message: str, error_code: str = "REMEDIATION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class RemediationService:
    """
    AI Remediation Service - generates structured remediation proposals for findings.

    Responsibilities:
    - Retrieve finding, evidence, and AI analysis context
    - Build remediation prompt with minimum necessary context
    - Call AI provider with structured output schema
    - Validate AI response against strict schema
    - Persist proposal and patch version
    - Track AI runs for audit and cost control
    """

    # Patch size limits
    MAX_PATCH_SIZE_BYTES = 50000
    MAX_FILES_PER_PATCH = 10
    MAX_DIFF_LINES = 500

    # Proposal expiration
    PROPOSAL_EXPIRATION_DAYS = 30

    def __init__(self, db: AsyncSession):
        self.db = db
        self.proposal_repo = RemediationProposalRepository(db)
        self.patch_repo = PatchVersionRepository(db)
        self.validation_repo = ValidationRunRepository(db)
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.ai_run_repo = AiRunRepository(db)
        self.ai_manager = AIManager(db)
        self.provider = get_active_provider()

    async def generate_proposal(
        self,
        finding_id: UUID,
        user_id: UUID,
        workspace_id: UUID,
    ) -> RemediationProposal:
        """
        Generate an AI remediation proposal for a finding.

        This is the main entry point for remediation generation.
        """
        # 1. Verify access and retrieve finding with context
        finding = await self._get_finding_for_remediation(finding_id, workspace_id)
        if not finding:
            raise RemediationServiceError("Finding not found or access denied", "FINDING_NOT_FOUND")

        # Check if there's already a recent proposal for this finding
        existing = await self._get_recent_proposal(finding_id, workspace_id)
        if existing and existing.status in [RemediationStatus.DRAFT, RemediationStatus.GENERATING, RemediationStatus.PROPOSED]:
            logger.info(f"Active proposal already exists for finding {finding_id}: {existing.id}")
            return existing

        # 2. Retrieve evidence and previous AI analysis
        evidence_list = await self.evidence_repo.get_by_finding(finding_id)
        evidence_data = self._prepare_evidence_for_remediation(evidence_list)

        ai_analysis = await self.ai_manager.get_finding_analysis(finding_id, workspace_id)

        # 3. Get asset and scan context
        asset = await self._get_asset(finding.asset_id, workspace_id)
        scan = await self._get_scan(finding.scan_id, workspace_id)

        # 4. Create proposal record in DRAFT status
        proposal = await self._create_draft_proposal(finding, asset, scan, user_id, workspace_id)

        try:
            # 5. Update to GENERATING
            await self.proposal_repo.update(proposal.id, {"status": RemediationStatus.GENERATING})

            # 6. Build remediation prompt
            prompt = self._build_remediation_prompt(finding, evidence_data, ai_analysis, asset, scan)

            # 7. Call AI provider with structured output
            remediation_output = await self._call_provider_for_remediation(prompt, finding_id, evidence_data)

            # 8. Validate and process AI output
            patch_version = await self._process_ai_output(proposal, remediation_output, finding, user_id)

            # 9. Update proposal with generated content
            await self._finalize_proposal(proposal, remediation_output, patch_version)

            # 10. Create initial validation runs (patch integrity, diff parsing)
            await self._create_initial_validations(proposal, patch_version)

            # 11. Audit log
            await audit_log(
                db=self.db,
                workspace_id=workspace_id,
                action="remediation.proposal.generated",
                resource_type="remediation_proposal",
                resource_id=proposal.id,
                new_state={
                    "finding_id": str(finding_id),
                    "proposal_id": str(proposal.id),
                    "patch_version_id": str(patch_version.id),
                    "fix_type": proposal.fix_type.value,
                    "affected_files_count": len(proposal.affected_files),
                },
                user_id=user_id,
            )

            return proposal

        except AIProviderError as e:
            await self._handle_generation_error(proposal, e)
            raise RemediationServiceError(f"AI provider error: {e.message}", e.error_code)
        except Exception as e:
            logger.exception(f"Unexpected error generating remediation for finding {finding_id}: {e}")
            await self._handle_generation_error(proposal, e)
            raise RemediationServiceError(f"Remediation generation failed: {e}", "GENERATION_FAILED")

    async def _get_finding_for_remediation(self, finding_id: UUID, workspace_id: UUID) -> Optional[Finding]:
        """Retrieve finding and verify workspace access."""
        finding = await self.finding_repo.get_by_id(finding_id)
        if not finding or finding.workspace_id != workspace_id:
            return None
        return finding

    async def _get_recent_proposal(self, finding_id: UUID, workspace_id: UUID) -> Optional[RemediationProposal]:
        """Check for recent proposal for the same finding."""
        result = await self.db.execute(
            select(RemediationProposal)
            .where(
                RemediationProposal.finding_id == finding_id,
                RemediationProposal.workspace_id == workspace_id,
                RemediationProposal.status.in_([
                    RemediationStatus.DRAFT,
                    RemediationStatus.GENERATING,
                    RemediationStatus.PROPOSED,
                    RemediationStatus.VALIDATING,
                    RemediationStatus.AWAITING_APPROVAL,
                    RemediationStatus.APPROVED,
                ])
            )
            .order_by(RemediationProposal.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_asset(self, asset_id: UUID, workspace_id: UUID) -> Optional[Asset]:
        from app.repositories import AssetRepository
        asset_repo = AssetRepository(self.db)
        asset = await asset_repo.get_by_id(asset_id)
        if asset and asset.workspace_id == workspace_id:
            return asset
        return None

    async def _get_scan(self, scan_id: UUID, workspace_id: UUID) -> Optional[Scan]:
        from app.repositories import ScanRepository
        scan_repo = ScanRepository(self.db)
        scan = await scan_repo.get_by_id(scan_id)
        if scan and scan.workspace_id == workspace_id:
            return scan
        return None

    def _prepare_evidence_for_remediation(self, evidence_list: List[FindingEvidence]) -> List[Dict[str, Any]]:
        """Prepare and sanitize evidence for AI transmission."""
        evidence_data = []
        for evidence in evidence_list:
            from app.ai.safety import sanitize_evidence_dict, sanitize_for_ai
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

    async def _create_draft_proposal(
        self,
        finding: Finding,
        asset: Optional[Asset],
        scan: Optional[Scan],
        user_id: UUID,
        workspace_id: UUID,
    ) -> RemediationProposal:
        """Create initial proposal record in DRAFT status."""
        expires_at = datetime.utcnow() + timedelta(days=self.PROPOSAL_EXPIRATION_DAYS)

        proposal = RemediationProposal(
            workspace_id=workspace_id,
            asset_id=finding.asset_id,
            finding_id=finding.id,
            source_scan_id=finding.scan_id,
            status=RemediationStatus.DRAFT,
            proposal_title=f"Remediation for: {finding.title}",
            problem_summary="",  # Will be filled by AI
            proposed_solution="",  # Will be filled by AI
            rationale="",  # Will be filled by AI
            affected_files=[],
            validation_results={},
            fix_type=RemediationProposal.fix_type.type.python_type.CODE_CHANGE,  # Default, AI will determine
            created_by=user_id,
            expires_at=expires_at,
            version=1,
        )
        return await self.proposal_repo.create(proposal)

    def _build_remediation_prompt(
        self,
        finding: Finding,
        evidence_data: List[Dict[str, Any]],
        ai_analysis: Optional[Any],
        asset: Optional[Asset],
        scan: Optional[Scan],
    ) -> str:
        """Build the complete prompt for remediation generation."""
        import json

        # Build evidence summary
        evidence_summary = json.dumps(evidence_data, indent=2) if evidence_data else "No structured evidence available"

        # Build AI analysis summary
        ai_analysis_summary = "No previous AI analysis available"
        if ai_analysis:
            ai_analysis_summary = f"""
Previous AI Analysis:
- Summary: {ai_analysis.summary}
- Vulnerability Type: {ai_analysis.vulnerability_type}
- Severity Assessment: {ai_analysis.severity_assessment}
- Confidence: {ai_analysis.confidence}
- Impact Assessment: {ai_analysis.impact_assessment}
- Affected Component: {ai_analysis.affected_component}
- Attack Preconditions: {ai_analysis.attack_preconditions}
- Reasoning: {ai_analysis.reasoning}
- Recommended Next Steps: {', '.join(ai_analysis.recommended_next_steps)}
- Uncertainty: {ai_analysis.uncertainty}
"""

        # Build asset context
        asset_context = ""
        if asset:
            asset_context = f"""
Asset Context:
- Name: {asset.name}
- Type: {asset.type.value if asset.type else 'unknown'}
- Criticality: {asset.criticality.value if asset.criticality else 'unknown'}
"""

        # Build code context from finding
        code_context = finding.code_snippet or "Not available"
        file_path = finding.location.get("file", "unknown") if finding.location else "unknown"
        line_start = finding.location.get("line_start", 0) if finding.location else 0
        line_end = finding.location.get("line_end", 0) if finding.location else 0

        return f"""<TRUSTED_SYSTEM_INSTRUCTIONS>
You are the ShadowOps AI Remediation Engineer. Your role is to generate a safe, minimal, and correct code fix for a security vulnerability.

CRITICAL RULES:
1. Output MUST match the RemediationProposalOutput schema exactly.
2. The patch must be a valid unified diff that applies cleanly.
3. Only modify files directly related to the vulnerability. Do NOT modify:
   - Environment files (.env, .env.*, config/secrets)
   - Authentication/authorization logic (unless the finding is auth-related)
   - Database migrations
   - Deployment configuration (Dockerfile, k8s manifests, CI/CD)
   - Build scripts
4. Maximum {self.MAX_FILES_PER_PATCH} files per patch.
5. Maximum {self.MAX_PATCH_SIZE_BYTES} bytes total patch size.
6. Maximum {self.MAX_DIFF_LINES} lines of diff per file.
7. Use parameterized queries, input validation, output encoding - standard secure coding practices.
8. Do NOT introduce new dependencies unless absolutely necessary.
9. Preserve existing code style and patterns.
10. If you cannot generate a safe patch, return an error in the schema.
</TRUSTED_SYSTEM_INSTRUCTIONS>

<UNTRUSTED_SECURITY_EVIDENCE>
FINDING CONTEXT:
- Finding ID: {finding.id}
- Title: {finding.title}
- Description: {finding.description}
- Severity: {finding.severity.value}
- Source: {finding.source.value}
- Rule ID: {finding.source_rule_id or 'unknown'}
- File: {file_path}
- Lines: {line_start}-{line_end}
- CWE IDs: {', '.join(finding.cwe_ids) if finding.cwe_ids else 'None'}
- OWASP Categories: {', '.join(finding.owasp_categories) if finding.owasp_categories else 'None'}

SOURCE CODE SNIPPET:
{code_context}

SCANNER EVIDENCE:
{evidence_summary}

{ai_analysis_summary}

{asset_context}
</UNTRUSTED_SECURITY_EVIDENCE>

Generate a remediation proposal with:
1. Clear problem summary
2. Proposed solution with root cause explanation
3. Rationale for the fix approach
4. Affected files with unified diffs
5. Expected security benefit
6. Compatibility risks
7. Assumptions and limitations
8. Suggested tests for verification

The fix_type must be one of: code_change, config_change, dependency_update, infrastructure_change, waf_rule, network_policy, secret_rotation.
For code changes, provide unified diffs for each affected file.
"""

    async def _call_provider_for_remediation(
        self,
        prompt: str,
        finding_id: UUID,
        evidence_data: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Call AI provider with remediation schema."""
        from app.services.remediation_schemas import RemediationProposalOutput

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            try:
                response = await self.provider.generate_structured(
                    prompt=prompt,
                    output_schema=RemediationProposalOutput,
                    system_prompt="",  # System prompt is embedded in the prompt
                    temperature=0.1,
                )

                if not response.success:
                    if any("validation" in err.lower() or "schema" in err.lower() for err in response.errors):
                        raise RemediationServiceError(f"AI output validation failed: {response.errors}", "AI_VALIDATION_ERROR")
                    raise AIProviderError(f"AI provider returned error: {response.errors}", "AI_PROVIDER_ERROR")

                # Validate output
                is_valid, errors = self._validate_remediation_output(response.data, finding_id, evidence_data)
                if not is_valid:
                    raise RemediationServiceError(f"Remediation output validation failed: {errors}", "VALIDATION_ERROR")

                return response.data.model_dump()

            except AIProviderError as e:
                last_error = e
                if not e.retryable or attempt == max_retries - 1:
                    raise
                logger.warning(f"AI provider error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                continue
            except RemediationServiceError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                continue

        raise last_error or AIProviderError("Max retries exceeded", "MAX_RETRIES_EXCEEDED")

    def _validate_remediation_output(
        self,
        output: Any,
        finding_id: UUID,
        evidence_data: List[Dict[str, Any]],
    ) -> tuple[bool, List[str]]:
        """Validate remediation output against constraints."""
        errors = []
        evidence_ids = {e["evidence_id"] for e in evidence_data}

        # Check patch size
        total_diff_size = 0
        for file_change in output.file_changes:
            if hasattr(file_change, 'unified_diff') and file_change.unified_diff:
                total_diff_size += len(file_change.unified_diff.encode())

        if total_diff_size > self.MAX_PATCH_SIZE_BYTES:
            errors.append(f"Patch size {total_diff_size} exceeds maximum {self.MAX_PATCH_SIZE_BYTES} bytes")

        # Check file count
        if len(output.file_changes) > self.MAX_FILES_PER_PATCH:
            errors.append(f"Too many files in patch: {len(output.file_changes)} (max {self.MAX_FILES_PER_PATCH})")

        # Check each file change
        for i, fc in enumerate(output.file_changes):
            if not fc.file_path:
                errors.append(f"File change {i}: missing file_path")
            if fc.file_path and (fc.file_path.startswith('/') or '..' in fc.file_path):
                errors.append(f"File change {i}: path traversal detected in {fc.file_path}")
            if hasattr(fc, 'unified_diff') and fc.unified_diff:
                diff_lines = fc.unified_diff.count('\n')
                if diff_lines > self.MAX_DIFF_LINES:
                    errors.append(f"File change {i}: diff too large ({diff_lines} lines, max {self.MAX_DIFF_LINES})")

        # Validate fix_type
        valid_fix_types = [ft.value for ft in RemediationProposal.fix_type.type.python_type]
        if output.fix_type not in valid_fix_types:
            errors.append(f"Invalid fix_type: {output.fix_type}")

        return len(errors) == 0, errors

    async def _process_ai_output(
        self,
        proposal: RemediationProposal,
        remediation_output: Dict[str, Any],
        finding: Finding,
        user_id: UUID,
    ) -> PatchVersion:
        """Process AI output and create patch version."""
        # Build unified diff from file changes
        unified_diff_parts = []
        file_changes = []

        for fc in remediation_output.get("file_changes", []):
            unified_diff_parts.append(fc.get("unified_diff", ""))
            file_changes.append({
                "file_path": fc.get("file_path", ""),
                "old_hash": fc.get("old_hash"),
                "new_hash": fc.get("new_hash"),
                "additions": fc.get("additions", 0),
                "deletions": fc.get("deletions", 0),
            })

        unified_diff = "\n".join(unified_diff_parts)
        patch_hash = hashlib.sha256(unified_diff.encode()).hexdigest()

        # Create patch version
        patch_version = PatchVersion(
            proposal_id=proposal.id,
            workspace_id=proposal.workspace_id,
            version=1,
            unified_diff=unified_diff,
            file_changes=file_changes,
            patch_hash=patch_hash,
            base_revision=None,  # Would be set if we had git integration
            created_by=user_id,
            is_current=True,
        )
        return await self.patch_repo.create(patch_version)

    async def _finalize_proposal(
        self,
        proposal: RemediationProposal,
        remediation_output: Dict[str, Any],
        patch_version: PatchVersion,
    ) -> None:
        """Update proposal with generated content."""
        # Convert affected_files to schema format
        affected_files = []
        for fc in remediation_output.get("file_changes", []):
            affected_files.append({
                "file_path": fc.get("file_path", ""),
                "language": self._detect_language(fc.get("file_path", "")),
                "change_type": "modify",
            })

        update_data = {
            "status": RemediationStatus.PROPOSED,
            "proposal_title": remediation_output.get("proposal_title", proposal.proposal_title),
            "problem_summary": remediation_output.get("problem_summary", ""),
            "proposed_solution": remediation_output.get("proposed_solution", ""),
            "rationale": remediation_output.get("rationale", ""),
            "affected_files": affected_files,
            "patch_reference": patch_version.id,
            "validation_results": {},
            "fix_type": remediation_output.get("fix_type", "code_change"),
            "expected_security_benefit": remediation_output.get("expected_security_benefit"),
            "compatibility_risks": remediation_output.get("compatibility_risks"),
            "assumptions": remediation_output.get("assumptions"),
            "limitations": remediation_output.get("limitations"),
            "suggested_tests": remediation_output.get("suggested_tests", []),
            "version": proposal.version + 1,
        }
        await self.proposal_repo.update(proposal.id, update_data)

    async def _create_initial_validations(
        self,
        proposal: RemediationProposal,
        patch_version: PatchVersion,
    ) -> None:
        """Create initial validation runs for patch integrity and diff parsing."""
        validation_types = [
            ValidationCheckType.PATCH_INTEGRITY,
            ValidationCheckType.DIFF_PARSING,
            ValidationCheckType.PATH_ALLOWLIST,
        ]

        for check_type in validation_types:
            validation = ValidationRun(
                proposal_id=proposal.id,
                patch_version_id=patch_version.id,
                workspace_id=proposal.workspace_id,
                status=ValidationStatus.PENDING,
                check_type=check_type,
            )
            await self.validation_repo.create(validation)

    async def _handle_generation_error(self, proposal: RemediationProposal, error: Exception) -> None:
        """Handle generation error by updating proposal status."""
        error_message = str(error)
        await self.proposal_repo.update(proposal.id, {
            "status": RemediationStatus.FAILED,
            "failure_reason": error_message[:1000],
        })

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect programming language from file extension."""
        ext_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.go': 'go',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.cc': 'cpp',
            '.cxx': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.rb': 'ruby',
            '.php': 'php',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.sql': 'sql',
        }
        import os
        _, ext = os.path.splitext(file_path)
        return ext_map.get(ext.lower())

    async def get_proposal(self, proposal_id: UUID, workspace_id: UUID) -> Optional[RemediationProposal]:
        """Get proposal by ID with workspace check."""
        result = await self.db.execute(
            select(RemediationProposal)
            .where(RemediationProposal.id == proposal_id, RemediationProposal.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    async def list_proposals(
        self,
        workspace_id: UUID,
        status: Optional[RemediationStatus] = None,
        finding_id: Optional[UUID] = None,
        asset_id: Optional[UUID] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[RemediationProposal]:
        """List proposals with filters."""
        query = select(RemediationProposal).where(RemediationProposal.workspace_id == workspace_id)
        if status:
            query = query.where(RemediationProposal.status == status)
        if finding_id:
            query = query.where(RemediationProposal.finding_id == finding_id)
        if asset_id:
            query = query.where(RemediationProposal.asset_id == asset_id)
        query = query.order_by(RemediationProposal.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_proposal_detail(self, proposal_id: UUID, workspace_id: UUID) -> Optional[Dict[str, Any]]:
        """Get full proposal detail with related records."""
        proposal = await self.get_proposal(proposal_id, workspace_id)
        if not proposal:
            return None

        patch_versions = await self.patch_repo.get_by_proposal(proposal_id)
        validations = await self.validation_repo.get_by_proposal(proposal_id)

        from app.repositories import RemediationApprovalRepository, RemediationApplicationRepository, RemediationRollbackRepository, RemediationVerificationHandoffRepository
        approval_repo = RemediationApprovalRepository(self.db)
        application_repo = RemediationApplicationRepository(self.db)
        rollback_repo = RemediationRollbackRepository(self.db)
        handoff_repo = RemediationVerificationHandoffRepository(self.db)

        approvals = await approval_repo.get_by_proposal(proposal_id)
        applications = await application_repo.get_by_proposal(proposal_id)
        rollbacks = await rollback_repo.get_by_application(applications[0].id) if applications else []
        handoff = await handoff_repo.get_by_proposal(proposal_id) if applications else None

        return {
            "proposal": proposal,
            "patch_versions": patch_versions,
            "validations": validations,
            "approvals": approvals,
            "applications": applications,
            "rollbacks": rollbacks,
            "verification_handoff": handoff,
        }
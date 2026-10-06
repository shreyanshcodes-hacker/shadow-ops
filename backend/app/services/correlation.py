import json
import logging
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func

from app.models import (
    Finding, FindingEvidence, FindingAiAnalysis, FindingRelationship,
    AttackPath, AttackPathNode, AttackPathNodeType, AttackPathEdge, AttackPathStatus,
    RiskSnapshot, RelationshipType, RelationshipSource,
    Asset, Workspace
)
from app.repositories import (
    FindingRepository, FindingEvidenceRepository, FindingRelationshipRepository,
    AttackPathRepository, AttackPathNodeRepository, AttackPathEdgeRepository,
    RiskSnapshotRepository, FindingAiAnalysisRepository
)
from app.ai.manager import AIManager
from app.ai.schemas import SecurityAnalysis
from app.ai.prompts import build_finding_analysis_prompt, SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


class CorrelationEngineError(Exception):
    def __init__(self, message: str, error_code: str = "CORRELATION_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class CorrelationEngine:
    """
    Deterministic correlation engine for finding relationships.
    
    Detects relationships based on:
    - Same asset
    - Same file
    - Nearby source locations
    - Same component
    - Same entry point
    - Same CWE/OWASP category
    - Shared data-flow metadata
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.relationship_repo = FindingRelationshipRepository(db)

    async def find_relationships_for_finding(
        self,
        finding_id: UUID,
        workspace_id: UUID,
        max_relationships: int = 10,
    ) -> List[FindingRelationship]:
        """
        Find all deterministic relationships for a finding.
        Returns AI_SUGGESTED relationships that need human confirmation.
        """
        finding = await self.finding_repo.get_by_id(finding_id)
        if not finding or finding.workspace_id != workspace_id:
            raise CorrelationEngineError("Finding not found or access denied", "FINDING_NOT_FOUND")

        # Get all other findings in the same workspace (excluding self)
        other_findings = await self.finding_repo.get_by_workspace(workspace_id, limit=1000)
        other_findings = [f for f in other_findings if f.id != finding_id]

        relationships = []
        for other in other_findings:
            rels = self._detect_relationships(finding, other)
            for rel in rels:
                # Check if relationship already exists
                existing = await self.relationship_repo.get_by_findings(finding_id, other.id)
                if not any(e.relationship_type == rel.relationship_type for e in existing):
                    relationships.append(rel)

        # Sort by confidence descending and limit
        relationships.sort(key=lambda r: r.confidence, reverse=True)
        return relationships[:max_relationships]

    async def find_all_relationships(
        self,
        workspace_id: UUID,
        max_relationships: int = 100,
    ) -> List[FindingRelationship]:
        """Find all deterministic relationships in a workspace."""
        findings = await self.finding_repo.get_by_workspace(workspace_id, limit=500)
        relationships = []

        for i, finding_a in enumerate(findings):
            for finding_b in findings[i+1:]:
                rels = self._detect_relationships(finding_a, finding_b)
                for rel in rels:
                    # Check if relationship already exists
                    existing = await self.relationship_repo.get_by_findings(finding_a.id, finding_b.id)
                    if not any(e.relationship_type == rel.relationship_type for e in existing):
                        relationships.append(rel)

        relationships.sort(key=lambda r: r.confidence, reverse=True)
        return relationships[:max_relationships]

    def _detect_relationships(self, finding_a: Finding, finding_b: Finding) -> List[FindingRelationship]:
        """Detect all deterministic relationships between two findings."""
        relationships = []

        # Same file
        file_a = finding_a.location.get("file") if finding_a.location else None
        file_b = finding_b.location.get("file") if finding_b.location else None
        if file_a and file_b and file_a == file_b:
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.SHARES_COMPONENT,
                0.9,
                f"Both findings in same file: {file_a}"
            ))

            # Nearby lines
            line_a_start = finding_a.location.get("line_start") if finding_a.location else None
            line_a_end = finding_a.location.get("line_end") if finding_a.location else None
            line_b_start = finding_b.location.get("line_start") if finding_b.location else None
            line_b_end = finding_b.location.get("line_end") if finding_b.location else None

            if line_a_start and line_b_start:
                distance = min(
                    abs(line_a_start - line_b_start),
                    abs(line_a_start - (line_b_end or line_b_start)),
                    abs((line_a_end or line_a_start) - line_b_start),
                    abs((line_a_end or line_a_start) - (line_b_end or line_b_start))
                )
                if distance <= 20:
                    relationships.append(self._create_relationship(
                        finding_a, finding_b,
                        RelationshipType.DEPENDS_ON,
                        0.7 - (distance * 0.02),
                        f"Findings within {distance} lines in same file"
                    ))

        # Same component (based on file path prefix)
        if file_a and file_b:
            comp_a = self._extract_component(file_a)
            comp_b = self._extract_component(file_b)
            if comp_a and comp_b and comp_a == comp_b:
                relationships.append(self._create_relationship(
                    finding_a, finding_b,
                    RelationshipType.SHARES_COMPONENT,
                    0.8,
                    f"Both findings in same component: {comp_a}"
                ))

        # Same CWE
        cwe_a = set(finding_a.cwe_ids or [])
        cwe_b = set(finding_b.cwe_ids or [])
        if cwe_a & cwe_b:
            shared_cwe = cwe_a & cwe_b
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.SHARES_DATA_FLOW,
                0.6,
                f"Shared CWE categories: {', '.join(shared_cwe)}"
            ))

        # Same OWASP category
        owasp_a = set(finding_a.owasp_categories or [])
        owasp_b = set(finding_b.owasp_categories or [])
        if owasp_a & owasp_b:
            shared_owasp = owasp_a & owasp_b
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.SHARES_COMPONENT,
                0.5,
                f"Shared OWASP categories: {', '.join(shared_owasp)}"
            ))

        # Same vulnerability type (from AI analysis)
        # This would require loading AI analyses

        # Injection -> Auth/Authorization chains
        if self._is_injection(finding_a) and self._is_auth_issue(finding_b):
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.ENABLES,
                0.6,
                "Injection vulnerability may enable authentication bypass"
            ))

        # Auth -> Data exposure
        if self._is_auth_issue(finding_a) and self._is_data_exposure(finding_b):
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.LEADS_TO,
                0.5,
                "Authentication issue may lead to data exposure"
            ))

        # Config -> Injection
        if self._is_misconfig(finding_a) and self._is_injection(finding_b):
            relationships.append(self._create_relationship(
                finding_a, finding_b,
                RelationshipType.ENABLES,
                0.5,
                "Misconfiguration may enable injection"
            ))

        return relationships

    def _extract_component(self, file_path: str) -> Optional[str]:
        """Extract component name from file path."""
        parts = file_path.split("/")
        if len(parts) >= 2:
            return parts[-2]  # Parent directory as component
        return None

    def _is_injection(self, finding: Finding) -> bool:
        return (finding.source_rule_id and "injection" in finding.source_rule_id.lower()) or \
               "injection" in finding.title.lower() or \
               "sql" in finding.title.lower() or \
               "xss" in finding.title.lower() or \
               "command" in finding.title.lower()

    def _is_auth_issue(self, finding: Finding) -> bool:
        return (finding.source_rule_id and ("auth" in finding.source_rule_id.lower() or "authentication" in finding.source_rule_id.lower())) or \
               "authentication" in finding.title.lower() or \
               "authorization" in finding.title.lower() or \
               "bypass" in finding.title.lower()

    def _is_data_exposure(self, finding: Finding) -> bool:
        return (finding.source_rule_id and "exposure" in finding.source_rule_id.lower()) or \
               "exposure" in finding.title.lower() or \
               "leak" in finding.title.lower() or \
               "disclosure" in finding.title.lower()

    def _is_misconfig(self, finding: Finding) -> bool:
        return (finding.source_rule_id and "config" in finding.source_rule_id.lower()) or \
               "config" in finding.title.lower() or \
               "hardcoded" in finding.title.lower() or \
               "secret" in finding.title.lower()

    def _create_relationship(
        self,
        source: Finding,
        target: Finding,
        rel_type: RelationshipType,
        confidence: float,
        rationale: str,
    ) -> FindingRelationship:
        return FindingRelationship(
            workspace_id=source.workspace_id,
            source_finding_id=source.id,
            target_finding_id=target.id,
            relationship_type=rel_type,
            confidence=max(0.0, min(1.0, confidence)),
            source=RelationshipSource.DETERMINISTIC,
            rationale=rationale,
            evidence_reference=None,
        )


class AIRelationshipAnalyzer:
    """
    AI-powered relationship analysis between findings.
    Uses the existing AI provider abstraction from Stage 5.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.ai_manager = AIManager(db)
        self.relationship_repo = FindingRelationshipRepository(db)

    async def analyze_relationship(
        self,
        finding_a_id: UUID,
        finding_b_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Optional[FindingRelationship]:
        """
        Ask AI to analyze if a relationship exists between two findings.
        Returns AI_SUGGESTED relationship if confident.
        """
        finding_a = await self.db.execute(select(Finding).where(Finding.id == finding_a_id))
        finding_a = finding_a.scalar_one_or_none()
        finding_b = await self.db.execute(select(Finding).where(Finding.id == finding_b_id))
        finding_b = finding_b.scalar_one_or_none()

        if not finding_a or not finding_b:
            return None

        if finding_a.workspace_id != workspace_id or finding_b.workspace_id != workspace_id:
            return None

        # Get evidence for both findings
        evidence_a = await self.evidence_repo.get_by_finding(finding_a_id)
        evidence_b = await self.evidence_repo.get_by_finding(finding_b_id)

        # Get AI analyses if available
        analysis_a = await self.ai_manager.get_finding_analysis(finding_a_id, workspace_id)
        analysis_b = await self.ai_manager.get_finding_analysis(finding_b_id, workspace_id)

        # Build prompt for relationship analysis
        prompt = self._build_relationship_prompt(
            finding_a, evidence_a, analysis_a,
            finding_b, evidence_b, analysis_b,
        )

        # Call AI provider
        try:
            from app.ai.providers import get_active_provider
            provider = get_active_provider()

            from app.ai.schemas import SecurityAnalysis
            # We'll use a simpler schema for relationship
            from pydantic import BaseModel, Field
            from typing import List, Optional

            class RelationshipAnalysis(BaseModel):
                relationship: Optional[str] = Field(default=None, description="Relationship type or null if no relationship")
                confidence: float = Field(ge=0.0, le=1.0)
                rationale: str
                required_evidence: List[str] = Field(default_factory=list)

            response = await provider.generate_structured(
                prompt=prompt,
                output_schema=RelationshipAnalysis,
                system_prompt=self._get_relationship_system_prompt(),
                temperature=0.1,
            )

            if not response.success or not response.data:
                return None

            analysis = response.data

            if not analysis.relationship or analysis.confidence < 0.5:
                return None

            # Validate relationship type
            try:
                rel_type = RelationshipType(analysis.relationship.lower())
            except ValueError:
                return None

            # Check if relationship already exists
            existing = await self.relationship_repo.get_by_findings(finding_a_id, finding_b_id)
            if any(e.relationship_type == rel_type for e in existing):
                return None

            return FindingRelationship(
                workspace_id=workspace_id,
                source_finding_id=finding_a_id,
                target_finding_id=finding_b_id,
                relationship_type=rel_type,
                confidence=analysis.confidence,
                source=RelationshipSource.AI_SUGGESTED,
                rationale=analysis.rationale,
                evidence_reference=json.dumps(analysis.required_evidence) if analysis.required_evidence else None,
            )

        except Exception as e:
            logger.warning(f"AI relationship analysis failed: {e}")
            return None

    def _get_relationship_system_prompt(self) -> str:
        return f"""{SECURITY_FINDING_ANALYSIS_SYSTEM_PROMPT}

ADDITIONAL TASK: Analyze the relationship between TWO security findings.

Determine if Finding A enables, leads to, exposes, or otherwise relates to Finding B.

Valid relationship types:
- depends_on: Finding A must exist for Finding B to be exploitable
- enables: Finding A creates conditions for Finding B
- exposes: Finding A exposes attack surface for Finding B
- leads_to: Finding A can lead to Finding B through attack chain
- shares_component: Both findings affect the same component
- shares_entry_point: Both findings share an entry point
- shares_data_flow: Both findings involve same data flow
- amplifies: Finding A amplifies the impact of Finding B

Respond with structured JSON only.
"""

    def _build_relationship_prompt(
        self,
        finding_a: Finding,
        evidence_a: List[FindingEvidence],
        analysis_a: Optional[FindingAiAnalysis],
        finding_b: Finding,
        evidence_b: List[FindingEvidence],
        analysis_b: Optional[FindingAiAnalysis],
    ) -> str:
        def format_finding(f: Finding, ev: List[FindingEvidence], ai: Optional[FindingAiAnalysis]) -> str:
            parts = [
                f"FINDING ID: {f.id}",
                f"Title: {f.title}",
                f"Severity: {f.severity.value}",
                f"Source: {f.source.value}",
                f"Rule: {f.source_rule_id or 'N/A'}",
                f"File: {f.location.get('file', 'N/A') if f.location else 'N/A'}",
                f"Lines: {f.location.get('line_start', 'N/A') if f.location else 'N/A'}-{f.location.get('line_end', 'N/A') if f.location else 'N/A'}",
                f"CWE IDs: {', '.join(f.cwe_ids) if f.cwe_ids else 'None'}",
                f"OWASP: {', '.join(f.owasp_categories) if f.owasp_categories else 'None'}",
                f"Code: {f.code_snippet or 'N/A'}",
            ]
            if ev:
                parts.append("EVIDENCE:")
                for e in ev[:3]:
                    parts.append(f"  - {e.evidence_type.value}: {e.title}")
            if ai:
                parts.append(f"AI ANALYSIS: {ai.summary}")
                parts.append(f"AI VULN TYPE: {ai.vulnerability_type}")
                parts.append(f"AI EXPLOITABILITY: {ai.exploitability_assessment}")
            return "\n".join(parts)

        return f"""Analyze the relationship between these two security findings:

FINDING A:
{format_finding(finding_a, evidence_a, analysis_a)}

FINDING B:
{format_finding(finding_b, evidence_b, analysis_b)}

Does Finding A relate to Finding B? If so, what type of relationship and how confident are you?
If no clear relationship exists, respond with relationship: null.
"""
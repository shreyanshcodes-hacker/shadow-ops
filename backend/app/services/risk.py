import logging
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    AttackPath, AttackPathNode, AttackPathEdge, AttackPathNodeType,
    Finding, FindingSeverity, FindingAiAnalysis, RiskSnapshot, RiskBand,
    RelationshipType, Workspace
)
from app.repositories import (
    AttackPathRepository, AttackPathNodeRepository, AttackPathEdgeRepository,
    RiskSnapshotRepository, FindingRepository, FindingAiAnalysisRepository
)
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


RISK_MODEL_VERSION = "risk-v1"


class RiskFactorName(str, Enum):
    SEVERITY = "severity"
    EXPLOITABILITY = "exploitability"
    IMPACT = "impact"
    CONFIDENCE = "confidence"
    EXPOSURE = "exposure"
    PATH_COMPLEXITY = "path_complexity"
    PRIVILEGE_BOUNDARY = "privilege_boundary"
    DATA_SENSITIVITY = "data_sensitivity"


@dataclass
class RiskFactor:
    name: RiskFactorName
    weight: float
    value: float  # 0.0 - 1.0
    contribution: float  # weight * value * 100
    description: str


@dataclass
class RiskCalculationResult:
    score: int  # 0-100
    risk_band: RiskBand
    model_version: str
    factors: List[RiskFactor]
    explanation: str


class RiskEngineError(Exception):
    def __init__(self, message: str, error_code: str = "RISK_ENGINE_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class RiskEngine:
    """
    Deterministic risk scoring engine.
    
    The score is calculated from explicit, auditable factors.
    Same inputs always produce the same score.
    No AI involvement in the final numerical score.
    """

    # Risk model weights (must sum to 1.0)
    WEIGHTS = {
        RiskFactorName.SEVERITY: 0.30,
        RiskFactorName.EXPLOITABILITY: 0.20,
        RiskFactorName.IMPACT: 0.20,
        RiskFactorName.CONFIDENCE: 0.15,
        RiskFactorName.EXPOSURE: 0.10,
        RiskFactorName.PATH_COMPLEXITY: 0.05,
    }

    # Risk band thresholds
    RISK_BANDS = [
        (0, 19, RiskBand.INFORMATIONAL),
        (20, 39, RiskBand.LOW),
        (40, 59, RiskBand.MEDIUM),
        (60, 79, RiskBand.HIGH),
        (80, 100, RiskBand.CRITICAL),
    ]

    def __init__(self, db: AsyncSession):
        self.db = db
        self.path_repo = AttackPathRepository(db)
        self.node_repo = AttackPathNodeRepository(db)
        self.edge_repo = AttackPathEdgeRepository(db)
        self.finding_repo = FindingRepository(db)
        self.analysis_repo = FindingAiAnalysisRepository(db)
        self.snapshot_repo = RiskSnapshotRepository(db)

    def calculate_risk(self, attack_path: AttackPath) -> RiskCalculationResult:
        """
        Calculate deterministic risk score for an attack path.
        
        This is the core deterministic function - no AI, no randomness.
        """
        factors = []
        
        # Load required data
        nodes = list(attack_path.nodes)
        edges = list(attack_path.edges)
        
        # Factor 1: Severity (max finding severity in path)
        severity_factor = self._calculate_severity_factor(nodes)
        factors.append(severity_factor)
        
        # Factor 2: Exploitability (from AI analyses + edge confidences)
        exploitability_factor = self._calculate_exploitability_factor(nodes, edges)
        factors.append(exploitability_factor)
        
        # Factor 3: Impact (from AI analyses + node types)
        impact_factor = self._calculate_impact_factor(nodes, edges)
        factors.append(impact_factor)
        
        # Factor 4: Confidence (overall path confidence)
        confidence_factor = self._calculate_confidence_factor(attack_path, nodes, edges)
        factors.append(confidence_factor)
        
        # Factor 5: Exposure (external entry points, public assets)
        exposure_factor = self._calculate_exposure_factor(nodes, attack_path)
        factors.append(exposure_factor)
        
        # Factor 6: Path Complexity (length, branches)
        complexity_factor = self._calculate_complexity_factor(nodes, edges)
        factors.append(complexity_factor)
        
        # Calculate weighted score
        total_score = sum(f.contribution for f in factors)
        score = int(round(total_score))
        score = max(0, min(100, score))  # Clamp to 0-100
        
        # Determine risk band
        risk_band = self._score_to_band(score)
        
        # Generate explanation
        explanation = self._generate_explanation(factors, score, risk_band)
        
        return RiskCalculationResult(
            score=score,
            risk_band=risk_band,
            model_version=RISK_MODEL_VERSION,
            factors=factors,
            explanation=explanation,
        )

    def _calculate_severity_factor(self, nodes: List[AttackPathNode]) -> RiskFactor:
        """Calculate severity factor from finding severities."""
        max_severity_value = 0.0
        
        for node in nodes:
            if node.finding_id and node.finding:
                finding = node.finding
                severity_map = {
                    FindingSeverity.CRITICAL: 1.0,
                    FindingSeverity.HIGH: 0.8,
                    FindingSeverity.MEDIUM: 0.6,
                    FindingSeverity.LOW: 0.4,
                    FindingSeverity.INFO: 0.2,
                }
                value = severity_map.get(finding.severity, 0.0)
                max_severity_value = max(max_severity_value, value)
        
        weight = self.WEIGHTS[RiskFactorName.SEVERITY]
        contribution = max_severity_value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.SEVERITY,
            weight=weight,
            value=max_severity_value,
            contribution=contribution,
            description=f"Maximum finding severity in path: {self._severity_to_str(max_severity_value)}",
        )

    def _calculate_exploitability_factor(
        self,
        nodes: List[AttackPathNode],
        edges: List[AttackPathEdge],
    ) -> RiskFactor:
        """Calculate exploitability factor."""
        exploitability_values = []
        
        # From AI analyses
        for node in nodes:
            if node.finding_id:
                # Would need to load AI analysis
                # For now, use edge confidence as proxy
                pass
        
        # From edge confidences (relationship confidence)
        if edges:
            avg_edge_confidence = sum(e.confidence for e in edges) / len(edges)
            exploitability_values.append(avg_edge_confidence)
        
        # Default if no data
        if not exploitability_values:
            exploitability_values = [0.5]  # Neutral default
        
        value = max(exploitability_values)
        weight = self.WEIGHTS[RiskFactorName.EXPLOITABILITY]
        contribution = value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.EXPLOITABILITY,
            weight=weight,
            value=value,
            contribution=contribution,
            description=f"Exploitability from relationship confidences: {value:.2f}",
        )

    def _calculate_impact_factor(
        self,
        nodes: List[AttackPathNode],
        edges: List[AttackPathEdge],
    ) -> RiskFactor:
        """Calculate impact factor from node types and AI assessments."""
        impact_values = []
        
        # Impact node at end increases impact
        has_impact_node = any(n.node_type == AttackPathNodeType.IMPACT for n in nodes)
        if has_impact_node:
            impact_values.append(0.8)
        
        # Boundary nodes indicate privilege escalation
        has_boundary = any(n.node_type == AttackPathNodeType.BOUNDARY for n in nodes)
        if has_boundary:
            impact_values.append(0.7)
        
        # From AI analysis impact assessments (would need loading)
        # Default
        if not impact_values:
            impact_values = [0.5]
        
        value = max(impact_values)
        weight = self.WEIGHTS[RiskFactorName.IMPACT]
        contribution = value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.IMPACT,
            weight=weight,
            value=value,
            contribution=contribution,
            description=f"Potential impact from path structure: {value:.2f}",
        )

    def _calculate_confidence_factor(
        self,
        attack_path: AttackPath,
        nodes: List[AttackPathNode],
        edges: List[AttackPathEdge],
    ) -> RiskFactor:
        """Calculate confidence factor."""
        confidence_values = [attack_path.confidence]
        
        # Edge confidences
        if edges:
            avg_edge_conf = sum(e.confidence for e in edges) / len(edges)
            confidence_values.append(avg_edge_conf)
        
        # AI analysis confidences (would need loading)
        
        value = sum(confidence_values) / len(confidence_values) if confidence_values else 0.5
        weight = self.WEIGHTS[RiskFactorName.CONFIDENCE]
        contribution = value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.CONFIDENCE,
            weight=weight,
            value=value,
            contribution=contribution,
            description=f"Overall analysis confidence: {value:.2f}",
        )

    def _calculate_exposure_factor(
        self,
        nodes: List[AttackPathNode],
        attack_path: AttackPath,
    ) -> RiskFactor:
        """Calculate exposure factor (external accessibility)."""
        exposure_values = []
        
        # Entry point node indicates external exposure
        has_entry = any(n.node_type == AttackPathNodeType.ENTRY for n in nodes)
        if has_entry:
            exposure_values.append(0.9)
        
        # Asset criticality (would need loading asset)
        # Default
        if not exposure_values:
            exposure_values = [0.5]
        
        value = max(exposure_values)
        weight = self.WEIGHTS[RiskFactorName.EXPOSURE]
        contribution = value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.EXPOSURE,
            weight=weight,
            value=value,
            contribution=contribution,
            description=f"External exposure level: {value:.2f}",
        )

    def _calculate_complexity_factor(
        self,
        nodes: List[AttackPathNode],
        edges: List[AttackPathEdge],
    ) -> RiskFactor:
        """Calculate path complexity factor."""
        # Longer paths = more complex = slightly lower risk (harder to exploit)
        # But more steps = more attack surface
        path_length = len(nodes)
        
        # Normalize: 2-3 nodes = 0.5, 8 nodes = 0.3
        if path_length <= 2:
            value = 0.6
        elif path_length <= 4:
            value = 0.5
        elif path_length <= 6:
            value = 0.4
        else:
            value = 0.3
        
        weight = self.WEIGHTS[RiskFactorName.PATH_COMPLEXITY]
        contribution = value * weight * 100
        
        return RiskFactor(
            name=RiskFactorName.PATH_COMPLEXITY,
            weight=weight,
            value=value,
            contribution=contribution,
            description=f"Attack path complexity (length: {path_length}): {value:.2f}",
        )

    def _score_to_band(self, score: int) -> RiskBand:
        """Map score to risk band."""
        for min_score, max_score, band in self.RISK_BANDS:
            if min_score <= score <= max_score:
                return band
        return RiskBand.INFORMATIONAL

    def _severity_to_str(self, value: float) -> str:
        if value >= 1.0:
            return "CRITICAL"
        elif value >= 0.8:
            return "HIGH"
        elif value >= 0.6:
            return "MEDIUM"
        elif value >= 0.4:
            return "LOW"
        elif value >= 0.2:
            return "INFO"
        return "UNKNOWN"

    def _generate_explanation(
        self,
        factors: List[RiskFactor],
        score: int,
        risk_band: RiskBand,
    ) -> str:
        """Generate human-readable explanation of risk score."""
        lines = [
            f"Risk Score: {score} / 100 ({risk_band.value.upper()})",
            f"Model: {RISK_MODEL_VERSION}",
            "",
            "Contributing Factors:",
        ]
        
        for factor in factors:
            pct = factor.contribution
            lines.append(f"  {factor.name.value:20s}  {pct:5.1f}  {factor.description}")
        
        lines.append("")
        lines.append(f"Total: {score:.1f} → {risk_band.value.upper()}")
        
        return "\n".join(lines)


class RiskManager:
    """High-level manager for risk operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.engine = RiskEngine(db)
        self.path_repo = AttackPathRepository(db)
        self.snapshot_repo = RiskSnapshotRepository(db)

    async def calculate_and_persist_risk(
        self,
        attack_path_id: UUID,
        workspace_id: UUID,
        user_id: UUID,
    ) -> Optional[RiskCalculationResult]:
        """Calculate risk for an attack path and persist snapshot."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            raise RiskEngineError("Attack path not found or access denied", "PATH_NOT_FOUND")

        result = self.engine.calculate_risk(path)
        
        # Update attack path with new score
        await self.path_repo.update(attack_path_id, {
            "risk_score": result.score,
            "severity": result.risk_band.value,
        })
        
        # Persist risk snapshot
        snapshot = RiskSnapshot(
            workspace_id=workspace_id,
            attack_path_id=attack_path_id,
            score=result.score,
            risk_band=result.risk_band.value,
            model_version=result.model_version,
            factors={
                "factors": [
                    {
                        "name": f.name.value,
                        "weight": f.weight,
                        "value": f.value,
                        "contribution": f.contribution,
                        "description": f.description,
                    }
                    for f in result.factors
                ],
                "explanation": result.explanation,
            },
        )
        await self.snapshot_repo.create(snapshot)
        
        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="risk.calculated",
            resource_type="risk_snapshot",
            resource_id=snapshot.id,
            new_state={
                "attack_path_id": str(attack_path_id),
                "score": result.score,
                "risk_band": result.risk_band.value,
                "model_version": result.model_version,
            },
            user_id=user_id,
        )
        
        return result

    async def get_risk_history(self, attack_path_id: UUID, workspace_id: UUID) -> List[RiskSnapshot]:
        """Get historical risk snapshots for an attack path."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return []
        return await self.snapshot_repo.get_by_attack_path(attack_path_id)

    async def get_latest_risk(self, attack_path_id: UUID, workspace_id: UUID) -> Optional[RiskSnapshot]:
        """Get latest risk snapshot for an attack path."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return None
        return await self.snapshot_repo.get_latest_by_attack_path(attack_path_id)


# Utility function for external use
def get_risk_band(score: int) -> RiskBand:
    """Get risk band for a score."""
    for min_score, max_score, band in RiskEngine.RISK_BANDS:
        if min_score <= score <= max_score:
            return band
    return RiskBand.INFORMATIONAL
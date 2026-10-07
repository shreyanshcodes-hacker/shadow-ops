import json
import logging
from typing import List, Dict, Any, Optional, Set
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import (
    Asset, Scan, Finding, FindingEvidence, FindingAiAnalysis,
    AttackPath, AttackPathNode, AttackPathEdge, RiskSnapshot,
    FindingRelationship, RelationshipType, RelationshipSource,
)
from app.repositories import (
    FindingRepository, FindingEvidenceRepository, FindingAiAnalysisRepository,
    AttackPathRepository, RiskSnapshotRepository, FindingRelationshipRepository,
)
from app.agents.team.base import TeamAgentContext

logger = logging.getLogger(__name__)


class ReconContextBuilder:
    """Builds minimal context for Recon Agent."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.analysis_repo = FindingAiAnalysisRepository(db)

    async def build(self, team_run_id: UUID, workspace_id: UUID, asset_id: UUID, scan_id: UUID, user_id: UUID) -> TeamAgentContext:
        """Build context with asset metadata, scan info, findings, and evidence."""
        context = TeamAgentContext(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            user_id=user_id,
            db=self.db,
        )
        
        # Get asset
        asset_result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        asset = asset_result.scalar_one_or_none()
        
        # Get scan
        scan_result = await self.db.execute(select(Scan).where(Scan.id == scan_id))
        scan = scan_result.scalar_one_or_none()
        
        # Get findings for this scan
        findings = await self.finding_repo.get_by_scan(scan_id)
        
        # Get evidence for all findings
        all_evidence = []
        all_analyses = []
        for finding in findings:
            evidence = await self.evidence_repo.get_by_finding(finding.id)
            all_evidence.extend(evidence)
            analysis = await self.analysis_repo.get_by_finding(finding.id)
            if analysis:
                all_analyses.extend(analysis)
        
        # Populate context with IDs for reference validation
        context.provided_finding_ids = {str(f.id) for f in findings}
        context.provided_evidence_ids = {str(e.id) for e in all_evidence}
        
        # Build minimal context data (stored in context.context for prompt building)
        context.context = {
            "asset": {
                "id": str(asset_id),
                "name": asset.name if asset else "Unknown",
                "type": asset.type.value if asset else "Unknown",
                "criticality": asset.criticality.value if asset else "Medium",
            } if asset else {},
            "scan": {
                "id": str(scan_id),
                "profile": scan.scan_profile.value if scan else "Unknown",
                "status": scan.status.value if scan else "Unknown",
            } if scan else {},
            "findings_summary": [
                {
                    "id": str(f.id),
                    "title": f.title,
                    "severity": f.severity.value,
                    "source": f.source.value,
                    "file": f.location.get("file") if f.location else None,
                    "component": self._extract_component(f.location.get("file") if f.location else None),
                }
                for f in findings[:50]  # Limit for context size
            ],
            "evidence_summary": [
                {
                    "id": str(e.id),
                    "finding_id": str(e.finding_id),
                    "type": e.evidence_type.value,
                    "title": e.title,
                    "file_path": e.file_path,
                }
                for e in all_evidence[:100]  # Limit for context size
            ],
            "ai_analyses_summary": [
                {
                    "finding_id": str(a.finding_id),
                    "vulnerability_type": a.vulnerability_type,
                    "severity_assessment": a.severity_assessment,
                    "confidence": a.confidence,
                }
                for a in all_analyses[:50]
            ],
        }
        
        return context

    def _extract_component(self, file_path: Optional[str]) -> Optional[str]:
        if not file_path:
            return None
        parts = file_path.split("/")
        if len(parts) >= 2:
            return parts[-2]
        return None


class VulnerabilityContextBuilder:
    """Builds context for Vulnerability Analyst Agent."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.evidence_repo = FindingEvidenceRepository(db)
        self.analysis_repo = FindingAiAnalysisRepository(db)

    async def build(self, team_run_id: UUID, workspace_id: UUID, asset_id: UUID, scan_id: UUID, user_id: UUID) -> TeamAgentContext:
        """Build context with findings and their evidence/analyses."""
        context = TeamAgentContext(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            user_id=user_id,
            db=self.db,
        )
        
        # Get findings for this scan
        findings = await self.finding_repo.get_by_scan(scan_id)
        
        # Build detailed context for each finding
        findings_data = []
        all_evidence_ids = set()
        all_finding_ids = set()
        
        for finding in findings:
            evidence = await self.evidence_repo.get_by_finding(finding.id)
            analysis = await self.analysis_repo.get_by_finding(finding.id)
            latest_analysis = analysis[0] if analysis else None
            
            finding_data = {
                "finding_id": str(finding.id),
                "title": finding.title,
                "description": finding.description,
                "severity": finding.severity.value,
                "source": finding.source.value,
                "source_rule_id": finding.source_rule_id,
                "location": finding.location,
                "code_snippet": finding.code_snippet,
                "cwe_ids": finding.cwe_ids,
                "owasp_categories": finding.owasp_categories,
                "remediation_guidance": finding.remediation_guidance,
                "evidence": [
                    {
                        "evidence_id": str(e.id),
                        "type": e.evidence_type.value,
                        "title": e.title,
                        "description": e.description,
                        "content": e.content,
                        "file_path": e.file_path,
                        "line_start": e.line_start,
                        "line_end": e.line_end,
                    }
                    for e in evidence
                ],
                "ai_analysis": {
                    "summary": latest_analysis.summary,
                    "vulnerability_type": latest_analysis.vulnerability_type,
                    "severity_assessment": latest_analysis.severity_assessment,
                    "confidence": latest_analysis.confidence,
                    "exploitability_assessment": latest_analysis.exploitability_assessment,
                    "impact_assessment": latest_analysis.impact_assessment,
                    "affected_component": latest_analysis.affected_component,
                    "attack_preconditions": latest_analysis.attack_preconditions,
                    "evidence_interpretation": latest_analysis.evidence_interpretation,
                    "reasoning": latest_analysis.reasoning,
                    "recommended_next_steps": latest_analysis.recommended_next_steps,
                    "uncertainty": latest_analysis.uncertainty,
                    "supporting_evidence": latest_analysis.supporting_evidence,
                } if latest_analysis else None,
            }
            findings_data.append(finding_data)
            all_finding_ids.add(str(finding.id))
            for e in evidence:
                all_evidence_ids.add(str(e.id))
        
        context.provided_finding_ids = all_finding_ids
        context.provided_evidence_ids = all_evidence_ids
        context.context = {
            "findings": findings_data,
        }
        
        return context


class AttackPathContextBuilder:
    """Builds context for Attack Path Agent."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.path_repo = AttackPathRepository(db)
        self.relationship_repo = FindingRelationshipRepository(db)

    async def build(self, team_run_id: UUID, workspace_id: UUID, asset_id: UUID, scan_id: UUID, user_id: UUID) -> TeamAgentContext:
        """Build context with attack paths, relationships, and findings."""
        context = TeamAgentContext(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            user_id=user_id,
            db=self.db,
        )
        
        # Get attack paths for this asset
        paths = await self.path_repo.get_by_asset(asset_id)
        
        # Get relationships for this workspace
        relationships = await self.relationship_repo.get_by_workspace(workspace_id, limit=200)
        
        # Get findings involved
        finding_ids = set()
        for path in paths:
            for node in path.nodes:
                if node.finding_id:
                    finding_ids.add(str(node.finding_id))
        for rel in relationships:
            finding_ids.add(str(rel.source_finding_id))
            finding_ids.add(str(rel.target_finding_id))
        
        context.provided_attack_path_ids = {str(p.id) for p in paths}
        context.provided_finding_ids = finding_ids
        
        # Build path summaries
        paths_data = []
        for path in paths:
            paths_data.append({
                "path_id": str(path.id),
                "title": path.title,
                "description": path.description,
                "status": path.status.value,
                "confidence": path.confidence,
                "severity": path.severity,
                "risk_score": path.risk_score,
                "nodes": [
                    {
                        "node_id": str(node.id),
                        "finding_id": str(node.finding_id) if node.finding_id else None,
                        "sequence": node.sequence,
                        "node_type": node.node_type.value,
                        "rationale": node.rationale,
                    }
                    for node in path.nodes
                ],
                "edges": [
                    {
                        "edge_id": str(edge.id),
                        "source_node_id": str(edge.source_node_id),
                        "target_node_id": str(edge.target_node_id),
                        "relationship_type": edge.relationship_type.value,
                        "confidence": edge.confidence,
                        "source": edge.source.value,
                        "rationale": edge.rationale,
                    }
                    for edge in path.edges
                ],
            })
        
        relationships_data = [
            {
                "id": str(r.id),
                "source_finding_id": str(r.source_finding_id),
                "target_finding_id": str(r.target_finding_id),
                "relationship_type": r.relationship_type.value,
                "confidence": r.confidence,
                "source": r.source.value,
                "rationale": r.rationale,
            }
            for r in relationships
        ]
        
        context.context = {
            "attack_paths": paths_data,
            "relationships": relationships_data,
        }
        
        return context


class RiskContextBuilder:
    """Builds context for Risk Analyst Agent."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.path_repo = AttackPathRepository(db)
        self.snapshot_repo = RiskSnapshotRepository(db)

    async def build(self, team_run_id: UUID, workspace_id: UUID, asset_id: UUID, scan_id: UUID, user_id: UUID) -> TeamAgentContext:
        """Build context with attack paths and their risk snapshots."""
        context = TeamAgentContext(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            user_id=user_id,
            db=self.db,
        )
        
        # Get attack paths for this asset
        paths = await self.path_repo.get_by_asset(asset_id)
        
        # Get latest risk snapshot for each path
        paths_data = []
        path_ids = set()
        
        for path in paths:
            snapshot = await self.snapshot_repo.get_latest_by_attack_path(path.id)
            path_ids.add(str(path.id))
            
            paths_data.append({
                "path_id": str(path.id),
                "title": path.title,
                "description": path.description,
                "status": path.status.value,
                "confidence": path.confidence,
                "severity": path.severity,
                "risk_score": path.risk_score,
                "risk_model_version": path.risk_model_version,
                "nodes": [
                    {
                        "node_id": str(node.id),
                        "finding_id": str(node.finding_id) if node.finding_id else None,
                        "sequence": node.sequence,
                        "node_type": node.node_type.value,
                        "rationale": node.rationale,
                    }
                    for node in path.nodes
                ],
                "edges": [
                    {
                        "edge_id": str(edge.id),
                        "source_node_id": str(edge.source_node_id),
                        "target_node_id": str(edge.target_node_id),
                        "relationship_type": edge.relationship_type.value,
                        "confidence": edge.confidence,
                        "source": edge.source.value,
                        "rationale": edge.rationale,
                    }
                    for edge in path.edges
                ],
                "latest_risk_snapshot": {
                    "score": snapshot.score,
                    "risk_band": snapshot.risk_band,
                    "model_version": snapshot.model_version,
                    "factors": snapshot.factors,
                    "calculated_at": snapshot.calculated_at.isoformat(),
                } if snapshot else None,
            })
        
        context.provided_attack_path_ids = path_ids
        context.context = {
            "attack_paths": paths_data,
        }
        
        return context


class ReviewerContextBuilder:
    """Builds context for Security Reviewer Agent (final assessment)."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        # Will load all previous agent outputs from agent_runs table
        from app.repositories import AgentRunRepository
        self.agent_run_repo = AgentRunRepository(db)

    async def build(self, team_run_id: UUID, workspace_id: UUID, asset_id: UUID, scan_id: UUID, user_id: UUID) -> TeamAgentContext:
        """Build context with all previous agent outputs."""
        context = TeamAgentContext(
            team_run_id=team_run_id,
            workspace_id=workspace_id,
            asset_id=asset_id,
            scan_id=scan_id,
            user_id=user_id,
            db=self.db,
        )
        
        # Get all agent runs for this team run
        agent_runs = await self.agent_run_repo.get_by_team_run(team_run_id)
        
        # Collect all referenced IDs
        all_finding_ids = set()
        all_evidence_ids = set()
        all_path_ids = set()
        agent_outputs = {}
        
        for run in agent_runs:
            if run.status.value == "succeeded" and run.output:
                agent_outputs[run.agent_name.value] = run.output
                # Extract references from output
                self._extract_references(run.output, all_finding_ids, all_evidence_ids, all_path_ids)
        
        context.provided_finding_ids = all_finding_ids
        context.provided_evidence_ids = all_evidence_ids
        context.provided_attack_path_ids = all_path_ids
        context.context = {
            "agent_outputs": agent_outputs,
        }
        
        return context

    def _extract_references(self, output: Dict[str, Any], finding_ids: Set[str], evidence_ids: Set[str], path_ids: Set[str]):
        """Recursively extract ID references from agent output."""
        if isinstance(output, dict):
            for key, value in output.items():
                if key in ("finding_id", "source_finding_id", "target_finding_id") and isinstance(value, str):
                    finding_ids.add(value)
                elif key == "evidence_id" and isinstance(value, str):
                    evidence_ids.add(value)
                elif key in ("path_id", "attack_path_id", "source_node_id", "target_node_id") and isinstance(value, str):
                    path_ids.add(value)
                elif isinstance(value, (dict, list)):
                    self._extract_references(value, finding_ids, evidence_ids, path_ids)
        elif isinstance(output, list):
            for item in output:
                self._extract_references(item, finding_ids, evidence_ids, path_ids)

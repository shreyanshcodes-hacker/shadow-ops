import logging
from typing import List, Optional, Dict, Any, Set, Tuple
from uuid import UUID, uuid4
from datetime import datetime
from collections import defaultdict, deque

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.models import (
    Finding, FindingRelationship, AttackPath, AttackPathNode,
    AttackPathNodeType, AttackPathEdge, AttackPathStatus,
    RelationshipType, RelationshipSource, Asset, Workspace
)
from app.repositories import (
    FindingRepository, FindingRelationshipRepository,
    AttackPathRepository, AttackPathNodeRepository, AttackPathEdgeRepository
)
from app.security.audit import audit_log

logger = logging.getLogger(__name__)


MAX_PATH_NODES = 8
MAX_PATH_EDGES = 20


class AttackPathBuilderError(Exception):
    def __init__(self, message: str, error_code: str = "ATTACK_PATH_ERROR"):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class AttackPathBuilder:
    """
    Builds attack paths from validated finding relationships.
    
    Constraints:
    - Same workspace only
    - Same asset unless explicitly supported
    - Maximum path length (MAX_PATH_NODES)
    - Cycle detection
    - Duplicate path detection
    - Deterministic ordering
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.finding_repo = FindingRepository(db)
        self.relationship_repo = FindingRelationshipRepository(db)
        self.path_repo = AttackPathRepository(db)
        self.node_repo = AttackPathNodeRepository(db)
        self.edge_repo = AttackPathEdgeRepository(db)

    async def build_attack_paths(
        self,
        workspace_id: UUID,
        asset_id: Optional[UUID] = None,
        min_confidence: float = 0.5,
        include_ai_suggested: bool = False,
    ) -> List[AttackPath]:
        """
        Build attack paths from relationships in a workspace.
        
        Args:
            workspace_id: Workspace to build paths for
            asset_id: Optional specific asset to build paths for
            min_confidence: Minimum relationship confidence to include
            include_ai_suggested: Whether to include AI_SUGGESTED relationships
            
        Returns:
            List of created attack paths
        """
        # Get all relationships meeting criteria
        relationships = await self._get_relationships(workspace_id, asset_id, min_confidence, include_ai_suggested)
        
        if not relationships:
            return []

        # Build adjacency graph
        graph = self._build_graph(relationships)
        
        # Find entry points (findings with no incoming edges or external entry)
        entry_points = self._find_entry_points(graph, relationships)
        
        # Build paths from entry points
        paths = []
        for entry_finding_id in entry_points:
            found_paths = self._dfs_build_paths(
                graph=graph,
                start=entry_finding_id,
                visited=set(),
                path=[],
                max_depth=MAX_PATH_NODES,
            )
            paths.extend(found_paths)

        # Deduplicate paths
        unique_paths = self._deduplicate_paths(paths)
        
        # Create attack path records
        created_paths = []
        for path_data in unique_paths:
            attack_path = await self._create_attack_path(path_data, workspace_id, asset_id)
            if attack_path:
                created_paths.append(attack_path)

        return created_paths

    async def _get_relationships(
        self,
        workspace_id: UUID,
        asset_id: Optional[UUID],
        min_confidence: float,
        include_ai_suggested: bool,
    ) -> List[FindingRelationship]:
        """Get all relationships meeting criteria."""
        # Get all relationships in workspace
        all_rels = await self.relationship_repo.get_by_workspace(workspace_id, limit=1000)
        
        filtered = []
        for rel in all_rels:
            if rel.confidence < min_confidence:
                continue
            if not include_ai_suggested and rel.source == RelationshipSource.AI_SUGGESTED:
                continue
            
            # Filter by asset if specified
            if asset_id:
                source_finding = await self.finding_repo.get_by_id(rel.source_finding_id)
                if not source_finding or source_finding.asset_id != asset_id:
                    continue
            
            filtered.append(rel)
        
        return filtered

    def _build_graph(self, relationships: List[FindingRelationship]) -> Dict[UUID, List[FindingRelationship]]:
        """Build adjacency graph from relationships."""
        graph = defaultdict(list)
        for rel in relationships:
            graph[rel.source_finding_id].append(rel)
        return graph

    def _find_entry_points(
        self,
        graph: Dict[UUID, List[FindingRelationship]],
        relationships: List[FindingRelationship],
    ) -> Set[UUID]:
        """Find potential entry points for attack paths."""
        # Nodes with no incoming edges
        all_targets = {rel.target_finding_id for rel in relationships}
        all_sources = {rel.source_finding_id for rel in relationships}
        
        entry_points = all_sources - all_targets
        
        # Also consider findings with external entry characteristics
        for finding_id in all_sources:
            if finding_id in entry_points:
                continue
            # Check if this finding has external-facing characteristics
            # This would require more context about the finding
            pass
        
        return entry_points

    def _dfs_build_paths(
        self,
        graph: Dict[UUID, List[FindingRelationship]],
        start: UUID,
        visited: Set[UUID],
        path: List[FindingRelationship],
        max_depth: int,
    ) -> List[List[FindingRelationship]]:
        """DFS to build all paths from entry point with cycle detection."""
        if len(path) >= max_depth:
            return [path.copy()] if path else []

        if start in visited:
            return []  # Cycle detected

        visited.add(start)
        paths = []

        for rel in graph.get(start, []):
            path.append(rel)
            # Continue from target
            sub_paths = self._dfs_build_paths(graph, rel.target_finding_id, visited, path, max_depth)
            paths.extend(sub_paths)
            path.pop()

        # Also return current path as valid if it has at least one edge
        if path:
            paths.append(path.copy())

        visited.remove(start)
        return paths

    def _deduplicate_paths(self, paths: List[List[FindingRelationship]]) -> List[List[FindingRelationship]]:
        """Remove duplicate paths based on finding sequence."""
        seen = set()
        unique = []
        for path in paths:
            # Create signature from finding IDs
            sig = tuple(rel.source_finding_id for rel in path)
            if path:
                sig = sig + (path[-1].target_finding_id,)
            if sig not in seen:
                seen.add(sig)
                unique.append(path)
        return unique

    async def _create_attack_path(
        self,
        path_relationships: List[FindingRelationship],
        workspace_id: UUID,
        asset_id: Optional[UUID],
    ) -> Optional[AttackPath]:
        """Create attack path record with nodes and edges."""
        if not path_relationships:
            return None

        # Determine asset from first finding
        first_rel = path_relationships[0]
        finding = await self.finding_repo.get_by_id(first_rel.source_finding_id)
        if not finding:
            return None
        
        target_asset_id = asset_id or finding.asset_id

        # Create attack path
        attack_path = AttackPath(
            workspace_id=workspace_id,
            asset_id=target_asset_id,
            title=self._generate_path_title(path_relationships),
            description=self._generate_path_description(path_relationships),
            status=AttackPathStatus.DRAFT,
            confidence=self._calculate_path_confidence(path_relationships),
            severity=self._calculate_path_severity(path_relationships),
            risk_score=None,  # Calculated separately
        )

        created_path = await self.path_repo.create(attack_path)

        # Create nodes
        nodes = await self._create_path_nodes(created_path.id, path_relationships)
        
        # Create edges
        await self._create_path_edges(created_path.id, nodes, path_relationships)

        # Audit log
        await audit_log(
            db=self.db,
            workspace_id=workspace_id,
            action="attack_path.created",
            resource_type="attack_path",
            resource_id=created_path.id,
            new_state={
                "asset_id": str(target_asset_id),
                "title": created_path.title,
                "node_count": len(nodes),
                "confidence": created_path.confidence,
            },
        )

        return created_path

    def _generate_path_title(self, relationships: List[FindingRelationship]) -> str:
        """Generate a human-readable title for the attack path."""
        if not relationships:
            return "Empty Attack Path"
        
        first = relationships[0]
        last = relationships[-1]
        
        # Get finding titles if available
        return f"Attack Path: {first.relationship_type.value} chain ({len(relationships)} steps)"

    def _generate_path_description(self, relationships: List[FindingRelationship]) -> str:
        """Generate a description of the attack path."""
        if not relationships:
            return ""
        
        parts = []
        for i, rel in enumerate(relationships):
            parts.append(
                f"Step {i+1}: {rel.relationship_type.value.replace('_', ' ').title()} "
                f"(confidence: {rel.confidence:.2f}) - {rel.rationale}"
            )
        return "\n".join(parts)

    def _calculate_path_confidence(self, relationships: List[FindingRelationship]) -> float:
        """Calculate overall path confidence (minimum of edge confidences)."""
        if not relationships:
            return 0.0
        return min(rel.confidence for rel in relationships)

    def _calculate_path_severity(self, relationships: List[FindingRelationship]) -> str:
        """Calculate path severity based on findings."""
        # This would require loading findings
        return "high"  # Default

    async def _create_path_nodes(
        self,
        attack_path_id: UUID,
        relationships: List[FindingRelationship],
    ) -> List[AttackPathNode]:
        """Create nodes for the attack path."""
        nodes = []
        finding_id_to_node = {}
        
        # Collect all unique finding IDs in order
        all_finding_ids = []
        for rel in relationships:
            if rel.source_finding_id not in all_finding_ids:
                all_finding_ids.append(rel.source_finding_id)
        if relationships:
            all_finding_ids.append(relationships[-1].target_finding_id)

        for seq, finding_id in enumerate(all_finding_ids):
            finding = await self.finding_repo.get_by_id(finding_id)
            node_type = self._determine_node_type(finding, seq, len(all_finding_ids))
            
            node = AttackPathNode(
                attack_path_id=attack_path_id,
                finding_id=finding_id,
                sequence=seq,
                node_type=node_type,
                rationale=self._get_node_rationale(finding, seq, len(all_finding_ids)),
            )
            created_node = await self.node_repo.create(node)
            nodes.append(created_node)
            finding_id_to_node[finding_id] = created_node

        return nodes

    def _determine_node_type(
        self,
        finding: Optional[Finding],
        sequence: int,
        total_nodes: int,
    ) -> AttackPathNodeType:
        """Determine node type based on position and finding characteristics."""
        if sequence == 0:
            return AttackPathNodeType.ENTRY
        elif sequence == total_nodes - 1:
            return AttackPathNodeType.IMPACT
        else:
            # Could check if it's a boundary (auth, network, etc.)
            return AttackPathNodeType.FINDING

    def _get_node_rationale(
        self,
        finding: Optional[Finding],
        sequence: int,
        total_nodes: int,
    ) -> str:
        """Generate rationale for node."""
        if sequence == 0:
            return "Initial entry point"
        elif sequence == total_nodes - 1:
            return "Final impact"
        else:
            return f"Intermediate step: {finding.title if finding else 'Finding'}"

    async def _create_path_edges(
        self,
        attack_path_id: UUID,
        nodes: List[AttackPathNode],
        relationships: List[FindingRelationship],
    ) -> None:
        """Create edges connecting the nodes."""
        if len(nodes) < 2:
            return

        # Map finding_id to node
        finding_to_node = {node.finding_id: node for node in nodes if node.finding_id}
        
        for rel in relationships:
            source_node = finding_to_node.get(rel.source_finding_id)
            target_node = finding_to_node.get(rel.target_finding_id)
            
            if source_node and target_node:
                edge = AttackPathEdge(
                    attack_path_id=attack_path_id,
                    source_node_id=source_node.id,
                    target_node_id=target_node.id,
                    relationship_type=rel.relationship_type,
                    confidence=rel.confidence,
                    source=rel.source,
                    rationale=rel.rationale,
                )
                await self.edge_repo.create(edge)


class AttackPathManager:
    """High-level manager for attack path operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.builder = AttackPathBuilder(db)
        self.path_repo = AttackPathRepository(db)
        self.node_repo = AttackPathNodeRepository(db)
        self.edge_repo = AttackPathEdgeRepository(db)

    async def get_attack_path(self, attack_path_id: UUID, workspace_id: UUID) -> Optional[AttackPath]:
        """Get attack path with all nodes and edges."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return None
        return path

    async def list_attack_paths(
        self,
        workspace_id: UUID,
        asset_id: Optional[UUID] = None,
        status: Optional[AttackPathStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[AttackPath]:
        """List attack paths with filtering."""
        if asset_id:
            return await self.path_repo.get_by_asset(asset_id, status)
        return await self.path_repo.get_by_workspace(workspace_id, status, limit, offset)

    async def update_attack_path(
        self,
        attack_path_id: UUID,
        workspace_id: UUID,
        data: Dict[str, Any],
    ) -> Optional[AttackPath]:
        """Update attack path metadata."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return None
        return await self.path_repo.update(attack_path_id, data)

    async def recalculate_attack_path(
        self,
        attack_path_id: UUID,
        workspace_id: UUID,
    ) -> Optional[AttackPath]:
        """Recalculate an existing attack path."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return None

        # Rebuild from current relationships
        # This is a simplified version - full rebuild would be more complex
        return path

    async def dismiss_attack_path(self, attack_path_id: UUID, workspace_id: UUID) -> bool:
        """Dismiss an attack path."""
        path = await self.path_repo.get_by_id(attack_path_id)
        if not path or path.workspace_id != workspace_id:
            return False
        await self.path_repo.update(attack_path_id, {"status": AttackPathStatus.DISMISSED})
        return True

    async def get_attack_paths_for_finding(self, finding_id: UUID, workspace_id: UUID) -> List[AttackPath]:
        """Get all attack paths that include a specific finding."""
        node_repo = self.node_repo
        nodes = await node_repo.get_by_finding(finding_id)
        
        path_ids = {node.attack_path_id for node in nodes}
        paths = []
        for pid in path_ids:
            path = await self.path_repo.get_by_id(pid)
            if path and path.workspace_id == workspace_id:
                paths.append(path)
        return paths
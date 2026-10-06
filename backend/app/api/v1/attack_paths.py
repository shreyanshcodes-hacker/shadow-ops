from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional, Dict, Any

from app.db.session import get_db
from app.security.auth import get_current_user, require_workspace_member
from app.services import WorkspaceService
from app.repositories import (
    FindingRepository, FindingRelationshipRepository,
    AttackPathRepository, AttackPathNodeRepository, AttackPathEdgeRepository,
    RiskSnapshotRepository
)
from app.services.attack_path import AttackPathManager, AttackPathBuilder
from app.services.correlation import CorrelationEngine, AIRelationshipAnalyzer
from app.services.risk import RiskManager, RiskEngine
from app.models import (
    Finding, FindingRelationship, RelationshipType, RelationshipSource,
    AttackPath, AttackPathStatus, AttackPathNode, AttackPathEdge,
    RiskSnapshot, RiskBand, Asset
)
from app.schemas import (
    FindingRelationshipResponse, FindingRelationshipCreate,
    AttackPathResponse, AttackPathCreate, AttackPathUpdate,
    AttackPathListResponse, AttackPathNodeResponse, AttackPathEdgeResponse,
    RiskSnapshotResponse, RiskCalculationResult,
    RelationshipConfirmRequest, RelationshipDismissRequest,
)
from app.security.audit import audit_log

router = APIRouter(prefix="/attack-paths", tags=["Attack Paths"])


# Finding Relationships
@router.get("/findings/{finding_id}/relationships", response_model=List[FindingRelationshipResponse])
async def list_finding_relationships(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all relationships for a finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    rel_repo = FindingRelationshipRepository(db)
    relationships = await rel_repo.get_by_finding(finding_id)

    # Load related findings for response
    result = []
    for rel in relationships:
        source_finding = await finding_repo.get_by_id(rel.source_finding_id)
        target_finding = await finding_repo.get_by_id(rel.target_finding_id)
        result.append(FindingRelationshipResponse(
            id=rel.id,
            workspace_id=rel.workspace_id,
            source_finding_id=rel.source_finding_id,
            target_finding_id=rel.target_finding_id,
            relationship_type=rel.relationship_type,
            confidence=rel.confidence,
            source=rel.source,
            rationale=rel.rationale,
            evidence_reference=rel.evidence_reference,
            created_at=rel.created_at,
            updated_at=rel.updated_at,
            source_finding=source_finding,
            target_finding=target_finding,
        ))
    return result


@router.post("/relationships/{relationship_id}/confirm", response_model=FindingRelationshipResponse)
async def confirm_relationship(
    relationship_id: UUID,
    request: RelationshipConfirmRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm an AI-suggested relationship (human confirmation)."""
    rel_repo = FindingRelationshipRepository(db)
    relationship = await rel_repo.get_by_id(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(relationship.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    if relationship.source != RelationshipSource.AI_SUGGESTED:
        raise HTTPException(status_code=400, detail="Only AI-suggested relationships can be confirmed")

    updated = await rel_repo.update(relationship_id, {"source": RelationshipSource.HUMAN_CONFIRMED})
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update relationship")

    await audit_log(
        db=db,
        workspace_id=relationship.workspace_id,
        action="relationship.confirmed",
        resource_type="finding_relationship",
        resource_id=relationship_id,
        new_state={"source": "human_confirmed"},
        user_id=current_user.id,
    )

    return FindingRelationshipResponse.model_validate(updated)


@router.post("/relationships/{relationship_id}/dismiss", response_model=FindingRelationshipResponse)
async def dismiss_relationship(
    relationship_id: UUID,
    request: RelationshipDismissRequest,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dismiss an AI-suggested relationship."""
    rel_repo = FindingRelationshipRepository(db)
    relationship = await rel_repo.get_by_id(relationship_id)
    if not relationship:
        raise HTTPException(status_code=404, detail="Relationship not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(relationship.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    if relationship.source != RelationshipSource.AI_SUGGESTED:
        raise HTTPException(status_code=400, detail="Only AI-suggested relationships can be dismissed")

    # Delete the relationship
    await rel_repo.delete(relationship_id)

    await audit_log(
        db=db,
        workspace_id=relationship.workspace_id,
        action="relationship.dismissed",
        resource_type="finding_relationship",
        resource_id=relationship_id,
        new_state={"dismissed": True},
        user_id=current_user.id,
    )

    return FindingRelationshipResponse.model_validate(relationship)


# Attack Paths
@router.get("", response_model=List[AttackPathListResponse])
async def list_attack_paths(
    workspace_id: UUID,
    asset_id: Optional[UUID] = Query(None),
    status: Optional[AttackPathStatus] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List attack paths for a workspace."""
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    manager = AttackPathManager(db)
    paths = await manager.list_attack_paths(workspace_id, asset_id, status, limit, offset)

    # Convert to list response with node count
    result = []
    for path in paths:
        node_count = len(path.nodes) if path.nodes else 0
        # Determine risk band from score
        risk_band = None
        if path.risk_score is not None:
            for min_s, max_s, band in RiskEngine.RISK_BANDS:
                if min_s <= path.risk_score <= max_s:
                    risk_band = band
                    break

        result.append(AttackPathListResponse(
            id=path.id,
            workspace_id=path.workspace_id,
            asset_id=path.asset_id,
            title=path.title,
            status=path.status,
            confidence=path.confidence,
            severity=path.severity,
            risk_score=path.risk_score,
            risk_band=risk_band,
            node_count=node_count,
            created_at=path.created_at,
            updated_at=path.updated_at,
        ))
    return result


@router.post("", response_model=AttackPathResponse, status_code=status.HTTP_201_CREATED)
async def create_attack_path(
    workspace_id: UUID,
    request: AttackPathCreate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new attack path (manual creation)."""
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    # Verify asset belongs to workspace
    from app.repositories import AssetRepository
    asset_repo = AssetRepository(db)
    asset = await asset_repo.get_by_id(request.asset_id)
    if not asset or asset.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    manager = AttackPathManager(db)
    path = AttackPath(
        workspace_id=workspace_id,
        asset_id=request.asset_id,
        title=request.title,
        description=request.description,
        status=request.status,
        confidence=request.confidence,
        severity=request.severity,
    )
    created = await manager.path_repo.create(path)

    await audit_log(
        db=db,
        workspace_id=workspace_id,
        action="attack_path.created",
        resource_type="attack_path",
        resource_id=created.id,
        new_state={"title": request.title, "asset_id": str(request.asset_id)},
        user_id=current_user.id,
    )

    return AttackPathResponse.model_validate(created)


@router.get("/{attack_path_id}", response_model=AttackPathResponse)
async def get_attack_path(
    attack_path_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get attack path with full details."""
    manager = AttackPathManager(db)
    path = await manager.get_attack_path(attack_path_id, UUID("00000000-0000-0000-0000-000000000000"))  # Will check workspace inside

    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    return AttackPathResponse.model_validate(path)


@router.patch("/{attack_path_id}", response_model=AttackPathResponse)
async def update_attack_path(
    attack_path_id: UUID,
    request: AttackPathUpdate,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update attack path metadata."""
    manager = AttackPathManager(db)
    path = await manager.path_repo.get_by_id(attack_path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    update_data = {}
    if request.title is not None:
        update_data["title"] = request.title
    if request.description is not None:
        update_data["description"] = request.description
    if request.status is not None:
        update_data["status"] = request.status
    if request.confidence is not None:
        update_data["confidence"] = request.confidence
    if request.severity is not None:
        update_data["severity"] = request.severity

    updated = await manager.path_repo.update(attack_path_id, update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update attack path")

    await audit_log(
        db=db,
        workspace_id=path.workspace_id,
        action="attack_path.updated",
        resource_type="attack_path",
        resource_id=attack_path_id,
        new_state=update_data,
        user_id=current_user.id,
    )

    return AttackPathResponse.model_validate(updated)


@router.get("/{attack_path_id}/nodes", response_model=List[AttackPathNodeResponse])
async def get_attack_path_nodes(
    attack_path_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all nodes for an attack path."""
    manager = AttackPathManager(db)
    path = await manager.get_attack_path(attack_path_id, UUID("00000000-0000-0000-0000-000000000000"))
    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    nodes = await manager.node_repo.get_by_attack_path(attack_path_id)
    result = []
    for node in nodes:
        finding = None
        if node.finding_id:
            finding = await FindingRepository(db).get_by_id(node.finding_id)
        result.append(AttackPathNodeResponse(
            id=node.id,
            attack_path_id=node.attack_path_id,
            finding_id=node.finding_id,
            sequence=node.sequence,
            node_type=node.node_type,
            rationale=node.rationale,
            created_at=node.created_at,
            updated_at=node.updated_at,
            finding=finding,
        ))
    return result


@router.get("/{attack_path_id}/edges", response_model=List[AttackPathEdgeResponse])
async def get_attack_path_edges(
    attack_path_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all edges (relationships) for an attack path."""
    manager = AttackPathManager(db)
    path = await manager.get_attack_path(attack_path_id, UUID("00000000-0000-0000-0000-000000000000"))
    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    edges = await manager.edge_repo.get_by_attack_path(attack_path_id)
    result = []
    for edge in edges:
        source_node = None
        target_node = None
        if edge.source_node:
            source_node = AttackPathNodeResponse.model_validate(edge.source_node)
        if edge.target_node:
            target_node = AttackPathNodeResponse.model_validate(edge.target_node)
        result.append(AttackPathEdgeResponse(
            id=edge.id,
            attack_path_id=edge.attack_path_id,
            source_node_id=edge.source_node_id,
            target_node_id=edge.target_node_id,
            relationship_type=edge.relationship_type,
            confidence=edge.confidence,
            source=edge.source,
            rationale=edge.rationale,
            created_at=edge.created_at,
            source_node=source_node,
            target_node=target_node,
        ))
    return result


@router.post("/{attack_path_id}/recalculate-risk", response_model=RiskCalculationResult)
async def recalculate_risk(
    attack_path_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Recalculate risk score for an attack path."""
    manager = AttackPathManager(db)
    path = await manager.path_repo.get_by_id(attack_path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    risk_manager = RiskManager(db)
    result = await risk_manager.calculate_and_persist_risk(attack_path_id, path.workspace_id, current_user.id)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to calculate risk")

    return result


@router.get("/{attack_path_id}/risk-history", response_model=List[RiskSnapshotResponse])
async def get_risk_history(
    attack_path_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get risk calculation history for an attack path."""
    manager = AttackPathManager(db)
    path = await manager.path_repo.get_by_id(attack_path_id)
    if not path:
        raise HTTPException(status_code=404, detail="Attack path not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(path.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    risk_manager = RiskManager(db)
    snapshots = await risk_manager.get_risk_history(attack_path_id, path.workspace_id)
    return [RiskSnapshotResponse.model_validate(s) for s in snapshots]


# Correlation Engine
@router.post("/correlate/{finding_id}", response_model=List[FindingRelationshipResponse])
async def correlate_finding(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run deterministic correlation for a finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    engine = CorrelationEngine(db)
    relationships = await engine.find_relationships_for_finding(finding_id, finding.workspace_id)

    # Persist relationships
    rel_repo = FindingRelationshipRepository(db)
    created = []
    for rel in relationships:
        try:
            created_rel = await rel_repo.create(rel)
            created.append(created_rel)
        except Exception as e:
            logger.warning(f"Failed to create relationship: {e}")

    await audit_log(
        db=db,
        workspace_id=finding.workspace_id,
        action="correlation.executed",
        resource_type="finding",
        resource_id=finding_id,
        new_state={"relationships_found": len(relationships), "relationships_created": len(created)},
        user_id=current_user.id,
    )

    return [FindingRelationshipResponse.model_validate(r) for r in created]


@router.post("/correlate/workspace/{workspace_id}", response_model=List[FindingRelationshipResponse])
async def correlate_workspace(
    workspace_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run deterministic correlation for all findings in a workspace."""
    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    engine = CorrelationEngine(db)
    relationships = await engine.find_all_relationships(workspace_id)

    # Persist relationships
    rel_repo = FindingRelationshipRepository(db)
    created = []
    for rel in relationships:
        try:
            created_rel = await rel_repo.create(rel)
            created.append(created_rel)
        except Exception as e:
            logger.warning(f"Failed to create relationship: {e}")

    await audit_log(
        db=db,
        workspace_id=workspace_id,
        action="correlation.executed",
        resource_type="workspace",
        resource_id=workspace_id,
        new_state={"relationships_found": len(relationships), "relationships_created": len(created)},
        user_id=current_user.id,
    )

    return [FindingRelationshipResponse.model_validate(r) for r in created]


@router.post("/correlate/ai/{finding_a_id}/{finding_b_id}", response_model=FindingRelationshipResponse)
async def ai_correlate_findings(
    finding_a_id: UUID,
    finding_b_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run AI correlation between two specific findings."""
    finding_repo = FindingRepository(db)
    finding_a = await finding_repo.get_by_id(finding_a_id)
    finding_b = await finding_repo.get_by_id(finding_b_id)
    if not finding_a or not finding_b:
        raise HTTPException(status_code=404, detail="Finding not found")

    if finding_a.workspace_id != finding_b.workspace_id:
        raise HTTPException(status_code=400, detail="Findings must be in same workspace")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding_a.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    analyzer = AIRelationshipAnalyzer(db)
    relationship = await analyzer.analyze_relationship(
        finding_a_id, finding_b_id, finding_a.workspace_id, current_user.id
    )

    if not relationship:
        raise HTTPException(status_code=404, detail="No AI relationship found")

    # Persist
    rel_repo = FindingRelationshipRepository(db)
    created = await rel_repo.create(relationship)

    await audit_log(
        db=db,
        workspace_id=finding_a.workspace_id,
        action="relationship.ai_suggested",
        resource_type="finding_relationship",
        resource_id=created.id,
        new_state={
            "source_finding": str(finding_a_id),
            "target_finding": str(finding_b_id),
            "type": created.relationship_type.value,
            "confidence": created.confidence,
        },
        user_id=current_user.id,
    )

    return FindingRelationshipResponse.model_validate(created)


# Attack Path Generation
@router.post("/generate/{asset_id}", response_model=List[AttackPathListResponse])
async def generate_attack_paths(
    asset_id: UUID,
    min_confidence: float = Query(0.5, ge=0.0, le=1.0),
    include_ai_suggested: bool = Query(False),
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate attack paths for an asset from existing relationships."""
    from app.repositories import AssetRepository
    asset_repo = AssetRepository(db)
    asset = await asset_repo.get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(asset.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    builder = AttackPathBuilder(db)
    paths = await builder.build_attack_paths(
        workspace_id=asset.workspace_id,
        asset_id=asset_id,
        min_confidence=min_confidence,
        include_ai_suggested=include_ai_suggested,
    )

    await audit_log(
        db=db,
        workspace_id=asset.workspace_id,
        action="attack_path.generated",
        resource_type="asset",
        resource_id=asset_id,
        new_state={"paths_created": len(paths)},
        user_id=current_user.id,
    )

    # Convert to list response
    result = []
    for path in paths:
        node_count = len(path.nodes) if path.nodes else 0
        risk_band = None
        if path.risk_score is not None:
            for min_s, max_s, band in RiskEngine.RISK_BANDS:
                if min_s <= path.risk_score <= max_s:
                    risk_band = band
                    break
        result.append(AttackPathListResponse(
            id=path.id,
            workspace_id=path.workspace_id,
            asset_id=path.asset_id,
            title=path.title,
            status=path.status,
            confidence=path.confidence,
            severity=path.severity,
            risk_score=path.risk_score,
            risk_band=risk_band,
            node_count=node_count,
            created_at=path.created_at,
            updated_at=path.updated_at,
        ))
    return result


# Finding -> Attack Paths
@router.get("/findings/{finding_id}/attack-paths", response_model=List[AttackPathListResponse])
async def get_attack_paths_for_finding(
    finding_id: UUID,
    current_user = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all attack paths that include a specific finding."""
    finding_repo = FindingRepository(db)
    finding = await finding_repo.get_by_id(finding_id)
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    ws_service = WorkspaceService(db)
    ws_member = await ws_service.get_member(finding.workspace_id, current_user.id)
    if not ws_member or ws_member.joined_at is None:
        raise HTTPException(status_code=403, detail="Not a member of this workspace")

    manager = AttackPathManager(db)
    paths = await manager.get_attack_paths_for_finding(finding_id, finding.workspace_id)

    result = []
    for path in paths:
        node_count = len(path.nodes) if path.nodes else 0
        risk_band = None
        if path.risk_score is not None:
            for min_s, max_s, band in RiskEngine.RISK_BANDS:
                if min_s <= path.risk_score <= max_s:
                    risk_band = band
                    break
        result.append(AttackPathListResponse(
            id=path.id,
            workspace_id=path.workspace_id,
            asset_id=path.asset_id,
            title=path.title,
            status=path.status,
            confidence=path.confidence,
            severity=path.severity,
            risk_score=path.risk_score,
            risk_band=risk_band,
            node_count=node_count,
            created_at=path.created_at,
            updated_at=path.updated_at,
        ))
    return result
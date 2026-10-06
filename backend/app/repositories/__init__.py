from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload

from app.models import Profile, Workspace, WorkspaceMember, Asset, AssetAuthorization, WorkspaceRole, AuthorizationStatus, Scan, ScanEvent, Finding, FindingEvidence, ScanTarget, ScanStatus, ScanProfile, ScanEventType, FindingSource, FindingSeverity, FindingConfidence, FindingStatus, FindingEvidenceType, AiRun, FindingAiAnalysis, AiProviderType, AiOperationType, AiRunStatus, FindingRelationship, RelationshipType, RelationshipSource, AttackPath, AttackPathStatus, AttackPathNode, AttackPathNodeType, AttackPathEdge, RiskSnapshot


class ProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: UUID) -> Optional[Profile]:
        result = await self.db.execute(select(Profile).where(Profile.id == profile_id))
        return result.scalar_one_or_none()

    async def get_by_firebase_uid(self, firebase_uid: str) -> Optional[Profile]:
        result = await self.db.execute(select(Profile).where(Profile.firebase_uid == firebase_uid))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[Profile]:
        result = await self.db.execute(select(Profile).where(Profile.email == email))
        return result.scalar_one_or_none()

    async def create(self, profile: Profile) -> Profile:
        self.db.add(profile)
        await self.db.flush()
        await self.db.refresh(profile)
        return profile

    async def update(self, profile_id: UUID, data: Dict[str, Any]) -> Optional[Profile]:
        result = await self.db.execute(
            update(Profile).where(Profile.id == profile_id).values(**data).returning(Profile)
        )
        return result.scalar_one_or_none()

    async def update_last_login(self, profile_id: UUID) -> None:
        await self.db.execute(
            update(Profile).where(Profile.id == profile_id).values(last_login_at=datetime.utcnow())
        )


class WorkspaceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, workspace_id: UUID) -> Optional[Workspace]:
        result = await self.db.execute(select(Workspace).where(Workspace.id == workspace_id))
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Optional[Workspace]:
        result = await self.db.execute(select(Workspace).where(Workspace.slug == slug))
        return result.scalar_one_or_none()

    async def get_by_owner(self, owner_id: UUID) -> List[Workspace]:
        result = await self.db.execute(
            select(Workspace).where(Workspace.owner_id == owner_id, Workspace.deleted_at.is_(None))
        )
        return list(result.scalars().all())

    async def get_user_workspaces(self, user_id: UUID) -> List[Workspace]:
        result = await self.db.execute(
            select(Workspace)
            .join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id)
            .where(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.joined_at.is_not(None),
                Workspace.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def create(self, workspace: Workspace) -> Workspace:
        self.db.add(workspace)
        await self.db.flush()
        await self.db.refresh(workspace)
        return workspace

    async def update(self, workspace_id: UUID, data: Dict[str, Any]) -> Optional[Workspace]:
        result = await self.db.execute(
            update(Workspace).where(Workspace.id == workspace_id).values(**data).returning(Workspace)
        )
        return result.scalar_one_or_none()

    async def soft_delete(self, workspace_id: UUID) -> bool:
        result = await self.db.execute(
            update(Workspace)
            .where(Workspace.id == workspace_id)
            .values(deleted_at=datetime.utcnow())
        )
        return result.rowcount > 0


class WorkspaceMemberRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, member_id: UUID) -> Optional[WorkspaceMember]:
        result = await self.db.execute(select(WorkspaceMember).where(WorkspaceMember.id == member_id))
        return result.scalar_one_or_none()

    async def get_by_workspace_and_user(self, workspace_id: UUID, user_id: UUID) -> Optional[WorkspaceMember]:
        result = await self.db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_workspace_members(self, workspace_id: UUID) -> List[WorkspaceMember]:
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .options(selectinload(WorkspaceMember.user))
        )
        return list(result.scalars().all())

    async def get_user_memberships(self, user_id: UUID) -> List[WorkspaceMember]:
        result = await self.db.execute(
            select(WorkspaceMember)
            .where(WorkspaceMember.user_id == user_id)
            .options(selectinload(WorkspaceMember.workspace))
        )
        return list(result.scalars().all())

    async def create(self, member: WorkspaceMember) -> WorkspaceMember:
        self.db.add(member)
        await self.db.flush()
        await self.db.refresh(member)
        return member

    async def update_role(self, workspace_id: UUID, user_id: UUID, role: WorkspaceRole) -> Optional[WorkspaceMember]:
        result = await self.db.execute(
            update(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .values(role=role)
            .returning(WorkspaceMember)
        )
        return result.scalar_one_or_none()

    async def set_joined_at(self, workspace_id: UUID, user_id: UUID) -> Optional[WorkspaceMember]:
        result = await self.db.execute(
            update(WorkspaceMember)
            .where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
            .values(joined_at=datetime.utcnow())
            .returning(WorkspaceMember)
        )
        return result.scalar_one_or_none()

    async def remove(self, workspace_id: UUID, user_id: UUID) -> bool:
        result = await self.db.execute(
            delete(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
            )
        )
        return result.rowcount > 0


class AssetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, asset_id: UUID) -> Optional[Asset]:
        result = await self.db.execute(select(Asset).where(Asset.id == asset_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID) -> List[Asset]:
        result = await self.db.execute(
            select(Asset).where(
                Asset.workspace_id == workspace_id,
                Asset.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def create(self, asset: Asset) -> Asset:
        self.db.add(asset)
        await self.db.flush()
        await self.db.refresh(asset)
        return asset

    async def update(self, asset_id: UUID, data: Dict[str, Any]) -> Optional[Asset]:
        result = await self.db.execute(
            update(Asset).where(Asset.id == asset_id).values(**data).returning(Asset)
        )
        return result.scalar_one_or_none()

    async def soft_delete(self, asset_id: UUID) -> bool:
        result = await self.db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(deleted_at=datetime.utcnow())
        )
        return result.rowcount > 0

    async def update_last_scanned(self, asset_id: UUID) -> None:
        await self.db.execute(
            update(Asset)
            .where(Asset.id == asset_id)
            .values(last_scanned_at=datetime.utcnow())
        )


class AssetAuthorizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, auth_id: UUID) -> Optional[AssetAuthorization]:
        result = await self.db.execute(select(AssetAuthorization).where(AssetAuthorization.id == auth_id))
        return result.scalar_one_or_none()

    async def get_by_asset(self, asset_id: UUID) -> Optional[AssetAuthorization]:
        result = await self.db.execute(select(AssetAuthorization).where(AssetAuthorization.asset_id == asset_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID) -> List[AssetAuthorization]:
        result = await self.db.execute(select(AssetAuthorization).where(AssetAuthorization.workspace_id == workspace_id))
        return list(result.scalars().all())

    async def create(self, auth: AssetAuthorization) -> AssetAuthorization:
        self.db.add(auth)
        await self.db.flush()
        await self.db.refresh(auth)
        return auth

    async def update(self, auth_id: UUID, data: Dict[str, Any]) -> Optional[AssetAuthorization]:
        result = await self.db.execute(
            update(AssetAuthorization).where(AssetAuthorization.id == auth_id).values(**data).returning(AssetAuthorization)
        )
        return result.scalar_one_or_none()

    async def verify(self, asset_id: UUID, verified_by: UUID) -> Optional[AssetAuthorization]:
        result = await self.db.execute(
            update(AssetAuthorization)
            .where(AssetAuthorization.asset_id == asset_id)
            .values(
                status=AuthorizationStatus.VERIFIED,
                verified_by=verified_by,
                verified_at=datetime.utcnow(),
            )
            .returning(AssetAuthorization)
        )
        return result.scalar_one_or_none()

    async def reject(self, asset_id: UUID, notes: Optional[str] = None) -> Optional[AssetAuthorization]:
        result = await self.db.execute(
            update(AssetAuthorization)
            .where(AssetAuthorization.asset_id == asset_id)
            .values(status=AuthorizationStatus.REJECTED, notes=notes)
            .returning(AssetAuthorization)
        )
        return result.scalar_one_or_none()

    async def is_authorized_for_scan(self, asset_id: UUID) -> bool:
        auth = await self.get_by_asset(asset_id)
        if not auth:
            return False
        if auth.status != AuthorizationStatus.VERIFIED:
            return False
        if auth.expires_at and auth.expires_at < datetime.utcnow():
            return False
        return True


class ScanRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, scan_id: UUID) -> Optional[Scan]:
        result = await self.db.execute(select(Scan).where(Scan.id == scan_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, status: Optional[ScanStatus] = None, limit: int = 50, offset: int = 0) -> List[Scan]:
        query = select(Scan).where(Scan.workspace_id == workspace_id).order_by(Scan.triggered_at.desc()).limit(limit).offset(offset)
        if status:
            query = query.where(Scan.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_asset(self, asset_id: UUID, limit: int = 50, offset: int = 0) -> List[Scan]:
        result = await self.db.execute(
            select(Scan).where(Scan.asset_id == asset_id).order_by(Scan.triggered_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id_with_relations(self, scan_id: UUID) -> Optional[Scan]:
        result = await self.db.execute(
            select(Scan)
            .options(
                selectinload(Scan.asset),
                selectinload(Scan.triggerer),
                selectinload(Scan.events),
                selectinload(Scan.findings)
            )
            .where(Scan.id == scan_id)
        )
        return result.scalar_one_or_none()

    async def create(self, scan: Scan) -> Scan:
        self.db.add(scan)
        await self.db.flush()
        await self.db.refresh(scan)
        return scan

    async def update(self, scan_id: UUID, data: Dict[str, Any]) -> Optional[Scan]:
        result = await self.db.execute(
            update(Scan).where(Scan.id == scan_id).values(**data).returning(Scan)
        )
        return result.scalar_one_or_none()

    async def count_by_workspace(self, workspace_id: UUID, status: Optional[ScanStatus] = None) -> int:
        query = select(func.count(Scan.id)).where(Scan.workspace_id == workspace_id)
        if status:
            query = query.where(Scan.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def get_latest_by_asset(self, asset_id: UUID) -> Optional[Scan]:
        result = await self.db.execute(
            select(Scan).where(Scan.asset_id == asset_id).order_by(Scan.triggered_at.desc()).limit(1)
        )
        return result.scalar_one_or_none()


class ScanEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, event: ScanEvent) -> ScanEvent:
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event

    async def get_by_scan(self, scan_id: UUID) -> List[ScanEvent]:
        result = await self.db.execute(
            select(ScanEvent).where(ScanEvent.scan_id == scan_id).order_by(ScanEvent.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_latest_by_scan(self, scan_id: UUID, limit: int = 1) -> List[ScanEvent]:
        result = await self.db.execute(
            select(ScanEvent).where(ScanEvent.scan_id == scan_id).order_by(ScanEvent.created_at.desc()).limit(limit)
        )
        return list(result.scalars().all())


class FindingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, finding_id: UUID) -> Optional[Finding]:
        result = await self.db.execute(select(Finding).where(Finding.id == finding_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, severity: Optional[FindingSeverity] = None, status: Optional[FindingStatus] = None, limit: int = 50, offset: int = 0) -> List[Finding]:
        query = select(Finding).where(Finding.workspace_id == workspace_id).order_by(Finding.first_seen_at.desc()).limit(limit).offset(offset)
        if severity:
            query = query.where(Finding.severity == severity)
        if status:
            query = query.where(Finding.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_scan(self, scan_id: UUID) -> List[Finding]:
        result = await self.db.execute(
            select(Finding).where(Finding.scan_id == scan_id).order_by(Finding.severity.desc(), Finding.first_seen_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_asset(self, asset_id: UUID, limit: int = 50, offset: int = 0) -> List[Finding]:
        result = await self.db.execute(
            select(Finding).where(Finding.asset_id == asset_id).order_by(Finding.first_seen_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create(self, finding: Finding) -> Finding:
        self.db.add(finding)
        await self.db.flush()
        await self.db.refresh(finding)
        return finding

    async def create_many(self, findings: List[Finding]) -> List[Finding]:
        for finding in findings:
            self.db.add(finding)
        await self.db.flush()
        for finding in findings:
            await self.db.refresh(finding)
        return findings

    async def update(self, finding_id: UUID, data: Dict[str, Any]) -> Optional[Finding]:
        result = await self.db.execute(
            update(Finding).where(Finding.id == finding_id).values(**data).returning(Finding)
        )
        return result.scalar_one_or_none()

    async def count_by_workspace(self, workspace_id: UUID, severity: Optional[FindingSeverity] = None, status: Optional[FindingStatus] = None) -> int:
        query = select(func.count(Finding.id)).where(Finding.workspace_id == workspace_id)
        if severity:
            query = query.where(Finding.severity == severity)
        if status:
            query = query.where(Finding.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()

    async def count_by_scan(self, scan_id: UUID) -> Dict[str, int]:
        result = await self.db.execute(
            select(Finding.severity, func.count(Finding.id))
            .where(Finding.scan_id == scan_id)
            .group_by(Finding.severity)
        )
        counts = {row.severity.value: row.count for row in result.all()}
        return {
            "total_findings": sum(counts.values()),
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
            "info": counts.get("info", 0),
        }


class FindingEvidenceRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, evidence: FindingEvidence) -> FindingEvidence:
        self.db.add(evidence)
        await self.db.flush()
        await self.db.refresh(evidence)
        return evidence

    async def create_many(self, evidence_list: List[FindingEvidence]) -> List[FindingEvidence]:
        for evidence in evidence_list:
            self.db.add(evidence)
        await self.db.flush()
        for evidence in evidence_list:
            await self.db.refresh(evidence)
        return evidence_list

    async def get_by_finding(self, finding_id: UUID) -> List[FindingEvidence]:
        result = await self.db.execute(
            select(FindingEvidence).where(FindingEvidence.finding_id == finding_id).order_by(FindingEvidence.created_at.asc())
        )
        return list(result.scalars().all())


class ScanTargetRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, target_id: UUID) -> Optional[ScanTarget]:
        result = await self.db.execute(select(ScanTarget).where(ScanTarget.id == target_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, is_demo: Optional[bool] = None) -> List[ScanTarget]:
        query = select(ScanTarget).where(ScanTarget.workspace_id == workspace_id)
        if is_demo is not None:
            query = query.where(ScanTarget.is_demo == is_demo)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_active_by_workspace(self, workspace_id: UUID) -> List[ScanTarget]:
        result = await self.db.execute(
            select(ScanTarget).where(
                ScanTarget.workspace_id == workspace_id,
                ScanTarget.is_active == True,
            )
        )
        return list(result.scalars().all())

    async def create(self, target: ScanTarget) -> ScanTarget:
        self.db.add(target)
        await self.db.flush()
        await self.db.refresh(target)
        return target

    async def update(self, target_id: UUID, data: Dict[str, Any]) -> Optional[ScanTarget]:
        result = await self.db.execute(
            update(ScanTarget).where(ScanTarget.id == target_id).values(**data).returning(ScanTarget)
        )
        return result.scalar_one_or_none()

    async def soft_delete(self, target_id: UUID) -> bool:
        result = await self.db.execute(
            update(ScanTarget)
            .where(ScanTarget.id == target_id)
            .values(is_active=False, updated_at=datetime.utcnow())
        )
        return result.rowcount > 0


class AiRunRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, ai_run: AiRun) -> AiRun:
        self.db.add(ai_run)
        await self.db.flush()
        await self.db.refresh(ai_run)
        return ai_run

    async def get_by_id(self, run_id: UUID) -> Optional[AiRun]:
        result = await self.db.execute(select(AiRun).where(AiRun.id == run_id))
        return result.scalar_one_or_none()

    async def update(self, run_id: UUID, data: Dict[str, Any]) -> Optional[AiRun]:
        result = await self.db.execute(
            update(AiRun).where(AiRun.id == run_id).values(**data).returning(AiRun)
        )
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, limit: int = 50, offset: int = 0) -> List[AiRun]:
        result = await self.db.execute(
            select(AiRun).where(AiRun.workspace_id == workspace_id).order_by(AiRun.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_scan(self, scan_id: UUID) -> List[AiRun]:
        result = await self.db.execute(
            select(AiRun).where(AiRun.scan_id == scan_id).order_by(AiRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_finding(self, finding_id: UUID) -> List[AiRun]:
        result = await self.db.execute(
            select(AiRun).where(AiRun.finding_id == finding_id).order_by(AiRun.created_at.desc())
        )
        return list(result.scalars().all())


class FindingAiAnalysisRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, analysis: FindingAiAnalysis) -> FindingAiAnalysis:
        self.db.add(analysis)
        await self.db.flush()
        await self.db.refresh(analysis)
        return analysis

    async def get_by_id(self, analysis_id: UUID) -> Optional[FindingAiAnalysis]:
        result = await self.db.execute(select(FindingAiAnalysis).where(FindingAiAnalysis.id == analysis_id))
        return result.scalar_one_or_none()

    async def get_by_finding(self, finding_id: UUID) -> List[FindingAiAnalysis]:
        result = await self.db.execute(
            select(FindingAiAnalysis).where(FindingAiAnalysis.finding_id == finding_id).order_by(FindingAiAnalysis.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_ai_run(self, ai_run_id: UUID) -> Optional[FindingAiAnalysis]:
        result = await self.db.execute(select(FindingAiAnalysis).where(FindingAiAnalysis.ai_run_id == ai_run_id))
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, limit: int = 50, offset: int = 0) -> List[FindingAiAnalysis]:
        result = await self.db.execute(
            select(FindingAiAnalysis).where(FindingAiAnalysis.workspace_id == workspace_id).order_by(FindingAiAnalysis.created_at.desc()).limit(limit).offset(offset)
        )
        return list(result.scalars().all())


class FindingRelationshipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, relationship: FindingRelationship) -> FindingRelationship:
        self.db.add(relationship)
        await self.db.flush()
        await self.db.refresh(relationship)
        return relationship

    async def get_by_id(self, relationship_id: UUID) -> Optional[FindingRelationship]:
        result = await self.db.execute(select(FindingRelationship).where(FindingRelationship.id == relationship_id))
        return result.scalar_one_or_none()

    async def get_by_findings(self, source_finding_id: UUID, target_finding_id: UUID) -> List[FindingRelationship]:
        result = await self.db.execute(
            select(FindingRelationship).where(
                FindingRelationship.source_finding_id == source_finding_id,
                FindingRelationship.target_finding_id == target_finding_id,
            )
        )
        return list(result.scalars().all())

    async def get_by_source(self, source_finding_id: UUID) -> List[FindingRelationship]:
        result = await self.db.execute(
            select(FindingRelationship).where(FindingRelationship.source_finding_id == source_finding_id)
        )
        return list(result.scalars().all())

    async def get_by_target(self, target_finding_id: UUID) -> List[FindingRelationship]:
        result = await self.db.execute(
            select(FindingRelationship).where(FindingRelationship.target_finding_id == target_finding_id)
        )
        return list(result.scalars().all())

    async def get_by_workspace(self, workspace_id: UUID, source: Optional[RelationshipSource] = None, limit: int = 100, offset: int = 0) -> List[FindingRelationship]:
        query = select(FindingRelationship).where(FindingRelationship.workspace_id == workspace_id).order_by(FindingRelationship.created_at.desc()).limit(limit).offset(offset)
        if source:
            query = query.where(FindingRelationship.source == source)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_finding(self, finding_id: UUID) -> List[FindingRelationship]:
        result = await self.db.execute(
            select(FindingRelationship).where(
                or_(
                    FindingRelationship.source_finding_id == finding_id,
                    FindingRelationship.target_finding_id == finding_id,
                )
            )
        )
        return list(result.scalars().all())

    async def update(self, relationship_id: UUID, data: Dict[str, Any]) -> Optional[FindingRelationship]:
        result = await self.db.execute(
            update(FindingRelationship).where(FindingRelationship.id == relationship_id).values(**data).returning(FindingRelationship)
        )
        return result.scalar_one_or_none()

    async def delete(self, relationship_id: UUID) -> bool:
        result = await self.db.execute(delete(FindingRelationship).where(FindingRelationship.id == relationship_id))
        return result.rowcount > 0


class AttackPathRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, attack_path: AttackPath) -> AttackPath:
        self.db.add(attack_path)
        await self.db.flush()
        await self.db.refresh(attack_path)
        return attack_path

    async def get_by_id(self, attack_path_id: UUID) -> Optional[AttackPath]:
        result = await self.db.execute(
            select(AttackPath)
            .options(
                selectinload(AttackPath.nodes).selectinload(AttackPathNode.finding),
                selectinload(AttackPath.edges).selectinload(AttackPathEdge.source_node).selectinload(AttackPathNode.finding),
                selectinload(AttackPath.edges).selectinload(AttackPathEdge.target_node).selectinload(AttackPathNode.finding),
            )
            .where(AttackPath.id == attack_path_id)
        )
        return result.scalar_one_or_none()

    async def get_by_workspace(self, workspace_id: UUID, status: Optional[AttackPathStatus] = None, limit: int = 50, offset: int = 0) -> List[AttackPath]:
        query = select(AttackPath).where(AttackPath.workspace_id == workspace_id).order_by(AttackPath.updated_at.desc()).limit(limit).offset(offset)
        if status:
            query = query.where(AttackPath.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_by_asset(self, asset_id: UUID, status: Optional[AttackPathStatus] = None) -> List[AttackPath]:
        query = select(AttackPath).where(AttackPath.asset_id == asset_id).order_by(AttackPath.updated_at.desc())
        if status:
            query = query.where(AttackPath.status == status)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update(self, attack_path_id: UUID, data: Dict[str, Any]) -> Optional[AttackPath]:
        result = await self.db.execute(
            update(AttackPath).where(AttackPath.id == attack_path_id).values(**data).returning(AttackPath)
        )
        return result.scalar_one_or_none()

    async def delete(self, attack_path_id: UUID) -> bool:
        result = await self.db.execute(delete(AttackPath).where(AttackPath.id == attack_path_id))
        return result.rowcount > 0

    async def count_by_workspace(self, workspace_id: UUID, status: Optional[AttackPathStatus] = None) -> int:
        query = select(func.count(AttackPath.id)).where(AttackPath.workspace_id == workspace_id)
        if status:
            query = query.where(AttackPath.status == status)
        result = await self.db.execute(query)
        return result.scalar_one()


class AttackPathNodeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, node: AttackPathNode) -> AttackPathNode:
        self.db.add(node)
        await self.db.flush()
        await self.db.refresh(node)
        return node

    async def create_many(self, nodes: List[AttackPathNode]) -> List[AttackPathNode]:
        for node in nodes:
            self.db.add(node)
        await self.db.flush()
        for node in nodes:
            await self.db.refresh(node)
        return nodes

    async def get_by_id(self, node_id: UUID) -> Optional[AttackPathNode]:
        result = await self.db.execute(select(AttackPathNode).where(AttackPathNode.id == node_id))
        return result.scalar_one_or_none()

    async def get_by_attack_path(self, attack_path_id: UUID) -> List[AttackPathNode]:
        result = await self.db.execute(
            select(AttackPathNode)
            .options(selectinload(AttackPathNode.finding))
            .where(AttackPathNode.attack_path_id == attack_path_id)
            .order_by(AttackPathNode.sequence)
        )
        return list(result.scalars().all())

    async def get_by_finding(self, finding_id: UUID) -> List[AttackPathNode]:
        result = await self.db.execute(
            select(AttackPathNode).where(AttackPathNode.finding_id == finding_id)
        )
        return list(result.scalars().all())


class AttackPathEdgeRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, edge: AttackPathEdge) -> AttackPathEdge:
        self.db.add(edge)
        await self.db.flush()
        await self.db.refresh(edge)
        return edge

    async def create_many(self, edges: List[AttackPathEdge]) -> List[AttackPathEdge]:
        for edge in edges:
            self.db.add(edge)
        await self.db.flush()
        for edge in edges:
            await self.db.refresh(edge)
        return edges

    async def get_by_id(self, edge_id: UUID) -> Optional[AttackPathEdge]:
        result = await self.db.execute(select(AttackPathEdge).where(AttackPathEdge.id == edge_id))
        return result.scalar_one_or_none()

    async def get_by_attack_path(self, attack_path_id: UUID) -> List[AttackPathEdge]:
        result = await self.db.execute(
            select(AttackPathEdge)
            .options(
                selectinload(AttackPathEdge.source_node).selectinload(AttackPathNode.finding),
                selectinload(AttackPathEdge.target_node).selectinload(AttackPathNode.finding),
            )
            .where(AttackPathEdge.attack_path_id == attack_path_id)
        )
        return list(result.scalars().all())


class RiskSnapshotRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, snapshot: RiskSnapshot) -> RiskSnapshot:
        self.db.add(snapshot)
        await self.db.flush()
        await self.db.refresh(snapshot)
        return snapshot

    async def get_by_id(self, snapshot_id: UUID) -> Optional[RiskSnapshot]:
        result = await self.db.execute(select(RiskSnapshot).where(RiskSnapshot.id == snapshot_id))
        return result.scalar_one_or_none()

    async def get_by_attack_path(self, attack_path_id: UUID) -> List[RiskSnapshot]:
        result = await self.db.execute(
            select(RiskSnapshot)
            .where(RiskSnapshot.attack_path_id == attack_path_id)
            .order_by(RiskSnapshot.calculated_at.desc())
        )
        return list(result.scalars().all())

    async def get_latest_by_attack_path(self, attack_path_id: UUID) -> Optional[RiskSnapshot]:
        result = await self.db.execute(
            select(RiskSnapshot)
            .where(RiskSnapshot.attack_path_id == attack_path_id)
            .order_by(RiskSnapshot.calculated_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
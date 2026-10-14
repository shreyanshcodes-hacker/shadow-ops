from typing import Optional, List, Dict, Any, Set
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete

from app.models import (
    NotificationRule,
    NotificationDelivery,
    Notification,
    EventOutbox,
    Profile,
    WorkspaceMember,
    WorkspaceRole,
    Finding,
    FindingSeverity,
    FindingStatus,
    Asset,
    AssetAuthorization,
    RemediationProposal,
    RemediationApproval,
    VerificationJob,
    VerificationOutcome,
    Report,
    RuleRecipientPolicy,
    NotificationChannel,
    DeliveryStatus,
)
from app.services.event_outbox import EventOutboxService
from app.security.audit import audit_log


class RulesService:
    """Service for managing notification rules and resolving recipients."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_rule(
        self,
        workspace_id: UUID,
        created_by: UUID,
        name: str,
        event_type: str,
        event_version: str = "1.0",
        recipient_policy: str = "asset_owners",
        specific_recipient_ids: Optional[List[UUID]] = None,
        severity_filter: Optional[List[str]] = None,
        status_filter: Optional[List[str]] = None,
        enabled_channels: Optional[List[str]] = None,
        deduplication_window_minutes: int = 60,
        rate_limit_per_hour: int = 100,
        require_acknowledgement: bool = False,
        acknowledgement_timeout_hours: Optional[int] = None,
        priority: str = "normal",
        action_url_template: Optional[str] = None,
        action_label_template: Optional[str] = None,
        description: Optional[str] = None,
    ) -> 'NotificationRule':
        """Create a new notification rule."""
        rule = NotificationRule(
            workspace_id=workspace_id,
            name=name,
            event_type=event_type,
            event_version=event_version,
            recipient_policy=RuleRecipientPolicy(recipient_policy),
            specific_recipient_ids=specific_recipient_ids or [],
            severity_filter=severity_filter or ["critical", "high", "medium", "low", "info"],
            status_filter=status_filter or ["open", "triaged", "in_progress"],
            enabled_channels=enabled_channels or ["in_app"],
            deduplication_window_minutes=deduplication_window_minutes,
            rate_limit_per_hour=rate_limit_per_hour,
            require_acknowledgement=require_acknowledgement,
            acknowledgement_timeout_hours=acknowledgement_timeout_hours,
            priority=priority,
            action_url_template=action_url_template,
            action_label_template=action_label_template,
            description=description,
            created_by=created_by,
        )
        self.db.add(rule)
        await self.db.flush()
        return rule

    async def get_rule(self, rule_id: UUID) -> Optional['NotificationRule']:
        """Get a rule by ID."""
        result = await self.db.execute(
            select(NotificationRule).where(NotificationRule.id == rule_id)
        )
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        workspace_id: UUID,
        event_type: Optional[str] = None,
        enabled_only: bool = True,
    ) -> List['NotificationRule']:
        """List rules for a workspace."""
        query = select(NotificationRule).where(NotificationRule.workspace_id == workspace_id)

        if event_type:
            query = query.where(NotificationRule.event_type == event_type)
        if enabled_only:
            query = query.where(NotificationRule.is_enabled == True)

        query = query.order_by(NotificationRule.created_at.desc())
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_rule(
        self,
        rule_id: UUID,
        **kwargs,
    ) -> Optional['NotificationRule']:
        """Update a rule."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return None

        for key, value in kwargs.items():
            if hasattr(rule, key) and value is not None:
                if key == "recipient_policy" and isinstance(value, str):
                    setattr(rule, key, RuleRecipientPolicy(value))
                else:
                    setattr(rule, key, value)

        rule.updated_at = datetime.utcnow()
        await self.db.flush()
        return rule

    async def delete_rule(self, rule_id: UUID) -> bool:
        """Delete a rule."""
        rule = await self.get_rule(rule_id)
        if not rule:
            return False

        await self.db.delete(rule)
        await self.db.flush()
        return True

    async def resolve_recipients(
        self,
        rule: 'NotificationRule',
        event_outbox: Optional[Any] = None,
    ) -> List[UUID]:
        """Resolve recipients based on rule policy and event context."""
        recipients = set()

        if rule.recipient_policy == RuleRecipientPolicy.SPECIFIC_USERS:
            recipients.update(rule.specific_recipient_ids)

        elif rule.recipient_policy == RuleRecipientPolicy.WORKSPACE_OWNERS:
            recipients.update(await self._get_workspace_owners(rule.workspace_id))

        elif rule.recipient_policy == RuleRecipientPolicy.WORKSPACE_ADMINS:
            recipients.update(await self._get_workspace_admins(rule.workspace_id))

        elif rule.recipient_policy == RuleRecipientPolicy.ASSET_OWNERS:
            if event_outbox and event_outbox.resource_type == "asset":
                recipients.update(await self._get_asset_owners(event_outbox.resource_id))
            elif event_outbox and event_outbox.resource_type == "finding":
                # Find asset through finding
                asset_id = await self._get_asset_for_finding(event_outbox.resource_id)
                if asset_id:
                    recipients.update(await self._get_asset_owners(asset_id))

        elif rule.recipient_policy == RuleRecipientPolicy.ASSET_MEMBERS:
            if event_outbox and event_outbox.resource_type == "asset":
                recipients.update(await self._get_asset_members(event_outbox.resource_id))
            elif event_outbox and event_outbox.resource_type == "finding":
                asset_id = await self._get_asset_for_finding(event_outbox.resource_id)
                if asset_id:
                    recipients.update(await self._get_asset_members(asset_id))

        elif rule.recipient_policy == RuleRecipientPolicy.FINDING_ASSIGNEES:
            if event_outbox and event_outbox.resource_type == "finding":
                assignee = await self._get_finding_assignee(event_outbox.resource_id)
                if assignee:
                    recipients.add(assignee)

        elif rule.recipient_policy == RuleRecipientPolicy.REMEDIATION_APPROVERS:
            if event_outbox and event_outbox.resource_type == "remediation_proposal":
                approvers = await self._get_remediation_approvers(event_outbox.resource_id)
                recipients.update(approvers)

        return list(recipients)

    async def _get_workspace_owners(self, workspace_id: UUID) -> Set[UUID]:
        """Get workspace owner user IDs."""
        result = await self.db.execute(
            select(WorkspaceMember.user_id).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role == WorkspaceRole.OWNER,
                    WorkspaceMember.joined_at.is_not(None),
                )
            )
        )
        return set(result.scalars().all())

    async def _get_workspace_admins(self, workspace_id: UUID) -> Set[UUID]:
        """Get workspace admin user IDs (including owners)."""
        result = await self.db.execute(
            select(WorkspaceMember.user_id).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.role.in_([WorkspaceRole.OWNER, WorkspaceRole.ADMIN]),
                    WorkspaceMember.joined_at.is_not(None),
                )
            )
        )
        return set(result.scalars().all())

    async def _get_asset_owners(self, asset_id: UUID) -> Set[UUID]:
        """Get asset owner user IDs (creator + authorization verifiers)."""
        recipients = set()

        # Asset creator
        asset_result = await self.db.execute(
            select(Asset.created_by).where(Asset.id == asset_id)
        )
        creator_id = asset_result.scalar_one_or_none()
        if creator_id:
            recipients.add(creator_id)

        # Authorization verifiers
        auth_result = await self.db.execute(
            select(AssetAuthorization.verified_by).where(
                and_(
                    AssetAuthorization.asset_id == asset_id,
                    AssetAuthorization.verified_by.is_not(None),
                )
            )
        )
        for verifier_id in auth_result.scalars().all():
            if verifier_id:
                recipients.add(verifier_id)

        return recipients

    async def _get_asset_members(self, asset_id: UUID) -> Set[UUID]:
        """Get all workspace members who have access to the asset."""
        # Get workspace for the asset
        asset_result = await self.db.execute(
            select(Asset.workspace_id).where(Asset.id == asset_id)
        )
        workspace_id = asset_result.scalar_one_or_none()
        if not workspace_id:
            return set()

        # Return all workspace members with joined_at
        result = await self.db.execute(
            select(WorkspaceMember.user_id).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.joined_at.is_not(None),
                )
            )
        )
        return set(result.scalars().all())

    async def _get_asset_for_finding(self, finding_id: UUID) -> Optional[UUID]:
        """Get asset ID for a finding."""
        result = await self.db.execute(
            select(Finding.asset_id).where(Finding.id == finding_id)
        )
        return result.scalar_one_or_none()

    async def _get_finding_assignee(self, finding_id: UUID) -> Optional[UUID]:
        """Get finding assignee (triaged_by)."""
        result = await self.db.execute(
            select(Finding.triaged_by).where(Finding.id == finding_id)
        )
        return result.scalar_one_or_none()

    async def _get_remediation_approvers(self, proposal_id: UUID) -> Set[UUID]:
        """Get users who can approve a remediation (workspace admins/owners)."""
        proposal_result = await self.db.execute(
            select(RemediationProposal.workspace_id).where(RemediationProposal.id == proposal_id)
        )
        workspace_id = proposal_result.scalar_one_or_none()
        if not workspace_id:
            return set()

        return await self._get_workspace_admins(workspace_id)

    async def check_rate_limit(
        self,
        rule: 'NotificationRule',
        workspace_id: UUID,
    ) -> bool:
        """Check if rule has exceeded rate limit in the last hour."""
        hour_ago = datetime.utcnow() - timedelta(hours=1)
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                and_(
                    Notification.workspace_id == workspace_id,
                    Notification.rule_id == rule.id,
                    Notification.created_at >= hour_ago,
                )
            )
        )
        count = result.scalar() or 0
        return count < rule.rate_limit_per_hour

    async def check_deduplication(
        self,
        rule: 'NotificationRule',
        workspace_id: UUID,
        deduplication_key: str,
    ) -> bool:
        """Check if a notification with this deduplication key was recently created."""
        window_start = datetime.utcnow() - timedelta(minutes=rule.deduplication_window_minutes)
        result = await self.db.execute(
            select(Notification.id).where(
                and_(
                    Notification.workspace_id == workspace_id,
                    Notification.rule_id == rule.id,
                    Notification.deduplication_key == deduplication_key,
                    Notification.created_at >= window_start,
                )
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None
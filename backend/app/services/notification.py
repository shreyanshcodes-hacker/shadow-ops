from typing import Optional, List, Dict, Any, Set
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, delete
from sqlalchemy.orm import selectinload

from app.models import (
    Notification,
    NotificationPreference,
    NotificationPreferenceCategory,
    NotificationRule,
    NotificationDelivery,
    NotificationChannel,
    NotificationPriority,
    DeliveryStatus,
    EventOutbox,
    EventProcessingStatus,
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
)
from app.services.event_outbox import EventOutboxService
from app.security.audit import audit_log
from app.core.config import settings


class NotificationService:
    """Service for creating and managing notifications."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.event_outbox_service = EventOutboxService(db)

    async def create_notification(
        self,
        workspace_id: UUID,
        user_id: UUID,
        notification_type: str,
        title: str,
        message: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[UUID] = None,
        channels: Optional[List[str]] = None,
        priority: str = "normal",
        action_url: Optional[str] = None,
        action_label: Optional[str] = None,
        deduplication_key: Optional[str] = None,
        expires_at: Optional[datetime] = None,
        event_outbox_id: Optional[UUID] = None,
        rule_id: Optional[UUID] = None,
    ) -> Optional[Notification]:
        """
        Create a notification for a specific user.
        Returns None if deduplication prevents creation.
        """
        # Check deduplication
        if deduplication_key:
            existing = await self.db.execute(
                select(Notification).where(
                    and_(
                        Notification.workspace_id == workspace_id,
                        Notification.user_id == user_id,
                        Notification.deduplication_key == deduplication_key,
                        Notification.created_at > datetime.utcnow() - timedelta(hours=24),
                    )
                )
            )
            if existing.scalar_one_or_none():
                return None

        # Check user preferences
        prefs = await self._get_user_preferences(user_id, workspace_id)
        channel_list = channels or ["in_app"]

        # Filter channels based on preferences
        enabled_channels = []
        for channel in channel_list:
            if channel == "in_app" and prefs.get("in_app_enabled", True):
                enabled_channels.append(channel)
            elif channel == "email" and prefs.get("email_enabled", False):
                enabled_channels.append(channel)

        if not enabled_channels:
            return None

        notification = Notification(
            workspace_id=workspace_id,
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            reference_type=reference_type,
            reference_id=reference_id,
            channels=enabled_channels,
            priority=priority,
            action_url=action_url,
            action_label=action_label,
            deduplication_key=deduplication_key,
            expires_at=expires_at,
            event_outbox_id=event_outbox_id,
        )
        self.db.add(notification)
        await self.db.flush()
        return notification

    async def create_notification_for_event(
        self,
        event_outbox_id: UUID,
        rule_id: UUID,
    ) -> List[Notification]:
        """Create notifications for all recipients of a rule based on an event."""
        from app.services.rules import RulesService

        rules_service = RulesService(self.db)
        rule = await self.db.get(NotificationRule, rule_id)
        if not rule or not rule.is_enabled:
            return []

        # Resolve recipients
        recipients = await rules_service.resolve_recipients(rule, None)
        if not recipients:
            return []

        # Get event for context
        event = await self.db.get(EventOutbox, rule.workspace_id)
        if not event:
            return []

        notifications = []
        for user_id in recipients:
            notification = await self.create_notification(
                workspace_id=rule.workspace_id,
                user_id=user_id,
                notification_type=rule.event_type,
                title=self._render_template(rule.name, event),
                message=self._render_template(f"Event: {event.event_type}", event),
                reference_type=event.resource_type,
                reference_id=event.resource_id,
                channels=rule.enabled_channels,
                priority=rule.priority,
                action_url=self._render_template(rule.action_url_template or "", event) if rule.action_url_template else None,
                action_label=rule.action_label_template,
                deduplication_key=f"{rule.id}:{event.event_id}" if rule.deduplication_window_minutes > 0 else None,
                expires_at=datetime.utcnow() + timedelta(hours=rule.acknowledgement_timeout_hours) if rule.acknowledgement_timeout_hours else None,
                event_outbox_id=rule.workspace_id,
                rule_id=rule.id,
            )
            if notification:
                notifications.append(notification)

        return notifications

    def _render_template(self, template: str, event: EventOutbox) -> str:
        """Simple template rendering for action URLs and labels."""
        if not template:
            return ""
        return template.replace("{event_id}", str(event.event_id)).replace(
            "{resource_id}", str(event.resource_id) if event.resource_id else ""
        ).replace("{event_type}", event.event_type)

    async def _get_user_preferences(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> Dict[str, bool]:
        """Get user notification preferences for a workspace."""
        result = await self.db.execute(
            select(NotificationPreference).where(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.workspace_id == workspace_id,
                )
            )
        )
        prefs = result.scalars().all()
        return {
            pref.category: {
                "in_app_enabled": pref.in_app_enabled,
                "email_enabled": pref.email_enabled,
            }
            for pref in prefs
        }

    async def get_user_notifications(
        self,
        user_id: UUID,
        workspace_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Notification]:
        """Get notifications for a user."""
        query = select(Notification).where(
            and_(
                Notification.user_id == user_id,
                Notification.workspace_id == workspace_id,
            )
        )

        if unread_only:
            query = query.where(Notification.read_at.is_(None))

        query = query.order_by(Notification.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_unread_count(self, user_id: UUID, workspace_id: UUID) -> int:
        """Get count of unread notifications for a user."""
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.workspace_id == workspace_id,
                    Notification.read_at.is_(None),
                )
            )
        )
        return result.scalar() or 0

    async def mark_as_read(self, notification_id: UUID, user_id: UUID) -> bool:
        """Mark a notification as read."""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.id == notification_id,
                    Notification.user_id == user_id,
                )
            )
        )
        notification = result.scalar_one_or_none()
        if not notification or notification.read_at:
            return False

        notification.read_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def mark_all_as_read(self, user_id: UUID, workspace_id: UUID) -> int:
        """Mark all notifications as read for a user."""
        result = await self.db.execute(
            select(Notification).where(
                and_(
                    Notification.user_id == user_id,
                    Notification.workspace_id == workspace_id,
                    Notification.read_at.is_(None),
                )
            )
        )
        notifications = result.scalars().all()
        count = 0
        for n in notifications:
            n.read_at = datetime.utcnow()
            count += 1
        await self.db.flush()
        return count

    async def delete_expired_notifications(self) -> int:
        """Delete expired notifications."""
        result = await self.db.execute(
            delete(Notification).where(
                and_(
                    Notification.expires_at.is_not(None),
                    Notification.expires_at < datetime.utcnow(),
                )
            )
        )
        return result.rowcount


class PreferencesService:
    """Service for managing notification preferences."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_user_preferences(
        self,
        user_id: UUID,
        workspace_id: UUID,
    ) -> List[NotificationPreference]:
        """Get all preferences for a user in a workspace."""
        result = await self.db.execute(
            select(NotificationPreference).where(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.workspace_id == workspace_id,
                )
            ).order_by(NotificationPreference.category)
        )
        return list(result.scalars().all())

    async def get_preference(
        self,
        user_id: UUID,
        workspace_id: UUID,
        category: str,
    ) -> Optional[NotificationPreference]:
        """Get a specific preference."""
        result = await self.db.execute(
            select(NotificationPreference).where(
                and_(
                    NotificationPreference.user_id == user_id,
                    NotificationPreference.workspace_id == workspace_id,
                    NotificationPreference.category == category,
                )
            )
        )
        return result.scalar_one_or_none()

    async def update_preference(
        self,
        user_id: UUID,
        workspace_id: UUID,
        category: str,
        in_app_enabled: Optional[bool] = None,
        email_enabled: Optional[bool] = None,
    ) -> NotificationPreference:
        """Update or create a preference."""
        pref = await self.get_preference(user_id, workspace_id, category)
        if not pref:
            pref = NotificationPreference(
                workspace_id=workspace_id,
                user_id=user_id,
                category=category,
                in_app_enabled=True,
                email_enabled=False,
            )
            self.db.add(pref)

        if in_app_enabled is not None:
            pref.in_app_enabled = in_app_enabled
        if email_enabled is not None:
            pref.email_enabled = email_enabled

        pref.updated_at = datetime.utcnow()
        await self.db.flush()
        return pref

    async def initialize_defaults(self, workspace_id: UUID, user_id: UUID) -> List[NotificationPreference]:
        """Initialize default preferences for a new workspace member."""
        preferences = []
        for category in NotificationPreferenceCategory:
            existing = await self.get_preference(user_id, workspace_id, category.value)
            if not existing:
                pref = NotificationPreference(
                    workspace_id=workspace_id,
                    user_id=user_id,
                    category=category.value,
                    in_app_enabled=True,
                    email_enabled=False,
                )
                self.db.add(pref)
                preferences.append(pref)

        await self.db.flush()
        return preferences

    async def get_effective_preference(
        self,
        user_id: UUID,
        workspace_id: UUID,
        category: str,
        channel: str,
    ) -> bool:
        """Check if a specific channel is enabled for a category."""
        pref = await self.get_preference(user_id, workspace_id, category)
        if not pref:
            # Default: in_app enabled, email disabled
            return channel == "in_app"

        if channel == "in_app":
            return pref.in_app_enabled
        elif channel == "email":
            return pref.email_enabled
        return False
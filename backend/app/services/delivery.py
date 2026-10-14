from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.models import (
    NotificationDelivery,
    Notification,
    DeliveryStatus,
    NotificationChannel,
    Profile,
    EventOutbox,
    EventProcessingStatus,
)
from app.services.event_outbox import EventOutboxService
from app.services.email_adapter import EmailAdapter
from app.services.n8n_adapter import N8nAdapter
from app.security.audit import audit_log
from app.core.config import settings


class DeliveryService:
    """Service for managing notification delivery across channels."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_adapter = EmailAdapter()
        self.n8n_adapter = N8nAdapter()

    async def create_delivery(
        self,
        notification_id: UUID,
        workspace_id: UUID,
        channel: str,
        recipient_id: UUID,
        max_attempts: int = 5,
    ) -> 'NotificationDelivery':
        """Create a delivery record for a notification."""
        delivery = NotificationDelivery(
            notification_id=notification_id,
            workspace_id=workspace_id,
            channel=channel,
            recipient_id=recipient_id,
            status=DeliveryStatus.PENDING,
            max_attempts=5,
        )
        self.db.add(delivery)
        await self.db.flush()
        return delivery

    async def create_deliveries_for_notification(
        self,
        notification: 'Notification',
    ) -> List['NotificationDelivery']:
        """Create delivery records for all channels of a notification."""
        deliveries = []
        for channel in notification.channels:
            delivery = await self.create_delivery(
                notification_id=notification.id,
                workspace_id=notification.workspace_id,
                channel=channel,
                recipient_id=notification.user_id,
            )
            deliveries.append(delivery)
        return deliveries

    async def process_pending_deliveries(
        self,
        limit: int = 100,
    ) -> int:
        """Process pending deliveries that are ready for retry."""
        result = await self.db.execute(
            select(NotificationDelivery).where(
                and_(
                    NotificationDelivery.status.in_([
                        DeliveryStatus.PENDING,
                        DeliveryStatus.RETRYING,
                    ]),
                    or_(
                        NotificationDelivery.next_retry_at.is_(None),
                        NotificationDelivery.next_retry_at <= datetime.utcnow(),
                    ),
                    NotificationDelivery.attempt_count < NotificationDelivery.max_attempts,
                )
            ).limit(limit)
        )
        deliveries = list(result.scalars().all())

        processed = 0
        for delivery in deliveries:
            await self._process_delivery(delivery)
            processed += 1

        return processed

    async def _process_delivery(self, delivery: 'NotificationDelivery') -> bool:
        """Process a single delivery attempt."""
        # Mark as processing
        delivery.status = DeliveryStatus.RETRYING if delivery.attempt_count > 0 else DeliveryStatus.PENDING
        delivery.attempt_count += 1
        delivery.last_error = None
        delivery.last_error_category = None
        await self.db.flush()

        try:
            notification = await self.db.get(Notification, delivery.notification_id)
            if not notification:
                raise ValueError("Notification not found")

            if delivery.channel == "in_app":
                success = await self._deliver_in_app(delivery, notification)
            elif delivery.channel == "email":
                success = await self._deliver_email(delivery, notification)
            else:
                raise ValueError(f"Unknown channel: {delivery.channel}")

            if success:
                delivery.status = DeliveryStatus.SENT
                delivery.sent_at = datetime.utcnow()
                delivery.last_error = None
                delivery.last_error_category = None
            else:
                raise ValueError("Delivery failed")

        except Exception as e:
            delivery.last_error = str(e)
            delivery.last_error_category = self._categorize_error(e)

            if delivery.attempt_count >= delivery.max_attempts:
                delivery.status = DeliveryStatus.FAILED
                delivery.failed_at = datetime.utcnow()
            else:
                delivery.status = DeliveryStatus.RETRYING
                # Exponential backoff
                delay_minutes = 2 ** (delivery.attempt_count - 1)
                delivery.next_retry_at = datetime.utcnow() + timedelta(minutes=min(delay_minutes, 60))

        await self.db.flush()
        return delivery.status == DeliveryStatus.SENT

    async def _deliver_in_app(self, delivery: 'NotificationDelivery', notification: 'Notification') -> bool:
        """Deliver in-app notification (already created, just mark as sent)."""
        # In-app notifications are created directly in the notifications table
        # This just confirms the notification exists
        notification_result = await self.db.get(Notification, delivery.notification_id)
        if notification_result:
            delivery.provider_message_id = str(notification.id)
            delivery.sent_at = datetime.utcnow()
            return True
        return False

    async def _deliver_email(self, delivery: 'NotificationDelivery', notification: 'Notification') -> bool:
        """Deliver notification via email."""
        recipient = await self.db.get(Profile, delivery.recipient_id)
        if not recipient or not recipient.email:
            raise ValueError("Recipient has no email address")

        # Check if email adapter is configured
        if not self.email_adapter.is_configured():
            raise ValueError("Email adapter not configured")

        # Build email content
        subject = notification.title
        html_body = self._build_email_html(notification)
        text_body = self._build_email_text(notification)

        # Send email
        result = await self.email_adapter.send_email(
            to_email=recipient.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
        )

        if result.success:
            delivery.provider_message_id = result.message_id
            delivery.provider_response = result.provider_response
            delivery.sent_at = datetime.utcnow()
            return True
        else:
            raise ValueError(result.error or "Email send failed")

    def _build_email_html(self, notification: 'Notification') -> str:
        """Build HTML email body."""
        return f"""
        <html>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #f8f9fa; border-radius: 8px; padding: 24px;">
                <h1 style="color: #1a1a2e; margin-top: 0;">{notification.title}</h1>
                <p style="color: #555;">{notification.message}</p>
                {f'<p><a href="{notification.action_url}" style="display: inline-block; background: #1a1a2e; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none;">{notification.action_label or "View Details"}</a></p>' if notification.action_url else ''}
                <hr style="border: none; border-top: 1px solid #e0e0e0; margin: 24px 0;">
                <p style="color: #888; font-size: 12px;">This notification was sent from ShadowOps. <a href="{settings.FRONTEND_URL or '#'}">View in dashboard</a></p>
            </div>
        </body>
        </html>
        """

    def _build_email_text(self, notification: 'Notification') -> str:
        """Build plain text email body."""
        lines = [
            notification.title,
            "",
            notification.message,
            "",
        ]
        if notification.action_url:
            lines.append(f"{notification.action_label or 'View Details'}: {notification.action_url}")
        lines.extend([
            "",
            "---",
            "This notification was sent from ShadowOps.",
        ])
        return "\n".join(lines)

    def _categorize_error(self, error: Exception) -> str:
        """Categorize error for retry logic."""
        error_str = str(error).lower()
        if "timeout" in error_str or "connection" in error_str:
            return "network"
        elif "auth" in error_str or "credential" in error_str or "unauthorized" in error_str:
            return "auth"
        elif "rate limit" in error_str or "quota" in error_str:
            return "rate_limit"
        elif "invalid" in error_str or "malformed" in error_str:
            return "validation"
        return "unknown"

    async def get_delivery(self, delivery_id: UUID) -> Optional['NotificationDelivery']:
        """Get a delivery by ID."""
        result = await self.db.execute(
            select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
        )
        return result.scalar_one_or_none()

    async def get_notification_deliveries(self, notification_id: UUID) -> List['NotificationDelivery']:
        """Get all deliveries for a notification."""
        result = await self.db.execute(
            select(NotificationDelivery).where(
                NotificationDelivery.notification_id == notification_id
            ).order_by(NotificationDelivery.created_at)
        )
        return list(result.scalars().all())

    async def get_pending_deliveries(
        self,
        workspace_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List['NotificationDelivery']:
        """Get pending deliveries ready for processing."""
        query = select(NotificationDelivery).where(
            and_(
                NotificationDelivery.status.in_([DeliveryStatus.PENDING, DeliveryStatus.RETRYING]),
                or_(
                    NotificationDelivery.next_retry_at.is_(None),
                    NotificationDelivery.next_retry_at <= datetime.utcnow(),
                ),
                NotificationDelivery.attempt_count < NotificationDelivery.max_attempts,
            )
        )

        if workspace_id:
            query = query.where(NotificationDelivery.workspace_id == workspace_id)

        query = query.order_by(NotificationDelivery.next_retry_at.asc().nullsfirst()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def retry_delivery(self, delivery_id: UUID) -> bool:
        """Manually retry a failed delivery."""
        result = await self.db.execute(
            select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
        )
        delivery = result.scalar_one_or_none()
        if not delivery:
            return False

        if delivery.status not in [DeliveryStatus.FAILED, DeliveryStatus.BOUNCED]:
            return False

        delivery.status = DeliveryStatus.PENDING
        delivery.attempt_count = 0
        delivery.last_error = None
        delivery.last_error_category = None
        delivery.next_retry_at = None
        await self.db.flush()
        return True

    async def get_delivery_stats(self, workspace_id: Optional[UUID] = None) -> Dict[str, int]:
        """Get delivery statistics."""
        query = select(
            NotificationDelivery.status,
            func.count(NotificationDelivery.id)
        ).group_by(NotificationDelivery.status)

        if workspace_id:
            query = query.where(NotificationDelivery.workspace_id == workspace_id)

        result = await self.db.execute(query)
        return {status.value: count for status, count in result.all()}

    async def cleanup_old_deliveries(self, days: int = 90) -> int:
        """Delete old delivery records."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        result = await self.db.execute(
            delete(NotificationDelivery).where(
                and_(
                    NotificationDelivery.created_at < cutoff,
                    NotificationDelivery.status.in_([DeliveryStatus.SENT, DeliveryStatus.DELIVERED, DeliveryStatus.FAILED, DeliveryStatus.BOUNCED]),
                )
            )
        )
        return result.rowcount
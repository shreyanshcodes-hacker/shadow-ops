from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update
from sqlalchemy.orm import selectinload

from app.models import (
    EventOutbox,
    EventProcessingStatus,
    Profile,
    WorkspaceMember,
    WorkspaceRole,
)
from app.security.audit import audit_log


class EventOutboxService:
    """Service for managing the transactional event outbox."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_event(
        self,
        workspace_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        event_version: str = "1.0",
        occurred_at: Optional[datetime] = None,
        max_attempts: int = 5,
    ) -> EventOutbox:
        """Create a new event in the outbox."""
        event = EventOutbox(
            workspace_id=workspace_id,
            event_type=event_type,
            event_version=event_version,
            payload=payload,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            occurred_at=occurred_at or datetime.utcnow(),
            max_attempts=max_attempts,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def create_event_transactional(
        self,
        workspace_id: UUID,
        event_type: str,
        payload: Dict[str, Any],
        actor_id: Optional[UUID] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        correlation_id: Optional[UUID] = None,
        event_version: str = "1.0",
        occurred_at: Optional[datetime] = None,
        max_attempts: int = 5,
    ) -> EventOutbox:
        """
        Create an event in the outbox within the current transaction.
        This should be called within the same transaction that creates the source event.
        """
        return await self.create_event(
            workspace_id=workspace_id,
            event_type=event_type,
            payload=payload,
            actor_id=actor_id,
            resource_type=resource_type,
            resource_id=resource_id,
            correlation_id=correlation_id,
            event_version=event_version,
            occurred_at=occurred_at,
            max_attempts=max_attempts,
        )

    async def get_pending_events(
        self,
        workspace_id: Optional[UUID] = None,
        limit: int = 100,
        event_types: Optional[List[str]] = None,
    ) -> List[EventOutbox]:
        """Get pending events ready for processing."""
        query = select(EventOutbox).where(
            and_(
                EventOutbox.status.in_([
                    EventProcessingStatus.PENDING,
                    EventProcessingStatus.PROCESSING,
                ]),
                or_(
                    EventOutbox.next_retry_at.is_(None),
                    EventOutbox.next_retry_at <= datetime.utcnow(),
                ),
                EventOutbox.attempt_count < EventOutbox.max_attempts,
            )
        )

        if workspace_id:
            query = query.where(EventOutbox.workspace_id == workspace_id)
        if event_types:
            query = query.where(EventOutbox.event_type.in_(event_types))

        query = query.order_by(EventOutbox.created_at).limit(limit)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_processing(self, event_id: UUID) -> Optional[EventOutbox]:
        """Mark an event as being processed."""
        result = await self.db.execute(
            select(EventOutbox).where(EventOutbox.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        if event.status not in (EventProcessingStatus.PENDING, EventProcessingStatus.PROCESSING):
            return None

        event.status = EventProcessingStatus.PROCESSING
        event.attempt_count += 1
        await self.db.flush()
        return event

    async def mark_completed(self, event_id: UUID) -> bool:
        """Mark an event as successfully processed."""
        result = await self.db.execute(
            select(EventOutbox).where(EventOutbox.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return False

        event.status = EventProcessingStatus.COMPLETED
        event.processed_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def mark_failed(
        self,
        event_id: UUID,
        error: str,
        error_category: str = "unknown",
        next_retry_delay: Optional[timedelta] = None,
    ) -> bool:
        """Mark an event as failed and schedule retry if attempts remain."""
        result = await self.db.execute(
            select(EventOutbox).where(EventOutbox.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return False

        event.attempt_count += 1
        event.last_error = error
        event.last_error_category = error_category

        if event.attempt_count >= event.max_attempts:
            event.status = EventProcessingStatus.DEAD_LETTER
        else:
            event.status = EventProcessingStatus.PENDING
            if next_retry_delay:
                event.next_retry_at = datetime.utcnow() + next_retry_delay
            else:
                # Exponential backoff: 1min, 2min, 4min, 8min, 16min...
                delay_minutes = 2 ** (event.attempt_count - 1)
                event.next_retry_at = datetime.utcnow() + timedelta(minutes=delay_minutes)

        await self.db.flush()
        return True

    async def get_dead_letter_events(
        self,
        workspace_id: Optional[UUID] = None,
        limit: int = 100,
    ) -> List[EventOutbox]:
        """Get events that have exceeded max attempts."""
        query = select(EventOutbox).where(
            EventOutbox.status == EventProcessingStatus.DEAD_LETTER
        )
        if workspace_id:
            query = query.where(EventOutbox.workspace_id == workspace_id)
        query = query.order_by(EventOutbox.updated_at.desc()).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def retry_event(self, event_id: UUID) -> Optional[EventOutbox]:
        """Manually retry a dead-letter or failed event."""
        result = await self.db.execute(
            select(EventOutbox).where(EventOutbox.id == event_id)
        )
        event = result.scalar_one_or_none()
        if not event:
            return None

        if event.status not in (EventProcessingStatus.DEAD_LETTER, EventProcessingStatus.FAILED):
            return None

        event.status = EventProcessingStatus.PENDING
        event.attempt_count = 0
        event.last_error = None
        event.last_error_category = None
        event.next_retry_at = None
        await self.db.flush()
        return event

    async def get_event(self, event_id: UUID) -> Optional[EventOutbox]:
        """Get a specific event by ID."""
        result = await self.db.execute(
            select(EventOutbox).where(EventOutbox.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_events_by_correlation_id(
        self,
        correlation_id: UUID,
        workspace_id: Optional[UUID] = None,
    ) -> List[EventOutbox]:
        """Get all events with the same correlation ID."""
        query = select(EventOutbox).where(EventOutbox.correlation_id == correlation_id)
        if workspace_id:
            query = query.where(EventOutbox.workspace_id == workspace_id)
        query = query.order_by(EventOutbox.created_at)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_stats(self, workspace_id: Optional[UUID] = None) -> Dict[str, int]:
        """Get processing statistics."""
        query = select(
            EventOutbox.status,
            func.count(EventOutbox.id)
        ).group_by(EventOutbox.status)

        if workspace_id:
            query = query.where(EventOutbox.workspace_id == workspace_id)

        result = await self.db.execute(query)
        return {status.value: count for status, count in result.all()}


# Helper function to emit events from services
async def emit_event(
    db: AsyncSession,
    workspace_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
    actor_id: Optional[UUID] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[UUID] = None,
    correlation_id: Optional[UUID] = None,
    event_version: str = "1.0",
    max_attempts: int = 5,
) -> EventOutbox:
    """
    Convenience function to emit an event to the outbox.
    Should be called within the same transaction as the source operation.
    """
    service = EventOutboxService(db)
    return await service.create_event_transactional(
        workspace_id=workspace_id,
        event_type=event_type,
        payload=payload,
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
        correlation_id=correlation_id,
        event_version=event_version,
        max_attempts=max_attempts,
    )


# Standard event type constants
class EventTypes:
    # Scan events
    SCAN_COMPLETED = "scan.completed"
    SCAN_FAILED = "scan.failed"
    SCAN_CANCELLED = "scan.cancelled"

    # Finding events
    FINDING_CREATED = "finding.created"
    FINDING_SEVERITY_CHANGED = "finding.severity_changed"
    FINDING_STATUS_CHANGED = "finding.status_changed"
    FINDING_TRIAGED = "finding.triaged"

    # Attack path events
    ATTACK_PATH_CREATED = "attack_path.created"
    ATTACK_PATH_STATUS_CHANGED = "attack_path.status_changed"

    # Risk events
    RISK_SCORE_CHANGED = "risk_score.changed"

    # Security Team events
    SECURITY_TEAM_COMPLETED = "security_team.completed"
    SECURITY_TEAM_REVIEW_SUBMITTED = "security_team.review_submitted"

    # Remediation events
    REMEDIATION_PROPOSED = "remediation.proposed"
    REMEDIATION_AWAITING_APPROVAL = "remediation.awaiting_approval"
    REMEDIATION_APPROVED = "remediation.approved"
    REMEDIATION_REJECTED = "remediation.rejected"
    REMEDIATION_APPLIED = "remediation.applied"
    REMEDIATION_FAILED = "remediation.failed"
    REMEDIATION_ROLLED_BACK = "remediation.rolled_back"

    # Verification events
    VERIFICATION_COMPLETED = "verification.completed"
    VERIFICATION_FAILED = "verification.failed"
    VERIFICATION_INCONCLUSIVE = "verification.inconclusive"
    VERIFICATION_REVIEW_SUBMITTED = "verification.review_submitted"

    # Report events
    REPORT_GENERATED = "report.generated"
    REPORT_GENERATION_FAILED = "report.generation_failed"
    REPORT_EXPORTED = "report.exported"

    # Security Team events
    SECURITY_TEAM_RUN_COMPLETED = "security_team.run_completed"
    SECURITY_TEAM_REVIEW_SUBMITTED = "security_team.review_submitted"
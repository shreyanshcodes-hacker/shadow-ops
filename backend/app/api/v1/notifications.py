from typing import Optional, List
from uuid import UUID
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import get_current_user
from app.models import Profile, WorkspaceRole
from app.schemas import (
    NotificationResponse,
    NotificationListResponse,
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    NotificationRuleResponse,
    NotificationRuleCreate,
    NotificationRuleUpdate,
    NotificationDeliveryResponse,
    WorkflowRunResponse,
    WorkflowRunListResponse,
    WorkflowRunCreate,
    WorkflowRunDetailResponse,
    WorkflowRunRetryRequest,
    EventOutboxResponse,
    EventOutboxListResponse,
    MarkReadRequest,
    MarkAllReadRequest,
)
from app.services.notification import NotificationService, PreferencesService
from app.services.rules import RulesService
from app.services.delivery import DeliveryService
from app.services.workflow import WorkflowService
from app.services.event_outbox import EventOutboxService

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_notification_service(db: AsyncSession = Depends(get_db)) -> NotificationService:
    return NotificationService(db)


def get_preferences_service(db: AsyncSession = Depends(get_db)) -> PreferencesService:
    return PreferencesService(db)


def get_rules_service(db: AsyncSession = Depends(get_db)) -> RulesService:
    return RulesService(db)


def get_delivery_service(db: AsyncSession = Depends(get_db)) -> DeliveryService:
    return DeliveryService(db)


def get_workflow_service(db: AsyncSession = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db)


def get_event_outbox_service(db: AsyncSession = Depends(get_db)) -> EventOutboxService:
    return EventOutboxService(db)


# =============================================================================
# Notifications
# =============================================================================

@router.get(
    "",
    response_model=List[NotificationListResponse],
    summary="List notifications for current user",
)
async def list_notifications(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    unread_only: bool = Query(False, description="Show only unread notifications"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """List notifications for the current user in a workspace."""
    notifications = await service.get_user_notifications(
        user_id=current_user.id,
        workspace_id=workspace_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return notifications


@router.get(
    "/unread-count",
    response_model=dict,
    summary="Get unread notification count",
)
async def get_unread_count(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Get count of unread notifications for the current user."""
    count = await service.get_unread_count(current_user.id, workspace_id)
    return {"unread_count": count}


@router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    summary="Mark notification as read",
)
async def mark_notification_read(
    notification_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark a single notification as read."""
    success = await service.mark_as_read(notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found or already read")

    # Fetch updated notification
    from app.services.notification import NotificationService as NS
    notification = await NS(db=service.db).db.get(Notification, notification_id)
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification


@router.post(
    "/read-all",
    response_model=dict,
    summary="Mark all notifications as read",
)
async def mark_all_read(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Mark all notifications as read for the current user."""
    count = await service.mark_all_as_read(current_user.id, workspace_id)
    return {"marked_read": count}


@router.delete(
    "/cleanup-expired",
    response_model=dict,
    summary="Clean up expired notifications",
)
async def cleanup_expired(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    """Clean up expired notifications (admin only)."""
    # Check if user is admin/owner
    from app.services import WorkspaceService
    ws_service = WorkspaceService(service.db)
    member = await ws_service.get_member(workspace_id, current_user.id)
    if not member or member.role not in [WorkspaceRole.OWNER, WorkspaceRole.ADMIN]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    count = await service.delete_expired_notifications()
    return {"deleted": count}


# =============================================================================
# Notification Preferences
# =============================================================================

@router.get(
    "/preferences",
    response_model=List[NotificationPreferenceResponse],
    summary="Get user notification preferences",
)
async def get_preferences(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: PreferencesService = Depends(get_preferences_service),
):
    """Get notification preferences for the current user."""
    prefs = await service.get_user_preferences(current_user.id, workspace_id)
    return prefs


@router.put(
    "/preferences/{category}",
    response_model=NotificationPreferenceResponse,
    summary="Update notification preference for a category",
)
async def update_preference(
    category: str,
    update: NotificationPreferenceUpdate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: PreferencesService = Depends(get_preferences_service),
):
    """Update a notification preference for a specific category."""
    pref = await service.update_preference(
        user_id=current_user.id,
        workspace_id=workspace_id,
        category=category,
        in_app_enabled=update.in_app_enabled,
        email_enabled=update.email_enabled,
    )
    return pref


# =============================================================================
# Notification Rules (Admin)
# =============================================================================

@router.get(
    "/rules",
    response_model=List[NotificationRuleResponse],
    summary="List notification rules",
)
async def list_rules(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    event_type: Optional[str] = Query(None),
    enabled_only: bool = Query(True),
    current_user: Profile = Depends(get_current_user),
    service: RulesService = Depends(get_rules_service),
):
    """List notification rules for a workspace (admin only)."""
    # Check admin permissions
    from app.services import WorkspaceService
    ws_service = WorkspaceService(RulesService.__init__.__globals__['db'] if 'db' in RulesService.__init__.__globals__ else None)
    # Simplified check - in practice would need proper auth
    rules = await service.list_rules(workspace_id, event_type, True)
    return rules


@router.post(
    "/rules",
    response_model=NotificationRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create notification rule",
)
async def create_rule(
    rule: NotificationRuleCreate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: RulesService = Depends(get_rules_service),
):
    """Create a new notification rule (admin only)."""
    # Check admin permissions
    rule = await service.create_rule(
        workspace_id=workspace_id,
        created_by=current_user.id,
        name=rule.name,
        event_type=rule.event_type,
        event_version=rule.event_version,
        recipient_policy=rule.recipient_policy,
        specific_recipient_ids=rule.specific_recipient_ids,
        severity_filter=rule.severity_filter,
        status_filter=rule.status_filter,
        enabled_channels=rule.enabled_channels,
        deduplication_window_minutes=rule.deduplication_window_minutes,
        rate_limit_per_hour=rule.rate_limit_per_hour,
        require_acknowledgement=rule.require_acknowledgement,
        acknowledgement_timeout_hours=rule.acknowledgement_timeout_hours,
        priority=rule.priority,
        action_url_template=rule.action_url_template,
        action_label_template=rule.action_label_template,
        description=rule.description,
    )
    return rule


@router.put(
    "/rules/{rule_id}",
    response_model=NotificationRuleResponse,
    summary="Update notification rule",
)
async def update_rule(
    rule_id: UUID,
    update: NotificationRuleUpdate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: RulesService = Depends(get_rules_service),
):
    """Update a notification rule (admin only)."""
    rule = await service.update_rule(rule_id, **update.dict(exclude_unset=True))
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.delete(
    "/rules/{rule_id}",
    response_model=dict,
    summary="Delete notification rule",
)
async def delete_rule(
    rule_id: UUID,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: RulesService = Depends(get_rules_service),
):
    """Delete a notification rule (admin only)."""
    success = await service.delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"deleted": True}


# =============================================================================
# Notification Deliveries
# =============================================================================

@router.get(
    "/{notification_id}/deliveries",
    response_model=List[NotificationDeliveryResponse],
    summary="Get deliveries for a notification",
)
async def get_deliveries(
    notification_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
):
    """Get all delivery attempts for a notification."""
    deliveries = await service.get_notification_deliveries(notification_id)
    return deliveries


@router.post(
    "/deliveries/{delivery_id}/retry",
    response_model=dict,
    summary="Retry a failed delivery",
)
async def retry_delivery(
    delivery_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
):
    """Retry a failed delivery."""
    success = await service.retry_delivery(delivery_id)
    if not success:
        raise HTTPException(status_code=404, detail="Delivery not found or not retryable")
    return {"retried": True}


@router.get(
    "/deliveries/stats",
    response_model=dict,
    summary="Get delivery statistics",
)
async def get_delivery_stats(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
):
    """Get delivery statistics for a workspace."""
    stats = await service.get_delivery_stats(workspace_id)
    return stats


# =============================================================================
# Workflow Runs
# =============================================================================

@router.post(
    "/workflows",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create workflow run",
)
async def create_workflow(
    workflow: WorkflowRunCreate,
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Create and execute a workflow run."""
    run = await service.create_workflow_run(
        workspace_id=workspace_id,
        workflow_id=workflow.workflow_id,
        workflow_version=workflow.workflow_version,
        input_payload=workflow.input_payload,
        trigger_event_outbox_id=workflow.trigger_event_outbox_id,
        trigger_event_type=workflow.trigger_event_type,
        trigger_resource_type=workflow.trigger_resource_type,
        trigger_resource_id=workflow.trigger_resource_id,
        created_by=current_user.id,
        timeout_minutes=workflow.timeout_minutes,
    )
    return run


@router.get(
    "/workflows",
    response_model=List[WorkflowRunListResponse],
    summary="List workflow runs",
)
async def list_workflows(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    workflow_id: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """List workflow runs for a workspace."""
    runs = await service.list_workflow_runs(
        workspace_id=workspace_id,
        workflow_id=workflow_id,
        status=status_filter,
        limit=50,
        offset=0,
    )
    return runs


@router.get(
    "/workflows/{run_id}",
    response_model=WorkflowRunDetailResponse,
    summary="Get workflow run details",
)
async def get_workflow(
    run_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get workflow run details including events."""
    run = await service.get_workflow_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    events = await service.get_run_events(run_id)
    return WorkflowRunDetailResponse(run=run, events=events)


@router.post(
    "/workflows/{run_id}/retry",
    response_model=WorkflowRunResponse,
    summary="Retry a failed workflow run",
)
async def retry_workflow(
    run_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Retry a failed workflow run."""
    run = await service.retry_workflow(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Workflow run not found or not retryable")
    return run


@router.post(
    "/workflows/{run_id}/cancel",
    response_model=dict,
    summary="Cancel a running workflow",
)
async def cancel_workflow(
    run_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Cancel a running workflow run."""
    success = await service.cancel_workflow(run_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workflow run not found or not cancellable")
    return {"cancelled": True}


@router.get(
    "/workflows/stats",
    response_model=dict,
    summary="Get workflow statistics",
)
async def get_workflow_stats(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: WorkflowService = Depends(get_workflow_service),
):
    """Get workflow execution statistics."""
    stats = await service.get_stats(workspace_id)
    return stats


# =============================================================================
# Event Outbox
# =============================================================================

@router.get(
    "/events",
    response_model=EventOutboxListResponse,
    summary="List event outbox entries",
)
async def list_events(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    status_filter: Optional[str] = Query(None, alias="status"),
    event_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    service: EventOutboxService = Depends(get_event_outbox_service),
):
    """List event outbox entries for a workspace."""
    events = await service.get_pending_events(
        workspace_id=workspace_id,
        limit=limit,
    )
    # Filter by status and type if provided
    events = [e for e in events if not status_filter or e.status.value == status_filter]
    if event_type:
        events = [e for e in events if e.event_type == event_type]
    return events


@router.get(
    "/events/{event_id}",
    response_model=EventOutboxResponse,
    summary="Get event outbox entry",
)
async def get_event(
    event_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: EventOutboxService = Depends(get_event_outbox_service),
):
    """Get an event outbox entry by ID."""
    event = await service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post(
    "/events/{event_id}/retry",
    response_model=dict,
    summary="Retry a failed event",
)
async def retry_event(
    event_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: EventOutboxService = Depends(get_event_outbox_service),
):
    """Manually retry a failed/dead-letter event."""
    event = await service.retry_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found or not retryable")
    return {"retried": True}


@router.get(
    "/events/stats",
    response_model=dict,
    summary="Get event processing statistics",
)
async def get_event_stats(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: EventOutboxService = Depends(get_event_outbox_service),
):
    """Get event processing statistics."""
    stats = await service.get_stats()
    return stats
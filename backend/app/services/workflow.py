from typing import Optional, List, Dict, Any, Callable, Awaitable
from uuid import UUID, uuid4
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
from sqlalchemy.orm import selectinload

from app.models import (
    WorkflowRun,
    WorkflowRunEvent,
    WorkflowStatus,
    EventOutbox,
    Profile,
    WorkspaceMember,
    WorkspaceRole,
    Notification,
    NotificationRule,
    NotificationDelivery,
    DeliveryStatus,
    NotificationChannel,
)
from app.services.event_outbox import EventOutboxService
from app.services.notification import NotificationService
from app.services.delivery import DeliveryService
from app.services.rules import RulesService
from app.services.n8n_adapter import N8nAdapter, get_n8n_adapter
from app.security.audit import audit_log
from app.core.config import settings
import logging
import re

logger = logging.getLogger(__name__)


# Type for workflow actions
ActionHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


class WorkflowRegistry:
    """Registry of allowed workflow actions."""

    def __init__(self):
        self.actions: Dict[str, ActionHandler] = {}
        self._register_builtin_actions()

    def _register_builtin_actions(self):
        """Register built-in workflow actions."""
        self.register("create_notification", self._action_create_notification)
        self.register("send_email", self._action_send_email)
        self.register("request_human_review", self._action_request_human_review)
        self.register("generate_report", self._action_generate_report)
        self.register("n8n_dispatch", self._action_n8n_dispatch)
        self.register("wait_for_event", self._action_wait_for_event)

    def register(self, action_name: str, handler: ActionHandler):
        """Register a new action handler."""
        if action_name in self.actions:
            raise ValueError(f"Action {action_name} already registered")
        self.actions[action_name] = handler

    def get_action(self, action_name: str) -> Optional[ActionHandler]:
        """Get an action handler by name."""
        return self.actions.get(action_name)

    def list_actions(self) -> List[str]:
        return list(self.actions.keys())

    # Built-in action handlers
    async def _action_create_notification(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create an in-app notification."""
        # This would be called with a notification service
        return {"status": "success", "action": "create_notification"}

    async def _action_send_email(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send an email notification."""
        return {"status": "success", "action": "send_email"}

    async def _action_request_human_review(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Request human review for a security decision."""
        return {"status": "success", "action": "request_human_review"}

    async def _action_generate_report(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a security report."""
        return {"status": "success", "action": "generate_report"}

    async def _action_n8n_dispatch(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch to n8n workflow."""
        return {"status": "success", "action": "n8n_dispatch"}

    async def _action_wait_for_event(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Wait for a specific event (placeholder for future async patterns)."""
        return {"status": "success", "action": "wait_for_event"}


class WorkflowService:
    """Service for executing workflow runs."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.registry = WorkflowRegistry()
        self.n8n_adapter = get_n8n_adapter()

    async def create_workflow_run(
        self,
        workspace_id: UUID,
        workflow_id: str,
        workflow_version: str,
        input_payload: Dict[str, Any],
        trigger_event_outbox_id: Optional[UUID] = None,
        trigger_event_type: Optional[str] = None,
        trigger_resource_type: Optional[str] = None,
        trigger_resource_id: Optional[UUID] = None,
        created_by: Optional[UUID] = None,
        timeout_minutes: int = 30,
    ) -> 'WorkflowRun':
        """Create a new workflow run."""
        idempotency_key = f"{workflow_id}:{workspace_id}:{datetime.utcnow().timestamp()}"

        run = WorkflowRun(
            workspace_id=workspace_id,
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            trigger_event_outbox_id=trigger_event_outbox_id,
            trigger_event_type=trigger_event_type,
            trigger_resource_type=trigger_resource_type,
            trigger_resource_id=trigger_resource_id,
            input_payload=input_payload,
            status=WorkflowStatus.PENDING,
            timeout_at=datetime.utcnow() + timedelta(minutes=timeout_minutes),
            idempotency_key=idempotency_key,
            created_by=created_by,
        )
        self.db.add(run)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=workspace_id,
            action="workflow.run_created",
            resource_type="workflow_run",
            resource_id=run.id,
            user_id=created_by,
            details={
                "workflow_id": workflow_id,
                "workflow_version": workflow_version,
            },
        )

        return run

    async def execute_workflow(self, run_id: UUID) -> 'WorkflowRun':
        """Execute a workflow run."""
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            raise ValueError(f"Workflow run {run_id} not found")

        if run.status != WorkflowStatus.PENDING:
            raise ValueError(f"Workflow run {run_id} is not in pending status: {run.status}")

        run.status = WorkflowStatus.RUNNING
        run.started_at = datetime.utcnow()
        run.current_action_index = 0
        run.actions_executed = []
        await self.db.flush()

        try:
            # Get workflow definition (would come from a workflow definition service)
            workflow_def = await self._get_workflow_definition(run.workflow_id, run.workflow_version)
            if not workflow_def:
                raise ValueError(f"Workflow definition not found: {run.workflow_id} v{run.workflow_version}")

            actions = workflow_def.get("actions", [])
            run.actions_executed = []

            for i, action in enumerate(actions):
                run.current_action_index = i

                action_name = action.get("name")
                action_params = action.get("params", {})

                # Resolve parameter templates
                resolved_params = self._resolve_params(action_params, run.input_payload)

                action_result = await self._execute_action(
                    run,
                    action_name,
                    resolved_params,
                )

                run.actions_executed.append({
                    "action": action_name,
                    "params": resolved_params,
                    "result": action_result,
                    "executed_at": datetime.utcnow().isoformat(),
                })

                if action_result.get("status") == "failed":
                    run.status = WorkflowStatus.FAILED
                    run.error_message = action_result.get("error", "Action failed")
                    run.error_category = "action_failed"
                    run.failed_at = datetime.utcnow()
                    break

            if run.status == WorkflowStatus.RUNNING:
                run.status = WorkflowStatus.COMPLETED
                run.completed_at = datetime.utcnow()
                run.output_payload = run.actions_executed[-1].get("result") if run.actions_executed else {}

        except Exception as e:
            run.status = WorkflowStatus.FAILED
            run.error_message = str(e)
            run.error_category = "execution_error"
            run.failed_at = datetime.utcnow()
            logger.error(f"Workflow run {run.id} failed: {e}")

        finally:
            run.completed_at = run.completed_at or datetime.utcnow()
            await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=run.workspace_id,
            action="workflow.run_completed",
            resource_type="workflow_run",
            resource_id=run.id,
            details={
                "workflow_id": run.workflow_id,
                "status": run.status.value,
                "error": run.error_message,
            },
        )

        return run

    def _resolve_params(self, params: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve parameter templates using context."""

        def resolve_value(value: Any) -> Any:
            if isinstance(value, str):
                # Replace {{key}} patterns
                def replacer(match):
                    key = match.group(1)
                    keys = key.split(".")
                    value = context
                    for k in keys:
                        if isinstance(value, dict):
                            value = value.get(k)
                        else:
                            return match.group(0)
                    return str(value) if value is not None else match.group(0)

                return re.sub(r'\{\{(\w+(?:\.\w+)*)\}\}', replacer, value)
            elif isinstance(value, dict):
                return {k: resolve_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [resolve_value(v) for v in value]
            return value

        return {k: resolve_value(v) for k, v in params.items()}

    async def _execute_action(
        self,
        run: 'WorkflowRun',
        action_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a single workflow action."""
        handler = self.registry.get_action(action_name)
        if not handler:
            return {"status": "failed", "error": f"Unknown action: {action_name}"}

        start_time = datetime.utcnow()
        try:
            result = await handler(params)
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            # Record action execution
            event = WorkflowRunEvent(
                workflow_run_id=run.id,
                workspace_id=run.workspace_id,
                action_type=action_name,
                action_name=action_name,
                action_input=params,
                action_output=result,
                status="completed" if result.get("status") == "success" else "failed",
                error_message=result.get("error") if result.get("status") == "failed" else None,
                duration_ms=duration_ms,
            )
            self.db.add(event)

            return result
        except Exception as e:
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            event = WorkflowRunEvent(
                workflow_run_id=run.id,
                workspace_id=run.workspace_id,
                action_type=action_name,
                action_name=action_name,
                action_input=params,
                action_output={"error": str(e)},
                status="failed",
                error_message=str(e),
                duration_ms=duration_ms,
            )
            self.db.add(event)
            return {"status": "failed", "error": str(e)}

    async def _get_workflow_definition(self, workflow_id: str, version: str) -> Optional[Dict[str, Any]]:
        """Get workflow definition. In production, this would come from a registry/database."""
        # Built-in workflows
        if workflow_id == "finding_triage":
            return {
                "version": "1.0",
                "actions": [
                    {"name": "create_notification", "params": {
                        "title": "New Finding: {{finding.title}}",
                        "message": "A new {{finding.severity}} severity finding was detected: {{finding.title}}",
                        "user_id": "{{finding.triaged_by}}",
                    }},
                ],
            }
        elif workflow_id == "remediation_approval_requested":
            return {
                "version": "1.0",
                "actions": [
                    {"name": "create_notification", "params": {
                        "title": "Remediation Approval Required",
                        "message": "Remediation proposal {{proposal.title}} requires your approval",
                        "user_id": "{{approver_id}}",
                    }},
                ],
            }
        elif workflow_id == "verification_completed":
            return {
                "version": "1.0",
                "actions": [
                    {"name": "create_notification", "params": {
                        "title": "Verification Completed",
                        "message": "Verification for finding {{finding_id}} completed with outcome {{outcome}}",
                        "user_id": "{{finding.triaged_by}}",
                    }},
                ],
            }

        return None

    async def get_run(self, run_id: UUID) -> Optional['WorkflowRun']:
        """Get a workflow run by ID."""
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        return result.scalar_one_or_none()

    async def list_workflow_runs(
        self,
        workspace_id: UUID,
        workflow_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List['WorkflowRun']:
        """List workflow runs for a workspace."""
        query = select(WorkflowRun).where(WorkflowRun.workspace_id == workspace_id)

        if workflow_id:
            query = query.where(WorkflowRun.workflow_id == workflow_id)
        if status:
            query = query.where(WorkflowRun.status == WorkflowStatus(status))

        query = query.order_by(WorkflowRun.created_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_run_events(self, run_id: UUID) -> List['WorkflowRunEvent']:
        """Get events for a workflow run."""
        result = await self.db.execute(
            select(WorkflowRunEvent).where(WorkflowRunEvent.workflow_run_id == run_id)
            .order_by(WorkflowRunEvent.executed_at)
        )
        return list(result.scalars().all())

    async def retry_workflow(self, run_id: UUID) -> Optional['WorkflowRun']:
        """Retry a failed workflow run."""
        run = await self.get_workflow_run(run_id)
        if not run:
            return None

        if run.status not in [WorkflowStatus.FAILED, WorkflowStatus.CANCELLED]:
            return None

        # Create new run with same parameters
        new_run = WorkflowRun(
            workspace_id=run.workspace_id,
            workflow_id=run.workflow_id,
            workflow_version=run.workflow_version,
            trigger_event_outbox_id=run.trigger_event_outbox_id,
            trigger_event_type=run.trigger_event_type,
            trigger_resource_type=run.trigger_resource_type,
            trigger_resource_id=run.trigger_resource_id,
            input_payload=run.input_payload,
            status=WorkflowStatus.PENDING,
            idempotency_key=f"{run.workflow_id}:{run.workspace_id}:retry:{datetime.utcnow().timestamp()}",
        )
        self.db.add(new_run)
        await self.db.flush()

        await audit_log(
            self.db,
            workspace_id=run.workspace_id,
            action="workflow.run_retried",
            resource_type="workflow_run",
            resource_id=new_run.id,
            details={
                "original_run_id": str(run.id),
                "workflow_id": run.workflow_id,
            },
        )

        return new_run

    async def cancel_workflow(self, run_id: UUID) -> bool:
        """Cancel a running workflow."""
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == run_id)
        )
        run = result.scalar_one_or_none()
        if not run:
            return False

        if run.status not in [WorkflowStatus.PENDING, WorkflowStatus.RUNNING]:
            return False

        run.status = WorkflowStatus.CANCELLED
        run.completed_at = datetime.utcnow()
        await self.db.flush()
        return True

    async def get_stats(self, workspace_id: Optional[UUID] = None) -> Dict[str, int]:
        """Get workflow execution statistics."""
        query = select(
            WorkflowRun.status,
            func.count(WorkflowRun.id)
        ).group_by(WorkflowRun.status)

        if workspace_id:
            query = query.where(WorkflowRun.workspace_id == workspace_id)

        result = await self.db.execute(query)
        return {status.value: count for status, count in result.all()}
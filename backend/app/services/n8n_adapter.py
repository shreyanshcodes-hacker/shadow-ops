from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from dataclasses import dataclass
import httpx
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class N8nDispatchResult:
    success: bool
    execution_id: Optional[str] = None
    error: Optional[str] = None
    response_data: Optional[Dict[str, Any]] = None


class N8nAdapter:
    """
    Optional n8n integration adapter.
    Disabled by default - requires explicit configuration.
    """

    def __init__(self):
        self.base_url = settings.N8N_BASE_URL
        self.api_key = settings.N8N_API_KEY
        self.webhook_secret = settings.N8N_WEBHOOK_SECRET
        self.enabled = settings.N8N_ENABLED and bool(self.base_url and self.api_key)
        self.allowed_workflows = set(settings.N8N_ALLOWED_WORKFLOWS.split(",")) if settings.N8N_ALLOWED_WORKFLOWS else set()

        if self.enabled:
            logger.info(f"n8n adapter enabled. Base URL: {self.base_url}")
            logger.info(f"Allowed workflows: {self.allowed_workflows}")
        else:
            logger.info("n8n adapter disabled (not configured or disabled)")

    def is_enabled(self) -> bool:
        return self.enabled

    def is_workflow_allowed(self, workflow_id: str) -> bool:
        """Check if a workflow is in the allowlist."""
        if not self.allowed_workflows:
            return False
        return workflow_id in self.allowed_workflows

    async def dispatch_event(
        self,
        workflow_id: str,
        event_payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> 'N8nDispatchResult':
        """
        Dispatch an event to an n8n workflow via webhook.
        Only allowed if adapter is enabled and workflow is allowlisted.
        """
        if not self.enabled:
            return N8nDispatchResult(
                success=False,
                error="n8n adapter is disabled",
            )

        if not self.is_workflow_allowed(workflow_id):
            return N8nDispatchResult(
                success=False,
                error=f"Workflow {workflow_id} not in allowlist",
            )

        webhook_url = f"{self.base_url.rstrip('/')}/webhook/{workflow_id}"

        payload = {
            "event": workflow_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "correlation_id": correlation_id,
            "payload": event_payload,
        }

        headers = {
            "Content-Type": "application/json",
        }

        if self.webhook_secret:
            headers["X-Webhook-Secret"] = self.webhook_secret

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers,
                    timeout=30.0,
                )

                if response.status_code in (200, 201, 202):
                    try:
                        data = response.json()
                    except Exception:
                        data = {"raw": response.text}

                    return N8nDispatchResult(
                        success=True,
                        execution_id=data.get("executionId") or data.get("executionId"),
                        response_data=data,
                    )
                else:
                    return N8nDispatchResult(
                        success=False,
                        error=f"n8n webhook returned {response.status_code}: {response.text}",
                    )

        except Exception as e:
            logger.error(f"n8n dispatch failed: {e}")
            return N8nDispatchResult(
                success=False,
                error=f"n8n dispatch failed: {str(e)}",
            )

    async def trigger_workflow(
        self,
        workflow_id: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> 'N8nDispatchResult':
        """
        Trigger an n8n workflow directly via API (for workflows that don't use webhooks).
        Requires n8n API access.
        """
        if not self.enabled:
            return N8nDispatchResult(
                success=False,
                error="n8n adapter is disabled",
            )

        if not self.is_workflow_allowed(workflow_id):
            return N8nDispatchResult(
                success=False,
                error=f"Workflow {workflow_id} not in allowlist",
            )

        url = f"{self.base_url.rstrip('/')}/api/v1/workflows/{workflow_id}/execute"

        headers = {
            "Content-Type": "application/json",
            "X-N8N-API-KEY": self.api_key,
        }

        body = {
            "workflowData": payload,
            "runData": {},
            "pinData": {},
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    url,
                    json=body,
                    headers=headers,
                    timeout=60.0,
                )

                if response.status_code in (200, 201, 202):
                    data = response.json()
                    return N8nDispatchResult(
                        success=True,
                        execution_id=data.get("id") or data.get("executionId"),
                        response_data=data,
                    )
                else:
                    return N8nDispatchResult(
                        success=False,
                        error=f"n8n API returned {response.status_code}: {response.text}",
                    )

        except Exception as e:
            logger.error(f"n8n workflow trigger failed: {e}")
            return N8nDispatchResult(
                success=False,
                error=f"n8n workflow trigger failed: {str(e)}",
            )

    async def get_workflow_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """Get the status of a workflow execution."""
        if not self.enabled:
            return None

        url = f"{self.base_url.rstrip('/')}/api/v1/executions/{execution_id}"
        headers = {
            "X-N8N-API-KEY": self.api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers, timeout=30.0)

                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(f"Failed to get execution status: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Failed to get execution status: {e}")
            return None

    def get_allowed_workflows(self) -> List[str]:
        """Get list of allowed workflow IDs."""
        return list(self.allowed_workflows)

    def get_config_status(self) -> Dict[str, Any]:
        """Get configuration status for debugging."""
        return {
            "enabled": self.enabled,
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "has_webhook_secret": bool(self.webhook_secret),
            "allowed_workflows": list(self.allowed_workflows),
        }


# Singleton instance
_n8n_adapter: Optional['N8nAdapter'] = None


def get_n8n_adapter() -> 'N8nAdapter':
    """Get or create the singleton n8n adapter instance."""
    global _n8n_adapter
    if _n8n_adapter is None:
        _n8n_adapter = N8nAdapter()
    return _n8n_adapter
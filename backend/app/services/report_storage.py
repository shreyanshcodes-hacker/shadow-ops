from typing import Optional
from uuid import UUID
from datetime import datetime, timedelta
import os

try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    create_client = None
    Client = None

from app.core.config import settings


class ReportStorageService:
    """Service for storing and retrieving report files via Supabase Storage."""

    def __init__(self):
        self.client: Optional[Client] = None
        self.bucket_name = "reports"
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Supabase client if credentials available."""
        if not SUPABASE_AVAILABLE:
            self.client = None
            return
        try:
            if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
                self.client = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_SERVICE_ROLE_KEY,
                )
        except Exception:
            # Storage unavailable - will use fallback
            self.client = None

    def _get_storage_path(
        self,
        workspace_id: UUID,
        report_id: UUID,
        format: str,
        filename: Optional[str] = None,
    ) -> str:
        """Generate storage path for report file."""
        if filename:
            return f"{workspace_id}/{report_id}/{filename}"
        return f"{workspace_id}/{report_id}/report.{format}"

    async def store_report(
        self,
        workspace_id: UUID,
        report_id: UUID,
        format: str,
        content: bytes,
        filename: Optional[str] = None,
    ) -> str:
        """Store report content in Supabase Storage."""
        path = self._get_storage_path(workspace_id, report_id, format, filename)

        if not self.client:
            # Storage unavailable - return local path as fallback
            # In production, this would write to local filesystem or return a local path
            local_dir = f"/tmp/reports/{workspace_id}/{report_id}"
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, filename or f"report.{format}")
            with open(local_path, "wb") as f:
                f.write(content)
            return local_path

        try:
            # Upload to Supabase Storage
            response = self.client.storage.from_(self.bucket_name).upload(
                path=path,
                file=content,
                file_options={
                    "content-type": "application/pdf" if format == "pdf" else "application/json",
                    "upsert": "true",
                },
            )

            if hasattr(response, 'error') and response.error:
                raise Exception(f"Storage upload failed: {response.error}")

            return path

        except Exception as e:
            # Fallback to local storage
            local_dir = f"/tmp/reports/{workspace_id}/{report_id}"
            os.makedirs(local_dir, exist_ok=True)
            local_path = os.path.join(local_dir, filename or f"report.{format}")
            with open(local_path, "wb") as f:
                f.write(content)
            return local_path

    async def get_download_url(
        self,
        storage_path: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """Generate signed download URL for a report file."""
        if not self.client:
            # Fallback: return local file path or None
            if os.path.exists(storage_path):
                return f"file://{storage_path}"
            return None

        try:
            # Generate signed URL
            response = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=storage_path,
                expires_in=expires_in,
            )

            if hasattr(response, 'error') and response.error:
                return None

            # Response format varies by supabase-py version
            if isinstance(response, dict):
                return response.get("signedURL") or response.get("signed_url")
            return getattr(response, 'signed_url', None) or getattr(response, 'signedURL', None)

        except Exception:
            return None

    async def delete_report(
        self,
        workspace_id: UUID,
        report_id: UUID,
    ) -> bool:
        """Delete all report files from storage."""
        if not self.client:
            return False

        try:
            # List and delete all files in the report directory
            prefix = f"{workspace_id}/{report_id}/"
            response = self.client.storage.from_(self.bucket_name).list(prefix=prefix)

            if hasattr(response, 'error') and response.error:
                return False

            files_to_delete = [f"{prefix}{f['name']}" for f in response]
            if files_to_delete:
                self.client.storage.from_(self.bucket_name).remove(files_to_delete)

            return True

        except Exception:
            return False

    async def get_file_metadata(
        self,
        storage_path: str,
    ) -> Optional[dict]:
        """Get metadata for a stored file."""
        if not self.client:
            if os.path.exists(storage_path):
                stat = os.stat(storage_path)
                return {
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            return None

        try:
            response = self.client.storage.from_(self.bucket_name).list(
                path=os.path.dirname(storage_path),
            )

            if hasattr(response, 'error') and response.error:
                return None

            filename = os.path.basename(storage_path)
            for f in response:
                if f['name'] == filename:
                    return {
                        "size": f.get('metadata', {}).get('size', 0),
                        "modified": f.get('updated_at'),
                        "mimetype": f.get('metadata', {}).get('mimetype'),
                    }

            return None

        except Exception:
            return None

    def is_available(self) -> bool:
        """Check if storage backend is available."""
        return self.client is not None
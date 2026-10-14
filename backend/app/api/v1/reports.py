from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.security.auth import get_current_user
from app.models import Profile, ReportType, ReportFormat, ReportStatus
from app.schemas import (
    DashboardMetrics,
    TrendResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    ReportListResponse,
    ReportResponse,
    ReportDetailResponse,
    ReportExportResponse,
)
from app.services.report_service import ReportService
from app.services.dashboard_metrics import DashboardMetricsService
from app.services.trends import TrendService
from app.security.audit import audit_log


router = APIRouter(prefix="/reports", tags=["reports"])


def get_report_service(db: AsyncSession = Depends(get_db)) -> ReportService:
    return ReportService(db)


def get_dashboard_service(db: AsyncSession = Depends(get_db)) -> DashboardMetricsService:
    return DashboardMetricsService(db)


def get_trend_service(db: AsyncSession = Depends(get_db)) -> TrendService:
    return TrendService(db)


@router.get(
    "/dashboard",
    response_model=DashboardMetrics,
    summary="Get workspace dashboard metrics",
)
async def get_dashboard_metrics(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    current_user: Profile = Depends(get_current_user),
    service: DashboardMetricsService = Depends(get_dashboard_service),
):
    """Get aggregated dashboard metrics for a workspace."""
    metrics = await service.get_workspace_metrics(workspace_id, current_user.id)
    return metrics


@router.get(
    "/dashboard/trends",
    response_model=TrendResponse,
    summary="Get workspace trend data",
)
async def get_dashboard_trends(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    period_start: Optional[str] = Query(None, description="ISO8601 start timestamp"),
    period_end: Optional[str] = Query(None, description="ISO8601 end timestamp"),
    severity_filters: Optional[List[str]] = Query(None, description="Filter by severity levels"),
    current_user: Profile = Depends(get_current_user),
    service: TrendService = Depends(get_trend_service),
):
    """Get time-series trend data for a workspace."""
    from datetime import datetime, timedelta

    end = datetime.fromisoformat(period_end) if period_end else datetime.utcnow()
    start = datetime.fromisoformat(period_start) if period_start else (end - timedelta(days=30))

    trends = await service.get_all_trends(
        workspace_id=workspace_id,
        period_start=start,
        period_end=end,
        severity_filters=severity_filters,
    )

    return TrendResponse(
        trends=trends["trends"],
        generated_at=datetime.fromisoformat(trends["generated_at"]),
        data_cutoff=datetime.fromisoformat(trends["data_cutoff"]),
    )


@router.post(
    "",
    response_model=GenerateReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new security report",
)
async def generate_report(
    request: GenerateReportRequest,
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Generate a new security report."""
    report = await service.create_report(current_user.id, request)

    # Estimate completion time based on report type
    estimates = {
        "executive_summary": 30,
        "technical_vulnerability": 60,
        "remediation_progress": 30,
        "verification_regression": 45,
        "asset_security_posture": 30,
    }

    return GenerateReportResponse(
        report=report,
        estimated_completion_seconds=estimates.get(report.report_type.value, 60),
    )


@router.get(
    "",
    response_model=List[ReportListResponse],
    summary="List reports for a workspace",
)
async def list_reports(
    workspace_id: UUID = Query(..., description="Workspace ID"),
    report_type: Optional[ReportType] = Query(None),
    status_filter: Optional[ReportStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """List reports for a workspace."""
    reports = await service.list_reports(
        workspace_id=workspace_id,
        user_id=current_user.id,
        report_type=report_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return reports


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report by ID",
)
async def get_report(
    report_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Get report metadata by ID."""
    report = await service.get_report(report_id, current_user.id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get(
    "/{report_id}/detail",
    response_model=ReportDetailResponse,
    summary="Get report with sections and exports",
)
async def get_report_detail(
    report_id: UUID,
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Get full report detail including sections and exports."""
    detail = await service.get_report_detail(report_id, current_user.id)
    if not detail:
        raise HTTPException(status_code=404, detail="Report not found")
    return detail


@router.post(
    "/{report_id}/export",
    response_model=ReportExportResponse,
    summary="Generate report export",
)
async def export_report(
    report_id: UUID,
    format: ReportFormat = Query(..., description="Export format"),
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Generate a new export for an existing report."""
    export = await service.export_report(report_id, current_user.id, format)
    return export


@router.get(
    "/{report_id}/download",
    summary="Get download URL for report export",
)
async def download_report(
    report_id: UUID,
    export_id: UUID = Query(..., description="Export ID"),
    current_user: Profile = Depends(get_current_user),
    service: ReportService = Depends(get_report_service),
):
    """Get signed download URL for a report export."""
    url = await service.get_download_url(export_id, current_user.id)
    if not url:
        raise HTTPException(status_code=404, detail="Export not found or expired")

    await audit_log(
        service.db,
        workspace_id=current_user.id,  # This would need to be the workspace_id from export
        user_id=current_user.id,
        action="report.downloaded",
        resource_type="report_export",
        resource_id=export_id,
        details={"report_id": str(report_id), "export_id": str(export_id)},
    )

    return {"download_url": url, "expires_in": 3600}
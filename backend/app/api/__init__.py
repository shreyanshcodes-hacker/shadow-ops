from fastapi import APIRouter

from app.api.v1 import health, auth, workspaces, assets, auth as auth_routes, scans, ai, findings, attack_paths, security_team, remediations, verifications, reports, notifications

api_router = APIRouter()

api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
api_router.include_router(assets.router, prefix="/workspaces", tags=["assets"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"])
api_router.include_router(auth_routes.router, prefix="/assets", tags=["authorizations"])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"])
api_router.include_router(findings.router, prefix="/findings", tags=["findings"])
api_router.include_router(attack_paths.router, prefix="/attack-paths", tags=["attack-paths"])
api_router.include_router(security_team.router, prefix="/security-team", tags=["security-team"])
api_router.include_router(remediations.router, prefix="/remediations", tags=["remediations"])
api_router.include_router(verifications.router, prefix="/verifications", tags=["verifications"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
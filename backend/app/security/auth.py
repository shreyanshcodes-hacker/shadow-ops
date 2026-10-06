import firebase_admin
from firebase_admin import credentials, auth as firebase_auth
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import logging
from uuid import UUID
from datetime import datetime

from app.core.config import settings
from app.db.session import get_db
from app.models import Profile, WorkspaceMember, WorkspaceRole, AssetAuthorization, AuthorizationStatus
from app.schemas import ProfileResponse
from app.security.audit import audit_log

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK
def initialize_firebase():
    if not firebase_admin._apps:
        cred_dict = {
            "type": "service_account",
            "project_id": settings.FIREBASE_PROJECT_ID,
            "client_email": settings.FIREBASE_CLIENT_EMAIL,
            "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n"),
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred, {
            "projectId": settings.FIREBASE_PROJECT_ID,
        })

initialize_firebase()

security = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    def __init__(self, detail: str, status_code: int = status.HTTP_401_UNAUTHORIZED):
        super().__init__(status_code=status_code, detail=detail)


async def verify_firebase_token(token: str) -> dict:
    try:
        decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
        return decoded_token
    except firebase_auth.InvalidIdTokenError as e:
        logger.warning(f"Invalid Firebase token: {e}")
        raise AuthError("Invalid authentication token")
    except firebase_auth.ExpiredIdTokenError:
        logger.warning("Expired Firebase token")
        raise AuthError("Authentication token has expired")
    except firebase_auth.RevokedIdTokenError:
        logger.warning("Revoked Firebase token")
        raise AuthError("Authentication token has been revoked")
    except Exception as e:
        logger.error(f"Firebase token verification failed: {e}")
        raise AuthError("Authentication failed")


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    if not credentials:
        raise AuthError("Authentication required")

    decoded_token = await verify_firebase_token(credentials.credentials)
    firebase_uid = decoded_token.get("uid")
    email = decoded_token.get("email")

    if not firebase_uid:
        raise AuthError("Invalid token: missing uid")

    # Lookup or create profile
    result = await db.execute(select(Profile).where(Profile.firebase_uid == firebase_uid))
    profile = result.scalar_one_or_none()

    if not profile:
        # Create new profile
        profile = Profile(
            firebase_uid=firebase_uid,
            email=email or "",
            display_name=decoded_token.get("name"),
            avatar_url=decoded_token.get("picture"),
        )
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        logger.info(f"Created new profile for Firebase UID: {firebase_uid}")
    else:
        # Update last login
        profile.last_login_at = datetime.utcnow()
        # Update profile info if changed
        if decoded_token.get("name") and profile.display_name != decoded_token.get("name"):
            profile.display_name = decoded_token.get("name")
        if decoded_token.get("picture") and profile.avatar_url != decoded_token.get("picture"):
            profile.avatar_url = decoded_token.get("picture")
        await db.commit()
        await db.refresh(profile)

    return profile


async def get_current_user_id(
    current_user: Profile = Depends(get_current_user),
) -> UUID:
    return current_user.id


def require_workspace_role(
    required_roles: List[WorkspaceRole],
    workspace_id_param: str = "workspace_id",
):
    async def dependency(
        workspace_id: UUID,
        current_user: Profile = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        result = await db.execute(
            select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == current_user.id,
            )
        )
        member = result.scalar_one_or_none()

        if not member or member.joined_at is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not a member of this workspace"
            )

        if member.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role: {[r.value for r in required_roles]}"
            )

        return member

    return dependency


# Common role dependencies
require_workspace_member = require_workspace_role([WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER])
require_workspace_admin = require_workspace_role([WorkspaceRole.OWNER, WorkspaceRole.ADMIN])
require_workspace_owner = require_workspace_role([WorkspaceRole.OWNER])


async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Optional[Profile]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials, db)
    except AuthError:
        return None


async def require_scan_authorization(
    asset_id: UUID,
    current_user: Profile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AssetAuthorization:
    """
    Dependency that validates an asset has valid authorization for scanning.
    
    NO AUTHORIZATION -> NO SCAN
    
    This enforces the critical security invariant that no scan can proceed
    without a verified, non-expired authorization record.
    """
    result = await db.execute(
        select(AssetAuthorization).where(AssetAuthorization.asset_id == asset_id)
    )
    auth = result.scalar_one_or_none()

    if not auth:
        await audit_log(
            db=db,
            workspace_id=auth.workspace_id if auth else UUID(int=0),
            action="scan.blocked",
            resource_type="scan",
            resource_id=asset_id,
            new_state={"reason": "missing_authorization", "asset_id": str(asset_id)},
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scan blocked: asset has no authorization record"
        )

    if auth.status != AuthorizationStatus.VERIFIED:
        await audit_log(
            db=db,
            workspace_id=auth.workspace_id,
            action="scan.blocked",
            resource_type="scan",
            resource_id=asset_id,
            new_state={"reason": f"authorization_status_{auth.status.value}", "asset_id": str(asset_id)},
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Scan blocked: authorization status is {auth.status.value} (must be VERIFIED)"
        )

    if auth.expires_at and auth.expires_at < datetime.utcnow():
        await audit_log(
            db=db,
            workspace_id=auth.workspace_id,
            action="scan.blocked",
            resource_type="scan",
            resource_id=asset_id,
            new_state={"reason": "authorization_expired", "asset_id": str(asset_id), "expires_at": auth.expires_at.isoformat()},
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scan blocked: authorization has expired"
        )

    # Verify user has access to the workspace
    from app.models import WorkspaceMember
    member_result = await db.execute(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == auth.workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
    )
    member = member_result.scalar_one_or_none()

    if not member or member.joined_at is None:
        await audit_log(
            db=db,
            workspace_id=auth.workspace_id,
            action="scan.blocked",
            resource_type="scan",
            resource_id=asset_id,
            new_state={"reason": "workspace_access_denied", "asset_id": str(asset_id)},
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Scan blocked: not a member of the asset's workspace"
        )

    return auth
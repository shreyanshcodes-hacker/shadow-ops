# Authentication Architecture

## Overview

ShadowOps uses **Firebase Authentication** as the identity provider. The backend verifies Firebase ID tokens on every request and maintains a synchronized `profiles` table in PostgreSQL.

## Authentication Flow

```
1. User signs in via Firebase (Email/Password, OAuth, SSO)
2. Firebase returns ID Token (JWT, 1hr expiry)
3. Frontend includes token: Authorization: Bearer <token>
4. Backend verifies token with Firebase Admin SDK
5. Backend extracts uid, email, claims
6. Backend looks up/creates ShadowOps profile
7. User context attached to request
8. Workspace middleware verifies membership
```

## Token Handling

| Aspect | Implementation |
|--------|----------------|
| Storage | HttpOnly Secure cookie (preferred) OR memory (SPA) |
| Refresh | Frontend handles via Firebase SDK `getIdToken(true)` |
| Backend Verification | Every request via FastAPI dependency |
| Clock Skew | Tolerate 60s |
| Revocation | Firebase handles; backend checks `revoked` claim |

## Backend Implementation

### FastAPI Dependency

```python
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Profile:
    if not credentials:
        raise AuthError("Authentication required")

    decoded_token = await verify_firebase_token(credentials.credentials)
    firebase_uid = decoded_token.get("uid")
    
    # Lookup or create profile
    profile = await profile_repo.get_by_firebase_uid(firebase_uid)
    if not profile:
        profile = await profile_repo.create(Profile(
            firebase_uid=firebase_uid,
            email=decoded_token.get("email"),
            display_name=decoded_token.get("name"),
            avatar_url=decoded_token.get("picture"),
        ))
    
    # Update last login
    profile.last_login_at = datetime.utcnow()
    await db.commit()
    
    return profile
```

### Firebase Token Verification

```python
async def verify_firebase_token(token: str) -> dict:
    try:
        decoded_token = firebase_auth.verify_id_token(token, check_revoked=True)
        return decoded_token
    except firebase_auth.InvalidIdTokenError:
        raise AuthError("Invalid authentication token")
    except firebase_auth.ExpiredIdTokenError:
        raise AuthError("Authentication token has expired")
    except firebase_auth.RevokedIdTokenError:
        raise AuthError("Authentication token has been revoked")
```

## Authorization Model

### Resource Hierarchy

```
Workspace (Root)
├── Members (with Roles)
├── Assets
│   └── Authorizations
├── Scans
├── Findings
├── Attack Paths
├── Remediations
├── Reports
├── Chat Conversations
└── Audit Logs
```

### Role Permissions Matrix

| Action | Owner | Admin | Member | Viewer |
|--------|-------|-------|--------|--------|
| Workspace: Delete | ✅ | ❌ | ❌ | ❌ |
| Workspace: Settings | ✅ | ✅ | ❌ | ❌ |
| Members: Invite | ✅ | ✅ | ❌ | ❌ |
| Members: Remove | ✅ | ✅ | ❌ | ❌ |
| Members: Change Role | ✅ | ✅* | ❌ | ❌ |
| Assets: Create | ✅ | ✅ | ✅ | ❌ |
| Assets: Delete | ✅ | ✅ | ✅** | ❌ |
| Assets: Manage Auth | ✅ | ✅ | ✅ | ❌ |
| Scans: Start | ✅ | ✅ | ✅ | ❌ |
| Scans: Cancel | ✅ | ✅ | ✅** | ❌ |
| Findings: View | ✅ | ✅ | ✅ | ✅ |
| Findings: Triage | ✅ | ✅ | ✅ | ❌ |
| Remediation: Approve | ✅ | ✅ | ❌ | ❌ |
| Remediation: Apply | ✅ | ✅ | ❌ | ❌ |
| Reports: Generate | ✅ | ✅ | ✅ | ❌ |
| Audit Logs: View | ✅ | ✅ | ❌ | ❌ |

* Admin cannot change Owner role
** Only if they created the asset/scan

### Backend Enforcement

```python
def require_workspace_role(
    required_roles: List[WorkspaceRole],
    workspace_id_param: str = "workspace_id",
):
    async def dependency(
        workspace_id: UUID,
        current_user: Profile = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> WorkspaceMember:
        member = await db.get_workspace_member(workspace_id, current_user.id)
        if not member or member.joined_at is None:
            raise Forbidden("Not a workspace member")
        if member.role not in required_roles:
            raise Forbidden(f"Requires role: {[r.value for r in required_roles]}")
        return member
    return dependency

# Common dependencies
require_workspace_member = require_workspace_role([OWNER, ADMIN, MEMBER])
require_workspace_admin = require_workspace_role([OWNER, ADMIN])
require_workspace_owner = require_workspace_role([OWNER])
```

## Workspace Isolation (RLS)

All workspace-scoped tables enforce Row Level Security:

```sql
-- Helper function
CREATE OR REPLACE FUNCTION current_user_workspace_ids()
RETURNS uuid[] LANGUAGE sql STABLE AS $$
  SELECT array_agg(workspace_id) FROM workspace_members
  WHERE user_id = auth.uid() AND joined_at IS NOT NULL;
$$;

-- Members can SELECT
CREATE POLICY "workspace_member_select" ON assets
  FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Admins/Owners can INSERT/UPDATE/DELETE
CREATE POLICY "workspace_admin_write" ON assets
  FOR ALL USING (
    workspace_id = ANY(current_user_workspace_ids()) AND
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = assets.workspace_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
      AND joined_at IS NOT NULL
    )
  );
```

## Security Rules

1. **Authentication Required** - Every API request authenticated
2. **Backend Authorization Mandatory** - Frontend never makes security decisions
3. **Workspace Isolation** - Zero data access across workspaces (enforced by RLS)
4. **Asset Authorization** - Scan only with verified `asset_authorizations.status = 'verified'`
5. **Secrets Never in Browser** - All secrets server-side only
6. **Audit Everything** - Immutable audit logs for all security-relevant actions

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/verify` | POST | Verify Firebase token |
| `/api/v1/auth/me` | GET | Current user profile |
| `/api/v1/workspaces` | GET | List user workspaces |
| `/api/v1/workspaces` | POST | Create workspace |
| `/api/v1/workspaces/{id}` | GET | Get workspace |
| `/api/v1/workspaces/{id}/members` | GET | List members |
| `/api/v1/workspaces/{id}/members` | POST | Invite member |

## Frontend Integration

```typescript
// Get Firebase token
const token = await getIdToken(true);

// API calls
const response = await fetch('/api/v1/workspaces', {
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json',
  },
});
```

## Error Responses

```json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "Authentication required",
    "details": {}
  }
}
```

| HTTP Code | Use Case |
|-----------|----------|
| 401 | Invalid/expired Firebase token |
| 403 | Workspace access denied, authorization missing |
| 404 | Resource not found |
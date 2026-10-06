# API Reference

## Base URL

```
Development: http://localhost:8000/api/v1
Production: https://api.shadowops.io/api/v1
```

## Authentication

All endpoints (except health) require Firebase ID token:

```
Authorization: Bearer <firebase-id-token>
```

## Error Format

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

## Health Endpoints

### GET /health

Basic health check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "environment": "development",
  "version": "0.1.0"
}
```

### GET /health/database

Database connectivity check.

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### GET /health/ready

Readiness check for Kubernetes.

**Response:**
```json
{
  "status": "ready",
  "checks": {
    "database": "healthy"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## Authentication

### POST /auth/verify

Verify Firebase token.

**Request:**
```json
{
  "token": "firebase-id-token"
}
```

**Response:**
```json
{
  "valid": true,
  "user": {
    "id": "uuid",
    "firebase_uid": "firebase-uid",
    "email": "user@example.com",
    "display_name": "John Doe",
    "avatar_url": null,
    "role": "user",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "last_login_at": "2024-01-15T10:30:00Z"
  }
}
```

### GET /auth/me

Get current user profile.

**Response:**
```json
{
  "id": "uuid",
  "firebase_uid": "firebase-uid",
  "email": "user@example.com",
  "display_name": "John Doe",
  "avatar_url": null,
  "role": "user",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "last_login_at": "2024-01-15T10:30:00Z"
}
```

### POST /auth/refresh

Refresh Firebase token.

**Response:**
```json
{
  "token": "new-firebase-id-token"
}
```

## Workspaces

### GET /workspaces

List user's workspaces.

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "My Workspace",
    "slug": "my-workspace",
    "plan": "free",
    "role": "owner",
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### POST /workspaces

Create workspace.

**Request:**
```json
{
  "name": "My Workspace",
  "slug": "my-workspace"
}
```

**Response:** 201 Created
```json
{
  "id": "uuid",
  "name": "My Workspace",
  "slug": "my-workspace",
  "owner_id": "uuid",
  "plan": "free",
  "settings": {},
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z",
  "deleted_at": null
}
```

### GET /workspaces/{workspace_id}

Get workspace details.

**Response:**
```json
{
  "id": "uuid",
  "name": "My Workspace",
  "slug": "my-workspace",
  "owner_id": "uuid",
  "plan": "free",
  "settings": {},
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "deleted_at": null
}
```

### PATCH /workspaces/{workspace_id}

Update workspace.

**Request:**
```json
{
  "name": "Updated Name",
  "settings": {
    "notifications": true,
    "retention_days": 90
  }
}
```

### DELETE /workspaces/{workspace_id}

Delete workspace (Owner only).

**Response:** 204 No Content

## Workspace Members

### GET /workspaces/{workspace_id}/members

List workspace members.

**Response:**
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "user_id": "uuid",
    "role": "owner",
    "invited_by": "uuid",
    "invited_at": "2024-01-01T00:00:00Z",
    "joined_at": "2024-01-01T00:00:00Z",
    "created_at": "2024-01-01T00:00:00Z",
    "user": {
      "id": "uuid",
      "email": "user@example.com",
      "display_name": "John Doe"
    }
  }
]
```

### POST /workspaces/{workspace_id}/members

Invite member (Admin+).

**Request:**
```json
{
  "email": "newuser@example.com",
  "role": "member"
}
```

### PATCH /workspaces/{workspace_id}/members/{user_id}

Update member role (Admin+).

**Request:**
```json
{
  "role": "admin"
}
```

### DELETE /workspaces/{workspace_id}/members/{user_id}

Remove member (Admin+).

**Response:** 204 No Content

## Assets

### GET /workspaces/{workspace_id}/assets

List assets.

**Response:**
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "name": "GitHub Repo",
    "type": "repository",
    "subtype": "github",
    "connection_config": {"url": "https://github.com/org/repo"},
    "credentials_ref": "vault:secret/github/org-repo",
    "criticality": "high",
    "status": "active",
    "last_scanned_at": "2024-01-15T08:00:00Z",
    "scan_frequency": "24 hours",
    "tags": ["production", "api"],
    "created_by": "uuid",
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z",
    "deleted_at": null
  }
]
```

### POST /workspaces/{workspace_id}/assets

Create asset (Member+).

**Request:**
```json
{
  "name": "GitHub Repo",
  "type": "repository",
  "subtype": "github",
  "connection_config": {
    "url": "https://github.com/org/repo",
    "branch": "main"
  },
  "credentials_ref": "vault:secret/github/org-repo",
  "criticality": "high",
  "tags": ["production"]
}
```

### GET /assets/{asset_id}

Get asset details.

### PATCH /assets/{asset_id}

Update asset (Member+).

### DELETE /assets/{asset_id}

Delete asset (Creator or Admin+).

## Asset Authorization

### POST /assets/{asset_id}/authorization

Create authorization record.

**Request:**
```json
{
  "authorization_type": "ownership",
  "evidence_files": [],
  "evidence_urls": ["https://example.com/policy.pdf"],
  "authorized_by": "CTO",
  "authorized_at": "2024-01-15T10:00:00Z",
  "expires_at": "2025-01-15T10:00:00Z",
  "notes": "Approved by CTO"
}
```

### GET /assets/{asset_id}/authorization

Get authorization status.

### POST /assets/{asset_id}/authorization/verify

Verify authorization (Admin+).

### POST /assets/{asset_id}/authorization/reject

Reject authorization (Admin+).

**Request:**
```json
{
  "notes": "Insufficient evidence"
}
```

## Scans (Placeholder - Full implementation in later stages)

### GET /workspaces/{workspace_id}/scans

List scans.

### POST /workspaces/{workspace_id}/scans

Start scan.

### GET /workspaces/{workspace_id}/scans/{scan_id}

Get scan details.

### POST /workspaces/{workspace_id}/scans/{scan_id}/cancel

Cancel scan.

### GET /workspaces/{workspace_id}/scans/{scan_id}/events

SSE stream for real-time scan events.

## Findings (Placeholder)

### GET /workspaces/{workspace_id}/findings

List findings with filters.

### GET /workspaces/{workspace_id}/findings/{finding_id}

Get finding details.

### PATCH /workspaces/{workspace_id}/findings/{finding_id}

Update finding status.

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| Auth | 10/minute |
| Scan Start | 5/minute per workspace |
| API Default | 100/minute per user |

## Pagination

```
?page=1&page_size=20
```

**Response:**
```json
{
  "data": [...],
  "total": 100,
  "page": 1,
  "page_size": 20,
  "total_pages": 5
}
```

## Filtering

```
?status=open&severity=critical&asset_id=uuid
```

## Webhooks (Future)

```
POST /webhooks/github
POST /webhooks/gitlab
```
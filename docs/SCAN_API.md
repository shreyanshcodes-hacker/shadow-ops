# SCAN API

## Base URL

```
/api/v1
```

## Authentication

All endpoints require valid Firebase ID token in Authorization header:

```
Authorization: Bearer <firebase_id_token>
```

## Endpoints

### Create Scan

**POST** `/scans`

Creates a new scan for an authorized asset.

#### Request

```json
{
  "asset_id": "uuid",
  "scan_type": "code",
  "scan_profile": "CODE_SECURITY",
  "scan_config": {}
}
```

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| asset_id | UUID | Yes | Asset to scan |
| scan_type | Enum | No | `full`, `recon`, `code`, `dependency`, `targeted` (default: `code`) |
| scan_profile | Enum | No | `QUICK`, `STANDARD`, `CODE_SECURITY` (default: `CODE_SECURITY`) |
| scan_config | Object | No | Additional scanner configuration |

#### Response

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "asset_id": "uuid",
  "scan_type": "code",
  "scan_profile": "CODE_SECURITY",
  "status": "queued",
  "triggered_by": "uuid",
  "triggered_at": "2024-01-15T10:30:00Z",
  "scan_config": {},
  "summary": {},
  "target_type": "repository",
  "target_reference": "https://github.com/org/repo",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:30:00Z"
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 201 | Scan created |
| 400 | Invalid request or asset not authorized |
| 401 | Invalid/missing authentication |
| 403 | Not a workspace member or insufficient role |
| 404 | Asset not found |

---

### List Scans

**GET** `/scans`

Returns scans for the authenticated user's workspace.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| status | Enum | Filter by status (`queued`, `running`, `completed`, `failed`, `cancelled`, `partial`) |
| limit | Integer | Max results (1-100, default 50) |
| offset | Integer | Pagination offset (default 0) |

#### Response

```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "asset_id": "uuid",
    "scan_type": "code",
    "scan_profile": "CODE_SECURITY",
    "status": "completed",
    "triggered_by": "uuid",
    "triggered_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:30:05Z",
    "completed_at": "2024-01-15T10:35:00Z",
    "duration_ms": 295000,
    "progress_percent": 100,
    "error_message": null,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

---

### Get Scan

**GET** `/scans/{scan_id}`

Returns full scan details with relationships.

#### Response

```json
{
  "id": "uuid",
  "workspace_id": "uuid",
  "asset_id": "uuid",
  "scan_type": "code",
  "scan_profile": "CODE_SECURITY",
  "status": "completed",
  "triggered_by": "uuid",
  "triggered_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:30:05Z",
  "completed_at": "2024-01-15T10:35:00Z",
  "failed_at": null,
  "cancelled_at": null,
  "authorization_confirmed_at": "2024-01-15T10:30:01Z",
  "duration_ms": 295000,
  "phases_completed": ["initialization", "authorization", "queued", "execution", "analysis", "semgrep", "completed"],
  "current_phase": "completed",
  "progress_percent": 100,
  "error_code": null,
  "error_message": null,
  "scan_config": {},
  "summary": {
    "total_findings": 5,
    "critical": 1,
    "high": 2,
    "medium": 1,
    "low": 1,
    "info": 0
  },
  "target_type": "repository",
  "target_reference": "https://github.com/org/repo",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z"
}
```

---

### Get Scan Events

**GET** `/scans/{scan_id}/events`

Returns immutable lifecycle events for a scan.

#### Response

```json
[
  {
    "id": 1,
    "scan_id": "uuid",
    "workspace_id": "uuid",
    "phase": "initialization",
    "event_type": "SCAN_CREATED",
    "message": "Scan created and queued",
    "data": {"scan_profile": "CODE_SECURITY", "scan_type": "code"},
    "created_at": "2024-01-15T10:30:00Z"
  },
  {
    "id": 2,
    "scan_id": "uuid",
    "workspace_id": "uuid",
    "phase": "authorization",
    "event_type": "AUTHORIZATION_CONFIRMED",
    "message": "Asset authorization verified",
    "data": {"authorization_id": "uuid", "authorization_type": "ownership"},
    "created_at": "2024-01-15T10:30:01Z"
  }
]
```

---

### Get Scan Summary

**GET** `/scans/{scan_id}/summary`

Returns finding counts by severity.

#### Response

```json
{
  "scan_id": "uuid",
  "status": "completed",
  "summary": {
    "total_findings": 5,
    "critical": 1,
    "high": 2,
    "medium": 1,
    "low": 1,
    "info": 0
  },
  "findings": {
    "total_findings": 5,
    "critical": 1,
    "high": 2,
    "medium": 1,
    "low": 1,
    "info": 0
  }
}
```

---

### Cancel Scan

**POST** `/scans/{scan_id}/cancel`

Cancels a queued or running scan.

#### Response

```json
{
  "status": "cancelled",
  "scan_id": "uuid"
}
```

#### Status Codes

| Code | Description |
|------|-------------|
| 200 | Scan cancelled |
| 400 | Scan cannot be cancelled (wrong status) |
| 403 | Not authorized (not requester or admin/owner) |
| 404 | Scan not found |

---

### Get Asset Scans

**GET** `/scans/assets/{asset_id}/scans`

Returns scans for a specific asset.

#### Query Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| limit | Integer | Max results (1-100, default 50) |
| offset | Integer | Pagination offset (default 0) |

#### Response

Same as List Scans.

---

## Error Responses

All errors follow the standard format:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

### Common Error Codes

| Code | HTTP | Description |
|------|------|-------------|
| AUTHORIZATION_FAILED | 403 | Asset not authorized for scanning |
| AUTHORIZATION_EXPIRED | 403 | Authorization has expired |
| AUTHORIZATION_PENDING | 403 | Authorization pending verification |
| AUTHORIZATION_REVOKED | 403 | Authorization was rejected |
| WORKSPACE_ACCESS_DENIED | 403 | Not a workspace member |
| ASSET_NOT_FOUND | 404 | Asset doesn't exist |
| SCAN_NOT_FOUND | 404 | Scan doesn't exist |
| INVALID_SCAN_STATUS | 400 | Invalid state transition |
| EXECUTION_FAILED | 500 | Scanner crashed |
| TIMEOUT | 504 | Scanner timeout |
| TARGET_TOO_LARGE | 413 | Target exceeds size limit |

---

## Scan Status Values

| Status | Description |
|--------|-------------|
| queued | Scan created, waiting for execution |
| running | Scan currently executing |
| completed | Scan finished successfully |
| failed | Scan encountered an error |
| cancelled | Scan cancelled by user |
| partial | Scan partially completed (future) |

## Scan Profile Values

| Profile | Description |
|---------|-------------|
| QUICK | Fast surface scan (secrets only) |
| STANDARD | Balanced depth and speed |
| CODE_SECURITY | Deep static analysis (SAST + SCA) |

## Scan Type Values

| Type | Description |
|------|-------------|
| full | Complete scan (all phases) |
| recon | Reconnaissance only |
| code | Static code analysis |
| dependency | Dependency scanning only |
| targeted | Specific target/path |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| POST /scans | 5/minute per workspace |
| GET /scans | 100/minute per user |
| GET /scans/{id} | 100/minute per user |
| POST /scans/{id}/cancel | 10/minute per user |

---

## Webhooks (Future)

Future stages will add webhook notifications for:
- scan.completed
- scan.failed
- scan.cancelled
- finding.critical
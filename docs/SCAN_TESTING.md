# SCAN TESTING

## Overview

This document describes the testing strategy for the ShadowOps scanning system, including unit tests, integration tests, security tests, and the critical security invariant verification.

## Test Structure

```
backend/tests/
├── test_services.py      # Service layer tests
├── test_api.py           # API endpoint tests
├── test_scans.py         # Scan-specific tests (security, lifecycle, runner)

frontend/__tests__/
├── auth.test.tsx         # Authentication tests
├── scans.test.tsx        # Scan UI and security tests
```

## Running Tests

### Backend

```bash
cd backend
pytest                    # Run all tests
pytest test_scans.py      # Scan-specific tests
pytest -v                 # Verbose output
pytest -k "scan"          # Filter scan-related tests
pytest --cov=app          # With coverage
```

### Frontend

```bash
cd frontend
npm test                  # Run all tests
npm test -- scans         # Scan-specific tests
npm test -- --coverage    # With coverage
```

## Test Categories

### 1. Authorization Tests (Security Critical)

These tests verify the **NO AUTHORIZATION → NO SCAN** invariant.

#### Backend: `test_scans.py::TestScanJobRunner`

| Test | Description | Expected |
|------|-------------|----------|
| `test_unauthorized_asset_never_reaches_scanner` | Missing authorization blocks scan | ScanAuthorizationError |
| `test_pending_authorization_blocks_scanner` | PENDING status blocks scan | ScanAuthorizationError |
| `test_revoked_authorization_blocks_scanner` | REJECTED status blocks scan | ScanAuthorizationError |
| `test_expired_authorization_blocks_scanner` | Expired auth blocks scan | ScanAuthorizationError |
| `test_valid_authorization_allows_scanner` | VERIFIED auth allows scan | Semgrep called |

#### Frontend: `scans.test.tsx`

| Test | Description |
|------|-------------|
| `test_missing_authorization_blocks_scan` | Missing auth → 403 |
| `test_pending_authorization_blocks_scan` | Pending → blocked UI |
| `test_revoked_authorization_blocks_scan` | Revoked → blocked UI |
| `test_expired_authorization_blocks_scan` | Expired → blocked UI |
| `test_authorized_asset_allows_scan` | Verified → scan button visible |

### 2. Scan Lifecycle Tests

#### Backend: `test_scans.py::TestScanService`

| Test | Description |
|------|-------------|
| `test_create_scan_success` | Valid scan creation with auth |
| `test_create_scan_no_authorization` | Missing auth raises error |
| `test_create_scan_pending_authorization` | Pending auth raises error |
| `test_create_scan_expired_authorization` | Expired auth raises error |
| `test_cancel_scan` | Cancel by requester |
| `test_cancel_scan_not_requester_or_admin` | Only requester/admin can cancel |

#### Backend: `test_scans.py::TestScanStateMachine`

| Test | Description |
|------|-------------|
| `test_valid_transitions` | QUEUED→RUNNING→COMPLETED |
| `test_invalid_transition_completed_to_running` | Rejected with error |

### 3. Cross-Workspace Security Tests

#### Backend: `test_scans.py::TestCrossWorkspaceSecurity`

| Test | Description |
|------|-------------|
| `test_user_cannot_scan_another_workspace_asset` | User A cannot scan User B's asset |

#### Backend: `test_scans.py::TestRoleEnforcement`

| Test | Description |
|------|-------------|
| `test_viewer_cannot_create_scan` | VIEWER role denied scan creation |

### 4. Finding Persistence Tests

#### Backend: `test_scans.py::TestFindingPersistence`

| Test | Description |
|------|-------------|
| `test_findings_persisted_with_correct_links` | Findings linked to workspace, scan, asset |

### 5. Summary Calculation Tests

#### Backend: `test_scans.py::TestSummaryCalculation`

| Test | Description |
|------|-------------|
| `test_summary_calculated_from_actual_results` | Counts from real findings, not hardcoded |

### 6. Scan API Tests

#### Backend: `test_api.py::TestScanEndpoints`

| Test | Description |
|------|-------------|
| `test_create_scan_unauthorized` | 401 without token |
| `test_create_scan_authorized` | 201 with valid token |
| `test_list_scans` | Returns user's scans |
| `test_get_scan` | Returns scan details |
| `test_cancel_scan` | Cancels running scan |

### 7. Frontend Integration Tests

#### Frontend: `scans.test.tsx`

| Test | Description |
|------|-------------|
| `renders scans page with empty state` | No scans shows empty state |
| `displays scans list with correct status badges` | Status badges render |
| `shows scan button only for authorized assets` | Auth check in UI |
| `filters scans by status` | Filter dropdown works |
| `displays scan overview with correct status` | Detail page status |
| `displays findings grouped by severity` | Findings tab |
| `shows events timeline grouped by phase` | Events tab |

## Critical Security Invariant Test

### The Mandatory Test

**File**: `backend/tests/test_scans.py::TestScanJobRunner::test_unauthorized_asset_never_reaches_scanner`

This test **must pass** for Stage 3 to be considered complete.

```python
async def test_unauthorized_asset_never_reaches_scanner(self, mock_db, sample_workspace, sample_asset):
    """Test the critical security invariant: NO AUTHORIZATION -> NO SCAN"""
    # Setup scan with RUNNING status
    # Setup NO authorization record
    # Execute scan
    # Assert ScanAuthorizationError raised
    # Assert Semgrep mock call_count == 0
```

### Verification Checklist

- [ ] Test exists in `test_scans.py`
- [ ] Test covers MISSING authorization
- [ ] Test covers PENDING authorization
- [ ] Test covers REVOKED authorization
- [ ] Test covers EXPIRED authorization
- [ ] Test covers WRONG WORKSPACE
- [ ] Test asserts Semgrep mock never called
- [ ] Test passes in CI

## Test Data Fixtures

### Sample Objects

```python
@pytest.fixture
def sample_profile():
    return Profile(
        id=uuid4(),
        firebase_uid="firebase-uid-123",
        email="test@example.com",
        display_name="Test User",
        role=UserRole.USER,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

@pytest.fixture
def sample_workspace(sample_profile):
    return Workspace(
        id=uuid4(),
        name="Test Workspace",
        slug="test-workspace",
        owner_id=sample_profile.id,
        plan="free",
        settings={},
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

@pytest.fixture
def sample_asset(sample_workspace, sample_profile):
    return Asset(
        id=uuid4(),
        workspace_id=sample_workspace.id,
        name="Test Repo",
        type=AssetType.REPOSITORY,
        subtype="github",
        connection_config={"url": "https://github.com/test/repo"},
        criticality=AssetCriticality.MEDIUM,
        status="active",
        created_by=sample_profile.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

@pytest.fixture
def sample_authorization(sample_asset, sample_workspace, sample_profile):
    return AssetAuthorization(
        id=uuid4(),
        asset_id=sample_asset.id,
        workspace_id=sample_workspace.id,
        authorization_type=AuthorizationType.OWNERSHIP,
        evidence_files=[],
        evidence_urls=[],
        authorized_by="Test User",
        authorized_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(days=30),
        status=AuthorizationStatus.VERIFIED,
        verified_by=sample_profile.id,
        verified_at=datetime.utcnow(),
    )
```

## Mocking Strategy

### Semgrep Mock

```python
with patch('app.scanning.runner.SemgrepManager') as mock_semgrep_class:
    mock_semgrep = AsyncMock()
    mock_semgrep.scan_code.return_value = []
    mock_semgrep.scan_dependencies.return_value = []
    mock_semgrep_class.return_value = mock_semgrep
```

### Database Mock

```python
mock_db = AsyncMock()
mock_scan_repo = AsyncMock()
mock_scan_repo.get_by_id.return_value = sample_scan
```

## Continuous Integration

### GitHub Actions (Future)

```yaml
name: Tests
on: [push, pull_request]
jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: cd backend && pip install -r requirements.txt
      - name: Run tests
        run: cd backend && pytest -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Node
        uses: actions/setup-node@v3
        with:
          node-version: '20'
      - name: Install dependencies
        run: cd frontend && npm ci
      - name: Run tests
        run: cd frontend && npm test -- --coverage
```

## Test Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Scan Service | 90% | TBD |
| Scan Runner | 95% | TBD |
| Scan API | 85% | TBD |
| Semgrep Integration | 90% | TBD |
| Frontend Scans | 80% | TBD |

## Manual Testing Checklist

### Pre-Deployment Verification

- [ ] Create workspace
- [ ] Create repository asset
- [ ] Create authorization (VERIFIED)
- [ ] Start scan → verify QUEUED → RUNNING → COMPLETED
- [ ] Verify findings appear in detail page
- [ ] Verify events timeline shows all phases
- [ ] Cancel running scan → verify CANCELLED
- [ ] Create asset without authorization → verify scan button disabled
- [ ] Create authorization PENDING → verify scan blocked
- [ ] Expire authorization → verify scan blocked
- [ ] Revoke authorization → verify scan blocked
- [ ] Cross-workspace access → verify 403
- [ ] VIEWER role → verify scan creation denied

### Security Verification

- [ ] No secrets in scan logs
- [ ] No credentials in finding evidence
- [ ] RLS policies block cross-workspace queries
- [ ] Semgrep never runs without authorization
- [ ] Target path validation prevents traversal
- [ ] Timeout kills long-running scans
- [ ] Cancel terminates Semgrep process

---

**Document Version**: 1.0  
**Last Updated**: Stage 3 Implementation
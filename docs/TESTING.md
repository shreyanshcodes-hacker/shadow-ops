# Testing Guide

## Test Pyramid

```
        E2E Tests (Few)
       /              \
   Integration Tests (Some)
  /                      \
Unit Tests (Many)
```

## Backend Testing

### Tools

- **pytest** - Test framework
- **pytest-asyncio** - Async support
- **httpx** - Async HTTP client for API testing
- **faker** - Test data generation
- **pytest-cov** - Coverage reporting

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific test file
pytest tests/test_auth.py -v

# Watch mode
pytest --watch
```

### Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── test_health.py           # Health endpoints
├── test_auth.py             # Authentication
├── test_workspaces.py       # Workspace CRUD
├── test_assets.py           # Asset management
├── test_authorizations.py   # Authorization flow
├── test_repositories.py     # Repository layer
├── test_services.py         # Service layer
└── test_security.py         # Security middleware
```

### Fixtures (conftest.py)

```python
@pytest.fixture
async def db_session():
    """Provide a test database session."""
    async with async_session_maker() as session:
        yield session
        await session.rollback()

@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = Profile(firebase_uid="test-uid", email="test@example.com")
    db_session.add(user)
    await db_session.flush()
    return user

@pytest.fixture
def test_workspace(db_session, test_user):
    """Create a test workspace."""
    ws = Workspace(name="Test Workspace", slug="test-ws", owner_id=test_user.id)
    db_session.add(ws)
    await db_session.flush()
    return ws

@pytest.fixture
def auth_headers(test_user):
    """Generate auth headers for test user."""
    # In real tests, use Firebase Admin SDK to create custom token
    return {"Authorization": f"Bearer test-token-{test_user.id}"}
```

### Example Tests

```python
# test_health.py
async def test_health_check(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

async def test_health_database(client):
    response = await client.get("/api/v1/health/database")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"

# test_auth.py
async def test_get_me_requires_auth(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401

async def test_get_me_with_valid_token(client, auth_headers):
    response = await client.get("/api/v1/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"

# test_workspaces.py
async def test_create_workspace(client, auth_headers):
    response = await client.post("/api/v1/workspaces", json={"name": "Test"}, headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test"
    assert data["owner_id"] is not None

async def test_list_workspaces(client, auth_headers, test_workspace):
    response = await client.get("/api/v1/workspaces", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1

async def test_workspace_isolation(client, auth_headers, test_workspace, other_user_workspace):
    # User cannot access other user's workspace
    response = await client.get(f"/api/v1/workspaces/{other_user_workspace.id}", headers=auth_headers)
    assert response.status_code == 403
```

## Frontend Testing

### Tools

- **Jest** - Test framework
- **React Testing Library** - Component testing
- **@testing-library/jest-dom** - Custom matchers

### Running Tests

```bash
cd frontend
npm run test          # Run once
npm run test:watch    # Watch mode
```

### Test Structure

```
frontend/
├── jest.config.js
├── jest.setup.ts
└── components/
    └── ui/
        ├── Button.test.tsx
        ├── Card.test.tsx
        └── ...
```

### Example Component Test

```tsx
// Button.test.tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { Button } from '@/components/ui/Button';

describe('Button', () => {
  it('renders children', () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole('button', { name: 'Click me' })).toBeInTheDocument();
  });

  it('handles click', () => {
    const handleClick = jest.fn();
    render(<Button onClick={handleClick}>Click me</Button>);
    fireEvent.click(screen.getByRole('button'));
    expect(handleClick).toHaveBeenCalledTimes(1);
  });

  it('shows loading state', () => {
    render(<Button loading>Click me</Button>);
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByTestId('spinner')).toBeInTheDocument();
  });

  it('applies variant classes', () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole('button')).toHaveClass('text-severity-critical');
  });
});
```

## Integration Testing

### API Integration Tests

```python
# test_scans_integration.py
async def test_scan_requires_authorization(client, auth_headers, test_asset):
    # Create asset without authorization
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/scans",
        json={"asset_id": str(test_asset.id), "scan_type": "full"},
        headers=auth_headers,
    )
    assert response.status_code == 403
    assert "authorization" in response.json()["error"]["message"].lower()

async def test_scan_with_valid_authorization(client, auth_headers, authorized_asset):
    response = await client.post(
        f"/api/v1/workspaces/{workspace_id}/scans",
        json={"asset_id": str(authorized_asset.id), "scan_type": "full"},
        headers=auth_headers,
    )
    assert response.status_code == 201
```

## Security Testing

### Secret Exposure Scan

```bash
# Install truffleHog
pip install trufflehog

# Scan for secrets
trufflehog filesystem . --no-verification
```

### Dependency Audit

```bash
# Backend
cd backend
pip-audit

# Frontend
cd frontend
npm audit
```

### SAST

```bash
# Backend
cd backend
semgrep scan --config=auto .

# Frontend
cd frontend
npm run lint
```

## Load Testing (Future)

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8000
```

## CI/CD Pipeline

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: cd backend && pip install -r requirements.txt
      - run: cd backend && pytest --cov=app

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: '20'
      - run: cd frontend && npm ci
      - run: cd frontend && npm run test
      - run: cd frontend && npm run typecheck
      - run: cd frontend && npm run lint

  security:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install trufflehog && trufflehog filesystem . --no-verification
```
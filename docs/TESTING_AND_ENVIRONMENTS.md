# TESTING & ENVIRONMENTS — ShadowOps

**Version:** 1.0
**Scope:** Backend (pytest) + Frontend (Jest) test strategy, environments, and CI integration

---

## 1. Test Philosophy

- **Unit tests** — Fast, isolated, no external dependencies, run on every commit
- **Integration tests** — Test service interactions with real DB (testcontainers), run on PR
- **Live integration tests** — Test against real Firebase/Supabase/Semgrep/AI providers, run manually/gated
- **E2E tests** — Full user flows, run in staging before release
- **Security tests** — Negative authorization, injection, boundary tests, run on every commit

**Rule:** Never disable a failing test. Fix the defect or mark as `BLOCKED` with issue reference.

---

## 2. Backend Testing (pytest)

### 2.1 Test Structure

```
backend/tests/
├── conftest.py              # Global fixtures, test env setup
├── test_ai.py               # AI provider, manager, security tests
├── test_ai_analyst.py       # AI analyst schema, safety tests
├── test_api.py              # API endpoint tests (FastAPI TestClient)
├── test_scans.py            # Scan service, runner, authorization
├── test_services.py         # Profile, Workspace, Asset services
├── test_remediation.py      # Remediation workflow, patch, approval
├── test_verification.py     # Verification, baseline, comparison
├── test_attack_paths.py     # MISSING — attack path, risk engine
├── test_reports.py          # MISSING — report generation, export
├── test_notifications.py    # MISSING — outbox, delivery, workflows
└── fixtures/                # Test data factories (to be created)
```

### 2.2 Test Configuration

**File:** `backend/tests/conftest.py`

Key fixtures:
- `mock_db` — AsyncMock SQLAlchemy session
- `sample_workspace_id`, `sample_user_id`, `sample_asset_id`, `sample_finding_id`
- `mock_profile` — Profile model with test data
- `mock_redis`, `mock_celery` — External service mocks (optional)
- **Firebase patched** — `MockCredential` prevents real Firebase calls

**Environment Variables (set in conftest.py):**
```python
DATABASE_URL = "postgresql+asyncpg://test:test@localhost:5432/test"
SUPABASE_URL = "http://localhost:54321"
SUPABASE_SERVICE_ROLE_KEY = "test-service-role-key"
SUPABASE_ANON_KEY = "test-anon-key"
SUPABASE_JWT_SECRET = "test-jwt-secret"
FIREBASE_PROJECT_ID = "test-project"
FIREBASE_CLIENT_EMAIL = "test@test-project.iam.gserviceaccount.com"
FIREBASE_PRIVATE_KEY = "-----BEGIN PRIVATE KEY-----...-----END PRIVATE KEY-----"
SECRET_KEY = "test-secret-key-for-testing-only"
GEMINI_API_KEY = "test-gemini-key"
GROK_API_KEY = "test-grok-key"
ENVIRONMENT = "test"
DEBUG = "true"
```

### 2.3 Running Tests

```bash
# Unit tests only (default)
cd backend && python -m pytest -v

# With coverage
cd backend && python -m pytest --cov=app --cov-report=term-missing

# Specific module
cd backend && python -m pytest tests/test_remediation.py -v

# Skip slow/integration tests
cd backend && python -m pytest -m "not integration" -v
```

### 2.4 Test Markers

```python
# conftest.py defines:
pytestmark = [
    pytest.mark.unit,        # Default
    pytest.mark.integration, # Requires testcontainers
    pytest.mark.live,        # Requires real credentials
    pytest.mark.security,    # Security boundary tests
    pytest.mark.slow,        # >10s
]
```

### 2.5 Current Test Status (2026-10-14)

| Module | Collected | Passed | Failed | Errors | Missing |
|--------|-----------|--------|--------|--------|---------|
| test_ai.py | 52 | ~35 | ~12 | 5 | — |
| test_ai_analyst.py | 14 | ~10 | ~4 | 0 | — |
| test_api.py | 28 | ~15 | ~8 | 5 | — |
| test_scans.py | 18 | ~12 | ~4 | 2 | — |
| test_services.py | 11 | ~8 | ~3 | 0 | — |
| test_remediation.py | 32 | ~28 | ~4 | 0 | — |
| test_verification.py | 15 | ~12 | ~3 | 0 | — |
| test_attack_paths.py | 0 | — | — | — | **MISSING** |
| test_reports.py | 0 | — | — | — | **MISSING** |
| test_notifications.py | 0 | — | — | — | **MISSING** |

---

## 3. Frontend Testing (Jest + React Testing Library)

### 3.1 Test Structure

```
frontend/
├── jest.config.js           # Jest configuration
├── jest.setup.ts            # Global mocks, setup
├── __tests__/
│   ├── auth.test.tsx        # Auth flow tests
│   ├── scans.test.tsx       # Scan page tests
│   └── ...                  # More test files needed
└── components/__tests__/    # Component tests (to be created)
```

### 3.2 Jest Configuration

**File:** `frontend/jest.config.js`
- Environment: `jsdom`
- Transform: `babel-jest` with `next/babel` preset
- Module mapper: `@/` → `<rootDir>/`
- Coverage threshold: 50% branches/functions/lines/statements

**File:** `frontend/jest.setup.ts`
Mocks:
- `next/navigation` — `useRouter`, `usePathname`, `useSearchParams`
- `next/link` — Renders as `<a>`
- `react-hot-toast` — `toast`, `Toaster`
- `@tanstack/react-query` — `useQuery`, `useMutation`, `QueryClient`
- `lucide-react` — All icons as `<svg data-testid>`

### 3.3 Running Tests

```bash
# Requires Node.js 20+ and pnpm
cd frontend && pnpm install
cd frontend && pnpm test           # Run once
cd frontend && pnpm test:watch     # Watch mode
cd frontend && pnpm test --coverage
```

### 3.4 Current Status

**BLOCKED** — Node.js/npm not available in test environment.

**Required to Unblock:**
1. Install Node.js 20+ (LTS)
2. Install pnpm: `corepack enable && corepack prepare pnpm@latest --activate`
3. Configure Firebase emulator for auth tests
4. Configure Supabase local dev stack for DB tests

---

## 4. Environment Definitions

| Environment | Purpose | Database | Firebase | AI Providers | Semgrep | Email | n8n |
|-------------|---------|----------|----------|--------------|---------|-------|-----|
| **Local Dev** | Developer iteration | Supabase Local (Docker) | Firebase Emulator | Mock/Fake | Local binary | Mock (logs) | Disabled |
| **CI Unit** | Fast feedback | SQLite (async) / Mock | MockCredential | FakeProvider | Mocked | Mock | Disabled |
| **CI Integration** | Service interaction | Testcontainers Postgres | Firebase Test Project | Test API Keys | Testcontainers Semgrep | Test SMTP (MailHog) | Disabled |
| **Staging** | Pre-release validation | Supabase Staging Project | Firebase Staging Project | Staging API Keys | Staging Runner | Staging SMTP | Staging n8n |
| **Production** | Live traffic | Supabase Prod Project | Firebase Prod Project | Prod API Keys | Isolated Workers | Prod SMTP | Prod n8n |

### 4.1 Local Development Setup

```bash
# 1. Start Supabase local
supabase start

# 2. Start Firebase emulator
firebase emulators:start --only auth,firestore

# 3. Backend
cd backend
cp .env.example .env
# Edit .env with local values
python -m uvicorn app.main:app --reload

# 4. Frontend
cd frontend
pnpm install
pnpm dev
```

### 4.2 CI Test Environment (GitHub Actions)

```yaml
# .github/workflows/test.yml (to be created)
services:
  postgres:
    image: postgres:16
    env:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    ports: ["5432:5432"]
    options: >-
      --health-cmd="pg_isready -U test"
      --health-interval=10s
      --health-timeout=5s
      --health-retries=5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

steps:
  - uses: actions/checkout@v4
  - name: Setup Python
    uses: actions/setup-python@v5
    with: { python-version: "3.12" }
  - name: Install deps
    run: pip install -r backend/requirements.txt
  - name: Run unit tests
    run: cd backend && python -m pytest -m "not integration" -v
  - name: Run integration tests
    run: cd backend && python -m pytest -m "integration" -v
    env:
      DATABASE_URL: postgresql+asyncpg://test:test@localhost:5432/test
      # ... other test env vars
```

---

## 5. Test Data Management

### 5.1 Fixtures Strategy

- **Factories** — Use `factory_boy` or custom builders for model creation
- **Isolation** — Each test gets fresh DB transaction (rollback after)
- **No Shared State** — No global test DB; use `async_session_maker` per test

### 5.2 Cleanup

```python
# conftest.py pattern
@pytest.fixture
async def db_session():
    async with async_session_maker() as session:
        yield session
        await session.rollback()  # Always rollback
```

### 5.3 Live Test Credentials

**Never commit real credentials.** Use:
- GitHub Actions secrets for CI
- 1Password/HashiCorp Vault for local
- `.env.local` (gitignored) for developer overrides

---

## 6. Security Testing Requirements

### 6.1 Mandatory Security Tests (Every Commit)

| Test Category | Examples |
|---------------|----------|
| AuthN negative | Expired token, revoked token, malformed token, missing token |
| AuthZ negative | Cross-workspace access, role escalation, object ID manipulation |
| Input validation | SQL injection, path traversal, XSS payloads, oversized requests |
| Scanner safety | Path escape, symlink attack, resource exhaustion |
| Patch safety | Path traversal in diff, disallowed files, hash mismatch |
| AI safety | Prompt injection, secret leakage, schema validation bypass |

### 6.2 Security Test Patterns

```python
# Example: Cross-workspace access test
async def test_user_cannot_access_another_workspace_asset(mock_db, user_a, user_b, asset_b):
    service = AssetService(mock_db)
    with pytest.raises(PermissionError):
        await service.get_asset(asset_b.id, workspace_id=user_a.workspace_id)
```

---

## 7. Dependency & Supply Chain Testing

### 7.1 Commands

```bash
# Backend
cd backend && pip-audit -r requirements.txt
cd backend && safety check -r requirements.txt

# Frontend
cd frontend && npm audit --audit-level=high
cd frontend && pnpm audit --audit-level=high
```

### 7.2 CI Integration

- Run on every PR
- Fail on CRITICAL/HIGH vulnerabilities
- Allow MEDIUM/LOW with documented acceptance

---

## 8. Test Documentation Standards

### 8.1 Test Naming

```
test_<unit>_<scenario>_<expected>
test_scan_service_create_scan_requires_authorization
test_patch_processor_rejects_path_traversal
test_auth_rejects_expired_firebase_token
```

### 8.2 Test Documentation

Each test file must have:
```python
"""
Test module: <feature>
Covers: <requirements/issue refs>
Fixtures: <key fixtures used>
External deps: <mocked/real>
"""
```

---

## 9. Known Test Gaps (Stage 12)

| Gap | Priority | Owner | Target |
|-----|----------|-------|--------|
| Missing `test_attack_paths.py` | HIGH | — | Pilot |
| Missing `test_reports.py` | HIGH | — | Pilot |
| Missing `test_notifications.py` | HIGH | — | Pilot |
| Frontend test environment | CRITICAL | — | Pilot |
| Live Firebase integration test | CRITICAL | — | Pilot |
| Live Supabase RLS test | CRITICAL | — | Pilot |
| Scanner isolation test | CRITICAL | — | Pilot |
| Patch apply/rollback E2E test | CRITICAL | — | Pilot |
| Verification independence test | CRITICAL | — | Pilot |
| Secret scanning in CI | HIGH | — | Pilot |
| Migration test suite | HIGH | — | Pilot |
| Backup/restore drill | MEDIUM | — | Production |

---

## 10. References

- `docs/STAGE_12_BASELINE.md` — Baseline audit matrix
- `docs/SECURITY_AUDIT.md` — Detailed security findings
- `docs/RELEASE_READINESS.md` — Release criteria
- `pytest.ini` — (to be created) pytest configuration
- `.github/workflows/` — (to be created) CI pipelines
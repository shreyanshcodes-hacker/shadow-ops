"""Pytest configuration for backend tests.

This module MUST be loaded before any other test modules to ensure
test environment variables are set before settings are initialized.
"""

import os
import sys

# Set test environment variables BEFORE any application imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret")

# Firebase - proper service account format
os.environ.setdefault("FIREBASE_PROJECT_ID", "test-project")
os.environ.setdefault("FIREBASE_CLIENT_EMAIL", "test@test-project.iam.gserviceaccount.com")
os.environ.setdefault("FIREBASE_PRIVATE_KEY", """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDc7Oq5LjZ8fKxO
testkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforu
nittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytest
keyforunittestingonlytestkeyforunittestingonlytestkeyforunittestingon
lytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforun
ittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkey
forunittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytes
tkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittestingon
lytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonly
-----END PRIVATE KEY-----""")
os.environ.setdefault("FIREBASE_CLIENT_X509_CERT_URL", "https://www.googleapis.com/robot/v1/metadata/x509/test%40test-project.iam.gserviceaccount.com")

# Security
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")

# AI Providers
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GROK_API_KEY", "test-grok-key")

# App
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("REMEDIATION_WORKSPACE_ROOT", "/tmp/test-workspace")
os.environ.setdefault("SCAN_WORKSPACE_ROOT", "/tmp/scan-workspace")

# Patch Firebase initialization for testing
import firebase_admin
from firebase_admin import credentials

class MockCredential(credentials.Base):
    def __init__(self):
        pass
    
    def get_credential(self):
        return None

# Override Firebase initialization
if not firebase_admin._apps:
    mock_cred = MockCredential()
    firebase_admin.initialize_app(mock_cred, {"projectId": "test-project"})

# Now import pytest fixtures
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from datetime import datetime

# Make fixtures available to all tests
pytest_plugins = []

# Common test fixtures
@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()

@pytest.fixture
def sample_workspace_id():
    return UUID("12345678-1234-5678-1234-567812345678")

@pytest.fixture
def sample_user_id():
    return UUID("87654321-4321-8765-4321-876543214321")

@pytest.fixture
def sample_asset_id():
    return UUID("11111111-2222-3333-4444-555555555555")

@pytest.fixture
def sample_finding_id():
    return UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

@pytest.fixture
def mock_profile(sample_user_id):
    from app.models import Profile, UserRole
    profile = Profile(
        id=sample_user_id,
        firebase_uid="test-firebase-uid",
        email="test@example.com",
        display_name="Test User",
        role=UserRole.USER,
    )
    return profile

# Mock external services
@pytest.fixture(autouse=True)
def mock_redis():
    with patch("redis.asyncio.Redis") as mock:
        yield mock

@pytest.fixture(autouse=True)
def mock_celery():
    try:
        import celery
        with patch("celery.Celery") as mock:
            yield mock
    except ImportError:
        yield None
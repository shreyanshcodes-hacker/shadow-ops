# Test environment configuration
import os

# Database
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
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunit
estingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforu
nittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkey
forunittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytest
keyforunittestingonlytestkeyforunittestingonlytestkeyforunittestingonly
testkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittesting
onlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunitt
estingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforun
ittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyf
orunittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestk
eyforunittestingonlytestkeyforunittestingonlytestkeyforunittestingonlyte
stkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittestingonly
testkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittesting
onlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforunittest
ingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyforuni
ttestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkeyfor
unittestingonlytestkeyforunittestingonlytestkeyforunittestingonlytestkey
forunittestingonly
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

# Patch the initialize_firebase function to use a mock
import sys
import firebase_admin
from firebase_admin import credentials

# Create a mock credential that doesn't require full validation
class MockCredential(credentials.Base):
    def __init__(self):
        pass
    
    def get_credential(self):
        return None

# Override the initialize_firebase function after it's loaded
def patch_firebase():
    """Patch Firebase initialization for testing."""
    if not firebase_admin._apps:
        # Use a mock credential
        mock_cred = MockCredential()
        firebase_admin.initialize_app(mock_cred, {"projectId": "test-project"})

# Apply patch immediately
patch_firebase()
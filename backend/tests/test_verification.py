import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from datetime import datetime

# Import test config first to set environment variables
from tests.test_config import patch_firebase

# Patch Firebase before any other imports
patch_firebase()

from app.models import (
    VerificationJob,
    VerificationBaseline,
    VerificationCheck,
    EvidenceComparison,
    VerificationPolicy,
    VerificationReview,
    VerificationStatus,
    VerificationOutcome,
    CheckStatus,
    CheckType,
    ComparisonCategory,
    ReviewDecision,
    Finding,
    Asset,
    ScanTarget,
    RemediationProposal,
    RemediationApplication,
    RemediationVerificationHandoff,
    VerificationHandoffStatus,
    Profile,
    Workspace,
    WorkspaceMember,
    WorkspaceRole,
    FindingSeverity,
    FindingConfidence,
    FindingStatus,
)
from app.services.baseline import BaselineCaptureService
from app.services.comparison import EvidenceComparisonService
from app.services.regression import RegressionAnalysisService
from app.services.policy import VerificationPolicyEngine
from app.services.verification import VerificationService
from app.schemas import StartVerificationRequest, VerificationReviewRequest, RerunVerificationRequest


@pytest.fixture
def mock_db():
    """Mock database session."""
    return AsyncMock()


@pytest.fixture
def mock_user():
    """Mock user profile."""
    user = MagicMock(spec=Profile)
    user.id = uuid4()
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_workspace():
    """Mock workspace."""
    ws = MagicMock(spec=Workspace)
    ws.id = uuid4()
    ws.name = "Test Workspace"
    return ws


@pytest.fixture
def mock_finding():
    """Mock finding."""
    finding = MagicMock(spec=Finding)
    finding.id = uuid4()
    finding.workspace_id = uuid4()
    finding.title = "Test Finding"
    finding.description = "Test Description"
    finding.severity = FindingSeverity.HIGH
    finding.confidence = FindingConfidence.MEDIUM
    finding.source_rule_id = "test-rule-123"
    finding.location = {"path": "test.py", "start_line": 10, "end_line": 20}
    finding.cwe_ids = ["CWE-79"]
    finding.cve_ids = []
    finding.owasp_categories = ["A03:2021"]
    finding.code_snippet = "test code"
    finding.remediation_guidance = "Fix the issue"
    finding.risk_score = 75.0
    finding.risk_factors = {}
    finding.status = FindingStatus.OPEN
    finding.source = MagicMock(value="semgrep")
    return finding


@pytest.fixture
def mock_asset():
    """Mock asset."""
    asset = MagicMock(spec=Asset)
    asset.id = uuid4()
    asset.workspace_id = uuid4()
    asset.connection_config = {"local_path": "/workspace"}
    return asset


@pytest.fixture
def mock_scan_target():
    """Mock scan target."""
    target = MagicMock(spec=ScanTarget)
    target.id = uuid4()
    return target


@pytest.fixture
def mock_proposal(mock_finding):
    """Mock remediation proposal."""
    proposal = MagicMock(spec=RemediationProposal)
    proposal.id = uuid4()
    proposal.finding_id = mock_finding.id
    proposal.suggested_tests = [{"command": "pytest", "description": "Run tests"}]
    proposal.patch_versions = []
    return proposal


@pytest.fixture
def mock_application(mock_proposal, mock_finding, mock_asset):
    """Mock remediation application."""
    app = MagicMock(spec=RemediationApplication)
    app.id = uuid4()
    app.workspace_id = mock_finding.workspace_id
    app.asset_id = mock_asset.id
    app.proposal_id = mock_proposal.id
    app.target_revision = "abc123"
    return app


@pytest.fixture
def mock_handoff(mock_proposal, mock_application, mock_finding, mock_asset):
    """Mock verification handoff."""
    handoff = MagicMock(spec=RemediationVerificationHandoff)
    handoff.id = uuid4()
    handoff.proposal_id = mock_proposal.id
    handoff.application_id = mock_application.id
    handoff.finding_id = mock_finding.id
    handoff.asset_id = mock_asset.id
    handoff.patch_hash = "patch_hash_123"
    handoff.repository_revision = "rev123"
    handoff.changed_files = []
    handoff.validation_results = {"scanner_config": {}}
    handoff.original_finding_snapshot = {"id": str(mock_finding.id)}
    handoff.applied_at = datetime.utcnow()
    handoff.applied_by = uuid4()
    handoff.status = VerificationHandoffStatus.VERIFICATION_REQUESTED
    handoff.proposal = mock_proposal
    return handoff


class TestBaselineCaptureService:
    """Tests for BaselineCaptureService."""

    @pytest.mark.asyncio
    async def test_compute_finding_fingerprint(self, mock_db, mock_finding):
        """Test finding fingerprint computation."""
        service = BaselineCaptureService(mock_db)

        evidence = []
        rule_ids = ["test-rule-123"]

        fingerprint = service._compute_finding_fingerprint(mock_finding, evidence, rule_ids)

        assert fingerprint is not None
        assert len(fingerprint) == 64  # SHA256 hex length

    @pytest.mark.asyncio
    async def test_compute_evidence_hash(self, mock_db):
        """Test evidence hash computation."""
        service = BaselineCaptureService(mock_db)

        evidence = MagicMock()
        evidence.content = {"key": "value"}
        evidence.metadata = {}

        hash_val = service._compute_evidence_hash(evidence)

        assert hash_val is not None
        assert len(hash_val) == 64


class TestEvidenceComparisonService:
    """Tests for EvidenceComparisonService."""

    @pytest.mark.asyncio
    async def test_normalize_file_path(self, mock_db):
        """Test file path normalization."""
        service = EvidenceComparisonService(mock_db)

        assert service._normalize_file_path("path/to/file.py") == "path/to/file.py"
        assert service._normalize_file_path("\\path\\to\\file.py") == "path/to/file.py"
        assert service._normalize_file_path("/path/to/file.py") == "path/to/file.py"

    @pytest.mark.asyncio
    async def test_compute_semgrep_finding_fingerprint(self, mock_db):
        """Test semgrep finding fingerprint computation."""
        service = EvidenceComparisonService(mock_db)

        finding = MagicMock()
        finding.path = "test.py"
        finding.start_line = 10
        finding.end_line = 20
        finding.start_col = 0
        finding.end_col = 10
        finding.extra = {"message": "test", "severity": "HIGH"}
        finding.code_snippet = "test code"

        fingerprint = service._compute_semgrep_finding_fingerprint(finding, "test-rule")

        assert fingerprint is not None
        assert len(fingerprint) == 64


class TestRegressionAnalysisService:
    """Tests for RegressionAnalysisService."""

    @pytest.mark.asyncio
    async def test_is_command_allowed(self, mock_db, mock_asset, mock_scan_target):
        """Test command allowlist checking."""
        service = RegressionAnalysisService(mock_db)

        mock_asset.connection_config = {"regression_test_allowlist": ["pytest", "npm test"]}

        assert service._is_command_allowed("pytest tests/", ["pytest", "npm test"]) is True
        assert service._is_command_allowed("npm test", ["pytest", "npm test"]) is True
        assert service._is_command_allowed("rm -rf /", ["pytest", "npm test"]) is False

    @pytest.mark.asyncio
    async def test_get_allowlist(self, mock_db, mock_asset, mock_scan_target):
        """Test getting allowlist from asset config."""
        service = RegressionAnalysisService(mock_db)

        mock_asset.connection_config = {"regression_test_allowlist": ["custom test"]}

        allowlist = service._get_allowlist(mock_asset, mock_scan_target)
        assert "custom test" in allowlist


class TestVerificationPolicyEngine:
    """Tests for VerificationPolicyEngine."""

    @pytest.mark.asyncio
    async def test_determine_outcome_all_passed(self, mock_db):
        """Test outcome determination when all checks pass."""
        engine = VerificationPolicyEngine(mock_db)

        results = {
            "baseline_valid": True,
            "scanner_execution": CheckStatus.PASSED,
            "original_vulnerability": CheckStatus.PASSED,
            "evidence_comparison": CheckStatus.PASSED,
            "regression_analysis": CheckStatus.PASSED,
            "test_execution": CheckStatus.PASSED,
        }

        outcome = engine._determine_outcome(results, {})

        assert outcome == VerificationOutcome.VERIFIED_CANDIDATE

    @pytest.mark.asyncio
    async def test_determine_outcome_any_failed(self, mock_db):
        """Test outcome determination when any check fails."""
        engine = VerificationPolicyEngine(mock_db)

        results = {
            "baseline_valid": True,
            "scanner_execution": CheckStatus.PASSED,
            "original_vulnerability": CheckStatus.FAILED,
            "evidence_comparison": CheckStatus.PASSED,
        }

        outcome = engine._determine_outcome(results, {})

        assert outcome == VerificationOutcome.FAILED

    @pytest.mark.asyncio
    async def test_determine_outcome_blocked(self, mock_db):
        """Test outcome determination when check is blocked."""
        engine = VerificationPolicyEngine(mock_db)

        results = {
            "baseline_valid": True,
            "scanner_execution": CheckStatus.BLOCKED,
            "original_vulnerability": CheckStatus.PASSED,
        }

        outcome = engine._determine_outcome(results, {})

        assert outcome == VerificationOutcome.BLOCKED


class TestVerificationService:
    """Tests for VerificationService."""

    @pytest.mark.asyncio
    async def test_create_verification_job(self, mock_db, mock_user, mock_application, mock_proposal, mock_finding):
        """Test creating a verification job."""
        with patch('app.services.verification.VerificationPolicyEngine.create_default_policy') as mock_policy:
            mock_policy.return_value = AsyncMock()

            # Add mock patch_version to proposal
            mock_patch_version = MagicMock()
            mock_patch_version.patch_hash = "test_patch_hash"
            mock_proposal.patch_versions = [mock_patch_version]

            service = VerificationService(mock_db)
            service.application_repo.get_by_id = AsyncMock(return_value=mock_application)
            service.proposal_repo.get_by_id = AsyncMock(return_value=mock_proposal)
            service.finding_repo.get_by_id = AsyncMock(return_value=mock_finding)
            service._verify_workspace_access = AsyncMock(return_value=MagicMock())
            
            # Mock db.execute for idempotency check
            mock_result = MagicMock()
            mock_result.scalar_one_or_none = MagicMock(return_value=None)
            mock_db.execute = AsyncMock(return_value=mock_result)

            job = await service.create_verification_job(
                user_id=mock_user.id,
                remediation_application_id=mock_application.id,
                idempotency_key="test-key",
            )

            assert job is not None
            assert job.workspace_id == mock_application.workspace_id
            assert job.status == VerificationStatus.QUEUED

    @pytest.mark.asyncio
    async def test_submit_review_accept(self, mock_db, mock_user, mock_finding):
        """Test submitting accept review."""
        job = MagicMock(spec=VerificationJob)
        job.id = uuid4()
        job.workspace_id = uuid4()
        job.status = VerificationStatus.PASSED_PENDING_REVIEW
        job.overall_outcome = VerificationOutcome.VERIFIED_CANDIDATE
        job.finding_id = mock_finding.id

        with patch('app.services.verification.FindingRepository') as mock_finding_repo:
            mock_finding_repo.return_value.get_by_id = AsyncMock(return_value=mock_finding)

            service = VerificationService(mock_db)
            service._verify_workspace_access = AsyncMock(return_value=MagicMock(role=WorkspaceRole.ADMIN))
            service.get_verification_job = AsyncMock(return_value=job)
            service.finding_repo.get_by_id = AsyncMock(return_value=mock_finding)

            result = await service.submit_review(
                job_id=job.id,
                user_id=mock_user.id,
                decision="accept",
                justification="Fix verified",
            )

            assert result.status == VerificationStatus.VERIFIED
            assert mock_finding.status == FindingStatus.FIXED


class TestVerificationSchemas:
    """Tests for verification schemas."""

    def test_start_verification_request(self):
        """Test StartVerificationRequest schema."""
        request = StartVerificationRequest(
            remediation_application_id=uuid4(),
            idempotency_key="test-key",
        )
        assert request.remediation_application_id is not None
        assert request.idempotency_key == "test-key"

    def test_verification_review_request(self):
        """Test VerificationReviewRequest schema."""
        request = VerificationReviewRequest(
            verification_job_id=uuid4(),
            decision=ReviewDecision.ACCEPT,
            justification="Fix verified",
        )
        assert request.decision == ReviewDecision.ACCEPT
        assert request.justification == "Fix verified"

    def test_rerun_verification_request(self):
        """Test RerunVerificationRequest schema."""
        request = RerunVerificationRequest(
            verification_job_id=uuid4(),
            idempotency_key="rerun-key",
        )
        assert request.idempotency_key == "rerun-key"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
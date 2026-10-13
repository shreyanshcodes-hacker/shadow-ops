-- Stage 9: Independent Fix Verification & Regression Analysis
-- Migration: 0007_stage9_verification.sql
-- Created: 2026-10-13

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE verification_status AS ENUM (
    'QUEUED',
    'RUNNING',
    'BASELINE_CHECK',
    'RESCANNING',
    'REGRESSION_CHECK',
    'COMPARING_EVIDENCE',
    'PASSED_PENDING_REVIEW',
    'VERIFIED',
    'FAILED',
    'INCONCLUSIVE',
    'BLOCKED',
    'CANCELED'
);

CREATE TYPE verification_outcome AS ENUM (
    'VERIFIED_CANDIDATE',
    'FAILED',
    'INCONCLUSIVE',
    'BLOCKED'
);

CREATE TYPE check_status AS ENUM (
    'PENDING',
    'RUNNING',
    'PASSED',
    'FAILED',
    'SKIPPED',
    'BLOCKED',
    'ERROR'
);

CREATE TYPE check_type AS ENUM (
    'ORIGINAL_VULNERABILITY',
    'REGRESSION_ANALYSIS',
    'SCANNER_EXECUTION',
    'TEST_EXECUTION',
    'EVIDENCE_COMPARISON'
);

CREATE TYPE comparison_category AS ENUM (
    'STILL_PRESENT',
    'NO_LONGER_DETECTED',
    'MODIFIED_OR_MOVED',
    'POSSIBLE_REGRESSION',
    'NEW_FINDING',
    'UNCOMPARABLE'
);

CREATE TYPE review_decision AS ENUM (
    'accept',
    'reject',
    'rerun_requested'
);

-- =============================================================================
-- VERIFICATION JOBS TABLE
-- =============================================================================

CREATE TABLE verification_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    remediation_proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    remediation_application_id UUID NOT NULL REFERENCES remediation_applications(id) ON DELETE CASCADE,
    patch_hash TEXT NOT NULL,
    source_revision TEXT NOT NULL,
    target_revision TEXT NOT NULL,
    verification_engine_version TEXT NOT NULL DEFAULT 'verification-v1',
    policy_version TEXT NOT NULL DEFAULT 'verification-policy-v1',
    status verification_status NOT NULL DEFAULT 'QUEUED',
    overall_outcome verification_outcome,
    original_vulnerability_outcome check_status,
    regression_analysis_outcome check_status,
    scanner_execution_outcome check_status,
    test_execution_outcome check_status,
    evidence_comparison_outcome check_status,
    requested_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    canceled_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    idempotency_key TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_jobs_ws_id ON verification_jobs(workspace_id);
CREATE INDEX idx_verification_jobs_asset_id ON verification_jobs(asset_id);
CREATE INDEX idx_verification_jobs_finding_id ON verification_jobs(finding_id);
CREATE INDEX idx_verification_jobs_proposal_id ON verification_jobs(remediation_proposal_id);
CREATE INDEX idx_verification_jobs_application_id ON verification_jobs(remediation_application_id);
CREATE INDEX idx_verification_jobs_status ON verification_jobs(status);
CREATE INDEX idx_verification_jobs_requested_by ON verification_jobs(requested_by);
CREATE INDEX idx_verification_jobs_idempotency_key ON verification_jobs(idempotency_key);

-- =============================================================================
-- VERIFICATION BASELINES TABLE
-- =============================================================================

CREATE TABLE verification_baselines (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_job_id UUID NOT NULL REFERENCES verification_jobs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    original_finding_snapshot JSONB NOT NULL,
    original_evidence JSONB NOT NULL DEFAULT '[]',
    scanner_version TEXT NOT NULL,
    scanner_config JSONB NOT NULL DEFAULT '{}',
    rule_ids TEXT[] NOT NULL DEFAULT '{}',
    finding_fingerprint TEXT NOT NULL,
    evidence_hashes JSONB NOT NULL DEFAULT '[]',
    repository_revision TEXT NOT NULL,
    scan_id UUID REFERENCES scans(id) ON DELETE SET NULL,
    pre_patch_scan_results JSONB,
    capture_method TEXT NOT NULL DEFAULT 'handoff',
    captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    captured_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT
);

CREATE INDEX idx_verification_baselines_job_id ON verification_baselines(verification_job_id);
CREATE INDEX idx_verification_baselines_finding_id ON verification_baselines(finding_id);
CREATE INDEX idx_verification_baselines_fingerprint ON verification_baselines(finding_fingerprint);

-- =============================================================================
-- VERIFICATION CHECKS TABLE
-- =============================================================================

CREATE TABLE verification_checks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_job_id UUID NOT NULL REFERENCES verification_jobs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    check_type check_type NOT NULL,
    check_name TEXT NOT NULL,
    check_version TEXT,
    status check_status NOT NULL DEFAULT 'PENDING',
    command TEXT,
    exit_code INTEGER,
    stdout TEXT,
    stderr TEXT,
    duration_ms INTEGER,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_checks_job_id ON verification_checks(verification_job_id);
CREATE INDEX idx_verification_checks_type ON verification_checks(check_type);
CREATE INDEX idx_verification_checks_status ON verification_checks(status);
CREATE INDEX idx_verification_checks_name ON verification_checks(check_name);

-- =============================================================================
-- EVIDENCE COMPARISONS TABLE
-- =============================================================================

CREATE TABLE evidence_comparisons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_job_id UUID NOT NULL REFERENCES verification_jobs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    baseline_finding_id UUID REFERENCES findings(id) ON DELETE SET NULL,
    post_patch_finding_id UUID REFERENCES findings(id) ON DELETE SET NULL,
    baseline_fingerprint TEXT NOT NULL,
    post_patch_fingerprint TEXT,
    scanner_rule_id TEXT NOT NULL,
    normalized_file_path TEXT NOT NULL,
    baseline_location JSONB,
    post_patch_location JSONB,
    baseline_evidence_hash TEXT NOT NULL,
    post_patch_evidence_hash TEXT,
    category comparison_category NOT NULL,
    match_confidence DOUBLE PRECISION,
    match_rationale TEXT,
    relationship_to_original TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_evidence_comparisons_job_id ON evidence_comparisons(verification_job_id);
CREATE INDEX idx_evidence_comparisons_category ON evidence_comparisons(category);
CREATE INDEX idx_evidence_comparisons_baseline_fp ON evidence_comparisons(baseline_fingerprint);
CREATE INDEX idx_evidence_comparisons_post_patch_fp ON evidence_comparisons(post_patch_fingerprint);

-- =============================================================================
-- VERIFICATION POLICIES TABLE
-- =============================================================================

CREATE TABLE verification_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    policy_config JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_policies_version ON verification_policies(version);
CREATE INDEX idx_verification_policies_active ON verification_policies(is_active);

-- =============================================================================
-- VERIFICATION REVIEWS TABLE
-- =============================================================================

CREATE TABLE verification_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    verification_job_id UUID NOT NULL REFERENCES verification_jobs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    reviewed_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    decision review_decision NOT NULL,
    justification TEXT NOT NULL,
    notes TEXT,
    policy_version TEXT NOT NULL,
    baseline_snapshot JSONB NOT NULL,
    comparison_snapshot JSONB NOT NULL,
    check_results_snapshot JSONB NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_verification_reviews_job_id ON verification_reviews(verification_job_id);
CREATE INDEX idx_verification_reviews_workspace_id ON verification_reviews(workspace_id);
CREATE INDEX idx_verification_reviews_reviewed_by ON verification_reviews(reviewed_by);
CREATE INDEX idx_verification_reviews_decision ON verification_reviews(decision);

-- =============================================================================
-- RLS POLICIES
-- =============================================================================

ALTER TABLE verification_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence_comparisons ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_reviews ENABLE ROW LEVEL SECURITY;

-- Verification Jobs RLS
CREATE POLICY verification_jobs_workspace_isolation ON verification_jobs
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Verification Baselines RLS
CREATE POLICY verification_baselines_workspace_isolation ON verification_baselines
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Verification Checks RLS
CREATE POLICY verification_checks_workspace_isolation ON verification_checks
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Evidence Comparisons RLS
CREATE POLICY evidence_comparisons_workspace_isolation ON evidence_comparisons
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Verification Policies RLS (global read, admin write)
CREATE POLICY verification_policies_read ON verification_policies
    FOR SELECT USING (true);

CREATE POLICY verification_policies_write ON verification_policies
    FOR ALL USING (
        auth.uid() IN (SELECT user_id FROM workspace_members WHERE role IN ('owner', 'admin'))
    );

-- Verification Reviews RLS
CREATE POLICY verification_reviews_workspace_isolation ON verification_reviews
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

CREATE TRIGGER update_verification_jobs_updated_at
    BEFORE UPDATE ON verification_jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_verification_policies_updated_at
    BEFORE UPDATE ON verification_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- DEFAULT POLICY
-- =============================================================================

INSERT INTO verification_policies (version, name, description, policy_config, is_active, created_by)
SELECT
    'verification-policy-v1',
    'Default Verification Policy v1',
    'Default deterministic verification policy',
    '{
        "version": "verification-policy-v1",
        "rules": {
            "baseline_validity": {
                "required": true,
                "description": "Baseline must be valid and complete"
            },
            "scanner_execution": {
                "required": true,
                "description": "Scanner must execute successfully",
                "allow_blocked": false
            },
            "original_vulnerability": {
                "required": true,
                "description": "Original vulnerability must not be detected",
                "required_outcome": "PASSED"
            },
            "evidence_comparison": {
                "required": true,
                "description": "Evidence comparison must pass",
                "required_outcome": "PASSED"
            },
            "regression_analysis": {
                "required": false,
                "description": "Regression tests must pass if configured",
                "required_outcome": "PASSED",
                "allow_skipped": true
            },
            "test_execution": {
                "required": false,
                "description": "Test execution must pass if configured",
                "required_outcome": "PASSED",
                "allow_skipped": true
            }
        },
        "outcome_mapping": {
            "all_passed": "VERIFIED_CANDIDATE",
            "any_failed": "FAILED",
            "any_blocked": "BLOCKED",
            "inconclusive": "INCONCLUSIVE"
        }
    }'::jsonb,
    true,
    (SELECT id FROM profiles WHERE role = 'admin' LIMIT 1)
WHERE NOT EXISTS (
    SELECT 1 FROM verification_policies WHERE version = 'verification-policy-v1'
);

-- =============================================================================
-- UPDATE REMINDER VERIFICATION HANDOFF STATUS ENUM
-- =============================================================================

-- Note: The remediation_verification_handoff table already exists from Stage 8
-- We just need to ensure the status enum is compatible
-- The existing VerificationHandoffStatus enum in models.py should match:
-- PENDING_VERIFICATION, VERIFICATION_REQUESTED, VERIFIED, VERIFICATION_FAILED, MANUAL_REVIEW_REQUIRED
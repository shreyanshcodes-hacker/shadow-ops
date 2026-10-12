-- Stage 8: AI Remediation, Human Approval & Safe Patch Management Migration
-- Adds remediation proposals, patch versions, approvals, validations, applications, rollbacks, and verification handoff

-- Enum types for remediation
CREATE TYPE remediation_status AS ENUM (
    'DRAFT',
    'GENERATING',
    'PROPOSED',
    'VALIDATING',
    'VALIDATION_FAILED',
    'AWAITING_APPROVAL',
    'APPROVED',
    'APPLYING',
    'APPLIED',
    'REJECTED',
    'EXPIRED',
    'ROLLED_BACK',
    'FAILED'
);

CREATE TYPE remediation_fix_type AS ENUM (
    'code_change',
    'config_change',
    'dependency_update',
    'infrastructure_change',
    'waf_rule',
    'network_policy',
    'secret_rotation'
);

CREATE TYPE validation_status AS ENUM (
    'PENDING',
    'RUNNING',
    'PASSED',
    'FAILED',
    'BLOCKED',
    'ERROR'
);

CREATE TYPE validation_check_type AS ENUM (
    'patch_integrity',
    'diff_parsing',
    'path_allowlist',
    'syntax_validation',
    'semgrep_rescan',
    'regression_check',
    'existing_tests'
);

CREATE TYPE application_status AS ENUM (
    'PENDING',
    'CHECKPOINT_CREATED',
    'PATCH_APPLIED',
    'VERIFIED',
    'FAILED',
    'ROLLED_BACK'
);

CREATE TYPE rollback_status AS ENUM (
    'PENDING',
    'IN_PROGRESS',
    'COMPLETED',
    'FAILED',
    'BLOCKED_DIVERGED'
);

-- Remediation Proposals table
CREATE TABLE IF NOT EXISTS remediation_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    source_scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    status remediation_status NOT NULL DEFAULT 'DRAFT',
    proposal_title TEXT NOT NULL,
    problem_summary TEXT NOT NULL,
    proposed_solution TEXT NOT NULL,
    rationale TEXT NOT NULL,
    affected_files JSONB NOT NULL DEFAULT '[]',  -- Array of {file_path, language, change_type}
    patch_reference UUID REFERENCES patch_versions(id) ON DELETE SET NULL,
    validation_results JSONB NOT NULL DEFAULT '{}',  -- Summary of validation runs
    fix_type remediation_fix_type NOT NULL DEFAULT 'code_change',
    expected_security_benefit TEXT,
    compatibility_risks TEXT,
    assumptions TEXT,
    limitations TEXT,
    suggested_tests JSONB NOT NULL DEFAULT '[]',
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    approved_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    approved_at TIMESTAMPTZ,
    applied_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    applied_at TIMESTAMPTZ,
    failure_reason TEXT,
    version INT NOT NULL DEFAULT 1,
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_remediation_proposals_ws_id ON remediation_proposals(workspace_id);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_asset_id ON remediation_proposals(asset_id);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_finding_id ON remediation_proposals(finding_id);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_scan_id ON remediation_proposals(source_scan_id);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_status ON remediation_proposals(status);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_created_by ON remediation_proposals(created_by);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_approved_by ON remediation_proposals(approved_by);
CREATE INDEX IF NOT EXISTS idx_remediation_proposals_expires_at ON remediation_proposals(expires_at);

-- Patch Versions table (immutable patch history)
CREATE TABLE IF NOT EXISTS patch_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    version INT NOT NULL,
    unified_diff TEXT NOT NULL,  -- Complete unified diff for all affected files
    file_changes JSONB NOT NULL DEFAULT '[]',  -- Array of {file_path, old_hash, new_hash, additions, deletions}
    patch_hash TEXT NOT NULL,  -- SHA256 of unified_diff for integrity
    base_revision TEXT,  -- Git commit SHA or revision identifier
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT FALSE,
    superseded_by UUID REFERENCES patch_versions(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_patch_version_proposal_version ON patch_versions(proposal_id, version);
CREATE INDEX IF NOT EXISTS idx_patch_versions_proposal_id ON patch_versions(proposal_id);
CREATE INDEX IF NOT EXISTS idx_patch_versions_workspace_id ON patch_versions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_patch_versions_patch_hash ON patch_versions(patch_hash);

-- Validation Runs table
CREATE TABLE IF NOT EXISTS validation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    patch_version_id UUID NOT NULL REFERENCES patch_versions(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    status validation_status NOT NULL DEFAULT 'PENDING',
    check_type validation_check_type NOT NULL,
    command TEXT,  -- Command that was run (sanitized)
    exit_code INT,
    stdout TEXT,  -- Truncated safe output
    stderr TEXT,  -- Truncated safe output
    duration_ms INT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',  -- Check-specific results
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_validation_runs_proposal_id ON validation_runs(proposal_id);
CREATE INDEX IF NOT EXISTS idx_validation_runs_patch_version_id ON validation_runs(patch_version_id);
CREATE INDEX IF NOT EXISTS idx_validation_runs_workspace_id ON validation_runs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_validation_runs_status ON validation_runs(status);
CREATE INDEX IF NOT EXISTS idx_validation_runs_check_type ON validation_runs(check_type);

-- Approvals table (immutable approval history)
CREATE TABLE IF NOT EXISTS remediation_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    patch_version_id UUID NOT NULL REFERENCES patch_versions(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    approved_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    justification TEXT,  -- Required for rejection
    conditions JSONB NOT NULL DEFAULT '[]',  -- Array of conditions
    patch_hash TEXT NOT NULL,  -- Hash of patch at time of approval
    proposal_version INT NOT NULL,  -- Proposal version at time of approval
    validation_snapshot JSONB NOT NULL DEFAULT '{}',  -- Validation results at approval time
    approved_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ  -- Approval expiration
);

CREATE INDEX IF NOT EXISTS idx_remediation_approvals_proposal_id ON remediation_approvals(proposal_id);
CREATE INDEX IF NOT EXISTS idx_remediation_approvals_patch_version_id ON remediation_approvals(patch_version_id);
CREATE INDEX IF NOT EXISTS idx_remediation_approvals_workspace_id ON remediation_approvals(workspace_id);
CREATE INDEX IF NOT EXISTS idx_remediation_approvals_approved_by ON remediation_approvals(approved_by);
CREATE INDEX IF NOT EXISTS idx_remediation_approvals_decision ON remediation_approvals(decision);

-- Applications table (immutable application history)
CREATE TABLE IF NOT EXISTS remediation_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    patch_version_id UUID NOT NULL REFERENCES patch_versions(id) ON DELETE CASCADE,
    approval_id UUID NOT NULL REFERENCES remediation_approvals(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    status application_status NOT NULL DEFAULT 'PENDING',
    target_revision TEXT NOT NULL,  -- Git revision at application time
    checkpoint_ref TEXT,  -- Reference to recovery checkpoint (git stash, branch, tag)
    applied_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    applied_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    completed_at TIMESTAMPTZ,
    result_diff TEXT,  -- Actual diff after application
    changed_files JSONB NOT NULL DEFAULT '[]',  -- Array of actually changed files
    validation_results JSONB NOT NULL DEFAULT '{}',  -- Post-application validation
    failure_reason TEXT,
    idempotency_key TEXT UNIQUE NOT NULL  -- For idempotent application requests
);

CREATE INDEX IF NOT EXISTS idx_remediation_applications_proposal_id ON remediation_applications(proposal_id);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_patch_version_id ON remediation_applications(patch_version_id);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_approval_id ON remediation_applications(approval_id);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_workspace_id ON remediation_applications(workspace_id);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_asset_id ON remediation_applications(asset_id);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_applied_by ON remediation_applications(applied_by);
CREATE INDEX IF NOT EXISTS idx_remediation_applications_idempotency_key ON remediation_applications(idempotency_key);

-- Rollbacks table
CREATE TABLE IF NOT EXISTS remediation_rollbacks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES remediation_applications(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    status rollback_status NOT NULL DEFAULT 'PENDING',
    requested_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    checkpoint_ref TEXT NOT NULL,  -- Reference to checkpoint used for rollback
    verification_diff TEXT,  -- Diff showing what was restored
    started_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    completed_at TIMESTAMPTZ,
    failure_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_remediation_rollbacks_proposal_id ON remediation_rollbacks(proposal_id);
CREATE INDEX IF NOT EXISTS idx_remediation_rollbacks_application_id ON remediation_rollbacks(application_id);
CREATE INDEX IF NOT EXISTS idx_remediation_rollbacks_workspace_id ON remediation_rollbacks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_remediation_rollbacks_requested_by ON remediation_rollbacks(requested_by);

-- Verification Handoff table (for future verification stage)
CREATE TABLE IF NOT EXISTS remediation_verification_handoff (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    application_id UUID NOT NULL REFERENCES remediation_applications(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    patch_hash TEXT NOT NULL,
    repository_revision TEXT NOT NULL,
    changed_files JSONB NOT NULL DEFAULT '[]',
    validation_results JSONB NOT NULL DEFAULT '{}',
    original_finding_snapshot JSONB NOT NULL DEFAULT '{}',  -- Finding state at application
    applied_at TIMESTAMPTZ NOT NULL,
    applied_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    verification_requested BOOLEAN NOT NULL DEFAULT FALSE,
    verification_requested_at TIMESTAMPTZ,
    verification_completed_at TIMESTAMPTZ,
    verification_result JSONB,
    status TEXT NOT NULL DEFAULT 'PENDING_VERIFICATION' CHECK (status IN ('PENDING_VERIFICATION', 'VERIFICATION_REQUESTED', 'VERIFIED', 'VERIFICATION_FAILED', 'MANUAL_REVIEW_REQUIRED'))
);

CREATE INDEX IF NOT EXISTS idx_verification_handoff_proposal_id ON remediation_verification_handoff(proposal_id);
CREATE INDEX IF NOT EXISTS idx_verification_handoff_application_id ON remediation_verification_handoff(application_id);
CREATE INDEX IF NOT EXISTS idx_verification_handoff_workspace_id ON remediation_verification_handoff(workspace_id);
CREATE INDEX IF NOT EXISTS idx_verification_handoff_finding_id ON remediation_verification_handoff(finding_id);
CREATE INDEX IF NOT EXISTS idx_verification_handoff_status ON remediation_verification_handoff(status);

-- RLS Policies
ALTER TABLE remediation_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE patch_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE validation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_rollbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_verification_handoff ENABLE ROW LEVEL SECURITY;

-- remediation_proposals policies
CREATE POLICY "remediation_proposal_select" ON remediation_proposals
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_proposal_insert" ON remediation_proposals
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_proposals.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

CREATE POLICY "remediation_proposal_update" ON remediation_proposals
    FOR UPDATE USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_proposals.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- patch_versions policies
CREATE POLICY "patch_version_select" ON patch_versions
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "patch_version_insert" ON patch_versions
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = patch_versions.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- validation_runs policies
CREATE POLICY "validation_run_select" ON validation_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "validation_run_insert" ON validation_runs
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = validation_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- remediation_approvals policies
CREATE POLICY "remediation_approval_select" ON remediation_approvals
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_approval_insert" ON remediation_approvals
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        user_id = auth.uid() AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_approvals.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- remediation_applications policies
CREATE POLICY "remediation_application_select" ON remediation_applications
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_application_insert" ON remediation_applications
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_applications.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- remediation_rollbacks policies
CREATE POLICY "remediation_rollback_select" ON remediation_rollbacks
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_rollback_insert" ON remediation_rollbacks
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_rollbacks.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- remediation_verification_handoff policies
CREATE POLICY "verification_handoff_select" ON remediation_verification_handoff
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "verification_handoff_insert" ON remediation_verification_handoff
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_verification_handoff.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Triggers for updated_at
CREATE TRIGGER update_remediation_proposals_updated_at
    BEFORE UPDATE ON remediation_proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE remediation_proposals IS 'AI-generated remediation proposals with human approval workflow. Workspace-isolated via RLS.';
COMMENT ON TABLE patch_versions IS 'Immutable patch versions with hash integrity. Workspace-isolated via RLS.';
COMMENT ON TABLE validation_runs IS 'Bounded validation pipeline results. Workspace-isolated via RLS.';
COMMENT ON TABLE remediation_approvals IS 'Human approval records bound to exact patch hash. Workspace-isolated via RLS. Only admins/owners can approve.';
COMMENT ON TABLE remediation_applications IS 'Controlled patch application history with checkpoints. Workspace-isolated via RLS. Only admins/owners can apply.';
COMMENT ON TABLE remediation_rollbacks IS 'Rollback records with checkpoint references. Workspace-isolated via RLS.';
COMMENT ON TABLE remediation_verification_handoff IS 'Handoff to future verification stage. Workspace-isolated via RLS.';

COMMENT ON COLUMN remediation_proposals.patch_reference IS 'Reference to current patch version';
COMMENT ON COLUMN remediation_proposals.version IS 'Optimistic locking version for proposal updates';
COMMENT ON COLUMN remediation_proposals.expires_at IS 'Proposal expiration (e.g., 30 days)';
COMMENT ON COLUMN patch_versions.patch_hash IS 'SHA256 of unified_diff for integrity verification';
COMMENT ON COLUMN patch_versions.base_revision IS 'Git commit SHA at patch creation time';
COMMENT ON COLUMN remediation_approvals.patch_hash IS 'Must match patch_versions.patch_hash at approval time';
COMMENT ON COLUMN remediation_approvals.validation_snapshot IS 'Validation results snapshot at approval time';
COMMENT ON COLUMN remediation_applications.idempotency_key IS 'Client-generated key for idempotent apply requests';
COMMENT ON COLUMN remediation_applications.checkpoint_ref IS 'Git reference for rollback (stash, branch, tag)';
COMMENT ON COLUMN remediation_verification_handoff.status IS 'PENDING_VERIFICATION -> VERIFICATION_REQUESTED -> VERIFIED/FAILED';
-- Stage 7: AI Security Team & Multi-Agent Orchestration Migration
-- Adds security team runs, agent runs, and team assessments

-- Enum types for security team
CREATE TYPE security_team_run_status AS ENUM ('queued', 'running', 'partial', 'succeeded', 'failed', 'canceled');
CREATE TYPE agent_run_status AS ENUM ('queued', 'running', 'succeeded', 'failed', 'blocked', 'canceled');
CREATE TYPE agent_name AS ENUM ('recon', 'vulnerability_analyst', 'attack_path_analyst', 'risk_analyst', 'security_reviewer');

-- Security Team Runs table
CREATE TABLE IF NOT EXISTS security_team_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    status security_team_run_status NOT NULL DEFAULT 'queued',
    requested_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    orchestration_version TEXT NOT NULL DEFAULT 'security-team-v1',
    team_summary JSONB DEFAULT '{}',
    confidence NUMERIC(3, 2) CHECK (confidence >= 0.0 AND confidence <= 1.0),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_team_runs_ws_id ON security_team_runs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_security_team_runs_asset_id ON security_team_runs(asset_id);
CREATE INDEX IF NOT EXISTS idx_security_team_runs_scan_id ON security_team_runs(scan_id);
CREATE INDEX IF NOT EXISTS idx_security_team_runs_status ON security_team_runs(status);
CREATE INDEX IF NOT EXISTS idx_security_team_runs_requested_by ON security_team_runs(requested_by);
CREATE INDEX IF NOT EXISTS idx_security_team_runs_created_at ON security_team_runs(created_at DESC);
-- Unique constraint for idempotency (active run per workspace+asset+scan+version)
CREATE UNIQUE INDEX IF NOT EXISTS uq_security_team_run_active 
    ON security_team_runs(workspace_id, asset_id, scan_id, orchestration_version)
    WHERE status IN ('queued', 'running');

-- Agent Runs table
CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_run_id UUID NOT NULL REFERENCES security_team_runs(id) ON DELETE CASCADE,
    agent_name agent_name NOT NULL,
    status agent_run_status NOT NULL DEFAULT 'queued',
    input_reference JSONB DEFAULT '{}',  -- Reference to context (finding IDs, evidence IDs, etc.)
    output JSONB DEFAULT '{}',           -- Structured agent output
    confidence NUMERIC(3, 2) CHECK (confidence >= 0.0 AND confidence <= 1.0),
    provider TEXT,
    model TEXT,
    prompt_version TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    attempt INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_team_run_id ON agent_runs(team_run_id);
CREATE INDEX IF NOT EXISTS idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX IF NOT EXISTS idx_agent_runs_status ON agent_runs(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_run_team_agent ON agent_runs(team_run_id, agent_name);

-- Team Assessments table (final security reviewer output)
CREATE TABLE IF NOT EXISTS team_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_run_id UUID NOT NULL UNIQUE REFERENCES security_team_runs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    executive_summary TEXT NOT NULL,
    key_findings JSONB NOT NULL DEFAULT '[]',
    key_attack_paths JSONB NOT NULL DEFAULT '[]',
    risk_interpretation TEXT NOT NULL,
    uncertainties JSONB NOT NULL DEFAULT '[]',
    conflicting_assessments JSONB NOT NULL DEFAULT '[]',
    recommended_human_actions JSONB NOT NULL DEFAULT '[]',
    overall_confidence NUMERIC(3, 2) NOT NULL CHECK (overall_confidence >= 0.0 AND overall_confidence <= 1.0),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_team_assessments_ws_id ON team_assessments(workspace_id);

-- Team Reviews table (human review tracking)
CREATE TABLE IF NOT EXISTS team_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    team_run_id UUID NOT NULL UNIQUE REFERENCES security_team_runs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    reviewed_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    reviewed_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_team_reviews_ws_id ON team_reviews(workspace_id);
CREATE INDEX IF NOT EXISTS idx_team_reviews_reviewed_by ON team_reviews(reviewed_by);

-- RLS Policies
ALTER TABLE security_team_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_reviews ENABLE ROW LEVEL SECURITY;

-- security_team_runs policies
CREATE POLICY "security_team_run_select" ON security_team_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "security_team_run_insert" ON security_team_runs
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = security_team_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

CREATE POLICY "security_team_run_update" ON security_team_runs
    FOR UPDATE USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = security_team_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- agent_runs policies
CREATE POLICY "agent_run_select" ON agent_runs
    FOR SELECT USING (
        team_run_id IN (
            SELECT id FROM security_team_runs WHERE workspace_id = ANY(current_user_workspace_ids())
        )
    );

CREATE POLICY "agent_run_insert" ON agent_runs
    FOR INSERT WITH CHECK (
        team_run_id IN (
            SELECT id FROM security_team_runs 
            WHERE workspace_id = ANY(current_user_workspace_ids())
            AND EXISTS (
                SELECT 1 FROM workspace_members
                WHERE workspace_id = security_team_runs.workspace_id
                AND user_id = auth.uid()
                AND role IN ('owner', 'admin', 'member')
                AND joined_at IS NOT NULL
            )
        )
    );

CREATE POLICY "agent_run_update" ON agent_runs
    FOR UPDATE USING (
        team_run_id IN (
            SELECT id FROM security_team_runs 
            WHERE workspace_id = ANY(current_user_workspace_ids())
            AND EXISTS (
                SELECT 1 FROM workspace_members
                WHERE workspace_id = security_team_runs.workspace_id
                AND user_id = auth.uid()
                AND role IN ('owner', 'admin', 'member')
                AND joined_at IS NOT NULL
            )
        )
    );

-- team_assessments policies
CREATE POLICY "team_assessment_select" ON team_assessments
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "team_assessment_insert" ON team_assessments
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = team_assessments.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

CREATE POLICY "team_assessment_update" ON team_assessments
    FOR UPDATE USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = team_assessments.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- team_reviews policies
CREATE POLICY "team_review_select" ON team_reviews
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "team_review_insert" ON team_reviews
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        user_id = auth.uid() AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = team_reviews.workspace_id
            AND user_id = auth.uid()
            AND joined_at IS NOT NULL
        )
    );

-- Triggers for updated_at
CREATE TRIGGER update_security_team_runs_updated_at 
    BEFORE UPDATE ON security_team_runs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_agent_runs_updated_at 
    BEFORE UPDATE ON agent_runs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_team_assessments_updated_at 
    BEFORE UPDATE ON team_assessments 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments
COMMENT ON TABLE security_team_runs IS 'AI Security Team orchestration runs. Workspace-isolated via RLS.';
COMMENT ON TABLE agent_runs IS 'Individual agent executions within a team run. Workspace-isolated via RLS.';
COMMENT ON TABLE team_assessments IS 'Final security reviewer assessment. Workspace-isolated via RLS.';
COMMENT ON TABLE team_reviews IS 'Human review records. Workspace-isolated via RLS.';
COMMENT ON COLUMN security_team_runs.orchestration_version IS 'Version of the orchestration logic (e.g., security-team-v1)';
COMMENT ON COLUMN security_team_runs.team_summary IS 'Aggregated summary of all agent outputs';
COMMENT ON COLUMN agent_runs.input_reference IS 'Minimal context reference (finding IDs, evidence IDs, path IDs)';
COMMENT ON COLUMN agent_runs.output IS 'Structured agent output per agent contract';
COMMENT ON COLUMN agent_runs.prompt_version IS 'Version of the agent prompt (e.g., recon-v1)';
COMMENT ON COLUMN team_reviews.reviewed_by IS 'Human reviewer (AI agents cannot self-review)';

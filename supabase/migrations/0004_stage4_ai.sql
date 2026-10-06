-- Stage 4: AI Security Manager Migration
-- Adds AI runs and AI analysis tables for structured security analysis

-- Create enum types for AI operations
CREATE TYPE ai_provider_type AS ENUM ('gemini', 'grok');
CREATE TYPE ai_operation_type AS ENUM ('finding_analysis', 'scan_analysis');
CREATE TYPE ai_run_status AS ENUM ('queued', 'running', 'completed', 'failed');

-- AI Runs table - tracks AI analysis executions
CREATE TABLE IF NOT EXISTS ai_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    finding_id UUID REFERENCES findings(id) ON DELETE SET NULL,
    requested_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    provider ai_provider_type NOT NULL,
    model TEXT NOT NULL,
    operation ai_operation_type NOT NULL,
    status ai_run_status NOT NULL DEFAULT 'queued',
    prompt_version TEXT NOT NULL DEFAULT '1.0',
    input_hash TEXT NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    input_tokens INT,
    output_tokens INT,
    estimated_cost_usd NUMERIC(10, 6),
    error_code TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ai_runs_workspace_id ON ai_runs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_scan_id ON ai_runs(scan_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_finding_id ON ai_runs(finding_id);
CREATE INDEX IF NOT EXISTS idx_ai_runs_status ON ai_runs(status);
CREATE INDEX IF NOT EXISTS idx_ai_runs_requested_by ON ai_runs(requested_by);
CREATE INDEX IF NOT EXISTS idx_ai_runs_input_hash ON ai_runs(input_hash);
CREATE INDEX IF NOT EXISTS idx_ai_runs_created_at ON ai_runs(created_at);

-- AI Analysis table - stores structured AI analysis for findings
CREATE TABLE IF NOT EXISTS finding_ai_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    ai_run_id UUID NOT NULL REFERENCES ai_runs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    technical_explanation TEXT NOT NULL,
    impact TEXT NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    classification TEXT,
    uncertainty TEXT,
    supporting_evidence JSONB NOT NULL DEFAULT '[]',
    model TEXT NOT NULL,
    provider ai_provider_type NOT NULL,
    prompt_version TEXT NOT NULL DEFAULT '1.0',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_finding_ai_analysis_finding_id ON finding_ai_analysis(finding_id);
CREATE INDEX IF NOT EXISTS idx_finding_ai_analysis_ai_run_id ON finding_ai_analysis(ai_run_id);
CREATE INDEX IF NOT EXISTS idx_finding_ai_analysis_workspace_id ON finding_ai_analysis(workspace_id);

-- RLS Policies for ai_runs
ALTER TABLE ai_runs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "ai_run_select" ON ai_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "ai_run_insert" ON ai_runs
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = ai_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

CREATE POLICY "ai_run_update" ON ai_runs
    FOR UPDATE USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = ai_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- RLS Policies for finding_ai_analysis
ALTER TABLE finding_ai_analysis ENABLE ROW LEVEL SECURITY;

CREATE POLICY "finding_ai_analysis_select" ON finding_ai_analysis
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "finding_ai_analysis_insert" ON finding_ai_analysis
    FOR INSERT WITH CHECK (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = finding_ai_analysis.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

CREATE POLICY "finding_ai_analysis_update" ON finding_ai_analysis
    FOR UPDATE USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = finding_ai_analysis.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Trigger for updated_at
CREATE TRIGGER update_ai_runs_updated_at 
    BEFORE UPDATE ON ai_runs 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_finding_ai_analysis_updated_at 
    BEFORE UPDATE ON finding_ai_analysis 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Audit logging table additions for AI events
-- (Assuming audit_log table exists from earlier stages)
-- AI events: ai.analysis.requested, ai.analysis.started, ai.analysis.completed, ai.analysis.failed

COMMENT ON TABLE ai_runs IS 'AI analysis execution tracking. Workspace-isolated via RLS.';
COMMENT ON TABLE finding_ai_analysis IS 'Structured AI security analysis for findings. Workspace-isolated via RLS.';
COMMENT ON COLUMN ai_runs.input_hash IS 'Hash of normalized evidence input for deduplication';
COMMENT ON COLUMN finding_ai_analysis.confidence IS 'AI confidence score 0.0-1.0, separate from scanner severity';
COMMENT ON COLUMN finding_ai_analysis.supporting_evidence IS 'Array of {evidence_id, reason} references to actual evidence';
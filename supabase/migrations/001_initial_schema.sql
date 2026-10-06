-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. profiles table
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    firebase_uid TEXT UNIQUE NOT NULL,
    email TEXT NOT NULL,
    display_name TEXT,
    avatar_url TEXT,
    role TEXT DEFAULT 'user' NOT NULL CHECK (role IN ('user', 'admin')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    last_login_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX idx_profiles_firebase_uid ON profiles(firebase_uid);
CREATE INDEX idx_profiles_email ON profiles(email);

-- 2. workspaces table
CREATE TABLE workspaces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    owner_id UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    plan TEXT DEFAULT 'free' NOT NULL,
    settings JSONB DEFAULT '{}' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id);
CREATE INDEX idx_workspaces_slug ON workspaces(slug);

-- 3. workspace_members table
CREATE TABLE workspace_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member', 'viewer')),
    invited_by UUID REFERENCES profiles(id),
    invited_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    joined_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE UNIQUE INDEX uq_ws_members_ws_user ON workspace_members(workspace_id, user_id);
CREATE INDEX idx_ws_members_ws_id ON workspace_members(workspace_id);
CREATE INDEX idx_ws_members_user_id ON workspace_members(user_id);

-- 4. assets table
CREATE TABLE assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('repository', 'api', 'infrastructure', 'application', 'container')),
    subtype TEXT,
    connection_config JSONB NOT NULL DEFAULT '{}',
    credentials_ref TEXT,
    criticality TEXT DEFAULT 'medium' NOT NULL CHECK (criticality IN ('low', 'medium', 'high', 'critical')),
    status TEXT DEFAULT 'active' NOT NULL CHECK (status IN ('active', 'archived', 'error')),
    last_scanned_at TIMESTAMPTZ,
    scan_frequency INTERVAL DEFAULT '24 hours',
    tags TEXT[] DEFAULT '{}',
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_assets_ws_id ON assets(workspace_id);
CREATE INDEX idx_assets_type ON assets(type);
CREATE INDEX idx_assets_status ON assets(status);
CREATE INDEX idx_assets_last_scanned ON assets(last_scanned_at);

-- 5. asset_authorizations table
CREATE TABLE asset_authorizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    asset_id UUID NOT NULL UNIQUE REFERENCES assets(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    authorization_type TEXT NOT NULL CHECK (authorization_type IN ('ownership', 'written_permission', 'bug_bounty', 'internal')),
    evidence_files UUID[] DEFAULT '{}',
    evidence_urls TEXT[] DEFAULT '{}',
    authorized_by TEXT,
    authorized_at TIMESTAMPTZ NOT NULL,
    expires_at TIMESTAMPTZ,
    status TEXT DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'verified', 'rejected', 'expired')),
    verified_by UUID REFERENCES profiles(id),
    verified_at TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_asset_auth_asset_id ON asset_authorizations(asset_id);
CREATE INDEX idx_asset_auth_ws_id ON asset_authorizations(workspace_id);
CREATE INDEX idx_asset_auth_status ON asset_authorizations(status);

-- 6. scans table
CREATE TABLE scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    scan_type TEXT NOT NULL CHECK (scan_type IN ('full', 'recon', 'code', 'dependency', 'targeted')),
    status TEXT DEFAULT 'queued' NOT NULL CHECK (status IN ('queued', 'running', 'completed', 'failed', 'cancelled', 'partial')),
    triggered_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    triggered_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_ms BIGINT,
    phases_completed TEXT[] DEFAULT '{}',
    current_phase TEXT,
    progress_percent INT DEFAULT 0,
    error_message TEXT,
    scan_config JSONB DEFAULT '{}',
    summary JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_scans_ws_id ON scans(workspace_id);
CREATE INDEX idx_scans_asset_id ON scans(asset_id);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_scans_triggered_at ON scans(triggered_at);

-- 7. scan_events table (immutable, append-only)
CREATE TABLE scan_events (
    id BIGSERIAL PRIMARY KEY,
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    phase TEXT NOT NULL,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    data JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_scan_events_scan_id_created ON scan_events(scan_id, created_at DESC);
CREATE INDEX idx_scan_events_ws_id ON scan_events(workspace_id);

-- 8. agent_runs table
CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    agent_name TEXT NOT NULL,
    model_used TEXT,
    status TEXT DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed', 'timeout')),
    input_summary JSONB,
    output_summary JSONB,
    tokens_input INT,
    tokens_output INT,
    cost_usd DECIMAL(10,6),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_agent_runs_scan_id ON agent_runs(scan_id);
CREATE INDEX idx_agent_runs_agent_name ON agent_runs(agent_name);
CREATE INDEX idx_agent_runs_ws_id ON agent_runs(workspace_id);

-- 9. findings table
CREATE TABLE findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('semgrep', 'recon', 'dependency', 'ai_analysis', 'manual')),
    source_rule_id TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low', 'info')),
    confidence TEXT DEFAULT 'medium' NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    cwe_ids TEXT[] DEFAULT '{}',
    cve_ids TEXT[] DEFAULT '{}',
    owasp_categories TEXT[] DEFAULT '{}',
    location JSONB,
    code_snippet TEXT,
    remediation_guidance TEXT,
    status TEXT DEFAULT 'open' NOT NULL CHECK (status IN ('open', 'triaged', 'in_progress', 'fixed', 'false_positive', 'wont_fix', 'risk_accepted')),
    triaged_by UUID REFERENCES profiles(id),
    triaged_at TIMESTAMPTZ,
    risk_score DECIMAL(5,2),
    risk_factors JSONB DEFAULT '{}',
    first_seen_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    last_seen_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    fixed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_findings_ws_id ON findings(workspace_id);
CREATE INDEX idx_findings_scan_id ON findings(scan_id);
CREATE INDEX idx_findings_asset_id ON findings(asset_id);
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_findings_status ON findings(status);
CREATE INDEX idx_findings_risk_score ON findings(risk_score DESC);
CREATE INDEX idx_findings_source_rule ON findings(source, source_rule_id);

-- 10. finding_evidence table
CREATE TABLE finding_evidence (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL CHECK (evidence_type IN ('code_snippet', 'screenshot', 'log', 'request_response', 'config', 'dependency_tree', 'ai_reasoning')),
    title TEXT NOT NULL,
    description TEXT,
    content JSONB,
    file_path TEXT,
    line_start INT,
    line_end INT,
    storage_object_id UUID,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_finding_evidence_finding_id ON finding_evidence(finding_id);
CREATE INDEX idx_finding_evidence_type ON finding_evidence(evidence_type);

-- 11. risk_assessments table
CREATE TABLE risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    finding_id UUID NOT NULL UNIQUE REFERENCES findings(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    base_score DECIMAL(5,2) NOT NULL,
    exploitability DECIMAL(5,2),
    exposure DECIMAL(5,2),
    asset_criticality DECIMAL(5,2),
    confidence DECIMAL(5,2),
    attack_path_impact DECIMAL(5,2) DEFAULT 0,
    final_score DECIMAL(5,2) NOT NULL,
    factors JSONB NOT NULL,
    formula_version TEXT NOT NULL,
    calculated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    calculated_by TEXT NOT NULL
);

CREATE UNIQUE INDEX idx_risk_assessments_finding_id ON risk_assessments(finding_id);
CREATE INDEX idx_risk_assessments_ws_id ON risk_assessments(workspace_id);
CREATE INDEX idx_risk_assessments_final_score ON risk_assessments(final_score DESC);

-- 12. attack_paths table
CREATE TABLE attack_paths (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    scan_id UUID REFERENCES scans(id) ON DELETE SET NULL,
    name TEXT NOT NULL,
    description TEXT,
    entry_point TEXT,
    target_asset TEXT,
    risk_score DECIMAL(5,2),
    node_count INT DEFAULT 0,
    edge_count INT DEFAULT 0,
    is_critical BOOLEAN DEFAULT FALSE,
    status TEXT DEFAULT 'active' NOT NULL CHECK (status IN ('active', 'mitigated', 'broken')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_attack_paths_ws_id ON attack_paths(workspace_id);
CREATE INDEX idx_attack_paths_scan_id ON attack_paths(scan_id);
CREATE INDEX idx_attack_paths_risk_score ON attack_paths(risk_score DESC);

-- 13. attack_path_nodes table
CREATE TABLE attack_path_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attack_path_id UUID NOT NULL REFERENCES attack_paths(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    node_type TEXT NOT NULL CHECK (node_type IN ('asset', 'vulnerability', 'network_zone', 'trust_boundary', 'data_store', 'attacker')),
    label TEXT NOT NULL,
    description TEXT,
    asset_id UUID REFERENCES assets(id),
    finding_id UUID REFERENCES findings(id),
    risk_contribution DECIMAL(5,2) DEFAULT 0,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_ap_nodes_path_id ON attack_path_nodes(attack_path_id);
CREATE INDEX idx_ap_nodes_asset_id ON attack_path_nodes(asset_id);
CREATE INDEX idx_ap_nodes_finding_id ON attack_path_nodes(finding_id);

-- 14. attack_path_edges table
CREATE TABLE attack_path_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    attack_path_id UUID NOT NULL REFERENCES attack_paths(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_node_id UUID NOT NULL REFERENCES attack_path_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES attack_path_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL CHECK (edge_type IN ('exploits', 'accesses', 'trusts', 'contains', 'lateral_movement', 'privilege_escalation')),
    description TEXT,
    evidence_refs UUID[],
    likelihood DECIMAL(5,2),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_ap_edges_path_id ON attack_path_edges(attack_path_id);
CREATE INDEX idx_ap_edges_source ON attack_path_edges(source_node_id);
CREATE INDEX idx_ap_edges_target ON attack_path_edges(target_node_id);

-- 15. remediation_proposals table
CREATE TABLE remediation_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    proposed_by TEXT NOT NULL,
    model_used TEXT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    fix_type TEXT NOT NULL CHECK (fix_type IN ('code_change', 'config_change', 'dependency_update', 'infrastructure_change', 'waf_rule', 'network_policy')),
    code_changes JSONB,
    config_changes JSONB,
    commands TEXT[],
    prerequisites TEXT[],
    risk_level TEXT DEFAULT 'medium' NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    confidence TEXT DEFAULT 'medium' NOT NULL CHECK (confidence IN ('low', 'medium', 'high')),
    estimated_effort TEXT,
    status TEXT DEFAULT 'proposed' NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected', 'applied', 'superseded')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_remediation_proposals_ws_id ON remediation_proposals(workspace_id);
CREATE INDEX idx_remediation_proposals_finding_id ON remediation_proposals(finding_id);
CREATE INDEX idx_remediation_proposals_status ON remediation_proposals(status);

-- 16. remediation_approvals table
CREATE TABLE remediation_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id UUID NOT NULL REFERENCES remediation_proposals(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    approved_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    decision TEXT NOT NULL CHECK (decision IN ('approved', 'rejected')),
    justification TEXT,
    conditions TEXT[],
    approved_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    expires_at TIMESTAMPTZ
);

CREATE INDEX idx_remediation_approvals_proposal_id ON remediation_approvals(proposal_id);
CREATE INDEX idx_remediation_approvals_ws_id ON remediation_approvals(workspace_id);

-- 17. verification_runs table
CREATE TABLE verification_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    finding_id UUID NOT NULL REFERENCES findings(id) ON DELETE CASCADE,
    proposal_id UUID REFERENCES remediation_proposals(id) ON DELETE SET NULL,
    scan_id UUID REFERENCES scans(id) ON DELETE SET NULL,
    verification_type TEXT NOT NULL CHECK (verification_type IN ('reproduction_test', 'semgrep_rescan', 'dependency_check', 'config_audit', 'regression_test')),
    status TEXT DEFAULT 'pending' NOT NULL CHECK (status IN ('pending', 'running', 'passed', 'failed', 'inconclusive')),
    result JSONB,
    evidence_refs UUID[],
    passed BOOLEAN,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_verification_runs_ws_id ON verification_runs(workspace_id);
CREATE INDEX idx_verification_runs_finding_id ON verification_runs(finding_id);
CREATE INDEX idx_verification_runs_proposal_id ON verification_runs(proposal_id);

-- 18. reports table
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    scan_id UUID REFERENCES scans(id) ON DELETE SET NULL,
    report_type TEXT NOT NULL CHECK (report_type IN ('executive', 'technical', 'scan', 'compliance', 'custom')),
    title TEXT NOT NULL,
    description TEXT,
    format TEXT NOT NULL CHECK (format IN ('pdf', 'html', 'json', 'markdown')),
    status TEXT DEFAULT 'generating' NOT NULL CHECK (status IN ('generating', 'ready', 'failed')),
    storage_object_id UUID,
    generated_by TEXT NOT NULL,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_reports_ws_id ON reports(workspace_id);
CREATE INDEX idx_reports_scan_id ON reports(scan_id);
CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_created_at ON reports(created_at);

-- 19. chat_conversations table
CREATE TABLE chat_conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    title TEXT,
    context_type TEXT CHECK (context_type IN ('general', 'finding', 'asset', 'scan', 'attack_path', 'report')),
    context_id UUID,
    message_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_chat_conv_ws_id ON chat_conversations(workspace_id);
CREATE INDEX idx_chat_conv_user_id ON chat_conversations(user_id);
CREATE INDEX idx_chat_conv_context ON chat_conversations(context_type, context_id);

-- 20. chat_messages table
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES chat_conversations(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    citations UUID[],
    model_used TEXT,
    tokens_input INT,
    tokens_output INT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_chat_messages_conv_id_created ON chat_messages(conversation_id, created_at);
CREATE INDEX idx_chat_messages_ws_id ON chat_messages(workspace_id);

-- 21. audit_logs table (immutable, append-only)
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id UUID,
    old_state JSONB,
    new_state JSONB,
    ip_address INET,
    user_agent TEXT,
    request_id UUID DEFAULT gen_random_uuid() NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_audit_logs_ws_id_created ON audit_logs(workspace_id, created_at DESC);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);

-- 22. notifications table
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    reference_type TEXT,
    reference_id UUID,
    channels TEXT[] DEFAULT '{in_app}',
    read_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX idx_notifications_user_id_read ON notifications(user_id, read_at);
CREATE INDEX idx_notifications_ws_id_created ON notifications(workspace_id, created_at);

-- 23. roles reference table
CREATE TABLE roles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    permissions JSONB NOT NULL,
    description TEXT
);

INSERT INTO roles (id, name, permissions, description) VALUES
('owner', 'Owner', '{"all": true}', 'Full workspace access including deletion'),
('admin', 'Admin', '{"manage_members": true, "manage_assets": true, "manage_scans": true, "manage_findings": true, "manage_remediation": true, "manage_reports": true, "view_audit_logs": true}', 'Workspace administration'),
('member', 'Member', '{"create_assets": true, "manage_own_assets": true, "run_scans": true, "view_findings": true, "propose_remediation": true, "view_reports": true}', 'Active team member'),
('viewer', 'Viewer', '{"view_findings": true, "view_reports": true}', 'Read-only access');

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply updated_at triggers
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_workspaces_updated_at BEFORE UPDATE ON workspaces FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON assets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_asset_authorizations_updated_at BEFORE UPDATE ON asset_authorizations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_scans_updated_at BEFORE UPDATE ON scans FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_findings_updated_at BEFORE UPDATE ON findings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_finding_evidence_updated_at BEFORE UPDATE ON finding_evidence FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_risk_assessments_updated_at BEFORE UPDATE ON risk_assessments FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_attack_paths_updated_at BEFORE UPDATE ON attack_paths FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_remediation_proposals_updated_at BEFORE UPDATE ON remediation_proposals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_remediation_approvals_updated_at BEFORE UPDATE ON remediation_approvals FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_verification_runs_updated_at BEFORE UPDATE ON verification_runs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_reports_updated_at BEFORE UPDATE ON reports FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_chat_conversations_updated_at BEFORE UPDATE ON chat_conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- RLS Policies
-- Enable RLS on all workspace-scoped tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE asset_authorizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE scans ENABLE ROW LEVEL SECURITY;
ALTER TABLE scan_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE findings ENABLE ROW LEVEL SECURITY;
ALTER TABLE finding_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE risk_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE attack_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE attack_path_nodes ENABLE ROW LEVEL SECURITY;
ALTER TABLE attack_path_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE remediation_approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE verification_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;

-- Helper function for RLS policies
CREATE OR REPLACE FUNCTION current_user_workspace_ids()
RETURNS UUID[] LANGUAGE sql STABLE AS $$
    SELECT array_agg(workspace_id) FROM workspace_members
    WHERE user_id = auth.uid() AND joined_at IS NOT NULL;
$$;

-- Profiles: users see own profile, admins see all
CREATE POLICY "profiles_self_select" ON profiles
    FOR SELECT USING (firebase_uid = (SELECT firebase_uid FROM profiles WHERE id = auth.uid()) OR auth.jwt() ->> 'role' = 'admin');

CREATE POLICY "profiles_self_update" ON profiles
    FOR UPDATE USING (id = auth.uid());

-- Workspaces: members can view, admins/owners can manage
CREATE POLICY "workspace_member_select" ON workspaces
    FOR SELECT USING (id = ANY(current_user_workspace_ids()));

CREATE POLICY "workspace_admin_write" ON workspaces
    FOR ALL USING (
        id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = workspaces.id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Workspace members
CREATE POLICY "ws_member_select" ON workspace_members
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "ws_member_admin_write" ON workspace_members
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = workspace_members.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Assets
CREATE POLICY "asset_select" ON assets
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "asset_admin_write" ON assets
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = assets.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Asset authorizations
CREATE POLICY "asset_auth_select" ON asset_authorizations
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "asset_auth_admin_write" ON asset_authorizations
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = asset_authorizations.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Scans
CREATE POLICY "scan_select" ON scans
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "scan_admin_write" ON scans
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = scans.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Scan events (read-only for members)
CREATE POLICY "scan_event_select" ON scan_events
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Agent runs (read-only for members)
CREATE POLICY "agent_run_select" ON agent_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Findings
CREATE POLICY "finding_select" ON findings
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "finding_admin_write" ON findings
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = findings.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Finding evidence
CREATE POLICY "finding_evidence_select" ON finding_evidence
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Risk assessments
CREATE POLICY "risk_assessment_select" ON risk_assessments
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Attack paths
CREATE POLICY "attack_path_select" ON attack_paths
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "attack_path_admin_write" ON attack_paths
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = attack_paths.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Attack path nodes/edges
CREATE POLICY "ap_node_select" ON attack_path_nodes
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "ap_edge_select" ON attack_path_edges
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Remediation proposals
CREATE POLICY "remediation_proposal_select" ON remediation_proposals
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_proposal_admin_write" ON remediation_proposals
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_proposals.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Remediation approvals
CREATE POLICY "remediation_approval_select" ON remediation_approvals
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "remediation_approval_admin_write" ON remediation_approvals
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = remediation_approvals.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Verification runs
CREATE POLICY "verification_run_select" ON verification_runs
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "verification_run_admin_write" ON verification_runs
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = verification_runs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Reports
CREATE POLICY "report_select" ON reports
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "report_admin_write" ON reports
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = reports.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Chat conversations
CREATE POLICY "chat_conv_select" ON chat_conversations
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()) AND user_id = auth.uid());

CREATE POLICY "chat_conv_user_write" ON chat_conversations
    FOR ALL USING (user_id = auth.uid());

-- Chat messages
CREATE POLICY "chat_msg_select" ON chat_messages
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()) AND conversation_id IN (
        SELECT id FROM chat_conversations WHERE user_id = auth.uid()
    ));

CREATE POLICY "chat_msg_user_write" ON chat_messages
    FOR ALL USING (conversation_id IN (
        SELECT id FROM chat_conversations WHERE user_id = auth.uid()
    ));

-- Audit logs (only admins/owners)
CREATE POLICY "audit_log_admin_select" ON audit_logs
    FOR SELECT USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = audit_logs.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin')
            AND joined_at IS NOT NULL
        )
    );

-- Notifications (users see only their own)
CREATE POLICY "notification_select" ON notifications
    FOR SELECT USING (user_id = auth.uid());

CREATE POLICY "notification_user_write" ON notifications
    FOR ALL USING (user_id = auth.uid());
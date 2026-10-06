-- Stage 3: Scanning Foundation Migration
-- Adds enhanced scan schema, scan profiles, and security controls

-- Add new columns to scans table
ALTER TABLE scans
ADD COLUMN IF NOT EXISTS scan_profile TEXT DEFAULT 'CODE_SECURITY' 
    CHECK (scan_profile IN ('QUICK', 'STANDARD', 'CODE_SECURITY')),
ADD COLUMN IF NOT EXISTS target_type TEXT,
ADD COLUMN IF NOT EXISTS target_reference TEXT,
ADD COLUMN IF NOT EXISTS failed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS error_code TEXT,
ADD COLUMN IF NOT EXISTS authorization_confirmed_at TIMESTAMPTZ;

-- Add new columns to scan_events for enhanced event types
-- (existing columns are sufficient, but we add indexes for new query patterns)

-- Create index for scan authorization tracking
CREATE INDEX IF NOT EXISTS idx_scans_authorization_confirmed ON scans(authorization_confirmed_at);
CREATE INDEX IF NOT EXISTS idx_scans_scan_profile ON scans(scan_profile);
CREATE INDEX IF NOT EXISTS idx_scans_failed_at ON scans(failed_at);
CREATE INDEX IF NOT EXISTS idx_scans_cancelled_at ON scans(cancelled_at);

-- Add scan_events indexes for new event type queries
CREATE INDEX IF NOT EXISTS idx_scan_events_event_type ON scan_events(event_type);
CREATE INDEX IF NOT EXISTS idx_scan_events_phase ON scan_events(phase);

-- Create a controlled scan targets table for Stage 3 demo fixtures
CREATE TABLE IF NOT EXISTS scan_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    target_path TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT 'repository',
    is_demo BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scan_targets_ws_id ON scan_targets(workspace_id);
CREATE INDEX IF NOT EXISTS idx_scan_targets_is_demo ON scan_targets(is_demo);

-- RLS for scan_targets
ALTER TABLE scan_targets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "scan_target_select" ON scan_targets
    FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

CREATE POLICY "scan_target_admin_write" ON scan_targets
    FOR ALL USING (
        workspace_id = ANY(current_user_workspace_ids()) AND
        EXISTS (
            SELECT 1 FROM workspace_members
            WHERE workspace_id = scan_targets.workspace_id
            AND user_id = auth.uid()
            AND role IN ('owner', 'admin', 'member')
            AND joined_at IS NOT NULL
        )
    );

-- Add trigger for scan_targets updated_at
CREATE TRIGGER update_scan_targets_updated_at 
    BEFORE UPDATE ON scan_targets 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Insert a controlled demo scan target fixture
-- This is a local path that will be created in the scanner working directory
-- DO NOT USE REAL REPOSITORIES OR EXTERNAL TARGETS
INSERT INTO scan_targets (workspace_id, name, description, target_path, target_type, is_demo, is_active, created_by)
SELECT 
    w.id,
    'ShadowOps Demo Target',
    'Controlled demo fixture with intentional vulnerabilities for testing',
    '/scan-workspace/demo-target',
    'repository',
    TRUE,
    TRUE,
    w.owner_id
FROM workspaces w
WHERE w.slug = 'demo-workspace'
ON CONFLICT DO NOTHING;

-- Add comment to document the security boundary
COMMENT ON TABLE scans IS 'Scan execution records. NO AUTHORIZATION -> NO SCAN enforced at application layer.';
COMMENT ON TABLE scan_events IS 'Immutable scan lifecycle events. Workspace-isolated via RLS.';
COMMENT ON TABLE scan_targets IS 'Controlled scan targets. Only demo fixtures allowed in Stage 3. Production must use isolated workers.';
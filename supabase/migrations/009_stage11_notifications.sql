-- Stage 11: Notifications, Event Processing & Controlled Workflow Automation
-- Migration: 009_stage11_notifications.sql
-- Created: 2026-10-14

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE notification_channel AS ENUM (
    'in_app',
    'email'
);

CREATE TYPE notification_status AS ENUM (
    'pending',
    'sent',
    'delivered',
    'failed',
    'bounced'
);

CREATE TYPE delivery_status AS ENUM (
    'pending',
    'sent',
    'delivered',
    'failed',
    'bounced',
    'retrying'
);

CREATE TYPE workflow_status AS ENUM (
    'pending',
    'running',
    'completed',
    'failed',
    'cancelled'
);

CREATE TYPE event_processing_status AS ENUM (
    'pending',
    'processing',
    'completed',
    'failed',
    'dead_letter'
);

CREATE TYPE rule_recipient_policy AS ENUM (
    'asset_owners',
    'asset_members',
    'workspace_admins',
    'workspace_owners',
    'specific_users',
    'finding_assignees',
    'remediation_approvers'
);

-- =============================================================================
-- EVENT OUTBOX TABLE (Transactional Outbox Pattern)
-- =============================================================================

CREATE TABLE event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '1.0',
    event_id UUID NOT NULL DEFAULT gen_random_uuid(),
    correlation_id UUID,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    resource_type TEXT,
    resource_id UUID,
    payload JSONB NOT NULL DEFAULT '{}',
    status event_processing_status NOT NULL DEFAULT 'pending',
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    next_retry_at TIMESTAMPTZ,
    last_error TEXT,
    last_error_category TEXT,
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_event_outbox_workspace_status ON event_outbox(workspace_id, status);
CREATE INDEX idx_event_outbox_status_next_retry ON event_outbox(status, next_retry_at) WHERE status IN ('pending', 'retrying');
CREATE INDEX idx_event_outbox_correlation_id ON event_outbox(correlation_id);
CREATE INDEX idx_event_outbox_event_type ON event_outbox(event_type);
CREATE INDEX idx_event_outbox_created_at ON event_outbox(created_at);

-- =============================================================================
-- NOTIFICATIONS TABLE (Extended from existing schema)
-- =============================================================================

-- Note: notifications table already exists in 001_initial_schema.sql
-- We add columns if they don't exist
DO $$
BEGIN
    -- Add new columns to existing notifications table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'event_outbox_id') THEN
        ALTER TABLE notifications ADD COLUMN event_outbox_id UUID REFERENCES event_outbox(id) ON DELETE SET NULL;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'rule_id') THEN
        ALTER TABLE notifications ADD COLUMN rule_id UUID;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'priority') THEN
        ALTER TABLE notifications ADD COLUMN priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical'));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'action_url') THEN
        ALTER TABLE notifications ADD COLUMN action_url TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'action_label') THEN
        ALTER TABLE notifications ADD COLUMN action_label TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'deduplication_key') THEN
        ALTER TABLE notifications ADD COLUMN deduplication_key TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'notifications' AND column_name = 'expires_at') THEN
        ALTER TABLE notifications ADD COLUMN expires_at TIMESTAMPTZ;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_notifications_event_outbox_id ON notifications(event_outbox_id);
CREATE INDEX IF NOT EXISTS idx_notifications_rule_id ON notifications(rule_id);
CREATE INDEX IF NOT EXISTS idx_notifications_deduplication_key ON notifications(deduplication_key);
CREATE INDEX IF NOT EXISTS idx_notifications_priority ON notifications(priority);
CREATE INDEX IF NOT EXISTS idx_notifications_expires_at ON notifications(expires_at) WHERE expires_at IS NOT NULL;

-- =============================================================================
-- NOTIFICATION PREFERENCES TABLE
-- =============================================================================

CREATE TABLE notification_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    in_app_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_notification_prefs_user_category ON notification_preferences(user_id, category);
CREATE INDEX idx_notification_prefs_workspace ON notification_preferences(workspace_id);
CREATE INDEX idx_notification_prefs_user ON notification_preferences(user_id);

-- Default categories
INSERT INTO notification_preferences (workspace_id, user_id, category, in_app_enabled, email_enabled)
SELECT wm.workspace_id, wm.user_id, cat.category, true, false
FROM workspace_members wm
CROSS JOIN (VALUES
    ('finding_critical_high'),
    ('finding_severity_changed'),
    ('scan_failed'),
    ('scan_completed'),
    ('attack_path_created'),
    ('risk_score_changed'),
    ('remediation_awaiting_approval'),
    ('remediation_approved'),
    ('remediation_rejected'),
    ('remediation_applied'),
    ('remediation_failed'),
    ('remediation_rolled_back'),
    ('verification_completed'),
    ('verification_failed'),
    ('verification_inconclusive'),
    ('report_generated'),
    ('report_generation_failed'),
    ('security_team_completed')
) AS cat(category)
WHERE wm.joined_at IS NOT NULL
ON CONFLICT (user_id, category) DO NOTHING;

-- =============================================================================
-- NOTIFICATION RULES TABLE
-- =============================================================================

CREATE TABLE notification_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    event_type TEXT NOT NULL,
    event_version TEXT NOT NULL DEFAULT '1.0',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    recipient_policy rule_recipient_policy NOT NULL DEFAULT 'asset_owners',
    specific_recipient_ids UUID[] DEFAULT '{}',
    severity_filter TEXT[] DEFAULT '{"critical", "high", "medium", "low", "info"}',
    status_filter TEXT[] DEFAULT '{"open", "triaged", "in_progress"}',
    enabled_channels notification_channel[] NOT NULL DEFAULT '{in_app}',
    deduplication_window_minutes INT NOT NULL DEFAULT 60,
    rate_limit_per_hour INT NOT NULL DEFAULT 100,
    require_acknowledgement BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledgement_timeout_hours INT,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high', 'critical')),
    action_url_template TEXT,
    action_label_template TEXT,
    created_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_rules_workspace ON notification_rules(workspace_id);
CREATE INDEX idx_notification_rules_event_type ON notification_rules(event_type);
CREATE INDEX idx_notification_rules_enabled ON notification_rules(is_enabled) WHERE is_enabled = TRUE;

-- =============================================================================
-- NOTIFICATION DELIVERIES TABLE
-- =============================================================================

CREATE TABLE notification_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    channel notification_channel NOT NULL,
    recipient_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    status delivery_status NOT NULL DEFAULT 'pending',
    attempt_count INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 5,
    next_retry_at TIMESTAMPTZ,
    last_error TEXT,
    last_error_category TEXT,
    provider_message_id TEXT,
    provider_response JSONB,
    sent_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_notification_deliveries_notification ON notification_deliveries(notification_id);
CREATE INDEX idx_notification_deliveries_workspace_status ON notification_deliveries(workspace_id, status);
CREATE INDEX idx_notification_deliveries_status_next_retry ON notification_deliveries(status, next_retry_at) WHERE status IN ('pending', 'retrying');
CREATE INDEX idx_notification_deliveries_recipient ON notification_deliveries(recipient_id);

-- =============================================================================
-- WORKFLOW RUNS TABLE
-- =============================================================================

CREATE TABLE workflow_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    workflow_id TEXT NOT NULL,
    workflow_version TEXT NOT NULL,
    trigger_event_outbox_id UUID REFERENCES event_outbox(id) ON DELETE SET NULL,
    trigger_event_type TEXT,
    trigger_resource_type TEXT,
    trigger_resource_id UUID,
    input_payload JSONB NOT NULL DEFAULT '{}',
    status workflow_status NOT NULL DEFAULT 'pending',
    current_action_index INT NOT NULL DEFAULT 0,
    actions_executed JSONB NOT NULL DEFAULT '[]',
    output_payload JSONB,
    error_message TEXT,
    error_category TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    failed_at TIMESTAMPTZ,
    timeout_at TIMESTAMPTZ,
    idempotency_key TEXT NOT NULL,
    created_by UUID REFERENCES profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_workflow_runs_idempotency_key ON workflow_runs(idempotency_key);
CREATE INDEX idx_workflow_runs_workspace ON workflow_runs(workspace_id);
CREATE INDEX idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX idx_workflow_runs_trigger_event ON workflow_runs(trigger_event_outbox_id);
CREATE INDEX idx_workflow_runs_workflow_id ON workflow_runs(workflow_id);

-- =============================================================================
-- WORKFLOW RUN EVENTS TABLE (Audit trail for workflow execution)
-- =============================================================================

CREATE TABLE workflow_run_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_run_id UUID NOT NULL REFERENCES workflow_runs(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    action_name TEXT NOT NULL,
    action_input JSONB NOT NULL DEFAULT '{}',
    action_output JSONB,
    status TEXT NOT NULL CHECK (status IN ('started', 'completed', 'failed', 'skipped')),
    error_message TEXT,
    duration_ms BIGINT,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflow_run_events_run ON workflow_run_events(workflow_run_id);
CREATE INDEX idx_workflow_run_events_workspace ON workflow_run_events(workspace_id);

-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

CREATE TRIGGER update_notification_preferences_updated_at
    BEFORE UPDATE ON notification_preferences
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_rules_updated_at
    BEFORE UPDATE ON notification_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_notification_deliveries_updated_at
    BEFORE UPDATE ON notification_deliveries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_workflow_runs_updated_at
    BEFORE UPDATE ON workflow_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_event_outbox_updated_at
    BEFORE UPDATE ON event_outbox
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- RLS POLICIES
-- =============================================================================

ALTER TABLE event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_run_events ENABLE ROW LEVEL SECURITY;

-- Event Outbox RLS
CREATE POLICY event_outbox_workspace_isolation ON event_outbox
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Notification Preferences RLS
CREATE POLICY notification_prefs_user_isolation ON notification_preferences
    USING (user_id = auth.uid());

CREATE POLICY notification_prefs_workspace_isolation ON notification_preferences
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Notification Rules RLS
CREATE POLICY notification_rules_workspace_isolation ON notification_rules
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Notification Deliveries RLS
CREATE POLICY notification_deliveries_workspace_isolation ON notification_deliveries
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Workflow Runs RLS
CREATE POLICY workflow_runs_workspace_isolation ON workflow_runs
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Workflow Run Events RLS
CREATE POLICY workflow_run_events_workspace_isolation ON workflow_run_events
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Notifications table already has RLS from 001_initial_schema.sql
-- Verify and ensure policies are correct
-- Users see only their own notifications
-- (Policy "notification_select" and "notification_user_write" already exist)
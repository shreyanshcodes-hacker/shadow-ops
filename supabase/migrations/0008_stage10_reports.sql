-- Stage 10: Security Reports & Executive Dashboard
-- Migration: 0008_stage10_reports.sql
-- Created: 2026-10-13

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE report_type AS ENUM (
    'executive_summary',
    'technical_vulnerability',
    'remediation_progress',
    'verification_regression',
    'asset_security_posture'
);

CREATE TYPE report_format AS ENUM (
    'pdf',
    'json'
);

CREATE TYPE report_status AS ENUM (
    'pending',
    'generating',
    'ready',
    'failed',
    'expired'
);

-- =============================================================================
-- REPORTS TABLE
-- =============================================================================

CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    report_type report_type NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    format report_format NOT NULL DEFAULT 'pdf',
    status report_status NOT NULL DEFAULT 'pending',
    schema_version TEXT NOT NULL DEFAULT 'report-v1',
    risk_engine_version TEXT,
    verification_policy_version TEXT,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    data_cutoff TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filters JSONB NOT NULL DEFAULT '{}',
    included_asset_ids UUID[],
    severity_filters TEXT[],
    source_record_references JSONB NOT NULL DEFAULT '{}',
    completeness JSONB NOT NULL DEFAULT '{}',
    limitations TEXT[],
    generated_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    storage_object_id UUID,
    storage_path TEXT,
    file_size_bytes BIGINT,
    checksum TEXT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reports_workspace_id ON reports(workspace_id);
CREATE INDEX idx_reports_type ON reports(report_type);
CREATE INDEX idx_reports_status ON reports(status);
CREATE INDEX idx_reports_generated_by ON reports(generated_by);
CREATE INDEX idx_reports_created_at ON reports(created_at DESC);
CREATE INDEX idx_reports_period ON reports(period_start, period_end);

-- =============================================================================
-- REPORT SECTIONS TABLE (for structured report content)
-- =============================================================================

CREATE TABLE report_sections (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    section_key TEXT NOT NULL,
    section_title TEXT NOT NULL,
    section_order INTEGER NOT NULL DEFAULT 0,
    content JSONB NOT NULL DEFAULT '{}',
    data_references JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_report_sections_report_id ON report_sections(report_id);
CREATE INDEX idx_report_sections_workspace_id ON report_sections(workspace_id);
CREATE UNIQUE INDEX uq_report_section_key ON report_sections(report_id, section_key);

-- =============================================================================
-- REPORT EXPORTS TABLE (for tracking exports)
-- =============================================================================

CREATE TABLE report_exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    format report_format NOT NULL,
    storage_object_id UUID,
    storage_path TEXT,
    file_size_bytes BIGINT,
    checksum TEXT,
    generated_by UUID NOT NULL REFERENCES profiles(id) ON DELETE RESTRICT,
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_report_exports_report_id ON report_exports(report_id);
CREATE INDEX idx_report_exports_workspace_id ON report_exports(workspace_id);
CREATE INDEX idx_report_exports_created_at ON report_exports(created_at DESC);

-- =============================================================================
-- RLS POLICIES
-- =============================================================================

ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_exports ENABLE ROW LEVEL SECURITY;

-- Reports RLS
CREATE POLICY reports_workspace_isolation ON reports
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Report Sections RLS
CREATE POLICY report_sections_workspace_isolation ON report_sections
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- Report Exports RLS
CREATE POLICY report_exports_workspace_isolation ON report_exports
    USING (workspace_id IN (
        SELECT workspace_id FROM workspace_members WHERE user_id = auth.uid()
    ));

-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

CREATE TRIGGER update_reports_updated_at
    BEFORE UPDATE ON reports
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- STORAGE BUCKET FOR REPORTS (if using Supabase Storage)
-- =============================================================================
-- Note: Bucket creation is typically done via Supabase dashboard or client
-- This is a placeholder for the bucket configuration
-- INSERT INTO storage.buckets (id, name, public) VALUES ('reports', 'reports', false);
-- CREATE POLICY reports_storage_read ON storage.objects FOR SELECT USING (bucket_id = 'reports' AND auth.uid() IN (SELECT user_id FROM workspace_members WHERE workspace_id = (SELECT workspace_id FROM reports WHERE id = (storage.foldername(name))[1]::uuid)));
-- CREATE POLICY reports_storage_write ON storage.objects FOR INSERT WITH CHECK (bucket_id = 'reports' AND auth.uid() IN (SELECT user_id FROM workspace_members WHERE workspace_id = (SELECT workspace_id FROM reports WHERE id = (storage.foldername(name))[1]::uuid)));
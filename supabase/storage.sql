-- Supabase Storage Buckets for ShadowOps
-- Run this in Supabase SQL Editor after creating the project

-- Create storage buckets
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES
  ('evidence', 'evidence', false, 52428800, ARRAY['image/*', 'text/*', 'application/json', 'application/pdf']),
  ('reports', 'reports', false, 104857600, ARRAY['application/pdf', 'text/html', 'application/json', 'text/markdown']),
  ('artifacts', 'artifacts', false, 52428800, ARRAY['application/zip', 'application/gzip', 'application/octet-stream']),
  ('remediation', 'remediation', false, 52428800, ARRAY['text/*', 'application/json', 'application/x-diff']),
  ('verification', 'verification', false, 52428800, ARRAY['text/*', 'application/json', 'image/*'])
ON CONFLICT (id) DO NOTHING;

-- Storage Policies

-- Evidence bucket: workspace members can upload/read their workspace evidence
CREATE POLICY "evidence_workspace_access" ON storage.objects
  FOR ALL USING (
    bucket_id = 'evidence' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids())
  );

-- Reports bucket: workspace members can read, admins can write
CREATE POLICY "reports_workspace_read" ON storage.objects
  FOR SELECT USING (
    bucket_id = 'reports' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids())
  );

CREATE POLICY "reports_admin_write" ON storage.objects
  FOR INSERT WITH CHECK (
    bucket_id = 'reports' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids()) AND
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = (storage.foldername(name))[1]::uuid
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
      AND joined_at IS NOT NULL
    )
  );

-- Artifacts bucket: workspace members can read, system can write
CREATE POLICY "artifacts_workspace_read" ON storage.objects
  FOR SELECT USING (
    bucket_id = 'artifacts' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids())
  );

-- Remediation bucket: workspace members can read, system writes
CREATE POLICY "remediation_workspace_read" ON storage.objects
  FOR SELECT USING (
    bucket_id = 'remediation' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids())
  );

CREATE POLICY "remediation_system_write" ON storage.objects
  FOR INSERT WITH CHECK (
    bucket_id = 'remediation'
  );

-- Verification bucket: workspace members can read, system writes
CREATE POLICY "verification_workspace_read" ON storage.objects
  FOR SELECT USING (
    bucket_id = 'verification' AND
    (storage.foldername(name))[1] = ANY(current_user_workspace_ids())
  );

CREATE POLICY "verification_system_write" ON storage.objects
  FOR INSERT WITH CHECK (
    bucket_id = 'verification'
  );

-- Helper function for current user's workspace IDs
CREATE OR REPLACE FUNCTION current_user_workspace_ids()
RETURNS UUID[] LANGUAGE sql STABLE AS $$
  SELECT array_agg(workspace_id) FROM workspace_members
  WHERE user_id = auth.uid() AND joined_at IS NOT NULL;
$$;
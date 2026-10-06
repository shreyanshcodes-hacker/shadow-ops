# Database Architecture

## Overview

ShadowOps uses **Supabase PostgreSQL** as the primary database with Row Level Security (RLS) for workspace isolation.

## Design Principles

1. **Workspace Isolation via RLS** - Every table with workspace data has RLS policies
2. **Explicit Foreign Keys** - All relationships enforced at DB level
3. **Audit Fields** - `created_at`, `updated_at`, `created_by` on all tables
4. **Soft Deletes** - `deleted_at` for recoverable deletion
5. **Immutable Events** - `scan_events`, `audit_logs` are append-only
6. **JSONB for Flexibility** - Evidence, AI outputs, configurable metadata
7. **Indexes for Query Patterns** - Composite indexes matching access patterns

## Core Tables

### 1. profiles
Extended user profile synced from Firebase Auth.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| firebase_uid | TEXT | UNIQUE, NOT NULL |
| email | TEXT | NOT NULL |
| display_name | TEXT | |
| avatar_url | TEXT | |
| role | TEXT | DEFAULT 'user' (user, admin) |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |
| last_login_at | TIMESTAMPTZ | |

### 2. workspaces
Top-level container for all resources; billing/plan boundary.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| name | TEXT | NOT NULL |
| slug | TEXT | UNIQUE, NOT NULL |
| owner_id | UUID | FK → profiles.id, NOT NULL |
| plan | TEXT | DEFAULT 'free' |
| settings | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |
| deleted_at | TIMESTAMPTZ | Soft delete |

### 3. workspace_members
Many-to-many users ↔ workspaces with roles.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| user_id | UUID | FK → profiles.id, NOT NULL |
| role | TEXT | NOT NULL (owner, admin, member, viewer) |
| invited_by | UUID | FK → profiles.id |
| invited_at | TIMESTAMPTZ | DEFAULT now() |
| joined_at | TIMESTAMPTZ | Null until accepted |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### 4. assets
Targets to be scanned (repos, APIs, infra, apps).

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| name | TEXT | NOT NULL |
| type | TEXT | NOT NULL (repository, api, infrastructure, application, container) |
| subtype | TEXT | (github, gitlab, bitbucket, aws, gcp, kubernetes, docker, generic) |
| connection_config | JSONB | NOT NULL |
| credentials_ref | TEXT | Reference to secret in vault |
| criticality | TEXT | DEFAULT 'medium' (low, medium, high, critical) |
| status | TEXT | DEFAULT 'active' (active, archived, error) |
| last_scanned_at | TIMESTAMPTZ | |
| scan_frequency | INTERVAL | DEFAULT '24 hours' |
| tags | TEXT[] | DEFAULT '{}' |
| created_by | UUID | FK → profiles.id, NOT NULL |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |
| deleted_at | TIMESTAMPTZ | |

### 5. asset_authorizations
Proof of authorization to scan an asset (ENFORCES NO AUTH → NO SCAN).

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| asset_id | UUID | FK → assets.id, NOT NULL, UNIQUE |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| authorization_type | TEXT | NOT NULL (ownership, written_permission, bug_bounty, internal) |
| evidence_files | UUID[] | Array of storage object IDs |
| evidence_urls | TEXT[] | External URLs |
| authorized_by | TEXT | Name/role of authorizer |
| authorized_at | TIMESTAMPTZ | NOT NULL |
| expires_at | TIMESTAMPTZ | Optional expiration |
| status | TEXT | DEFAULT 'pending' (pending, verified, rejected, expired) |
| verified_by | UUID | FK → profiles.id |
| verified_at | TIMESTAMPTZ | |
| notes | TEXT | |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

**Critical**: Backend must check `status = 'verified' AND (expires_at IS NULL OR expires_at > now())` before allowing scan.

### 6. scans
Scan execution records.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| asset_id | UUID | FK → assets.id, NOT NULL |
| scan_type | TEXT | NOT NULL (full, recon, code, dependency, targeted) |
| status | TEXT | DEFAULT 'queued' (queued, running, completed, failed, cancelled, partial) |
| triggered_by | UUID | FK → profiles.id, NOT NULL |
| triggered_at | TIMESTAMPTZ | DEFAULT now() |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| duration_ms | BIGINT | |
| phases_completed | TEXT[] | DEFAULT '{}' |
| current_phase | TEXT | |
| progress_percent | INT | DEFAULT 0 |
| error_message | TEXT | |
| scan_config | JSONB | DEFAULT '{}' |
| summary | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

### 7. scan_events
Immutable event log for scan progress (realtime UI, debugging, audit).

| Column | Type | Constraints |
|--------|------|-------------|
| id | BIGSERIAL | PK |
| scan_id | UUID | FK → scans.id, NOT NULL |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| phase | TEXT | NOT NULL |
| event_type | TEXT | NOT NULL |
| message | TEXT | NOT NULL |
| data | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### 8. agent_runs
Track individual AI agent executions within a scan.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| scan_id | UUID | FK → scans.id, NOT NULL |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| agent_name | TEXT | NOT NULL |
| model_used | TEXT | |
| status | TEXT | DEFAULT 'pending' (pending, running, completed, failed, timeout) |
| input_summary | JSONB | |
| output_summary | JSONB | |
| tokens_input | INT | |
| tokens_output | INT | |
| cost_usd | DECIMAL(10,6) | |
| started_at | TIMESTAMPTZ | |
| completed_at | TIMESTAMPTZ | |
| error_message | TEXT | |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### 9. findings
Normalized security findings from all sources.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| scan_id | UUID | FK → scans.id, NOT NULL |
| asset_id | UUID | FK → assets.id, NOT NULL |
| source | TEXT | NOT NULL (semgrep, recon, dependency, ai_analysis, manual) |
| source_rule_id | TEXT | |
| title | TEXT | NOT NULL |
| description | TEXT | NOT NULL |
| severity | TEXT | NOT NULL (critical, high, medium, low, info) |
| confidence | TEXT | DEFAULT 'medium' (low, medium, high) |
| cwe_ids | TEXT[] | DEFAULT '{}' |
| cve_ids | TEXT[] | DEFAULT '{}' |
| owasp_categories | TEXT[] | DEFAULT '{}' |
| location | JSONB | |
| code_snippet | TEXT | |
| remediation_guidance | TEXT | |
| status | TEXT | DEFAULT 'open' (open, triaged, in_progress, fixed, false_positive, wont_fix, risk_accepted) |
| triaged_by | UUID | FK → profiles.id |
| triaged_at | TIMESTAMPTZ | |
| risk_score | DECIMAL(5,2) | |
| risk_factors | JSONB | DEFAULT '{}' |
| first_seen_at | TIMESTAMPTZ | DEFAULT now() |
| last_seen_at | TIMESTAMPTZ | DEFAULT now() |
| fixed_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

### 10. finding_evidence
Provenance and evidence for each finding.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| finding_id | UUID | FK → findings.id, NOT NULL |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| evidence_type | TEXT | NOT NULL (code_snippet, screenshot, log, request_response, config, dependency_tree, ai_reasoning) |
| title | TEXT | NOT NULL |
| description | TEXT | |
| content | JSONB | |
| file_path | TEXT | |
| line_start | INT | |
| line_end | INT | |
| storage_object_id | UUID | Ref to Supabase Storage |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### 11. risk_assessments
Deterministic risk calculation results.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| finding_id | UUID | FK → findings.id, NOT NULL, UNIQUE |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| base_score | DECIMAL(5,2) | NOT NULL |
| exploitability | DECIMAL(5,2) | |
| exposure | DECIMAL(5,2) | |
| asset_criticality | DECIMAL(5,2) | |
| confidence | DECIMAL(5,2) | |
| attack_path_impact | DECIMAL(5,2) | DEFAULT 0 |
| final_score | DECIMAL(5,2) | NOT NULL |
| factors | JSONB | NOT NULL |
| formula_version | TEXT | NOT NULL |
| calculated_at | TIMESTAMPTZ | DEFAULT now() |
| calculated_by | TEXT | NOT NULL |

### 12-15. Attack Path Tables
- `attack_paths` - Graph containers
- `attack_path_nodes` - Nodes (asset, vulnerability, network_zone, trust_boundary, data_store, attacker)
- `attack_path_edges` - Directed edges (exploits, accesses, trusts, contains, lateral_movement, privilege_escalation)

### 16-18. Remediation & Verification
- `remediation_proposals` - AI-generated fix proposals
- `remediation_approvals` - Human approval audit trail
- `verification_runs` - Empirical verification results

### 19. reports
Generated reports (executive, technical, scan).

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| scan_id | UUID | FK → scans.id |
| report_type | TEXT | NOT NULL (executive, technical, scan, compliance, custom) |
| title | TEXT | NOT NULL |
| format | TEXT | NOT NULL (pdf, html, json, markdown) |
| status | TEXT | DEFAULT 'generating' (generating, ready, failed) |
| storage_object_id | UUID | Supabase Storage object ID |
| generated_by | TEXT | NOT NULL |
| period_start | TIMESTAMPTZ | |
| period_end | TIMESTAMPTZ | |
| metadata | JSONB | DEFAULT '{}' |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| completed_at | TIMESTAMPTZ | |

### 20-21. Chat Tables
- `chat_conversations` - AI Security Chat sessions
- `chat_messages` - Messages with citations

### 22. audit_logs
Immutable audit trail for all security-relevant actions.

| Column | Type | Constraints |
|--------|------|-------------|
| id | BIGSERIAL | PK |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| user_id | UUID | FK → profiles.id |
| action | TEXT | NOT NULL |
| resource_type | TEXT | NOT NULL |
| resource_id | UUID | |
| old_state | JSONB | |
| new_state | JSONB | |
| ip_address | INET | |
| user_agent | TEXT | |
| request_id | UUID | DEFAULT gen_random_uuid() |
| created_at | TIMESTAMPTZ | DEFAULT now() |

### 23. notifications
In-app and external notifications.

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK, default gen_random_uuid() |
| workspace_id | UUID | FK → workspaces.id, NOT NULL |
| user_id | UUID | FK → profiles.id, NOT NULL |
| type | TEXT | NOT NULL |
| title | TEXT | NOT NULL |
| message | TEXT | NOT NULL |
| reference_type | TEXT | |
| reference_id | UUID | |
| channels | TEXT[] | DEFAULT '{in_app}' |
| read_at | TIMESTAMPTZ | |
| sent_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | DEFAULT now() |

## RLS Policy Pattern

```sql
-- Enable RLS
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

-- Helper: current user's workspace IDs
CREATE OR REPLACE FUNCTION current_user_workspace_ids()
RETURNS uuid[] LANGUAGE sql STABLE AS $$
  SELECT array_agg(workspace_id) FROM workspace_members
  WHERE user_id = auth.uid() AND joined_at IS NOT NULL;
$$;

-- Members can SELECT
CREATE POLICY "workspace_member_select" ON assets
  FOR SELECT USING (workspace_id = ANY(current_user_workspace_ids()));

-- Admins/Owners can INSERT/UPDATE/DELETE
CREATE POLICY "workspace_admin_write" ON assets
  FOR ALL USING (
    workspace_id = ANY(current_user_workspace_ids()) AND
    EXISTS (
      SELECT 1 FROM workspace_members
      WHERE workspace_id = assets.workspace_id
      AND user_id = auth.uid()
      AND role IN ('owner', 'admin')
      AND joined_at IS NOT NULL
    )
  );
```

## Migration Strategy

1. **Stage 1**: Core tables (profiles, workspaces, workspace_members, roles)
2. **Stage 4-5**: Assets, asset_authorizations
3. **Stage 6**: Scans, scan_events
4. **Stage 7**: Findings, finding_evidence
5. **Stage 8-9**: Agent runs, AI Manager tables
6. **Stage 10-12**: Risk assessments, attack paths
7. **Stage 13-14**: Remediation, verification
8. **Stage 15**: Reports
9. **Stage 16**: Chat
10. **Stage 19**: Audit logs, notifications

## Updated_at Trigger

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE ON profiles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
-- ... repeat for all tables
```
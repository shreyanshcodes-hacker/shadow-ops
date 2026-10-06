# DATABASE ARCHITECTURE

## Design Principles

1. **Workspace Isolation via RLS** — Every table with workspace data has Row Level Security policies
2. **Explicit Foreign Keys** — All relationships enforced at DB level
3. **Audit Fields** — `created_at`, `updated_at`, `created_by` on all tables
4. **Soft Deletes** — `deleted_at` for recoverable deletion
5. **Immutable Events** — `scan_events`, `audit_logs` are append-only
6. **JSONB for Flexibility** — Evidence, AI outputs, configurable metadata
7. **Indexes for Query Patterns** — Composite indexes matching access patterns

---

## Table Definitions

### 1. users / profiles

**Purpose**: Extended user profile synced from Firebase Auth

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | Internal user ID |
| firebase_uid | TEXT | UNIQUE, NOT NULL | Firebase Auth UID |
| email | TEXT | NOT NULL | User email |
| display_name | TEXT | | Display name |
| avatar_url | TEXT | | Profile image |
| role | TEXT | DEFAULT 'user' | Global role: user, admin |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |
| last_login_at | TIMESTAMPTZ | | |

**Indexes**: `idx_profiles_firebase_uid` (unique), `idx_profiles_email`

**RLS**: Users see only their own profile. Admins see all.

---

### 2. workspaces

**Purpose**: Top-level container for all resources; billing/plan boundary

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| name | TEXT | NOT NULL | Workspace name |
| slug | TEXT | UNIQUE, NOT NULL | URL-friendly identifier |
| owner_id | UUID | FK → profiles.id, NOT NULL | Workspace owner |
| plan | TEXT | DEFAULT 'free' | free, pro, enterprise |
| settings | JSONB | DEFAULT '{}' | Configuration (notifications, retention, etc.) |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |
| deleted_at | TIMESTAMPTZ | | Soft delete |

**Indexes**: `idx_workspaces_owner_id`, `idx_workspaces_slug`

**RLS**: Members see workspaces they belong to. Owner sees all.

---

### 3. workspace_members

**Purpose**: Many-to-many users ↔ workspaces with roles

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| user_id | UUID | FK → profiles.id, NOT NULL | |
| role | TEXT | NOT NULL | owner, admin, member, viewer |
| invited_by | UUID | FK → profiles.id | |
| invited_at | TIMESTAMPTZ | DEFAULT now() | |
| joined_at | TIMESTAMPTZ | | Null until accepted |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_ws_members_ws_id`, `idx_ws_members_user_id`, `uq_ws_members_ws_user` (unique on workspace_id + user_id)

**RLS**: Users see memberships for workspaces they belong to.

---

### 4. roles (Reference Table)

**Purpose**: Role definitions and permissions (extensible)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | TEXT | PK | owner, admin, member, viewer |
| name | TEXT | NOT NULL | Display name |
| permissions | JSONB | NOT NULL | Permission bitmask/array |
| description | TEXT | | |

**Data**: Pre-populated with 4 roles. Extensible for custom roles (Enterprise).

---

### 5. assets

**Purpose**: Targets to be scanned (repos, APIs, infra, apps)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| name | TEXT | NOT NULL | Display name |
| type | TEXT | NOT NULL | repository, api, infrastructure, application, container |
| subtype | TEXT | | github, gitlab, bitbucket, aws, gcp, kubernetes, docker, generic |
| connection_config | JSONB | NOT NULL | Type-specific config (URL, credentials ref, paths) |
| credentials_ref | TEXT | | Reference to secret in vault (not stored in DB) |
| criticality | TEXT | DEFAULT 'medium' | low, medium, high, critical |
| status | TEXT | DEFAULT 'active' | active, archived, error |
| last_scanned_at | TIMESTAMPTZ | | |
| scan_frequency | INTERVAL | DEFAULT '24 hours' | For scheduled scans |
| tags | TEXT[] | DEFAULT '{}' | User-defined tags |
| created_by | UUID | FK → profiles.id, NOT NULL | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |
| deleted_at | TIMESTAMPTZ | | |

**Indexes**: `idx_assets_ws_id`, `idx_assets_type`, `idx_assets_status`, `idx_assets_last_scanned`

**RLS**: Workspace members see assets in their workspace.

**Security**: `credentials_ref` points to external secret manager (Supabase Vault / Railway secrets). Never store secrets in DB.

---

### 6. asset_authorizations

**Purpose**: Proof of authorization to scan an asset (ENFORCES NO AUTH → NO SCAN)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| asset_id | UUID | FK → assets.id, NOT NULL, UNIQUE | One authorization per asset |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | Denormalized for RLS |
| authorization_type | TEXT | NOT NULL | ownership, written_permission, bug_bounty, internal |
| evidence_files | UUID[] | | Array of storage object IDs (screenshots, docs) |
| evidence_urls | TEXT[] | | External URLs (policy pages, emails) |
| authorized_by | TEXT | | Name/role of authorizer |
| authorized_at | TIMESTAMPTZ | NOT NULL | When authorization was granted |
| expires_at | TIMESTAMPTZ | | Optional expiration |
| status | TEXT | DEFAULT 'pending' | pending, verified, rejected, expired |
| verified_by | UUID | FK → profiles.id | Who verified |
| verified_at | TIMESTAMPTZ | | |
| notes | TEXT | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_asset_auth_asset_id` (unique), `idx_asset_auth_ws_id`, `idx_asset_auth_status`

**RLS**: Workspace members see authorizations for their workspace assets.

**Critical**: Backend **must** check `status = 'verified' AND (expires_at IS NULL OR expires_at > now())` before allowing scan.

---

### 7. scans

**Purpose**: Scan execution records

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| asset_id | UUID | FK → assets.id, NOT NULL | |
| scan_type | TEXT | NOT NULL | full, recon, code, dependency, targeted |
| status | TEXT | DEFAULT 'queued' | queued, running, completed, failed, cancelled, partial |
| triggered_by | UUID | FK → profiles.id, NOT NULL | User or 'scheduler' |
| triggered_at | TIMESTAMPTZ | DEFAULT now() | |
| started_at | TIMESTAMPTZ | | |
| completed_at | TIMESTAMPTZ | | |
| duration_ms | BIGINT | | Total duration |
| phases_completed | TEXT[] | DEFAULT '{}' | ['recon', 'code', 'dependency', 'analysis', 'risk', 'attack_path'] |
| current_phase | TEXT | | For progress tracking |
| progress_percent | INT | DEFAULT 0 | 0-100 |
| error_message | TEXT | | If failed |
| scan_config | JSONB | DEFAULT '{}' | Semgrep config, AI config, scope limits |
| summary | JSONB | DEFAULT '{}' | Counts by severity, risk score, etc. |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_scans_ws_id`, `idx_scans_asset_id`, `idx_scans_status`, `idx_scans_triggered_at`

**RLS**: Workspace members see scans in their workspace.

---

### 8. scan_events

**Purpose**: Immutable event log for scan progress (realtime UI, debugging, audit)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | BIGSERIAL | PK | Auto-increment for ordering |
| scan_id | UUID | FK → scans.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | Denormalized for RLS |
| phase | TEXT | NOT NULL | queued, recon, code_analysis, dep_analysis, normalization, ai_analysis, risk, attack_path, completed |
| event_type | TEXT | NOT NULL | phase_start, phase_progress, phase_complete, finding, error, warning, info |
| message | TEXT | NOT NULL | Human-readable |
| data | JSONB | DEFAULT '{}' | Structured data (finding counts, percentages, etc.) |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_scan_events_scan_id_created` (scan_id, created_at DESC), `idx_scan_events_ws_id`

**RLS**: Workspace members see events for their workspace scans.

**Retention**: 90 days (configurable per workspace plan).

---

### 9. agent_runs

**Purpose**: Track individual AI agent executions within a scan

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| scan_id | UUID | FK → scans.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| agent_name | TEXT | NOT NULL | recon, code_security, dependency, threat_analyst, risk_analyst, remediation, verification, reporting |
| model_used | TEXT | | gemini-1.5-pro, gemini-1.5-flash, grok |
| status | TEXT | DEFAULT 'pending' | pending, running, completed, failed, timeout |
| input_summary | JSONB | | Truncated input for debugging |
| output_summary | JSONB | | Truncated output |
| tokens_input | INT | | |
| tokens_output | INT | | |
| cost_usd | DECIMAL(10,6) | | Estimated cost |
| started_at | TIMESTAMPTZ | | |
| completed_at | TIMESTAMPTZ | | |
| error_message | TEXT | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_agent_runs_scan_id`, `idx_agent_runs_agent_name`, `idx_agent_runs_ws_id`

**RLS**: Workspace members see agent runs for their workspace scans.

---

### 10. findings

**Purpose**: Normalized security findings from all sources

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| scan_id | UUID | FK → scans.id, NOT NULL | |
| asset_id | UUID | FK → assets.id, NOT NULL | |
| source | TEXT | NOT NULL | semgrep, recon, dependency, ai_analysis, manual |
| source_rule_id | TEXT | | Semgrep rule ID, CVE ID, etc. |
| title | TEXT | NOT NULL | Short title |
| description | TEXT | NOT NULL | Detailed description |
| severity | TEXT | NOT NULL | critical, high, medium, low, info |
| confidence | TEXT | DEFAULT 'medium' | low, medium, high (AI-assessed) |
| cwe_ids | TEXT[] | DEFAULT '{}' | CWE identifiers |
| cve_ids | TEXT[] | DEFAULT '{}' | CVE identifiers |
| owasp_categories | TEXT[] | DEFAULT '{}' | OWASP Top 10 categories |
| location | JSONB | | File, line, function, endpoint, etc. |
| code_snippet | TEXT | | Relevant code (truncated) |
| remediation_guidance | TEXT | | Generic guidance |
| status | TEXT | DEFAULT 'open' | open, triaged, in_progress, fixed, false_positive, wont_fix, risk_accepted |
| triaged_by | UUID | FK → profiles.id | |
| triaged_at | TIMESTAMPTZ | | |
| risk_score | DECIMAL(5,2) | | 0-100 (from risk engine) |
| risk_factors | JSONB | DEFAULT '{}' | Breakdown of risk calculation |
| first_seen_at | TIMESTAMPTZ | DEFAULT now() | |
| last_seen_at | TIMESTAMPTZ | DEFAULT now() | |
| fixed_at | TIMESTAMPTZ | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: 
- `idx_findings_ws_id`
- `idx_findings_scan_id`
- `idx_findings_asset_id`
- `idx_findings_severity`
- `idx_findings_status`
- `idx_findings_risk_score` (DESC)
- `idx_findings_source_rule` (source, source_rule_id)

**RLS**: Workspace members see findings in their workspace.

---

### 11. finding_evidence

**Purpose**: Provenance and evidence for each finding

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| finding_id | UUID | FK → findings.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| evidence_type | TEXT | NOT NULL | code_snippet, screenshot, log, request_response, config, dependency_tree, ai_reasoning |
| title | TEXT | NOT NULL | |
| description | TEXT | | |
| content | JSONB | | Structured evidence (varies by type) |
| file_path | TEXT | | Source file path |
| line_start | INT | | |
| line_end | INT | | |
| storage_object_id | UUID | | Ref to Supabase Storage object |
| metadata | JSONB | DEFAULT '{}' | Tool version, timestamps, etc. |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_finding_evidence_finding_id`, `idx_finding_evidence_type`

**RLS**: Workspace members see evidence for their workspace findings.

---

### 12. risk_assessments

**Purpose**: Deterministic risk calculation results (separate from findings for history)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| finding_id | UUID | FK → findings.id, NOT NULL, UNIQUE | One assessment per finding |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| base_score | DECIMAL(5,2) | NOT NULL | 0-100 (CVSS-like base) |
| exploitability | DECIMAL(5,2) | | 0-100 |
| exposure | DECIMAL(5,2) | | 0-100 (network exposure) |
| asset_criticality | DECIMAL(5,2) | | 0-100 (from asset.criticality) |
| confidence | DECIMAL(5,2) | | 0-100 (from finding.confidence) |
| attack_path_impact | DECIMAL(5,2) | DEFAULT 0 | Additional risk from attack paths |
| final_score | DECIMAL(5,2) | NOT NULL | 0-100 (weighted formula) |
| factors | JSONB | NOT NULL | Full factor breakdown with weights |
| formula_version | TEXT | NOT NULL | Version of risk formula used |
| calculated_at | TIMESTAMPTZ | DEFAULT now() | |
| calculated_by | TEXT | NOT NULL | 'risk_engine_v1' |

**Indexes**: `idx_risk_assessments_finding_id` (unique), `idx_risk_assessments_ws_id`, `idx_risk_assessments_final_score` (DESC)

**RLS**: Workspace members see assessments for their workspace findings.

---

### 13. attack_paths

**Purpose**: Constructed attack paths (graph containers)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| scan_id | UUID | FK → scans.id | Originating scan |
| name | TEXT | NOT NULL | Auto-generated or custom |
| description | TEXT | | |
| entry_point | TEXT | | e.g., "Internet" |
| target_asset | TEXT | | e.g., "Customer Database" |
| risk_score | DECIMAL(5,2) | | Path aggregate risk |
| node_count | INT | DEFAULT 0 | |
| edge_count | INT | DEFAULT 0 | |
| is_critical | BOOLEAN | DEFAULT FALSE | |
| status | TEXT | DEFAULT 'active' | active, mitigated, broken |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_attack_paths_ws_id`, `idx_attack_paths_scan_id`, `idx_attack_paths_risk_score` (DESC)

**RLS**: Workspace members see attack paths in their workspace.

---

### 14. attack_path_nodes

**Purpose**: Nodes in attack path graph

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| attack_path_id | UUID | FK → attack_paths.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| node_type | TEXT | NOT NULL | asset, vulnerability, network_zone, trust_boundary, data_store, attacker |
| label | TEXT | NOT NULL | Display label |
| description | TEXT | | |
| asset_id | UUID | FK → assets.id | If node represents an asset |
| finding_id | UUID | FK → findings.id | If node represents a vulnerability |
| risk_contribution | DECIMAL(5,2) | DEFAULT 0 | Node's risk contribution |
| metadata | JSONB | DEFAULT '{}' | Position, styling, extra data |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_ap_nodes_path_id`, `idx_ap_nodes_asset_id`, `idx_ap_nodes_finding_id`

**RLS**: Workspace members see nodes for their workspace attack paths.

---

### 15. attack_path_edges

**Purpose**: Directed edges in attack path graph

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| attack_path_id | UUID | FK → attack_paths.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| source_node_id | UUID | FK → attack_path_nodes.id, NOT NULL | |
| target_node_id | UUID | FK → attack_path_nodes.id, NOT NULL | |
| edge_type | TEXT | NOT NULL | exploits, accesses, trusts, contains, lateral_movement, privilege_escalation |
| description | TEXT | | |
| evidence_refs | UUID[] | | Finding/evidence IDs supporting this edge |
| likelihood | DECIMAL(5,2) | | 0-100 |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_ap_edges_path_id`, `idx_ap_edges_source`, `idx_ap_edges_target`

**RLS**: Workspace members see edges for their workspace attack paths.

---

### 16. remediation_proposals

**Purpose**: AI-generated remediation proposals awaiting human review

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| finding_id | UUID | FK → findings.id, NOT NULL | |
| proposed_by | TEXT | NOT NULL | 'ai_manager', 'remediation_agent' |
| model_used | TEXT | | gemini-1.5-pro, grok |
| title | TEXT | NOT NULL | |
| description | TEXT | NOT NULL | |
| fix_type | TEXT | NOT NULL | code_change, config_change, dependency_update, infrastructure_change, waf_rule, network_policy |
| code_changes | JSONB | | Structured diff/patch for code fixes |
| config_changes | JSONB | | Structured config changes |
| commands | TEXT[] | | CLI commands to apply |
| prerequisites | TEXT[] | | Required before applying |
| risk_level | TEXT | DEFAULT 'medium' | low, medium, high (risk of applying) |
| confidence | TEXT | DEFAULT 'medium' | low, medium, high (AI confidence) |
| estimated_effort | TEXT | | minutes, hours, days |
| status | TEXT | DEFAULT 'proposed' | proposed, approved, rejected, applied, superseded |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_remediation_proposals_ws_id`, `idx_remediation_proposals_finding_id`, `idx_remediation_proposals_status`

**RLS**: Workspace members see proposals for their workspace findings.

---

### 17. remediation_approvals

**Purpose**: Audit trail for human approval of remediation

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| proposal_id | UUID | FK → remediation_proposals.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| approved_by | UUID | FK → profiles.id, NOT NULL | |
| decision | TEXT | NOT NULL | approved, rejected |
| justification | TEXT | | Required for rejection |
| conditions | TEXT[] | | Conditions for approval (e.g., "test in staging first") |
| approved_at | TIMESTAMPTZ | DEFAULT now() | |
| expires_at | TIMESTAMPTZ | | Approval expiration |

**Indexes**: `idx_remediation_approvals_proposal_id`, `idx_remediation_approvals_ws_id`

**RLS**: Workspace members see approvals for their workspace proposals.

---

### 18. verification_runs

**Purpose**: Verification that fixes actually work

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| finding_id | UUID | FK → findings.id, NOT NULL | |
| proposal_id | UUID | FK → remediation_proposals.id | |
| scan_id | UUID | FK → scans.id | Verification scan |
| verification_type | TEXT | NOT NULL | reproduction_test, semgrep_rescan, dependency_check, config_audit, regression_test |
| status | TEXT | DEFAULT 'pending' | pending, running, passed, failed, inconclusive |
| result | JSONB | | Details: what was tested, what passed/failed |
| evidence_refs | UUID[] | | Evidence from verification |
| passed | BOOLEAN | | |
| started_at | TIMESTAMPTZ | | |
| completed_at | TIMESTAMPTZ | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_verification_runs_ws_id`, `idx_verification_runs_finding_id`, `idx_verification_runs_proposal_id`

**RLS**: Workspace members see verifications for their workspace findings.

---

### 19. reports

**Purpose**: Generated reports (executive, technical, scan)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| scan_id | UUID | FK → scans.id | Optional: scan-specific report |
| report_type | TEXT | NOT NULL | executive, technical, scan, compliance, custom |
| title | TEXT | NOT NULL | |
| description | TEXT | | |
| format | TEXT | NOT NULL | pdf, html, json, markdown |
| status | TEXT | DEFAULT 'generating' | generating, ready, failed |
| storage_object_id | UUID | | Supabase Storage object ID |
| generated_by | TEXT | NOT NULL | 'reporting_agent', 'scheduled', 'manual' |
| period_start | TIMESTAMPTZ | | Report period |
| period_end | TIMESTAMPTZ | | |
| metadata | JSONB | DEFAULT '{}' | Template version, sections, etc. |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| completed_at | TIMESTAMPTZ | | |

**Indexes**: `idx_reports_ws_id`, `idx_reports_scan_id`, `idx_reports_type`, `idx_reports_created_at`

**RLS**: Workspace members see reports for their workspace.

---

### 20. chat_conversations

**Purpose**: AI Security Chat conversations

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| user_id | UUID | FK → profiles.id, NOT NULL | |
| title | TEXT | | Auto-generated from first message |
| context_type | TEXT | | general, finding, asset, scan, attack_path, report |
| context_id | UUID | | Reference to context object |
| message_count | INT | DEFAULT 0 | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |
| updated_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_chat_conv_ws_id`, `idx_chat_conv_user_id`, `idx_chat_conv_context`

**RLS**: Users see their own conversations in workspace.

---

### 21. chat_messages

**Purpose**: Individual chat messages

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| conversation_id | UUID | FK → chat_conversations.id, NOT NULL | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| role | TEXT | NOT NULL | user, assistant, system |
| content | TEXT | NOT NULL | Message content |
| citations | UUID[] | | Finding/evidence/report IDs cited |
| model_used | TEXT | | |
| tokens_input | INT | | |
| tokens_output | INT | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_chat_messages_conv_id_created` (conversation_id, created_at), `idx_chat_messages_ws_id`

**RLS**: Users see messages in their workspace conversations.

---

### 22. audit_logs

**Purpose**: Immutable audit trail for all security-relevant actions

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | BIGSERIAL | PK | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| user_id | UUID | FK → profiles.id | Null for system actions |
| action | TEXT | NOT NULL | Standardized action codes |
| resource_type | TEXT | NOT NULL | asset, scan, finding, remediation, authorization, member, settings |
| resource_id | UUID | | |
| old_state | JSONB | | Before state (for updates) |
| new_state | JSONB | | After state (for creates/updates) |
| ip_address | INET | | |
| user_agent | TEXT | | |
| request_id | UUID | | Correlation ID |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_audit_logs_ws_id_created` (workspace_id, created_at DESC), `idx_audit_logs_user_id`, `idx_audit_logs_resource`, `idx_audit_logs_action`

**RLS**: Workspace admins/owners see audit logs. Regular members do not.

**Retention**: 7 years (compliance). Never deleted.

---

### 23. notifications

**Purpose**: In-app and external notifications

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK, default gen_random_uuid() | |
| workspace_id | UUID | FK → workspaces.id, NOT NULL | |
| user_id | UUID | FK → profiles.id, NOT NULL | Recipient |
| type | TEXT | NOT NULL | scan_complete, finding_critical, remediation_proposed, approval_needed, verification_complete, report_ready, mention |
| title | TEXT | NOT NULL | |
| message | TEXT | NOT NULL | |
| reference_type | TEXT | | scan, finding, remediation, report |
| reference_id | UUID | | |
| channels | TEXT[] | DEFAULT '{in_app}' | in_app, email, slack, webhook |
| read_at | TIMESTAMPTZ | | |
| sent_at | TIMESTAMPTZ | | |
| created_at | TIMESTAMPTZ | DEFAULT now() | |

**Indexes**: `idx_notifications_user_id_read` (user_id, read_at), `idx_notifications_ws_id_created`

**RLS**: Users see only their own notifications.

---

## RLS Policy Summary

```sql
-- Example pattern for all workspace-scoped tables:
-- 1. Enable RLS
ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

-- 2. Policy: Members can SELECT
CREATE POLICY "Members can view workspace assets"
  ON assets FOR SELECT
  USING (workspace_id IN (
    SELECT workspace_id FROM workspace_members 
    WHERE user_id = auth.uid() AND joined_at IS NOT NULL
  ));

-- 3. Policy: Admins/Owners can INSERT/UPDATE/DELETE
CREATE POLICY "Admins can manage workspace assets"
  ON assets FOR ALL
  USING (workspace_id IN (
    SELECT workspace_id FROM workspace_members 
    WHERE user_id = auth.uid() 
    AND role IN ('owner', 'admin')
    AND joined_at IS NOT NULL
  ));

-- 4. Audit logs: Only admins/owners
CREATE POLICY "Admins can view audit logs"
  ON audit_logs FOR SELECT
  USING (workspace_id IN (
    SELECT workspace_id FROM workspace_members 
    WHERE user_id = auth.uid() 
    AND role IN ('owner', 'admin')
    AND joined_at IS NOT NULL
  ));
```

---

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

Each stage creates tables with RLS policies, indexes, and triggers for `updated_at`.
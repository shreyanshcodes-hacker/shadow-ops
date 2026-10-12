import { getFirebaseToken } from './auth';
import { useAuthContext } from '@/components/providers/AuthProvider';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = 'v1';

export interface ApiError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

let authContextRefreshToken: (() => Promise<string | null>) | null = null;

export function setAuthContextRefreshToken(fn: () => Promise<string | null>) {
  authContextRefreshToken = fn;
}

class ApiClient {
  private baseUrl: string;
  private defaultHeaders: HeadersInit;
  private refreshing = false;
  private refreshPromise: Promise<string | null> | null = null;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
    this.defaultHeaders = {
      'Content-Type': 'application/json',
    };
  }

  private async getAuthHeaders(): Promise<HeadersInit> {
    const token = await getFirebaseToken();
    return {
      ...this.defaultHeaders,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    };
  }

  private async refreshTokenIfNeeded(): Promise<string | null> {
    if (this.refreshing && this.refreshPromise) {
      return this.refreshPromise;
    }

    this.refreshing = true;
    this.refreshPromise = (async () => {
      try {
        if (authContextRefreshToken) {
          return await authContextRefreshToken();
        }
        return await getFirebaseToken(true);
      } finally {
        this.refreshing = false;
        this.refreshPromise = null;
      }
    })();

    return this.refreshPromise;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {},
    retryCount = 0
  ): Promise<T> {
    const headers = await this.getAuthHeaders();
    const url = `${this.baseUrl}/api/${API_VERSION}${endpoint}`;

    const response = await fetch(url, {
      ...options,
      headers: {
        ...headers,
        ...options.headers,
      },
      credentials: 'include',
    });

    if (response.status === 401 && retryCount === 0) {
      await this.refreshTokenIfNeeded();
      return this.request<T>(endpoint, options, retryCount + 1);
    }

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`;
      let errorCode = 'UNKNOWN_ERROR';
      let errorDetails: Record<string, unknown> | undefined;

      try {
        const errorData: ApiError = await response.json();
        errorMessage = errorData.error?.message || errorMessage;
        errorCode = errorData.error?.code || errorCode;
        errorDetails = errorData.error?.details;
      } catch {
        // Ignore parsing errors
      }

      throw new ApiErrorClass(response.status, errorMessage, errorCode, errorDetails);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }

  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }

  // Health
  async health(): Promise<{ status: string; timestamp: string }> {
    return this.get('/health');
  }

  async healthDatabase(): Promise<{ status: string; database: string }> {
    return this.get('/health/database');
  }

  // Auth
  async getMe(): Promise<UserProfile> {
    return this.get('/me');
  }

  // Workspaces
  async listWorkspaces(): Promise<Workspace[]> {
    return this.get('/workspaces');
  }

  async createWorkspace(data: CreateWorkspaceRequest): Promise<Workspace> {
    return this.post('/workspaces', data);
  }

  async getWorkspace(id: string): Promise<Workspace> {
    return this.get(`/workspaces/${id}`);
  }

  async updateWorkspace(id: string, data: UpdateWorkspaceRequest): Promise<Workspace> {
    return this.patch(`/workspaces/${id}`, data);
  }

  async deleteWorkspace(id: string): Promise<void> {
    return this.delete(`/workspaces/${id}`);
  }

  async listWorkspaceMembers(workspaceId: string): Promise<WorkspaceMember[]> {
    return this.get(`/workspaces/${workspaceId}/members`);
  }

  async inviteMember(workspaceId: string, data: InviteMemberRequest): Promise<WorkspaceMember> {
    return this.post(`/workspaces/${workspaceId}/members`, data);
  }

  async updateMemberRole(workspaceId: string, userId: string, role: string): Promise<WorkspaceMember> {
    return this.patch(`/workspaces/${workspaceId}/members/${userId}`, { role });
  }

  async removeMember(workspaceId: string, userId: string): Promise<void> {
    return this.delete(`/workspaces/${workspaceId}/members/${userId}`);
  }

  // Assets
  async listAssets(workspaceId: string): Promise<Asset[]> {
    return this.get(`/workspaces/${workspaceId}/assets`);
  }

  async createAsset(workspaceId: string, data: CreateAssetRequest): Promise<Asset> {
    return this.post(`/workspaces/${workspaceId}/assets`, data);
  }

  async getAsset(assetId: string): Promise<Asset> {
    return this.get(`/assets/${assetId}`);
  }

  async updateAsset(assetId: string, data: UpdateAssetRequest): Promise<Asset> {
    return this.patch(`/assets/${assetId}`, data);
  }

  async deleteAsset(assetId: string): Promise<void> {
    return this.delete(`/assets/${assetId}`);
  }

  async createAuthorization(assetId: string, data: CreateAuthorizationRequest): Promise<Authorization> {
    return this.post(`/assets/${assetId}/authorization`, data);
  }

  async getAuthorization(assetId: string): Promise<Authorization> {
    return this.get(`/assets/${assetId}/authorization`);
  }

  // Scans
  async listScans(workspaceId: string, params?: Record<string, string>): Promise<ScanListResponse[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/scans${query}`);
  }

  async createScan(workspaceId: string, data: CreateScanRequest): Promise<Scan> {
    return this.post(`/scans`, { ...data, workspace_id: workspaceId });
  }

  async getScan(scanId: string): Promise<Scan> {
    return this.get(`/scans/${scanId}`);
  }

  async getScanEvents(scanId: string): Promise<ScanEvent[]> {
    return this.get(`/scans/${scanId}/events`);
  }

  async getScanSummary(scanId: string): Promise<ScanSummary> {
    return this.get(`/scans/${scanId}/summary`);
  }

  async cancelScan(scanId: string): Promise<void> {
    return this.post(`/scans/${scanId}/cancel`, {});
  }

  async getAssetScans(assetId: string, params?: Record<string, string>): Promise<ScanListResponse[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/scans/assets/${assetId}/scans${query}`);
  }

  // Findings
  async listFindings(workspaceId: string, params?: Record<string, string>): Promise<Finding[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/workspaces/${workspaceId}/findings${query}`);
  }

  async getFinding(workspaceId: string, findingId: string): Promise<Finding> {
    return this.get(`/workspaces/${workspaceId}/findings/${findingId}`);
  }

  async updateFinding(workspaceId: string, findingId: string, data: UpdateFindingRequest): Promise<Finding> {
    return this.patch(`/workspaces/${workspaceId}/findings/${findingId}`, data);
  }

  async listFindingEvidence(findingId: string): Promise<any[]> {
    return this.get(`/findings/${findingId}/evidence`);
  }

  // AI Analysis
  async startFindingAnalysis(scanId: string, findingId: string): Promise<AiRun> {
    return this.post(`/ai/scans/${scanId}/analyze-finding`, { finding_id: findingId });
  }

  async startFindingAnalysisDirect(findingId: string): Promise<AiRun> {
    return this.post(`/ai/findings/${findingId}/ai-analysis`, {});
  }

  async getScanAiRuns(scanId: string): Promise<AiRun[]> {
    return this.get(`/ai/scans/${scanId}/ai-runs`);
  }

  async getAiRun(runId: string): Promise<AiRun> {
    return this.get(`/ai/ai-runs/${runId}`);
  }

  async getFindingAiAnalysis(findingId: string): Promise<FindingAiAnalysis> {
    return this.get(`/ai/findings/${findingId}/ai-analysis`);
  }

  async getFindingAiAnalyses(findingId: string): Promise<FindingAiAnalysis[]> {
    return this.get(`/ai/findings/${findingId}/ai-analyses`);
  }

  async getAiAnalysisById(analysisId: string): Promise<FindingAiAnalysis> {
    return this.get(`/ai/ai-analyses/${analysisId}`);
  }

  async getAiProviderStatus(): Promise<AiProviderStatus[]> {
    return this.get(`/ai/providers/status`);
  }

  async getScanAiAnalysisStatus(scanId: string): Promise<AiAnalysisStatus[]> {
    return this.get(`/ai/scans/${scanId}/ai-analysis-status`);
  }

  // Attack Paths & Correlation
  async listFindingRelationships(findingId: string): Promise<FindingRelationship[]> {
    return this.get(`/attack-paths/findings/${findingId}/relationships`);
  }

  async confirmRelationship(relationshipId: string): Promise<FindingRelationship> {
    return this.post(`/attack-paths/relationships/${relationshipId}/confirm`, {});
  }

  async dismissRelationship(relationshipId: string): Promise<FindingRelationship> {
    return this.post(`/attack-paths/relationships/${relationshipId}/dismiss`, {});
  }

  async listAttackPaths(workspaceId: string, params?: Record<string, string>): Promise<AttackPath[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/attack-paths${query}`);
  }

  async createAttackPath(workspaceId: string, data: CreateAttackPathRequest): Promise<AttackPath> {
    return this.post(`/attack-paths`, { ...data, workspace_id: workspaceId });
  }

  async getAttackPath(attackPathId: string): Promise<AttackPath> {
    return this.get(`/attack-paths/${attackPathId}`);
  }

  async updateAttackPath(attackPathId: string, data: UpdateAttackPathRequest): Promise<AttackPath> {
    return this.patch(`/attack-paths/${attackPathId}`, data);
  }

  async getAttackPathNodes(attackPathId: string): Promise<AttackPathNode[]> {
    return this.get(`/attack-paths/${attackPathId}/nodes`);
  }

  async getAttackPathEdges(attackPathId: string): Promise<AttackPathEdge[]> {
    return this.get(`/attack-paths/${attackPathId}/edges`);
  }

  async recalculateRisk(attackPathId: string): Promise<RiskCalculationResult> {
    return this.post(`/attack-paths/${attackPathId}/recalculate-risk`, {});
  }

  async getRiskHistory(attackPathId: string): Promise<RiskSnapshot[]> {
    return this.get(`/attack-paths/${attackPathId}/risk-history`);
  }

  async correlateFinding(findingId: string): Promise<FindingRelationship[]> {
    return this.post(`/attack-paths/correlate/${findingId}`, {});
  }

  async correlateWorkspace(workspaceId: string): Promise<FindingRelationship[]> {
    return this.post(`/attack-paths/correlate/workspace/${workspaceId}`, {});
  }

  async aiCorrelateFindings(findingAId: string, findingBId: string): Promise<FindingRelationship> {
    return this.post(`/attack-paths/correlate/ai/${findingAId}/${findingBId}`, {});
  }

  async generateAttackPaths(assetId: string, params?: Record<string, string>): Promise<AttackPath[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.post(`/attack-paths/generate/${assetId}${query}`, {});
  }

  async getFindingAttackPaths(findingId: string): Promise<AttackPath[]> {
    return this.get(`/attack-paths/findings/${findingId}/attack-paths`);
  }

  // Security Team
  async createSecurityTeamRun(data: { asset_id: string; scan_id: string; analysis_mode?: string }): Promise<SecurityTeamRunResponse> {
    return this.post('/security-team/runs', data);
  }

  async listSecurityTeamRuns(workspaceId: string, params?: Record<string, string>): Promise<SecurityTeamRunListResponse[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/security-team/runs${query}`);
  }

  async getSecurityTeamRun(runId: string): Promise<SecurityTeamRunResponse> {
    return this.get(`/security-team/runs/${runId}`);
  }

  async getSecurityTeamRunAgents(runId: string): Promise<SecurityTeamAgentRunResponse[]> {
    return this.get(`/security-team/runs/${runId}/agents`);
  }

  async getSecurityTeamAssessment(runId: string): Promise<SecurityTeamAssessmentResponse> {
    return this.get(`/security-team/runs/${runId}/assessment`);
  }

  async submitSecurityTeamReview(runId: string, notes?: string): Promise<SecurityTeamReviewResponse> {
    return this.post(`/security-team/runs/${runId}/review`, { notes });
  }

  async cancelSecurityTeamRun(runId: string): Promise<void> {
    return this.post(`/security-team/runs/${runId}/cancel`, {});
  }

  // Remediation
  async listRemediations(workspaceId: string, params?: Record<string, string>): Promise<RemediationProposal[]> {
    const query = params ? `?${new URLSearchParams(params).toString()}` : '';
    return this.get(`/remediations${query}`);
  }

  async generateRemediation(findingId: string): Promise<RemediationProposal> {
    return this.post(`/remediations/findings/${findingId}/remediations`, {});
  }

  async getRemediation(proposalId: string): Promise<RemediationDetailResponse> {
    return this.get(`/remediations/${proposalId}`);
  }

  async validateRemediation(proposalId: string): Promise<ValidationRun[]> {
    return this.post(`/remediations/${proposalId}/validate`, {});
  }

  async getValidations(proposalId: string): Promise<ValidationRun[]> {
    return this.get(`/remediations/${proposalId}/validations`);
  }

  async approveRemediation(proposalId: string, data: ApproveRemediationRequest): Promise<RemediationApproval> {
    return this.post(`/remediations/${proposalId}/approve`, data);
  }

  async rejectRemediation(proposalId: string, data: RejectRemediationRequest): Promise<RemediationApproval> {
    return this.post(`/remediations/${proposalId}/reject`, data);
  }

  async getApprovals(proposalId: string): Promise<RemediationApproval[]> {
    return this.get(`/remediations/${proposalId}/approvals`);
  }

  async applyRemediation(proposalId: string, data: ApplyRemediationRequest): Promise<RemediationApplication> {
    return this.post(`/remediations/${proposalId}/apply`, data);
  }

  async getApplications(proposalId: string): Promise<RemediationApplication[]> {
    return this.get(`/remediations/${proposalId}/applications`);
  }

  async rollbackRemediation(proposalId: string, data: RollbackRemediationRequest): Promise<RemediationRollback> {
    return this.post(`/remediations/${proposalId}/rollback`, data);
  }

  async getRollbacks(proposalId: string): Promise<RemediationRollback[]> {
    return this.get(`/remediations/${proposalId}/rollbacks`);
  }

  async getRollbackStatus(applicationId: string): Promise<RollbackStatusResponse> {
    return this.get(`/remediations/applications/${applicationId}/rollback-status`);
  }

  async requestVerification(applicationId: string): Promise<{ message: string; handoff_id: string }> {
    return this.post(`/remediations/applications/${applicationId}/request-verification`, {});
  }

  // Reports
  async listReports(workspaceId: string): Promise<Report[]> {
    return this.get(`/workspaces/${workspaceId}/reports`);
  }

  async generateReport(workspaceId: string, data: GenerateReportRequest): Promise<Report> {
    return this.post(`/workspaces/${workspaceId}/reports`, data);
  }
}

export const api = new ApiClient();

export class ApiErrorClass extends Error {
  constructor(
    public status: number,
    message: string,
    public code: string = 'UNKNOWN_ERROR',
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'ApiError';
  }

  isUnauthorized(): boolean {
    return this.status === 401;
  }

  isForbidden(): boolean {
    return this.status === 403;
  }

  isNotFound(): boolean {
    return this.status === 404;
  }

  isValidationError(): boolean {
    return this.status === 422;
  }

  isServerError(): boolean {
    return this.status >= 500;
  }

  isNetworkError(): boolean {
    return this.status === 0;
  }
}

// Types
export interface UserProfile {
  id: string;
  firebase_uid: string;
  email: string;
  display_name: string | null;
  avatar_url: string | null;
  role: string;
  created_at: string;
  updated_at: string;
  last_login_at: string | null;
}

export interface Workspace {
  id: string;
  name: string;
  slug: string;
  owner_id: string;
  plan: string;
  settings: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface CreateWorkspaceRequest {
  name: string;
  slug?: string;
}

export interface UpdateWorkspaceRequest {
  name?: string;
  settings?: Record<string, unknown>;
}

export interface WorkspaceMember {
  id: string;
  workspace_id: string;
  user_id: string;
  role: 'owner' | 'admin' | 'member' | 'viewer';
  invited_by: string | null;
  invited_at: string;
  joined_at: string | null;
  created_at: string;
  user?: UserProfile;
}

export interface InviteMemberRequest {
  email: string;
  role: 'admin' | 'member' | 'viewer';
}

export interface Asset {
  id: string;
  workspace_id: string;
  name: string;
  type: 'repository' | 'api' | 'infrastructure' | 'application' | 'container';
  subtype?: string;
  connection_config: Record<string, unknown>;
  credentials_ref?: string;
  criticality: 'low' | 'medium' | 'high' | 'critical';
  status: 'active' | 'archived' | 'error';
  last_scanned_at: string | null;
  scan_frequency: string;
  tags: string[];
  created_by: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface CreateAssetRequest {
  name: string;
  type: Asset['type'];
  subtype?: string;
  connection_config: Record<string, unknown>;
  credentials_ref?: string;
  criticality?: Asset['criticality'];
  tags?: string[];
}

export interface UpdateAssetRequest {
  name?: string;
  connection_config?: Record<string, unknown>;
  credentials_ref?: string;
  criticality?: Asset['criticality'];
  status?: Asset['status'];
  scan_frequency?: string;
  tags?: string[];
}

export interface Authorization {
  id: string;
  asset_id: string;
  workspace_id: string;
  authorization_type: 'ownership' | 'written_permission' | 'bug_bounty' | 'internal';
  evidence_files: string[];
  evidence_urls: string[];
  authorized_by: string | null;
  authorized_at: string;
  expires_at: string | null;
  status: 'pending' | 'verified' | 'rejected' | 'expired';
  verified_by: string | null;
  verified_at: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CreateAuthorizationRequest {
  authorization_type: Authorization['authorization_type'];
  evidence_files?: string[];
  evidence_urls?: string[];
  authorized_by?: string;
  expires_at?: string;
  notes?: string;
}

export interface Scan {
  id: string;
  workspace_id: string;
  asset_id: string;
  scan_type: 'full' | 'recon' | 'code' | 'dependency' | 'targeted';
  scan_profile: 'QUICK' | 'STANDARD' | 'CODE_SECURITY';
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | 'partial';
  triggered_by: string;
  triggered_at: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  cancelled_at: string | null;
  authorization_confirmed_at: string | null;
  duration_ms: number | null;
  phases_completed: string[];
  current_phase: string | null;
  progress_percent: number;
  error_code: string | null;
  error_message: string | null;
  scan_config: Record<string, unknown>;
  summary: Record<string, unknown>;
  target_type: string | null;
  target_reference: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScanListResponse {
  id: string;
  workspace_id: string;
  asset_id: string;
  scan_type: Scan['scan_type'];
  scan_profile: Scan['scan_profile'];
  status: Scan['status'];
  triggered_by: string;
  triggered_at: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
  progress_percent: number;
  error_message: string | null;
  created_at: string;
}

export interface ScanEvent {
  id: number;
  scan_id: string;
  workspace_id: string;
  phase: string;
  event_type: string;
  message: string;
  data: Record<string, unknown>;
  created_at: string;
}

export interface ScanSummary {
  scan_id: string;
  status: string;
  summary: Record<string, unknown>;
  findings: {
    total_findings: number;
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
}

export interface CreateScanRequest {
  asset_id: string;
  scan_type: Scan['scan_type'];
  scan_profile?: Scan['scan_profile'];
  scan_config?: Record<string, unknown>;
}

export interface Finding {
  id: string;
  workspace_id: string;
  scan_id: string;
  asset_id: string;
  source: 'semgrep' | 'recon' | 'dependency' | 'ai_analysis' | 'manual';
  source_rule_id: string | null;
  title: string;
  description: string;
  severity: 'critical' | 'high' | 'medium' | 'low' | 'info';
  confidence: 'low' | 'medium' | 'high';
  cwe_ids: string[];
  cve_ids: string[];
  owasp_categories: string[];
  location: Record<string, unknown> | null;
  code_snippet: string | null;
  remediation_guidance: string | null;
  status: 'open' | 'triaged' | 'in_progress' | 'fixed' | 'false_positive' | 'wont_fix' | 'risk_accepted';
  triaged_by: string | null;
  triaged_at: string | null;
  risk_score: number | null;
  risk_factors: Record<string, unknown>;
  first_seen_at: string;
  last_seen_at: string;
  fixed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UpdateFindingRequest {
  status?: Finding['status'];
  triaged_by?: string;
}

export interface RemediationProposal {
  id: string;
  workspace_id: string;
  finding_id: string;
  proposed_by: string;
  model_used: string | null;
  title: string;
  description: string;
  fix_type: 'code_change' | 'config_change' | 'dependency_update' | 'infrastructure_change' | 'waf_rule' | 'network_policy';
  code_changes: Record<string, unknown> | null;
  config_changes: Record<string, unknown> | null;
  commands: string[];
  prerequisites: string[];
  risk_level: 'low' | 'medium' | 'high';
  confidence: 'low' | 'medium' | 'high';
  estimated_effort: string | null;
  status: 'proposed' | 'approved' | 'rejected' | 'applied' | 'superseded';
  created_at: string;
  updated_at: string;
}

export interface ApproveRemediationRequest {
  justification?: string;
  conditions?: string[];
}

export interface RemediationApproval {
  id: string;
  proposal_id: string;
  workspace_id: string;
  approved_by: string;
  decision: 'approved' | 'rejected';
  justification: string | null;
  conditions: string[];
  approved_at: string;
  expires_at: string | null;
}

export interface Report {
  id: string;
  workspace_id: string;
  scan_id: string | null;
  report_type: 'executive' | 'technical' | 'scan' | 'compliance' | 'custom';
  title: string;
  description: string | null;
  format: 'pdf' | 'html' | 'json' | 'markdown';
  status: 'generating' | 'ready' | 'failed';
  storage_object_id: string | null;
  generated_by: string;
  period_start: string | null;
  period_end: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  completed_at: string | null;
}

export interface GenerateReportRequest {
  report_type: Report['report_type'];
  title: string;
  scan_id?: string;
  period_start?: string;
  period_end?: string;
  format?: Report['format'];
}

// AI Types
export interface AiProviderType {
  provider: 'gemini' | 'grok';
  configured: boolean;
  model: string | null;
}

export interface AiProviderStatus {
  provider: 'gemini' | 'grok';
  configured: boolean;
  model: string | null;
}

export interface AiRun {
  id: string;
  workspace_id: string;
  scan_id: string;
  finding_id: string | null;
  requested_by: string;
  provider: 'gemini' | 'grok';
  model: string;
  operation: 'finding_analysis' | 'scan_analysis';
  status: 'queued' | 'running' | 'completed' | 'failed';
  prompt_version: string;
  input_hash: string;
  started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost_usd: number | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface SupportingEvidenceRef {
  evidence_id: string;
  reason: string;
  certainty: 'observed' | 'inferred' | 'uncertain';
}

export interface FindingAiAnalysis {
  id: string;
  workspace_id: string;
  finding_id: string;
  ai_run_id: string;
  summary: string;
  vulnerability_type: string;
  severity_assessment: string;
  confidence: number;
  exploitability_assessment: string;
  impact_assessment: string;
  affected_component: string;
  attack_preconditions: string;
  evidence_interpretation: string;
  reasoning: string;
  recommended_next_steps: string[];
  uncertainty: string;
  supporting_evidence: SupportingEvidenceRef[];
  model: string;
  provider: 'gemini' | 'grok';
  prompt_version: string;
  created_at: string;
  updated_at: string;
}

export interface AiAnalysisStatus {
  finding_id: string;
  has_analysis: boolean;
  ai_run_id: string | null;
  status: string | null;
  error: string | null;
}

// Attack Path & Correlation Types
export type RelationshipType = 
  | 'depends_on' 
  | 'enables' 
  | 'exposes' 
  | 'leads_to' 
  | 'shares_component' 
  | 'shares_entry_point' 
  | 'shares_data_flow' 
  | 'amplifies';

export type RelationshipSource = 
  | 'deterministic' 
  | 'ai_suggested' 
  | 'human_confirmed';

export type AttackPathStatus = 'draft' | 'active' | 'dismissed' | 'resolved';

export type AttackPathNodeType = 'entry' | 'finding' | 'boundary' | 'impact';

export type RiskBand = 'informational' | 'low' | 'medium' | 'high' | 'critical';

export interface FindingRelationship {
  id: string;
  workspace_id: string;
  source_finding_id: string;
  target_finding_id: string;
  relationship_type: RelationshipType;
  confidence: number;
  source: RelationshipSource;
  rationale: string;
  evidence_reference: string | null;
  created_at: string;
  updated_at: string;
  source_finding?: Finding;
  target_finding?: Finding;
}

export interface CreateAttackPathRequest {
  asset_id: string;
  title: string;
  description?: string;
  status?: AttackPathStatus;
  confidence?: number;
  severity?: string;
}

export interface UpdateAttackPathRequest {
  title?: string;
  description?: string;
  status?: AttackPathStatus;
  confidence?: number;
  severity?: string;
}

export interface AttackPathNode {
  id: string;
  attack_path_id: string;
  finding_id: string | null;
  sequence: number;
  node_type: AttackPathNodeType;
  rationale: string;
  created_at: string;
  updated_at: string;
  finding?: Finding;
}

export interface AttackPathEdge {
  id: string;
  attack_path_id: string;
  source_node_id: string;
  target_node_id: string;
  relationship_type: RelationshipType;
  confidence: number;
  source: RelationshipSource;
  rationale: string;
  created_at: string;
  source_node?: AttackPathNode;
  target_node?: AttackPathNode;
}

export interface AttackPath {
  id: string;
  workspace_id: string;
  asset_id: string;
  title: string;
  description: string;
  status: AttackPathStatus;
  confidence: number;
  severity: string;
  risk_score: number | null;
  risk_band: RiskBand | null;
  risk_model_version: string;
  created_at: string;
  updated_at: string;
  nodes: AttackPathNode[];
  edges: AttackPathEdge[];
  asset?: Asset;
}

export interface AttackPathListItem {
  id: string;
  workspace_id: string;
  asset_id: string;
  title: string;
  status: AttackPathStatus;
  confidence: number;
  severity: string;
  risk_score: number | null;
  risk_band: RiskBand | null;
  node_count: number;
  created_at: string;
  updated_at: string;
}

export interface RiskFactor {
  name: string;
  weight: number;
  value: number;
  contribution: number;
  description: string;
}

export interface RiskCalculationResult {
  score: number;
  risk_band: RiskBand;
  model_version: string;
  factors: RiskFactor[];
  explanation: string;
}

export interface RiskSnapshot {
  id: string;
  workspace_id: string;
  attack_path_id: string;
  score: number;
  risk_band: RiskBand;
  model_version: string;
  factors: Record<string, unknown>;
  calculated_at: string;
}

// Security Team Types
export type SecurityTeamRunStatus = 'queued' | 'running' | 'partial' | 'succeeded' | 'failed' | 'canceled';

export type AgentRunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'blocked' | 'canceled';

export type AgentName = 'recon' | 'vulnerability_analyst' | 'attack_path_analyst' | 'risk_analyst' | 'security_reviewer';

export interface SecurityTeamRunCreateRequest {
  asset_id: string;
  scan_id: string;
  analysis_mode?: string;
}

export interface SecurityTeamRunResponse {
  id: string;
  workspace_id: string;
  asset_id: string;
  scan_id: string;
  status: SecurityTeamRunStatus;
  requested_by: string;
  started_at: string | null;
  completed_at: string | null;
  orchestration_version: string;
  team_summary: Record<string, unknown>;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}

export interface SecurityTeamRunListResponse {
  id: string;
  workspace_id: string;
  asset_id: string;
  scan_id: string;
  status: SecurityTeamRunStatus;
  requested_by: string;
  started_at: string | null;
  completed_at: string | null;
  orchestration_version: string;
  team_summary: Record<string, unknown>;
  confidence: number | null;
  created_at: string;
  updated_at: string;
}

export interface SecurityTeamAgentRunResponse {
  id: string;
  team_run_id: string;
  agent_name: AgentName;
  status: AgentRunStatus;
  input_reference: Record<string, unknown>;
  output: Record<string, unknown>;
  confidence: number | null;
  provider: string | null;
  model: string | null;
  prompt_version: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_code: string | null;
  error_message: string | null;
  attempt: number;
  created_at: string;
}

export interface SecurityTeamAssessmentResponse {
  id: string;
  team_run_id: string;
  workspace_id: string;
  executive_summary: string;
  key_findings: Array<{
    finding_id: string;
    title: string;
    severity: string;
    ai_confidence: number;
    reason: string;
  }>;
  key_attack_paths: Array<{
    attack_path_id: string;
    title: string;
    risk_score: number;
    risk_band: string;
    reason: string;
  }>;
  risk_interpretation: string;
  uncertainties: string[];
  conflicting_assessments: Array<{
    agent_a: string;
    agent_b: string;
    finding_or_path_id: string;
    agent_a_confidence: number;
    agent_b_confidence: number;
    description: string;
  }>;
  recommended_human_actions: string[];
  overall_confidence: number;
  deterministic_risk_score_referenced: number | null;
  human_review_required: boolean;
  created_at: string;
  updated_at: string;
}

export interface SecurityTeamReviewResponse {
  id: string;
  team_run_id: string;
  workspace_id: string;
  reviewed_by: string;
  reviewed_at: string;
  notes: string | null;
  created_at: string;
}

// Remediation Types
export type RemediationStatus = 
  | 'DRAFT' 
  | 'GENERATING' 
  | 'PROPOSED' 
  | 'VALIDATING' 
  | 'VALIDATION_FAILED' 
  | 'AWAITING_APPROVAL' 
  | 'APPROVED' 
  | 'APPLYING' 
  | 'APPLIED' 
  | 'REJECTED' 
  | 'EXPIRED' 
  | 'ROLLED_BACK' 
  | 'FAILED';

export type RemediationFixType = 
  | 'code_change' 
  | 'config_change' 
  | 'dependency_update' 
  | 'infrastructure_change' 
  | 'waf_rule' 
  | 'network_policy' 
  | 'secret_rotation';

export type ValidationStatus = 'PENDING' | 'RUNNING' | 'PASSED' | 'FAILED' | 'BLOCKED' | 'ERROR';
export type ValidationCheckType = 
  | 'patch_integrity' 
  | 'diff_parsing' 
  | 'path_allowlist' 
  | 'syntax_validation' 
  | 'semgrep_rescan' 
  | 'regression_check' 
  | 'existing_tests';

export type ApplicationStatus = 'PENDING' | 'CHECKPOINT_CREATED' | 'PATCH_APPLIED' | 'VERIFIED' | 'FAILED' | 'ROLLED_BACK';
export type RollbackStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED' | 'BLOCKED_DIVERGED';
export type VerificationHandoffStatus = 
  | 'PENDING_VERIFICATION' 
  | 'VERIFICATION_REQUESTED' 
  | 'VERIFIED' 
  | 'VERIFICATION_FAILED' 
  | 'MANUAL_REVIEW_REQUIRED';

export interface AffectedFile {
  file_path: string;
  language?: string;
  change_type: string;
}

export interface SuggestedTest {
  test_type: string;
  description: string;
  command?: string;
}

export interface FileChange {
  file_path: string;
  old_hash?: string;
  new_hash?: string;
  additions: number;
  deletions: number;
}

export interface RemediationProposal {
  id: string;
  workspace_id: string;
  asset_id: string;
  finding_id: string;
  source_scan_id: string;
  proposal_title: string;
  problem_summary: string;
  proposed_solution: string;
  rationale: string;
  affected_files: AffectedFile[];
  patch_reference?: string;
  validation_results: Record<string, unknown>;
  fix_type: RemediationFixType;
  expected_security_benefit?: string;
  compatibility_risks?: string;
  assumptions?: string;
  limitations?: string;
  suggested_tests: SuggestedTest[];
  status: RemediationStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  approved_by?: string;
  approved_at?: string;
  applied_by?: string;
  applied_at?: string;
  failure_reason?: string;
  version: number;
  expires_at?: string;
  finding?: Finding;
  asset?: Asset;
}

export interface RemediationProposalListItem {
  id: string;
  workspace_id: string;
  asset_id: string;
  finding_id: string;
  source_scan_id: string;
  proposal_title: string;
  status: RemediationStatus;
  fix_type: RemediationFixType;
  created_by: string;
  created_at: string;
  approved_at?: string;
  applied_at?: string;
}

export interface PatchVersion {
  id: string;
  proposal_id: string;
  workspace_id: string;
  version: number;
  unified_diff: string;
  file_changes: FileChange[];
  patch_hash: string;
  base_revision?: string;
  created_by: string;
  created_at: string;
  is_current: boolean;
  superseded_by?: string;
}

export interface ValidationRun {
  id: string;
  proposal_id: string;
  patch_version_id: string;
  workspace_id: string;
  status: ValidationStatus;
  check_type: ValidationCheckType;
  command?: string;
  exit_code?: number;
  stdout?: string;
  stderr?: string;
  duration_ms?: number;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface RemediationApproval {
  id: string;
  proposal_id: string;
  patch_version_id: string;
  workspace_id: string;
  approved_by: string;
  decision: 'approved' | 'rejected';
  justification?: string;
  conditions: string[];
  patch_hash: string;
  proposal_version: number;
  validation_snapshot: Record<string, unknown>;
  approved_at: string;
  expires_at?: string;
  approver?: UserProfile;
}

export interface RemediationApplication {
  id: string;
  proposal_id: string;
  patch_version_id: string;
  approval_id: string;
  workspace_id: string;
  asset_id: string;
  status: ApplicationStatus;
  target_revision: string;
  checkpoint_ref?: string;
  applied_by: string;
  applied_at: string;
  completed_at?: string;
  result_diff?: string;
  changed_files: FileChange[];
  validation_results: Record<string, unknown>;
  failure_reason?: string;
  applier?: UserProfile;
}

export interface RemediationRollback {
  id: string;
  proposal_id: string;
  application_id: string;
  workspace_id: string;
  asset_id: string;
  status: RollbackStatus;
  requested_by: string;
  reason: string;
  checkpoint_ref: string;
  verification_diff?: string;
  started_at: string;
  completed_at?: string;
  failure_reason?: string;
  requester?: UserProfile;
}

export interface RemediationVerificationHandoff {
  id: string;
  proposal_id: string;
  application_id: string;
  workspace_id: string;
  finding_id: string;
  asset_id: string;
  patch_hash: string;
  repository_revision: string;
  changed_files: FileChange[];
  validation_results: Record<string, unknown>;
  original_finding_snapshot: Record<string, unknown>;
  applied_at: string;
  applied_by: string;
  verification_requested: boolean;
  verification_requested_at?: string;
  verification_completed_at?: string;
  verification_result?: Record<string, unknown>;
  status: VerificationHandoffStatus;
  finding?: Finding;
  asset?: Asset;
}

export interface RemediationDetailResponse {
  proposal: RemediationProposal;
  patch_versions: PatchVersion[];
  validations: ValidationRun[];
  approvals: RemediationApproval[];
  applications: RemediationApplication[];
  rollbacks: RemediationRollback[];
  verification_handoff?: RemediationVerificationHandoff;
}

export interface ApproveRemediationRequest {
  proposal_id: string;
  patch_version_id: string;
  justification?: string;
  conditions?: string[];
}

export interface RejectRemediationRequest {
  proposal_id: string;
  patch_version_id: string;
  justification: string;
}

export interface ApplyRemediationRequest {
  proposal_id: string;
  patch_version_id: string;
  approval_id: string;
  idempotency_key: string;
}

export interface RollbackRemediationRequest {
  application_id: string;
  reason: string;
}

export interface ValidateRemediationRequest {
  proposal_id: string;
}

export interface RollbackStatusResponse {
  available: boolean;
  reason?: string;
  checkpoint_ref?: string;
  target_revision?: string;
  requires_manual_recovery?: boolean;
}
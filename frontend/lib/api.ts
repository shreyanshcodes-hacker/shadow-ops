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

  // Remediation
  async listRemediations(workspaceId: string): Promise<RemediationProposal[]> {
    return this.get(`/workspaces/${workspaceId}/remediations`);
  }

  async generateRemediation(workspaceId: string, findingId: string): Promise<RemediationProposal> {
    return this.post(`/workspaces/${workspaceId}/findings/${findingId}/remediation`, {});
  }

  async approveRemediation(workspaceId: string, remediationId: string, data: ApproveRemediationRequest): Promise<RemediationApproval> {
    return this.post(`/workspaces/${workspaceId}/remediations/${remediationId}/approve`, data);
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
'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  RemediationDetailResponse,
  RemediationProposal,
  PatchVersion,
  ValidationRun,
  ValidationStatus,
  RemediationApproval,
  RemediationApplication,
  RemediationRollback,
  RemediationVerificationHandoff,
  RemediationStatus,
  ApplicationStatus,
  RollbackStatus,
} from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import Link from 'next/link';
import { formatDate } from '@/lib/utils';

const statusColors: Record<RemediationStatus, string> = {
  DRAFT: 'bg-gray-100 text-gray-800',
  GENERATING: 'bg-blue-100 text-blue-800',
  PROPOSED: 'bg-yellow-100 text-yellow-800',
  VALIDATING: 'bg-blue-100 text-blue-800',
  VALIDATION_FAILED: 'bg-red-100 text-red-800',
  AWAITING_APPROVAL: 'bg-orange-100 text-orange-800',
  APPROVED: 'bg-green-100 text-green-800',
  APPLYING: 'bg-blue-100 text-blue-800',
  APPLIED: 'bg-green-100 text-green-800',
  REJECTED: 'bg-red-100 text-red-800',
  EXPIRED: 'bg-gray-100 text-gray-600',
  ROLLED_BACK: 'bg-purple-100 text-purple-800',
  FAILED: 'bg-red-100 text-red-800',
};

const validationStatusColors: Record<ValidationStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  PASSED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  BLOCKED: 'bg-yellow-100 text-yellow-800',
  ERROR: 'bg-red-100 text-red-800',
};

const applicationStatusColors: Record<ApplicationStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  CHECKPOINT_CREATED: 'bg-blue-100 text-blue-800',
  PATCH_APPLIED: 'bg-yellow-100 text-yellow-800',
  VERIFIED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  ROLLED_BACK: 'bg-purple-100 text-purple-800',
};

const rollbackStatusColors: Record<RollbackStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  IN_PROGRESS: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  BLOCKED_DIVERGED: 'bg-yellow-100 text-yellow-800',
};

export default function RemediationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { currentWorkspace } = useAuthContext();
  const [detail, setDetail] = useState<RemediationDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'patch' | 'validations' | 'approvals' | 'applications' | 'rollbacks' | 'verification'>('overview');
  const [validating, setValidating] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [applying, setApplying] = useState(false);
  const [rollingBack, setRollingBack] = useState(false);
  const [rejectionJustification, setRejectionJustification] = useState('');

  useEffect(() => {
    if (!currentWorkspace || !params.id) return;
    fetchDetail();
  }, [currentWorkspace, params.id]);

  const fetchDetail = async () => {
    if (!currentWorkspace || !params.id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getRemediation(params.id as string);
      setDetail(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load remediation detail');
    } finally {
      setLoading(false);
    }
  };

  const handleValidate = async () => {
    if (!detail) return;
    setValidating(true);
    try {
      await api.validateRemediation(detail.proposal.id);
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Validation failed');
    } finally {
      setValidating(false);
    }
  };

  const handleApprove = async () => {
    if (!detail || !detail.proposal.patch_reference) return;
    setApproving(true);
    try {
      await api.approveRemediation(detail.proposal.id, {
        proposal_id: detail.proposal.id,
        patch_version_id: detail.proposal.patch_reference,
        justification: '',
        conditions: [],
      });
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Approval failed');
    } finally {
      setApproving(false);
    }
  };

  const handleReject = async () => {
    if (!detail || !detail.proposal.patch_reference || !rejectionJustification.trim()) return;
    setRejecting(true);
    try {
      await api.rejectRemediation(detail.proposal.id, {
        proposal_id: detail.proposal.id,
        patch_version_id: detail.proposal.patch_reference,
        justification: rejectionJustification,
      });
      setRejectionJustification('');
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Rejection failed');
    } finally {
      setRejecting(false);
    }
  };

  const handleApply = async () => {
    if (!detail || !detail.approvals.length) return;
    const latestApproval = detail.approvals[0];
    if (latestApproval.decision !== 'approved') return;
    
    setApplying(true);
    try {
      await api.applyRemediation(detail.proposal.id, {
        proposal_id: detail.proposal.id,
        patch_version_id: latestApproval.patch_version_id,
        approval_id: latestApproval.id,
        idempotency_key: `apply-${detail.proposal.id}-${Date.now()}`,
      });
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Application failed');
    } finally {
      setApplying(false);
    }
  };

  const handleRollback = async (applicationId: string) => {
    if (!confirm('Are you sure you want to rollback this application? This will restore the code to the state before the patch was applied.')) return;
    
    setRollingBack(true);
    try {
      await api.rollbackRemediation(detail!.proposal.id, {
        application_id: applicationId,
        reason: 'Manual rollback requested',
      });
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Rollback failed');
    } finally {
      setRollingBack(false);
    }
  };

  const handleRequestVerification = async (applicationId: string) => {
    try {
      await api.requestVerification(applicationId);
      await fetchDetail();
    } catch (err: any) {
      setError(err.message || 'Failed to request verification');
    }
  };

  if (!currentWorkspace) {
    return <div className="p-6 text-center text-gray-500">No workspace selected</div>;
  }

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-2 text-gray-500">Loading remediation detail...</p>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="p-6 text-center">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg max-w-md mx-auto">
          {error}
        </div>
      </div>
    );
  }

  if (!detail) {
    return <div className="p-6 text-center text-gray-500">Remediation not found</div>;
  }

  const { proposal, patch_versions, validations, approvals, applications, rollbacks, verification_handoff } = detail;
  const currentPatch = patch_versions.find(p => p.is_current) || patch_versions[patch_versions.length - 1];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link href="/remediations" className="text-sm text-gray-500 hover:text-gray-700 mb-1 inline-block">
            ← Back to Remediations
          </Link>
          <h1 className="text-2xl font-bold text-gray-900">{proposal.proposal_title}</h1>
          <p className="text-gray-500 mt-1">{proposal.problem_summary}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColors[proposal.status]}`}>
            {proposal.status}
          </span>
          {proposal.fix_type && (
            <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
              {proposal.fix_type.replace('_', ' ')}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg mb-4">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('overview')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'overview' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('patch')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'patch' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Patch ({patch_versions.length})
          </button>
          <button
            onClick={() => setActiveTab('validations')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'validations' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Validations ({validations.length})
          </button>
          <button
            onClick={() => setActiveTab('approvals')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'approvals' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Approvals ({approvals.length})
          </button>
          <button
            onClick={() => setActiveTab('applications')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'applications' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Applications ({applications.length})
          </button>
          <button
            onClick={() => setActiveTab('rollbacks')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'rollbacks' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
          >
            Rollbacks ({rollbacks.length})
          </button>
          {verification_handoff && (
            <button
              onClick={() => setActiveTab('verification')}
              className={`py-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'verification' ? 'border-blue-600 text-blue-600' : 'border-transparent text-gray-500 hover:text-gray-700'}`}
            >
              Verification
            </button>
          )}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Proposal ID</h3>
                <p className="mt-1 font-mono text-sm text-gray-900">{proposal.id}</p>
              </div>
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Finding</h3>
                <p className="mt-1 font-mono text-sm text-gray-900">{proposal.finding_id}</p>
              </div>
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Asset</h3>
                <p className="mt-1 font-mono text-sm text-gray-900">{proposal.asset_id}</p>
              </div>
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Created By</h3>
                <p className="mt-1 font-mono text-sm text-gray-900">{proposal.created_by}</p>
              </div>
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Created At</h3>
                <p className="mt-1 text-sm text-gray-900">{formatDate(proposal.created_at)}</p>
              </div>
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-sm font-medium text-gray-500">Version</h3>
                <p className="mt-1 text-sm text-gray-900">{proposal.version}</p>
              </div>
            </div>

            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Proposed Solution</h3>
              <p className="text-gray-700 whitespace-pre-wrap">{proposal.proposed_solution}</p>
            </div>

            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Rationale</h3>
              <p className="text-gray-700 whitespace-pre-wrap">{proposal.rationale}</p>
            </div>

            {proposal.expected_security_benefit && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Expected Security Benefit</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{proposal.expected_security_benefit}</p>
              </div>
            )}

            {proposal.compatibility_risks && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Compatibility Risks</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{proposal.compatibility_risks}</p>
              </div>
            )}

            {proposal.assumptions && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Assumptions</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{proposal.assumptions}</p>
              </div>
            )}

            {proposal.limitations && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Limitations</h3>
                <p className="text-gray-700 whitespace-pre-wrap">{proposal.limitations}</p>
              </div>
            )}

            {proposal.suggested_tests.length > 0 && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Suggested Tests</h3>
                <ul className="list-disc list-inside space-y-2 text-gray-700">
                  {proposal.suggested_tests.map((test, i) => (
                    <li key={i}>
                      <strong>{test.test_type}:</strong> {test.description}
                      {test.command && <code className="ml-2 text-sm bg-gray-100 px-1 rounded">{test.command}</code>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {proposal.affected_files.length > 0 && (
              <div className="bg-white p-6 rounded-lg border border-gray-200">
                <h3 className="text-lg font-medium text-gray-900 mb-4">Affected Files</h3>
                <ul className="space-y-2">
                  {proposal.affected_files.map((file, i) => (
                    <li key={i} className="flex items-center gap-2 text-sm">
                      <code className="bg-gray-100 px-2 py-1 rounded font-mono">{file.file_path}</code>
                      <span className="text-gray-500">({file.change_type})</span>
                      {file.language && <span className="text-gray-400 text-xs">{file.language}</span>}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Actions */}
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Actions</h3>
              <div className="flex flex-wrap gap-3">
                {proposal.status === 'PROPOSED' && (
                  <button
                    onClick={handleValidate}
                    disabled={validating}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {validating ? 'Validating...' : 'Run Validation'}
                  </button>
                )}
                {proposal.status === 'AWAITING_APPROVAL' && (
                  <>
                    <button
                      onClick={handleApprove}
                      disabled={approving}
                      className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                    >
                      {approving ? 'Approving...' : 'Approve'}
                    </button>
                    <button
                      onClick={() => setRejecting(true)}
                      className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
                    >
                      Reject
                    </button>
                  </>
                )}
                {proposal.status === 'APPROVED' && applications.length === 0 && (
                  <button
                    onClick={handleApply}
                    disabled={applying}
                    className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                  >
                    {applying ? 'Applying...' : 'Apply Patch'}
                  </button>
                )}
                {applications.some(a => a.status === 'VERIFIED') && (
                  <button
                    onClick={() => handleRequestVerification(applications.find(a => a.status === 'VERIFIED')!.id)}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                  >
                    Request Verification
                  </button>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Patch Tab */}
        {activeTab === 'patch' && (
          <div className="space-y-6">
            {patch_versions.map((patch, index) => (
              <div key={patch.id} className="bg-white p-6 rounded-lg border border-gray-200">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">Patch Version {patch.version}</h3>
                    <p className="text-sm text-gray-500">Hash: {patch.patch_hash.slice(0, 16)}...</p>
                  </div>
                  {patch.is_current && (
                    <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      Current
                    </span>
                  )}
                </div>
                <div className="bg-gray-900 text-green-400 p-4 rounded font-mono text-sm overflow-x-auto max-h-96">
                  <pre>{patch.unified_diff}</pre>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Validations Tab */}
        {activeTab === 'validations' && (
          <div className="space-y-4">
            {validations.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No validations run yet. Click "Run Validation" on the Overview tab.</div>
            ) : (
              validations.map(validation => (
                <div key={validation.id} className="bg-white p-6 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">{validation.check_type.replace('_', ' ')}</h3>
                      <p className="text-sm text-gray-500">Duration: {validation.duration_ms}ms</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${validationStatusColors[validation.status]}`}>
                      {validation.status}
                    </span>
                  </div>
                  {validation.error_message && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                      {validation.error_message}
                    </div>
                  )}
                  {validation.metadata && Object.keys(validation.metadata).length > 0 && (
                    <details className="mt-3">
                      <summary className="text-sm font-medium text-gray-700 cursor-pointer">Metadata</summary>
                      <pre className="mt-2 text-xs bg-gray-100 p-3 rounded overflow-x-auto">{JSON.stringify(validation.metadata, null, 2)}</pre>
                    </details>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Approvals Tab */}
        {activeTab === 'approvals' && (
          <div className="space-y-4">
            {approvals.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No approvals yet.</div>
            ) : (
              approvals.map(approval => (
                <div key={approval.id} className="bg-white p-6 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900 capitalize">{approval.decision}</h3>
                      <p className="text-sm text-gray-500">By: {approval.approved_by} at {formatDate(approval.approved_at)}</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${approval.decision === 'approved' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {approval.decision}
                    </span>
                  </div>
                  {approval.justification && (
                    <div className="mt-3">
                      <p className="text-sm font-medium text-gray-700">Justification:</p>
                      <p className="text-gray-600 whitespace-pre-wrap">{approval.justification}</p>
                    </div>
                  )}
                  {approval.conditions.length > 0 && (
                    <div className="mt-3">
                      <p className="text-sm font-medium text-gray-700">Conditions:</p>
                      <ul className="list-disc list-inside text-gray-600 mt-1">
                        {approval.conditions.map((c, i) => <li key={i}>{c}</li>)}
                      </ul>
                    </div>
                  )}
                  <div className="mt-3 text-sm text-gray-500">
                    Patch hash at approval: <code className="font-mono">{approval.patch_hash.slice(0, 32)}...</code>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Applications Tab */}
        {activeTab === 'applications' && (
          <div className="space-y-4">
            {applications.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No applications yet.</div>
            ) : (
              applications.map(application => (
                <div key={application.id} className="bg-white p-6 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">Application</h3>
                      <p className="text-sm text-gray-500">By: {application.applied_by} at {formatDate(application.applied_at)}</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${applicationStatusColors[application.status]}`}>
                      {application.status}
                    </span>
                  </div>
                  <div className="mt-3 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-gray-500">Target Revision</p>
                      <p className="font-mono">{application.target_revision.slice(0, 16)}...</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Checkpoint</p>
                      <p className="font-mono">{application.checkpoint_ref || 'N/A'}</p>
                    </div>
                    <div>
                      <p className="text-gray-500">Files Changed</p>
                      <p>{application.changed_files.length}</p>
                    </div>
                  </div>
                  {application.result_diff && (
                    <details className="mt-3">
                      <summary className="text-sm font-medium text-gray-700 cursor-pointer">Result Diff</summary>
                      <pre className="mt-2 text-xs bg-gray-900 text-green-400 p-3 rounded overflow-x-auto max-h-96">{application.result_diff}</pre>
                    </details>
                  )}
                  {application.failure_reason && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                      Failure: {application.failure_reason}
                    </div>
                  )}
                  {application.status === 'VERIFIED' && (
                    <div className="mt-4 flex gap-2">
                      <button
                        onClick={() => handleRollback(application.id)}
                        disabled={rollingBack}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
                      >
                        {rollingBack ? 'Rolling back...' : 'Rollback'}
                      </button>
                      <button
                        onClick={() => handleRequestVerification(application.id)}
                        className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                      >
                        Request Verification
                      </button>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Rollbacks Tab */}
        {activeTab === 'rollbacks' && (
          <div className="space-y-4">
            {rollbacks.length === 0 ? (
              <div className="text-center py-8 text-gray-500">No rollbacks performed.</div>
            ) : (
              rollbacks.map(rollback => (
                <div key={rollback.id} className="bg-white p-6 rounded-lg border border-gray-200">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="text-lg font-medium text-gray-900">Rollback</h3>
                      <p className="text-sm text-gray-500">By: {rollback.requested_by} at {formatDate(rollback.started_at)}</p>
                    </div>
                    <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${rollbackStatusColors[rollback.status]}`}>
                      {rollback.status}
                    </span>
                  </div>
                  <div className="mt-3">
                    <p className="text-sm font-medium text-gray-700">Reason:</p>
                    <p className="text-gray-600">{rollback.reason}</p>
                  </div>
                  {rollback.verification_diff && (
                    <details className="mt-3">
                      <summary className="text-sm font-medium text-gray-700 cursor-pointer">Verification Diff</summary>
                      <pre className="mt-2 text-xs bg-gray-900 text-green-400 p-3 rounded overflow-x-auto max-h-96">{rollback.verification_diff}</pre>
                    </details>
                  )}
                  {rollback.failure_reason && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
                      Failure: {rollback.failure_reason}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}

        {/* Verification Tab */}
        {activeTab === 'verification' && verification_handoff && (
          <div className="space-y-6">
            <div className="bg-white p-6 rounded-lg border border-gray-200">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-medium text-gray-900">Verification Handoff</h3>
                  <p className="text-sm text-gray-500">Status: {verification_handoff.status}</p>
                </div>
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
                  {verification_handoff.status}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-gray-500">Applied At</p>
                  <p>{formatDate(verification_handoff.applied_at)}</p>
                </div>
                <div>
                  <p className="text-gray-500">Applied By</p>
                  <p>{verification_handoff.applied_by}</p>
                </div>
                <div>
                  <p className="text-gray-500">Repository Revision</p>
                  <p className="font-mono">{verification_handoff.repository_revision.slice(0, 16)}...</p>
                </div>
              </div>
              {verification_handoff.verification_requested && (
                <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded text-green-700">
                  Verification requested at {verification_handoff.verification_requested_at ? formatDate(verification_handoff.verification_requested_at) : 'unknown'}
                </div>
              )}
              {verification_handoff.verification_completed_at && (
                <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded text-blue-700">
                  Verification completed at {formatDate(verification_handoff.verification_completed_at)}
                  {verification_handoff.verification_result && (
                    <pre className="mt-2 text-xs bg-white p-2 rounded">{JSON.stringify(verification_handoff.verification_result, null, 2)}</pre>
                  )}
                </div>
              )}
              {!verification_handoff.verification_requested && (
                <button
                  onClick={() => handleRequestVerification(applications[0]?.id || '')}
                  className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
                >
                  Request Verification
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function formatDate(dateString: string): string {
  if (!dateString) return 'N/A';
  return new Date(dateString).toLocaleString();
}
'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  VerificationDetailResponse,
  VerificationJob,
  VerificationBaseline,
  VerificationCheck,
  EvidenceComparison,
  VerificationReview,
  VerificationPolicy,
  VerificationStatus,
  VerificationOutcome,
  CheckStatus,
  CheckType,
  ComparisonCategory,
  ReviewDecision,
} from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';

const statusColors: Record<VerificationStatus, string> = {
  QUEUED: 'bg-gray-100 text-gray-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  BASELINE_CHECK: 'bg-blue-100 text-blue-800',
  RESCANNING: 'bg-blue-100 text-blue-800',
  REGRESSION_CHECK: 'bg-blue-100 text-blue-800',
  COMPARING_EVIDENCE: 'bg-blue-100 text-blue-800',
  PASSED_PENDING_REVIEW: 'bg-green-100 text-green-800',
  VERIFIED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  INCONCLUSIVE: 'bg-yellow-100 text-yellow-800',
  BLOCKED: 'bg-orange-100 text-orange-800',
  CANCELED: 'bg-gray-100 text-gray-600',
};

const outcomeColors: Record<VerificationOutcome, string> = {
  VERIFIED_CANDIDATE: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  INCONCLUSIVE: 'bg-yellow-100 text-yellow-800',
  BLOCKED: 'bg-orange-100 text-orange-800',
};

const checkStatusColors: Record<CheckStatus, string> = {
  PENDING: 'bg-gray-100 text-gray-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  PASSED: 'bg-green-100 text-green-800',
  FAILED: 'bg-red-100 text-red-800',
  SKIPPED: 'bg-yellow-100 text-yellow-800',
  BLOCKED: 'bg-orange-100 text-orange-800',
  ERROR: 'bg-red-100 text-red-800',
};

const categoryColors: Record<ComparisonCategory, string> = {
  STILL_PRESENT: 'bg-red-100 text-red-800',
  NO_LONGER_DETECTED: 'bg-green-100 text-green-800',
  MODIFIED_OR_MOVED: 'bg-yellow-100 text-yellow-800',
  POSSIBLE_REGRESSION: 'bg-orange-100 text-orange-800',
  NEW_FINDING: 'bg-blue-100 text-blue-800',
  UNCOMPARABLE: 'bg-gray-100 text-gray-800',
};

const checkTypeLabels: Record<CheckType, string> = {
  ORIGINAL_VULNERABILITY: 'Original Vulnerability',
  REGRESSION_ANALYSIS: 'Regression Analysis',
  SCANNER_EXECUTION: 'Scanner Execution',
  TEST_EXECUTION: 'Test Execution',
  EVIDENCE_COMPARISON: 'Evidence Comparison',
};

const categoryLabels: Record<ComparisonCategory, string> = {
  STILL_PRESENT: 'Still Present',
  NO_LONGER_DETECTED: 'No Longer Detected',
  MODIFIED_OR_MOVED: 'Modified or Moved',
  POSSIBLE_REGRESSION: 'Possible Regression',
  NEW_FINDING: 'New Finding',
  UNCOMPARABLE: 'Uncomparable',
};

export default function VerificationDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { currentWorkspace } = useAuthContext();
  const [detail, setDetail] = useState<VerificationDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'baseline' | 'comparisons' | 'checks' | 'reviews' | 'policy'>('overview');

  const jobId = params.id as string;

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchDetail();
  }, [currentWorkspace, jobId]);

  const fetchDetail = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getVerificationDetail(jobId);
      setDetail(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load verification details');
    } finally {
      setLoading(false);
    }
  };

  const handleReview = async (decision: ReviewDecision) => {
    if (!detail) return;
    const justification = prompt(`Enter justification for ${decision}:`);
    if (!justification) return;

    try {
      await api.submitVerificationReview({
        verification_job_id: jobId,
        decision,
        justification,
      });
      fetchDetail();
    } catch (err: any) {
      alert(err.message || 'Failed to submit review');
    }
  };

  const handleRerun = async () => {
    if (!detail) return;
    const idempotencyKey = crypto.randomUUID();
    try {
      await api.rerunVerification({
        verification_job_id: jobId,
        idempotency_key: idempotencyKey,
      });
      router.push(`/verifications/${jobId}`);
    } catch (err: any) {
      alert(err.message || 'Failed to rerun verification');
    }
  };

  const handleCancel = async () => {
    if (!detail) return;
    if (!confirm('Are you sure you want to cancel this verification?')) return;
    try {
      await api.cancelVerification(jobId);
      fetchDetail();
    } catch (err: any) {
      alert(err.message || 'Failed to cancel verification');
    }
  };

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-6 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        <p className="mt-2 text-gray-500">Loading verification...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg max-w-md mx-auto">
          {error}
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Verification not found</p>
      </div>
    );
  }

  const { job, baseline, checks, comparisons, reviews, policy } = detail;

  const canReview = job.status === 'PASSED_PENDING_REVIEW' && job.overall_outcome === 'VERIFIED_CANDIDATE';

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-4 mb-2">
            <h1 className="text-2xl font-bold text-gray-900">Verification Details</h1>
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${statusColors[job.status]}`}>
              {job.status}
            </span>
            {job.overall_outcome && (
              <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${outcomeColors[job.overall_outcome]}`}>
                {job.overall_outcome}
              </span>
            )}
          </div>
          <p className="text-gray-500">ID: <code className="font-mono text-sm bg-gray-100 px-1.5 py-0.5 rounded">{job.id}</code></p>
        </div>
        <div className="flex gap-2">
          {canReview && (
            <>
              <button
                onClick={() => handleReview('accept')}
                className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 text-sm font-medium"
              >
                Accept
              </button>
              <button
                onClick={() => handleReview('reject')}
                className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 text-sm font-medium"
              >
                Reject
              </button>
            </>
          )}
          {job.status === 'RUNNING' && (
            <button
              onClick={handleCancel}
              className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 text-sm font-medium"
            >
              Cancel
            </button>
          )}
          {(job.status === 'FAILED' || job.status === 'INCONCLUSIVE' || job.status === 'BLOCKED' || job.status === 'CANCELED') && (
            <button
              onClick={handleRerun}
              className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium"
            >
              Rerun
            </button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8" aria-label="Tabs">
          {[
            { id: 'overview', label: 'Overview', count: 1 },
            { id: 'baseline', label: 'Baseline', count: baseline ? 1 : 0 },
            { id: 'comparisons', label: 'Comparisons', count: comparisons.length },
            { id: 'checks', label: 'Checks', count: checks.length },
            { id: 'reviews', label: 'Reviews', count: reviews.length },
            { id: 'policy', label: 'Policy', count: policy ? 1 : 0 },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as typeof activeTab)}
              className={`py-4 px-1 border-b-2 font-medium text-sm flex items-center gap-1.5 ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              {tab.count > 0 && (
                <span className={`px-2 py-0.5 text-xs rounded-full ${
                  activeTab === tab.id ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-600'
                }`}>
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="space-y-6">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Job Info */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Job Information</h2>
              <dl className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2">
                  <dt className="text-gray-500">Finding ID</dt>
                  <dd className="font-mono text-gray-900">{job.finding_id}</dd>
                  <dt className="text-gray-500">Asset ID</dt>
                  <dd className="font-mono text-gray-900">{job.asset_id}</dd>
                  <dt className="text-gray-500">Proposal ID</dt>
                  <dd className="font-mono text-gray-900">{job.remediation_proposal_id}</dd>
                  <dt className="text-gray-500">Application ID</dt>
                  <dd className="font-mono text-gray-900">{job.remediation_application_id}</dd>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <dt className="text-gray-500">Patch Hash</dt>
                  <dd className="font-mono text-gray-900">{job.patch_hash}</dd>
                  <dt className="text-gray-500">Source Revision</dt>
                  <dd className="font-mono text-gray-900">{job.source_revision.slice(0, 16)}...</dd>
                  <dt className="text-gray-500">Target Revision</dt>
                  <dd className="font-mono text-gray-900">{job.target_revision.slice(0, 16)}...</dd>
                  <dt className="text-gray-500">Engine Version</dt>
                  <dd className="text-gray-900">{job.verification_engine_version}</dd>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <dt className="text-gray-500">Policy Version</dt>
                  <dd className="text-gray-900">{job.policy_version}</dd>
                  <dt className="text-gray-500">Requested By</dt>
                  <dd className="font-mono text-gray-900">{job.requested_by}</dd>
                  <dt className="text-gray-500">Started At</dt>
                  <dd className="text-gray-900">{job.started_at ? new Date(job.started_at).toLocaleString() : '-'}</dd>
                  <dt className="text-gray-500">Completed At</dt>
                  <dd className="text-gray-900">{job.completed_at ? new Date(job.completed_at).toLocaleString() : '-'}</dd>
                </div>
                {job.error_message && (
                  <div className="p-3 bg-red-50 border border-red-200 rounded-md">
                    <dt className="text-red-700 text-sm font-medium">Error</dt>
                    <dd className="text-red-600 text-sm font-mono">{job.error_message}</dd>
                  </div>
                )}
              </dl>
            </div>

            {/* Outcome Summary */}
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Outcome Summary</h2>
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                  <span className="text-gray-700">Overall Outcome</span>
                  <span className={`px-3 py-1 rounded-full text-sm font-medium ${job.overall_outcome ? outcomeColors[job.overall_outcome] : 'bg-gray-100 text-gray-500'}`}>
                    {job.overall_outcome || 'Pending'}
                  </span>
                </div>
                {[
                  { key: 'original_vulnerability_outcome', label: 'Original Vulnerability' },
                  { key: 'scanner_execution_outcome', label: 'Scanner Execution' },
                  { key: 'evidence_comparison_outcome', label: 'Evidence Comparison' },
                  { key: 'regression_analysis_outcome', label: 'Regression Analysis' },
                  { key: 'test_execution_outcome', label: 'Test Execution' },
                ].map(item => {
                  const value = job[item.key as keyof VerificationJob] as CheckStatus | undefined;
                  return value ? (
                    <div key={item.key} className="flex items-center justify-between p-3 bg-gray-50 rounded-md">
                      <span className="text-gray-700">{item.label}</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${checkStatusColors[value]}`}>
                        {value}
                      </span>
                    </div>
                  ) : null;
                })}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'baseline' && baseline && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Baseline Capture</h2>
            <dl className="space-y-3 text-sm grid grid-cols-2 gap-4">
              <div>
                <dt className="text-gray-500">Baseline ID</dt>
                <dd className="font-mono text-gray-900">{baseline.id}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Capture Method</dt>
                <dd className="text-gray-900 capitalize">{baseline.capture_method}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Scanner Version</dt>
                <dd className="text-gray-900">{baseline.scanner_version}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Repository Revision</dt>
                <dd className="font-mono text-gray-900">{baseline.repository_revision}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Finding Fingerprint</dt>
                <dd className="font-mono text-gray-900">{baseline.finding_fingerprint}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Rule IDs</dt>
                <dd className="text-gray-900">{baseline.rule_ids.join(', ') || 'None'}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Evidence Hashes</dt>
                <dd className="text-gray-900">{baseline.evidence_hashes.length} hashes</dd>
              </div>
              <div>
                <dt className="text-gray-500">Captured At</dt>
                <dd className="text-gray-900">{new Date(baseline.captured_at).toLocaleString()}</dd>
              </div>
              <div className="col-span-2">
                <dt className="text-gray-500">Original Finding Snapshot</dt>
                <dd className="mt-1 p-3 bg-gray-50 rounded-md overflow-auto max-h-64">
                  <pre className="text-xs font-mono text-gray-700">{JSON.stringify(baseline.original_finding_snapshot, null, 2)}</pre>
                </dd>
              </div>
            </dl>
          </div>
        )}

        {activeTab === 'baseline' && !baseline && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
            <p className="text-gray-500">No baseline captured yet</p>
          </div>
        )}

        {activeTab === 'comparisons' && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {comparisons.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No evidence comparisons yet</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rule ID</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">File Path</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Match Confidence</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Rationale</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {comparisons.map(comp => (
                      <tr key={comp.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 font-mono text-sm text-gray-900">{comp.scanner_rule_id}</td>
                        <td className="px-6 py-4 font-mono text-sm text-gray-600">{comp.normalized_file_path}</td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${categoryColors[comp.category]}`}>
                            {categoryLabels[comp.category]}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-900">
                          {comp.match_confidence !== null ? `${(comp.match_confidence * 100).toFixed(0)}%` : '-'}
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">{comp.match_rationale || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'checks' && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {checks.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No checks executed yet</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Check Type</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Duration</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Command</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Exit Code</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {checks.map(check => (
                      <tr key={check.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-700">{checkTypeLabels[check.check_type] || check.check_type}</td>
                        <td className="px-6 py-4 font-medium text-gray-900">{check.check_name}</td>
                        <td className="px-6 py-4">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${checkStatusColors[check.status]}`}>
                            {check.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-sm text-gray-500">
                          {check.duration_ms ? `${(check.duration_ms / 1000).toFixed(1)}s` : '-'}
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-gray-600 max-w-md truncate">{check.command || '-'}</td>
                        <td className="px-6 py-4 text-sm text-gray-500">{check.exit_code !== null && check.exit_code !== undefined ? check.exit_code : '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {activeTab === 'reviews' && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            {reviews.length === 0 ? (
              <div className="p-6 text-center text-gray-500">No reviews yet</div>
            ) : (
              <div className="divide-y divide-gray-200">
                {reviews.map(review => (
                  <div key={review.id} className="p-6">
                    <div className="flex items-start justify-between mb-4">
                      <div>
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                          review.decision === 'accept' ? 'bg-green-100 text-green-800' :
                          review.decision === 'reject' ? 'bg-red-100 text-red-800' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {review.decision}
                        </span>
                        <span className="ml-3 text-sm text-gray-500">by {review.reviewed_by.slice(0, 8)}...</span>
                        <span className="ml-3 text-sm text-gray-500">{new Date(review.reviewed_at).toLocaleString()}</span>
                      </div>
                    </div>
                    <div className="prose prose-sm max-w-none">
                      <p className="font-medium text-gray-700 mb-1">Justification:</p>
                      <p className="text-gray-600">{review.justification}</p>
                      {review.notes && (
                        <p className="mt-2 font-medium text-gray-700 mb-1">Notes:</p>
                      )}
                      {review.notes && <p className="text-gray-600">{review.notes}</p>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === 'policy' && policy && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Verification Policy</h2>
            <dl className="space-y-3 text-sm">
              <div className="grid grid-cols-2 gap-2">
                <dt className="text-gray-500">Version</dt>
                <dd className="font-mono text-gray-900">{policy.version}</dd>
                <dt className="text-gray-500">Active</dt>
                <dd className="text-gray-900">{policy.is_active ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Name</dt>
                <dd className="text-gray-900">{policy.name}</dd>
              </div>
              {policy.description && (
                <div>
                  <dt className="text-gray-500">Description</dt>
                  <dd className="text-gray-900">{policy.description}</dd>
                </div>
              )}
              <div>
                <dt className="text-gray-500">Policy Configuration</dt>
                <dd className="mt-1 p-3 bg-gray-50 rounded-md overflow-auto max-h-96">
                  <pre className="text-xs font-mono text-gray-700">{JSON.stringify(policy.policy_config, null, 2)}</pre>
                </dd>
              </div>
            </dl>
          </div>
        )}

        {activeTab === 'policy' && !policy && (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 text-center">
            <p className="text-gray-500">No policy found for this version</p>
          </div>
        )}
      </div>
    </div>
  );
}
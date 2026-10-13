'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { VerificationJobListItem, VerificationStatus, VerificationOutcome } from '@/lib/api';
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

export default function VerificationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentWorkspace } = useAuthContext();
  const [jobs, setJobs] = useState<VerificationJobListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    outcome: searchParams.get('outcome') || '',
    finding_id: searchParams.get('finding_id') || '',
    asset_id: searchParams.get('asset_id') || '',
    page: parseInt(searchParams.get('page') || '1'),
    limit: 20,
  });
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchJobs();
  }, [currentWorkspace, filters]);

  const fetchJobs = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('workspace_id', currentWorkspace.id);
      if (filters.status) params.set('status', filters.status);
      if (filters.outcome) params.set('outcome', filters.outcome);
      if (filters.finding_id) params.set('finding_id', filters.finding_id);
      if (filters.asset_id) params.set('asset_id', filters.asset_id);
      params.set('limit', filters.limit.toString());
      params.set('offset', ((filters.page - 1) * filters.limit).toString());

      const data = await api.listVerifications(currentWorkspace.id, Object.fromEntries(params));
      setJobs(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load verifications');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }));
    const params = new URLSearchParams(searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    params.set('page', '1');
    router.push(`/verifications?${params.toString()}`);
  };

  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
    const params = new URLSearchParams(searchParams);
    params.set('page', page.toString());
    router.push(`/verifications?${params.toString()}`);
  };

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'QUEUED', label: 'Queued' },
    { value: 'RUNNING', label: 'Running' },
    { value: 'BASELINE_CHECK', label: 'Baseline Check' },
    { value: 'RESCANNING', label: 'Rescanning' },
    { value: 'REGRESSION_CHECK', label: 'Regression Check' },
    { value: 'COMPARING_EVIDENCE', label: 'Comparing Evidence' },
    { value: 'PASSED_PENDING_REVIEW', label: 'Passed - Pending Review' },
    { value: 'VERIFIED', label: 'Verified' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'INCONCLUSIVE', label: 'Inconclusive' },
    { value: 'BLOCKED', label: 'Blocked' },
    { value: 'CANCELED', label: 'Canceled' },
  ];

  const outcomeOptions = [
    { value: '', label: 'All Outcomes' },
    { value: 'VERIFIED_CANDIDATE', label: 'Verified Candidate' },
    { value: 'FAILED', label: 'Failed' },
    { value: 'INCONCLUSIVE', label: 'Inconclusive' },
    { value: 'BLOCKED', label: 'Blocked' },
  ];

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Verifications</h1>
          <p className="text-gray-500 mt-1">Independent fix verification & regression analysis</p>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={filters.status}
              onChange={(e) => handleFilterChange('status', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {statusOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Outcome</label>
            <select
              value={filters.outcome}
              onChange={(e) => handleFilterChange('outcome', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              {outcomeOptions.map(opt => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Finding ID</label>
            <input
              type="text"
              value={filters.finding_id}
              onChange={(e) => handleFilterChange('finding_id', e.target.value)}
              placeholder="Filter by finding ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Asset ID</label>
            <input
              type="text"
              value={filters.asset_id}
              onChange={(e) => handleFilterChange('asset_id', e.target.value)}
              placeholder="Filter by asset ID"
              className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Jobs Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-gray-500">Loading verifications...</p>
          </div>
        ) : jobs.length === 0 ? (
          <div className="p-6 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No verifications found</h3>
            <p className="mt-1 text-sm text-gray-500">Start a verification from a remediation application detail page.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Finding</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Asset</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Patch Hash</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Outcome</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Requested By</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Completed</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {jobs.map(job => (
                    <tr key={job.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Link href={`/findings/${job.finding_id}`} className="text-sm font-medium text-blue-600 hover:text-blue-900 font-mono">
                          {job.finding_id.slice(0, 8)}...
                        </Link>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-gray-500 font-mono">{job.asset_id.slice(0, 8)}...</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-mono text-gray-600">{job.patch_hash.slice(0, 16)}...</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[job.status]}`}>
                          {job.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {job.overall_outcome ? (
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${outcomeColors[job.overall_outcome]}`}>
                            {job.overall_outcome}
                          </span>
                        ) : (
                          <span className="text-sm text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500 font-mono">
                        {job.requested_by.slice(0, 8)}...
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {new Date(job.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {job.completed_at ? new Date(job.completed_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-6 py-4 text-right text-sm font-medium">
                        <Link href={`/verifications/${job.id}`} className="text-blue-600 hover:text-blue-900">View</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="px-6 py-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Showing {((filters.page - 1) * filters.limit) + 1} to {Math.min(filters.page * filters.limit, total)} of {total} results
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handlePageChange(filters.page - 1)}
                    disabled={filters.page <= 1}
                    className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => handlePageChange(filters.page + 1)}
                    disabled={filters.page * filters.limit >= total}
                    className="px-3 py-1 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
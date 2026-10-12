'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { RemediationProposalListItem, RemediationStatus, RemediationFixType } from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';

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

const fixTypeLabels: Record<RemediationFixType, string> = {
  code_change: 'Code Change',
  config_change: 'Config Change',
  dependency_update: 'Dependency Update',
  infrastructure_change: 'Infrastructure Change',
  waf_rule: 'WAF Rule',
  network_policy: 'Network Policy',
  secret_rotation: 'Secret Rotation',
};

export default function RemediationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentWorkspace } = useAuthContext();
  const [proposals, setProposals] = useState<RemediationProposalListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    finding_id: searchParams.get('finding_id') || '',
    asset_id: searchParams.get('asset_id') || '',
    page: parseInt(searchParams.get('page') || '1'),
    limit: 20,
  });
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchProposals();
  }, [currentWorkspace, filters]);

  const fetchProposals = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('workspace_id', currentWorkspace.id);
      if (filters.status) params.set('status', filters.status);
      if (filters.finding_id) params.set('finding_id', filters.finding_id);
      if (filters.asset_id) params.set('asset_id', filters.asset_id);
      params.set('limit', filters.limit.toString());
      params.set('offset', ((filters.page - 1) * filters.limit).toString());

      const data = await api.listRemediations(currentWorkspace.id, Object.fromEntries(params));
      setProposals(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load remediations');
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
    router.push(`/remediations?${params.toString()}`);
  };

  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
    const params = new URLSearchParams(searchParams);
    params.set('page', page.toString());
    router.push(`/remediations?${params.toString()}`);
  };

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'DRAFT', label: 'Draft' },
    { value: 'GENERATING', label: 'Generating' },
    { value: 'PROPOSED', label: 'Proposed' },
    { value: 'VALIDATING', label: 'Validating' },
    { value: 'VALIDATION_FAILED', label: 'Validation Failed' },
    { value: 'AWAITING_APPROVAL', label: 'Awaiting Approval' },
    { value: 'APPROVED', label: 'Approved' },
    { value: 'APPLYING', label: 'Applying' },
    { value: 'APPLIED', label: 'Applied' },
    { value: 'REJECTED', label: 'Rejected' },
    { value: 'EXPIRED', label: 'Expired' },
    { value: 'ROLLED_BACK', label: 'Rolled Back' },
    { value: 'FAILED', label: 'Failed' },
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
          <h1 className="text-2xl font-bold text-gray-900">Remediations</h1>
          <p className="text-gray-500 mt-1">AI-generated remediation proposals with human approval workflow</p>
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

      {/* Proposals Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="p-6 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-2 text-gray-500">Loading remediations...</p>
          </div>
        ) : proposals.length === 0 ? (
          <div className="p-6 text-center">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No remediations found</h3>
            <p className="mt-1 text-sm text-gray-500">Generate a remediation from a finding detail page to get started.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Finding</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Fix Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Approved</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Applied</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {proposals.map(proposal => (
                    <tr key={proposal.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Link href={`/remediations/${proposal.id}`} className="text-sm font-medium text-blue-600 hover:text-blue-900">
                          {proposal.proposal_title}
                        </Link>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-gray-500 font-mono">{proposal.finding_id.slice(0, 8)}...</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {fixTypeLabels[proposal.fix_type] || proposal.fix_type}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${statusColors[proposal.status]}`}>
                          {proposal.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {new Date(proposal.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {proposal.approved_at ? new Date(proposal.approved_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {proposal.applied_at ? new Date(proposal.applied_at).toLocaleDateString() : '-'}
                      </td>
                      <td className="px-6 py-4 text-right text-sm font-medium">
                        <Link href={`/remediations/${proposal.id}`} className="text-blue-600 hover:text-blue-900">View</Link>
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
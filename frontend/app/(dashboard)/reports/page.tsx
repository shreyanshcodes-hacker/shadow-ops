'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { ReportListResponse, ReportType, ReportFormat, ReportStatus } from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { formatDistanceToNow, format } from 'date-fns';
import {
  FileText, Download, Search, Filter, Plus, Eye, Clock,
  TrendingUp, Shield, Bug, Zap, RotateCcw
} from 'lucide-react';

const REPORT_TYPE_LABELS: Record<ReportType, string> = {
  executive_summary: 'Executive Summary',
  technical_vulnerability: 'Technical Vulnerability',
  remediation_progress: 'Remediation Progress',
  verification_regression: 'Verification & Regression',
  asset_security_posture: 'Asset Security Posture',
};

const REPORT_FORMAT_LABELS: Record<ReportFormat, string> = {
  pdf: 'PDF',
  json: 'JSON',
};

const STATUS_CONFIG: Record<ReportStatus, { label: string; color: string }> = {
  pending: { label: 'Pending', color: 'secondary' },
  generating: { label: 'Generating', color: 'info' },
  ready: { label: 'Ready', color: 'success' },
  failed: { label: 'Failed', color: 'error' },
  expired: { label: 'Expired', color: 'secondary' },
};

export default function ReportsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentWorkspace } = useAuthContext();
  const [reports, setReports] = useState<ReportListResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    report_type: searchParams.get('report_type') || '',
    status: searchParams.get('status') || '',
    page: parseInt(searchParams.get('page') || '1'),
    limit: 20,
  });
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchReports();
  }, [currentWorkspace, filters]);

  const fetchReports = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('workspace_id', currentWorkspace.id);
      if (filters.report_type) params.set('report_type', filters.report_type);
      if (filters.status) params.set('status', filters.status);
      params.set('limit', filters.limit.toString());
      params.set('offset', ((filters.page - 1) * filters.limit).toString());

      const data = await api.listReports(currentWorkspace.id, Object.fromEntries(params));
      setReports(data);
      setTotal(data.length); // API doesn't return total, using length as fallback
    } catch (err: any) {
      setError(err.message || 'Failed to load reports');
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
    router.push(`/reports?${params.toString()}`);
  };

  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
    const params = new URLSearchParams(searchParams);
    params.set('page', page.toString());
    router.push(`/reports?${params.toString()}`);
  };

  const reportTypeOptions = [
    { value: '', label: 'All Types' },
    { value: 'executive_summary', label: 'Executive Summary' },
    { value: 'technical_vulnerability', label: 'Technical Vulnerability' },
    { value: 'remediation_progress', label: 'Remediation Progress' },
    { value: 'verification_regression', label: 'Verification & Regression' },
    { value: 'asset_security_posture', label: 'Asset Security Posture' },
  ];

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'generating', label: 'Generating' },
    { value: 'ready', label: 'Ready' },
    { value: 'failed', label: 'Failed' },
    { value: 'expired', label: 'Expired' },
  ];

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Security Reports</h1>
          <p className="text-gray-500 mt-1">Generate and manage security reports for your workspace</p>
        </div>
        <Button asChild>
          <Link href="/reports/new">
            <Plus className="h-4 w-4 mr-2" />
            Generate Report
          </Link>
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-4 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">Report Type</label>
              <Select value={filters.report_type} onValueChange={(v) => handleFilterChange('report_type', v)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Types" />
                </SelectTrigger>
                <SelectContent>
                  {reportTypeOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
              <Select value={filters.status} onValueChange={(v) => handleFilterChange('status', v)}>
                <SelectTrigger>
                  <SelectValue placeholder="All Statuses" />
                </SelectTrigger>
                <SelectContent>
                  {statusOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Reports Table */}
      <Card>
        {loading ? (
          <div className="p-6">
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <CardSkeleton key={i} />
              ))}
            </div>
          </div>
        ) : reports.length === 0 ? (
          <div className="p-12 text-center">
            <FileText className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Reports Found</h3>
            <p className="text-gray-500 mb-6">Generate your first security report to get started.</p>
            <Button asChild>
              <Link href="/reports/new">
                <Plus className="h-4 w-4 mr-2" />
                Generate Report
              </Link>
            </Button>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Type</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Format</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Period</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Completed</th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {reports.map(report => (
                    <tr key={report.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4">
                        <Link href={`/reports/${report.id}`} className="text-sm font-medium text-blue-600 hover:text-blue-900">
                          {report.title}
                        </Link>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                          {REPORT_TYPE_LABELS[report.report_type] || report.report_type}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-50 text-blue-700">
                          {REPORT_FORMAT_LABELS[report.format] || report.format}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${STATUS_CONFIG[report.status]?.color || 'bg-gray-100 text-gray-800'}`}>
                          {STATUS_CONFIG[report.status]?.label || report.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {report.period_start && report.period_end ? (
                          <>
                            {format(new Date(report.period_start), 'MMM d, yyyy')} - {format(new Date(report.period_end), 'MMM d, yyyy')}
                          </>
                        ) : report.period_end ? (
                          format(new Date(report.period_end), 'MMM d, yyyy')
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
                      </td>
                      <td className="px-6 py-4 text-sm text-gray-500">
                        {report.completed_at ? formatDistanceToNow(new Date(report.completed_at), { addSuffix: true }) : '-'}
                      </td>
                      <td className="px-6 py-4 text-right text-sm font-medium space-x-2">
                        <Link href={`/reports/${report.id}`} className="text-blue-600 hover:text-blue-900 flex items-center gap-1">
                          <Eye className="h-4 w-4" />
                          View
                        </Link>
                        {report.status === 'ready' && (
                          <Button variant="ghost" size="sm" asChild onClick={() => router.push(`/reports/${report.id}`)}>
                            <Download className="h-4 w-4 mr-1" />
                            Export
                          </Button>
                        )}
                        {report.status === 'failed' && (
                          <Button variant="ghost" size="sm" onClick={() => { /* regenerate */ }}>
                            <RotateCcw className="h-4 w-4 mr-1" />
                            Retry
                          </Button>
                        )}
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
                  <Button
                    onClick={() => handlePageChange(filters.page - 1)}
                    disabled={filters.page <= 1}
                    variant="outline"
                    size="sm"
                  >
                    Previous
                  </Button>
                  <Button
                    onClick={() => handlePageChange(filters.page + 1)}
                    disabled={filters.page * filters.limit >= total}
                    variant="outline"
                    size="sm"
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
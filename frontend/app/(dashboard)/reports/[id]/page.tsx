'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import {
  ReportDetailResponse,
  ReportResponse,
  ReportSectionResponse,
  ReportExportResponse,
  ReportType,
  ReportFormat,
  ReportStatus,
} from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Link } from 'next/navigation';
import { format, formatDistanceToNow } from 'date-fns';
import {
  ArrowLeft, Download, FileText, Shield, Bug, Zap, RotateCcw,
  Clock, Eye, AlertTriangle, CheckCircle, XCircle, Loader2,
  Sparkles, Brain, ArrowRight, ChevronRight
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

const STATUS_CONFIG: Record<ReportStatus, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: 'Pending', color: 'secondary', icon: <Clock className="h-3 w-3" /> },
  generating: { label: 'Generating', color: 'info', icon: <Loader2 className="h-3 w-3 animate-spin" /> },
  ready: { label: 'Ready', color: 'success', icon: <CheckCircle className="h-3 w-3" /> },
  failed: { label: 'Failed', color: 'error', icon: <XCircle className="h-3 w-3" /> },
  expired: { label: 'Expired', color: 'secondary', icon: <Clock className="h-3 w-3" /> },
};

const SECTION_ICONS: Record<string, React.ReactNode> = {
  executive_overview: <Shield className="h-4 w-4" />,
  security_posture: <Shield className="h-4 w-4" />,
  critical_risks: <AlertTriangle className="h-4 w-4" />,
  critical_findings: <Bug className="h-4 w-4" />,
  attack_paths: <Shield className="h-4 w-4" />,
  remediation_progress: <RotateCcw className="h-4 w-4" />,
  verification_outcomes: <Zap className="h-4 w-4" />,
  unresolved_risks: <AlertTriangle className="h-4 w-4" />,
  recommended_actions: <ArrowRight className="h-4 w-4" />,
  scope_limitations: <FileText className="h-4 w-4" />,
  ai_narrative: <Brain className="h-4 w-4" />,
};

export default function ReportDetailPage() {
  const router = useRouter();
  const params = useParams();
  const { currentWorkspace } = useAuthContext();
  const [detail, setDetail] = useState<ReportDetailResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [exporting, setExporting] = useState<string | null>(null);

  const reportId = params.id as string;

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchDetail();
  }, [currentWorkspace, reportId]);

  const fetchDetail = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getReportDetail(reportId);
      setDetail(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load report details');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: ReportFormat) => {
    if (!detail) return;
    setExporting(format);
    try {
      const exportResult = await api.exportReport(reportId, format);
      const downloadResult = await api.getReportDownloadUrl(reportId, exportResult.id);
      window.open(downloadResult.download_url, '_blank');
    } catch (err: any) {
      alert(err.message || 'Failed to export report');
    } finally {
      setExporting(null);
    }
  };

  const handleRegenerate = async () => {
    if (!detail) return;
    try {
      await api.generateReport({
        workspace_id: detail.report.workspace_id,
        report_type: detail.report.report_type,
        title: detail.report.title,
        description: detail.report.description,
        format: detail.report.format,
        period_start: detail.report.period_start,
        period_end: detail.report.period_end,
        included_asset_ids: detail.report.included_asset_ids,
        severity_filters: detail.report.severity_filters,
        filters: detail.report.filters,
      });
      router.push(`/reports/${reportId}`);
    } catch (err: any) {
      alert(err.message || 'Failed to regenerate report');
    }
  };

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-6 space-y-6 animate-pulse">
        <CardSkeleton />
        <CardSkeleton />
        <CardSkeleton className="min-h-[400px]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg max-w-md mx-auto">
          {error}
          <Button className="mt-2" onClick={fetchDetail}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Report not found</p>
      </div>
    );
  }

  const { report, sections, exports } = detail;
  const statusConfig = STATUS_CONFIG[report.status];

  const canExport = report.status === 'ready';
  const canRegenerate = report.status === 'failed';

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => router.back()}>
            <ArrowLeft className="h-4 w-4 mr-1" />
            Back
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-gray-900">{report.title}</h1>
              <span className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-sm font-medium ${statusConfig.color}`}>
                {statusConfig.icon}
                {statusConfig.label}
              </span>
            </div>
            <p className="text-gray-500 mt-1">
              {REPORT_TYPE_LABELS[report.report_type]} • {REPORT_FORMAT_LABELS[report.format]} •
              Generated {formatDistanceToNow(new Date(report.created_at), { addSuffix: true })}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canExport && (
            <>
              <Button variant="outline" onClick={() => handleExport('pdf')} disabled={exporting === 'pdf'}>
                <Download className="h-4 w-4 mr-2" />
                {exporting === 'pdf' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Export PDF'}
              </Button>
              <Button variant="outline" onClick={() => handleExport('json')} disabled={exporting === 'json'}>
                <Download className="h-4 w-4 mr-2" />
                {exporting === 'json' ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Export JSON'}
              </Button>
            </>
          )}
          {canRegenerate && (
            <Button variant="secondary" onClick={handleRegenerate}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Regenerate
            </Button>
          )}
          <Button variant="secondary" onClick={() => router.push('/reports')}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Reports
          </Button>
        </div>
      </div>

      {/* Report Metadata */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 text-sm">
            <div>
              <p className="text-gray-500">Report ID</p>
              <p className="font-mono text-gray-900">{report.id}</p>
            </div>
            <div>
              <p className="text-gray-500">Schema Version</p>
              <p className="font-medium text-gray-900">{report.schema_version}</p>
            </div>
            <div>
              <p className="text-gray-500">Risk Engine</p>
              <p className="font-medium text-gray-900">{report.risk_engine_version || 'N/A'}</p>
            </div>
            <div>
              <p className="text-gray-500">Verification Policy</p>
              <p className="font-medium text-gray-900">{report.verification_policy_version || 'N/A'}</p>
            </div>
            <div>
              <p className="text-gray-500">Data Cutoff</p>
              <p className="font-medium text-gray-900">{format(new Date(report.data_cutoff), 'MMM d, yyyy HH:mm')}</p>
            </div>
            <div>
              <p className="text-gray-500">Generated By</p>
              <p className="font-mono text-gray-900">{report.generated_by.slice(0, 8)}...</p>
            </div>
            {report.period_start && report.period_end && (
              <div className="md:col-span-2">
                <p className="text-gray-500">Reporting Period</p>
                <p className="font-medium text-gray-900">
                  {format(new Date(report.period_start), 'MMM d, yyyy')} - {format(new Date(report.period_end), 'MMM d, yyyy')}
                </p>
              </div>
            )}
            {report.completed_at && (
              <div>
                <p className="text-gray-500">Completed</p>
                <p className="font-medium text-gray-900">
                  {formatDistanceToNow(new Date(report.completed_at), { addSuffix: true })}
                </p>
              </div>
            )}
            {report.file_size_bytes && (
              <div>
                <p className="text-gray-500">File Size</p>
                <p className="font-medium text-gray-900">
                  {(report.file_size_bytes / 1024).toFixed(1)} KB
                </p>
              </div>
            )}
          </div>

          {/* Completeness & Limitations */}
          <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-green-600" />
                Data Completeness
              </h4>
              <div className="space-y-1 text-sm">
                {Object.entries(report.completeness).map(([key, value]) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className={value ? 'text-green-600' : 'text-red-600'}>
                      {value ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
                    </span>
                    <span className={value ? 'text-gray-900' : 'text-gray-500'}>{key.replace('_', ' ')}</span>
                  </div>
                ))}
              </div>
            </div>
            {report.limitations.length > 0 && (
              <div>
                <h4 className="font-medium text-gray-900 mb-2 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-yellow-600" />
                  Limitations
                </h4>
                <ul className="space-y-1 text-sm text-gray-600">
                  {report.limitations.map((lim, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <span className="text-yellow-600 mt-1">•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Tabs */}
      <Tabs defaultValue="overview" onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3 md:grid-cols-5">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="sections">Sections</TabsTrigger>
          <TabsTrigger value="exports">Exports ({exports.length})</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="mt-6 space-y-6">
          {/* Summary Stats */}
          <div className="grid gap-4 md:grid-cols-4">
            <StatCard
              title="Assets"
              value={report.source_record_references.asset_count || 0}
              icon={Shield}
              color="text-blue-600"
            />
            <StatCard
              title="Scans"
              value={report.source_record_references.scan_count || 0}
              icon={Zap}
              color="text-yellow-600"
            />
            <StatCard
              title="Findings"
              value={report.source_record_references.finding_count || 0}
              icon={Bug}
              color="text-red-600"
            />
            <StatCard
              title="Attack Paths"
              value={report.source_record_references.attack_path_count || 0}
              icon={Shield}
              color="text-purple-600"
            />
          </div>

          {/* Key Metrics from first section */}
          {sections.length > 0 && sections[0].content && (
            <Card>
              <CardHeader>
                <CardTitle>Executive Summary</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="prose prose-sm max-w-none">
                  {renderSectionContent(sections[0].content)}
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Sections Tab */}
        <TabsContent value="sections" className="mt-6 space-y-4">
          {sections.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <EmptyState
                  icon="FileText"
                  title="No Sections"
                  description="This report has no generated sections."
                />
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {sections.map((section) => (
                <Card key={section.id} className="overflow-hidden">
                  <CardHeader className="py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded bg-accent-glow">
                          {SECTION_ICONS[section.section_key] || <FileText className="h-4 w-4" />}
                        </div>
                        <div>
                          <h3 className="font-semibold text-gray-900">{section.section_title}</h3>
                          <p className="text-xs text-gray-500">{section.section_key}</p>
                        </div>
                      </div>
                      {section.data_references && Object.keys(section.data_references).length > 0 && (
                        <span className="text-xs text-gray-500">
                          {Object.values(section.data_references).flat().length} references
                        </span>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="prose prose-sm max-w-none">
                      {renderSectionContent(section.content)}
                    </div>
                    {section.data_references && Object.keys(section.data_references).length > 0 && (
                      <div className="mt-4 pt-4 border-t">
                        <h4 className="text-sm font-medium text-gray-700 mb-2">Data References</h4>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(section.data_references).flatMap(([type, refs]) =>
                            (refs as string[]).map(ref => (
                              <Badge key={`${type}-${ref}`} variant="outline" className="gap-1">
                                <ChevronRight className="h-3 w-3" />
                                {type}: {ref.slice(0, 8)}...
                              </Badge>
                            ))
                          )}
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Exports Tab */}
        <TabsContent value="exports" className="mt-6">
          {exports.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <EmptyState
                  icon="Download"
                  title="No Exports"
                  description="Generate exports from the report detail page."
                  action={
                    canExport && (
                      <Button onClick={() => handleExport('pdf')}>
                        <Download className="h-4 w-4 mr-2" />
                        Export PDF
                      </Button>
                    )
                  }
                />
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Report Exports</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Format</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Created</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Expires</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Checksum</th>
                        <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {exports.map(exp => (
                        <tr key={exp.id} className="hover:bg-gray-50">
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                              exp.format === 'pdf' ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'
                            }`}>
                              {exp.format.toUpperCase()}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {(exp.file_size_bytes / 1024).toFixed(1)} KB
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {formatDistanceToNow(new Date(exp.created_at), { addSuffix: true })}
                          </td>
                          <td className="px-6 py-4 text-sm text-gray-500">
                            {exp.expires_at ? formatDistanceToNow(new Date(exp.expires_at), { addSuffix: true }) : 'Never'}
                          </td>
                          <td className="px-6 py-4 text-sm font-mono text-gray-500">
                            {exp.checksum?.slice(0, 16)}...
                          </td>
                          <td className="px-6 py-4 text-right text-sm font-medium">
                            <Button variant="ghost" size="sm" onClick={() => {
                              api.getReportDownloadUrl(reportId, exp.id).then(r => window.open(r.download_url, '_blank'));
                            }}>
                              <Download className="h-4 w-4 mr-1" />
                              Download
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function StatCard({ title, value, icon: Icon, color }: { title: string; value: number; icon: React.ComponentType<{ className?: string }>; color: string }) {
  return (
    <Card className="card-hover">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wider">{title}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
          </div>
          <div className="p-2 rounded-lg bg-gray-100">
            <Icon className={`h-6 w-6 ${color}`} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function renderSectionContent(content: Record<string, unknown>): React.ReactNode {
  if (!content || Object.keys(content).length === 0) {
    return <p className="text-gray-500">No content available</p>;
  }

  return (
    <div className="space-y-4">
      {Object.entries(content).map(([key, value]) => (
        <div key={key}>
          <h4 className="font-medium text-gray-900 capitalize">{key.replace(/_/g, ' ')}</h4>
          {renderValue(value)}
        </div>
      ))}
    </div>
  );
}

function renderValue(value: unknown): React.ReactNode {
  if (value === null || value === undefined) {
    return <span className="text-gray-400 italic">N/A</span>;
  }

  if (typeof value === 'string') {
    return <p className="text-gray-700 mt-1 whitespace-pre-wrap">{value}</p>;
  }

  if (typeof value === 'number') {
    return <p className="text-gray-700 mt-1 font-mono">{value.toLocaleString()}</p>;
  }

  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-gray-400 italic">Empty</span>;
    return (
      <ul className="list-disc list-inside space-y-1 mt-1 text-gray-700">
        {value.map((item, i) => (
          <li key={i}>{typeof item === 'object' ? JSON.stringify(item) : String(item)}</li>
        ))}
      </ul>
    );
  }

  if (typeof value === 'object') {
    return (
      <div className="mt-1 space-y-2">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="flex gap-4">
            <span className="font-medium text-gray-500 min-w-[150px]">{k.replace(/_/g, ' ')}:</span>
            <span className="text-gray-700">{renderValue(v)}</span>
          </div>
        ))}
      </div>
    );
  }

  return <span className="text-gray-700">{String(value)}</span>;
}
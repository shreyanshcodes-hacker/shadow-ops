'use client';

import { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  Shield, GitBranch, AlertTriangle, BarChart3, CheckCircle, Clock,
  Users, Plus, Search, Bot, RotateCcw, Eye, Download, FileText,
  TrendingUp, TrendingDown, Minus, AlertCircle, Zap
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { api } from '@/lib/api';
import { DashboardMetrics, TrendResponse, TrendSeries, TrendDataPoint } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';
import { formatDistanceToNow, format, subDays, startOfDay, endOfDay } from 'date-fns';
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend, BarChart, Bar, Cell,
  PieChart, Pie, Cell as PieCell
} from 'recharts';

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  info: '#3b82f6',
};

const STATUS_COLORS: Record<string, string> = {
  completed: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  queued: '#6b7280',
  cancelled: '#9ca3af',
  partial: '#f97316',
};

const REMEDIATION_STATUS_COLORS: Record<string, string> = {
  DRAFT: '#9ca3af',
  GENERATING: '#3b82f6',
  PROPOSED: '#eab308',
  VALIDATING: '#3b82f6',
  VALIDATION_FAILED: '#ef4444',
  AWAITING_APPROVAL: '#f97316',
  APPROVED: '#22c55e',
  APPLYING: '#3b82f6',
  APPLIED: '#22c55e',
  REJECTED: '#ef4444',
  EXPIRED: '#9ca3af',
  ROLLED_BACK: '#a855f7',
  FAILED: '#ef4444',
};

const VERIFICATION_STATUS_COLORS: Record<string, string> = {
  QUEUED: '#9ca3af',
  RUNNING: '#3b82f6',
  BASELINE_CHECK: '#3b82f6',
  RESCANNING: '#3b82f6',
  REGRESSION_CHECK: '#3b82f6',
  COMPARING_EVIDENCE: '#3b82f6',
  PASSED_PENDING_REVIEW: '#22c55e',
  VERIFIED: '#22c55e',
  FAILED: '#ef4444',
  INCONCLUSIVE: '#eab308',
  BLOCKED: '#f97316',
  CANCELED: '#9ca3af',
};

const VERIFICATION_OUTCOME_COLORS: Record<string, string> = {
  VERIFIED_CANDIDATE: '#22c55e',
  FAILED: '#ef4444',
  INCONCLUSIVE: '#eab308',
  BLOCKED: '#f97316',
};

const RISK_BAND_COLORS: Record<string, string> = {
  critical: '#ef4444',
  high: '#f97316',
  medium: '#eab308',
  low: '#22c55e',
  informational: '#3b82f6',
};

const CHART_COLORS = ['#3b82f6', '#ef4444', '#f97316', '#eab308', '#22c55e', '#a855f7', '#06b6d4', '#f472b6'];

interface SeverityStat {
  severity: string;
  count: number;
  color: string;
}

interface TrendChartData {
  label: string;
  [key: string]: string | number;
}

export default function DashboardPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentWorkspace } = useAuthContext();
  const [timeRange, setTimeRange] = useState('30d');
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [trends, setTrends] = useState<TrendResponse | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);
  const [trendsLoading, setTrendsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchData();
  }, [currentWorkspace, timeRange]);

  const getPeriodDates = () => {
    const end = new Date();
    let start: Date;
    switch (timeRange) {
      case '7d': start = subDays(end, 7); break;
      case '30d': start = subDays(end, 30); break;
      case '90d': start = subDays(end, 90); break;
      case '1y': start = subDays(end, 365); break;
      default: start = subDays(end, 30);
    }
    return { start: startOfDay(start), end: endOfDay(end) };
  };

  const fetchData = async () => {
    if (!currentWorkspace) return;
    setMetricsLoading(true);
    setTrendsLoading(true);
    setError(null);

    try {
      const { start, end } = getPeriodDates();
      const params = {
        workspace_id: currentWorkspace.id,
        period_start: start.toISOString(),
        period_end: end.toISOString(),
      };

      const [metricsData, trendsData] = await Promise.all([
        api.getDashboardMetrics(currentWorkspace.id),
        api.getDashboardTrends(currentWorkspace.id, params),
      ]);

      setMetrics(metricsData);
      setTrends(trendsData);
    } catch (err: any) {
      setError(err.message || 'Failed to load dashboard data');
    } finally {
      setMetricsLoading(false);
      setTrendsLoading(false);
    }
  };

  const handleTimeRangeChange = (value: string) => {
    setTimeRange(value);
    const params = new URLSearchParams(searchParams);
    params.set('range', value);
    router.push(`/dashboard?${params.toString()}`);
  };

  const timeRangeOptions = [
    { value: '7d', label: 'Last 7 days' },
    { value: '30d', label: 'Last 30 days' },
    { value: '90d', label: 'Last 90 days' },
    { value: '1y', label: 'Last year' },
  ];

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <Shield className="h-12 w-12 text-gray-400 mx-auto mb-4" />
        <h1 className="text-2xl font-bold text-gray-900">Welcome to ShadowOps</h1>
        <p className="text-gray-500 mt-2">Select a workspace to view your security dashboard</p>
      </div>
    );
  }

  if (metricsLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
        <CardSkeleton className="min-h-[300px]" />
        <CardSkeleton className="min-h-[300px]" />
        <CardSkeleton className="min-h-[300px]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
          <Button className="mt-2" onClick={fetchData}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">Loading dashboard...</p>
      </div>
    );
  }

  // Transform data for charts
  const severityStats: SeverityStat[] = [
    { severity: 'Critical', count: metrics.findings.open_findings_by_severity.critical || 0, color: SEVERITY_COLORS.critical },
    { severity: 'High', count: metrics.findings.open_findings_by_severity.high || 0, color: SEVERITY_COLORS.high },
    { severity: 'Medium', count: metrics.findings.open_findings_by_severity.medium || 0, color: SEVERITY_COLORS.medium },
    { severity: 'Low', count: metrics.findings.open_findings_by_severity.low || 0, color: SEVERITY_COLORS.low },
    { severity: 'Info', count: metrics.findings.open_findings_by_severity.info || 0, color: SEVERITY_COLORS.info },
  ];

  const openFindingsTotal = severityStats.reduce((sum, s) => sum + s.count, 0);

  // Prepare trend chart data
  const findingTrendSeries = trends?.trends.find(t => t.metric_name === 'total_findings');
  const openFindingTrendSeries = trends?.trends.find(t => t.metric_name === 'open_findings');
  const riskTrendSeries = trends?.trends.find(t => t.metric_name === 'risk_score');
  const scanCompletedTrend = trends?.trends.find(t => t.metric_name === 'scans_completed');
  const scanFailedTrend = trends?.trends.find(t => t.metric_name === 'scans_failed');
  const newFindingsTrend = trends?.trends.find(t => t.metric_name === 'new_findings');
  const resolvedFindingsTrend = trends?.trends.find(t => t.metric_name === 'resolved_findings');
  const remediationProposedTrend = trends?.trends.find(t => t.metric_name === 'remediation_proposed');
  const remediationApprovedTrend = trends?.trends.find(t => t.metric_name === 'remediation_approved');
  const remediationAppliedTrend = trends?.trends.find(t => t.metric_name === 'remediation_applied');
  const verificationVerifiedTrend = trends?.trends.find(t => t.metric_name === 'verification_verified');
  const verificationFailedTrend = trends?.trends.find(t => t.metric_name === 'verification_failed');

  const buildTrendChartData = (series?: TrendSeries, color?: string): TrendChartData[] => {
    if (!series || series.data_points.length === 0) return [];
    return series.data_points.map((point, index) => ({
      date: point.label || point.timestamp.split('T')[0],
      value: point.value,
      color: color || CHART_COLORS[index % CHART_COLORS.length],
    }));
  };

  const findingTrendData = buildTrendChartData(findingTrendSeries, '#3b82f6');
  const openFindingTrendData = buildTrendChartData(openFindingTrendSeries, '#ef4444');
  const riskTrendData = buildTrendChartData(riskTrendSeries, '#a855f7');
  const scanTrendData = scanCompletedTrend && scanFailedTrend ? 
    scanCompletedTrend.data_points.map((point, i) => ({
      date: point.label || point.timestamp.split('T')[0],
      completed: point.value,
      failed: scanFailedTrend.data_points[i]?.value || 0,
    })) : [];
  const findingFlowData = newFindingsTrend && resolvedFindingsTrend ?
    newFindingsTrend.data_points.map((point, i) => ({
      date: point.label || point.timestamp.split('T')[0],
      new: point.value,
      resolved: resolvedFindingsTrend.data_points[i]?.value || 0,
    })) : [];
  const remediationTrendData = remediationProposedTrend && remediationApprovedTrend && remediationAppliedTrend ?
    remediationProposedTrend.data_points.map((point, i) => ({
      date: point.label || point.timestamp.split('T')[0],
      proposed: point.value,
      approved: remediationApprovedTrend.data_points[i]?.value || 0,
      applied: remediationAppliedTrend.data_points[i]?.value || 0,
    })) : [];
  const verificationTrendData = verificationVerifiedTrend && verificationFailedTrend ?
    verificationVerifiedTrend.data_points.map((point, i) => ({
      date: point.label || point.timestamp.split('T')[0],
      verified: point.value,
      failed: verificationFailedTrend.data_points[i]?.value || 0,
    })) : [];

  const riskScore = metrics.risk.current_risk_score ?? 0;
  const riskBand = riskScore >= 70 ? 'critical' : riskScore >= 50 ? 'high' : riskScore >= 30 ? 'medium' : riskScore > 0 ? 'low' : 'informational';

  const stats = [
    {
      label: 'Assets Monitored',
      value: metrics.assets.total_assets,
      sub: `${metrics.assets.assets_with_authorization} authorized`,
      icon: GitBranch,
      color: 'text-status-success',
      trend: metrics.assets.assets_with_authorization === metrics.assets.total_assets ? 'good' : 'warning',
    },
    {
      label: 'Open Findings',
      value: openFindingsTotal,
      sub: `${metrics.findings.open_findings_by_severity.critical || 0} critical, ${metrics.findings.open_findings_by_severity.high || 0} high`,
      icon: AlertTriangle,
      color: openFindingsTotal > 0 ? 'text-status-error' : 'text-status-success',
      trend: openFindingsTotal > 0 ? 'bad' : 'good',
    },
    {
      label: 'Risk Score',
      value: riskScore || 'N/A',
      sub: `Band: ${riskBand}`,
      icon: BarChart3,
      color: riskScore > 0 ? `text-[${RISK_BAND_COLORS[riskBand]}]` : 'text-foreground-muted',
      trend: riskScore >= 50 ? 'bad' : riskScore > 0 ? 'warning' : 'good',
    },
    {
      label: 'Active Attack Paths',
      value: metrics.risk.attack_paths_by_status.active || 0,
      sub: `${metrics.risk.total_attack_paths} total paths`,
      icon: TrendingUp,
      color: metrics.risk.attack_paths_by_status.active > 0 ? 'text-status-warning' : 'text-status-success',
      trend: metrics.risk.attack_paths_by_status.active > 0 ? 'bad' : 'good',
    },
  ];

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Security Dashboard</h1>
          <p className="text-gray-500 mt-1">
            Workspace: {currentWorkspace.name} • Data as of {format(new Date(), 'MMM d, yyyy HH:mm')}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={timeRange} onValueChange={handleTimeRangeChange}>
            <SelectTrigger className="w-[160px]">
              <SelectValue placeholder="Time range" />
            </SelectTrigger>
            <SelectContent>
              {timeRangeOptions.map(opt => (
                <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Badge variant={metrics.scans.scans_running > 0 ? 'info' : 'success'} dot>
            {metrics.scans.scans_running > 0 ? 'Scan Running' : 'System Operational'}
          </Badge>
        </div>
      </div>

      {/* Key Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="card-hover">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-gray-500 uppercase tracking-wide">{stat.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-1">{stat.value}</p>
                  <p className="text-xs text-gray-500 mt-1">{stat.sub}</p>
                </div>
                <div className="p-2 rounded-lg bg-accent-glow">
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs">
                <span className={`px-2 py-0.5 rounded-full ${
                  stat.trend === 'good' ? 'bg-green-100 text-green-800' :
                  stat.trend === 'bad' ? 'bg-red-100 text-red-800' :
                  'bg-yellow-100 text-yellow-800'
                }`}>
                  {stat.trend === 'good' && <CheckCircle className="h-3 w-3 mr-1" />}
                  {stat.trend === 'bad' && <AlertCircle className="h-3 w-3 mr-1" />}
                  {stat.trend === 'warning' && <AlertTriangle className="h-3 w-3 mr-1" />}
                  {stat.trend === 'good' ? 'Healthy' : stat.trend === 'bad' ? 'Action Needed' : 'Review'}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Charts Row 1: Findings & Risk */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Findings by Severity Pie Chart */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Open Findings by Severity</CardTitle>
            {openFindingsTotal > 0 && (
              <Button variant="ghost" size="sm" asChild>
                <Link href="/findings?status=open">
                  <Eye className="h-4 w-4 mr-1" />
                  View All
                </Link>
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {openFindingsTotal > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={severityStats.filter(s => s.count > 0)}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      fill="#8884d8"
                      paddingAngle={2}
                      dataKey="count"
                      nameKey="severity"
                      label={({ severity, count, percent }) => `${severity}: ${count} (${(percent * 100).toFixed(0)}%)`}
                      labelLine={false}
                    >
                      {severityStats.filter(s => s.count > 0).map((entry, index) => (
                        <PieCell key={`cell-${index}`} fill={entry.color} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(value: number) => [value, 'findings']} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="CheckCircle"
                  title="No Open Findings"
                  description="All findings have been resolved or triaged."
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Risk Score Trend */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Risk Score Trend</CardTitle>
            <Badge variant={riskScore >= 70 ? 'error' : riskScore >= 50 ? 'warning' : riskScore > 0 ? 'secondary' : 'success'} dot>
              {riskScore > 0 ? riskBand.toUpperCase() : 'NO DATA'}
            </Badge>
          </CardHeader>
          <CardContent>
            {riskTrendData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={riskTrendData}>
                    <defs>
                      <linearGradient id="riskColor" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor={RISK_BAND_COLORS[riskBand]} stopOpacity={0.3} />
                        <stop offset="95%" stopColor={RISK_BAND_COLORS[riskBand]} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                    <YAxis
                      stroke="#9ca3af"
                      fontSize={10}
                      domain={[0, Math.max(100, Math.max(...riskTrendData.map(d => d.value as number)) * 1.2)]}
                      tickFormatter={(value) => value}
                    />
                    <Tooltip
                      formatter={(value: number) => [value, 'Risk Score']}
                      labelFormatter={(date) => `Date: ${date}`}
                    />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke={RISK_BAND_COLORS[riskBand]}
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#riskColor)"
                      name="Risk Score"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="BarChart3"
                  title="No Risk Data"
                  description={metrics.risk.total_attack_paths === 0
                    ? 'Generate attack paths to see risk scores.'
                    : 'Risk snapshots will appear here over time.'}
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2: Scans & Finding Flow */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Scan Status Trend */}
        <Card>
          <CardHeader>
            <CardTitle>Scan Activity</CardTitle>
          </CardHeader>
          <CardContent>
            {scanTrendData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={scanTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                    <YAxis stroke="#9ca3af" fontSize={10} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="completed" name="Completed" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="failed" name="Failed" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="Zap"
                  title="No Scan Data"
                  description="Run scans to see activity trends."
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Finding Flow: New vs Resolved */}
        <Card>
          <CardHeader>
            <CardTitle>Finding Flow</CardTitle>
          </CardHeader>
          <CardContent>
            {findingFlowData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={findingFlowData}>
                    <defs>
                      <linearGradient id="newColor" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="resolvedColor" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                    <YAxis stroke="#9ca3af" fontSize={10} />
                    <Tooltip />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="new"
                      stroke="#ef4444"
                      fillOpacity={1}
                      fill="url(#newColor)"
                      name="New Findings"
                    />
                    <Area
                      type="monotone"
                      dataKey="resolved"
                      stroke="#22c55e"
                      fillOpacity={1}
                      fill="url(#resolvedColor)"
                      name="Resolved Findings"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="TrendingUp"
                  title="No Finding Flow Data"
                  description="Finding trends will appear as scans complete."
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 3: Remediation & Verification */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Remediation Progress */}
        <Card>
          <CardHeader>
            <CardTitle>Remediation Progress</CardTitle>
          </CardHeader>
          <CardContent>
            {remediationTrendData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={remediationTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                    <YAxis stroke="#9ca3af" fontSize={10} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="proposed" name="Proposed" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="approved" name="Approved" fill="#f97316" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="applied" name="Applied" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="Bot"
                  title="No Remediation Data"
                  description="Generate remediations to track progress."
                />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Verification Outcomes */}
        <Card>
          <CardHeader>
            <CardTitle>Verification Outcomes</CardTitle>
          </CardHeader>
          <CardContent>
            {verificationTrendData.length > 0 ? (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={verificationTrendData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis dataKey="date" stroke="#9ca3af" fontSize={10} />
                    <YAxis stroke="#9ca3af" fontSize={10} />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="verified" name="Verified" fill="#22c55e" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="failed" name="Failed" fill="#ef4444" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <div className="h-64 flex items-center justify-center">
                <EmptyState
                  icon="Shield"
                  title="No Verification Data"
                  description="Start verifications to track outcomes."
                />
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Summary Tables */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Asset Summary */}
        <Card>
          <CardHeader>
            <CardTitle>Asset Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Total Assets</span>
                <span className="font-medium">{metrics.assets.total_assets}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Authorized</span>
                <span className="font-medium text-green-600">{metrics.assets.assets_with_authorization}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Unauthorized</span>
                <span className="font-medium text-red-600">{metrics.assets.total_assets - metrics.assets.assets_with_authorization}</span>
              </div>
              <div className="pt-2 border-t">
                <p className="text-xs font-medium text-gray-500 uppercase tracking-wider mb-2">By Criticality</p>
                <div className="space-y-1">
                  {Object.entries(metrics.assets.assets_by_criticality).map(([crit, count]) => (
                    <div key={crit} className="flex justify-between text-sm">
                      <span className="capitalize">{crit}</span>
                      <span className="font-medium">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Scan Summary */}
        <Card>
          <CardHeader>
            <CardTitle>Scan Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-500">Total Scans</span>
                <span className="font-medium">{metrics.scans.total_scans}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Completed</span>
                <span className="font-medium text-green-600">{metrics.scans.scans_completed}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Failed</span>
                <span className="font-medium text-red-600">{metrics.scans.scans_failed}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Running</span>
                <span className="font-medium text-blue-600">{metrics.scans.scans_running}</span>
              </div>
              {metrics.scans.latest_completed_scan_at && (
                <div className="pt-2 border-t text-sm text-gray-500">
                  Latest: {formatDistanceToNow(new Date(metrics.scans.latest_completed_scan_at), { addSuffix: true })}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Verification Summary */}
        <Card>
          <CardHeader>
            <CardTitle>Verification Summary</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {Object.entries(metrics.verification.verification_outcomes).map(([outcome, count]) => (
                <div key={outcome} className="flex justify-between">
                  <span className="text-gray-500">{outcome.replace('_', ' ')}</span>
                  <span className={`font-medium ${VERIFICATION_OUTCOME_COLORS[outcome] ? 'text-' + VERIFICATION_OUTCOME_COLORS[outcome].replace('#', '') : ''}`}>
                    {count}
                  </span>
                </div>
              ))}
              <div className="flex justify-between">
                <span className="text-gray-500">Pending Review</span>
                <span className="font-medium text-yellow-600">{metrics.verification.verification_jobs_by_status.PASSED_PENDING_REVIEW || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">Regression Failures</span>
                <span className="font-medium text-red-600">{metrics.verification.regression_failures}</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Quick Actions */}
      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/assets">
                <Plus className="h-4 w-4 mr-2" /> Add Asset
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/scans">
                <Zap className="h-4 w-4 mr-2" /> Start Scan
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/findings">
                <AlertTriangle className="h-4 w-4 mr-2" /> View Findings
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/reports/new">
                <FileText className="h-4 w-4 mr-2" /> Generate Report
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/reports">
                <Download className="h-4 w-4 mr-2" /> View Reports
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/security-team">
                <Bot className="h-4 w-4 mr-2" /> Security Team
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/verifications">
                <Shield className="h-4 w-4 mr-2" /> Verifications
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
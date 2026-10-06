'use client';

import { useState } from 'react';
import { 
  Zap, Clock, AlertTriangle, CheckCircle, XCircle, Loader2, 
  ChevronRight, ChevronDown, FileText, Code, AlertCircle,
  BarChart2, Download, RefreshCw, X, Brain, Bot, Shield, Sparkles,
  ExternalLink
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Progress } from '@/components/ui/Progress';
import { useWorkspace } from '@/hooks/useWorkspace';
import { useParams, useRouter } from 'next/navigation';
import { api, type Scan, type ScanEvent, type ScanSummary, type Finding, type FindingAiAnalysis, type AiRun, type AiAnalysisStatus } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

interface FindingRowProps {
  finding: Finding;
  aiStatus: AiAnalysisStatus | undefined;
  analyzeMutation: ReturnType<typeof useMutation>;
  isCompleted: boolean;
}

function FindingRow({ finding, aiStatus, analyzeMutation, isCompleted }: FindingRowProps) {
  const [showAiAnalysis, setShowAiAnalysis] = useState(false);
  const config = SEVERITY_CONFIG[finding.severity] || SEVERITY_CONFIG.info;
  
  const hasAnalysis = aiStatus?.has_analysis;
  const isAnalyzing = aiStatus?.status === 'running' || aiStatus?.status === 'queued';
  const analysisFailed = aiStatus?.status === 'failed';

  return (
    <div className="p-4 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
      <div className="flex items-start gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link 
              href={`/findings/${finding.id}`}
              className="font-medium text-foreground-DEFAULT hover:text-accent-DEFAULT transition-colors"
            >
              {finding.title}
            </Link>
            {finding.source_rule_id && (
              <Badge variant="outline" className="text-xs font-mono">{finding.source_rule_id}</Badge>
            )}
          </div>
          <p className="text-sm text-foreground-muted mb-2">{finding.description}</p>
          <div className="flex flex-wrap gap-2 text-xs text-foreground-muted">
            {finding.location?.file && (
              <span className="flex items-center gap-1">
                <FileText className="h-3 w-3" />
                {finding.location.file}:{finding.location.line_start || 0}
              </span>
            )}
            <span className="flex items-center gap-1">
              <Code className="h-3 w-3" />
              {finding.source}
            </span>
            {finding.cwe_ids.length > 0 && (
              <span className="flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                CWE: {finding.cwe_ids.join(', ')}
              </span>
            )}
          </div>
        </div>
        <div className="flex flex-col items-end gap-1">
          <Badge variant="outline" className={config.color}>{config.label}</Badge>
          <span className="text-xs text-foreground-muted font-mono">
            {finding.id.slice(0, 8)}...
          </span>
        </div>
      </div>

      {/* AI Analysis Section */}
      <div className="mt-4 pt-4 border-t border-border-DEFAULT">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            {analysisFailed && (
              <Badge variant="outline" className="text-status-error">
                <AlertTriangle className="h-3 w-3 mr-1" />
                AI Analysis Failed
              </Badge>
            )}
            {hasAnalysis && (
              <Badge variant="outline" className="text-status-success">
                <CheckCircle className="h-3 w-3 mr-1" />
                AI Analysis Available
              </Badge>
            )}
            {isAnalyzing && (
              <Badge variant="outline" className="text-status-warning animate-pulse">
                <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                Analyzing...
              </Badge>
            )}
            {!hasAnalysis && !isAnalyzing && !analysisFailed && (
              <Badge variant="outline" className="text-foreground-muted">
                <Bot className="h-3 w-3 mr-1" />
                Not Analyzed
              </Badge>
            )}
          </div>

          {!hasAnalysis && !isAnalyzing && isCompleted && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => analyzeMutation.mutate(finding.id)}
              disabled={analyzeMutation.isPending}
              className="gap-1"
            >
              <Brain className="h-3 w-3" />
              <Sparkles className="h-3 w-3" />
              Analyze with AI
            </Button>
          )}

          {hasAnalysis && (
            <Link 
              href={`/findings/${finding.id}`}
              className="flex items-center gap-1 text-sm text-accent-DEFAULT hover:underline"
            >
              <Shield className="h-3 w-3" />
              <ExternalLink className="h-3 w-3" />
              View AI Analysis
            </Link>
          )}
        </div>

        {showAiAnalysis && hasAnalysis && (
          <div className="mt-4 p-4 rounded-lg bg-background-tertiary/50 border border-border-DEFAULT">
            <div className="flex items-center gap-2 mb-3 text-xs text-foreground-muted">
              <span className="font-medium text-foreground-DEFAULT">AI-Generated Analysis</span>
              <Badge variant="outline" className="text-accent-DEFAULT">
                <Bot className="h-2 w-2 mr-1" />
                Advisory Only
              </Badge>
            </div>

            <div className="space-y-3 text-sm text-foreground-muted">
              <p><span className="font-medium text-foreground-DEFAULT">Summary:</span> Analysis available - click to view details</p>
              <p><span className="font-medium text-foreground-DEFAULT">Technical Explanation:</span> Analysis available - click to view details</p>
              <p><span className="font-medium text-foreground-DEFAULT">Impact:</span> Analysis available - click to view details</p>
              <div className="flex flex-wrap gap-2">
                <Badge variant="outline">Classification: Available</Badge>
                <Badge variant="outline">Confidence: Available</Badge>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STATUS_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  queued: { label: 'Queued', icon: Clock, color: 'text-status-warning' },
  running: { label: 'Running', icon: Zap, color: 'text-accent-DEFAULT animate-pulse' },
  completed: { label: 'Completed', icon: CheckCircle, color: 'text-status-success' },
  failed: { label: 'Failed', icon: AlertTriangle, color: 'text-status-error' },
  cancelled: { label: 'Cancelled', icon: XCircle, color: 'text-foreground-muted' },
  partial: { label: 'Partial', icon: AlertTriangle, color: 'text-status-warning' },
};

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: 'Critical', color: 'text-status-error', bg: 'bg-status-error/10' },
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10' },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10' },
  low: { label: 'Low', color: 'text-status-info', bg: 'bg-status-info/10' },
  info: { label: 'Info', color: 'text-foreground-muted', bg: 'bg-background-tertiary' },
};

const EVENT_PHASE_ORDER = [
  'initialization',
  'authorization',
  'queued',
  'execution',
  'analysis',
  'semgrep',
  'results_parsing',
  'evidence_storage',
  'completion',
  'cancellation',
  'failure',
];

export default function ScanDetailPage() {
  const { workspaceId } = useWorkspace();
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const scanId = params.id as string;
  const [activeTab, setActiveTab] = useState<'overview' | 'events' | 'findings'>('overview');
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());

  const { data: scan, isLoading: scanLoading, error: scanError } = useQuery({
    queryKey: ['scan', scanId],
    queryFn: () => api.getScan(scanId),
    enabled: !!scanId,
    staleTime: 10 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data as Scan | undefined;
      if (data && ['queued', 'running'].includes(data.status)) {
        return 3000;
      }
      return false;
    },
  });

  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['scan-events', scanId],
    queryFn: () => api.getScanEvents(scanId),
    enabled: !!scanId,
    staleTime: 10 * 1000,
  });

  const { data: summary } = useQuery({
    queryKey: ['scan-summary', scanId],
    queryFn: () => api.getScanSummary(scanId),
    enabled: !!scanId,
    staleTime: 30 * 1000,
  });

  const { data: findings, isLoading: findingsLoading } = useQuery({
    queryKey: ['findings', workspaceId, { scan_id: scanId }],
    queryFn: () => api.listFindings(workspaceId!, { scan_id: scanId }),
    enabled: !!workspaceId && !!scanId,
    staleTime: 30 * 1000,
  });

  // AI Analysis status for all findings in this scan
  const { data: aiAnalysisStatus, refetch: refetchAiStatus } = useQuery({
    queryKey: ['ai-analysis-status', scanId],
    queryFn: () => api.getScanAiAnalysisStatus(scanId),
    enabled: !!scanId && isCompleted,
    staleTime: 30 * 1000,
  });

  // AI Analysis mutation
  const analyzeMutation = useMutation({
    mutationFn: (findingId: string) => api.startFindingAnalysis(scanId, findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ai-analysis-status', scanId] });
    },
  });

  // Get AI analysis for a specific finding
  const getAiAnalysis = useQuery({
    queryKey: ['ai-analysis', ''],
    queryFn: () => Promise.resolve(null),
    enabled: false,
  });

  const isRunning = scan && ['queued', 'running'].includes(scan.status);

  if (scanLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card><CardContent><Skeleton className="h-8 w-1/4" /></CardContent></Card>
        <div className="grid gap-4 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i}><CardContent><Skeleton className="h-20 w-full" /></CardContent></Card>
          ))}
        </div>
      </div>
    );
  }

  if (scanError || !scan) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon="AlertTriangle"
          title="Scan Not Found"
          description="The scan you're looking for doesn't exist or you don't have access to it."
          action={<Button onClick={() => router.push('/scans')}>Back to Scans</Button>}
        />
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[scan.status] || { label: scan.status, icon: AlertTriangle, color: 'text-foreground-muted' };
  const isCompleted = ['completed', 'failed', 'cancelled'].includes(scan.status);

  // Group events by phase
  const eventsByPhase = events?.reduce((acc, event) => {
    if (!acc[event.phase]) acc[event.phase] = [];
    acc[event.phase].push(event);
    return acc;
  }, {} as Record<string, ScanEvent[]>) || {};

  const sortedPhases = Object.keys(eventsByPhase).sort((a, b) => {
    const idxA = EVENT_PHASE_ORDER.indexOf(a);
    const idxB = EVENT_PHASE_ORDER.indexOf(b);
    return (idxA === -1 ? 999 : idxA) - (idxB === -1 ? 999 : idxB);
  });

  const findingsBySeverity = findings?.reduce((acc, finding) => {
    if (!acc[finding.severity]) acc[finding.severity] = [];
    acc[finding.severity].push(finding);
    return acc;
  }, {} as Record<string, Finding[]>) || {};

  const severityOrder = ['critical', 'high', 'medium', 'low', 'info'];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/scans" className="p-2 rounded-lg hover:bg-background-tertiary transition-colors">
            <ChevronRight className="h-5 w-5 rotate-180 text-foreground-muted" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT flex items-center gap-2">
              <Zap className="h-6 w-6 text-accent-DEFAULT" />
              Scan Details
            </h1>
            <p className="text-sm text-foreground-muted mt-1 font-mono">{scan.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-background-tertiary/50">
            <statusConfig.icon className={`h-5 w-5 ${statusConfig.color}`} />
            <span className="font-medium text-foreground-DEFAULT">{statusConfig.label}</span>
          </div>
          {isRunning && (
            <Button variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending} className="text-status-error hover:text-status-error hover:border-status-error">
              <X className="h-4 w-4 mr-2" />
              Cancel Scan
            </Button>
          )}
        </div>
      </div>

      {/* Scan Info Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <Zap className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Profile</p>
                <p className="text-lg font-bold text-foreground-DEFAULT">{scan.scan_profile}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-info/10">
                <FileText className="h-5 w-5 text-status-info" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Type</p>
                <p className="text-lg font-bold text-foreground-DEFAULT capitalize">{scan.scan_type}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-warning/10">
                <Clock className="h-5 w-5 text-status-warning" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Duration</p>
                <p className="text-lg font-bold text-foreground-DEFAULT">
                  {scan.duration_ms ? `${Math.round(scan.duration_ms / 1000)}s` : isRunning ? 'Running...' : '—'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-success/10">
                <BarChart2 className="h-5 w-5 text-status-success" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Total Findings</p>
                <p className="text-lg font-bold text-foreground-DEFAULT">
                  {summary?.findings?.total_findings ?? 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Progress Bar for Running Scans */}
      {isRunning && (
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="flex justify-between text-sm mb-2">
                  <span className="text-foreground-muted">Progress</span>
                  <span className="font-medium text-foreground-DEFAULT">{scan.progress_percent}%</span>
                </div>
                <Progress value={scan.progress_percent} className="h-3" />
                <p className="text-xs text-foreground-muted mt-2">
                  Current phase: <span className="font-medium capitalize">{scan.current_phase?.replace('_', ' ') || 'initializing'}</p>
                </p>
              </div>
              <Button variant="outline" size="sm" onClick={() => queryClient.invalidateQueries({ queryKey: ['scan', scanId] })}>
                <RefreshCw className="h-4 w-4 mr-2" />
                Refresh
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="findings">Findings ({findings?.length ?? 0})</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Scan Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <dl className="space-y-3">
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Asset</dt>
                    <dd className="font-medium text-foreground-DEFAULT truncate max-w-xs">{scan.target_reference || 'N/A'}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Asset Type</dt>
                    <dd className="font-medium text-foreground-DEFAULT capitalize">{scan.target_type}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Triggered By</dt>
                    <dd className="font-medium text-foreground-DEFAULT font-mono text-sm">{scan.triggered_by.slice(0, 8)}...</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-foreground-muted">Triggered At</dt>
                    <dd className="font-medium text-foreground-DEFAULT">{new Date(scan.triggered_at).toLocaleString()}</dd>
                  </div>
                  {scan.started_at && (
                    <div className="flex justify-between">
                      <dt className="text-foreground-muted">Started At</dt>
                      <dd className="font-medium text-foreground-DEFAULT">{new Date(scan.started_at).toLocaleString()}</dd>
                    </div>
                  )}
                  {scan.completed_at && (
                    <div className="flex justify-between">
                      <dt className="text-foreground-muted">Completed At</dt>
                      <dd className="font-medium text-foreground-DEFAULT">{new Date(scan.completed_at).toLocaleString()}</dd>
                    </div>
                  )}
                  {scan.failed_at && (
                    <div className="flex justify-between">
                      <dt className="text-foreground-muted">Failed At</dt>
                      <dd className="font-medium text-status-error">{new Date(scan.failed_at).toLocaleString()}</dd>
                    </div>
                  )}
                  {scan.cancelled_at && (
                    <div className="flex justify-between">
                      <dt className="text-foreground-muted">Cancelled At</dt>
                      <dd className="font-medium text-foreground-muted">{new Date(scan.cancelled_at).toLocaleString()}</dd>
                    </div>
                  )}
                  {scan.authorization_confirmed_at && (
                    <div className="flex justify-between">
                      <dt className="text-foreground-muted">Authorization Confirmed</dt>
                      <dd className="font-medium text-status-success">{new Date(scan.authorization_confirmed_at).toLocaleString()}</dd>
                    </div>
                  )}
                </dl>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Summary</CardTitle>
              </CardHeader>
              <CardContent>
                {summary?.findings ? (
                  <div className="space-y-3">
                    {severityOrder.map(severity => {
                      const count = summary.findings[severity as keyof typeof summary.findings] as number || 0;
                      const config = SEVERITY_CONFIG[severity];
                      return count > 0 ? (
                        <div key={severity} className="flex items-center gap-3 p-3 rounded-lg border border-border-DEFAULT">
                          <div className={`w-2 h-8 rounded ${config.bg}`} />
                          <div className="flex-1">
                            <p className="text-sm font-medium {config.color}">{config.label}</p>
                            <p className="text-xs text-foreground-muted">{count} finding{count !== 1 ? 's' : ''}</p>
                          </div>
                          <Badge variant="outline" className={config.color}>{count}</Badge>
                        </div>
                      ) : null;
                    })}
                    {Object.values(summary.findings).every(v => v === 0) && (
                      <div className="text-center py-8 text-foreground-muted">
                        <CheckCircle className="h-10 w-10 mx-auto mb-2 text-status-success" />
                        <p>No findings detected</p>
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-foreground-muted">Summary not available yet</p>
                )}
              </CardContent>
            </Card>
          </div>

          {scan.error_message && (
            <Card className="border-status-error/30">
              <CardHeader className="text-status-error">
                <CardTitle>Error Details</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="p-4 rounded-lg bg-status-error/10 border border-status-error/30">
                  <p className="font-medium">Error Code: {scan.error_code || 'UNKNOWN'}</p>
                  <p className="mt-2 font-mono text-sm">{scan.error_message}</p>
                </div>
              </CardContent>
            </Card>
          )}

          {isCompleted && !isRunning && (
            <Card>
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-3">
                  <Button asChild variant="outline">
                    <Link href={`/scans/${scan.id}?tab=findings`}>
                      <FileText className="h-4 w-4 mr-2" />
                      View All Findings
                    </Link>
                  </Button>
                  <Button asChild variant="outline">
                    <Link href={`/scans/${scan.id}?tab=events`}>
                      <Code className="h-4 w-4 mr-2" />
                      View Event Timeline
                    </Link>
                  </Button>
                  <Button variant="outline">
                    <Download className="h-4 w-4 mr-2" />
                    Export Results
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Events Tab */}
        <TabsContent value="events" className="space-y-4">
          {eventsLoading ? (
            <Card>
              <CardContent>
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-16 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : events && events.length > 0 ? (
            <div className="space-y-4">
              {sortedPhases.map(phase => (
                <Card key={phase}>
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-sm">
                      <span className="px-2 py-0.5 text-xs rounded bg-background-tertiary text-foreground-muted uppercase">
                        {phase.replace('_', ' ')}
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-2">
                      {eventsByPhase[phase]?.map(event => (
                        <div 
                          key={event.id} 
                          className="flex items-start gap-3 p-3 rounded-lg hover:bg-background-tertiary/50 transition-colors"
                        >
                          <div className="flex-shrink-0 w-10 text-center">
                            <span className="text-xs text-foreground-muted font-mono">
                              {new Date(event.created_at).toLocaleTimeString()}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-foreground-DEFAULT">{event.message}</span>
                              <Badge variant="outline" className="text-xs">{event.event_type}</Badge>
                            </div>
                            {event.data && Object.keys(event.data).length > 0 && (
                              <div className="mt-2">
                                <Button 
                                  variant="ghost" 
                                  size="sm" 
                                  className="text-xs px-2 py-1"
                                  onClick={() => setExpandedEvents(prev => {
                                    const next = new Set(prev);
                                    if (next.has(event.id)) next.delete(event.id);
                                    else next.add(event.id);
                                    return next;
                                  })}
                                >
                                  {expandedEvents.has(event.id) ? (
                                    <>
                                      <ChevronDown className="h-3 w-3 mr-1" />
                                      Hide Details
                                    </>
                                  ) : (
                                    <>
                                      <ChevronRight className="h-3 w-3 mr-1" />
                                      Show Details
                                    </>
                                  )}
                                </Button>
                              )}
                            )}
                            {expandedEvents.has(event.id) && event.data && Object.keys(event.data).length > 0 && (
                              <div className="mt-2 p-3 rounded bg-background-tertiary/50 border border-border-DEFAULT">
                                <pre className="text-xs font-mono text-foreground-muted overflow-x-auto">
                                  {JSON.stringify(event.data, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <EmptyState
                  icon="Clock"
                  title="No Events Yet"
                  description="Scan events will appear here as the scan progresses."
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Findings Tab */}
        <TabsContent value="findings" className="space-y-4">
          {findingsLoading ? (
            <Card>
              <CardContent>
                <div className="space-y-3">
                  {Array.from({ length: 5 }).map((_, i) => (
                    <Skeleton key={i} className="h-20 w-full" />
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : findings && findings.length > 0 ? (
            <div className="space-y-4">
              {severityOrder.map(severity => {
                const severityFindings = findingsBySeverity[severity] || [];
                if (severityFindings.length === 0) return null;
                const config = SEVERITY_CONFIG[severity];
                return (
                  <Card key={severity} className={`border-l-4 ${config.bg.replace('bg-', 'bg-')}`}>
                    <CardHeader className="pb-2">
                      <CardTitle className="flex items-center gap-2">
                        <Badge variant="outline" className={config.color}>{config.label}</Badge>
                        <span className="text-foreground-muted">({severityFindings.length})</span>
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        {severityFindings.map(finding => {
                          const aiStatus = aiAnalysisStatus?.find(s => s.finding_id === finding.id);
                          return (
                            <FindingRow
                              key={finding.id}
                              finding={finding}
                              aiStatus={aiStatus}
                              analyzeMutation={analyzeMutation}
                              isCompleted={isCompleted}
                            />
                          );
                        })}
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <EmptyState
                  icon={scan.status === 'completed' ? "CheckCircle" : "AlertTriangle"}
                  title={scan.status === 'completed' ? "No Findings" : "Scan Not Complete"}
                  description={scan.status === 'completed' 
                    ? "The scan completed successfully with no security issues detected."
                    : "Findings will appear here once the scan completes."}
                />
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
'use client';

import { useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { 
  Shield, Bot, CheckCircle, XCircle, AlertTriangle, Loader2, Clock, 
  ChevronDown, ChevronUp, FileText, AlertTriangle as AlertTriangleIcon,
  Brain, GitBranch, Target, ClipboardList, Eye, RotateCcw, Check
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/Tabs';
import { Separator } from '@/components/ui/Separator';
import { ScrollArea } from '@/components/ui/ScrollArea';
import { api, type SecurityTeamRunResponse, type AgentRunDetailResponse, type TeamAssessmentResponse, type TeamReviewResponse } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow, format } from 'date-fns';
import { clsx } from 'clsx';
import { formatJSON } from '@/lib/utils';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  succeeded: { label: 'Succeeded', color: 'success', icon: CheckCircle },
  partial: { label: 'Partial', color: 'warning', icon: AlertTriangle },
  failed: { label: 'Failed', color: 'error', icon: XCircle },
  running: { label: 'Running', color: 'info', icon: Loader2 },
  queued: { label: 'Queued', color: 'secondary', icon: Clock },
  canceled: { label: 'Canceled', color: 'secondary', icon: XCircle },
};

const AGENT_CONFIG: Record<string, { label: string; icon: React.ComponentType<{ className?: string }>; description: string }> = {
  recon: { label: 'Recon Agent', icon: Shield, description: 'Asset structure & entry points' },
  vulnerability_analyst: { label: 'Vulnerability Analyst', icon: AlertTriangleIcon, description: 'Deep finding analysis' },
  attack_path_analyst: { label: 'Attack Path Analyst', icon: GitBranch, description: 'Finding relationships & paths' },
  risk_analyst: { label: 'Risk Analyst', icon: Target, description: 'Risk score interpretation' },
  security_reviewer: { label: 'Security Reviewer', icon: ClipboardList, description: 'Final assessment synthesis' },
};

const AGENT_ORDER = [
  'recon',
  'vulnerability_analyst',
  'attack_path_analyst',
  'risk_analyst',
  'security_reviewer',
];

function AgentStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || { label: status, color: 'secondary', icon: Clock };
  const Icon = config.icon;
  return (
    <Badge variant={config.color as any} dot className="gap-1">
      <Icon className="h-3 w-3" />
      {config.label}
    </Badge>
  );
}

function CollapsibleSection({ 
  title, 
  icon: Icon, 
  children, 
  status, 
  confidence,
  duration,
  provider,
  model,
  promptVersion,
}: { 
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
  status: string;
  confidence?: number | null;
  duration?: number | null;
  provider?: string | null;
  model?: string | null;
  promptVersion?: string | null;
}) {
  const [open, setOpen] = useState(false);
  const statusConfig = STATUS_CONFIG[status] || { label: status, color: 'secondary', icon: Clock };
  const StatusIcon = statusConfig.icon;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-2 cursor-pointer" onClick={() => setOpen(!open)}>
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-accent-glow">
            <Icon className="h-5 w-5 text-accent-DEFAULT" />
          </div>
          <div className="flex-1">
            <h3 className="font-medium text-foreground-DEFAULT">{title}</h3>
            <div className="flex items-center gap-2 text-sm text-foreground-muted">
              <AgentStatusBadge status={status} />
              {confidence !== null && confidence !== undefined && (
                <span>Confidence: {Math.round(confidence * 100)}%</span>
              )}
              {duration && <span>Duration: {duration < 1000 ? `${duration}ms` : `${(duration / 1000).toFixed(1)}s`}</span>}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {provider && model && (
              <Badge variant="outline" className="text-xs">{provider} / {model}</Badge>
            )}
            {promptVersion && <Badge variant="secondary" className="text-xs">{promptVersion}</Badge>}
            <Icon 
              className={clsx('h-5 w-5 text-foreground-muted transition-transform', open && 'rotate-180')} 
            />
          </div>
        </div>
      </CardHeader>
      {open && (
        <CardContent className="pt-0">
          <Separator />
          <div className="space-y-4">{children}</div>
        </CardContent>
      )}
    </Card>
  );
}

function JsonDisplay({ data, title }: { data: any; title?: string }) {
  return (
    <div className="space-y-2">
      {title && <h4 className="text-sm font-medium text-foreground-muted">{title}</h4>}
      <pre className="bg-background-tertiary p-4 rounded-lg text-xs overflow-x-auto font-mono text-foreground-DEFAULT max-h-96 overflow-y-auto">
        {formatJSON(data, 2)}
      </pre>
    </div>
  );
}

export default function SecurityTeamRunDetailPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const runId = params.id as string;

  const { data: run, isLoading: runLoading, error: runError } = useQuery({
    queryKey: ['security-team-run', runId],
    queryFn: () => api.get(`/security-team/runs/${runId}`),
    staleTime: 10 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data as SecurityTeamRunResponse | undefined;
      if (!data) return false;
      return ['queued', 'running'].includes(data.status) ? 5000 : false;
    },
  });

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['security-team-agents', runId],
    queryFn: () => api.get(`/security-team/runs/${runId}/agents`),
    enabled: !!run,
    staleTime: 30 * 1000,
  });

  const { data: assessment, isLoading: assessmentLoading } = useQuery({
    queryKey: ['security-team-assessment', runId],
    queryFn: () => api.get(`/security-team/runs/${runId}/assessment`),
    enabled: !!run && (run.status === 'succeeded' || run.status === 'partial'),
    staleTime: 30 * 1000,
  });

  const reviewMutation = useMutation({
    mutationFn: (notes: string) => api.post(`/security-team/runs/${runId}/review`, { notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-team-run', runId] });
      queryClient.invalidateQueries({ queryKey: ['security-team-assessment', runId] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: () => api.post(`/security-team/runs/${runId}/cancel`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-team-run', runId] });
      queryClient.invalidateQueries({ queryKey: ['security-team-agents', runId] });
    },
  });

  if (runLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card><CardContent><Skeleton className="h-8 w-1/4" /></CardContent></Card>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i}><CardContent><Skeleton className="h-40 w-full" /></CardContent></Card>
          ))}
        </div>
      </div>
    );
  }

  if (runError || !run) {
    return (
      <div className="text-center py-12">
        <Shield className="h-12 w-12 text-foreground-muted mx-auto mb-4" />
        <h2 className="text-xl font-medium text-foreground-DEFAULT mb-2">Team Run Not Found</h2>
        <p className="text-foreground-muted mb-4">The requested security team run could not be found.</p>
        <Button onClick={() => router.push('/security-team')}>Back to Team Runs</Button>
      </div>
    );
  }

  const statusConfig = STATUS_CONFIG[run.status] || { label: run.status, color: 'secondary', icon: Clock };
  const StatusIcon = statusConfig.icon;

  const startedAt = run.started_at ? new Date(run.started_at) : null;
  const completedAt = run.completed_at ? new Date(run.completed_at) : null;
  const duration = startedAt && completedAt 
    ? Math.round((completedAt.getTime() - startedAt.getTime()) / 1000)
    : startedAt 
      ? Math.round((Date.now() - startedAt.getTime()) / 1000)
      : null;

  const handleReview = async () => {
    const notes = prompt('Review notes (optional):');
    if (notes !== null) {
      await reviewMutation.mutateAsync(notes);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <Link 
            href="/security-team" 
            className="text-sm text-foreground-muted hover:text-foreground-DEFAULT mb-2 inline-flex items-center gap-1"
          >
            <ChevronUp className="h-4 w-4" />
            Back to Team Runs
          </Link>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-foreground-DEFAULT">Security Team Run</h1>
            <Badge variant={statusConfig.color as any} dot className="gap-1">
              <StatusIcon className="h-3 w-3" />
              {statusConfig.label}
            </Badge>
            {run.status === 'succeeded' && (
              <Badge variant="success" dot>
                <Check className="h-3 w-3" />
                Human Review Required
              </Badge>
            )}
          </div>
        </div>
        <div className="flex gap-2">
          {run.status === 'running' || run.status === 'queued' ? (
            <Button variant="outline" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
              <XCircle className="h-4 w-4 mr-2" />
              Cancel
            </Button>
          ) : run.status === 'succeeded' || run.status === 'partial' ? (
            <Button onClick={handleReview} disabled={reviewMutation.isPending}>
              <ClipboardList className="h-4 w-4 mr-2" />
              Mark as Reviewed
            </Button>
          ) : null}
          <Button variant="outline" onClick={() => queryClient.invalidateQueries({ queryKey: ['security-team-run', runId] })}>
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Metadata Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <Shield className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-sm text-foreground-muted">Asset</p>
                <p className="font-mono text-sm text-foreground-DEFAULT">{run.asset_id.toString().slice(0, 12)}...</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <GitBranch className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-sm text-foreground-muted">Scan</p>
                <p className="font-mono text-sm text-foreground-DEFAULT">{run.scan_id.toString().slice(0, 12)}...</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <Clock className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-sm text-foreground-muted">Duration</p>
                <p className="font-mono text-sm text-foreground-DEFAULT">
                  {duration !== null ? (duration < 60 ? `${duration}s` : `${Math.round(duration / 60)}m ${duration % 60}s`) : '—'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <Brain className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-sm text-foreground-muted">Confidence</p>
                <p className="font-mono text-sm text-foreground-DEFAULT">
                  {run.confidence !== null ? `${Math.round(run.confidence * 100)}%` : '—'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-6">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="agents">Agents ({AGENT_ORDER.length})</TabsTrigger>
          <TabsTrigger value="assessment" disabled={run.status !== 'succeeded' && run.status !== 'partial'}>
            Assessment
          </TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="raw">Raw Data</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Team Summary</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div>
                  <p className="text-sm text-foreground-muted">Orchestration Version</p>
                  <p className="font-mono text-foreground-DEFAULT">{run.orchestration_version}</p>
                </div>
                <div>
                  <p className="text-sm text-foreground-muted">Requested By</p>
                  <p className="font-mono text-foreground-DEFAULT">{run.requested_by.toString().slice(0, 12)}...</p>
                </div>
                <div>
                  <p className="text-sm text-foreground-muted">Created</p>
                  <p className="text-foreground-DEFAULT">{format(new Date(run.created_at), 'PPpp')}</p>
                </div>
              </div>
              
              {run.team_summary && Object.keys(run.team_summary).length > 0 && (
                <div>
                  <p className="text-sm text-foreground-muted mb-2">Execution Summary</p>
                  <JsonDisplay data={run.team_summary} />
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                {AGENT_ORDER.map((agentKey) => {
                  const agent = agents?.find(a => a.agent_name === agentKey);
                  const config = AGENT_CONFIG[agentKey];
                  const Icon = config.icon;
                  return (
                    <Badge 
                      key={agentKey} 
                      variant={agent ? (agent.status === 'succeeded' ? 'success' : agent.status === 'failed' ? 'error' : 'secondary') : 'outline'}
                      className="gap-1"
                    >
                      <Icon className="h-3 w-3" />
                      {config.label}
                    </Badge>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {assessment && (
            <Card>
              <CardHeader>
                <CardTitle>Final Assessment Summary</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div>
                  <p className="text-sm text-foreground-muted mb-2">Executive Summary</p>
                  <p className="text-foreground-DEFAULT">{assessment.executive_summary}</p>
                </div>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <p className="text-sm text-foreground-muted mb-2">Key Security Concerns ({assessment.key_security_concerns?.length || 0})</p>
                    <ul className="space-y-1">
                      {assessment.key_security_concerns?.map((concern, i) => (
                        <li key={i} className="text-sm text-foreground-DEFAULT flex items-center gap-2">
                          <AlertTriangleIcon className="h-4 w-4 text-status-warning flex-shrink-0" />
                          {concern}
                        </li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <p className="text-sm text-foreground-muted mb-2">Recommended Human Actions ({assessment.recommended_human_actions?.length || 0})</p>
                    <ul className="space-y-1">
                      {assessment.recommended_human_actions?.map((action, i) => (
                        <li key={i} className="text-sm text-foreground-DEFAULT flex items-center gap-2">
                          <Check className="h-4 w-4 text-status-success flex-shrink-0" />
                          {action}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-foreground-muted">Overall Confidence:</span>
                  <span className="font-mono text-foreground-DEFAULT">{Math.round(assessment.overall_confidence * 100)}%</span>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Agents Tab */}
        <TabsContent value="agents" className="space-y-4">
          {agentsLoading ? (
            <div className="space-y-4">
              {AGENT_ORDER.map((_, i) => (
                <Card key={i}><CardContent><Skeleton className="h-32 w-full" /></CardContent></Card>
              ))}
            </div>
          ) : (
            <>
              <div className="space-y-2 text-sm text-foreground-muted">
                <p>Agents execute in dependency order. Failed agents block downstream agents.</p>
                <p className="text-xs">Status: <strong>Queued</strong> → <strong>Running</strong> → <strong>Succeeded/Failed/Blocked</strong></p>
              </div>
              <div className="space-y-4">
                {AGENT_ORDER.map((agentKey) => {
                  const agent = agents?.find(a => a.agent_name === agentKey);
                  const config = AGENT_CONFIG[agentKey];
                  const Icon = config.icon;

                  if (!agent) {
                    return (
                      <Card key={agentKey} className="opacity-50">
                        <CardContent className="py-4">
                          <div className="flex items-center gap-3 text-foreground-muted">
                            <div className="p-2 rounded-lg bg-background-tertiary">
                              <Icon className="h-5 w-5" />
                            </div>
                            <div>
                              <p className="font-medium">{config.label}</p>
                              <p className="text-sm">Not yet scheduled</p>
                            </div>
                          </div>
                        </CardContent>
                      </Card>
                    );
                  }

                  const output = agent.output || {};

                  return (
                    <CollapsibleSection
                      key={agentKey}
                      title={config.label}
                      icon={Icon}
                      status={agent.status}
                      confidence={agent.confidence}
                      duration={agent.duration}
                      provider={agent.provider}
                      model={agent.model}
                      promptVersion={agent.prompt_version}
                    >
                      <div className="grid gap-4 md:grid-cols-2">
                        <div>
                          <h4 className="text-sm font-medium text-foreground-muted mb-2">Summary</h4>
                          <p className="text-foreground-DEFAULT">{agent.output?.summary || 'No summary available'}</p>
                        </div>
                        {agent.confidence !== null && agent.confidence !== undefined && (
                          <div>
                            <h4 className="text-sm font-medium text-foreground-muted mb-2">Confidence</h4>
                            <div className="w-48 h-2 bg-background-tertiary rounded-full overflow-hidden">
                              <div 
                                className="h-full bg-accent-DEFAULT" 
                                style={{ width: `${Math.round(agent.confidence * 100)}%` }}
                              />
                            </div>
                          </div>
                        )}
                      </div>

                      {agent.error_message && (
                        <div className="p-3 rounded-lg bg-status-error/10 border border-status-error/20">
                          <p className="text-sm text-status-error font-medium">Error: {agent.error_code}</p>
                          <p className="text-sm text-foreground-muted mt-1">{agent.error_message}</p>
                        </div>
                      )}

                      <div className="space-y-4">
                        {agentKey === 'recon' && output.structured_output && (
                          <>
                            <JsonDisplay 
                              data={output.structured_output.relevant_components} 
                              title="Relevant Components" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.entry_points} 
                              title="Entry Points" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.security_boundaries} 
                              title="Security Boundaries" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.exposed_areas} 
                              title="Exposed Areas" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.observations} 
                              title="Observations" 
                            />
                          </>
                        )}
                        {agentKey === 'vulnerability_analyst' && output.structured_output && (
                          <>
                            <JsonDisplay 
                              data={output.structured_output.findings_analyzed} 
                              title="Findings Analyzed" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.interpretations} 
                              title="Vulnerability Interpretations" 
                            />
                          </>
                        )}
                        {agentKey === 'attack_path_analyst' && output.structured_output && (
                          <>
                            <JsonDisplay 
                              data={output.structured_output.candidate_relationships} 
                              title="Candidate Relationships" 
                            />
                            <JsonDisplay 
                              data={output.structured_output.path_observations} 
                              title="Path Observations" 
                            />
                          </>
                        )}
                        {agentKey === 'risk_analyst' && output.structured_output && (
                          <>
                            <div className="space-y-2">
                              <h4 className="text-sm font-medium text-foreground-muted">Risk Interpretation</h4>
                              <p className="text-foreground-DEFAULT">{output.structured_output.explanation}</p>
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Important Factors</h4>
                              <JsonDisplay data={output.structured_output.important_factors} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Review Priorities</h4>
                              <JsonDisplay data={output.structured_output.recommended_review_priorities} />
                            </div>
                          </>
                        )}
                        {agentKey === 'security_reviewer' && output.structured_output && (
                          <>
                            <div className="space-y-2">
                              <h4 className="text-sm font-medium text-foreground-muted">Executive Summary</h4>
                              <p className="text-foreground-DEFAULT">{output.structured_output.executive_summary}</p>
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Key Security Concerns</h4>
                              <JsonDisplay data={output.structured_output.key_security_concerns} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Highest Priority Findings</h4>
                              <JsonDisplay data={output.structured_output.highest_priority_findings} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Highest Priority Attack Paths</h4>
                              <JsonDisplay data={output.structured_output.highest_priority_attack_paths} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Uncertainties</h4>
                              <JsonDisplay data={output.structured_output.uncertainties} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Conflicting Assessments</h4>
                              <JsonDisplay data={output.structured_output.conflicting_assessments} />
                              <h4 className="text-sm font-medium text-foreground-muted mt-4">Recommended Human Actions</h4>
                              <JsonDisplay data={output.structured_output.recommended_human_actions} />
                            </div>
                          </>
                        )}
                      </div>
                    </CollapsibleSection>
                  );
                })}
              </div>
            </>
          )}
        </TabsContent>

        {/* Assessment Tab */}
        <TabsContent value="assessment" className="space-y-6">
          {assessmentLoading ? (
            <Card><CardContent><Skeleton className="h-64 w-full" /></CardContent></Card>
          ) : assessment ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>Executive Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-foreground-DEFAULT whitespace-pre-wrap">{assessment.executive_summary}</p>
                </CardContent>
              </Card>

              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Key Security Concerns</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {assessment.key_security_concerns?.map((concern, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <AlertTriangleIcon className="h-4 w-4 text-status-warning flex-shrink-0 mt-0.5" />
                          <span className="text-foreground-DEFAULT">{concern}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Recommended Human Actions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ol className="space-y-2">
                      {assessment.recommended_human_actions?.map((action, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <span className="font-mono text-accent-DEFAULT flex-shrink-0">{i + 1}.</span>
                          <span className="text-foreground-DEFAULT">{action}</span>
                        </li>
                      ))}
                    </ol>
                  </CardContent>
                </Card>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                <Card>
                  <CardHeader>
                    <CardTitle>Highest Priority Findings</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {assessment.highest_priority_findings?.length === 0 ? (
                      <p className="text-foreground-muted text-sm">No priority findings identified</p>
                    ) : (
                      <div className="space-y-3">
                        {assessment.highest_priority_findings?.map((finding, i) => (
                          <Card key={i} className="p-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground-DEFAULT truncate">{finding.title}</p>
                                <div className="flex items-center gap-2 text-xs text-foreground-muted mt-1">
                                  <Badge variant="outline">{finding.severity}</Badge>
                                  <span>AI Confidence: {Math.round(finding.ai_confidence * 100)}%</span>
                                </div>
                                <p className="text-sm text-foreground-muted mt-1">{finding.reason}</p>
                              </div>
                              <Button variant="ghost" size="sm" onClick={() => router.push(`/findings/${finding.finding_id}`)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </div>
                          </Card>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle>Highest Priority Attack Paths</CardTitle>
                  </CardHeader>
                  <CardContent>
                    {assessment.highest_priority_attack_paths?.length === 0 ? (
                      <p className="text-foreground-muted text-sm">No priority attack paths identified</p>
                    ) : (
                      <div className="space-y-3">
                        {assessment.highest_priority_attack_paths?.map((path, i) => (
                          <Card key={i} className="p-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="flex-1 min-w-0">
                                <p className="font-medium text-foreground-DEFAULT truncate">{path.title}</p>
                                <div className="flex items-center gap-2 text-xs text-foreground-muted mt-1">
                                  <Badge variant="outline">{path.risk_band}</Badge>
                                  <span>Risk Score: {path.risk_score}/100</span>
                                </div>
                                <p className="text-sm text-foreground-muted mt-1">{path.reason}</p>
                              </div>
                              <Button variant="ghost" size="sm" onClick={() => router.push(`/attack-paths/${path.attack_path_id}`)}>
                                <Eye className="h-4 w-4" />
                              </Button>
                            </div>
                          </Card>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Risk Interpretation</CardTitle>
                </CardHeader>
                <CardContent>
                  <p className="text-foreground-DEFAULT whitespace-pre-wrap">{assessment.risk_interpretation}</p>
                </CardContent>
              </Card>

              {assessment.uncertainties && assessment.uncertainties.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Uncertainties</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <ul className="space-y-2">
                      {assessment.uncertainties?.map((uncertainty, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <AlertTriangleIcon className="h-4 w-4 text-status-warning flex-shrink-0 mt-0.5" />
                          <span className="text-foreground-DEFAULT">{uncertainty}</span>
                        </li>
                      ))}
                    </ul>
                  </CardContent>
                </Card>
              )}

              {assessment.conflicting_assessments && assessment.conflicting_assessments.length > 0 && (
                <Card>
                  <CardHeader>
                    <CardTitle>Conflicting Assessments</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      {assessment.conflicting_assessments?.map((conflict, i) => (
                        <Card key={i} className="p-3 border-status-warning/20">
                          <div className="flex items-start gap-2">
                            <AlertTriangleIcon className="h-4 w-4 text-status-warning flex-shrink-0 mt-0.5" />
                            <div className="flex-1 text-sm">
                              <p className="font-medium text-foreground-DEFAULT">
                                {conflict.agent_a} (conf: {Math.round(conflict.agent_a_confidence * 100)}%) vs {conflict.agent_b} (conf: {Math.round(conflict.agent_b_confidence * 100)}%)
                              </p>
                              <p className="text-foreground-muted mt-1">{conflict.description}</p>
                              <p className="text-xs text-foreground-muted mt-1">Finding/Path: {conflict.finding_or_path_id}</p>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="flex items-center gap-4 p-4 bg-background-tertiary rounded-lg">
                <Brain className="h-6 w-6 text-accent-DEFAULT" />
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Overall Confidence: <span className="font-mono">{Math.round(assessment.overall_confidence * 100)}%</span></p>
                  <p className="text-xs text-foreground-muted">
                    {assessment.deterministic_risk_score_referenced !== null && assessment.deterministic_risk_score_referenced !== undefined
                      ? `Deterministic risk score referenced: ${assessment.deterministic_risk_score_referenced}/100`
                      : 'No deterministic risk score referenced'}
                  </p>
                </div>
              </div>
            </>
          ) : (
            <Card>
              <CardContent className="py-12 text-center">
                <Shield className="h-12 w-12 text-foreground-muted mx-auto mb-4" />
                <h3 className="text-lg font-medium text-foreground-DEFAULT mb-2">Assessment Not Available</h3>
                <p className="text-foreground-muted mb-4">
                  The Security Reviewer agent has not completed yet, or the team run did not succeed.
                </p>
                <p className="text-sm text-foreground-muted">
                  Status: {run.status} • Assessment requires all 5 agents to complete successfully.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Execution Timeline</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {agents?.map((agent, index) => {
                  const config = AGENT_CONFIG[agent.agent_name];
                  const Icon = config.icon;
                  const startedAt = agent.started_at ? new Date(agent.started_at) : null;
                  const completedAt = agent.completed_at ? new Date(agent.completed_at) : null;
                  const agentDuration = startedAt && completedAt 
                    ? completedAt.getTime() - startedAt.getTime()
                    : null;

                  return (
                    <div key={agent.agent_name} className="flex items-start gap-4">
                      <div className="flex flex-col items-center flex-shrink-0">
                        <div className={clsx(
                          'w-3 h-3 rounded-full border-2 transition-colors',
                          agent.status === 'succeeded' && 'bg-status-success border-status-success',
                          agent.status === 'failed' && 'bg-status-error border-status-error',
                          agent.status === 'running' && 'bg-accent-DEFAULT border-accent-DEFAULT animate-pulse',
                          agent.status === 'queued' && 'bg-foreground-muted border-foreground-muted',
                          agent.status === 'blocked' && 'bg-status-warning border-status-warning',
                          agent.status === 'canceled' && 'bg-foreground-muted border-foreground-muted',
                        )} />
                        {index < AGENT_ORDER.length - 1 && (
                          <div className="w-0.5 h-8 bg-border-DEFAULT mt-1" />
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <div className="p-1.5 rounded-lg bg-accent-glow">
                            <Icon className="h-4 w-4 text-accent-DEFAULT" />
                          </div>
                          <div>
                            <p className="font-medium text-foreground-DEFAULT">{config.label}</p>
                            <p className="text-sm text-foreground-muted">{config.description}</p>
                          </div>
                          <AgentStatusBadge status={agent.status} />
                        </div>
                        <div className="flex items-center gap-4 mt-2 ml-10 text-sm text-foreground-muted">
                          {startedAt && (
                            <span>Started: {format(startedAt, 'HH:mm:ss')}</span>
                          )}
                          {completedAt && (
                            <span>Completed: {format(completedAt, 'HH:mm:ss')}</span>
                          )}
                          {agentDuration !== null && (
                            <span>Duration: {agentDuration < 1000 ? `${agentDuration}ms` : `${(agentDuration / 1000).toFixed(1)}s`}</span>
                          )}
                          {agent.attempt > 0 && (
                            <span className="text-status-warning">Retries: {agent.attempt}</span>
                          )}
                          {agent.error_message && (
                            <span className="text-status-error">Error: {agent.error_message}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Raw Data Tab */}
        <TabsContent value="raw" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Team Run (Raw)</CardTitle>
            </CardHeader>
            <CardContent>
              <JsonDisplay data={run} />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Agent Runs (Raw)</CardTitle>
            </CardHeader>
            <CardContent>
              <JsonDisplay data={agents} />
            </CardContent>
          </Card>
          {assessment && (
            <Card>
              <CardHeader>
                <CardTitle>Assessment (Raw)</CardTitle>
              </CardHeader>
              <CardContent>
                <JsonDisplay data={assessment} />
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

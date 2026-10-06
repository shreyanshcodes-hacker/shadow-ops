'use client';

import { useState } from 'react';
import {
  Zap, AlertTriangle, CheckCircle, XCircle, Loader2,
  ChevronRight, ChevronDown, FileText, Code, AlertCircle,
  BarChart2, Download, RefreshCw, X, Brain, Bot, Shield, Sparkles,
  Info, AlertCircle as AlertCircleIcon, Flag, Target, Search,
  GitBranch, Link as LinkIcon, Eye, EyeOff, Trash2, Check
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
import { api, type Scan, type ScanEvent, type ScanSummary, type Finding, type FindingAiAnalysis, type AiRun, type AiAnalysisStatus, type FindingRelationship, type AttackPath, type AttackPathNode, type AttackPathEdge, type RiskCalculationResult, type RiskFactor, type RiskSnapshot, type RiskBand } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

const SEVERITY_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  critical: { label: 'Critical', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertTriangle },
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertTriangle },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10', icon: AlertCircle },
  low: { label: 'Low', color: 'text-status-info', bg: 'bg-status-info/10', icon: Info },
  info: { label: 'Info', color: 'text-foreground-muted', bg: 'bg-background-tertiary', icon: Info },
};

const RISK_BAND_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: 'Critical', color: 'text-status-error', bg: 'bg-status-error/10' },
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10' },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10' },
  low: { label: 'Low', color: 'text-status-info', bg: 'bg-status-info/10' },
  informational: { label: 'Informational', color: 'text-foreground-muted', bg: 'bg-background-tertiary' },
};

const NODE_TYPE_CONFIG: Record<string, { label: string; color: string; bg: string; icon: React.ComponentType<{ className?: string }> }> = {
  entry: { label: 'Entry Point', color: 'text-status-info', bg: 'bg-status-info/10', icon: Flag },
  finding: { label: 'Finding', color: 'text-accent-DEFAULT', bg: 'bg-accent-DEFAULT/10', icon: AlertCircle },
  boundary: { label: 'Boundary', color: 'text-status-warning', bg: 'bg-status-warning/10', icon: Shield },
  impact: { label: 'Impact', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertTriangle },
};

const RELATIONSHIP_TYPE_LABELS: Record<string, string> = {
  depends_on: 'Depends On',
  enables: 'Enables',
  exposes: 'Exposes',
  leads_to: 'Leads To',
  shares_component: 'Shares Component',
  shares_entry_point: 'Shares Entry Point',
  shares_data_flow: 'Shares Data Flow',
  amplifies: 'Amplifies',
};

const SOURCE_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  deterministic: { label: 'Deterministic', color: 'text-status-success', bg: 'bg-status-success/10' },
  ai_suggested: { label: 'AI Suggested', color: 'text-accent-DEFAULT', bg: 'bg-accent-DEFAULT/10' },
  human_confirmed: { label: 'Human Confirmed', color: 'text-status-info', bg: 'bg-status-info/10' },
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  const percentage = Math.round(confidence * 100);
  let color = 'bg-status-error';
  if (percentage >= 80) color = 'bg-status-success';
  else if (percentage >= 60) color = 'bg-status-warning';
  else if (percentage >= 40) color = 'bg-status-info';

  return (
    <div className="w-full max-w-xs">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-foreground-muted">Confidence</span>
        <span className="font-mono font-medium">{percentage}%</span>
      </div>
      <div className="h-2 bg-background-tertiary rounded-full overflow-hidden">
        <div className={`${color} h-full rounded-full transition-all`} style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

function RiskScoreDisplay({ score, riskBand }: { score: number | null; riskBand: RiskBand | null }) {
  if (score === null) {
    return (
      <div className="text-center py-4">
        <p className="text-3xl font-bold text-foreground-muted">—</p>
        <p className="text-xs text-foreground-muted">Not Calculated</p>
      </div>
    );
  }

  const band = riskBand || 'informational';
  const config = RISK_BAND_CONFIG[band];

  return (
    <div className="text-center py-4">
      <div className="flex items-center justify-center gap-2 mb-2">
        <span className="text-4xl font-bold text-foreground-DEFAULT">{score}</span>
        <Badge variant="outline" className={clsx(config.color, config.bg)}>
          {config.label}
        </Badge>
      </div>
      <Progress value={score} className="h-3 max-w-xs mx-auto" />
    </div>
  );
}

function RelationshipBadge({ type, source, confidence }: { type: string; source: string; confidence: number }) {
  const typeLabel = RELATIONSHIP_TYPE_LABELS[type] || type;
  const sourceConfig = SOURCE_CONFIG[source] || SOURCE_CONFIG.deterministic;
  const percentage = Math.round(confidence * 100);

  return (
    <div className="flex items-center gap-2 px-2 py-1 rounded border border-border-DEFAULT">
      <Badge variant="outline" className={clsx(sourceConfig.color, sourceConfig.bg)}>
        {sourceConfig.label}
      </Badge>
      <span className="text-xs font-mono text-foreground-muted">{typeLabel}</span>
      <span className="text-xs text-foreground-muted font-mono">{percentage}%</span>
    </div>
  );
}

function AttackPathGraph({ nodes, edges }: { nodes: AttackPathNode[]; edges: AttackPathEdge[] }) {
  if (!nodes.length) {
    return <p className="text-center text-foreground-muted py-8">No nodes in path</p>;
  }

  return (
    <div className="space-y-4">
      {nodes.map((node, index) => {
        const nodeConfig = NODE_TYPE_CONFIG[node.node_type] || NODE_TYPE_CONFIG.finding;
        const NodeIcon = nodeConfig.icon;
        const outgoingEdges = edges.filter(e => e.source_node_id === node.id);
        
        return (
          <div key={node.id} className="relative">
            {/* Node */}
            <div className="flex items-center gap-3">
              {/* Vertical line connector */}
              {index < nodes.length - 1 && (
                <div className="absolute left-6 top-10 bottom-0 w-0.5 bg-border-DEFAULT/50" style={{ zIndex: 0 }} />
              )}
              <div className="relative flex items-center gap-3" style={{ zIndex: 1 }}>
                <div className={clsx('flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center', nodeConfig.bg)}>
                  <NodeIcon className={clsx('h-5 w-5', nodeConfig.color)} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-foreground-DEFAULT">
                      {node.finding?.title || `${nodeConfig.label} ${node.sequence + 1}`}
                    </span>
                    <Badge variant="outline" className={clsx('text-xs', nodeConfig.color)}>
                      {nodeConfig.label}
                    </Badge>
                  </div>
                  {node.rationale && (
                    <p className="text-xs text-foreground-muted truncate">{node.rationale}</p>
                  )}
                  {node.finding && (
                    <div className="flex items-center gap-2 text-xs text-foreground-muted mt-1">
                      <Badge variant="outline" className="text-xs">
                        {node.finding.severity}
                      </Badge>
                      {node.finding.location?.file && (
                        <span className="font-mono truncate max-w-xs">{node.finding.location.file}</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Edge labels */}
            {outgoingEdges.length > 0 && (
              <div className="ml-14 mt-2 space-y-1">
                {outgoingEdges.map((edge, edgeIndex) => {
                  const edgeConfig = RELATIONSHIP_TYPE_LABELS[edge.relationship_type] || edge.relationship_type;
                  const sourceConfig = SOURCE_CONFIG[edge.source] || SOURCE_CONFIG.deterministic;
                  
                  return (
                    <div key={edge.id} className="flex items-center gap-2 text-xs">
                      <div className="w-4 h-0.5 bg-border-DEFAULT" />
                      <div className="flex items-center gap-1">
                        <span className={clsx('px-1.5 py-0.5 rounded text-[10px]', sourceConfig.bg, sourceConfig.color)}>
                          {sourceConfig.label}
                        </span>
                        <span className="text-foreground-muted">{edgeConfig}</span>
                        <span className="text-foreground-muted font-mono">{Math.round(edge.confidence * 100)}%</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function TextualAttackPath({ nodes, edges }: { nodes: AttackPathNode[]; edges: AttackPathEdge[] }) {
  return (
    <div className="space-y-2 text-sm">
      {nodes.map((node, index) => {
        const nodeConfig = NODE_TYPE_CONFIG[node.node_type] || NODE_TYPE_CONFIG.finding;
        const outgoingEdges = edges.filter(e => e.source_node_id === node.id);
        
        return (
          <div key={node.id} className="flex items-center gap-2 p-2 rounded bg-background-tertiary/50">
            <span className="flex-shrink-0 w-6 text-center text-foreground-muted font-mono">{index + 1}.</span>
            <NodeIcon className={clsx('h-4 w-4', nodeConfig.color)} />
            <span className="font-medium text-foreground-DEFAULT">
              {node.finding?.title || `${nodeConfig.label} ${node.sequence + 1}`}
            </span>
            <Badge variant="outline" className={clsx('text-xs', nodeConfig.color)}>
              {nodeConfig.label}
            </Badge>
            {outgoingEdges.length > 0 && (
              <span className="flex-1 text-right text-foreground-muted">
                → {outgoingEdges.map(e => RELATIONSHIP_TYPE_LABELS[e.relationship_type] || e.relationship_type).join(', ')}
              </span>
            )}
          </div>
        );
      })}
    </div>
  );
}

function RiskFactorsBreakdown({ factors }: { factors: RiskFactor[] }) {
  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-foreground-DEFAULT">Risk Factors</h4>
      <div className="space-y-2">
        {factors.map((factor, idx) => (
          <div key={idx} className="p-3 rounded-lg border border-border-DEFAULT bg-background-secondary/50">
            <div className="flex items-center justify-between mb-1">
              <span className="text-xs font-medium text-foreground-muted uppercase tracking-wide">{factor.name}</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-sm text-foreground-DEFAULT">{(factor.contribution).toFixed(1)}</span>
                <div className="w-24 h-1.5 bg-background-tertiary rounded-full overflow-hidden">
                  <div className="bg-accent-DEFAULT h-full rounded-full" style={{ width: `${factor.value * 100}%` }} />
                </div>
              </div>
            </div>
            <p className="text-xs text-foreground-muted">{factor.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function AttackPathDetailPage() {
  const { workspaceId } = useWorkspace();
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const attackPathId = params.id as string;

  const { data: attackPath, isLoading: pathLoading, error: pathError } = useQuery({
    queryKey: ['attack-path', attackPathId],
    queryFn: () => api.getAttackPath(attackPathId),
    enabled: !!attackPathId,
    staleTime: 30 * 1000,
  });

  const { data: riskHistory } = useQuery({
    queryKey: ['risk-history', attackPathId],
    queryFn: () => api.getRiskHistory(attackPathId),
    enabled: !!attackPathId,
    staleTime: 30 * 1000,
  });

  const recalculateMutation = useMutation({
    mutationFn: (id: string) => api.recalculateRisk(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attack-path', attackPathId] });
      queryClient.invalidateQueries({ queryKey: ['risk-history', attackPathId] });
    },
  });

  const isRecalculating = recalculateMutation.isPending;

  if (pathLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card><CardContent><Skeleton className="h-8 w-1/4" /></CardContent></Card>
        <Card><CardContent><Skeleton className="h-40 w-full" /></CardContent></Card>
      </div>
    );
  }

  if (pathError || !attackPath) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon="AlertTriangle"
          title="Attack Path Not Found"
          description="The attack path you're looking for doesn't exist or you don't have access to it."
          action={<Button onClick={() => router.push('/attack-paths')}>Back to Attack Paths</Button>}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Link href="/attack-paths" className="p-2 rounded-lg hover:bg-background-tertiary transition-colors">
            <ChevronRight className="h-5 w-5 rotate-180 text-foreground-muted" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT flex items-center gap-2">
              <Zap className="h-6 w-6 text-accent-DEFAULT" />
              Attack Path Details
            </h1>
            <p className="text-sm text-foreground-muted font-mono mt-1">{attackPath.id}</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="outline" className={clsx(RISK_BAND_CONFIG[attackPath.risk_band || 'informational']?.color)}>
            {RISK_BAND_CONFIG[attackPath.risk_band || 'informational']?.label}
          </Badge>
          <Badge variant="outline" className={clsx(attackPath.status)}>
            {attackPath.status}
          </Badge>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Risk Score */}
          <Card className="border-accent-DEFAULT/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Flag className="h-5 w-5 text-accent-DEFAULT" />
                Risk Score
              </CardTitle>
              <CardDescription>
                Deterministic risk score based on severity, exploitability, impact, confidence, exposure, and path complexity.
                Model: {attackPath.risk_model_version || 'risk-v1'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col md:flex-row gap-6 items-center">
                <div className="flex-1">
                  <RiskScoreDisplay score={attackPath.risk_score} riskBand={attackPath.risk_band} />
                </div>
                <div className="flex gap-3">
                  <Button 
                    variant="outline" 
                    onClick={() => recalculateMutation.mutate(attackPathId)}
                    disabled={isRecalculating}
                    className="gap-2"
                  >
                    <RefreshCw className={clsx('h-4 w-4', isRecalculating && 'animate-spin')} />
                    Recalculate
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Risk Factors */}
          {attackPath.risk_score !== null && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart2 className="h-5 w-5" />
                  Risk Factor Breakdown
                </CardTitle>
              </CardHeader>
              <CardContent>
                {/* This would need the full risk calculation result */}
                <p className="text-sm text-foreground-muted">Run "Recalculate" to see detailed factor breakdown.</p>
              </CardContent>
            </Card>
          )}

          {/* Attack Path Graph */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <GitBranch className="h-5 w-5" />
                Attack Path Visualization
              </CardTitle>
              <CardDescription>
                Visual representation of the attack path. Nodes represent findings or boundaries, edges represent relationships.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="graph" className="w-full">
                <TabsList className="grid w-full grid-cols-2">
                  <TabsTrigger value="graph">Graph View</TabsTrigger>
                  <TabsTrigger value="textual">Textual View</TabsTrigger>
                </TabsList>
                <TabsContent value="graph" className="pt-4">
                  <div className="overflow-x-auto">
                    <AttackPathGraph nodes={attackPath.nodes || []} edges={attackPath.edges || []} />
                  </div>
                </TabsContent>
                <TabsContent value="textual" className="pt-4">
                  <div className="space-y-2">
                    <p className="text-xs text-foreground-muted">Textual representation for accessibility:</p>
                    <TextualAttackPath nodes={attackPath.nodes || []} edges={attackPath.edges || []} />
                  </div>
                </TabsContent>
              </Tabs>
            </CardContent          </Card>

          {/* Path Nodes Detail */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="h-5 w-5" />
                Path Nodes ({attackPath.nodes?.length || 0})
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {attackPath.nodes?.map((node, index) => {
                  const nodeConfig = NODE_TYPE_CONFIG[node.node_type] || NODE_TYPE_CONFIG.finding;
                  const NodeIcon = nodeConfig.icon;
                  const outgoingEdges = attackPath.edges?.filter(e => e.source_node_id === node.id) || [];
                  
                  return (
                    <div key={node.id} className="p-4 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
                      <div className="flex items-start gap-4">
                        <div className={clsx('flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center', nodeConfig.bg)}>
                          <NodeIcon className={clsx('h-5 w-5', nodeConfig.color)} />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-foreground-DEFAULT">
                              {node.finding?.title || `${nodeConfig.label} ${index + 1}`}
                            </span>
                            <Badge variant="outline" className={clsx('text-xs', nodeConfig.color)}>
                              {nodeConfig.label}
                            </Badge>
                            {outgoingEdges.length > 0 && (
                              <span className="text-xs text-foreground-muted">
                                → {outgoingEdges.map(e => RELATIONSHIP_TYPE_LABELS[e.relationship_type] || e.relationship_type).join(', ')}
                              </span>
                            )}
                          </div>
                          {node.rationale && (
                            <p className="text-sm text-foreground-muted">{node.rationale}</p>
                          )}
                          {node.finding && (
                            <div className="mt-2 flex flex-wrap gap-2 text-xs text-foreground-muted">
                              <Badge variant="outline" className={SEVERITY_CONFIG[node.finding.severity]?.color}>
                                {SEVERITY_CONFIG[node.finding.severity]?.label}
                              </Badge>
                              {node.finding.location?.file && (
                                <span className="flex items-center gap-1">
                                  <FileText className="h-3 w-3" />
                                  <span className="font-mono truncate max-w-xs">{node.finding.location.file}</span>
                                  {node.finding.location?.line_start && (
                                    <>
                                      <span>:</span>
                                      <span className="font-mono">{node.finding.location.line_start}</span>
                                    </>
                                  )}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </CardContent          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Info className="h-5 w-5" />
                Path Info
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Asset</dt>
                  <dd className="font-medium text-foreground-DEFAULT truncate max-w-[150px]">{attackPath.asset?.name || attackPath.asset_id}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Status</dt>
                  <dd className="font-medium text-foreground-DEFAULT capitalize">{attackPath.status}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Confidence</dt>
                  <dd className="font-medium text-foreground-DEFAULT">{Math.round(attackPath.confidence * 100)}%</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Severity</dt>
                  <dd className="font-medium text-foreground-DEFAULT capitalize">{attackPath.severity}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Risk Model</dt>
                  <dd className="font-mono text-xs">{attackPath.risk_model_version}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Created</dt>
                  <dd className="font-mono text-xs">{formatDate(attackPath.created_at)}</dd>
                </div>
                <div className="flex justify-between">
                  <dt className="text-foreground-muted">Updated</dt>
                  <dd className="font-mono text-xs">{formatDate(attackPath.updated_at)}</dd>
                </div>
              </dl>
            </CardContent          </Card>

          {/* Risk History */}
          {riskHistory && riskHistory.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart2 className="h-5 w-5" />
                  Risk History ({riskHistory.length})
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {riskHistory.map((snapshot, idx) => (
                    <div key={snapshot.id} className="p-3 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <Badge variant="outline" className={clsx(RISK_BAND_CONFIG[snapshot.risk_band]?.color)}>
                            {RISK_BAND_CONFIG[snapshot.risk_band]?.label}
                          </Badge>
                          <span className="text-xs text-foreground-muted font-mono">{snapshot.model_version}</span>
                        </div>
                        <div className="text-right">
                          <p className="text-xl font-bold text-foreground-DEFAULT">{snapshot.score}</p>
                          <p className="text-xs text-foreground-muted">{formatDate(snapshot.calculated_at)}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent            </Card>
          )}

          {/* Related Findings */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <LinkIcon className="h-5 w-5" />
                Related Findings
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {attackPath.nodes?.filter(n => n.finding).map((node, idx) => {
                  const finding = node.finding!;
                  return (
                    <Link key={finding.id} href={`/findings/${finding.id}`} className="flex items-center gap-2 p-2 rounded-lg hover:bg-background-tertiary/50 transition-colors">
                      <Badge variant="outline" className={clsx(SEVERITY_CONFIG[finding.severity]?.color)}>{SEVERITY_CONFIG[finding.severity]?.label}</Badge>
                      <span className="font-medium text-foreground-DEFAULT truncate flex-1">{finding.title}</span>
                      <Badge variant="outline" className="text-xs">{NODE_TYPE_CONFIG[node.node_type]?.label}</Badge>
                    </Link>
                  );
                })}
                {(!attackPath.nodes || !attackPath.nodes.some(n => n.finding)) && (
                  <p className="text-sm text-foreground-muted text-center py-4">No findings linked</p>
                )}
              </div>
            </CardContent          </Card>
        </div>
      </div>
    </div>
  );
}
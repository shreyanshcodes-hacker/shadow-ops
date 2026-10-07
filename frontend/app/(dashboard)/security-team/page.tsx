'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Shield, Bot, Clock, CheckCircle, XCircle, AlertTriangle, Loader2, RefreshCw } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from '@/components/ui/Table';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { MoreHorizontal, Play, Eye, RotateCcw } from 'lucide-react';
import { useWorkspace } from '@/hooks/useWorkspace';
import { api, type SecurityTeamRunListResponse } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { clsx } from 'clsx';

const STATUS_CONFIG: Record<string, { label: string; color: string; icon: React.ComponentType<{ className?: string }> }> = {
  succeeded: { label: 'Succeeded', color: 'success', icon: CheckCircle },
  partial: { label: 'Partial', color: 'warning', icon: AlertTriangle },
  failed: { label: 'Failed', color: 'error', icon: XCircle },
  running: { label: 'Running', color: 'info', icon: Loader2 },
  queued: { label: 'Queued', color: 'secondary', icon: Clock },
  canceled: { label: 'Canceled', color: 'secondary', icon: XCircle },
};

const AGENT_NAMES: Record<string, string> = {
  recon: 'Recon',
  vulnerability_analyst: 'Vulnerability Analyst',
  attack_path_analyst: 'Attack Path Analyst',
  risk_analyst: 'Risk Analyst',
  security_reviewer: 'Security Reviewer',
};

const AGENT_ORDER = [
  'recon',
  'vulnerability_analyst',
  'attack_path_analyst',
  'risk_analyst',
  'security_reviewer',
];

export default function SecurityTeamPage() {
  const { workspaceId, workspaces, switchWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(workspaceId || null);

  const { data: runs, isLoading, refetch } = useQuery({
    queryKey: ['security-team-runs', selectedWorkspaceId],
    queryFn: () => selectedWorkspaceId ? api.get(`/security-team/runs?workspace_id=${selectedWorkspaceId}&limit=50`) : [],
    enabled: !!selectedWorkspaceId,
    staleTime: 30 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const hasRunning = data.some((r: SecurityTeamRunListResponse) => 
        ['queued', 'running'].includes(r.status)
      );
      return hasRunning ? 5000 : false;
    },
  });

  const createMutation = useMutation({
    mutationFn: (data: { asset_id: string; scan_id: string }) => 
      api.post('/security-team/runs', data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-team-runs', selectedWorkspaceId] });
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (runId: string) => api.post(`/security-team/runs/${runId}/cancel`, {}),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['security-team-runs', selectedWorkspaceId] });
    },
  });

  const currentWorkspace = workspaces.find(w => w.id === selectedWorkspaceId);

  if (!selectedWorkspaceId) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT">AI Security Team</h1>
            <p className="text-sm text-foreground-muted mt-1">Multi-agent security analysis and assessment</p>
          </div>
        </div>
        <Card>
          <CardContent className="py-12 text-center">
            <Shield className="h-12 w-12 text-foreground-muted mx-auto mb-4" />
            <h3 className="text-lg font-medium text-foreground-DEFAULT mb-2">Select a Workspace</h3>
            <p className="text-foreground-muted mb-4">Choose a workspace from the selector above to view Security Team runs.</p>
            {workspaces.length > 0 && (
              <Button onClick={() => setSelectedWorkspaceId(workspaces[0].id)}>
                Use {workspaces[0].name}
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
    );
  }

  const handleCreateRun = async () => {
    // In a real implementation, this would open a dialog to select asset/scan
    // For now, we'll just show an alert
    alert('Select an asset and scan from the Assets or Scans page to start a Security Team run.');
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">AI Security Team</h1>
          <p className="text-sm text-foreground-muted mt-1">Multi-agent security analysis and assessment</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={handleCreateRun} disabled={createMutation.isPending}>
            <Play className="h-4 w-4 mr-2" />
            New Team Run
          </Button>
          <Button variant="outline" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Security Team Runs</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          ) : runs && runs.length === 0 ? (
            <EmptyState
              icon="Shield"
              title="No Security Team Runs"
              description="Start a new team run to analyze your scan findings with the AI Security Team."
              action={
                <Button onClick={handleCreateRun} disabled={createMutation.isPending}>
                  <Play className="h-4 w-4 mr-2" />
                  Start Team Run
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Asset / Scan</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Agents</TableHead>
                    <TableHead>Confidence</TableHead>
                    <TableHead>Duration</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {runs.map((run) => {
                    const statusConfig = STATUS_CONFIG[run.status] || { label: run.status, color: 'secondary', icon: Clock };
                    const StatusIcon = statusConfig.icon;
                    const summary = run.team_summary as { completed_agents?: string[]; failed_agents?: string[] } | undefined;
                    const completedCount = summary?.completed_agents?.length || 0;
                    const failedCount = summary?.failed_agents?.length || 0;
                    const totalAgents = 5;
                    
                    const startedAt = run.started_at ? new Date(run.started_at) : null;
                    const completedAt = run.completed_at ? new Date(run.completed_at) : null;
                    const duration = startedAt && completedAt 
                      ? Math.round((completedAt.getTime() - startedAt.getTime()) / 1000)
                      : startedAt 
                        ? Math.round((Date.now() - startedAt.getTime()) / 1000)
                        : null;

                    return (
                      <TableRow key={run.id}>
                        <TableCell>
                          <div>
                            <Link href={`/security-team/${run.id}`} className="font-mono text-sm text-foreground-DEFAULT hover:text-accent-DEFAULT">
                              {run.id.toString().slice(0, 8)}...
                            </Link>
                            <p className="text-xs text-foreground-muted">{run.orchestration_version}</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <div>
                            <p className="font-medium text-foreground-DEFAULT truncate max-w-xs">{run.asset_id.toString().slice(0, 8)}...</p>
                            <p className="text-xs text-foreground-muted">{run.scan_id.toString().slice(0, 8)}...</p>
                          </div>
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusConfig.color as any} dot className="gap-1">
                            <StatusIcon className="h-3 w-3" />
                            {statusConfig.label}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <span className="text-sm font-mono text-foreground-DEFAULT">
                              {completedCount}/{totalAgents}
                            </span>
                            {failedCount > 0 && (
                              <Badge variant="error" className="text-xs">{failedCount} failed</Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {run.confidence !== null && run.confidence !== undefined ? (
                            <div className="flex items-center gap-2">
                              <div className="w-24 h-2 bg-background-tertiary rounded-full overflow-hidden">
                                <div 
                                  className="h-full bg-accent-DEFAULT" 
                                  style={{ width: `${Math.round(run.confidence * 100)}%` }}
                                />
                              </div>
                              <span className="text-sm font-mono">{Math.round(run.confidence * 100)}%</span>
                            </div>
                          ) : (
                            <span className="text-foreground-muted">—</span>
                          )}
                        </TableCell>
                        <TableCell>
                          {duration !== null ? (
                            <span className="text-sm font-mono text-foreground-DEFAULT">
                              {duration < 60 ? `${duration}s` : `${Math.round(duration / 60)}m ${duration % 60}s`}
                            </span>
                          ) : (
                            <span className="text-foreground-muted">—</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right">
                          <Dropdown>
                            <DropdownTrigger className="p-2 rounded-lg hover:bg-background-tertiary" aria-label="More actions">
                              <MoreHorizontal className="h-4 w-4" />
                            </DropdownTrigger>
                            <DropdownContent align="end">
                              <DropdownItem 
                                onClick={() => window.location.href = `/security-team/${run.id}`}
                                disabled={run.status !== 'succeeded' && run.status !== 'partial'}
                              >
                                <Eye className="h-4 w-4 mr-2" />
                                View Details
                              </DropdownItem>
                              {run.status === 'running' || run.status === 'queued' ? (
                                <>
                                  <DropdownSeparator />
                                  <DropdownItem
                                    onClick={() => cancelMutation.mutate(run.id)}
                                    className="text-status-error"
                                    disabled={cancelMutation.isPending}
                                  >
                                    <XCircle className="h-4 w-4 mr-2" />
                                    Cancel Run
                                  </DropdownItem>
                                </>
                              ) : run.status === 'failed' ? (
                                <>
                                  <DropdownSeparator />
                                  <DropdownItem
                                    onClick={() => {
                                      // Re-run would be a new run with same params
                                      alert('Re-run functionality would create a new team run with the same asset/scan');
                                    }}
                                  >
                                    <RotateCcw className="h-4 w-4 mr-2" />
                                    Re-run
                                  </DropdownItem>
                                </>
                              ) : null}
                            </DropdownContent>
                          </Dropdown>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Agent Status Legend */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle>Agent Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            {AGENT_ORDER.map((agentKey, index) => (
              <div key={agentKey} className="flex items-center gap-2">
                {index > 0 && <span className="text-foreground-muted">→</span>}
                <span className="font-medium text-foreground-DEFAULT">{AGENT_NAMES[agentKey]}</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-foreground-muted mt-2">
            Agents execute in dependency order. Recon → Vulnerability Analyst → Attack Path Analyst → Risk Analyst → Security Reviewer.
            Failed agents block downstream agents. Partial results are available when ≥3 agents succeed.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

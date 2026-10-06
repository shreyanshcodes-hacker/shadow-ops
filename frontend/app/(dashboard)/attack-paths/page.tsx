'use client';

import { useState } from 'react';
import {
  Zap, AlertTriangle, CheckCircle, XCircle, Loader2,
  ChevronRight, ChevronDown, FileText, Code, AlertCircle,
  BarChart2, Download, RefreshCw, X, Brain, Bot, Shield, Sparkles,
  Info, AlertCircle as AlertCircleIcon, Flag, Target, Search,
  GitBranch, Link as LinkIcon, Eye, EyeOff, Trash2, Check, Filter, Plus
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
import { useRouter } from 'next/navigation';
import { api, type AttackPath, type Asset } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

const RISK_BAND_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  critical: { label: 'Critical', color: 'text-status-error', bg: 'bg-status-error/10' },
  high: { label: 'High', color: 'text-status-error', bg: 'bg-status-error/10' },
  medium: { label: 'Medium', color: 'text-status-warning', bg: 'bg-status-warning/10' },
  low: { label: 'Low', color: 'text-status-info', bg: 'bg-status-info/10' },
  informational: { label: 'Informational', color: 'text-foreground-muted', bg: 'bg-background-tertiary' },
};

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: 'Draft', color: 'text-foreground-muted', bg: 'bg-background-tertiary' },
  active: { label: 'Active', color: 'text-accent-DEFAULT', bg: 'bg-accent-DEFAULT/10' },
  dismissed: { label: 'Dismissed', color: 'text-status-warning', bg: 'bg-status-warning/10' },
  resolved: { label: 'Resolved', color: 'text-status-success', bg: 'bg-status-success/10' },
};

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '—';
  return new Date(dateStr).toLocaleString();
}

function RiskScoreDisplay({ score, riskBand }: { score: number | null; riskBand: string | null }) {
  if (score === null) {
    return (
      <div className="text-center py-2">
        <p className="text-xl font-bold text-foreground-muted">—</p>
        <p className="text-xs text-foreground-muted">Not Calculated</p>
      </div>
    );
  }

  const band = riskBand || 'informational';
  const config = RISK_BAND_CONFIG[band];

  return (
    <div className="text-center py-2">
      <div className="flex items-center justify-center gap-2 mb-1">
        <span className="text-2xl font-bold text-foreground-DEFAULT">{score}</span>
        <Badge variant="outline" className={clsx(config.color, config.bg)}>
          {config.label}
        </Badge>
      </div>
      <Progress value={score} className="h-2 max-w-xs mx-auto" />
    </div>
  );
}

function AttackPathRow({ attackPath, onRefresh }: { attackPath: AttackPath; onRefresh: () => void }) {
  const statusConfig = STATUS_CONFIG[attackPath.status] || STATUS_CONFIG.draft;
  const riskConfig = attackPath.risk_band ? RISK_BAND_CONFIG[attackPath.risk_band] : RISK_BAND_CONFIG.informational;

  return (
    <div className="p-4 rounded-lg border border-border-DEFAULT hover:bg-background-tertiary/50 transition-colors">
      <div className="flex items-start gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Link 
              href={`/attack-paths/${attackPath.id}`}
              className="font-medium text-foreground-DEFAULT hover:text-accent-DEFAULT transition-colors"
            >
              {attackPath.title}
            </Link>
            <Badge variant="outline" className={clsx(statusConfig.color, statusConfig.bg)}>
              {statusConfig.label}
            </Badge>
          </div>
          <p className="text-sm text-foreground-muted mb-2">{attackPath.description || 'No description'}</p>
          <div className="flex flex-wrap gap-2 text-xs text-foreground-muted">
            <span className="flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              Asset: {attackPath.asset?.name || attackPath.asset_id}
            </span>
            <span className="flex items-center gap-1">
              <FileText className="h-3 w-3" />
              {attackPath.node_count} nodes
            </span>
            <span className="flex items-center gap-1">
              <Shield className="h-3 w-3" />
              Confidence: {Math.round(attackPath.confidence * 100)}%
            </span>
          </div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <div className="w-24">
            <RiskScoreDisplay score={attackPath.risk_score} riskBand={attackPath.risk_band} />
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onRefresh} className="gap-1">
              <RefreshCw className="h-3 w-3" />
              Refresh
            </Button>
            <Button variant="ghost" size="sm" asChild className="gap-1">
              <Link href={`/attack-paths/${attackPath.id}`}>
                <Eye className="h-3 w-3" />
                View
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AttackPathsPage() {
  const { workspaceId } = useWorkspace();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'all' | 'active' | 'draft' | 'dismissed'>('all');
  const [filterAsset, setFilterAsset] = useState<string>('');

  const { data: assets, isLoading: assetsLoading } = useQuery({
    queryKey: ['assets', workspaceId],
    queryFn: () => workspaceId ? api.listAssets(workspaceId) : [],
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  const statusFilter = activeTab === 'all' ? undefined : activeTab;

  const { data: attackPaths, isLoading: pathsLoading, refetch } = useQuery({
    queryKey: ['attack-paths', workspaceId, statusFilter, filterAsset],
    queryFn: () => {
      const params: Record<string, string> = {};
      if (statusFilter) params.status = statusFilter;
      if (filterAsset) params.asset_id = filterAsset;
      return api.listAttackPaths(workspaceId!, params);
    },
    enabled: !!workspaceId,
    staleTime: 30 * 1000,
  });

  const generateMutation = useMutation({
    mutationFn: (assetId: string) => api.generateAttackPaths(assetId, { min_confidence: '0.5' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['attack-paths', workspaceId] });
    },
  });

  const isGenerating = generateMutation.isPending;

  if (!workspaceId) {
    return (
      <div className="space-y-6">
        <EmptyState
          icon="AlertTriangle"
          title="No Workspace Selected"
          description="Please select a workspace to view attack paths."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT flex items-center gap-2">
            <Zap className="h-6 w-6 text-accent-DEFAULT" />
            Attack Paths
          </h1>
          <p className="text-sm text-foreground-muted mt-1">Correlated security findings and risk analysis</p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={filterAsset}
            onChange={(e) => setFilterAsset(e.target.value)}
            className="px-3 py-2 rounded-lg border border-border-DEFAULT bg-background-secondary text-sm"
          >
            <option value="">All Assets</option>
            {assets?.map(asset => (
              <option key={asset.id} value={asset.id}>{asset.name}</option>
            ))}
          </select>
          <Button onClick={() => refetch()} variant="outline" className="gap-1">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-error/10">
                <AlertTriangle className="h-5 w-5 text-status-error" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Total Paths</p>
                <p className="text-2xl font-bold text-foreground-DEFAULT">{attackPaths?.length || 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-error/10">
                <AlertTriangle className="h-5 w-5 text-status-error" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Critical</p>
                <p className="text-2xl font-bold text-status-error">
                  {attackPaths?.filter(p => p.risk_band === 'critical').length || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-status-warning/10">
                <AlertTriangle className="h-5 w-5 text-status-warning" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">High</p>
                <p className="text-2xl font-bold text-status-error">
                  {attackPaths?.filter(p => p.risk_band === 'high').length || 0}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-accent-glow">
                <Zap className="h-5 w-5 text-accent-DEFAULT" />
              </div>
              <div>
                <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">Avg Risk Score</p>
                <p className="text-2xl font-bold text-foreground-DEFAULT">
                  {attackPaths && attackPaths.length > 0
                    ? Math.round(attackPaths.filter(p => p.risk_score !== null).reduce((sum, p) => sum + (p.risk_score || 0), 0) / attackPaths.filter(p => p.risk_score !== null).length)
                    : '—'}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Generate Attack Paths */}
      {assets && assets.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-accent-DEFAULT" />
              Generate Attack Paths
            </CardTitle>
            <CardDescription>
              Build attack paths from deterministic correlations for a specific asset.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-3">
              {assets.map(asset => (
                <Button
                  key={asset.id}
                  variant="outline"
                  onClick={() => generateMutation.mutate(asset.id)}
                  disabled={isGenerating}
                  className="gap-2"
                >
                  <GitBranch className="h-4 w-4" />
                  {asset.name}
                </Button>
              ))}
              {isGenerating && (
                <Button variant="outline" disabled className="gap-2">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Generating...
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Attack Paths List */}
      <Card>
        <CardHeader>
          <CardTitle>Attack Paths ({attackPaths?.length || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          {pathsLoading ? (
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-20 w-full" />
              ))}
            </div>
          ) : attackPaths && attackPaths.length > 0 ? (
            <div className="space-y-3">
              {attackPaths.map(attackPath => (
                <AttackPathRow
                  key={attackPath.id}
                  attackPath={attackPath}
                  onRefresh={() => refetch()}
                />
              ))}
            </div>
          ) : (
            <EmptyState
              icon="GitBranch"
              title="No Attack Paths"
              description={assets && assets.length === 0
                ? "Add assets and run scans to generate attack paths."
                : "Run correlation on findings or generate attack paths from assets."}
              action={assets && assets.length > 0 && (
                <Button onClick={() => generateMutation.mutate(assets[0].id)}>
                  <Zap className="h-4 w-4 mr-2" />
                  Generate from First Asset
                </Button>
              )}
            />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
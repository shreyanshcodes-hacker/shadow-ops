'use client';

import { useState } from 'react';
import { Search, Filter, Zap, Clock, AlertTriangle, CheckCircle, XCircle, Loader2, ChevronDown, BarChart2 } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { useWorkspace } from '@/hooks/useWorkspace';
import { api, type ScanListResponse, type ScanStatus } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

const STATUS_CONFIG: Record<ScanStatus, { label: string; icon: React.ComponentType<{ className?: string }>; color: string }> = {
  queued: { label: 'Queued', icon: Clock, color: 'text-status-warning' },
  running: { label: 'Running', icon: Zap, color: 'text-accent-DEFAULT animate-pulse' },
  completed: { label: 'Completed', icon: CheckCircle, color: 'text-status-success' },
  failed: { label: 'Failed', icon: AlertTriangle, color: 'text-status-error' },
  cancelled: { label: 'Cancelled', icon: XCircle, color: 'text-foreground-muted' },
  partial: { label: 'Partial', icon: AlertTriangle, color: 'text-status-warning' },
};

const SCAN_PROFILES = [
  { value: 'QUICK', label: 'Quick', description: 'Fast surface-level scan' },
  { value: 'STANDARD', label: 'Standard', description: 'Balanced depth and speed' },
  { value: 'CODE_SECURITY', label: 'Code Security', description: 'Deep static analysis (SAST + SCA)' },
];

export default function ScansPage() {
  const { workspaceId } = useWorkspace();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterProfile, setFilterProfile] = useState<string>('all');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [selectedAssetId, setSelectedAssetId] = useState<string>('');
  const [selectedProfile, setSelectedProfile] = useState<'QUICK' | 'STANDARD' | 'CODE_SECURITY'>('CODE_SECURITY');

  const { data: scans, isLoading, error } = useQuery({
    queryKey: ['scans', workspaceId, filterStatus, filterProfile],
    queryFn: () => workspaceId ? api.listScans(workspaceId, { 
      status: filterStatus !== 'all' ? filterStatus : undefined,
      scan_profile: filterProfile !== 'all' ? filterProfile : undefined,
    }) : [],
    enabled: !!workspaceId,
    staleTime: 30 * 1000,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && data.some((s: ScanListResponse) => ['queued', 'running'].includes(s.status))) {
        return 5000;
      }
      return false;
    },
  });

  const { data: assets } = useQuery({
    queryKey: ['assets', workspaceId],
    queryFn: () => workspaceId ? api.listAssets(workspaceId) : [],
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: (data: { asset_id: string; scan_type: string; scan_profile: string }) => 
      api.createScan(workspaceId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans', workspaceId] });
      setCreateDialogOpen(false);
      setSelectedAssetId('');
    },
  });

  const cancelMutation = useMutation({
    mutationFn: (scanId: string) => api.cancelScan(scanId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans', workspaceId] });
    },
  });

  const filteredScans = scans?.filter(scan => {
    const matchesSearch = scan.id.toLowerCase().includes(search.toLowerCase()) ||
      (scan.asset_id && assets?.find(a => a.id === scan.asset_id)?.name.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = filterStatus === 'all' || scan.status === filterStatus;
    const matchesProfile = filterProfile === 'all' || scan.scan_profile === filterProfile;
    return matchesSearch && matchesStatus && matchesProfile;
  }) || [];

  if (!workspaceId) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT">Scans</h1>
            <p className="text-sm text-foreground-muted mt-1">Manage and monitor security scans</p>
          </div>
        </div>
        <EmptyState
          icon="Building2"
          title="No Workspace Selected"
          description="Select a workspace from the sidebar to view and manage scans."
        />
      </div>
    );
  }

  const authorizedAssets = assets?.filter(a => a.id && a.status === 'active') || [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">Scans</h1>
          <p className="text-sm text-foreground-muted mt-1">Monitor and manage security scans for your workspace</p>
        </div>
        {authorizedAssets.length > 0 && (
          <Button onClick={() => setCreateDialogOpen(true)} disabled={createMutation.isPending}>
            <Zap className="h-4 w-4 mr-2" />
            Start New Scan
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
              <Input
                placeholder="Search scans..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Dropdown>
                <DropdownTrigger className="w-full sm:w-40">
                  <SelectValue placeholder="All Status" />
                </DropdownTrigger>
                <DropdownContent>
                  <DropdownItem onClick={() => setFilterStatus('all')}>All Status</DropdownItem>
                  <DropdownSeparator />
                  {Object.entries(STATUS_CONFIG).map(([key, config]) => (
                    <DropdownItem key={key} onClick={() => setFilterStatus(key)}>
                      <config.icon className={`h-4 w-4 mr-2 ${config.color}`} />
                      {config.label}
                    </DropdownItem>
                  ))}
                </DropdownContent>
              </Dropdown>
              <Dropdown>
                <DropdownTrigger className="w-full sm:w-40">
                  <SelectValue placeholder="All Profiles" />
                </DropdownTrigger>
                <DropdownContent>
                  <DropdownItem onClick={() => setFilterProfile('all')}>All Profiles</DropdownItem>
                  <DropdownSeparator />
                  {SCAN_PROFILES.map(profile => (
                    <DropdownItem key={profile.value} onClick={() => setFilterProfile(profile.value)}>
                      {profile.label}
                    </DropdownItem>
                  ))}
                </DropdownContent>
              </Dropdown>
            </div>
          </div>
        </CardContent>
      </Card>

      {isLoading ? (
        <Card>
          <CardContent>
            <div className="space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <Skeleton key={i} className="h-16 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      ) : error ? (
        <Card>
          <CardContent className="py-12 text-center">
            <EmptyState
              icon="AlertTriangle"
              title="Failed to Load Scans"
              description="Please try refreshing the page."
              action={<Button onClick={() => queryClient.invalidateQueries({ queryKey: ['scans', workspaceId] })}>Retry</Button>}
            />
          </CardContent>
        </Card>
      ) : filteredScans.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon={search || filterStatus !== 'all' || filterProfile !== 'all' ? "Filter" : "Zap"}
              title={search || filterStatus !== 'all' || filterProfile !== 'all' ? 'No Matching Scans' : 'No Scans Yet'}
              description={search || filterStatus !== 'all' || filterProfile !== 'all' 
                ? 'Try adjusting your search or filter criteria.'
                : authorizedAssets.length === 0
                  ? 'Add an authorized asset first, then start a scan.'
                  : 'Start your first security scan to analyze your assets.'}
              action={authorizedAssets.length > 0 && !search && filterStatus === 'all' && filterProfile === 'all' ? (
                <Button onClick={() => setCreateDialogOpen(true)}>
                  <Zap className="h-4 w-4 mr-2" />
                  Start New Scan
                </Button>
              ) : undefined}
            />
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-border-DEFAULT">
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Scan</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Asset</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Profile</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Progress</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Findings</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Started</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-DEFAULT">
                  {filteredScans.map((scan) => {
                    const asset = assets?.find(a => a.id === scan.asset_id);
                    const statusConfig = STATUS_CONFIG[scan.status as ScanStatus] || { label: scan.status, icon: AlertTriangle, color: 'text-foreground-muted' };
                    const isRunning = ['queued', 'running'].includes(scan.status);
                    const findings = scan.summary ? (
                      typeof scan.summary === 'object' && 'total_findings' in scan.summary
                        ? (scan.summary as any).total_findings
                        : 0
                    ) : 0;

                    return (
                      <tr key={scan.id} className="hover:bg-background-tertiary/50 transition-colors">
                        <td className="px-4 py-3">
                          <Link href={`/scans/${scan.id}`} className="font-mono text-sm text-accent-DEFAULT hover:underline">
                            {scan.id.slice(0, 8)}...
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {asset?.type === 'repository' && <span className="text-accent-DEFAULT">⌥</span>}
                            <span className="text-sm font-medium text-foreground-DEFAULT truncate max-w-xs">
                              {asset?.name || 'Unknown Asset'}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline">{scan.scan_profile}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <statusConfig.icon className={`h-4 w-4 ${statusConfig.color}`} />
                            <StatusBadge status={scan.status as any} />
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="w-32 h-2 bg-background-tertiary rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-accent-DEFAULT transition-all duration-300" 
                              style={{ width: `${scan.progress_percent}%` }}
                            />
                          </div>
                          <span className="text-xs text-foreground-muted ml-2">{scan.progress_percent}%</span>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={findings > 0 ? 'destructive' : 'success'}>{findings}</Badge>
                        </td>
                        <td className="px-4 py-3 text-foreground-muted text-sm">
                          {scan.duration_ms ? `${Math.round(scan.duration_ms / 1000)}s` : '—'}
                        </td>
                        <td className="px-4 py-3 text-foreground-muted text-sm font-mono">
                          {scan.started_at ? new Date(scan.started_at).toLocaleString() : scan.triggered_at ? new Date(scan.triggered_at).toLocaleString() : '—'}
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Link href={`/scans/${scan.id}`}>
                              <Button variant="ghost" size="sm">View</Button>
                            </Link>
                            {isRunning && (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                onClick={() => cancelMutation.mutate(scan.id)}
                                disabled={cancelMutation.isPending}
                              >
                                <XCircle className="h-4 w-4 mr-1" />
                                Cancel
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Start New Scan</DialogTitle>
            <DialogDescription>Configure and start a new security scan</DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate({ asset_id: selectedAssetId, scan_type: 'code', scan_profile: selectedProfile }); }}>
            <DialogContent className="space-y-4 p-6 pt-0">
              {authorizedAssets.length === 0 ? (
                <div className="p-4 rounded-lg bg-status-warning/10 border border-status-warning/30">
                  <AlertTriangle className="h-5 w-5 text-status-warning mr-2" />
                  <span className="text-sm text-status-warning">No authorized assets available. Create and authorize an asset first.</span>
                </div>
              ) : (
                <>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground-DEFAULT">Asset *</label>
                    <Select value={selectedAssetId} onValueChange={setSelectedAssetId}>
                      <SelectTrigger>
                        <SelectValue placeholder="Select asset to scan" />
                      </SelectTrigger>
                      <SelectContent>
                        {authorizedAssets.map(asset => (
                          <SelectItem key={asset.id} value={asset.id}>
                            {asset.name} ({asset.type})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-foreground-DEFAULT">Scan Profile *</label>
                    <Select value={selectedProfile} onValueChange={setSelectedProfile}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {SCAN_PROFILES.map(profile => (
                          <SelectItem key={profile.value} value={profile.value}>
                            <div>
                              <p className="font-medium">{profile.label}</p>
                              <p className="text-xs text-foreground-muted">{profile.description}</p>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </>
              )}
            </DialogContent>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setCreateDialogOpen(false)}>Cancel</Button>
              <Button type="submit" loading={createMutation.isPending} disabled={!selectedAssetId || authorizedAssets.length === 0}>
                <Loader2 className="h-4 w-4 mr-2" />
                Start Scan
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
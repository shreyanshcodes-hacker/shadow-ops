'use client';

import { useState } from 'react';
import { Plus, Search, Filter, GitBranch, Server, Database, Box, Layers, Loader2, ChevronDown, Zap, Shield, AlertCircle, Clock } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/Dialog';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { Label } from '@/components/ui/Input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { useAuth } from '@/hooks/useAuth';
import { api, type Asset, type CreateAssetRequest, type Authorization } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';
import { useWorkspace } from '@/hooks/useWorkspace';
import { useRouter } from 'next/navigation';

const ASSET_TYPES = [
  { value: 'repository', label: 'Repository', icon: GitBranch, description: 'GitHub, GitLab, Bitbucket repositories' },
  { value: 'api', label: 'API', icon: Server, description: 'REST, GraphQL, gRPC endpoints' },
  { value: 'infrastructure', label: 'Infrastructure', icon: Database, description: 'Cloud, Kubernetes, Terraform' },
  { value: 'application', label: 'Application', icon: Box, description: 'Web, mobile, desktop applications' },
  { value: 'container', label: 'Container', icon: Layers, description: 'Docker images, container registries' },
];

const ENVIRONMENTS = ['development', 'staging', 'production'];
const CRITICALITIES = ['low', 'medium', 'high', 'critical'];

const AUTH_STATUS_CONFIG = {
  verified: { label: 'Authorized', color: 'text-status-success', bg: 'bg-status-success/10', icon: Shield },
  pending: { label: 'Pending', color: 'text-status-warning', bg: 'bg-status-warning/10', icon: Clock },
  rejected: { label: 'Rejected', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertCircle },
  expired: { label: 'Expired', color: 'text-foreground-muted', bg: 'bg-background-tertiary', icon: AlertCircle },
  missing: { label: 'Not Authorized', color: 'text-status-error', bg: 'bg-status-error/10', icon: AlertCircle },
} as const;

export default function AssetsPage() {
  const { workspaceId } = useWorkspace();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [filterType, setFilterType] = useState<string>('all');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedType, setSelectedType] = useState<'repository' | 'api' | 'infrastructure' | 'application' | 'container'>('repository');

  const { data: assets, isLoading, error } = useQuery({
    queryKey: ['assets', workspaceId],
    queryFn: () => workspaceId ? api.listAssets(workspaceId) : [],
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  // Fetch authorizations for all assets in parallel
  const { data: authorizations } = useQuery({
    queryKey: ['authorizations', workspaceId],
    queryFn: async () => {
      if (!assets || !workspaceId) return {};
      const authMap: Record<string, Authorization> = {};
      await Promise.all(
        assets.map(async (asset) => {
          try {
            const auth = await api.getAuthorization(asset.id);
            authMap[asset.id] = auth;
          } catch {
            authMap[asset.id] = { status: 'missing' } as Authorization;
          }
        })
      );
      return authMap;
    }),
    enabled: !!workspaceId && !!assets?.length,
    staleTime: 2 * 60 * 1000,
  });

  const createMutation = useMutation({
    mutationFn: (data: CreateAssetRequest) => api.createAsset(workspaceId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets', workspaceId] });
      setDialogOpen(false);
    },
  });

  const filteredAssets = assets?.filter(asset => {
    const matchesSearch = asset.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = filterType === 'all' || asset.type === filterType;
    return matchesSearch && matchesType;
  }) || [];

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const data: CreateAssetRequest = {
      name: formData.get('name') as string,
      type: selectedType,
      subtype: formData.get('subtype') as string || undefined,
      connection_config: {
        url: formData.get('url') as string,
        branch: formData.get('branch') as string || 'main',
      },
      credentials_ref: formData.get('credentials_ref') as string || undefined,
      criticality: formData.get('criticality') as any,
      tags: (formData.get('tags') as string).split(',').map(t => t.trim()).filter(Boolean),
    };
    createMutation.mutate(data);
  };

  const getAuthStatus = (assetId: string) => {
    const auth = authorizations?.[assetId];
    if (!auth || auth.status === 'missing') return 'missing' as const;
    return auth.status as keyof typeof AUTH_STATUS_CONFIG;
  };

  const canScan = (assetId: string) => {
    const authStatus = getAuthStatus(assetId);
    return authStatus === 'verified';
  };

  if (!workspaceId) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT">Assets</h1>
            <p className="text-sm text-foreground-muted mt-1">Manage your scan targets</p>
          </div>
        </div>
        <EmptyState
          icon="Building2"
          title="No Workspace Selected"
          description="Select a workspace from the sidebar to view and manage assets."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">Assets</h1>
          <p className="text-sm text-foreground-muted mt-1">Manage your scan targets and authorization status</p>
        </div>
        <Button onClick={() => { setSelectedType('repository'); setDialogOpen(true); }}>
          <Plus className="h-4 w-4 mr-2" />
          Add Asset
        </Button>
      </div>

      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-foreground-muted" />
              <Input
                placeholder="Search assets..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-10"
              />
            </div>
            <Dropdown>
              <DropdownTrigger className="w-full sm:w-48">
                <SelectValue placeholder="All Types" />
              </DropdownTrigger>
              <DropdownContent>
                <DropdownItem onClick={() => setFilterType('all')}>All Types</DropdownItem>
                <DropdownSeparator />
                {ASSET_TYPES.map(type => (
                  <DropdownItem key={type.value} onClick={() => setFilterType(type.value)}>
                    {type.label}
                  </DropdownItem>
                ))}
              </DropdownContent>
            </Dropdown>
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
              title="Failed to Load Assets"
              description="Please try refreshing the page."
              action={<Button onClick={() => queryClient.invalidateQueries({ queryKey: ['assets', workspaceId] })}>Retry</Button>}
            />
          </CardContent>
        </Card>
      ) : filteredAssets.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <EmptyState
              icon="Database"
              title={search || filterType !== 'all' ? 'No Matching Assets' : 'No Assets Yet'}
              description={search || filterType !== 'all' 
                ? 'Try adjusting your search or filter criteria.'
                : 'Add your first repository or API to start monitoring.'}
              action={
                <Button onClick={() => { setSelectedType('repository'); setDialogOpen(true); }}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Asset
                </Button>
              }
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
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Asset</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Type</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Environment</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Criticality</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-foreground-muted uppercase tracking-wider">Authorization</th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-foreground-muted uppercase tracking-wider">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border-DEFAULT">
                  {filteredAssets.map((asset) => {
                    const authStatus = getAuthStatus(asset.id);
                    const authConfig = AUTH_STATUS_CONFIG[authStatus];
                    const scanEnabled = canScan(asset.id);

                    return (
                      <tr key={asset.id} className="hover:bg-background-tertiary/50 transition-colors">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            <div className="p-1.5 rounded bg-accent-glow">
                              {asset.type === 'repository' && <GitBranch className="h-4 w-4 text-accent-DEFAULT" />}
                              {asset.type === 'api' && <Server className="h-4 w-4 text-accent-DEFAULT" />}
                              {asset.type === 'infrastructure' && <Database className="h-4 w-4 text-accent-DEFAULT" />}
                              {asset.type === 'application' && <Box className="h-4 w-4 text-accent-DEFAULT" />}
                              {asset.type === 'container' && <Layers className="h-4 w-4 text-accent-DEFAULT" />}
                            </div>
                            <div>
                              <p className="text-sm font-medium text-foreground-DEFAULT">{asset.name}</p>
                              <p className="text-xs text-foreground-muted font-mono">{asset.subtype || '—'}</p>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="outline" className="capitalize">{asset.type}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="secondary">{asset.connection_config?.environment || '—'}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={asset.criticality as any} />
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={asset.status as any} />
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <div className={`p-1.5 rounded ${authConfig.bg}`}>
                              <authConfig.icon className={`h-4 w-4 ${authConfig.color}`} />
                            </div>
                            <span className={`text-sm font-medium ${authConfig.color}`}>{authConfig.label}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button variant="ghost" size="sm" asChild>
                              <a href={`/assets/${asset.id}`}>View</a>
                            </Button>
                            {scanEnabled && (
                              <Button 
                                variant="secondary" 
                                size="sm" 
                                onClick={() => router.push(`/scans?asset=${asset.id}`)}
                              >
                                <Zap className="h-4 w-4 mr-2" />
                                Scan
                              </Button>
                            )}
                            {!scanEnabled && authStatus !== 'missing' && (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                disabled
                                className="text-foreground-muted"
                              >
                                <Shield className="h-4 w-4 mr-2" />
                                Scan Blocked
                              </Button>
                            )}
                            {authStatus === 'missing' && (
                              <Button 
                                variant="outline" 
                                size="sm" 
                                disabled
                                className="text-foreground-muted"
                              >
                                <AlertCircle className="h-4 w-4 mr-2" />
                                Authorize First
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

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Add New Asset</DialogTitle>
            <DialogDescription>Configure a new scan target for your workspace</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-6 p-6 pt-0">
              <div className="space-y-2">
                <Label htmlFor="type">Asset Type</Label>
                <div className="grid grid-cols-2 gap-3">
                  {ASSET_TYPES.map(type => (
                    <label
                      key={type.value}
                      className={clsx(
                        'relative flex flex-col items-center p-4 rounded-lg border-2 transition-all cursor-pointer',
                        selectedType === type.value
                          ? 'border-accent-DEFAULT bg-accent-glow'
                          : 'border-border-DEFAULT hover:border-accent-DEFAULT/50'
                      )}
                    >
                      <input
                        type="radio"
                        name="type"
                        value={type.value}
                        checked={selectedType === type.value}
                        onChange={() => setSelectedType(type.value as any)}
                        className="sr-only"
                      />
                      <type.icon className="h-6 w-6 mb-2 text-accent-DEFAULT" />
                      <span className="font-medium text-foreground-DEFAULT">{type.label}</span>
                      <p className="text-xs text-foreground-muted text-center mt-1">{type.description}</p>
                    </label>
                  ))}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name">Name *</Label>
                  <Input id="name" name="name" placeholder="ShadowOps Demo" required />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="subtype">Subtype</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select subtype" />
                    </SelectTrigger>
                    <SelectContent>
                      {selectedType === 'repository' && (
                        <>
                          <SelectItem value="github">GitHub</SelectItem>
                          <SelectItem value="gitlab">GitLab</SelectItem>
                          <SelectItem value="bitbucket">Bitbucket</SelectItem>
                          <SelectItem value="azure_devops">Azure DevOps</SelectItem>
                        </>
                      )}
                      {selectedType === 'api' && (
                        <>
                          <SelectItem value="rest">REST</SelectItem>
                          <SelectItem value="graphql">GraphQL</SelectItem>
                          <SelectItem value="grpc">gRPC</SelectItem>
                        </>
                      )}
                      {selectedType === 'infrastructure' && (
                        <>
                          <SelectItem value="aws">AWS</SelectItem>
                          <SelectItem value="gcp">GCP</SelectItem>
                          <SelectItem value="azure">Azure</SelectItem>
                          <SelectItem value="kubernetes">Kubernetes</SelectItem>
                          <SelectItem value="terraform">Terraform</SelectItem>
                        </>
                      )}
                      {selectedType === 'container' && (
                        <>
                          <SelectItem value="docker">Docker Hub</SelectItem>
                          <SelectItem value="ecr">Amazon ECR</SelectItem>
                          <SelectItem value="gcr">Google GCR</SelectItem>
                          <SelectItem value="ghcr">GitHub Container Registry</SelectItem>
                        </>
                      )}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="url">Repository URL / Endpoint *</Label>
                <Input
                  id="url"
                  name="url"
                  placeholder={selectedType === 'repository' ? 'https://github.com/org/repo' : 'https://api.example.com'}
                  required
                />
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="branch">Branch (for repositories)</Label>
                  <Input id="branch" name="branch" placeholder="main" defaultValue="main" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="environment">Environment</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select environment" />
                    </SelectTrigger>
                    <SelectContent>
                      {ENVIRONMENTS.map(env => (
                        <SelectItem key={env} value={env}>{env.charAt(0).toUpperCase() + env.slice(1)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="criticality">Criticality *</Label>
                  <Select defaultValue="medium">
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {CRITICALITIES.map(c => (
                        <SelectItem key={c} value={c}>{c.charAt(0).toUpperCase() + c.slice(1)}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="credentials_ref">Credentials Reference (Optional)</Label>
                  <Input
                    id="credentials_ref"
                    name="credentials_ref"
                    placeholder="vault:secret/github/token"
                    type="text"
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="tags">Tags (comma-separated)</Label>
                <Input id="tags" name="tags" placeholder="production, team-backend, pci-dss" />
              </div>
            </CardContent>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setDialogOpen(false)}>Cancel</Button>
              <Button type="submit" loading={createMutation.isPending}>
                <Loader2 className="h-4 w-4 mr-2" />
                Create Asset
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
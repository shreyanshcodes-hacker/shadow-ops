'use client';

import { Shield, Zap, GitBranch, BarChart3, AlertTriangle, CheckCircle, Clock, Users, Plus, Search } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
import { api } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';
import { clsx } from 'clsx';
import Link from 'next/link';

interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan: string;
  role: string;
  created_at: string;
}

interface Asset {
  id: string;
  name: string;
  type: string;
  criticality: string;
  status: string;
  created_at: string;
}

export default function DashboardPage() {
  const { profile } = useAuth();

  const { data: workspaces, isLoading: workspacesLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.listWorkspaces(),
    staleTime: 5 * 60 * 1000,
  });

  const { data: assets, isLoading: assetsLoading } = useQuery({
    queryKey: ['assets', workspaces?.[0]?.id],
    queryFn: () => workspaces?.[0]?.id ? api.listAssets(workspaces[0].id) : [],
    enabled: !!workspaces?.[0]?.id,
    staleTime: 5 * 60 * 1000,
  });

  const stats = [
    { label: 'Workspaces', value: workspaces?.length || 0, icon: Shield, color: 'text-accent-DEFAULT' },
    { label: 'Assets Monitored', value: assets?.length || 0, icon: GitBranch, color: 'text-status-success' },
    { label: 'Active Workspace', value: workspaces?.[0]?.name || 'None', icon: Users, sub: workspaces?.[0]?.slug, color: 'text-foreground-DEFAULT' },
    { label: 'Security Score', value: '—', icon: BarChart3, sub: 'Requires scan', color: 'text-foreground-muted' },
  ];

  if (workspacesLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <CardSkeleton key={i} />
          ))}
        </div>
        <CardSkeleton className="min-h-[300px]" />
        <CardSkeleton className="min-h-[300px]" />
      </div>
    );
  }

  if (!workspaces || workspaces.length === 0) {
    return (
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-foreground-DEFAULT">Dashboard</h1>
            <p className="text-sm text-foreground-muted mt-1">
              Welcome to your security operations center
            </p>
          </div>
        </div>

        <EmptyState
          icon="Shield"
          title="No Workspaces Yet"
          description="Create your first workspace to start monitoring your assets and security posture."
          action={
            <Button onClick={() => {}} className="w-full sm:w-auto">
              <Plus className="h-4 w-4 mr-2" />
              Create Workspace
            </Button>
          }
        />
      </div>
    );
  }

  const activeWorkspace = workspaces[0];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">Dashboard</h1>
          <p className="text-sm text-foreground-muted mt-1">
            {activeWorkspace ? `Workspace: ${activeWorkspace.name}` : 'No active workspace'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="success" dot>System Operational</Badge>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="card-hover">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
                    {stat.label}
                  </p>
                  <p className="text-3xl font-bold text-foreground-DEFAULT mt-1">
                    {typeof stat.value === 'string' ? stat.value : stat.value}
                  </p>
                  {stat.sub && (
                    <p className="text-xs text-foreground-subtle mt-1">{stat.sub}</p>
                  )}
                </div>
                <div className="p-2 rounded-lg bg-accent-glow">
                  <stat.icon className={`h-6 w-6 ${stat.color}`} />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Recent Assets</CardTitle>
            <Link href="/assets" className="text-sm text-accent-DEFAULT hover:text-accent-light font-medium">
              View all →
            </Link>
          </CardHeader>
          <CardContent>
            {assetsLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 3 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            ) : assets && assets.length > 0 ? (
              <div className="space-y-3">
                {assets.slice(0, 5).map((asset) => (
                  <div key={asset.id} className="flex items-center gap-3 p-3 hover:bg-background-tertiary/50 rounded-lg transition-colors">
                    <div className="p-2 rounded-lg bg-accent-glow">
                      {asset.type === 'repository' && <GitBranch className="h-5 w-5 text-accent-DEFAULT" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-foreground-DEFAULT truncate">{asset.name}</p>
                      <p className="text-xs text-foreground-subtle font-mono capitalize">{asset.type}</p>
                    </div>
                    <StatusBadge status={asset.criticality as any} />
                    <StatusBadge status={asset.status as any} />
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState
                icon="Database"
                title="No Assets Yet"
                description="Add your first repository or API to start monitoring."
                action={
                  <Button onClick={() => {}} size="sm">
                    <Plus className="h-4 w-4 mr-2" />
                    Add Asset
                  </Button>
                }
              />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Workspaces</CardTitle>
            <Link href="/team" className="text-sm text-accent-DEFAULT hover:text-accent-light font-medium">
              Manage →
            </Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {workspaces.map((ws) => (
                <Link key={ws.id} href="/team" className="flex items-center gap-3 p-3 hover:bg-background-tertiary/50 rounded-lg transition-colors">
                  <div className="p-2 rounded-lg bg-accent-glow">
                    <Shield className="h-5 w-5 text-accent-DEFAULT" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground-DEFAULT truncate">{ws.name}</p>
                    <p className="text-xs text-foreground-subtle font-mono">{ws.slug}</p>
                  </div>
                  <Badge variant="outline" className="capitalize">{ws.role}</Badge>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Quick Actions</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button asChild>
              <Link href="/assets">
                <Plus className="h-4 w-4" />
                Add Asset
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/team">
                <Users className="h-4 w-4" />
                Invite Team
              </Link>
            </Button>
            <Button variant="secondary" asChild>
              <Link href="/settings">
                <Search className="h-4 w-4" />
                Workspace Settings
              </Link>
            </Button>
            <Button variant="secondary" disabled>
              <Zap className="h-4 w-4" />
              Start Scan
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
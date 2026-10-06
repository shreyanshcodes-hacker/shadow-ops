'use client';

import { Shield, Zap, GitBranch, BarChart3, AlertTriangle, CheckCircle, Clock, Users } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { useAuth } from '@/hooks/useAuth';
import { clsx } from 'clsx';

const stats = [
  { label: 'Security Score', value: '94', icon: Shield, trend: '+2%', trendUp: true },
  { label: 'Open Findings', value: '12', icon: AlertTriangle, sub: '3 critical, 4 high', color: 'text-severity-critical' },
  { label: 'Assets Monitored', value: '8', icon: GitBranch, sub: '5 repos, 3 APIs' },
  { label: 'Scans This Week', value: '24', icon: Zap, sub: '22 passed, 2 partial' },
];

const recentScans = [
  { id: '1', asset: 'api-gateway', type: 'full', status: 'completed', time: '2h ago', findings: '3 new' },
  { id: '2', asset: 'web-app', type: 'code', status: 'completed', time: '5h ago', findings: '0 new' },
  { id: '3', asset: 'infra-aws', type: 'recon', status: 'running', time: '10m ago', findings: '—' },
  { id: '4', asset: 'mobile-api', type: 'dependency', status: 'completed', time: '1d ago', findings: '1 new' },
];

const topFindings = [
  { id: '1', title: 'SQL Injection in User Search', severity: 'critical', asset: 'api-gateway', status: 'open' },
  { id: '2', title: 'Hardcoded AWS Credentials', severity: 'high', asset: 'web-app', status: 'triaged' },
  { id: '3', title: 'Missing Rate Limiting', severity: 'high', asset: 'api-gateway', status: 'in_progress' },
  { id: '4', title: 'Outdated Dependency: lodash@4.17.20', severity: 'medium', asset: 'mobile-api', status: 'open' },
];

export function Dashboard() {
  const { user, loading } = useAuth();

  if (loading) {
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">
            Dashboard
          </h1>
          <p className="text-sm text-foreground-muted mt-1">
            Welcome back, {user?.displayName || user?.email?.split('@')[0] || 'User'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="success" dot>System Operational</Badge>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => (
          <Card key={stat.label} className="card-hover">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium text-foreground-muted uppercase tracking-wide">
                    {stat.label}
                  </p>
                  <p className="text-3xl font-bold text-foreground-DEFAULT mt-1">{stat.value}</p>
                  {stat.sub && (
                    <p className="text-xs text-foreground-subtle mt-1">{stat.sub}</p>
                  )}
                  {stat.trend && (
                    <p className={clsx('text-xs font-medium mt-1', stat.trendUp ? 'text-status-success' : 'text-status-error')}>
                      {stat.trend} vs last week
                    </p>
                  )}
                </div>
                <div className="p-2 rounded-lg bg-accent-glow">
                  <stat.icon className="h-6 w-6 text-accent-DEFAULT" />
                </div>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Recent Scans & Top Findings */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Recent Scans */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Scans</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <table className="table">
                <thead>
                  <tr>
                    <th className="w-8"></th>
                    <th>Asset</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Findings</th>
                  </tr>
                </thead>
                <tbody>
                  {recentScans.map((scan) => (
                    <tr key={scan.id}>
                      <td>
                        <div className="w-2 h-2 rounded-full bg-accent-DEFAULT" />
                      </td>
                      <td className="font-mono text-sm">{scan.asset}</td>
                      <td>
                        <Badge variant="pending" className="capitalize">{scan.type}</Badge>
                      </td>
                      <td>
                        <StatusBadge status={scan.status} />
                      </td>
                      <td className="text-sm text-foreground-muted">{scan.time}</td>
                      <td className="text-sm font-mono text-foreground-muted">{scan.findings}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 pt-4 border-t border-border-DEFAULT">
              <a href="#" className="text-sm text-accent-DEFAULT hover:text-accent-light font-medium">
                View all scans →
              </a>
            </div>
          </CardContent>
        </Card>

        {/* Top Findings */}
        <Card>
          <CardHeader>
            <CardTitle>Top Findings</CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <div className="space-y-3">
              {topFindings.map((finding) => (
                <div key={finding.id} className="flex items-center gap-3 p-3 hover:bg-background-tertiary/50 rounded-lg transition-colors">
                  <StatusBadge status={finding.severity} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-foreground-DEFAULT truncate">{finding.title}</p>
                    <p className="text-xs text-foreground-subtle font-mono">{finding.asset}</p>
                  </div>
                  <StatusBadge status={finding.status} />
                </div>
              ))}
            </div>
            <div className="mt-4 pt-4 border-t border-border-DEFAULT">
              <a href="#" className="text-sm text-accent-DEFAULT hover:text-accent-light font-medium">
                View all findings →
              </a>
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
            <button className="btn-primary">
              <Zap className="h-4 w-4" />
              Start New Scan
            </button>
            <button className="btn-secondary">
              <GitBranch className="h-4 w-4" />
              Add Asset
            </button>
            <button className="btn-secondary">
              <Shield className="h-4 w-4" />
              View Reports
            </button>
            <button className="btn-secondary">
              <Users className="h-4 w-4" />
              Invite Team
            </button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
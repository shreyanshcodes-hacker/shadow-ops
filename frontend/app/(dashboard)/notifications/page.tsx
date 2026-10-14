'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '@/lib/api';
import { NotificationListResponse, NotificationPriority, NotificationChannel } from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { Bell, BellOff, Check, X, Filter, ChevronDown, AlertTriangle, Zap, Shield, Bug, Clock, RotateCcw } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Skeleton, CardSkeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/Popover';
import { Checkbox } from '@/components/ui/Checkbox';
import { formatDistanceToNow, format } from 'date-fns';
import { clsx } from 'clsx';

const priorityColors: Record<NotificationPriority, string> = {
  low: 'bg-gray-100 text-gray-800',
  normal: 'bg-blue-100 text-blue-800',
  high: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800',
};

const channelIcons: Record<NotificationChannel, React.ReactNode> = {
  in_app: <Bell className="h-3 w-3" />,
  email: <Zap className="h-3 w-3" />,
};

const typeIcons: Record<string, React.ReactNode> = {
  finding_critical_high: <AlertTriangle className="h-4 w-4 text-red-500" />,
  finding_severity_changed: <Bug className="h-4 w-4 text-orange-500" />,
  scan_failed: <Zap className="h-4 w-4 text-red-500" />,
  scan_completed: <Check className="h-4 w-4 text-green-500" />,
  attack_path_created: <Shield className="h-4 w-4 text-purple-500" />,
  risk_score_changed: <Bug className="h-4 w-4 text-yellow-500" />,
  remediation_awaiting_approval: <Clock className="h-4 w-4 text-blue-500" />,
  remediation_approved: <Check className="h-4 w-4 text-green-500" />,
  remediation_rejected: <X className="h-4 w-4 text-red-500" />,
  remediation_applied: <Shield className="h-4 w-4 text-green-500" />,
  remediation_failed: <AlertTriangle className="h-4 w-4 text-red-500" />,
  remediation_rolled_back: <RotateCcw className="h-4 w-4 text-orange-500" />,
  verification_completed: <Check className="h-4 w-4 text-green-500" />,
  verification_failed: <AlertTriangle className="h-4 w-4 text-red-500" />,
  verification_inconclusive: <Bug className="h-4 w-4 text-yellow-500" />,
  report_generated: <Shield className="h-4 w-4 text-blue-500" />,
  report_generation_failed: <AlertTriangle className="h-4 w-4 text-red-500" />,
  security_team_completed: <Shield className="h-4 w-4 text-purple-500" />,
};

export default function NotificationsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { currentWorkspace } = useAuthContext();
  const [notifications, setNotifications] = useState<NotificationListResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    status: searchParams.get('status') || '',
    priority: searchParams.get('priority') || '',
    type: searchParams.get('type') || '',
    page: parseInt(searchParams.get('page') || '1'),
    limit: 20,
  });
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);

  const fetchNotifications = useCallback(async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set('workspace_id', currentWorkspace.id);
      if (filters.status) params.set('status', filters.status);
      if (filters.priority) params.set('priority', filters.priority);
      if (filters.type) params.set('type', filters.type);
      params.set('limit', filters.limit.toString());
      params.set('offset', ((filters.page - 1) * filters.limit).toString());

      const data = await api.listNotifications(currentWorkspace.id, Object.fromEntries(params));
      setNotifications(data);
      setTotal(data.length);
    } catch (err: any) {
      setError(err.message || 'Failed to load notifications');
    } finally {
      setLoading(false);
    }
  }, [currentWorkspace, filters]);

  const fetchUnreadCount = useCallback(async () => {
    if (!currentWorkspace) return;
    try {
      const data = await api.getUnreadCount(currentWorkspace.id);
      setUnreadCount(data.unread_count);
    } catch {
      // Ignore error
    }
  }, [currentWorkspace]);

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchNotifications();
    fetchUnreadCount();
  }, [currentWorkspace, filters, fetchNotifications, fetchUnreadCount]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters(prev => ({ ...prev, [key]: value, page: 1 }));
    const params = new URLSearchParams(searchParams);
    if (value) params.set(key, value);
    else params.delete(key);
    params.set('page', '1');
    router.push(`/notifications?${params.toString()}`);
  };

  const handlePageChange = (page: number) => {
    setFilters(prev => ({ ...prev, page }));
    const params = new URLSearchParams(searchParams);
    params.set('page', page.toString());
    router.push(`/notifications?${params.toString()}`);
  };

  const handleMarkRead = async (notificationId: string, index: number) => {
    try {
      await api.markNotificationRead(notificationId);
      setNotifications(prev => prev.map((n, i) => i === index ? { ...n, read_at: new Date().toISOString() } : n));
    } catch (err: any) {
      console.error('Failed to mark as read:', err);
    }
  };

  const handleMarkAllRead = async () => {
    if (!currentWorkspace) return;
    try {
      await api.markAllRead(currentWorkspace.id);
      setNotifications(prev => prev.map(n => ({ ...n, read_at: new Date().toISOString() })));
      setUnreadCount(0);
    } catch (err: any) {
      console.error('Failed to mark all as read:', err);
    }
  };

  const typeOptions = [
    { value: '', label: 'All Types' },
    { value: 'finding_critical_high', label: 'Critical/High Findings' },
    { value: 'finding_severity_changed', label: 'Finding Severity Changed' },
    { value: 'scan_failed', label: 'Scan Failed' },
    { value: 'scan_completed', label: 'Scan Completed' },
    { value: 'attack_path_created', label: 'Attack Path Created' },
    { value: 'risk_score_changed', label: 'Risk Score Changed' },
    { value: 'remediation_awaiting_approval', label: 'Remediation Awaiting Approval' },
    { value: 'remediation_approved', label: 'Remediation Approved' },
    { value: 'remediation_rejected', label: 'Remediation Rejected' },
    { value: 'remediation_applied', label: 'Remediation Applied' },
    { value: 'remediation_failed', label: 'Remediation Failed' },
    { value: 'remediation_rolled_back', label: 'Remediation Rolled Back' },
    { value: 'verification_completed', label: 'Verification Completed' },
    { value: 'verification_failed', label: 'Verification Failed' },
    { value: 'verification_inconclusive', label: 'Verification Inconclusive' },
    { value: 'report_generated', label: 'Report Generated' },
    { value: 'report_generation_failed', label: 'Report Generation Failed' },
    { value: 'security_team_completed', label: 'Security Team Completed' },
  ];

  const priorityOptions = [
    { value: '', label: 'All Priorities' },
    { value: 'critical', label: 'Critical' },
    { value: 'high', label: 'High' },
    { value: 'normal', label: 'Normal' },
    { value: 'low', label: 'Low' },
  ];

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'unread', label: 'Unread' },
    { value: 'read', label: 'Read' },
  ];

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Bell className="h-6 w-6 text-accent-DEFAULT" />
            Notifications
            {unreadCount > 0 && (
              <span className="inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform rounded-full bg-red-500">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </h1>
        </div>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <Button variant="secondary" size="sm" onClick={handleMarkAllRead}>
              <Check className="h-4 w-4 mr-2" />
              Mark all as read
            </Button>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 space-y-4">
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <Select value={filters.status} onValueChange={e => handleFilterChange('status', e.target.value)}>
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                {statusOptions.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Priority</label>
            <Select value={filters.priority} onValueChange={e => handleFilterChange('priority', e.target.value)}>
              <SelectTrigger>
                <SelectValue placeholder="All Priorities" />
              </SelectTrigger>
              <SelectContent>
                {priorityOptions.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex-1 min-w-[250px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
            <Select value={filters.type} onValueChange={e => handleFilterChange('type', e.target.value)}>
              <SelectTrigger>
                <SelectValue placeholder="All Types" />
              </SelectTrigger>
              <SelectContent>
                {typeOptions.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Notifications List */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {loading ? (
          <div className="space-y-4 p-6">
            {Array.from({ length: 5 }).map((_, i) => (
              <CardSkeleton key={i} className="h-20" />
            ))}
          </div>
        ) : notifications.length === 0 ? (
          <div className="p-12 text-center">
            <BellOff className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No notifications</h3>
            <p className="text-gray-500">You're all caught up! New notifications will appear here.</p>
          </div>
        ) : (
          <>
            <div className="divide-y divide-gray-200">
              {notifications.map((notification, index) => (
                <div
                  key={notification.id}
                  className={`p-4 hover:bg-gray-50 transition-colors ${notification.read_at ? '' : 'bg-blue-50/50'}`}
                >
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-100 flex items-center justify-center">
                      {typeIcons[notification.type] || <Bell className="h-5 w-5 text-gray-500" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3">
                        <h4 className="font-medium text-gray-900 truncate">{notification.title}</h4>
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${priorityColors[notification.priority as NotificationPriority]}`}>
                          {notification.priority}
                        </span>
                        <span className="flex items-center gap-1 text-xs text-gray-500">
                          {notification.channels.map((c, i) => (
                            <span key={i} className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-700">
                              {channelIcons[c as NotificationChannel]}
                              {c}
                            </span>
                          ))}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1 line-clamp-2">{notification.message}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                        <span>{formatDistanceToNow(new Date(notification.created_at), { addSuffix: true })}</span>
                        <span className="font-mono text-gray-400">{notification.id.slice(0, 8)}...</span>
                        {notification.reference_type && (
                          <span>{notification.reference_type}: <span className="font-mono">{notification.reference_id?.slice(0, 8)}...</span></span>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!notification.read_at && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleMarkRead(notification.id, index)}
                          className="p-2"
                        >
                          <Check className="h-4 w-4 text-green-600" />
                          <span className="sr-only">Mark as read</span>
                        </Button>
                      )}
                      {notification.action_url && (
                        <a
                          href={notification.action_url}
                          className="text-sm font-medium text-accent-DEFAULT hover:text-accent-light flex items-center gap-1"
                        >
                          {notification.action_label || 'View'}
                          <RotateCcw className="h-3 w-3" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Pagination */}
            <div className="px-6 py-4 border-t border-gray-200">
              <div className="flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Showing {((filters.page - 1) * filters.limit) + 1} to {Math.min(filters.page * filters.limit, total)} of {total} results
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(filters.page - 1)}
                    disabled={filters.page <= 1}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(filters.page + 1)}
                    disabled={filters.page * filters.limit >= total}
                  >
                    Next
                  </Button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
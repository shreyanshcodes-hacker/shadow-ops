'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { NotificationPreferenceResponse, NotificationPreferenceCategory, NotificationRuleResponse, NotificationRuleCreate, RuleRecipientPolicy } from '@/lib/api';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Switch } from '@/components/ui/Switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Checkbox } from '@/components/ui/Checkbox';
import { Switch } from '@/components/ui/Switch';
import { Bell, Mail, Shield, Users, Settings, Plus, Trash2, Edit2, Save, X, Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { clsx } from 'clsx';

const CATEGORY_LABELS: Record<string, string> = {
  finding_critical_high: 'Critical & High Findings',
  finding_severity_changed: 'Finding Severity Changed',
  scan_failed: 'Scan Failed',
  scan_completed: 'Scan Completed',
  attack_path_created: 'Attack Path Created',
  risk_score_changed: 'Risk Score Changed',
  remediation_awaiting_approval: 'Remediation Awaiting Approval',
  remediation_approved: 'Remediation Approved',
  remediation_rejected: 'Remediation Rejected',
  remediation_applied: 'Remediation Applied',
  remediation_failed: 'Remediation Failed',
  remediation_rolled_back: 'Remediation Rolled Back',
  verification_completed: 'Verification Completed',
  verification_failed: 'Verification Failed',
  verification_inconclusive: 'Verification Inconclusive',
  report_generated: 'Report Generated',
  report_generation_failed: 'Report Generation Failed',
  security_team_completed: 'Security Team Completed',
};

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  finding_critical_high: <span className="text-red-500">⚠</span>,
  finding_severity_changed: <span className="text-orange-500">🔧</span>,
  scan_failed: <span className="text-red-500">⚡</span>,
  scan_completed: <span className="text-green-500">✓</span>,
  attack_path_created: <span className="text-purple-500">🛡</span>,
  risk_score_changed: <span className="text-yellow-500">📊</span>,
  remediation_awaiting_approval: <span className="text-blue-500">⏰</span>,
  remediation_approved: <span className="text-green-500">✓</span>,
  remediation_rejected: <span className="text-red-500">✗</span>,
  remediation_applied: <span className="text-green-500">✓</span>,
  remediation_failed: <span className="text-red-500">✗</span>,
  remediation_rolled_back: <span className="text-orange-500">↶</span>,
  verification_completed: <span className="text-green-500">✓</span>,
  verification_failed: <span className="text-red-500">✗</span>,
  verification_inconclusive: <span className="text-yellow-500">?</span>,
  report_generated: <span className="text-blue-500">📄</span>,
  report_generation_failed: <span className="text-red-500">✗</span>,
  security_team_completed: <span className="text-purple-500">🤖</span>,
};

const RECIPIENT_POLICY_LABELS: Record<string, string> = {
  asset_owners: 'Asset Owners',
  asset_members: 'Asset Members',
  workspace_admins: 'Workspace Admins',
  workspace_owners: 'Workspace Owners',
  specific_users: 'Specific Users',
  finding_assignees: 'Finding Assignees',
  remediation_approvers: 'Remediation Approvers',
};

const SEVERITY_OPTIONS = [
  { value: 'critical', label: 'Critical' },
  { value: 'high', label: 'High' },
  { value: 'medium', label: 'Medium' },
  { value: 'low', label: 'Low' },
  { value: 'info', label: 'Info' },
];

const STATUS_OPTIONS = [
  { value: 'open', label: 'Open' },
  { value: 'triaged', label: 'Triaged' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'fixed', label: 'Fixed' },
  { value: 'false_positive', label: 'False Positive' },
  { value: 'wont_fix', label: 'Won\'t Fix' },
  { value: 'risk_accepted', label: 'Risk Accepted' },
];

const CHANNEL_OPTIONS = [
  { value: 'in_app', label: 'In-App' },
  { value: 'email', label: 'Email' },
];

const RECIPIENT_POLICIES = [
  { value: 'asset_owners', label: 'Asset Owners' },
  { value: 'asset_members', label: 'Asset Members' },
  { value: 'workspace_admins', label: 'Workspace Admins' },
  { value: 'workspace_owners', label: 'Workspace Owners' },
  { value: 'specific_users', label: 'Specific Users' },
  { value: 'finding_assignees', label: 'Finding Assignees' },
  { value: 'remediation_approvers', label: 'Remediation Approvers' },
];

export default function NotificationSettingsPage() {
  const router = useRouter();
  const { currentWorkspace } = useAuthContext();
  const [preferences, setPreferences] = useState<any[]>([]);
  const [rules, setRules] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'preferences' | 'rules'>('preferences');
  const [creatingRule, setCreatingRule] = useState(false);
  const [editingRule, setEditingRule] = useState<any | null>(null);
  const [ruleForm, setRuleForm] = useState({
    name: '',
    description: '',
    event_type: 'finding_critical_high',
    event_version: '1.0',
    is_enabled: true,
    recipient_policy: 'asset_owners',
    specific_recipient_ids: [] as string[],
    severity_filter: ['critical', 'high', 'medium', 'low', 'info'],
    status_filter: ['open', 'triaged', 'in_progress'],
    enabled_channels: ['in_app'],
    deduplication_window_minutes: 60,
    rate_limit_per_hour: 100,
    require_acknowledgement: false,
    acknowledgement_timeout_hours: undefined,
    priority: 'normal',
    action_url_template: '',
    action_label_template: '',
    description: '',
  });

  useEffect(() => {
    if (!currentWorkspace) return;
    fetchData();
  }, [currentWorkspace]);

  const fetchData = async () => {
    if (!currentWorkspace) return;
    setLoading(true);
    setError(null);
    try {
      const [prefsData, rulesData] = await Promise.all([
        api.getPreferences(currentWorkspace.id),
        api.listRules(currentWorkspace.id),
      ]);
      setPreferences(prefsData);
      setRules(rulesData);
    } catch (err: any) {
      setError(err.message || 'Failed to load settings');
    } finally {
      setLoading(false);
    }
  };

  const handlePreferenceChange = async (category: string, channel: 'in_app' | 'email', enabled: boolean) => {
    try {
      await api.updatePreference(currentWorkspace!.id, category, {
        [channel === 'in_app' ? 'in_app_enabled' : 'email_enabled']: enabled,
      });
      setPreferences(prev => prev.map(p => 
        p.category === category 
          ? { ...p, [channel === 'in_app' ? 'in_app_enabled' : 'email_enabled']: enabled }
          : p
      ));
    } catch (err: any) {
      alert(err.message || 'Failed to update preference');
    }
  };

  const handleCreateRule = async () => {
    try {
      await api.createRule(currentWorkspace!.id, ruleForm);
      setCreatingRule(false);
      setRuleForm({
        name: '',
        description: '',
        event_type: 'finding_critical_high',
        event_version: '1.0',
        is_enabled: true,
        recipient_policy: 'asset_owners',
        specific_recipient_ids: [],
        severity_filter: ['critical', 'high', 'medium', 'low', 'info'],
        status_filter: ['open', 'triaged', 'in_progress'],
        enabled_channels: ['in_app'],
        deduplication_window_minutes: 60,
        rate_limit_per_hour: 100,
        require_acknowledgement: false,
        acknowledgement_timeout_hours: undefined,
        priority: 'normal',
        action_url_template: '',
        action_label_template: '',
        description: '',
      });
      const rulesData = await api.listRules(currentWorkspace!.id);
      setRules(rulesData);
    } catch (err: any) {
      alert(err.message || 'Failed to create rule');
    }
  };

  const handleUpdateRule = async (ruleId: string) => {
    try {
      await api.updateRule(editingRule.id, ruleForm);
      setEditingRule(null);
      setRuleForm({
        name: '',
        description: '',
        event_type: 'finding_critical_high',
        event_version: '1.0',
        is_enabled: true,
        recipient_policy: 'asset_owners',
        specific_recipient_ids: [],
        severity_filter: ['critical', 'high', 'medium', 'low', 'info'],
        status_filter: ['open', 'triaged', 'in_progress'],
        enabled_channels: ['in_app'],
        deduplication_window_minutes: 60,
        rate_limit_per_hour: 100,
        require_acknowledgement: false,
        acknowledgement_timeout_hours: undefined,
        priority: 'normal',
        action_url_template: '',
        action_label_template: '',
        description: '',
      });
      const rulesData = await api.listRules(currentWorkspace!.id);
      setRules(rulesData);
    } catch (err: any) {
      alert(err.message || 'Failed to update rule');
    }
  };

  const handleDeleteRule = async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      await api.deleteRule(ruleId);
      setRules(prev => prev.filter(r => r.id !== ruleId));
    } catch (err: any) {
      alert(err.message || 'Failed to delete rule');
    }
  };

  const handleEditRule = (rule: any) => {
    setEditingRule(rule);
    setRuleForm({
      name: rule.name,
      description: rule.description || '',
      event_type: rule.event_type,
      event_version: rule.event_version,
      is_enabled: rule.is_enabled,
      recipient_policy: rule.recipient_policy,
      specific_recipient_ids: rule.specific_recipient_ids,
      severity_filter: rule.severity_filter,
      status_filter: rule.status_filter,
      enabled_channels: rule.enabled_channels,
      deduplication_window_minutes: rule.deduplication_window_minutes,
      rate_limit_per_hour: rule.rate_limit_per_hour,
      require_acknowledgement: rule.require_acknowledgement,
      acknowledgement_timeout_hours: rule.acknowledgement_timeout_hours,
      priority: rule.priority,
      action_url_template: rule.action_url_template || '',
      action_label_template: rule.action_label_template || '',
      description: rule.description || '',
    });
    setCreatingRule(false);
  };

  const handleCancelRule = () => {
    setCreatingRule(false);
    setEditingRule(null);
    setRuleForm({
      name: '',
      description: '',
      event_type: 'finding_critical_high',
      event_version: '1.0',
      is_enabled: true,
      recipient_policy: 'asset_owners',
      specific_recipient_ids: [],
      severity_filter: ['critical', 'high', 'medium', 'low', 'info'],
      status_filter: ['open', 'triaged', 'in_progress'],
      enabled_channels: ['in_app'],
      deduplication_window_minutes: 60,
      rate_limit_per_hour: 100,
      require_acknowledgement: false,
      acknowledgement_timeout_hours: undefined,
      priority: 'normal',
      action_url_template: '',
      action_label_template: '',
      description: '',
    });
  };

  if (!currentWorkspace) {
    return (
      <div className="p-6 text-center">
        <p className="text-gray-500">No workspace selected</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-6 space-y-6 animate-pulse">
        <CardSkeleton />
        <CardSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 text-center">
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg max-w-md mx-auto">
          {error}
          <Button className="mt-2" onClick={fetchData}>Retry</Button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notification Settings</h1>
          <p className="text-gray-500 mt-1">Configure how you receive security notifications</p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-8" aria-label="Tabs">
          <button
            onClick={() => setActiveTab('preferences')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'preferences'
                ? 'border-accent-DEFAULT text-accent-DEFAULT'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Bell className="h-4 w-4 mr-2 inline" />
            Preferences
          </button>
          <button
            onClick={() => setActiveTab('rules')}
            className={`py-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'rules'
                ? 'border-accent-DEFAULT text-accent-DEFAULT'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            <Shield className="h-4 w-4 mr-2 inline" />
            Rules
          </button>
        </nav>
      </div>

      {/* Preferences Tab */}
      {activeTab === 'preferences' && (
        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Notification Preferences</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-gray-500 mb-6">
                Choose which notifications you want to receive and through which channels.
                In-app notifications are always available in the <a href="/notifications" className="text-accent-DEFAULT hover:underline">Notification Center</a>.
              </p>

              <div className="overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200">
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Category</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">In-App</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {Object.values(NotificationPreferenceCategory).map(category => {
                      const pref = preferences.find(p => p.category === category) || {
                        category,
                        in_app_enabled: true,
                        email_enabled: false,
                      };
                      const Icon = CATEGORY_ICONS[category];
                      return (
                        <tr key={category} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-3">
                              <span className="text-lg">{CATEGORY_ICONS[category]}</span>
                              <div>
                                <p className="font-medium text-gray-900">{CATEGORY_LABELS[category]}</p>
                                <p className="text-xs text-gray-500">{category.replace(/_/g, ' ')}</p>
                              </div>
                            </div>
                          </td>
                          <td className="px-4 py-3">
                            <Switch
                              checked={preferences.find(p => p.category === category)?.in_app_enabled ?? true}
                              onCheckedChange={(checked) => handlePreferenceChange(category, 'in_app', checked)}
                            />
                          </td>
                          <td className="px-4 py-3">
                            <Switch
                              checked={preferences.find(p => p.category === category)?.email_enabled ?? false}
                              onCheckedChange={(checked) => handlePreferenceChange(category, 'email', checked)}
                            />
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
      </div>
    </div>
  );
}
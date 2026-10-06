'use client';

import { useState } from 'react';
import { User, Shield, Key, Bell, Palette, Loader2, CheckCircle } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/Dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { useAuth } from '@/hooks/useAuth';
import { useWorkspace } from '@/hooks/useWorkspace';
import { api, type Workspace } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';

export default function SettingsPage() {
  const { profile, user, isAuthenticated } = useAuth();
  const { workspaceId, workspaces, switchWorkspace } = useWorkspace();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'profile' | 'workspace' | 'security' | 'notifications' | 'appearance'>('profile');
  const [displayName, setDisplayName] = useState(profile?.display_name || user?.displayName || '');
  const [saving, setSaving] = useState(false);

  const updateProfileMutation = useMutation({
    mutationFn: async (data: { display_name: string }) => {
      const token = await (await import('@/lib/auth')).getFirebaseToken();
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/me`, {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(data),
      });
      if (!response.ok) throw new Error('Failed to update profile');
      return response.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['profile'] });
      setSaving(false);
    },
  });

  const handleProfileSave = (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    updateProfileMutation.mutate({ display_name: displayName });
  };

  const tabs = [
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'workspace', label: 'Workspace', icon: Shield },
    { id: 'security', label: 'Security', icon: Key },
    { id: 'notifications', label: 'Notifications', icon: Bell },
    { id: 'appearance', label: 'Appearance', icon: Palette },
  ];

  const currentWorkspace = workspaces.find(w => w.id === workspaceId);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold text-foreground-DEFAULT">Settings</h1>
        <p className="text-sm text-foreground-muted mt-1">Manage your account and workspace preferences</p>
      </div>

      <div className="flex gap-2 border-b border-border-DEFAULT overflow-x-auto">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={clsx(
              'flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 transition-colors whitespace-nowrap',
              activeTab === tab.id
                ? 'border-accent-DEFAULT text-accent-DEFAULT'
                : 'border-transparent text-foreground-muted hover:text-foreground-DEFAULT'
            )}
          >
            <tab.icon className="h-4 w-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {activeTab === 'profile' && (
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
            <CardDescription>Manage your personal information</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleProfileSave} className="space-y-6">
              <div className="flex items-center gap-6">
                <div className="relative h-20 w-20 rounded-full bg-accent-glow flex items-center justify-center overflow-hidden">
                  {profile?.avatar_url || user?.photoURL ? (
                    <img src={profile?.avatar_url || user?.photoURL} alt="" className="h-full w-full object-cover" />
                  ) : (
                    <svg className="h-10 w-10 text-accent-DEFAULT" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
                    </svg>
                  )}
                </div>
                <div>
                  <p className="text-sm text-foreground-muted">Profile picture</p>
                  <Button variant="outline" size="sm" type="button">Change</Button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="displayName">Display Name</Label>
                <Input id="displayName" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input id="email" value={profile?.email || user?.email || ''} disabled />
                <p className="text-xs text-foreground-muted">Email cannot be changed. Contact support if needed.</p>
              </div>

              <div className="space-y-2">
                <Label>User ID</Label>
                <Input value={profile?.id || '—'} disabled />
              </div>

              <div className="space-y-2">
                <Label>Firebase UID</Label>
                <Input value={profile?.firebase_uid || '—'} disabled />
              </div>

              <div className="flex justify-end pt-4 border-t border-border-DEFAULT">
                <Button type="submit" loading={saving}>
                  <Loader2 className="h-4 w-4 mr-2" />
                  Save Changes
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {activeTab === 'workspace' && currentWorkspace && (
        <Card>
          <CardHeader>
            <CardTitle>Workspace Settings</CardTitle>
            <CardDescription>Configure workspace preferences for {currentWorkspace.name}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label htmlFor="workspaceName">Workspace Name</Label>
              <Input id="workspaceName" defaultValue={currentWorkspace.name} disabled />
            </div>

            <div className="space-y-2">
              <Label htmlFor="workspaceSlug">Slug</Label>
              <Input id="workspaceSlug" defaultValue={currentWorkspace.slug} disabled />
            </div>

            <div className="space-y-2">
              <Label>Plan</Label>
              <div className="flex items-center gap-2">
                <Badge variant="outline">{currentWorkspace.plan}</Badge>
                <Button variant="outline" size="sm" asChild>
                  <a href="/settings/billing">Manage Billing</a>
                </Button>
              </div>
            </div>

            <div className="pt-4 border-t border-border-DEFAULT">
              <h3 className="font-medium text-foreground-DEFAULT mb-4">Danger Zone</h3>
              <div className="flex items-center justify-between p-4 rounded-lg bg-status-error/10 border border-status-error/20">
                <div>
                  <p className="font-medium text-status-error">Delete Workspace</p>
                  <p className="text-sm text-foreground-muted">Permanently delete this workspace and all its data.</p>
                </div>
                <Button variant="destructive" size="sm">Delete Workspace</Button>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'security' && (
        <Card>
          <CardHeader>
            <CardTitle>Security</CardTitle>
            <CardDescription>Manage your authentication and security settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Two-Factor Authentication</p>
                  <p className="text-sm text-foreground-muted">Add an extra layer of security to your account</p>
                </div>
                <Button variant="outline">Enable 2FA</Button>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Password</p>
                  <p className="text-sm text-foreground-muted">Change your password</p>
                </div>
                <Button variant="outline" asChild>
                  <a href="/auth/reset-password">Change Password</a>
                </Button>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Active Sessions</p>
                  <p className="text-sm text-foreground-muted">View and manage your active sessions</p>
                </div>
                <Button variant="outline">View Sessions</Button>
              </div>
            </div>

            <div className="pt-4 border-t border-border-DEFAULT">
              <h3 className="font-medium text-foreground-DEFAULT mb-4">API Keys</h3>
              <p className="text-sm text-foreground-muted mb-4">Manage API keys for programmatic access</p>
              <Button variant="outline" size="sm">Generate API Key</Button>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'notifications' && (
        <Card>
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
            <CardDescription>Configure how you receive notifications</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              {[
                { title: 'Email Notifications', desc: 'Receive email updates about scans, findings, and team activity', defaultChecked: true },
                { title: 'Scan Complete', desc: 'Get notified when scans finish', defaultChecked: true },
                { title: 'Critical Findings', desc: 'Immediate alerts for critical vulnerabilities', defaultChecked: true },
                { title: 'Team Activity', desc: 'Updates about member invites and role changes', defaultChecked: false },
                { title: 'Weekly Digest', desc: 'Summary of security posture every week', defaultChecked: true },
              ].map((item) => (
                <div key={item.title} className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                  <div>
                    <p className="font-medium text-foreground-DEFAULT">{item.title}</p>
                    <p className="text-sm text-foreground-muted">{item.desc}</p>
                  </div>
                  <Switch defaultChecked={item.defaultChecked} />
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'appearance' && (
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
            <CardDescription>Customize how ShadowOps looks</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-4">
              <div className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Theme</p>
                  <p className="text-sm text-foreground-muted">Choose your preferred color scheme</p>
                </div>
                <Select defaultValue="dark">
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="dark">Dark</SelectItem>
                    <SelectItem value="light">Light</SelectItem>
                    <SelectItem value="system">System</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between p-4 rounded-lg border border-border-DEFAULT">
                <div>
                  <p className="font-medium text-foreground-DEFAULT">Density</p>
                  <p className="text-sm text-foreground-muted">Adjust spacing and compactness</p>
                </div>
                <Select defaultValue="comfortable">
                  <SelectTrigger className="w-40">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="compact">Compact</SelectItem>
                    <SelectItem value="comfortable">Comfortable</SelectItem>
                    <SelectItem value="spacious">Spacious</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
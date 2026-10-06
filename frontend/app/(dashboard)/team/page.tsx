'use client';

import { useState } from 'react';
import { Plus, Users, Shield, UserCheck, UserX, Mail, Settings, Loader2, MoreHorizontal } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import { Skeleton } from '@/components/ui/Skeleton';
import { EmptyState } from '@/components/ui/EmptyState';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/Dialog';
import { Dropdown, DropdownItem, DropdownTrigger, DropdownContent, DropdownSeparator } from '@/components/ui/Dropdown';
import { Label } from '@/components/ui/Input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select';
import { useAuth } from '@/hooks/useAuth';
import { useWorkspace } from '@/hooks/useWorkspace';
import { api, type Workspace, type WorkspaceMember, type WorkspaceRole } from '@/lib/api';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { clsx } from 'clsx';

const ROLES: { value: WorkspaceRole; label: string; description: string }[] = [
  { value: 'owner', label: 'Owner', description: 'Full workspace control, billing, deletion' },
  { value: 'admin', label: 'Admin', description: 'Manage members, assets, settings' },
  { value: 'member', label: 'Member', description: 'Operational access to assets and scans' },
  { value: 'viewer', label: 'Viewer', description: 'Read-only access' },
];

export default function TeamPage() {
  const { workspaceId, workspaces, switchWorkspace, loading: workspaceLoading } = useWorkspace();
  const { profile } = useAuth();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'members' | 'workspaces'>('members');
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [createWorkspaceDialogOpen, setCreateWorkspaceDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<WorkspaceRole>('member');
  const [newWorkspaceName, setNewWorkspaceName] = useState('');
  const [newWorkspaceSlug, setNewWorkspaceSlug] = useState('');

  const { data: members, isLoading: membersLoading } = useQuery({
    queryKey: ['members', workspaceId],
    queryFn: () => workspaceId ? api.listWorkspaceMembers(workspaceId) : [],
    enabled: !!workspaceId,
    staleTime: 5 * 60 * 1000,
  });

  const inviteMutation = useMutation({
    mutationFn: ({ workspaceId, email, role }: { workspaceId: string; email: string; role: WorkspaceRole }) =>
      api.inviteMember(workspaceId, { email, role }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members', workspaceId] });
      setInviteDialogOpen(false);
      setInviteEmail('');
    },
  });

  const updateRoleMutation = useMutation({
    mutationFn: ({ workspaceId, userId, role }: { workspaceId: string; userId: string; role: WorkspaceRole }) =>
      api.updateMemberRole(workspaceId, userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members', workspaceId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: ({ workspaceId, userId }: { workspaceId: string; userId: string }) =>
      api.removeMember(workspaceId, userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['members', workspaceId] });
    },
  });

  const createWorkspaceMutation = useMutation({
    mutationFn: (data: { name: string; slug?: string }) => api.createWorkspace(data),
    onSuccess: (workspace) => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
      setCreateWorkspaceDialogOpen(false);
      setNewWorkspaceName('');
      setNewWorkspaceSlug('');
      switchWorkspace(workspace.id);
    },
  });

  const currentWorkspace = workspaces.find(w => w.id === workspaceId);

  const isOwner = members?.some(m => m.user_id === profile?.id && m.role === 'owner');

  if (workspaceLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card><CardContent><Skeleton className="h-8 w-1/4" /></CardContent></Card>
        <Card><CardContent><Skeleton className="h-64 w-full" /></CardContent></Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground-DEFAULT">Team</h1>
          <p className="text-sm text-foreground-muted mt-1">Manage workspaces and team members</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => setCreateWorkspaceDialogOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            New Workspace
          </Button>
          {workspaceId && (
            <Button onClick={() => setInviteDialogOpen(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Invite Member
            </Button>
          )}
        </div>
      </div>

      <div className="flex gap-2 border-b border-border-DEFAULT">
        <button
          onClick={() => setActiveTab('workspaces')}
          className={clsx(
            'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
            activeTab === 'workspaces'
              ? 'border-accent-DEFAULT text-accent-DEFAULT'
              : 'border-transparent text-foreground-muted hover:text-foreground-DEFAULT'
          )}
        >
          <Shield className="h-4 w-4 mr-2 inline" />
          Workspaces
        </button>
        <button
          onClick={() => setActiveTab('members')}
          className={clsx(
            'px-4 py-2 text-sm font-medium border-b-2 transition-colors',
            activeTab === 'members'
              ? 'border-accent-DEFAULT text-accent-DEFAULT'
              : 'border-transparent text-foreground-muted hover:text-foreground-DEFAULT'
          )}
        >
          <Users className="h-4 w-4 mr-2 inline" />
          Members
        </button>
      </div>

      {activeTab === 'workspaces' && (
        <Card>
          <CardContent>
            {workspaces.length === 0 ? (
              <EmptyState
                icon="Shield"
                title="No Workspaces"
                description="Create your first workspace to get started."
                action={
                  <Button onClick={() => setCreateWorkspaceDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Create Workspace
                  </Button>
                }
              />
            ) : (
              <div className="space-y-3">
                {workspaces.map((ws) => (
                  <div
                    key={ws.id}
                    className={clsx(
                      'flex items-center gap-4 p-4 rounded-lg border transition-colors',
                      ws.id === workspaceId
                        ? 'border-accent-DEFAULT/50 bg-accent-glow'
                        : 'border-border-DEFAULT hover:bg-background-tertiary/50'
                    )}
                  >
                    <div className="p-2 rounded-lg bg-accent-glow">
                      <Shield className="h-5 w-5 text-accent-DEFAULT" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground-DEFAULT truncate">{ws.name}</p>
                        <Badge variant="outline">{ws.slug}</Badge>
                        {ws.id === workspaceId && <Badge variant="success" dot>Active</Badge>}
                      </div>
                      <p className="text-sm text-foreground-muted">Role: {ws.role} • Plan: {ws.plan}</p>
                    </div>
                    {ws.id !== workspaceId && (
                      <Button variant="ghost" size="sm" onClick={() => switchWorkspace(ws.id)}>
                        Switch
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {activeTab === 'members' && (
        <Card>
          <CardContent>
            {!workspaceId ? (
              <EmptyState
                icon="Users"
                title="Select a Workspace"
                description="Choose a workspace from the Workspaces tab to manage its members."
              />
            ) : membersLoading ? (
              <div className="space-y-3">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Skeleton key={i} className="h-16 w-full" />
                ))}
              </div>
            ) : members && members.length === 0 ? (
              <EmptyState
                icon="Users"
                title="No Members Yet"
                description="Invite your security team to collaborate on this workspace."
                action={
                  <Button onClick={() => setInviteDialogOpen(true)}>
                    <Plus className="h-4 w-4 mr-2" />
                    Invite Member
                  </Button>
                }
              />
            ) : (
              <div className="space-y-3">
                {members.map((member) => (
                  <div key={member.id} className="flex items-center gap-4 p-4 border-b border-border-DEFAULT last:border-0">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground-DEFAULT truncate">
                          {member.user?.display_name || member.user?.email || 'Unknown User'}
                        </p>
                        <Badge variant="outline">{member.user?.email}</Badge>
                      </div>
                      <p className="text-sm text-foreground-muted">
                        Joined {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'Pending'}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Select defaultValue={member.role} disabled={member.role === 'owner' || member.user_id === profile?.id}>
                        <SelectTrigger className="w-36">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {ROLES.filter(r => r.value !== 'owner' || member.role === 'owner').map(role => (
                            <SelectItem key={role.value} value={role.value}>
                              {role.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {member.user_id !== profile?.id && member.role !== 'owner' && (
                        <Dropdown>
                          <DropdownTrigger className="p-2 rounded-lg hover:bg-background-tertiary" aria-label="More actions">
                            <MoreHorizontal className="h-4 w-4" />
                          </DropdownTrigger>
                          <DropdownContent align="end">
                            <DropdownItem
                              onClick={() => removeMutation.mutate({ workspaceId: workspaceId!, userId: member.user_id })}
                              className="text-status-error"
                              disabled={removeMutation.isPending}
                            >
                              <UserX className="h-4 w-4 mr-2" />
                              Remove
                            </DropdownItem>
                          </DropdownContent>
                        </Dropdown>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={inviteDialogOpen} onOpenChange={setInviteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Member</DialogTitle>
            <DialogDescription>Add a team member to {currentWorkspace?.name}</DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); inviteMutation.mutate({ workspaceId: workspaceId!, email: inviteEmail, role: inviteRole }); }}>
            <DialogContent className="space-y-4 p-6 pt-0">
              <div className="space-y-2">
                <Label htmlFor="email">Email *</Label>
                <Input
                  id="email"
                  type="email"
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="colleague@company.com"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="role">Role *</Label>
                <Select defaultValue={inviteRole} onValueChange={setInviteRole}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLES.filter(r => r.value !== 'owner').map(role => (
                      <SelectItem key={role.value} value={role.value}>
                        {role.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-foreground-muted">Owner role cannot be assigned via invitation.</p>
              </div>
            </DialogContent>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setInviteDialogOpen(false)}>Cancel</Button>
              <Button type="submit" loading={inviteMutation.isPending}>
                <Loader2 className="h-4 w-4 mr-2" />
                Send Invitation
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <Dialog open={createWorkspaceDialogOpen} onOpenChange={setCreateWorkspaceDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Workspace</DialogTitle>
            <DialogDescription>Create a new workspace for your team</DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => { e.preventDefault(); createWorkspaceMutation.mutate({ name: newWorkspaceName, slug: newWorkspaceSlug || undefined }); }}>
            <DialogContent className="space-y-4 p-6 pt-0">
              <div className="space-y-2">
                <Label htmlFor="name">Workspace Name *</Label>
                <Input
                  id="name"
                  value={newWorkspaceName}
                  onChange={(e) => setNewWorkspaceName(e.target.value)}
                  placeholder="My Security Workspace"
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="slug">Slug (Optional)</Label>
                <Input
                  id="slug"
                  value={newWorkspaceSlug}
                  onChange={(e) => setNewWorkspaceSlug(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
                  placeholder="auto-generated-from-name"
                />
                <p className="text-xs text-foreground-muted">URL-friendly identifier. Auto-generated if empty.</p>
              </div>
            </DialogContent>
            <DialogFooter>
              <Button type="button" variant="secondary" onClick={() => setCreateWorkspaceDialogOpen(false)}>Cancel</Button>
              <Button type="submit" loading={createWorkspaceMutation.isPending}>
                <Loader2 className="h-4 w-4 mr-2" />
                Create Workspace
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
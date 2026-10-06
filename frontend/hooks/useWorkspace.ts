'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useAuth } from './useAuth';
import { api, type Workspace } from '@/lib/api';
import { useQuery } from '@tanstack/react-query';

export function useWorkspace() {
  const { profile, isAuthenticated, loading: authLoading } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [workspaceId, setWorkspaceId] = useState<string | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(true);

  const { data: fetchedWorkspaces, isLoading: workspacesLoading } = useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.listWorkspaces(),
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000,
  });

  useEffect(() => {
    if (fetchedWorkspaces) {
      setWorkspaces(fetchedWorkspaces);
      setLoading(false);
    }
  }, [fetchedWorkspaces]);

  useEffect(() => {
    if (!authLoading && isAuthenticated && workspaces.length > 0) {
      const savedWorkspaceId = localStorage.getItem('activeWorkspaceId');
      const validWorkspaceId = savedWorkspaceId && workspaces.find(w => w.id === savedWorkspaceId)?.id;
      
      const targetWorkspaceId = validWorkspaceId || workspaces[0].id;
      setWorkspaceId(targetWorkspaceId);
      localStorage.setItem('activeWorkspaceId', targetWorkspaceId);
    }
  }, [authLoading, isAuthenticated, workspaces]);

  const switchWorkspace = useCallback((id: string) => {
    setWorkspaceId(id);
    localStorage.setItem('activeWorkspaceId', id);
  }, []);

  return {
    workspaceId,
    workspaces,
    loading: authLoading || workspacesLoading || loading,
    switchWorkspace,
  };
}
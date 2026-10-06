'use client';

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, type Workspace, type Asset, type Scan, type Finding, type UserProfile, type WorkspaceMember } from '@/lib/api';
import { useWorkspaceStore } from '@/lib/store';

export function useMe() {
  return useQuery({
    queryKey: ['me'],
    queryFn: () => api.getMe(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useWorkspaces() {
  return useQuery({
    queryKey: ['workspaces'],
    queryFn: () => api.listWorkspaces(),
  });
}

export function useWorkspace(workspaceId: string | null) {
  return useQuery({
    queryKey: ['workspace', workspaceId],
    queryFn: () => api.getWorkspace(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useCreateWorkspace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { name: string; slug?: string }) => api.createWorkspace(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['workspaces'] });
    },
  });
}

export function useWorkspaceMembers(workspaceId: string | null) {
  return useQuery({
    queryKey: ['workspace-members', workspaceId],
    queryFn: () => api.listWorkspaceMembers(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useInviteMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, data }: { workspaceId: string; data: { email: string; role: string } }) =>
      api.inviteMember(workspaceId, data),
    onSuccess: (_, { workspaceId }) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
    },
  });
}

export function useUpdateMemberRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, userId, role }: { workspaceId: string; userId: string; role: string }) =>
      api.updateMemberRole(workspaceId, userId, role),
    onSuccess: (_, { workspaceId }) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
    },
  });
}

export function useRemoveMember() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ workspaceId, userId }: { workspaceId: string; userId: string }) =>
      api.removeMember(workspaceId, userId),
    onSuccess: (_, { workspaceId }) => {
      queryClient.invalidateQueries({ queryKey: ['workspace-members', workspaceId] });
    },
  });
}

export function useAssets(workspaceId: string | null) {
  return useQuery({
    queryKey: ['assets', workspaceId],
    queryFn: () => api.listAssets(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useCreateAsset() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createAsset>[1]) => api.createAsset(currentWorkspaceId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets', currentWorkspaceId] });
    },
  });
}

export function useAsset(assetId: string | null) {
  return useQuery({
    queryKey: ['asset', assetId],
    queryFn: () => api.getAsset(assetId!),
    enabled: !!assetId,
  });
}

export function useUpdateAsset() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, data }: { assetId: string; data: Parameters<typeof api.updateAsset>[1] }) =>
      api.updateAsset(assetId, data),
    onSuccess: (_, { assetId }) => {
      queryClient.invalidateQueries({ queryKey: ['asset', assetId] });
      queryClient.invalidateQueries({ queryKey: ['assets'] });
    },
  });
}

export function useDeleteAsset() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: (assetId: string) => api.deleteAsset(assetId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assets', currentWorkspaceId] });
    },
  });
}

export function useAuthorization(assetId: string | null) {
  return useQuery({
    queryKey: ['authorization', assetId],
    queryFn: () => api.getAuthorization(assetId!),
    enabled: !!assetId,
  });
}

export function useCreateAuthorization() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ assetId, data }: { assetId: string; data: Parameters<typeof api.createAuthorization>[1] }) =>
      api.createAuthorization(assetId, data),
    onSuccess: (_, { assetId }) => {
      queryClient.invalidateQueries({ queryKey: ['authorization', assetId] });
    },
  });
}

export function useScans(workspaceId: string | null, params?: Record<string, string>) {
  return useQuery({
    queryKey: ['scans', workspaceId, params],
    queryFn: () => api.listScans(workspaceId!, params),
    enabled: !!workspaceId,
  });
}

export function useCreateScan() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: (data: Parameters<typeof api.createScan>[1]) => api.createScan(currentWorkspaceId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scans', currentWorkspaceId] });
    },
  });
}

export function useScan(workspaceId: string | null, scanId: string | null) {
  return useQuery({
    queryKey: ['scan', workspaceId, scanId],
    queryFn: () => api.getScan(workspaceId!, scanId!),
    enabled: !!workspaceId && !!scanId,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data && ['queued', 'running'].includes(data.status)) {
        return 3000;
      }
      return false;
    },
  });
}

export function useCancelScan() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: (scanId: string) => api.cancelScan(currentWorkspaceId!, scanId),
    onSuccess: (_, scanId) => {
      queryClient.invalidateQueries({ queryKey: ['scan', currentWorkspaceId, scanId] });
      queryClient.invalidateQueries({ queryKey: ['scans', currentWorkspaceId] });
    },
  });
}

export function useFindings(workspaceId: string | null, params?: Record<string, string>) {
  return useQuery({
    queryKey: ['findings', workspaceId, params],
    queryFn: () => api.listFindings(workspaceId!, params),
    enabled: !!workspaceId,
  });
}

export function useFinding(workspaceId: string | null, findingId: string | null) {
  return useQuery({
    queryKey: ['finding', workspaceId, findingId],
    queryFn: () => api.getFinding(workspaceId!, findingId!),
    enabled: !!workspaceId && !!findingId,
  });
}

export function useUpdateFinding() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: ({ findingId, data }: { findingId: string; data: Parameters<typeof api.updateFinding>[2] }) =>
      api.updateFinding(currentWorkspaceId!, findingId, data),
    onSuccess: (_, { findingId }) => {
      queryClient.invalidateQueries({ queryKey: ['finding', currentWorkspaceId, findingId] });
      queryClient.invalidateQueries({ queryKey: ['findings', currentWorkspaceId] });
    },
  });
}

export function useRemediations(workspaceId: string | null) {
  return useQuery({
    queryKey: ['remediations', workspaceId],
    queryFn: () => api.listRemediations(workspaceId!),
    enabled: !!workspaceId,
  });
}

export function useGenerateRemediation() {
  const queryClient = useQueryClient();
  const { currentWorkspaceId } = useWorkspaceStore();
  return useMutation({
    mutationFn: (findingId: string) => api.generateRemediation(currentWorkspaceId!, findingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['remediations', currentWorkspaceId] });
    },
  });
}

export function useReports(workspaceId: string | null) {
  return useQuery({
    queryKey: ['reports', workspaceId],
    queryFn: () => api.listReports(workspaceId!),
    enabled: !!workspaceId,
  });
}
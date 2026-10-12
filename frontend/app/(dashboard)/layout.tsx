'use client';

import { ReactNode, useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { useAuth } from '@/hooks/useAuth';
import { Sidebar, SidebarItem } from '@/components/ui/Sidebar';

const navigation: SidebarItem[] = [
  { label: 'Dashboard', href: '/dashboard', icon: 'LayoutDashboard' },
  { label: 'Scans', href: '/scans', icon: 'Search' },
  { label: 'Findings', href: '/findings', icon: 'AlertTriangle' },
  { label: 'Attack Paths', href: '/attack-paths', icon: 'GitBranch' },
  { label: 'Security Team', href: '/security-team', icon: 'Bot' },
  { label: 'Remediations', href: '/remediations', icon: 'Wrench' },
  { label: 'Reports', href: '/reports', icon: 'FileText', disabled: true, badge: 'Soon' },
  { label: 'AI Security Chat', href: '/chat', icon: 'MessageSquare', disabled: true, badge: 'Soon' },
  { type: 'divider' },
  { label: 'Assets', href: '/assets', icon: 'Database' },
  { label: 'Team', href: '/team', icon: 'Users' },
  { label: 'Settings', href: '/settings', icon: 'Settings' },
];

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const { user, profile, loading, isAuthenticated, isEmailVerified } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (mounted && !loading) {
      if (!isAuthenticated) {
        router.push('/auth/login');
      } else if (!isEmailVerified) {
        router.push('/auth/verify-email');
      }
    }
  }, [mounted, loading, isAuthenticated, isEmailVerified, router]);

  if (!mounted || loading) {
    return (
      <div className="min-h-screen bg-background-DEFAULT flex items-center justify-center">
        <div className="animate-pulse flex flex-col items-center gap-4">
          <div className="h-8 w-48 bg-background-tertiary rounded" />
          <div className="h-4 w-32 bg-background-tertiary rounded" />
        </div>
      </div>
    );
  }

  if (!isAuthenticated || !isEmailVerified) {
    return null;
  }

  const isAssetRoute = pathname.startsWith('/assets');
  const isTeamRoute = pathname.startsWith('/team');
  const isSettingsRoute = pathname.startsWith('/settings');

  return (
    <div className="min-h-screen bg-background-DEFAULT flex">
      <Sidebar
        navigation={navigation}
        currentPath={pathname}
        user={user}
        profile={profile}
      >
        {children}
      </Sidebar>
    </div>
  );
}

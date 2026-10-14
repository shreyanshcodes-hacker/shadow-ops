'use client';

import { ReactNode, useState } from 'react';
import Link from 'next/link';
import { useAuthContext } from '@/components/providers/AuthProvider';
import { api } from '@/lib/api';
import { Bell, BellOff } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { 
  LayoutDashboard, Search, AlertTriangle, GitBranch, Bot, Wrench, FileText, MessageSquare, Database, Users, Settings, LogOut, ChevronRight, Menu, X, User, Building2, Shield, Bell 
} from 'lucide-react';
import { clsx } from 'clsx';
import { useAuth } from '@/hooks/useAuth';
import { Button } from './Button';
import { Avatar } from './Avatar';
import { Dropdown, DropdownItem, DropdownSeparator } from './Dropdown';

export interface SidebarItem {
  label: string;
  href: string;
  icon: string;
  disabled?: boolean;
  badge?: string;
  type?: 'divider';
}

interface SidebarProps {
  navigation: SidebarItem[];
  currentPath: string;
  user: { displayName?: string | null; email?: string | null; photoURL?: string | null } | null;
  profile: { display_name?: string | null; email?: string | null; avatar_url?: string | null } | null;
  children: ReactNode;
}

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  Search,
  AlertTriangle,
  GitBranch,
  Bot,
  Wrench,
  FileText,
  MessageSquare,
  Database,
  Users,
  Settings,
};

export function Sidebar({ navigation, currentPath, user, profile, children }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const { logout } = useAuth();
  const pathname = usePathname();
  const { currentWorkspace } = useAuthContext();

  const displayName = profile?.display_name || user?.displayName || user?.email?.split('@')[0] || 'User';
  const displayEmail = profile?.email || user?.email || '';
  const avatarUrl = profile?.avatar_url || user?.photoURL;

  const [unreadCount, setUnreadCount] = useState(0);

  useEffect(() => {
    if (currentWorkspace) {
      api.getUnreadCount(currentWorkspace.id).then(data => setUnreadCount(data.unread_count)).catch(() => {});
    }
  }, [currentWorkspace]);

  const handleLogout = async () => {
    await logout();
  };

  return (
    <>
      <button
        className="fixed top-4 left-4 z-50 lg:hidden p-2 rounded-lg bg-background-secondary border border-border-DEFAULT"
        onClick={() => setMobileOpen(true)}
        aria-label="Open menu"
      >
        <Menu className="h-5 w-5" />
      </button>

      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 bg-background-secondary border-r border-border-DEFAULT transition-all duration-200 flex flex-col',
          collapsed ? 'w-16' : 'w-64',
          mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
        aria-label="Main navigation"
      >
        <div className="flex h-16 items-center justify-between px-4 border-b border-border-DEFAULT">
          {!collapsed && (
            <Link href="/dashboard" className="flex items-center gap-2" aria-label="ShadowOps Home">
              <Shield className="h-7 w-7 text-accent-DEFAULT" />
              <span className="font-bold text-lg text-foreground-DEFAULT">ShadowOps</span>
            </Link>
          )}
          <div className="flex items-center gap-2">
            {!collapsed && currentWorkspace && (
              <button
                className="relative p-2 rounded-lg hover:bg-background-tertiary transition-colors text-foreground-muted hover:text-foreground-DEFAULT"
                onClick={() => window.location.href = '/notifications'}
                aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
              >
                {unreadCount > 0 ? (
                  <span className="absolute -top-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white text-xs font-medium">
                    {unreadCount > 99 ? '99+' : unreadCount}
                  </span>
                ) : null}
                <Bell className="h-5 w-5" />
              </button>
            )}
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="p-1.5 rounded-lg hover:bg-background-tertiary transition-colors"
              aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              aria-expanded={!collapsed}
            >
              <ChevronRight className={clsx('h-4 w-4 transition-transform', collapsed && 'rotate-180')} />
            </button>
          </div>

        <nav className="flex-1 overflow-y-auto py-4 px-2" aria-label="Navigation">
          <ul className="space-y-1" role="list">
            {navigation.map((item, index) => {
              if (item.type === 'divider') {
                return (
                  <li key={`divider-${index}`}>
                    <hr className="my-3 border-border-DEFAULT" aria-hidden="true" />
                  </li>
                );
              }

              const Icon = iconMap[item.icon];
              const isActive = currentPath === item.href || (item.href !== '/dashboard' && currentPath.startsWith(item.href));
              const disabled = item.disabled;

              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={clsx(
                      'flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors',
                      disabled
                        ? 'text-foreground-muted cursor-not-allowed'
                        : isActive
                        ? 'bg-accent-glow text-accent-DEFAULT'
                        : 'text-foreground-muted hover:bg-background-tertiary hover:text-foreground-DEFAULT',
                      collapsed && 'justify-center'
                    )}
                    aria-current={isActive ? 'page' : undefined}
                    tabIndex={disabled ? -1 : undefined}
                    aria-disabled={disabled}
                  >
                    <Icon className="h-5 w-5 flex-shrink-0" aria-hidden="true" />
                    {!collapsed && (
                      <>
                        <span className="font-medium truncate">{item.label}</span>
                        {item.badge && (
                          <span className="ml-auto px-2 py-0.5 text-xs rounded-full bg-background-tertiary text-foreground-muted">
                            {item.badge}
                          </span>
                        )}
                      </>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        {!collapsed && (
          <div className="p-4 border-t border-border-DEFAULT space-y-3">
            <div className="flex items-center gap-3 p-2 rounded-lg bg-background-tertiary/50">
              <Avatar src={avatarUrl} alt={displayName} className="h-9 w-9" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground-DEFAULT truncate">{displayName}</p>
                <p className="text-xs text-foreground-muted truncate">{displayEmail}</p>
              </div>
            </div>
            <Dropdown>
              <DropdownItem onClick={handleLogout} className="text-status-error">
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </DropdownItem>
            </Dropdown>
          </div>
        )}

        {collapsed && (
          <div className="absolute bottom-16 left-0 right-0 p-2 bg-background-secondary border-t border-border-DEFAULT">
            <Dropdown>
              <DropdownItem onClick={handleLogout} className="text-status-error">
                <LogOut className="h-4 w-4 mr-2" />
                Sign Out
              </DropdownItem>
            </Dropdown>
          </div>
        )}
      </aside>

      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      <main
        className={clsx(
          'flex-1 min-w-0 transition-all duration-200',
          collapsed ? 'lg:pl-16' : 'lg:pl-64'
        )}
      >
        <div className="p-6 lg:p-8">
          {children}
        </div>
      </main>
    </>
  );
}

export function Avatar({ src, alt, className }: { src?: string | null; alt?: string; className?: string }) {
  return (
    <div className={clsx('relative rounded-full overflow-hidden bg-accent-glow flex items-center justify-center', className)}>
      {src ? (
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <Shield className="h-1/2 w-1/2 text-accent-DEFAULT" />
      )}
    </div>
  );
}
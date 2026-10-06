'use client';

import { HTMLAttributes, forwardRef } from 'react';
import { clsx } from 'clsx';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'critical' | 'high' | 'medium' | 'low' | 'info' | 'success' | 'warning' | 'pending';
  dot?: boolean;
}

const variantStyles = {
  default: 'bg-background-tertiary text-foreground-muted border border-border-DEFAULT',
  critical: 'bg-severity-critical/15 text-severity-critical border border-severity-critical/30',
  high: 'bg-severity-high/15 text-severity-high border border-severity-high/30',
  medium: 'bg-severity-medium/15 text-severity-medium border border-severity-medium/30',
  low: 'bg-severity-low/15 text-severity-low border border-severity-low/30',
  info: 'bg-severity-info/15 text-severity-info border border-severity-info/30',
  success: 'bg-status-success/15 text-status-success border border-status-success/30',
  warning: 'bg-status-warning/15 text-status-warning border border-status-warning/30',
  pending: 'bg-background-tertiary text-foreground-muted border border-border-DEFAULT',
};

export const Badge = forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', dot, children, ...props }, ref) => {
    return (
      <span
        ref={ref}
        className={clsx(
          'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
          variantStyles[variant],
          className
        )}
        {...props}
      >
        {dot && (
          <span
            className={clsx('w-1.5 h-1.5 rounded-full', {
              'bg-severity-critical': variant === 'critical',
              'bg-severity-high': variant === 'high',
              'bg-severity-medium': variant === 'medium',
              'bg-severity-low': variant === 'low',
              'bg-severity-info': variant === 'info',
              'bg-status-success': variant === 'success',
              'bg-status-warning': variant === 'warning',
              'bg-foreground-subtle': variant === 'pending' || variant === 'default',
            })}
          />
        )}
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';

export const StatusBadge = ({ status }: { status: string }) => {
  const statusMap: Record<string, { variant: BadgeProps['variant']; label: string }> = {
    critical: { variant: 'critical', label: 'Critical' },
    high: { variant: 'high', label: 'High' },
    medium: { variant: 'medium', label: 'Medium' },
    low: { variant: 'low', label: 'Low' },
    info: { variant: 'info', label: 'Info' },
    open: { variant: 'critical', label: 'Open' },
    triaged: { variant: 'warning', label: 'Triaged' },
    in_progress: { variant: 'info', label: 'In Progress' },
    fixed: { variant: 'success', label: 'Fixed' },
    false_positive: { variant: 'default', label: 'False Positive' },
    wont_fix: { variant: 'default', label: 'Won\'t Fix' },
    risk_accepted: { variant: 'warning', label: 'Risk Accepted' },
    queued: { variant: 'pending', label: 'Queued' },
    running: { variant: 'info', label: 'Running' },
    completed: { variant: 'success', label: 'Completed' },
    failed: { variant: 'critical', label: 'Failed' },
    cancelled: { variant: 'default', label: 'Cancelled' },
    partial: { variant: 'warning', label: 'Partial' },
    pending_authorization: { variant: 'pending', label: 'Pending' },
    verified: { variant: 'success', label: 'Verified' },
    rejected: { variant: 'critical', label: 'Rejected' },
    expired: { variant: 'warning', label: 'Expired' },
    proposed: { variant: 'pending', label: 'Proposed' },
    approved: { variant: 'success', label: 'Approved' },
    applied: { variant: 'info', label: 'Applied' },
    superseded: { variant: 'default', label: 'Superseded' },
  };

  const config = statusMap[status] || { variant: 'default', label: status };
  return <Badge variant={config.variant} dot>{config.label}</Badge>;
};
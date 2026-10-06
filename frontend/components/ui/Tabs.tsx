'use client';

import { cn } from '@/lib/utils';
import { forwardRef } from 'react';

interface TabsProps {
  value: string;
  onValueChange: (value: string) => void;
  children: React.ReactNode;
  className?: string;
}

export function Tabs({ value, onValueChange, children, className }: TabsProps) {
  return (
    <div 
      className={cn('w-full', className)}
      data-value={value}
      onValueChange={(e: React.SyntheticEvent) => {
        const target = e.target as HTMLElement;
        const val = target.getAttribute('data-value');
        if (val) onValueChange(val);
      }}
    >
      {children}
    </div>
  );
}

interface TabsListProps {
  children: React.ReactNode;
  className?: string;
}

export function TabsList({ children, className }: TabsListProps) {
  return (
    <div 
      className={cn(
        'inline-flex h-10 items-center justify-center rounded-lg bg-background-tertiary p-1 text-foreground-muted',
        className
      )}
      role="tablist"
      aria-orientation="horizontal"
    >
      {children}
    </div>
  );
}

interface TabsTriggerProps {
  value: string;
  children: React.ReactNode;
  disabled?: boolean;
  className?: string;
}

export const TabsTrigger = forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ value, children, disabled, className, ...props }, ref) => {
    const isActive = false; // Will be set by parent Tabs
    return (
      <button
        ref={ref}
        type="button"
        data-value={value}
        disabled={disabled}
        role="tab"
        aria-selected={isActive}
        aria-disabled={disabled}
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-DEFAULT focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 data-[state=active]:bg-background-DEFAULT data-[state=active]:text-foreground-DEFAULT data-[state=active]:shadow-sm',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
);
TabsTrigger.displayName = 'TabsTrigger';

interface TabsContentProps {
  value: string;
  children: React.ReactNode;
  className?: string;
  forceMount?: boolean;
}

export function TabsContent({ value, children, className, forceMount }: TabsContentProps) {
  // We'll use a simple approach - the parent Tabs manages the active value
  // This is a simplified version - in production you'd use a context
  return (
    <div 
      className={cn('mt-2 ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-DEFAULT focus-visible:ring-offset-2', className)}
      role="tabpanel"
      data-value={value}
    >
      {children}
    </div>
  );
}
'use client';

import { forwardRef } from 'react';
import { cn } from '@/lib/utils';

interface SwitchProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ className, label, ...props }, ref) => {
    return (
      <div className={cn('flex items-center gap-3', className)}>
        <div className="relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full border-2 border-border-DEFAULT transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-DEFAULT focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-accent-DEFAULT data-[state=checked]:border-accent-DEFAULT">
          <span
            className={cn(
              'pointer-events-none block h-5 w-5 rounded-full bg-background-DEFAULT shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0'
            )}
          />
          <input
            type="checkbox"
            className="sr-only peer"
            ref={ref}
            {...props}
          />
        </div>
        {label && <label className="text-sm font-medium text-foreground-DEFAULT cursor-pointer">{label}</label>}
      </div>
    );
  }
);
Switch.displayName = 'Switch';
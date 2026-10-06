'use client';

import { forwardRef, useId } from 'react';
import { ChevronDown, ChevronUp, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from './Button';
import { Dialog, DialogContent, DialogItem } from './Dialog';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, children, placeholder, ...props }, ref) => {
    return (
      <select
        className={cn(
          'flex h-10 w-full items-center justify-between rounded-lg border border-border-DEFAULT bg-background-DEFAULT px-3 py-2 text-sm ring-offset-background placeholder:text-foreground-muted focus:outline-none focus:ring-2 focus:ring-accent-DEFAULT focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
          className
        )}
        ref={ref}
        {...props}
      >
        {placeholder && <option value="" disabled>{placeholder}</option>}
        {children}
      </select>
    );
  }
);
Select.displayName = 'Select';

interface SelectTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  placeholder?: string;
}

export const SelectTrigger = forwardRef<HTMLButtonElement, SelectTriggerProps>(
  ({ className, children, placeholder, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        variant="outline"
        role="combobox"
        aria-expanded="false"
        aria-haspopup="listbox"
        className={cn('w-full justify-between', className)}
        {...props}
      >
        {children || placeholder}
        <ChevronDown className="ml-2 h-4 w-4 opacity-50" aria-hidden="true" />
      </Button>
    );
  }
);
SelectTrigger.displayName = 'SelectTrigger';

interface SelectValueProps {
  placeholder?: string;
}

export function SelectValue({ placeholder }: SelectValueProps) {
  return <span className="text-foreground-muted">{placeholder}</span>;
}

interface SelectContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function SelectContent({ className, children, ...props }: SelectContentProps) {
  return (
    <DialogContent className={cn('relative z-50 max-h-96 min-w-[8rem] overflow-hidden rounded-lg border border-border-DEFAULT bg-background-DEFAULT text-foreground-DEFAULT shadow-lg', className)} {...props}>
      <div className="overflow-y-auto">{children}</div>
    </DialogContent>
  );
}

interface SelectItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string;
  disabled?: boolean;
}

export const SelectItem = forwardRef<HTMLDivElement, SelectItemProps>(
  ({ className, children, value, disabled, ...props }, ref) => {
    const id = useId();
    return (
      <DialogItem
        ref={ref}
        role="option"
        id={id}
        aria-selected="false"
        aria-disabled={disabled}
        value={value}
        disabled={disabled}
        className={cn(
          'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent-glow focus:text-accent-DEFAULT data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
          className
        )}
        {...props}
      >
        <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
          <Check className="h-4 w-4" />
        </span>
        {children}
      </DialogItem>
    );
  }
);
SelectItem.displayName = 'SelectItem';
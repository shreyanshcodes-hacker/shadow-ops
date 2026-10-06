'use client';

import { Fragment, ReactNode, forwardRef } from 'react';
import { X } from 'lucide-react';
import { clsx } from 'clsx';
import { createPortal } from 'react-dom';

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

const sizeStyles = {
  sm: 'max-w-sm',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  full: 'max-w-[90vw]',
};

export function Dialog({ open, onOpenChange, title, description, children, className, size = 'md' }: DialogProps) {
  if (!open) return null;

  const content = (
    <Fragment>
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm dialog-overlay"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />
      <div
        className={clsx(
          'fixed z-50 w-full max-h-[90vh] overflow-hidden rounded-lg border border-border-DEFAULT bg-background-DEFAULT text-foreground-DEFAULT shadow-xl',
          sizeStyles[size],
          className
        )}
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
        aria-describedby={description ? 'dialog-description' : undefined}
        style={{ top: '50%', left: '50%', transform: 'translate(-50%, -50%)' }}
      >
        <div className="flex items-start justify-between p-4 border-b border-border-DEFAULT">
          <div>
            <h2 id="dialog-title" className="text-lg font-semibold text-foreground-DEFAULT">
              {title}
            </h2>
            {description && (
              <p id="dialog-description" className="text-sm text-foreground-muted mt-1">
                {description}
              </p>
            )}
          </div>
          <button
            className="p-1 rounded-lg hover:bg-background-tertiary transition-colors"
            onClick={() => onOpenChange(false)}
            aria-label="Close dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="p-4 overflow-y-auto max-h-[calc(90vh-80px)]">
          {children}
        </div>
      </div>
    </Fragment>
  );

  if (typeof window === 'undefined') return null;
  return createPortal(content, document.body);
}

interface DialogTriggerProps {
  children: ReactNode;
  onClick?: () => void;
}

export const DialogTrigger = forwardRef<HTMLButtonElement, DialogTriggerProps>(
  ({ children, onClick, ...props }, ref) => (
    <button ref={ref} type="button" onClick={onClick} {...props}>
      {children}
    </button>
  )
);
DialogTrigger.displayName = 'DialogTrigger';

interface DialogContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function DialogContent({ className, children, ...props }: DialogContentProps) {
  return (
    <div className={clsx('p-4', className)} {...props}>
      {children}
    </div>
  );
}

interface DialogHeaderProps {
  children: ReactNode;
  className?: string;
}

export function DialogHeader({ children, className }: DialogHeaderProps) {
  return <div className={clsx('mb-4', className)}>{children}</div>;
}

interface DialogTitleProps {
  children: ReactNode;
  className?: string;
}

export function DialogTitle({ children, className }: DialogTitleProps) {
  return <h3 className={clsx('text-lg font-semibold text-foreground-DEFAULT', className)}>{children}</h3>;
}

interface DialogDescriptionProps {
  children: ReactNode;
  className?: string;
}

export function DialogDescription({ children, className }: DialogDescriptionProps) {
  return <p className={clsx('text-sm text-foreground-muted mt-1', className)}>{children}</p>;
}

interface DialogFooterProps {
  children: ReactNode;
  className?: string;
}

export function DialogFooter({ children, className }: DialogFooterProps) {
  return <div className={clsx('flex justify-end gap-2 mt-4 pt-4 border-t border-border-DEFAULT', className)}>{children}</div>;
}

interface DialogItemProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
  disabled?: boolean;
}

export const DialogItem = forwardRef<HTMLButtonElement, DialogItemProps>(
  ({ className, children, value, disabled, ...props }, ref) => (
    <button
      ref={ref}
      role="option"
      value={value}
      disabled={disabled}
      className={clsx(
        'relative flex w-full cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none focus:bg-accent-glow focus:text-accent-DEFAULT data-[disabled]:pointer-events-none data-[disabled]:opacity-50',
        className
      )}
      {...props}
    >
      <span className="absolute left-2 flex h-3.5 w-3.5 items-center justify-center">
        <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20"><path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" /></svg>
      </span>
      {children}
    </button>
  )
);
DialogItem.displayName = 'DialogItem';

interface AlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  variant?: 'danger' | 'warning' | 'info';
}

const variantStyles = {
  danger: 'bg-status-error/10 border-status-error/30 text-status-error',
  warning: 'bg-status-warning/10 border-status-warning/30 text-status-warning',
  info: 'bg-status-info/10 border-status-info/30 text-status-info',
};

export function AlertDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  variant = 'danger',
}: AlertDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={title} size="sm">
      <p className="text-sm text-foreground-muted mb-6">{description}</p>
      <div className="flex justify-end gap-2">
        <button
          className="btn-secondary"
          onClick={() => onOpenChange(false)}
        >
          {cancelLabel}
        </button>
        <button
          className={clsx('btn', variant === 'danger' && 'btn-danger', variant !== 'danger' && 'btn-primary')}
          onClick={() => {
            onConfirm();
            onOpenChange(false);
          }}
        >
          {confirmLabel}
        </button>
      </div>
    </Dialog>
  );
}
'use client';

import { ReactNode } from 'react';
import { X, AlertCircle, CheckCircle, Info, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';

interface AlertProps {
  variant?: 'info' | 'success' | 'warning' | 'error';
  title?: string;
  children: ReactNode;
  dismissible?: boolean;
  onDismiss?: () => void;
  className?: string;
}

const variantIcons = {
  info: Info,
  success: CheckCircle,
  warning: AlertTriangle,
  error: AlertCircle,
};

const variantClasses = {
  info: 'border-status-info/30 bg-status-info/10 text-status-info',
  success: 'border-status-success/30 bg-status-success/10 text-status-success',
  warning: 'border-status-warning/30 bg-status-warning/10 text-status-warning',
  error: 'border-status-error/30 bg-status-error/10 text-status-error',
};

export function Alert({ variant = 'info', title, children, dismissible, onDismiss, className }: AlertProps) {
  const Icon = variantIcons[variant];

  return (
    <div className={clsx('alert', variantClasses[variant], className)} role="alert">
      <Icon className="h-5 w-5 flex-shrink-0 mt-0.5" aria-hidden="true" />
      <div className="flex-1 min-w-0">
        {title && <p className="font-medium text-sm">{title}</p>}
        <div className="text-sm mt-1">{children}</div>
      </div>
      {dismissible && (
        <button
          onClick={onDismiss}
          className="flex-shrink-0 p-1 rounded hover:bg-black/10 transition-colors"
          aria-label="Dismiss"
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  );
}

export function AlertBanner({ message, variant = 'info', onDismiss }: { message: string; variant?: 'info' | 'warning' | 'error'; onDismiss?: () => void }) {
  return (
    <Alert variant={variant} dismissible={!!onDismiss} onDismiss={onDismiss} className="fixed bottom-4 right-4 z-50 max-w-md shadow-card-hover animate-slide-up">
      {message}
    </Alert>
  );
}
'use client';

import { clsx } from 'clsx';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'text' | 'card' | 'circle' | 'rect' | 'table-row';
  lines?: number;
}

export function Skeleton({ className, variant = 'rect', lines, ...props }: SkeletonProps) {
  const variants = {
    text: 'h-4 w-full max-w-xs',
    card: 'h-32 w-full rounded-lg',
    circle: 'h-10 w-10 rounded-full',
    rect: 'h-16 w-full rounded',
    'table-row': 'h-12 w-full',
  };

  if (variant === 'text' && lines && lines > 1) {
    return (
      <div className={clsx('space-y-2', className)} {...props}>
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className={clsx('skeleton h-4 rounded', i === lines - 1 && 'w-3/4')} />
        ))}
      </div>
    );
  }

  return <div className={clsx('skeleton', variants[variant], className)} {...props} />;
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={clsx('glass-card rounded-lg p-4 animate-pulse', className)}>
      <div className="space-y-3">
        <div className="flex items-center gap-3">
          <Skeleton variant="circle" />
          <div className="space-y-1 flex-1">
            <Skeleton variant="text" />
            <Skeleton variant="text" className="w-1/3" />
          </div>
        </div>
        <Skeleton variant="text" lines={3} />
      </div>
    </div>
  );
}

export function TableRowSkeleton({ columns = 5 }: { columns?: number }) {
  return (
    <tr>
      {Array.from({ length: columns }).map((_, i) => (
        <td key={i} className="py-3">
          <Skeleton variant="text" className="w-3/4" />
        </td>
      ))}
    </tr>
  );
}

export function TableSkeleton({ columns = 5, rows = 5 }: { columns?: number; rows?: number }) {
  return (
    <div className="table-container">
      <table className="table">
        <thead>
          <tr>
            {Array.from({ length: columns }).map((_, i) => (
              <th key={i} className="h-10">
                <Skeleton variant="text" className="w-3/4" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <TableRowSkeleton key={i} columns={columns} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div className="space-y-6 animate-pulse">
      <div className="flex items-center justify-between">
        <div className="space-y-1">
          <Skeleton variant="text" className="w-48 h-8" />
          <Skeleton variant="text" className="w-64" />
        </div>
        <Skeleton variant="circle" className="h-10 w-10" />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <CardSkeleton key={i} />
        ))}
      </div>
      <CardSkeleton className="min-h-[400px]" />
    </div>
  );
}
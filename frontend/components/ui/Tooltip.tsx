'use client';

import { useState, ReactNode } from 'react';
import { clsx } from 'clsx';

interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  delay?: number;
  className?: string;
}

const positionStyles = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2',
};

const arrowStyles = {
  top: 'top-full left-1/2 -translate-x-1/2 border-t-accent-DEFAULT border-transparent border-4',
  bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-accent-DEFAULT border-transparent border-4',
  left: 'left-full top-1/2 -translate-y-1/2 border-l-accent-DEFAULT border-transparent border-4',
  right: 'right-full top-1/2 -translate-y-1/2 border-r-accent-DEFAULT border-transparent border-4',
};

export function Tooltip({ content, children, position = 'top', delay = 200, className }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timeoutRef = useState<NodeJS.Timeout | null>(null);

  const show = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => setVisible(true), delay);
  };

  const hide = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setVisible(false);
  };

  return (
    <div className="relative inline-flex" onMouseEnter={show} onMouseLeave={hide} onFocus={show} onBlur={hide}>
      {children}
      {visible && (
        <div
          className={clsx(
            'tooltip absolute z-50 px-2 py-1.5 text-xs text-white bg-accent-DEFAULT rounded shadow-card whitespace-nowrap',
            positionStyles[position],
            className
          )}
          role="tooltip"
        >
          {content}
          <div className={clsx('absolute', arrowStyles[position])} />
        </div>
      )}
    </div>
  );
}
'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';

interface PopoverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
  align?: 'start' | 'center' | 'end';
}

interface PopoverTriggerProps {
  children: React.ReactElement;
  asChild?: boolean;
}

interface PopoverContentProps {
  children: React.ReactNode;
  className?: string;
  align?: 'start' | 'center' | 'end';
  sideOffset?: number;
}

export function Popover({ open, onOpenChange, children, align = 'start' }: PopoverProps) {
  const [triggerRef, setTriggerRef] = useState<HTMLElement | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (event: MouseEvent) => {
      if (contentRef.current && !contentRef.current.contains(event.target as Node) &&
          triggerRef && !triggerRef.contains(event.target as Node)) {
        onOpenChange(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open, onOpenChange]);

  const trigger = React.Children.only(children);

  return (
    <>
      <span ref={setTriggerRef}>{trigger}</span>
      {open && createPortal(
        <div
          ref={contentRef}
          className={cn(
            'fixed z-50',
            align === 'start' ? 'left-0' : align === 'center' ? 'left-1/2 -translate-x-1/2' : 'right-0',
            'top-full mt-2'
          )}
          style={{
            transformOrigin: align === 'center' ? 'center top' : align === 'start' ? 'left top' : 'right top',
          }}
        >
          <div className="relative">
            <div className="absolute -top-1.5 left-4 w-3 h-3 bg-white border-l border-t border-gray-200 rotate-45" />
            {createPortal(
              <div ref={contentRef} className="bg-white rounded-lg shadow-lg border border-gray-200 min-w-[200px]">
                {children}
              </div>,
              document.body
            )}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}

export function PopoverTrigger({ children, asChild = false }: PopoverTriggerProps) {
  if (asChild) {
    return React.cloneElement(children as React.ReactElement, {
      onClick: (e: React.MouseEvent) => {
        e.stopPropagation();
        children.props.onClick?.(e);
      },
    });
  }
  return <span onClick={e => e.stopPropagation()}>{children}</span>;
}

export function PopoverContent({ children, className, align = 'start', sideOffset = 4 }: PopoverContentProps) {
  return (
    <div
      className={cn(
        'bg-white rounded-lg shadow-lg border border-gray-200',
        'animate-in fade-in-0 zoom-in-95',
        'data-[side=bottom]:slide-in-from-top-2',
        'data-[side=left]:slide-in-from-right-2',
        'data-[side=right]:slide-in-from-left-2',
        'data-[side=top]:slide-in-from-bottom-2',
        className
      )}
      style={{ transformOrigin: align === 'center' ? 'center top' : align === 'start' ? 'left top' : 'right top' }}
    >
      {children}
    </div>
  );
}
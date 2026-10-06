'use client';

import { useState, useRef, useEffect, ReactNode } from 'react';
import { clsx } from 'clsx';
import { createPortal } from 'react-dom';

interface DropdownItem {
  label: string;
  onClick: () => void;
  icon?: ReactNode;
  disabled?: boolean;
  danger?: boolean;
  divider?: boolean;
}

interface DropdownMenuProps {
  trigger: ReactNode;
  items: DropdownItem[];
  align?: 'left' | 'right';
  className?: string;
}

export function DropdownMenu({ trigger, items, align = 'right', className }: DropdownMenuProps) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (triggerRef.current && !triggerRef.current.contains(event.target as Node)) {
        if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
          setOpen(false);
        }
      }
    }

    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const menuContent = (
    <div
      ref={menuRef}
      className={clsx('dropdown', align === 'right' ? 'right-0' : 'left-0', className)}
      role="menu"
    >
      {items.map((item, index) => (
        item.divider ? (
          <div key={index} className="dropdown-divider" role="separator" />
        ) : (
          <button
            key={index}
            className={clsx(
              'dropdown-item w-full text-left',
              item.disabled && 'opacity-50 cursor-not-allowed',
              item.danger && 'text-status-error'
            )}
            onClick={() => {
              if (!item.disabled) {
                item.onClick();
                setOpen(false);
              }
            }}
            disabled={item.disabled}
            role="menuitem"
          >
            {item.icon && <span className="h-4 w-4 flex-shrink-0">{item.icon}</span>}
            <span>{item.label}</span>
          </button>
        )
      ))}
    </div>
  );

  return (
    <div className="relative inline-block" ref={triggerRef}>
      <div
        onClick={() => setOpen(!open)}
        className="inline-flex"
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen(!open);
          }
        }}
        aria-haspopup="true"
        aria-expanded={open}
      >
        {trigger}
      </div>
      {open && typeof window !== 'undefined' && createPortal(menuContent, document.body)}
    </div>
  );
}
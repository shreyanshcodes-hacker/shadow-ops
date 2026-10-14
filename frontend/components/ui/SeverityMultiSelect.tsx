'use client';

import { forwardRef, useState } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Checkbox } from '@/components/ui/Checkbox';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/Popover';
import { ChevronDown, Check } from 'lucide-react';

const SEVERITIES = [
  { value: 'critical', label: 'Critical', color: '#ef4444' },
  { value: 'high', label: 'High', color: '#f97316' },
  { value: 'medium', label: 'Medium', color: '#eab308' },
  { value: 'low', label: 'Low', color: '#22c55e' },
  { value: 'info', label: 'Info', color: '#3b82f6' },
];

interface SeverityMultiSelectProps {
  selected: string[];
  onChange: (selected: string[]) => void;
  placeholder?: string;
  label?: string;
  className?: string;
}

export const SeverityMultiSelect = forwardRef<HTMLButtonElement, SeverityMultiSelectProps>(
  ({ selected, onChange, placeholder = 'Select severities...', label, className, ...props }, ref) => {
    const [open, setOpen] = useState(false);

    const toggleSeverity = (severity: string) => {
      onChange(selected.includes(severity)
        ? selected.filter(s => s !== severity)
        : [...selected, severity]
      );
    };

    const selectedCount = selected.length;

    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            ref={ref}
            variant="outline"
            className={cn('w-full justify-between text-left h-auto py-3', className)}
            {...props}
          >
            <div className="flex flex-col gap-1">
              {label && <Label className="text-xs font-medium text-gray-500">{label}</Label>}
              <div className="flex items-center justify-between">
                <span className={selectedCount > 0 ? 'text-gray-900' : 'text-gray-500'}>
                  {selectedCount > 0
                    ? `${selectedCount} severity${selectedCount > 1 ? 's' : ''} selected`
                    : placeholder}
                </span>
                <ChevronDown className="h-4 w-4 text-gray-400" />
              </div>
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-64 p-0" align="start">
          <div className="p-4 space-y-2">
            <Label className="font-medium">Select Severities</Label>
            {SEVERITIES.map(severity => (
              <label
                key={severity.value}
                className="flex items-center gap-3 p-2 hover:bg-gray-50 rounded-lg cursor-pointer transition-colors"
              >
                <Checkbox
                  checked={selected.includes(severity.value)}
                  onCheckedChange={() => toggleSeverity(severity.value)}
                />
                <div className="flex items-center gap-2 flex-1">
                  <span
                    className="w-3 h-3 rounded"
                    style={{ backgroundColor: severity.color }}
                  />
                  <span className="capitalize text-gray-900">{severity.label}</span>
                </div>
                {selected.includes(severity.value) && <Check className="h-4 w-4 text-accent-DEFAULT" />}
              </label>
            ))}
            {selectedCount > 0 && (
              <Button variant="outline" size="sm" className="w-full mt-2" onClick={() => onChange([])}>
                Clear all
              </Button>
            )}
          </div>
        </PopoverContent>
      </Popover>
    );
  }
);

SeverityMultiSelect.displayName = 'SeverityMultiSelect';
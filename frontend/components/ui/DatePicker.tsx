'use client';

import { forwardRef, useState, useRef, useEffect } from 'react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Label } from '@/components/ui/Label';
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from '@/components/ui/Popover';
import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { format, startOfMonth, endOfMonth, startOfWeek, endOfWeek, addMonths, subMonths, addDays, isSameMonth, isSameDay, isWithinInterval } from 'date-fns';

interface DatePickerProps {
  selected?: Date | null;
  onChange: (date: Date | null) => void;
  placeholder?: string;
  label?: string;
  className?: string;
  selectsStart?: boolean;
  selectsEnd?: boolean;
  startDate?: Date | null;
  endDate?: Date | null;
  disabled?: boolean;
}

export const DatePicker = forwardRef<HTMLButtonElement, DatePickerProps>(
  ({ selected, onChange, placeholder = 'Select date...', label, className, selectsStart, selectsEnd, startDate, endDate, disabled, ...props }, ref) => {
    const [open, setOpen] = useState(false);
    const [viewDate, setViewDate] = useState(selected || new Date());
    const [viewMode, setViewMode] = useState<'month' | 'year'>('month');

    const currentMonth = viewDate;
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calendarStart = startOfWeek(monthStart);
    const calendarEnd = endOfWeek(monthEnd);

    const days = [];
    let day = calendarStart;
    while (day <= calendarEnd) {
      days.push(day);
      day = addDays(day, 1);
    }

    const handleDayClick = (day: Date) => {
      if (disabled) return;
      const isDisabled = (startDate && day < startOfDay(startDate)) ||
        (endDate && day > endOfDay(endDate));
      if (isDisabled) return;

      if (selectsStart && selectsEnd) {
        if (!startDate || (startDate && endDate)) {
          onChange(day);
        } else if (day <= startDate!) {
          onChange(day);
        } else {
          onChange(day);
        }
      } else {
        onChange(day);
      }
      setOpen(false);
    };

    const isSelected = (day: Date) => {
      if (!selected) return false;
      if (startDate && endDate) {
        return isWithinInterval(day, { start: startOfDay(startDate), end: endOfDay(endDate) });
      }
      return isSameDay(day, selected);
    };

    const isInRange = (day: Date) => {
      if (!startDate || !endDate) return false;
      return isWithinInterval(day, { start: startOfDay(startDate), end: endOfDay(endDate) });
    };

    const isDisabled = (day: Date) => {
      if (startDate && day < startOfDay(startDate)) return true;
      if (endDate && day > endOfDay(endDate)) return true;
      return false;
    };

    return (
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            ref={ref}
            variant="outline"
            className={cn('w-full justify-between text-left h-auto py-3', className)}
            disabled={disabled}
            {...props}
          >
            <div className="flex flex-col gap-1">
              {label && <Label className="text-xs font-medium text-gray-500">{label}</Label>}
              <div className="flex items-center justify-between">
                <span className={selected ? 'text-gray-900' : 'text-gray-500'}>
                  {selected ? format(selected, 'MMM d, yyyy') : placeholder}
                </span>
                <Calendar className="h-4 w-4 text-gray-400" />
              </div>
            </div>
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-auto p-0" align="start">
          <div className="p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <Button variant="ghost" size="icon" onClick={() => setViewDate(subMonths(viewDate, 1))}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="font-medium text-lg" onClick={() => setViewMode('year')}>
                {format(viewDate, 'MMMM yyyy')}
              </span>
              <Button variant="ghost" size="icon" onClick={() => setViewDate(addMonths(viewDate, 1))}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>

            {/* Weekday headers */}
            <div className="grid grid-cols-7 gap-1 text-center text-xs font-medium text-gray-500">
              {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => (
                <div key={d} className="py-1">{d}</div>
              ))}
            </div>

            {/* Days */}
            <div className="grid grid-cols-7 gap-1">
              {days.map(day => {
                const isCurrentMonth = isSameMonth(day, currentMonth);
                const selectedState = isSelected(day);
                const inRange = isInRange(day);
                const disabledState = isDisabled(day);

                return (
                  <Button
                    key={day.toISOString()}
                    variant="ghost"
                    size="icon"
                    className={cn(
                      'h-9 w-9 text-sm rounded-full',
                      !isCurrentMonth && 'text-gray-300',
                      disabledState && 'opacity-50 cursor-not-allowed',
                      selectedState && 'bg-accent-DEFAULT text-white',
                      inRange && !selectedState && 'bg-accent-DEFAULT/20',
                      selectedState && inRange && 'bg-accent-DEFAULT text-white',
                    )}
                    disabled={disabledState}
                    onClick={() => handleDayClick(day)}
                  >
                    {format(day, 'd')}
                  </Button>
                );
              })}
            </div>

            {/* Today button */}
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                const today = new Date();
                handleDayClick(today);
              }}
            >
              Today
            </Button>
          </div>
        </PopoverContent>
      </Popover>
    );
  }
);

DatePicker.displayName = 'DatePicker';
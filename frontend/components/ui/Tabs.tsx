'use client';

import { cn } from '@/lib/utils';
import { Slot } from '@radix-ui/react-slot';
import { cva, type VariantProps } from 'class-variance-authority';

const tabsVariants = cva(
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-gray-100 text-gray-900 hover:bg-gray-200 data-[state=active]:bg-white data-[state=active]:shadow-sm',
        outline: 'border border-gray-300 bg-white text-gray-900 hover:bg-gray-50 data-[state=active]:bg-gray-100',
      },
    },
    defaultVariants: {
      variant: 'default',
    },
  }
);

interface TabsProps {
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  value?: string;
  children: React.ReactNode;
  className?: string;
  orientation?: 'horizontal' | 'vertical';
}

export function Tabs({ defaultValue, onValueChange, value, children, className, orientation = 'horizontal' }: TabsProps) {
  const [activeValue, setActiveValue] = useState(defaultValue || '');

  const handleValueChange = (newValue: string) => {
    setActiveValue(newValue);
    onValueChange?.(newValue);
  };

  return (
    <div className={cn(className)}>
      <TabsList
        role="tablist"
        aria-orientation={orientation}
        value={value || activeValue}
        onValueChange={handleValueChange}
        className={cn(
          'inline-flex h-10 items-center justify-center rounded-md bg-gray-100 p-1 text-gray-900',
          orientation === 'vertical' ? 'flex-col w-[180px]' : 'flex-row'
        )}
      >
        {React.Children.map(children, child => {
          if (!React.isValidElement(child)) return null;
          return React.cloneElement(child, {
            value: child.props.value,
            onClick: () => handleValueChange(child.props.value),
            selected: (value || activeValue) === child.props.value,
          });
        })}
      </TabsList>
      <TabsContent value={value || activeValue}>
        {React.Children.map(children, child => {
          if (!React.isValidElement(child)) return null;
          return React.cloneElement(child, {
            value: child.props.value,
          });
        })}
      </TabsContent>
    </div>
  );
}

function TabsList({ children, className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={cn(
        'inline-flex h-10 items-center justify-center rounded-md bg-gray-100 p-1 text-gray-900',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

function TabsTrigger({ children, value, selected, onClick, className, disabled, ...props }: 
  React.ButtonHTMLAttributes<HTMLButtonElement> & { value: string; selected?: boolean }) {
  return (
    <button
      role="tab"
      aria-selected={selected}
      value={value}
      onClick={onClick}
      disabled={disabled}
      className={cn(
        'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-white transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
        selected
          ? 'bg-white text-gray-900 shadow-sm'
          : 'text-gray-600 hover:text-gray-900 hover:bg-gray-100',
        className
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function TabsContent({ children, value, className, ...props }: React.HTMLAttributes<HTMLDivElement> & { value: string }) {
  return (
    <div
      role="tabpanel"
      hidden={false}
      className={cn(
        'mt-2 ring-offset-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

TabsTrigger.displayName = 'TabsTrigger';
TabsContent.displayName = 'TabsContent';
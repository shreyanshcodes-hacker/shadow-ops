'use client';

import { ReactNode } from 'react';
import { QueryProvider } from './QueryProvider';
import { AuthProvider } from './AuthProvider';
import { DemoModeProvider } from './DemoModeProvider';

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <QueryProvider>
      <AuthProvider>
        <DemoModeProvider defaultDemoMode={false}>
          {children}
        </DemoModeProvider>
      </AuthProvider>
    </QueryProvider>
  );
}
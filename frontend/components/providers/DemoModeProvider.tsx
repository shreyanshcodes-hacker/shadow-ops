'use client';

import { ReactNode, useContext, createContext, useState, useCallback } from 'react';

interface DemoModeContextType {
  demoMode: boolean;
  toggleDemoMode: () => void;
  enableDemoMode: () => void;
  disableDemoMode: () => void;
}

const DemoModeContext = createContext<DemoModeContextType | undefined>(undefined);

interface DemoModeProviderProps {
  children: ReactNode;
  defaultDemoMode?: boolean;
}

export function DemoModeProvider({ children, defaultDemoMode = false }: DemoModeProviderProps) {
  const [demoMode, setDemoMode] = useState(defaultDemoMode);

  const toggleDemoMode = useCallback(() => setDemoMode(prev => !prev), []);
  const enableDemoMode = useCallback(() => setDemoMode(true), []);
  const disableDemoMode = useCallback(() => setDemoMode(false), []);

  return (
    <DemoModeContext.Provider value={{ demoMode, toggleDemoMode, enableDemoMode, disableDemoMode }}>
      {children}
    </DemoModeContext.Provider>
  );
}

export function useDemoMode() {
  const context = useContext(DemoModeContext);
  if (!context) {
    throw new Error('useDemoMode must be used within a DemoModeProvider');
  }
  return context;
}

export function useIsDemoMode() {
  const { demoMode } = useDemoMode();
  return demoMode;
}
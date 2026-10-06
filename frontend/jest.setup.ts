import '@testing-library/jest-dom';

// Mock next/navigation
jest.mock('next/navigation', () => ({
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    prefetch: jest.fn(),
    back: jest.fn(),
    refresh: jest.fn(),
  }),
  usePathname: () => '/dashboard',
  useSearchParams: () => new URLSearchParams(),
}));

// Mock next/link
jest.mock('next/link', ({ children, href, ...props }: any) => (
  <a href={href} {...props}>{children}</a>
));

// Mock react-hot-toast
jest.mock('react-hot-toast', () => ({
  toast: jest.fn(),
  Toaster: () => null,
}));

// Mock @tanstack/react-query
jest.mock('@tanstack/react-query', () => ({
  useQuery: jest.fn(() => ({ data: undefined, isLoading: false, error: null })),
  useMutation: jest.fn(() => ({ mutate: jest.fn(), isPending: false })),
  useQueryClient: jest.fn(() => ({
    invalidateQueries: jest.fn(),
    setQueryData: jest.fn(),
    getQueryData: jest.fn(),
  })),
  QueryClient: jest.fn(),
  QueryClientProvider: ({ children }: any) => children,
}));

// Mock lucide-react
jest.mock('lucide-react', () => ({
  Shield: () => <svg data-testid="shield" />,
  Zap: () => <svg data-testid="zap" />,
  GitBranch: () => <svg data-testid="git-branch" />,
  BarChart3: () => <svg data-testid="bar-chart" />,
  AlertTriangle: () => <svg data-testid="alert-triangle" />,
  CheckCircle: () => <svg data-testid="check-circle" />,
  Clock: () => <svg data-testid="clock" />,
  Users: () => <svg data-testid="users" />,
  Plus: () => <svg data-testid="plus" />,
  Search: () => <svg data-testid="search" />,
  Filter: () => <svg data-testid="filter" />,
  Server: () => <svg data-testid="server" />,
  Database: () => <svg data-testid="database" />,
  Box: () => <svg data-testid="box" />,
  Layers: () => <svg data-testid="layers" />,
  Loader2: () => <svg data-testid="loader" />,
  ChevronDown: () => <svg data-testid="chevron-down" />,
  ChevronRight: () => <svg data-testid="chevron-right" />,
  Menu: () => <svg data-testid="menu" />,
  X: () => <svg data-testid="x" />,
  User: () => <svg data-testid="user" />,
  Building2: () => <svg data-testid="building" />,
  Mail: () => <svg data-testid="mail" />,
  Lock: () => <svg data-testid="lock" />,
  Eye: () => <svg data-testid="eye" />,
  EyeOff: () => <svg data-testid="eye-off" />,
  AlertCircle: () => <svg data-testid="alert-circle" />,
  RefreshCw: () => <svg data-testid="refresh-cw" />,
  MoreHorizontal: () => <svg data-testid="more-horizontal" />,
  UserCheck: () => <svg data-testid="user-check" />,
  UserX: () => <svg data-testid="user-x" />,
  Settings: () => <svg data-testid="settings" />,
  Palette: () => <svg data-testid="palette" />,
  Bell: () => <svg data-testid="bell" />,
  Key: () => <svg data-testid="key" />,
  Bot: () => <svg data-testid="bot" />,
  Wrench: () => <svg data-testid="wrench" />,
  FileText: () => <svg data-testid="file-text" />,
  MessageSquare: () => <svg data-testid="message-square" />,
  LayoutDashboard: () => <svg data-testid="layout-dashboard" />,
}));

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: jest.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: jest.fn(),
    removeListener: jest.fn(),
    addEventListener: jest.fn(),
    removeEventListener: jest.fn(),
    dispatchEvent: jest.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = jest.fn().mockImplementation(() => ({
  observe: jest.fn(),
  unobserve: jest.fn(),
  disconnect: jest.fn(),
}));

// Suppress console errors in tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});
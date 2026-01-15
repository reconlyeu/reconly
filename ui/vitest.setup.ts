/**
 * Vitest global setup file.
 * Configures mocks for SSR-unfriendly libraries and global test utilities.
 */
import { vi } from 'vitest';
import { config } from '@vue/test-utils';

// ============================================================================
// Mock vue-toastification
// ============================================================================
vi.mock('vue-toastification', () => ({
  globalEventBus: {},
  createToastInterface: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
  }),
}));

// ============================================================================
// Mock @tanstack/vue-query
// ============================================================================
const mockQueryClient = {
  invalidateQueries: vi.fn(),
  setQueryData: vi.fn(),
  getQueryData: vi.fn(),
  refetchQueries: vi.fn(),
};

vi.mock('@tanstack/vue-query', async () => {
  const actual = await vi.importActual('@tanstack/vue-query');
  return {
    ...actual,
    useQueryClient: () => mockQueryClient,
    useQuery: vi.fn(() => ({
      data: { value: null },
      isLoading: { value: false },
      isError: { value: false },
      error: { value: null },
      refetch: vi.fn(),
    })),
    useMutation: vi.fn(() => ({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: { value: false },
      isError: { value: false },
      error: { value: null },
      reset: vi.fn(),
    })),
  };
});

// ============================================================================
// Mock localStorage
// ============================================================================
const localStorageMock = {
  store: {} as Record<string, string>,
  getItem: vi.fn((key: string) => localStorageMock.store[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageMock.store[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageMock.store[key];
  }),
  clear: vi.fn(() => {
    localStorageMock.store = {};
  }),
};

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// ============================================================================
// Mock window.confirm for tests
// ============================================================================
Object.defineProperty(window, 'confirm', {
  value: vi.fn(() => true),
  writable: true,
});

// ============================================================================
// Global Vue Test Utils configuration
// ============================================================================
config.global.stubs = {
  // Stub lucide icons to avoid rendering issues
  ChevronLeft: true,
  ChevronRight: true,
  // Add more icon stubs as needed
};

// ============================================================================
// Export mocks for use in tests
// ============================================================================
export { mockQueryClient, localStorageMock };

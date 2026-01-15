import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { useQuery, useMutation } from '@tanstack/vue-query';
import {
  EXTENSIONS_QUERY_KEY,
  CATALOG_QUERY_KEY,
  useExtensionsList,
  useExtensionsByType,
  useExtension,
  useEnabledExtensions,
  useToggleExtension,
  useCatalog,
  useCatalogSearch,
  useInstallExtension,
  useUninstallExtension,
} from '../useExtensions';
import type { Extension, ExtensionType } from '@/types/entities';

// Mock the API
vi.mock('@/services/api', () => ({
  extensionsApi: {
    list: vi.fn(),
    listByType: vi.fn(),
    setEnabled: vi.fn(),
    getCatalog: vi.fn(),
    searchCatalog: vi.fn(),
    install: vi.fn(),
    uninstall: vi.fn(),
  },
}));

const mockUseQuery = vi.mocked(useQuery);
const mockUseMutation = vi.mocked(useMutation);

describe('useExtensions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('query keys', () => {
    it('EXTENSIONS_QUERY_KEY has correct value', () => {
      expect(EXTENSIONS_QUERY_KEY).toEqual(['extensions']);
    });

    it('CATALOG_QUERY_KEY has correct value', () => {
      expect(CATALOG_QUERY_KEY).toEqual(['extensions', 'catalog']);
    });
  });

  describe('useExtensionsList', () => {
    it('calls useQuery with correct parameters', () => {
      useExtensionsList();

      expect(mockUseQuery).toHaveBeenCalledWith({
        queryKey: expect.arrayContaining(['extensions']),
        queryFn: expect.any(Function),
        staleTime: 5 * 60 * 1000,
      });
    });

    it('includes type in query key when provided', () => {
      const type = ref<ExtensionType | undefined>('summarizer');

      useExtensionsList(type);

      expect(mockUseQuery).toHaveBeenCalledWith({
        queryKey: ['extensions', 'summarizer'],
        queryFn: expect.any(Function),
        staleTime: 5 * 60 * 1000,
      });
    });
  });

  describe('useExtensionsByType', () => {
    it('calls useQuery with type in query key', () => {
      useExtensionsByType('fetcher');

      expect(mockUseQuery).toHaveBeenCalledWith({
        queryKey: ['extensions', 'fetcher'],
        queryFn: expect.any(Function),
        staleTime: 5 * 60 * 1000,
      });
    });
  });

  describe('useExtension', () => {
    it('returns extension by type and name from list', () => {
      const mockExtensions: Extension[] = [
        { name: 'summarizer1', type: 'summarizer', enabled: true, version: '1.0.0' },
        { name: 'fetcher1', type: 'fetcher', enabled: false, version: '1.0.0' },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExtensions),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extension } = useExtension('summarizer', 'summarizer1');

      expect(extension.value).toEqual(mockExtensions[0]);
    });

    it('returns null when extension not found', () => {
      mockUseQuery.mockReturnValue({
        data: ref([]),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extension } = useExtension('summarizer', 'nonexistent');

      expect(extension.value).toBeNull();
    });

    it('returns null when data is not yet loaded', () => {
      mockUseQuery.mockReturnValue({
        data: ref(null),
        isLoading: ref(true),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extension } = useExtension('summarizer', 'summarizer1');

      expect(extension.value).toBeNull();
    });
  });

  describe('useEnabledExtensions', () => {
    it('filters enabled extensions', () => {
      const mockExtensions: Extension[] = [
        { name: 'summarizer1', type: 'summarizer', enabled: true, version: '1.0.0' },
        { name: 'fetcher1', type: 'fetcher', enabled: false, version: '1.0.0' },
        { name: 'exporter1', type: 'exporter', enabled: true, version: '1.0.0' },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExtensions),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extensions } = useEnabledExtensions();

      expect(extensions.value).toHaveLength(2);
      expect(extensions.value.map((e) => e.name)).toEqual(['summarizer1', 'exporter1']);
    });

    it('returns empty array when no extensions are enabled', () => {
      const mockExtensions: Extension[] = [
        { name: 'summarizer1', type: 'summarizer', enabled: false, version: '1.0.0' },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExtensions),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extensions } = useEnabledExtensions();

      expect(extensions.value).toHaveLength(0);
    });

    it('returns empty array when data is not loaded', () => {
      mockUseQuery.mockReturnValue({
        data: ref(null),
        isLoading: ref(true),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { extensions } = useEnabledExtensions();

      expect(extensions.value).toHaveLength(0);
    });
  });

  describe('useToggleExtension', () => {
    it('calls useMutation with correct config', () => {
      useToggleExtension();

      expect(mockUseMutation).toHaveBeenCalledWith({
        mutationFn: expect.any(Function),
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      });
    });

    it('accepts optional callbacks', () => {
      const onSuccess = vi.fn();
      const onError = vi.fn();

      useToggleExtension({ onSuccess, onError });

      expect(mockUseMutation).toHaveBeenCalled();
    });
  });

  describe('catalog hooks', () => {
    describe('useCatalog', () => {
      it('calls useQuery with catalog query key', () => {
        useCatalog();

        expect(mockUseQuery).toHaveBeenCalledWith({
          queryKey: expect.arrayContaining(['extensions', 'catalog']),
          queryFn: expect.any(Function),
          staleTime: 5 * 60 * 1000,
        });
      });

      it('includes forceRefresh in query key when provided', () => {
        useCatalog({ forceRefresh: true });

        expect(mockUseQuery).toHaveBeenCalledWith({
          queryKey: ['extensions', 'catalog', true],
          queryFn: expect.any(Function),
          staleTime: 5 * 60 * 1000,
        });
      });
    });

    describe('useCatalogSearch', () => {
      it('calls useQuery with search parameters', () => {
        const query = ref('test');
        const type = ref<ExtensionType | undefined>('summarizer');
        const verifiedOnly = ref(true);

        useCatalogSearch(query, type, verifiedOnly);

        expect(mockUseQuery).toHaveBeenCalledWith({
          queryKey: expect.arrayContaining(['extensions', 'catalog', 'search']),
          queryFn: expect.any(Function),
          staleTime: 5 * 60 * 1000,
        });
      });
    });
  });

  describe('install/uninstall hooks', () => {
    describe('useInstallExtension', () => {
      it('calls useMutation with correct config', () => {
        useInstallExtension();

        expect(mockUseMutation).toHaveBeenCalledWith({
          mutationFn: expect.any(Function),
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        });
      });

      it('accepts optional callbacks', () => {
        const onSuccess = vi.fn();
        const onError = vi.fn();

        useInstallExtension({ onSuccess, onError });

        expect(mockUseMutation).toHaveBeenCalled();
      });
    });

    describe('useUninstallExtension', () => {
      it('calls useMutation with correct config', () => {
        useUninstallExtension();

        expect(mockUseMutation).toHaveBeenCalledWith({
          mutationFn: expect.any(Function),
          onSuccess: expect.any(Function),
          onError: expect.any(Function),
        });
      });

      it('accepts optional callbacks', () => {
        const onSuccess = vi.fn();
        const onError = vi.fn();

        useUninstallExtension({ onSuccess, onError });

        expect(mockUseMutation).toHaveBeenCalled();
      });
    });
  });
});

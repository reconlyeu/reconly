import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import {
  FETCHERS_QUERY_KEY,
  useFetchersList,
  useFetcher,
  getFetcherSettingsPrefix,
  getFetcherSettingKey,
} from '../useFetchers';
import type { Fetcher } from '@/types/entities';

// Mock the API
vi.mock('@/services/api', () => ({
  fetchersApi: {
    list: vi.fn(),
  },
}));

const mockUseQuery = vi.mocked(useQuery);

describe('useFetchers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('FETCHERS_QUERY_KEY', () => {
    it('has correct value', () => {
      expect(FETCHERS_QUERY_KEY).toEqual(['fetchers']);
    });
  });

  describe('useFetchersList', () => {
    it('calls useQuery with correct parameters', () => {
      useFetchersList();

      expect(mockUseQuery).toHaveBeenCalledWith({
        queryKey: FETCHERS_QUERY_KEY,
        queryFn: expect.any(Function),
        staleTime: 5 * 60 * 1000,
      });
    });
  });

  describe('useFetcher', () => {
    it('returns fetcher by name from list', () => {
      const mockFetchers: Fetcher[] = [
        { name: 'rss', description: 'RSS fetcher', config_schema: { fields: [] }, is_configured: true, is_extension: false },
        { name: 'web', description: 'Web fetcher', config_schema: { fields: [] }, is_configured: true, is_extension: false },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockFetchers),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { fetcher, isLoading, isError } = useFetcher('rss');

      expect(fetcher.value).toEqual(mockFetchers[0]);
      expect(isLoading.value).toBe(false);
      expect(isError.value).toBe(false);
    });

    it('returns null when fetcher not found', () => {
      mockUseQuery.mockReturnValue({
        data: ref([]),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { fetcher } = useFetcher('nonexistent');

      expect(fetcher.value).toBeNull();
    });

    it('returns null when data is not yet loaded', () => {
      mockUseQuery.mockReturnValue({
        data: ref(null),
        isLoading: ref(true),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { fetcher } = useFetcher('rss');

      expect(fetcher.value).toBeNull();
    });
  });

  describe('helper functions', () => {
    describe('getFetcherSettingsPrefix', () => {
      it('returns correct prefix', () => {
        expect(getFetcherSettingsPrefix('rss')).toBe('fetch.rss');
        expect(getFetcherSettingsPrefix('web')).toBe('fetch.web');
        expect(getFetcherSettingsPrefix('imap')).toBe('fetch.imap');
      });
    });

    describe('getFetcherSettingKey', () => {
      it('returns correct full key', () => {
        expect(getFetcherSettingKey('rss', 'timeout')).toBe('fetch.rss.timeout');
        expect(getFetcherSettingKey('web', 'user_agent')).toBe('fetch.web.user_agent');
      });
    });
  });
});

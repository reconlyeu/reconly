import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ref } from 'vue';
import { useQuery, useMutation } from '@tanstack/vue-query';
import {
  EXPORTERS_QUERY_KEY,
  useExportersList,
  useExporter,
  useDirectExportCapableExporters,
  useEnabledExporters,
  useEnabledDirectExportExporters,
  useToggleExporter,
  useExportToPath,
  getExporterSettingsPrefix,
  getExporterSettingKey,
} from '../useExporters';
import type { Exporter } from '@/types/entities';

// Mock the API
vi.mock('@/services/api', () => ({
  exportersApi: {
    list: vi.fn(),
    setEnabled: vi.fn(),
  },
  digestsApi: {
    exportToPath: vi.fn(),
  },
}));

const mockUseQuery = vi.mocked(useQuery);
const mockUseMutation = vi.mocked(useMutation);

describe('useExporters', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('EXPORTERS_QUERY_KEY', () => {
    it('has correct value', () => {
      expect(EXPORTERS_QUERY_KEY).toEqual(['exporters']);
    });
  });

  describe('useExportersList', () => {
    it('calls useQuery with correct parameters', () => {
      useExportersList();

      expect(mockUseQuery).toHaveBeenCalledWith({
        queryKey: EXPORTERS_QUERY_KEY,
        queryFn: expect.any(Function),
        staleTime: 5 * 60 * 1000,
      });
    });
  });

  describe('useExporter', () => {
    it('returns exporter by name from list', () => {
      const mockExporters: Exporter[] = [
        { name: 'markdown', enabled: true, supports_direct_export: true, config_schema: null },
        { name: 'html', enabled: false, supports_direct_export: true, config_schema: null },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExporters),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporter, isLoading, isError } = useExporter('markdown');

      expect(exporter.value).toEqual(mockExporters[0]);
      expect(isLoading.value).toBe(false);
      expect(isError.value).toBe(false);
    });

    it('returns null when exporter not found', () => {
      mockUseQuery.mockReturnValue({
        data: ref([]),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporter } = useExporter('nonexistent');

      expect(exporter.value).toBeNull();
    });

    it('returns null when data is not yet loaded', () => {
      mockUseQuery.mockReturnValue({
        data: ref(null),
        isLoading: ref(true),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporter } = useExporter('markdown');

      expect(exporter.value).toBeNull();
    });
  });

  describe('useDirectExportCapableExporters', () => {
    it('filters exporters that support direct export', () => {
      const mockExporters: Exporter[] = [
        { name: 'markdown', enabled: true, supports_direct_export: true, config_schema: null },
        { name: 'email', enabled: true, supports_direct_export: false, config_schema: null },
        { name: 'html', enabled: false, supports_direct_export: true, config_schema: null },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExporters),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporters } = useDirectExportCapableExporters();

      expect(exporters.value).toHaveLength(2);
      expect(exporters.value.map((e) => e.name)).toEqual(['markdown', 'html']);
    });
  });

  describe('useEnabledExporters', () => {
    it('filters enabled exporters', () => {
      const mockExporters: Exporter[] = [
        { name: 'markdown', enabled: true, supports_direct_export: true, config_schema: null },
        { name: 'html', enabled: false, supports_direct_export: true, config_schema: null },
        { name: 'json', enabled: true, supports_direct_export: false, config_schema: null },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExporters),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporters } = useEnabledExporters();

      expect(exporters.value).toHaveLength(2);
      expect(exporters.value.map((e) => e.name)).toEqual(['markdown', 'json']);
    });
  });

  describe('useEnabledDirectExportExporters', () => {
    it('filters exporters that are both enabled and support direct export', () => {
      const mockExporters: Exporter[] = [
        { name: 'markdown', enabled: true, supports_direct_export: true, config_schema: null },
        { name: 'html', enabled: false, supports_direct_export: true, config_schema: null },
        { name: 'json', enabled: true, supports_direct_export: false, config_schema: null },
        { name: 'pdf', enabled: true, supports_direct_export: true, config_schema: null },
      ];

      mockUseQuery.mockReturnValue({
        data: ref(mockExporters),
        isLoading: ref(false),
        isError: ref(false),
        error: ref(null),
        refetch: vi.fn(),
      } as any);

      const { exporters } = useEnabledDirectExportExporters();

      expect(exporters.value).toHaveLength(2);
      expect(exporters.value.map((e) => e.name)).toEqual(['markdown', 'pdf']);
    });
  });

  describe('useToggleExporter', () => {
    it('calls useMutation with correct config', () => {
      useToggleExporter();

      expect(mockUseMutation).toHaveBeenCalledWith({
        mutationFn: expect.any(Function),
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      });
    });

    it('accepts optional callbacks', () => {
      const onSuccess = vi.fn();
      const onError = vi.fn();

      useToggleExporter({ onSuccess, onError });

      expect(mockUseMutation).toHaveBeenCalled();
    });
  });

  describe('useExportToPath', () => {
    it('calls useMutation with correct config', () => {
      useExportToPath();

      expect(mockUseMutation).toHaveBeenCalledWith({
        mutationFn: expect.any(Function),
        onSuccess: expect.any(Function),
        onError: expect.any(Function),
      });
    });
  });

  describe('helper functions', () => {
    describe('getExporterSettingsPrefix', () => {
      it('returns correct prefix', () => {
        expect(getExporterSettingsPrefix('markdown')).toBe('export.markdown');
        expect(getExporterSettingsPrefix('html')).toBe('export.html');
      });
    });

    describe('getExporterSettingKey', () => {
      it('returns correct full key', () => {
        expect(getExporterSettingKey('markdown', 'output_path')).toBe('export.markdown.output_path');
        expect(getExporterSettingKey('html', 'template')).toBe('export.html.template');
      });
    });
  });
});

/**
 * API client service using Axios
 *
 * Provides typed API calls to the Reconly backend.
 * Uses TanStack Vue Query for caching and state management.
 */

import axios, { type AxiosInstance, type AxiosError } from 'axios';
import type {
  Source,
  SourceCreate,
  SourceUpdate,
  Feed,
  FeedCreate,
  FeedUpdate,
  FeedSource,
  FeedSourceCreate,
  FeedRun,
  FeedRunSourcesResponse,
  PromptTemplate,
  PromptTemplateCreate,
  PromptTemplateUpdate,
  ReportTemplate,
  ReportTemplateCreate,
  ReportTemplateUpdate,
  Digest,
  Tag,
  TagListResponse,
  TagSuggestionsResponse,
  TagDeleteResponse,
  TagBulkDeleteResponse,
  ProviderConfig,
  ModelInfo,
  AnalyticsSummary,
  TokensByProvider,
  TokensByFeed,
  UsageOverTime,
  Settings,
  EmailSettings,
  ExportSettings,
  SettingsV2,
  SettingsUpdateRequest,
  SettingsResetRequest,
  SettingsResetResponse,
  DashboardStats,
  PaginatedResponse,
  ApiError,
  FeedRunStatus,
  BatchDeleteResponse,
  Exporter,
  ExporterListResponse,
  ExportToPathRequest,
  ExportToPathResponse,
  // Fetcher types
  Fetcher,
  FetcherListResponse,
  // Extension types
  Extension,
  ExtensionType,
  ExtensionListResponse,
  CatalogEntry,
  CatalogResponse,
  ExtensionInstallResponse,
  // Feed Bundle types
  FeedBundle,
  BundleExportRequest,
  BundleExportResponse,
  BundleValidateResponse,
  BundlePreviewResponse,
  BundleImportResponse,
  // Knowledge Graph types
  GraphResponse,
  GraphFilters,
  // Agent Run types
  AgentRun,
  AgentRunStatus,
  AgentRunListResponse,
} from '@/types/entities';

// ═══════════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════════

const API_BASE_URL = import.meta.env.PUBLIC_API_URL || '/api/v1';

/**
 * Create axios instance with default configuration
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      'Content-Type': 'application/json',
    },
    timeout: 30000, // 30 seconds
  });

  // Response interceptor for error handling
  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError<ApiError>) => {
      // Transform error to consistent format
      const apiError: ApiError = {
        detail: error.response?.data?.detail || error.message || 'An error occurred',
        status_code: error.response?.status,
      };
      return Promise.reject(apiError);
    }
  );

  return client;
};

export const apiClient = createApiClient();

// ═══════════════════════════════════════════════════════════════════════════════
// HEALTH
// ═══════════════════════════════════════════════════════════════════════════════

export const healthApi = {
  check: async (): Promise<{ status: string; timestamp: string }> => {
    // Health endpoint is at root level, not under /api/v1
    const { data } = await axios.get('/health', { timeout: 5000 });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

export const dashboardApi = {
  getStats: async (): Promise<DashboardStats> => {
    const { data } = await apiClient.get<DashboardStats>('/dashboard/stats');
    return data;
  },

  getRecentRuns: async (limit = 5): Promise<FeedRun[]> => {
    const { data } = await apiClient.get<{ items: FeedRun[]; total: number }>('/feed-runs/', {
      params: { limit },
    });
    return data.items;
  },

  getRecentDigests: async (limit = 5): Promise<Digest[]> => {
    const { data } = await apiClient.get<{ total: number; digests: Digest[] }>('/digests/', {
      params: { limit },
    });
    return data.digests;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SOURCES
// ═══════════════════════════════════════════════════════════════════════════════

export const sourcesApi = {
  list: async (type?: string): Promise<Source[]> => {
    const { data } = await apiClient.get<Source[]>('/sources/', {
      params: type ? { type } : undefined,
    });
    return data;
  },

  get: async (id: number): Promise<Source> => {
    const { data } = await apiClient.get<Source>(`/sources/${id}`);
    return data;
  },

  create: async (source: SourceCreate): Promise<Source> => {
    const { data } = await apiClient.post<Source>('/sources/', source);
    return data;
  },

  update: async (id: number, source: SourceUpdate): Promise<Source> => {
    const { data } = await apiClient.put<Source>(`/sources/${id}`, source);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/sources/${id}`);
  },

  toggleEnabled: async (id: number, enabled: boolean): Promise<Source> => {
    const { data } = await apiClient.patch<Source>(`/sources/${id}`, { enabled });
    return data;
  },

  batchDelete: async (ids: number[]): Promise<BatchDeleteResponse> => {
    const { data } = await apiClient.post<BatchDeleteResponse>('/sources/batch-delete', { ids });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// FEEDS
// ═══════════════════════════════════════════════════════════════════════════════

export const feedsApi = {
  list: async (): Promise<Feed[]> => {
    const { data } = await apiClient.get<Feed[]>('/feeds/');
    return data;
  },

  get: async (id: number): Promise<Feed> => {
    const { data } = await apiClient.get<Feed>(`/feeds/${id}`);
    return data;
  },

  create: async (feed: FeedCreate): Promise<Feed> => {
    const { data } = await apiClient.post<Feed>('/feeds/', feed);
    return data;
  },

  update: async (id: number, feed: FeedUpdate): Promise<Feed> => {
    const { data } = await apiClient.put<Feed>(`/feeds/${id}`, feed);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/feeds/${id}`);
  },

  run: async (id: number): Promise<FeedRun> => {
    const { data } = await apiClient.post<FeedRun>(`/feeds/${id}/run`);
    return data;
  },

  getRuns: async (id: number, page = 1, perPage = 20): Promise<PaginatedResponse<FeedRun>> => {
    const { data } = await apiClient.get<PaginatedResponse<FeedRun>>(`/feeds/${id}/runs`, {
      params: { page, per_page: perPage },
    });
    return data;
  },

  // Feed source management
  addSource: async (feedId: number, source: FeedSourceCreate): Promise<FeedSource> => {
    const { data } = await apiClient.post<FeedSource>(`/feeds/${feedId}/sources`, source);
    return data;
  },

  removeSource: async (feedId: number, sourceId: number): Promise<void> => {
    await apiClient.delete(`/feeds/${feedId}/sources/${sourceId}`);
  },

  updateSource: async (
    feedId: number,
    sourceId: number,
    updates: Partial<FeedSourceCreate>
  ): Promise<FeedSource> => {
    const { data } = await apiClient.patch<FeedSource>(
      `/feeds/${feedId}/sources/${sourceId}`,
      updates
    );
    return data;
  },

  batchDelete: async (ids: number[]): Promise<BatchDeleteResponse> => {
    const { data } = await apiClient.post<BatchDeleteResponse>('/feeds/batch-delete', { ids });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// FEED RUNS
// ═══════════════════════════════════════════════════════════════════════════════

export interface FeedRunFilters {
  feed_id?: number;
  status?: FeedRunStatus;
  from_date?: string;
  to_date?: string;
}

export const feedRunsApi = {
  list: async (
    filters?: FeedRunFilters,
    limit = 20,
    offset = 0
  ): Promise<{ items: FeedRun[]; total: number }> => {
    const { data } = await apiClient.get<{ items: FeedRun[]; total: number }>('/feed-runs/', {
      params: { ...filters, limit, offset },
    });
    return data;
  },

  get: async (id: number): Promise<FeedRun> => {
    const { data } = await apiClient.get<FeedRun>(`/feed-runs/${id}`);
    return data;
  },

  getSources: async (id: number): Promise<FeedRunSourcesResponse> => {
    const { data } = await apiClient.get<FeedRunSourcesResponse>(`/feed-runs/${id}/sources`);
    return data;
  },

  getDigests: async (id: number): Promise<Digest[]> => {
    const { data } = await apiClient.get<Digest[]>(`/feed-runs/${id}/digests`);
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// AGENT RUNS
// ═══════════════════════════════════════════════════════════════════════════════

export interface AgentRunFilters {
  source_id?: number;
  status?: AgentRunStatus;
  from_date?: string;
  to_date?: string;
}

export const agentRunsApi = {
  list: async (
    filters?: AgentRunFilters,
    limit = 20,
    offset = 0
  ): Promise<AgentRunListResponse> => {
    const searchParams = new URLSearchParams();
    if (filters?.source_id) searchParams.set('source_id', String(filters.source_id));
    if (filters?.status) searchParams.set('status', filters.status);
    if (filters?.from_date) searchParams.set('from_date', filters.from_date);
    if (filters?.to_date) searchParams.set('to_date', filters.to_date);
    if (limit) searchParams.set('limit', String(limit));
    if (offset) searchParams.set('offset', String(offset));
    const query = searchParams.toString();
    const { data } = await apiClient.get<AgentRunListResponse>(
      `/agent-runs/${query ? '?' + query : ''}`
    );
    return data;
  },

  get: async (id: number): Promise<AgentRun> => {
    const { data } = await apiClient.get<AgentRun>(`/agent-runs/${id}`);
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// PROMPT TEMPLATES
// ═══════════════════════════════════════════════════════════════════════════════

export const promptTemplatesApi = {
  list: async (activeOnly?: boolean): Promise<PromptTemplate[]> => {
    const { data } = await apiClient.get<PromptTemplate[]>('/templates/prompt', {
      params: activeOnly !== undefined ? { active_only: activeOnly } : undefined,
    });
    return data;
  },

  get: async (id: number): Promise<PromptTemplate> => {
    const { data } = await apiClient.get<PromptTemplate>(`/templates/prompt/${id}`);
    return data;
  },

  create: async (template: PromptTemplateCreate): Promise<PromptTemplate> => {
    const { data } = await apiClient.post<PromptTemplate>('/templates/prompt', template);
    return data;
  },

  update: async (id: number, template: PromptTemplateUpdate): Promise<PromptTemplate> => {
    const { data } = await apiClient.put<PromptTemplate>(`/templates/prompt/${id}`, template);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/templates/prompt/${id}`);
  },

  toggle: async (id: number): Promise<PromptTemplate> => {
    const { data } = await apiClient.patch<PromptTemplate>(`/templates/prompt/${id}/toggle`);
    return data;
  },

  batchDelete: async (ids: number[]): Promise<BatchDeleteResponse> => {
    const { data } = await apiClient.post<BatchDeleteResponse>('/templates/prompt/batch-delete', { ids });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// REPORT TEMPLATES
// ═══════════════════════════════════════════════════════════════════════════════

export const reportTemplatesApi = {
  list: async (activeOnly?: boolean): Promise<ReportTemplate[]> => {
    const { data } = await apiClient.get<ReportTemplate[]>('/templates/report', {
      params: activeOnly !== undefined ? { active_only: activeOnly } : undefined,
    });
    return data;
  },

  get: async (id: number): Promise<ReportTemplate> => {
    const { data } = await apiClient.get<ReportTemplate>(`/templates/report/${id}`);
    return data;
  },

  create: async (template: ReportTemplateCreate): Promise<ReportTemplate> => {
    const { data } = await apiClient.post<ReportTemplate>('/templates/report', template);
    return data;
  },

  update: async (id: number, template: ReportTemplateUpdate): Promise<ReportTemplate> => {
    const { data } = await apiClient.put<ReportTemplate>(`/templates/report/${id}`, template);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/templates/report/${id}`);
  },

  toggle: async (id: number): Promise<ReportTemplate> => {
    const { data } = await apiClient.patch<ReportTemplate>(`/templates/report/${id}/toggle`);
    return data;
  },

  batchDelete: async (ids: number[]): Promise<BatchDeleteResponse> => {
    const { data } = await apiClient.post<BatchDeleteResponse>('/templates/report/batch-delete', { ids });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// DIGESTS
// ═══════════════════════════════════════════════════════════════════════════════

export interface DigestFilters {
  feed_id?: number;
  source_id?: number;
  tags?: string;  // Comma-separated tag names for filtering
  search?: string;
}

export const digestsApi = {
  list: async (
    filters?: DigestFilters,
    page = 1,
    perPage = 20
  ): Promise<{ total: number; digests: Digest[] }> => {
    const { data } = await apiClient.get<{ total: number; digests: Digest[] }>('/digests/', {
      params: { ...filters, limit: perPage },
    });
    return data;
  },

  get: async (id: number): Promise<Digest> => {
    const { data } = await apiClient.get<Digest>(`/digests/${id}`);
    return data;
  },

  delete: async (id: number): Promise<void> => {
    await apiClient.delete(`/digests/${id}`);
  },

  export: async (
    ids: number[],
    format: string
  ): Promise<Blob> => {
    const { data } = await apiClient.post(
      '/digests/export',
      { ids, format },
      { responseType: 'blob' }
    );
    return data;
  },

  getTags: async (): Promise<Tag[]> => {
    const { data } = await apiClient.get<TagListResponse>('/tags/');
    return data.tags;
  },

  updateTags: async (id: number, tags: string[]): Promise<Digest> => {
    const { data } = await apiClient.patch<Digest>(`/digests/${id}/tags`, { tags });
    return data;
  },

  batchDelete: async (ids: number[]): Promise<BatchDeleteResponse> => {
    const { data } = await apiClient.post<BatchDeleteResponse>('/digests/batch-delete', { ids });
    return data;
  },

  exportToPath: async (request: ExportToPathRequest): Promise<ExportToPathResponse> => {
    const { data } = await apiClient.post<ExportToPathResponse>('/digests/export-to-path/', request);
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// TAGS
// ═══════════════════════════════════════════════════════════════════════════════

export const tagsApi = {
  /**
   * List all tags with digest counts.
   * Tags are sorted by digest count (most used first).
   */
  list: async (): Promise<Tag[]> => {
    const { data } = await apiClient.get<TagListResponse>('/tags/');
    return data.tags;
  },

  /**
   * Get tag suggestions for autocomplete.
   * @param query - Query string to match against tag names (prefix match)
   * @param limit - Maximum number of suggestions to return
   */
  getSuggestions: async (query: string = '', limit: number = 10): Promise<TagSuggestionsResponse> => {
    const { data } = await apiClient.get<TagSuggestionsResponse>('/tags/suggestions/', {
      params: { q: query, limit },
    });
    return data;
  },

  /**
   * Delete a specific tag by ID.
   * This will also remove the tag from all associated digests.
   */
  delete: async (tagId: number): Promise<TagDeleteResponse> => {
    const { data } = await apiClient.delete<TagDeleteResponse>(`/tags/${tagId}/`);
    return data;
  },

  /**
   * Delete all tags that are not associated with any digests.
   */
  deleteUnused: async (): Promise<TagBulkDeleteResponse> => {
    const { data } = await apiClient.delete<TagBulkDeleteResponse>('/tags/unused/');
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// EXPORTERS
// ═══════════════════════════════════════════════════════════════════════════════

export const exportersApi = {
  list: async (enabledOnly?: boolean): Promise<Exporter[]> => {
    const params = enabledOnly ? { enabled_only: true } : {};
    const { data } = await apiClient.get<ExporterListResponse>('/exporters/', { params });
    return data.exporters;
  },

  setEnabled: async (name: string, enabled: boolean): Promise<Exporter> => {
    const { data } = await apiClient.put<Exporter>(`/exporters/${name}/enabled`, { enabled });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// FETCHERS
// ═══════════════════════════════════════════════════════════════════════════════

export const fetchersApi = {
  list: async (enabledOnly?: boolean): Promise<Fetcher[]> => {
    const params = enabledOnly ? { enabled_only: true } : {};
    const { data } = await apiClient.get<FetcherListResponse>('/fetchers/', { params });
    return data.fetchers;
  },

  get: async (name: string): Promise<Fetcher> => {
    const { data } = await apiClient.get<Fetcher>(`/fetchers/${name}`);
    return data;
  },

  setEnabled: async (name: string, enabled: boolean): Promise<Fetcher> => {
    const { data } = await apiClient.put<Fetcher>(`/fetchers/${name}/enabled`, { enabled });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// EXTENSIONS
// ═══════════════════════════════════════════════════════════════════════════════

export const extensionsApi = {
  list: async (type?: ExtensionType): Promise<Extension[]> => {
    const params = type ? { type } : {};
    const { data } = await apiClient.get<ExtensionListResponse>('/extensions/', { params });
    return data.items;
  },

  listByType: async (type: ExtensionType): Promise<Extension[]> => {
    const { data } = await apiClient.get<ExtensionListResponse>(`/extensions/${type}/`);
    return data.items;
  },

  get: async (type: ExtensionType, name: string): Promise<Extension> => {
    const { data } = await apiClient.get<Extension>(`/extensions/${type}/${name}/`);
    return data;
  },

  setEnabled: async (type: ExtensionType, name: string, enabled: boolean): Promise<Extension> => {
    const { data } = await apiClient.put<Extension>(`/extensions/${type}/${name}/enabled`, { enabled });
    return data;
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // Catalog (Phase 2)
  // ─────────────────────────────────────────────────────────────────────────────

  getCatalog: async (forceRefresh = false): Promise<CatalogEntry[]> => {
    const params = forceRefresh ? { force_refresh: true } : {};
    const { data } = await apiClient.get<CatalogResponse>('/extensions/catalog/', { params });
    return data.extensions;
  },

  searchCatalog: async (query?: string, type?: ExtensionType, verifiedOnly = false): Promise<CatalogEntry[]> => {
    const params: Record<string, unknown> = {};
    if (query) params.q = query;
    if (type) params.type = type;
    if (verifiedOnly) params.verified_only = true;
    const { data } = await apiClient.get<CatalogResponse>('/extensions/catalog/search/', { params });
    return data.extensions;
  },

  install: async (packageName: string, upgrade = false): Promise<ExtensionInstallResponse> => {
    const { data } = await apiClient.post<ExtensionInstallResponse>('/extensions/install/', {
      package: packageName,
      upgrade,
    });
    return data;
  },

  uninstall: async (type: ExtensionType, name: string): Promise<ExtensionInstallResponse> => {
    const { data } = await apiClient.delete<ExtensionInstallResponse>(`/extensions/${type}/${name}/`);
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS
// ═══════════════════════════════════════════════════════════════════════════════

export type AnalyticsPeriod = '7d' | '30d' | '90d';

export const analyticsApi = {
  getSummary: async (period: AnalyticsPeriod = '7d'): Promise<AnalyticsSummary> => {
    const { data } = await apiClient.get<AnalyticsSummary>('/analytics/summary', {
      params: { period },
    });
    return data;
  },

  getTokensByProvider: async (period: AnalyticsPeriod = '7d'): Promise<TokensByProvider[]> => {
    const { data } = await apiClient.get<TokensByProvider[]>('/analytics/tokens-by-provider', {
      params: { period },
    });
    return data;
  },

  getTokensByFeed: async (period: AnalyticsPeriod = '7d'): Promise<TokensByFeed[]> => {
    const { data } = await apiClient.get<TokensByFeed[]>('/analytics/tokens-by-feed', {
      params: { period },
    });
    return data;
  },

  getUsageOverTime: async (period: AnalyticsPeriod = '7d'): Promise<UsageOverTime[]> => {
    const { data } = await apiClient.get<UsageOverTime[]>('/analytics/usage', {
      params: { period },
    });
    return data;
  },

  export: async (period: AnalyticsPeriod = '7d'): Promise<Blob> => {
    const { data } = await apiClient.get('/analytics/export', {
      params: { period },
      responseType: 'blob',
    });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// PROVIDERS
// ═══════════════════════════════════════════════════════════════════════════════

export interface ProviderStatus {
  name: string;
  status: 'available' | 'configured' | 'not_configured';
  masked_api_key: string | null;
  models: string[];
  is_default: boolean;
}

export const providersApi = {
  getConfig: async (): Promise<ProviderConfig> => {
    const { data } = await apiClient.get<ProviderConfig>('/providers');
    return data;
  },

  getStatus: async (): Promise<ProviderStatus[]> => {
    const { data } = await apiClient.get<{ providers: ProviderStatus[] }>('/providers');
    return data.providers;
  },

  getModels: async (providerName: string): Promise<ModelInfo[]> => {
    const { data } = await apiClient.get<ModelInfo[]>(`/providers/${providerName}/models`);
    return data;
  },

  refreshModels: async (providerName?: string): Promise<{ providers?: Record<string, ModelInfo[]>; provider?: string; models?: ModelInfo[] }> => {
    const params = providerName ? { provider_name: providerName } : {};
    const { data } = await apiClient.post('/providers/refresh-models', null, { params });
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════════════════════

export const settingsApi = {
  get: async (): Promise<Settings> => {
    const { data } = await apiClient.get<Settings>('/settings');
    return data;
  },

  update: async (settings: Partial<Settings>): Promise<Settings> => {
    const { data } = await apiClient.put<Settings>('/settings', settings);
    return data;
  },

  updateEmail: async (email: EmailSettings): Promise<Settings> => {
    const { data } = await apiClient.put<Settings>('/settings/email', email);
    return data;
  },

  updateExports: async (exports: ExportSettings): Promise<Settings> => {
    const { data } = await apiClient.put<Settings>('/settings/exports', exports);
    return data;
  },

  testEmail: async (): Promise<{ success: boolean; message: string }> => {
    const { data } = await apiClient.post<{ success: boolean; message: string }>(
      '/settings/test-email'
    );
    return data;
  },

  // V2 Settings API (with source indicators)
  getV2: async (category?: string): Promise<SettingsV2> => {
    const params = category ? { category } : {};
    const { data } = await apiClient.get<SettingsV2>('/settings/v2', { params });
    return data;
  },

  updateV2: async (request: SettingsUpdateRequest): Promise<{
    updated: string[];
    errors: Array<{ key: string; error: string }>;
    message: string;
  }> => {
    const { data } = await apiClient.put('/settings/v2', request);
    return data;
  },

  reset: async (request: SettingsResetRequest): Promise<SettingsResetResponse> => {
    const { data } = await apiClient.post<SettingsResetResponse>('/settings/reset', request);
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// AUTHENTICATION (OSS Password Protection)
// ═══════════════════════════════════════════════════════════════════════════════

export interface AuthConfig {
  auth_required: boolean;
  edition: string;
}

export interface LoginRequest {
  password: string;
}

export interface LoginResponse {
  success: boolean;
  message: string;
}

export const authApi = {
  /**
   * Get authentication configuration.
   * Returns whether auth is required and the current edition.
   */
  getConfig: async (): Promise<AuthConfig> => {
    const { data } = await apiClient.get<AuthConfig>('/auth/config/');
    return data;
  },

  /**
   * Login with password.
   * On success, a session cookie is set by the server.
   */
  login: async (password: string): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/login/', {
      password,
    });
    return data;
  },

  /**
   * Logout and clear session.
   */
  logout: async (): Promise<LoginResponse> => {
    const { data } = await apiClient.post<LoginResponse>('/auth/logout/');
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// FEED BUNDLES (Marketplace Export/Import)
// ═══════════════════════════════════════════════════════════════════════════════

export const bundlesApi = {
  /**
   * Export a feed as a portable JSON bundle.
   * @param feedId - The ID of the feed to export
   * @param options - Optional export configuration (version, category, tags, etc.)
   */
  export: async (feedId: number, options?: BundleExportRequest): Promise<BundleExportResponse> => {
    const { data } = await apiClient.post<BundleExportResponse>(
      `/feeds/${feedId}/export`,
      options || {}
    );
    return data;
  },

  /**
   * Download a feed as a bundle JSON file.
   * Triggers browser download of the bundle file.
   * @param feedId - The ID of the feed to export
   * @param options - Optional export configuration
   */
  downloadBundle: async (feedId: number, options?: BundleExportRequest): Promise<void> => {
    const response = await bundlesApi.export(feedId, options);
    if (response.success) {
      // Create blob and trigger download
      const blob = new Blob([JSON.stringify(response.bundle, null, 2)], {
        type: 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = response.filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    }
  },

  /**
   * Validate a bundle without importing it.
   * @param bundle - The bundle JSON object to validate
   */
  validate: async (bundle: FeedBundle | Record<string, unknown>): Promise<BundleValidateResponse> => {
    const { data } = await apiClient.post<BundleValidateResponse>('/bundles/validate', {
      bundle,
    });
    return data;
  },

  /**
   * Preview what would be created by importing a bundle.
   * @param bundle - The bundle JSON object to preview
   */
  preview: async (bundle: FeedBundle | Record<string, unknown>): Promise<BundlePreviewResponse> => {
    const { data } = await apiClient.post<BundlePreviewResponse>('/bundles/preview', {
      bundle,
    });
    return data;
  },

  /**
   * Import a bundle to create a new feed with sources and templates.
   * @param bundle - The bundle JSON object to import
   * @param skipDuplicateSources - If true, reuse existing sources with the same URL (default: true)
   */
  import: async (
    bundle: FeedBundle | Record<string, unknown>,
    skipDuplicateSources = true
  ): Promise<BundleImportResponse> => {
    const { data } = await apiClient.post<BundleImportResponse>('/bundles/import', {
      bundle,
      skip_duplicate_sources: skipDuplicateSources,
    });
    return data;
  },

  /**
   * Get the JSON schema for feed bundles.
   */
  getSchema: async (): Promise<Record<string, unknown>> => {
    const { data } = await apiClient.get<Record<string, unknown>>('/bundles/schema');
    return data;
  },
};

// ═══════════════════════════════════════════════════════════════════════════════
// KNOWLEDGE GRAPH
// ═══════════════════════════════════════════════════════════════════════════════

export const graphApi = {
  /**
   * Get graph nodes and edges for visualization.
   * @param filters - Optional filters for the graph query
   */
  getNodes: async (filters?: GraphFilters): Promise<GraphResponse> => {
    const params: Record<string, unknown> = {};

    if (filters?.center_digest_id) params.center_digest_id = filters.center_digest_id;
    if (filters?.depth !== undefined) params.depth = filters.depth;
    if (filters?.min_similarity !== undefined) params.min_similarity = filters.min_similarity;
    if (filters?.include_tags !== undefined) params.include_tags = filters.include_tags;
    if (filters?.relationship_types?.length) params.relationship_types = filters.relationship_types.join(',');
    if (filters?.limit !== undefined) params.limit = filters.limit;
    if (filters?.feed_id) params.feed_id = filters.feed_id;
    if (filters?.from_date) params.from_date = filters.from_date;
    if (filters?.to_date) params.to_date = filters.to_date;
    if (filters?.tags?.length) params.tags = filters.tags.join(',');

    const { data } = await apiClient.get<GraphResponse>('/graph/nodes/', { params });
    return data;
  },

  /**
   * Expand a specific node to get its neighbors.
   * @param nodeId - The ID of the node to expand (e.g., "d_42" for digest 42)
   * @param depth - How many levels to expand (default: 1)
   * @param minSimilarity - Minimum similarity score for semantic edges
   */
  expandNode: async (
    nodeId: string,
    depth = 1,
    minSimilarity = 0.5
  ): Promise<GraphResponse> => {
    const { data } = await apiClient.get<GraphResponse>(`/graph/expand/${nodeId}/`, {
      params: { depth, min_similarity: minSimilarity },
    });
    return data;
  },
};

/**
 * TypeScript types matching the Reconly entity model
 *
 * These types mirror the Python SQLAlchemy models in:
 * packages/core/reconly_core/database/models.py
 */

// ═══════════════════════════════════════════════════════════════════════════════
// SOURCE
// ═══════════════════════════════════════════════════════════════════════════════

export type SourceType = 'rss' | 'youtube' | 'website' | 'blog' | 'agent' | 'imap';
export type FilterMode = 'title_only' | 'content' | 'both';
export type AuthStatus = 'active' | 'pending_oauth' | 'auth_failed';
export type IMAPProvider = 'gmail' | 'outlook' | 'generic';
export type SearchProvider = 'duckduckgo' | 'searxng' | 'tavily';

export interface SourceConfig {
  // RSS-specific
  max_items?: number;
  fetch_full_content?: boolean;
  // YouTube-specific
  fetch_transcript?: boolean;
  // Website/Blog-specific
  selectors?: {
    title?: string;
    content?: string;
    date?: string;
  };
  // Agent-specific
  max_iterations?: number;
  search_provider?: SearchProvider;  // Per-source search provider override
  // IMAP-specific
  provider?: IMAPProvider;
  folders?: string[];
  from_filter?: string;
  subject_filter?: string;
  imap_host?: string;
  imap_port?: number;
  imap_username?: string;
  imap_use_ssl?: boolean;
}

export interface Source {
  id: number;
  user_id?: number | null;
  name: string;
  type: SourceType;
  url: string;
  config?: SourceConfig | null;
  enabled: boolean;
  default_language?: string | null;
  default_provider?: string | null;
  default_model?: string | null;
  // Content filtering
  include_keywords?: string[] | null;
  exclude_keywords?: string[] | null;
  filter_mode?: FilterMode | null;
  use_regex?: boolean;
  created_at: string;
  updated_at?: string | null;
  // IMAP-specific fields
  auth_status?: AuthStatus | null;
  oauth_credential_id?: number | null;
}

export interface SourceCreate {
  name: string;
  type: SourceType;
  url: string;
  config?: SourceConfig | null;
  enabled?: boolean;
  // Content filtering
  include_keywords?: string[] | null;
  exclude_keywords?: string[] | null;
  filter_mode?: FilterMode;
  use_regex?: boolean;
}

export interface SourceUpdate {
  name?: string;
  type?: SourceType;
  url?: string;
  config?: SourceConfig | null;
  enabled?: boolean;
  // Content filtering
  include_keywords?: string[] | null;
  exclude_keywords?: string[] | null;
  filter_mode?: FilterMode | null;
  use_regex?: boolean | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FEED
// ═══════════════════════════════════════════════════════════════════════════════

export type DigestMode = 'individual' | 'per_source' | 'all_sources';

export interface OutputConfig {
  db?: boolean;
  email?: {
    enabled: boolean;
    recipients: string[];
  };
  obsidian?: {
    vault_path: string;
    folder: string;
  };
}

export interface Feed {
  id: number;
  user_id?: number | null;
  name: string;
  description?: string | null;
  digest_mode: DigestMode;
  schedule_cron?: string | null;
  schedule_enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
  prompt_template_id?: number | null;
  report_template_id?: number | null;
  model_provider?: string | null;
  model_name?: string | null;
  output_config?: OutputConfig | null;
  created_at: string;
  updated_at?: string | null;
  feed_sources?: FeedSource[];
}

export interface FeedCreate {
  name: string;
  description?: string | null;
  digest_mode?: DigestMode;
  schedule_cron?: string | null;
  schedule_enabled?: boolean;
  prompt_template_id?: number | null;
  report_template_id?: number | null;
  model_provider?: string | null;
  model_name?: string | null;
  output_config?: OutputConfig | null;
  source_ids?: number[];
}

export interface FeedUpdate {
  name?: string;
  description?: string | null;
  digest_mode?: DigestMode;
  schedule_cron?: string | null;
  schedule_enabled?: boolean;
  prompt_template_id?: number | null;
  report_template_id?: number | null;
  model_provider?: string | null;
  model_name?: string | null;
  output_config?: OutputConfig | null;
  source_ids?: number[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// FEED SOURCE (Junction)
// ═══════════════════════════════════════════════════════════════════════════════

export interface FeedSource {
  feed_id: number;
  source_id: number;
  source_name?: string | null;
  source_type?: SourceType | null;
  enabled: boolean;
  priority: number;
}

export interface FeedSourceCreate {
  source_id: number;
  enabled?: boolean;
  priority?: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// TEMPLATE ORIGIN (for marketplace provenance tracking)
// ═══════════════════════════════════════════════════════════════════════════════

export type TemplateOrigin = 'builtin' | 'user' | 'imported';

// ═══════════════════════════════════════════════════════════════════════════════
// PROMPT TEMPLATE
// ═══════════════════════════════════════════════════════════════════════════════

export interface PromptTemplate {
  id: number;
  user_id?: number | null;
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt_template: string;
  language: string;
  target_length: number;
  model_provider?: string | null;
  model_name?: string | null;
  origin: TemplateOrigin;
  imported_from_bundle?: string | null;
  is_system: boolean; // Backwards compatibility - true if origin === 'builtin'
  is_active: boolean;
  created_at: string;
}

export interface PromptTemplateCreate {
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt_template: string;
  language?: string;
  target_length?: number;
  model_provider?: string | null;
  model_name?: string | null;
}

export interface PromptTemplateUpdate {
  name?: string;
  description?: string | null;
  system_prompt?: string;
  user_prompt_template?: string;
  language?: string;
  target_length?: number;
  model_provider?: string | null;
  model_name?: string | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// REPORT TEMPLATE
// ═══════════════════════════════════════════════════════════════════════════════

export type ReportFormat = 'markdown' | 'html' | 'text';

export interface ReportTemplate {
  id: number;
  user_id?: number | null;
  name: string;
  description?: string | null;
  format: ReportFormat;
  template_content: string;
  origin: TemplateOrigin;
  imported_from_bundle?: string | null;
  is_system: boolean; // Backwards compatibility - true if origin === 'builtin'
  is_active: boolean;
  created_at: string;
}

export interface ReportTemplateCreate {
  name: string;
  description?: string | null;
  format?: ReportFormat;
  template_content: string;
}

export interface ReportTemplateUpdate {
  name?: string;
  description?: string | null;
  format?: ReportFormat;
  template_content?: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FEED RUN
// ═══════════════════════════════════════════════════════════════════════════════

export type FeedRunStatus = 'pending' | 'running' | 'completed' | 'completed_with_errors' | 'failed';
export type TriggerType = 'schedule' | 'manual' | 'api';
export type ErrorType = 'FetchError' | 'ParseError' | 'SummarizeError' | 'SaveError' | 'TimeoutError';

export interface SourceError {
  source_id: number;
  source_name?: string | null;
  error_type: ErrorType;
  message: string;
  timestamp: string;
}

export interface ErrorDetails {
  errors: SourceError[];
  summary?: string | null;
}

export interface FeedRun {
  id: number;
  feed_id: number;
  feed_name?: string | null;  // Included via join with Feed table
  triggered_by: TriggerType;
  triggered_by_user_id?: number | null;
  status: FeedRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  sources_total: number;
  sources_processed: number;
  sources_failed: number;
  items_processed: number;
  total_tokens_in: number;
  total_tokens_out: number;
  total_cost: number;
  error_log?: string | null;
  error_details?: ErrorDetails | null;  // Structured error information
  trace_id?: string | null;  // UUID for log correlation
  llm_provider?: string | null;  // LLM provider used (anthropic, openai, etc.)
  llm_model?: string | null;  // LLM model used (claude-3-5-sonnet, gpt-4, etc.)
  created_at: string;
  // Computed
  duration_seconds?: number | null;
  digests_count?: number;  // For detail response
  // Relationships (when expanded)
  feed?: Feed;
}

export interface FeedRunSourceStatus {
  source_id: number;
  source_name: string;
  source_type: SourceType;
  source_url?: string | null;
  status: 'success' | 'failed' | 'pending';
  error_message?: string | null;
}

export interface FeedRunSourcesResponse {
  run_id: number;
  sources: FeedRunSourceStatus[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// AGENT RUN
// ═══════════════════════════════════════════════════════════════════════════════

export type AgentRunStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface AgentToolCall {
  tool: string;
  input: Record<string, unknown>;
  output: string;
}

export interface AgentRun {
  id: number;
  source_id: number;
  source_name?: string | null;
  prompt: string;
  status: AgentRunStatus;
  started_at?: string | null;
  completed_at?: string | null;
  iterations: number;
  tool_calls?: AgentToolCall[] | null;
  sources_consulted?: string[] | null;
  result_title?: string | null;
  result_content?: string | null;
  tokens_in: number;
  tokens_out: number;
  estimated_cost: number;
  error_log?: string | null;
  trace_id?: string | null;
  created_at: string;
  duration_seconds?: number | null;
}

export interface AgentRunListResponse {
  items: AgentRun[];
  total: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// LLM USAGE LOG
// ═══════════════════════════════════════════════════════════════════════════════

export interface LLMUsageLog {
  id: number;
  user_id?: number | null;
  feed_run_id?: number | null;
  digest_id?: number | null;
  provider: string;
  model: string;
  tokens_in: number;
  tokens_out: number;
  cost: number;
  request_type?: string | null;
  latency_ms?: number | null;
  success: boolean;
  error_message?: string | null;
  timestamp: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// DIGEST
// ═══════════════════════════════════════════════════════════════════════════════

export interface DigestSourceItem {
  id: number;
  digest_id: number;
  source_id?: number | null;
  source_name?: string | null;
  item_url: string;
  item_title?: string | null;
  item_published_at?: string | null;
  created_at: string;
}

export interface Digest {
  id: number;
  url: string;
  title?: string | null;
  content?: string | null;
  summary?: string | null;
  source_type?: SourceType | null;
  feed_url?: string | null;
  feed_title?: string | null;
  image_url?: string | null;
  author?: string | null;
  published_at?: string | null;
  created_at: string;
  provider?: string | null;
  language?: string | null;
  estimated_cost: number;
  consolidated_count: number;
  user_id?: number | null;
  feed_run_id?: number | null;
  source_id?: number | null;
  tags: string[];
  // Token usage from LLM API
  tokens_in: number;
  tokens_out: number;
  // Relationships (when expanded)
  source?: Source;
  feed_run?: FeedRun;
  source_items?: DigestSourceItem[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// TAG
// ═══════════════════════════════════════════════════════════════════════════════

export interface Tag {
  id: number;
  name: string;
  digest_count?: number;  // Number of digests using this tag
}

export interface TagListResponse {
  tags: Tag[];
  total: number;
}

export interface TagSuggestion {
  name: string;
  digest_count: number;
}

export interface TagSuggestionsResponse {
  suggestions: TagSuggestion[];
}

export interface DigestTagsUpdate {
  tags: string[];
}

export interface TagDeleteResponse {
  deleted: boolean;
  tag_name: string;
  digests_affected: number;
}

export interface TagBulkDeleteResponse {
  deleted_count: number;
  tag_names: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENT METADATA
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Base metadata interface for all component types (providers, fetchers, exporters).
 */
export interface ComponentMetadata {
  name: string;
  display_name: string;
  description: string;
  icon: string | null;
}

/**
 * Metadata for LLM providers.
 */
export interface ProviderMetadata extends ComponentMetadata {
  is_local: boolean;
  requires_api_key: boolean;
}

/**
 * Metadata for content fetchers.
 */
export interface FetcherMetadata extends ComponentMetadata {
  url_schemes: string[];
  supports_oauth: boolean;
  oauth_providers: string[];
  supports_incremental: boolean;
  supports_validation: boolean;
  supports_test_fetch: boolean;
}

/**
 * Metadata for digest exporters.
 */
export interface ExporterMetadata extends ComponentMetadata {
  file_extension: string;
  mime_type: string;
  ui_color: string | null;
}

// ═══════════════════════════════════════════════════════════════════════════════
// PROVIDER STATUS
// ═══════════════════════════════════════════════════════════════════════════════

export type ProviderStatus = 'available' | 'configured' | 'not_configured' | 'unavailable';

/**
 * Information about an available model from a provider.
 */
export interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
  deprecated: boolean;
}

/**
 * Configuration field type for provider config schema.
 */
export type ProviderConfigFieldType = 'string' | 'boolean' | 'integer' | 'path' | 'select';

/**
 * Configuration field for provider settings.
 */
export interface ProviderConfigField {
  key: string;
  type: ProviderConfigFieldType;
  label: string;
  description: string;
  default?: unknown;
  required: boolean;
  placeholder: string;
  env_var?: string | null;
  editable: boolean;
  secret: boolean;
  options_from?: string | null;  // e.g., "models" to use models list for select options
}

/**
 * Schema describing how to configure a provider.
 */
export interface ProviderConfigSchema {
  fields: ProviderConfigField[];
  requires_api_key: boolean;
}

/**
 * Provider information including status and configuration schema.
 */
export interface Provider {
  name: string;
  description: string;
  status: ProviderStatus;
  is_local: boolean;
  models: ModelInfo[];
  config_schema: ProviderConfigSchema;
  masked_api_key?: string | null;
  is_extension: boolean;
  metadata?: ProviderMetadata | null;
}

/**
 * Response from GET /providers endpoint.
 */
export interface ProviderListResponse {
  providers: Provider[];
  fallback_chain: string[];
}

/**
 * Response from GET /providers/default endpoint.
 * Returns the first available provider from the fallback chain.
 */
export interface ResolvedProvider {
  /** The resolved provider name (first available) */
  provider: string;
  /** The default model for this provider */
  model: string | null;
  /** Whether the provider is available */
  available: boolean;
  /** Whether we fell back from first choice */
  fallback_used: boolean;
  /** Providers that were checked but unavailable */
  unavailable_providers: string[];
}

/**
 * @deprecated Use ProviderListResponse instead. Kept for backwards compatibility.
 */
export interface ProviderConfig {
  providers: Provider[];
  fallback_chain: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// ANALYTICS
// ═══════════════════════════════════════════════════════════════════════════════

export interface AnalyticsSummary {
  total_tokens_in: number;
  total_tokens_out: number;
  success_rate: number;
  total_runs: number;
  total_digests: number;
}

export interface TokensByModel {
  model: string;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  percentage: number;
}

export interface TokensByProvider {
  provider: string;
  tokens_in: number;
  tokens_out: number;
  total_tokens: number;
  percentage: number;
  models: TokensByModel[];
}

export interface TokensByFeed {
  feed_id: number;
  feed_name: string;
  run_count: number;
  digest_count: number;
  tokens_in: number;
  tokens_out: number;
}

export interface UsageOverTime {
  date: string;
  tokens_in: number;
  tokens_out: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// SETTINGS
// ═══════════════════════════════════════════════════════════════════════════════

export type SettingSource = 'database' | 'environment' | 'default';

export interface SettingValue {
  value: unknown;
  source: SettingSource;
  editable: boolean;
}

/**
 * Settings organized by category with source indicators.
 * Each setting includes its current value, source (database/environment/default),
 * and whether it can be edited via the UI.
 *
 * Categories are populated dynamically from SETTINGS_REGISTRY, allowing
 * extensions to register new categories without code changes.
 */
export interface Settings {
  categories: Record<string, Record<string, SettingValue>>;
}

/**
 * Helper type to access settings by category.
 * Usage: settings.categories.provider['api_key']
 */
export type SettingsCategory = Record<string, SettingValue>;

export interface SettingUpdate {
  key: string;
  value: unknown;
}

export interface SettingsUpdateRequest {
  settings: SettingUpdate[];
}

export interface SettingsResetRequest {
  keys: string[];
}

export interface SettingsResetResponse {
  reset: string[];
  not_found: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// EXPORTERS
// ═══════════════════════════════════════════════════════════════════════════════

export type ConfigFieldType = 'string' | 'boolean' | 'integer' | 'path';

export interface ConfigField {
  key: string;
  type: ConfigFieldType;
  label: string;
  description: string;
  default: unknown;
  required: boolean;
  placeholder: string;
}

export interface ExporterConfigSchema {
  fields: ConfigField[];
  supports_direct_export: boolean;
}

export interface Exporter {
  name: string;
  description: string;
  content_type: string;
  file_extension: string;
  supports_direct_export: boolean;
  config_schema: ExporterConfigSchema;
  // Activation state fields
  enabled: boolean;
  is_configured: boolean;
  can_enable: boolean;
  // Extension flag
  is_extension: boolean;
  // Component metadata
  metadata?: ExporterMetadata | null;
}

export interface ExporterListResponse {
  exporters: Exporter[];
}

export interface ExportToPathRequest {
  format: string;
  path?: string | null;
  digest_ids?: number[] | null;
  feed_id?: number | null;
  source_id?: number | null;
  tag?: string | null;
  search?: string | null;
}

export interface ExportToPathResponse {
  success: boolean;
  files_written: number;
  files_skipped: number;
  target_path: string;
  filenames: string[];
  errors: Array<{ file: string; error: string }>;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FETCHERS
// ═══════════════════════════════════════════════════════════════════════════════

export interface FetcherConfigSchema {
  fields: ConfigField[];
}

export interface Fetcher {
  name: string;
  description: string;
  config_schema: FetcherConfigSchema;
  enabled: boolean;
  is_configured: boolean;
  can_enable: boolean;
  is_extension: boolean;
  // Component metadata
  metadata?: FetcherMetadata | null;
}

export interface FetcherListResponse {
  fetchers: Fetcher[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// EXTENSIONS
// ═══════════════════════════════════════════════════════════════════════════════

export type ExtensionType = 'exporter' | 'fetcher' | 'provider';

export interface ExtensionMetadata {
  name: string;
  version: string;
  author: string;
  min_reconly: string;
  description: string;
  homepage: string | null;
  type: ExtensionType;
  registry_name: string;
}

export interface Extension {
  name: string;
  type: ExtensionType;
  metadata: ExtensionMetadata;
  is_extension: boolean;
  enabled: boolean;
  is_configured: boolean;
  can_enable: boolean;
  load_error: string | null;
  config_api: string | null;
}

export interface ExtensionListResponse {
  total: number;
  items: Extension[];
}

export interface ExtensionToggleRequest {
  enabled: boolean;
}

// ─────────────────────────────────────────────────────────────────────────────
// Extension Catalog (Phase 2)
// ─────────────────────────────────────────────────────────────────────────────

export type InstallSource = 'pypi' | 'github' | 'local';

export interface CatalogEntry {
  package: string;
  name: string;
  type: ExtensionType;
  description: string;
  author: string;
  version: string;
  verified: boolean;
  homepage: string | null;
  pypi_url: string | null;
  installed: boolean;
  installed_version: string | null;
  // GitHub marketplace fields
  install_source: InstallSource;
  github_url: string | null;
}

export interface CatalogResponse {
  version: string;
  extensions: CatalogEntry[];
  last_updated: string | null;
}

export interface ExtensionInstallRequest {
  package?: string;
  github_url?: string;
  upgrade?: boolean;
}

export interface ExtensionInstallResponse {
  success: boolean;
  package: string;
  version: string | null;
  error: string | null;
  requires_restart: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════════
// API RESPONSES
// ═══════════════════════════════════════════════════════════════════════════════

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

export interface BatchDeleteResponse {
  deleted_count: number;
  failed_ids: number[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════════

export interface DashboardStats {
  sources_count: number;
  feeds_count: number;
  digests_count: number;
  tokens_today: number;
  tokens_week: number;
  success_rate: number;
}

export interface DashboardInsights {
  new_today: number;
  new_this_week: number;
  total_digests: number;
  feeds_healthy: number;
  feeds_failing: number;
  last_sync_at: string | null;
  daily_counts: number[];
  change_today: number;
  change_week: number;
}

// ═══════════════════════════════════════════════════════════════════════════════
// FEED BUNDLES (Marketplace Export/Import)
// ═══════════════════════════════════════════════════════════════════════════════

export type BundleCategory = 'news' | 'finance' | 'tech' | 'science' | 'entertainment' | 'sports' | 'business' | 'other';

export interface BundleAuthor {
  name: string;
  github?: string | null;
  email?: string | null;
}

export interface BundleSource {
  name: string;
  type: SourceType;
  url: string;
  config?: Record<string, unknown> | null;
  default_language?: string | null;
  include_keywords?: string[] | null;
  exclude_keywords?: string[] | null;
  filter_mode?: FilterMode | null;
  use_regex?: boolean;
}

export interface BundlePromptTemplate {
  name: string;
  description?: string | null;
  system_prompt: string;
  user_prompt_template: string;
  language: string;
  target_length: number;
}

export interface BundleReportTemplate {
  name: string;
  description?: string | null;
  format: ReportFormat;
  template_content: string;
}

export interface BundleSchedule {
  cron: string;
  description?: string | null;
}

export interface BundleCompatibility {
  min_reconly_version?: string | null;
  required_features?: string[] | null;
}

export interface BundleMetadata {
  license?: string | null;
  homepage?: string | null;
  repository?: string | null;
}

export interface FeedBundle {
  schema_version: string;
  bundle: {
    id: string; // slug
    name: string;
    description?: string | null;
    version: string;
    author: BundleAuthor;
    category?: BundleCategory | null;
    tags?: string[] | null;
    sources: BundleSource[];
    prompt_template?: BundlePromptTemplate | null;
    report_template?: BundleReportTemplate | null;
    schedule?: BundleSchedule | null;
    output_config?: OutputConfig | null;
    digest_mode?: DigestMode;
  };
  compatibility?: BundleCompatibility;
  metadata?: BundleMetadata;
}

// Bundle export request
export interface BundleExportRequest {
  version?: string;
  category?: BundleCategory | null;
  tags?: string[] | null;
  min_reconly_version?: string | null;
  required_features?: string[] | null;
  license?: string | null;
  homepage?: string | null;
  repository?: string | null;
}

// Bundle export response
export interface BundleExportResponse {
  success: boolean;
  bundle: FeedBundle;
  filename: string;
}

// Bundle validation response
export interface BundleValidateResponse {
  is_valid: boolean;
  errors: string[];
  warnings: string[];
}

// Bundle preview types
export interface SourcePreview {
  name: string;
  url: string;
  type?: SourceType | null;
  existing_id?: number | null;
}

export interface FeedPreview {
  name: string;
  id: string;
  version: string;
  description?: string | null;
  already_exists: boolean;
}

export interface TemplatePreview {
  included: boolean;
  name?: string | null;
}

export interface SchedulePreview {
  included: boolean;
  cron?: string | null;
}

export interface SourcesPreview {
  total: number;
  new: SourcePreview[];
  existing: SourcePreview[];
}

export interface BundlePreviewResponse {
  valid: boolean;
  errors: string[];
  warnings: string[];
  feed?: FeedPreview | null;
  sources?: SourcesPreview | null;
  prompt_template?: TemplatePreview | null;
  report_template?: TemplatePreview | null;
  schedule?: SchedulePreview | null;
}

// Bundle import response
export interface BundleImportResponse {
  success: boolean;
  feed_id?: number | null;
  feed_name?: string | null;
  sources_created: number;
  prompt_template_id?: number | null;
  report_template_id?: number | null;
  errors: string[];
  warnings: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// KNOWLEDGE GRAPH
// ═══════════════════════════════════════════════════════════════════════════════

export type GraphNodeType = 'digest' | 'tag' | 'source' | 'feed';
export type GraphEdgeType = 'semantic' | 'tag' | 'source' | 'temporal';
export type GraphLayoutType = 'force' | 'hierarchical' | 'radial';
export type GraphViewMode = '2d' | '3d';

export interface GraphNodeData {
  // Common fields
  label: string;
  // Digest-specific
  title?: string | null;
  summary?: string | null;
  published_at?: string | null;
  url?: string | null;
  feed_title?: string | null;
  source_name?: string | null;
  tags?: string[];
  // Tag-specific
  count?: number;
  // Source-specific
  source_type?: SourceType | null;
  // Feed-specific
  digest_count?: number;
}

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  data: GraphNodeData;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: GraphEdgeType;
  score: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total_nodes: number;
  total_edges: number;
}

export interface GraphFilters {
  center_digest_id?: number;
  depth?: number;
  min_similarity?: number;
  include_tags?: boolean;
  relationship_types?: GraphEdgeType[];
  limit?: number;
  feed_id?: number;
  from_date?: string;
  to_date?: string;
  tags?: string[];
}

// ═══════════════════════════════════════════════════════════════════════════════
// IMAP SOURCE (Email)
// ═══════════════════════════════════════════════════════════════════════════════

export interface IMAPSourceCreate {
  name: string;
  provider: IMAPProvider;
  // Content filtering (optional)
  include_keywords?: string[] | null;
  exclude_keywords?: string[] | null;
  filter_mode?: FilterMode;
  use_regex?: boolean;
  // Email filtering
  folders?: string[];
  from_filter?: string;
  subject_filter?: string;
  // Generic IMAP only
  imap_host?: string;
  imap_port?: number;
  imap_username?: string;
  imap_password?: string;
  imap_use_ssl?: boolean;
}

export interface IMAPSourceCreateResponse {
  source: Source;
  oauth_url?: string | null;
  message: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// OAUTH
// ═══════════════════════════════════════════════════════════════════════════════

export type OAuthProvider = 'gmail' | 'outlook';

export interface OAuthProviderInfo {
  provider: OAuthProvider;
  display_name: string;
  scopes: string[];
  configured: boolean;
}

export interface OAuthProvidersResponse {
  providers: OAuthProviderInfo[];
}

export interface OAuthAuthorizeResponse {
  authorization_url: string;
  provider: OAuthProvider;
}

export interface OAuthStatusResponse {
  connected: boolean;
  provider?: OAuthProvider | null;
  expires_at?: string | null;
  needs_refresh: boolean;
  has_refresh_token: boolean;
}

export interface OAuthRevokeResponse {
  success: boolean;
  source_id: number;
  provider: OAuthProvider;
  message: string;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CHAT CONVERSATIONS AND MESSAGES
// ═══════════════════════════════════════════════════════════════════════════════

export type ChatMessageRole = 'user' | 'assistant' | 'tool_call' | 'tool_result';

export interface ToolCall {
  id: string | null;
  name: string;
  parameters: Record<string, unknown>;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  role: ChatMessageRole;
  content: string | null;
  tool_calls: ToolCall[] | null;
  tool_call_id: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  created_at: string;
}

export interface ChatConversation {
  id: number;
  user_id: number | null;
  title: string;
  model_provider: string | null;
  model_name: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatConversationDetail extends ChatConversation {
  messages: ChatMessage[];
}

export interface ChatConversationCreate {
  title?: string;
  model_provider?: string | null;
  model_name?: string | null;
}

export interface ChatConversationUpdate {
  title?: string | null;
  model_provider?: string | null;
  model_name?: string | null;
}

export interface ChatConversationList {
  total: number;
  items: ChatConversation[];
}

export interface ChatCompletionRequest {
  message: string;
  model_provider?: string | null;
  model_name?: string | null;
}

export interface ToolCallExecuted {
  id: string;
  name: string;
  parameters: Record<string, unknown>;
  success: boolean | null;
  result: unknown;
  error: string | null;
}

export interface ChatCompletionResponse {
  message: ChatMessage;
  conversation_id: number;
  tool_calls_executed: ToolCallExecuted[] | null;
}

// SSE Stream event types
export type ChatStreamEventType = 'content' | 'tool_call' | 'tool_result' | 'done' | 'error';

export interface ChatStreamContentEvent {
  content: string;
}

export interface ChatStreamToolCallEvent {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ChatStreamToolResultEvent {
  call_id: string;
  result: unknown;
  success: boolean;
  error?: string;
}

export interface ChatStreamDoneEvent {
  tokens_in: number;
  tokens_out: number;
}

export interface ChatStreamErrorEvent {
  error: string;
}

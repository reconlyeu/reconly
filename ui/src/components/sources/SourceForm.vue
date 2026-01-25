<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import * as z from 'zod';
import { useMutation, useQueryClient } from '@tanstack/vue-query';
import { sourcesApi } from '@/services/api';
import type { Source, FilterMode, SourceConfig, IMAPProvider, IMAPSourceCreate } from '@/types/entities';
import { X, Loader2, Filter, Plus, AlertCircle, ExternalLink } from 'lucide-vue-next';
import AgentSourceForm from './AgentSourceForm.vue';
import ImapSourceForm from './ImapSourceForm.vue';
import { strings } from '@/i18n/en';
import { useFetcherTypes, hasCustomForm } from '@/composables/useFetcherTypes';

interface Props {
  isOpen: boolean;
  source?: Source | null;
}

interface Emits {
  (e: 'close'): void;
  (e: 'success'): void;
  (e: 'oauth-redirect', url: string): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const queryClient = useQueryClient();

// Use dynamic fetcher types
const {
  sourceTypeOptions,
  validSourceTypes,
  isLoading: isFetchersLoading,
  getUrlPlaceholder,
} = useFetcherTypes();

// Validation schema - URL is required for types that don't have custom forms
// Type validation is dynamic based on available fetchers
const formSchema = computed(() => toTypedSchema(
  z.object({
    name: z.string().min(1, 'Name is required').max(200, 'Name is too long'),
    type: z.string().min(1, 'Please select a source type').refine(
      (val) => {
        // If fetchers are still loading, accept any non-empty value
        if (isFetchersLoading.value) return val.length > 0;
        // Otherwise validate against available types
        return validSourceTypes.value.includes(val);
      },
      { message: 'Please select a valid source type' }
    ),
    url: z.string(),
    enabled: z.boolean(),
  }).superRefine((data, ctx) => {
    // URL is required for types that don't have custom forms (agent, imap)
    if (!hasCustomForm(data.type)) {
      if (!data.url) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: 'URL is required',
          path: ['url'],
        });
      } else {
        try {
          new URL(data.url);
        } catch {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: 'Must be a valid URL',
            path: ['url'],
          });
        }
      }
    }
  })
));

// Form setup
const { defineField, handleSubmit, resetForm, errors } = useForm({
  validationSchema: formSchema,
  initialValues: {
    name: '',
    type: 'rss' as const,
    url: '',
    enabled: true,
  },
});

const [name, nameAttrs] = defineField('name');
const [type, typeAttrs] = defineField('type');
const [url, urlAttrs] = defineField('url');
const [enabled, enabledAttrs] = defineField('enabled');

// Filter fields (outside vee-validate for simplicity)
const showFilters = ref(false);
const maxItems = ref<number | null>(null);
const includeKeywords = ref<string[]>([]);
const excludeKeywords = ref<string[]>([]);
const filterMode = ref<FilterMode>('both');
const useRegex = ref(false);
const includeInput = ref('');
const excludeInput = ref('');
const regexError = ref<string | null>(null);

// Agent-specific fields
const agentConfig = ref<SourceConfig>({});
const agentPrompt = ref('');

// IMAP-specific fields
const imapProvider = ref<IMAPProvider>('gmail');
const imapConnectionId = ref<number | null>(null);
const imapFolders = ref('');
const imapFromFilter = ref('');
const imapSubjectFilter = ref('');
const imapConfig = ref<SourceConfig>({});
const oauthUrl = ref<string | null>(null);

// Validate regex pattern
const validateRegex = (pattern: string): boolean => {
  if (!useRegex.value) return true;
  try {
    new RegExp(pattern);
    return true;
  } catch {
    return false;
  }
};

// Add keyword chip
const addIncludeKeyword = () => {
  const keyword = includeInput.value.trim();
  if (keyword && !includeKeywords.value.includes(keyword)) {
    if (useRegex.value && !validateRegex(keyword)) {
      regexError.value = `Invalid regex: ${keyword}`;
      return;
    }
    includeKeywords.value.push(keyword);
    regexError.value = null;
  }
  includeInput.value = '';
};

const addExcludeKeyword = () => {
  const keyword = excludeInput.value.trim();
  if (keyword && !excludeKeywords.value.includes(keyword)) {
    if (useRegex.value && !validateRegex(keyword)) {
      regexError.value = `Invalid regex: ${keyword}`;
      return;
    }
    excludeKeywords.value.push(keyword);
    regexError.value = null;
  }
  excludeInput.value = '';
};

// Remove keyword chip
const removeIncludeKeyword = (index: number) => {
  includeKeywords.value.splice(index, 1);
};

const removeExcludeKeyword = (index: number) => {
  excludeKeywords.value.splice(index, 1);
};

// Reset filter fields
const resetFilterFields = () => {
  maxItems.value = null;
  includeKeywords.value = [];
  excludeKeywords.value = [];
  filterMode.value = 'both';
  useRegex.value = false;
  includeInput.value = '';
  excludeInput.value = '';
  regexError.value = null;
  showFilters.value = false;
  // Reset agent fields
  agentConfig.value = {};
  agentPrompt.value = '';
  // Reset IMAP fields
  imapProvider.value = 'gmail';
  imapConnectionId.value = null;
  imapFolders.value = '';
  imapFromFilter.value = '';
  imapSubjectFilter.value = '';
  imapConfig.value = {};
  oauthUrl.value = null;
};

// Watch for source prop changes (edit mode)
watch(
  () => props.source,
  (newSource) => {
    if (newSource) {
      resetForm({
        values: {
          name: newSource.name,
          type: newSource.type,
          url: newSource.url,
          enabled: newSource.enabled,
        },
      });
      // Restore filter fields
      maxItems.value = newSource.config?.max_items ?? null;
      includeKeywords.value = newSource.include_keywords || [];
      excludeKeywords.value = newSource.exclude_keywords || [];
      filterMode.value = newSource.filter_mode || 'both';
      useRegex.value = newSource.use_regex || false;
      // Show filters section if any filters are configured
      showFilters.value = !!(maxItems.value || newSource.include_keywords?.length || newSource.exclude_keywords?.length);
      // Restore agent fields
      if (newSource.type === 'agent') {
        agentConfig.value = {
          max_iterations: newSource.config?.max_iterations,
          search_provider: newSource.config?.search_provider,
          research_strategy: newSource.config?.research_strategy,
          report_format: newSource.config?.report_format,
          max_subtopics: newSource.config?.max_subtopics,
        };
        agentPrompt.value = newSource.url; // URL field stores the prompt for agent sources
      } else {
        agentConfig.value = {};
        agentPrompt.value = '';
      }
      // Restore IMAP fields
      if (newSource.type === 'imap') {
        imapProvider.value = newSource.config?.provider || 'generic';
        imapConnectionId.value = newSource.connection_id ?? null;
        imapFolders.value = newSource.config?.folders?.join(', ') || '';
        imapFromFilter.value = newSource.config?.from_filter || '';
        imapSubjectFilter.value = newSource.config?.subject_filter || '';
        imapConfig.value = newSource.config || {};
      } else {
        imapProvider.value = 'gmail';
        imapConnectionId.value = null;
        imapFolders.value = '';
        imapFromFilter.value = '';
        imapSubjectFilter.value = '';
        imapConfig.value = {};
      }
    } else {
      resetForm();
      resetFilterFields();
    }
  },
  { immediate: true }
);

const isEditMode = computed(() => !!props.source);

// Create/Update mutation
const saveMutation = useMutation({
  mutationFn: async (data: any) => {
    // Handle IMAP sources separately
    if (data.type === 'imap' && !isEditMode.value) {
      // Build IMAP-specific request
      const imapRequest: IMAPSourceCreate = {
        name: data.name,
        provider: imapProvider.value,
        folders: imapFolders.value ? imapFolders.value.split(',').map((f: string) => f.trim()).filter(Boolean) : undefined,
        from_filter: imapFromFilter.value || undefined,
        subject_filter: imapSubjectFilter.value || undefined,
        include_keywords: includeKeywords.value.length > 0 ? includeKeywords.value : undefined,
        exclude_keywords: excludeKeywords.value.length > 0 ? excludeKeywords.value : undefined,
        filter_mode: filterMode.value,
        use_regex: useRegex.value,
      };

      // Add connection_id for generic IMAP (credentials come from Connection)
      if (imapProvider.value === 'generic') {
        imapRequest.connection_id = imapConnectionId.value;
      }

      const response = await sourcesApi.createImap(imapRequest);

      // If OAuth URL is returned, store it for redirect
      if (response.oauth_url) {
        oauthUrl.value = response.oauth_url;
      }

      return response.source;
    }

    // Build config object based on source type
    let config: SourceConfig | null = null;
    if (data.type === 'agent') {
      const { max_iterations, search_provider, research_strategy, report_format, max_subtopics } = agentConfig.value;
      const hasConfig = max_iterations || search_provider || research_strategy || report_format || max_subtopics;
      config = hasConfig ? { max_iterations, search_provider, research_strategy, report_format, max_subtopics } : null;
    } else if (maxItems.value) {
      config = { max_items: maxItems.value };
    }

    // For agent sources, the prompt is stored in the URL field
    const finalUrl = data.type === 'agent' ? agentPrompt.value : data.url;

    // Add filter fields to data
    const payload = {
      ...data,
      url: finalUrl,
      config,
      include_keywords: includeKeywords.value.length > 0 ? includeKeywords.value : null,
      exclude_keywords: excludeKeywords.value.length > 0 ? excludeKeywords.value : null,
      filter_mode: filterMode.value,
      use_regex: useRegex.value,
    };
    if (isEditMode.value && props.source) {
      return await sourcesApi.update(props.source.id, payload);
    } else {
      return await sourcesApi.create(payload);
    }
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['sources'] });

    // If OAuth URL was returned, redirect to it
    if (oauthUrl.value) {
      emit('oauth-redirect', oauthUrl.value);
      window.location.href = oauthUrl.value;
      return;
    }

    emit('success');
    emit('close');
    resetForm();
    resetFilterFields();
  },
  onError: (error: any) => {
    console.error('Failed to save source:', error);
    // Mutation state will automatically reset to idle
  },
});

// Watch for modal open to reset state
// Watch both isOpen and source together to handle Vue reactivity timing
watch(
  () => [props.isOpen, props.source] as const,
  ([isOpen, source], [wasOpen]) => {
    if (isOpen && !wasOpen) {
      // Modal just opened
      saveMutation.reset();
      // Always reset first, then let the source watcher repopulate if editing
      if (!source) {
        resetForm();
        resetFilterFields();
      }
    }
  }
);

// Computed for reactive pending state
const isSaving = computed(() => saveMutation.isPending.value);

const onSubmit = handleSubmit((values) => {
  saveMutation.mutate(values);
});

const handleClose = () => {
  if (!isSaving.value) {
    emit('close');
    resetForm();
    resetFilterFields();
  }
};

// Computed to check if filters are configured
const hasFilters = computed(() => {
  return maxItems.value !== null || includeKeywords.value.length > 0 || excludeKeywords.value.length > 0;
});

// Count active filters for badge
const activeFilterCount = computed(() => {
  let count = includeKeywords.value.length + excludeKeywords.value.length;
  if (maxItems.value !== null) count++;
  return count;
});

// Dynamic URL placeholder based on type (using composable)
const urlPlaceholder = computed(() => getUrlPlaceholder(type.value));
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="isOpen"
        class="fixed inset-0 z-50 flex items-center justify-center p-4"
        @mousedown.self="handleClose"
      >
        <!-- Backdrop -->
        <div class="absolute inset-0 bg-black/80 backdrop-blur-sm" />

        <!-- Modal -->
        <div
          class="relative flex w-full max-w-lg flex-col rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface shadow-2xl shadow-black/50"
          style="max-height: 85vh;"
        >
          <!-- Decorative gradient orb -->
          <div class="absolute -right-20 -top-20 h-40 w-40 rounded-full bg-accent-primary/20 blur-3xl" />

          <!-- Header (fixed) -->
          <div class="relative flex shrink-0 items-center justify-between p-6 pb-4">
            <h2 class="text-2xl font-bold text-text-primary">
              {{ isEditMode ? strings.sources.editSource : strings.sources.form.addNewSource }}
            </h2>
            <button
              @click="handleClose"
              :disabled="isSaving"
              class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
            >
              <X :size="20" />
            </button>
          </div>

          <!-- Form (scrollable) -->
          <form @submit.prevent="onSubmit" class="relative flex-1 space-y-5 overflow-y-auto px-6">
            <!-- Name Field -->
            <div>
              <label for="name" class="mb-2 block text-sm font-medium text-text-primary">
                Name
              </label>
              <input
                id="name"
                v-model="name"
                v-bind="nameAttrs"
                type="text"
                :placeholder="strings.sources.placeholders.name"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.name
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.name" class="mt-2 text-sm text-status-failed">
                  {{ errors.name }}
                </p>
              </Transition>
            </div>

            <!-- Type Field -->
            <div>
              <label for="type" class="mb-2 block text-sm font-medium text-text-primary">
                Type
              </label>
              <!-- Loading state for fetcher types -->
              <div v-if="isFetchersLoading" class="relative">
                <select
                  id="type"
                  disabled
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-muted opacity-60"
                >
                  <option>{{ strings.common.loading }}</option>
                </select>
                <Loader2 :size="16" class="absolute right-10 top-1/2 -translate-y-1/2 animate-spin text-text-muted" />
              </div>
              <!-- Dynamic type dropdown -->
              <select
                v-else
                id="type"
                v-model="type"
                v-bind="typeAttrs"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.type
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              >
                <option
                  v-for="option in sourceTypeOptions"
                  :key="option.name"
                  :value="option.name"
                >
                  {{ option.displayName }}
                </option>
              </select>
              <Transition name="error">
                <p v-if="errors.type" class="mt-2 text-sm text-status-failed">
                  {{ errors.type }}
                </p>
              </Transition>
            </div>

            <!-- Agent Source Form (shown when type is 'agent') -->
            <AgentSourceForm
              v-if="type === 'agent'"
              v-model:config="agentConfig"
              v-model:prompt="agentPrompt"
            />

            <!-- IMAP Source Form (shown when type is 'imap') -->
            <ImapSourceForm
              v-else-if="type === 'imap'"
              v-model:config="imapConfig"
              v-model:provider="imapProvider"
              v-model:connection-id="imapConnectionId"
              v-model:folders="imapFolders"
              v-model:from-filter="imapFromFilter"
              v-model:subject-filter="imapSubjectFilter"
              :is-loading="isSaving"
              :is-edit-mode="isEditMode"
            />

            <!-- URL Field (hidden for agent and imap types) -->
            <div v-else>
              <label for="url" class="mb-2 block text-sm font-medium text-text-primary">
                URL
              </label>
              <input
                id="url"
                v-model="url"
                v-bind="urlAttrs"
                type="url"
                :placeholder="urlPlaceholder"
                class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                :class="
                  errors.url
                    ? 'border-status-failed focus:ring-status-failed'
                    : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                "
              />
              <Transition name="error">
                <p v-if="errors.url" class="mt-2 text-sm text-status-failed">
                  {{ errors.url }}
                </p>
              </Transition>
              <!-- YouTube helper text -->
              <p v-if="type === 'youtube'" class="mt-2 text-xs text-text-muted">
                {{ strings.sources.youtubeHelper }}
              </p>
            </div>

            <!-- Filters Section (hidden for agent type only) -->
            <div v-if="type !== 'agent'" class="rounded-lg border border-border-subtle bg-bg-surface">
              <!-- Toggle Header -->
              <button
                type="button"
                @click="showFilters = !showFilters"
                class="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-bg-hover"
              >
                <div class="flex items-center gap-2">
                  <Filter :size="18" class="text-text-muted" />
                  <span class="text-sm font-medium text-text-primary">{{ strings.sources.form.filters }}</span>
                  <span v-if="hasFilters" class="rounded-full bg-accent-primary/20 px-2 py-0.5 text-xs text-accent-primary">
                    {{ activeFilterCount }} {{ strings.sources.form.active }}
                  </span>
                </div>
                <span class="text-xs text-text-muted">{{ showFilters ? strings.sources.form.hide : strings.sources.form.show }}</span>
              </button>

              <!-- Filter Content -->
              <Transition name="slide">
                <div v-if="showFilters" class="border-t border-border-subtle p-4 space-y-4">
                  <!-- Max Items -->
                  <div>
                    <label class="mb-2 block text-sm font-medium text-text-primary">
                      {{ strings.sources.fields.maxItemsPerRun }}
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      {{ strings.sources.filterHints.maxItems }}
                    </p>
                    <input
                      v-model.number="maxItems"
                      type="number"
                      min="1"
                      max="100"
                      :placeholder="strings.sources.placeholders.noLimit"
                      class="w-32 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                    />
                  </div>

                  <!-- Regex Error -->
                  <div v-if="regexError" class="flex items-center gap-2 rounded-lg bg-status-failed/10 p-3 text-sm text-status-failed">
                    <AlertCircle :size="16" />
                    {{ regexError }}
                  </div>

                  <!-- Include Keywords -->
                  <div>
                    <label class="mb-2 block text-sm font-medium text-text-primary">
                      {{ strings.sources.fields.includeKeywords }}
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      {{ strings.sources.filterHints.includeKeywords }}
                    </p>
                    <div class="flex gap-2">
                      <input
                        v-model="includeInput"
                        type="text"
                        :placeholder="strings.sources.placeholders.addKeyword"
                        @keydown.enter.prevent="addIncludeKeyword"
                        class="flex-1 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                      />
                      <button
                        type="button"
                        @click="addIncludeKeyword"
                        class="rounded-lg border border-border-subtle bg-bg-base p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                      >
                        <Plus :size="18" />
                      </button>
                    </div>
                    <div v-if="includeKeywords.length" class="mt-2 flex flex-wrap gap-2">
                      <span
                        v-for="(keyword, index) in includeKeywords"
                        :key="index"
                        class="flex items-center gap-1 rounded-full bg-status-success/20 px-2.5 py-1 text-xs text-status-success"
                      >
                        {{ keyword }}
                        <button
                          type="button"
                          @click="removeIncludeKeyword(index)"
                          class="ml-1 rounded-full p-0.5 transition-colors hover:bg-status-success/30"
                        >
                          <X :size="12" />
                        </button>
                      </span>
                    </div>
                  </div>

                  <!-- Exclude Keywords -->
                  <div>
                    <label class="mb-2 block text-sm font-medium text-text-primary">
                      {{ strings.sources.fields.excludeKeywords }}
                    </label>
                    <p class="mb-2 text-xs text-text-muted">
                      {{ strings.sources.filterHints.excludeKeywords }}
                    </p>
                    <div class="flex gap-2">
                      <input
                        v-model="excludeInput"
                        type="text"
                        :placeholder="strings.sources.placeholders.addKeyword"
                        @keydown.enter.prevent="addExcludeKeyword"
                        class="flex-1 rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                      />
                      <button
                        type="button"
                        @click="addExcludeKeyword"
                        class="rounded-lg border border-border-subtle bg-bg-base p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary"
                      >
                        <Plus :size="18" />
                      </button>
                    </div>
                    <div v-if="excludeKeywords.length" class="mt-2 flex flex-wrap gap-2">
                      <span
                        v-for="(keyword, index) in excludeKeywords"
                        :key="index"
                        class="flex items-center gap-1 rounded-full bg-status-failed/20 px-2.5 py-1 text-xs text-status-failed"
                      >
                        {{ keyword }}
                        <button
                          type="button"
                          @click="removeExcludeKeyword(index)"
                          class="ml-1 rounded-full p-0.5 transition-colors hover:bg-status-failed/30"
                        >
                          <X :size="12" />
                        </button>
                      </span>
                    </div>
                  </div>

                  <!-- Filter Mode & Regex Toggle -->
                  <div class="flex gap-4">
                    <!-- Filter Mode -->
                    <div class="flex-1">
                      <label class="mb-2 block text-sm font-medium text-text-primary">
                        {{ strings.sources.fields.searchIn }}
                      </label>
                      <select
                        v-model="filterMode"
                        class="w-full rounded-lg border border-border-subtle bg-bg-base px-3 py-2 text-sm text-text-primary focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                      >
                        <option value="both">{{ strings.sources.filterModes.both }}</option>
                        <option value="title_only">{{ strings.sources.filterModes.titleOnly }}</option>
                        <option value="content">{{ strings.sources.filterModes.content }}</option>
                      </select>
                    </div>

                    <!-- Use Regex Toggle -->
                    <div class="flex items-end">
                      <button
                        type="button"
                        @click="useRegex = !useRegex"
                        class="flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors"
                        :class="useRegex
                          ? 'border-accent-primary bg-accent-primary/10 text-accent-primary'
                          : 'border-border-subtle bg-bg-base text-text-muted hover:bg-bg-hover hover:text-text-primary'"
                      >
                        <span class="font-mono text-xs">.*</span>
                        {{ strings.sources.form.regex }}
                      </button>
                    </div>
                  </div>
                </div>
              </Transition>
            </div>

            <!-- Enabled Toggle -->
            <div class="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-surface p-4">
              <div>
                <label for="enabled" class="block text-sm font-medium text-text-primary">
                  {{ strings.sources.fields.enableSource }}
                </label>
                <p class="mt-1 text-xs text-text-muted">
                  {{ strings.sources.form.disabledSourcesNotFetched }}
                </p>
              </div>
              <button
                type="button"
                @click="enabled = !enabled"
                class="relative inline-flex h-7 w-14 items-center rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                :class="enabled ? 'bg-accent-primary' : 'bg-bg-hover'"
                role="switch"
                :aria-checked="enabled"
              >
                <span
                  class="inline-block h-5 w-5 transform rounded-full bg-white shadow-lg transition-transform duration-300"
                  :class="enabled ? 'translate-x-8' : 'translate-x-1'"
                />
              </button>
            </div>

          </form>

          <!-- Actions (fixed at bottom) -->
          <div class="flex shrink-0 gap-3 border-t border-border-subtle p-6 pt-4">
            <button
              type="button"
              @click="handleClose"
              :disabled="isSaving"
              class="flex-1 rounded-lg border border-border-subtle bg-bg-surface px-6 py-3 font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50"
            >
              {{ strings.common.cancel }}
            </button>
            <button
              type="button"
              @click="onSubmit"
              :disabled="isSaving"
              class="flex-1 rounded-lg bg-accent-primary px-6 py-3 font-medium text-white transition-all hover:bg-accent-primary-hover disabled:opacity-50 flex items-center justify-center gap-2"
            >
              <Loader2
                v-if="isSaving"
                :size="18"
                class="animate-spin"
              />
              {{ isSaving ? strings.common.loading : (isEditMode ? strings.common.edit : strings.common.create) }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
/* Modal transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-active > div:last-child,
.modal-leave-active > div:last-child {
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from > div:last-child,
.modal-leave-to > div:last-child {
  transform: scale(0.95) translateY(20px);
  opacity: 0;
}

/* Error message transitions */
.error-enter-active,
.error-leave-active {
  transition: all 0.2s ease;
}

.error-enter-from,
.error-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

/* Slide transitions for filter section */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
  overflow: hidden;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>

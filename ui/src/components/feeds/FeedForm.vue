<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { feedsApi, sourcesApi, promptTemplatesApi, reportTemplatesApi, settingsApi } from '@/services/api';
import type { Feed, Exporter } from '@/types/entities';
import { X, Loader2, Search, Calendar, Mail, Webhook, FileStack, Download, AlertTriangle, HelpCircle } from 'lucide-vue-next';
import { useDirectExportCapableExporters, useEnabledDirectExportExporters } from '@/composables/useExporters';
import cronstrue from 'cronstrue';
import { strings } from '@/i18n/en';

interface Props {
  isOpen: boolean;
  feed?: Feed | null;
}

interface Emits {
  (e: 'close'): void;
  (e: 'success'): void;
}

const props = defineProps<Props>();
const emit = defineEmits<Emits>();

const queryClient = useQueryClient();

// Fetch sources for multi-select
const { data: sources } = useQuery({
  queryKey: ['sources'],
  queryFn: () => sourcesApi.list(),
  enabled: computed(() => props.isOpen),
});

// Fetch prompt templates (active only for feed selection)
const { data: promptTemplates } = useQuery({
  queryKey: ['prompt-templates', 'active'],
  queryFn: () => promptTemplatesApi.list(true),
  enabled: computed(() => props.isOpen),
});

// Fetch report templates (active only for feed selection)
const { data: reportTemplates } = useQuery({
  queryKey: ['report-templates', 'active'],
  queryFn: () => reportTemplatesApi.list(true),
  enabled: computed(() => props.isOpen),
});

// Fetch exporters that support direct export (for auto-export configuration)
// Use enabled exporters for showing available options
const { exporters: enabledExporters } = useEnabledDirectExportExporters();
// Keep all direct export exporters to check for disabled ones that were previously configured
const { exporters: allDirectExportExporters } = useDirectExportCapableExporters();

// Fetch export settings to check global paths
const { data: exportSettings } = useQuery({
  queryKey: ['settings', 'export'],
  queryFn: () => settingsApi.get('export'),
  staleTime: 30000,
  enabled: computed(() => props.isOpen),
});

// Helper to get the global path for an exporter
const getGlobalExportPath = (exporterName: string): string | null => {
  if (!exportSettings.value?.categories?.export) return null;

  // Settings are stored with exporter prefix: obsidian.vault_path, json.export_path, etc.
  // Different exporters use different path field names:
  // - Obsidian uses vault_path
  // - JSON, CSV, etc. use export_path
  if (exporterName === 'obsidian') {
    return exportSettings.value.categories.export['obsidian.vault_path']?.value as string || null;
  } else {
    return exportSettings.value.categories.export[`${exporterName}.export_path`]?.value as string || null;
  }
};

// Check if an exporter has a path configured (either global or local override)
const hasPathConfigured = (exporterName: string): boolean => {
  const localPath = autoExportConfig.value[exporterName]?.path;
  if (localPath) return true;
  return !!getGlobalExportPath(exporterName);
};

// Auto-export configuration state (not part of vee-validate form)
const autoExportConfig = ref<Record<string, { enabled: boolean; path: string }>>({});

// Initialize auto-export config when exporters are loaded
watch(allDirectExportExporters, (newExporters) => {
  if (newExporters && newExporters.length > 0) {
    // Initialize config for each exporter if not already set
    newExporters.forEach((exporter) => {
      if (!autoExportConfig.value[exporter.name]) {
        autoExportConfig.value[exporter.name] = { enabled: false, path: '' };
      }
    });
  }
}, { immediate: true });

// Get disabled exporters that have auto-export configured on this feed
const disabledConfiguredExporters = computed(() => {
  if (!allDirectExportExporters.value || !props.feed?.output_config?.exports) return [];

  const feedExports = props.feed.output_config.exports;
  return allDirectExportExporters.value.filter((exporter) => {
    // Exporter is disabled and was configured for auto-export on this feed
    return !exporter.enabled && feedExports[exporter.name]?.enabled;
  });
});

// Source search and ordering
const sourceSearch = ref('');
// Capture initial selection when modal opens (for stable sorting during editing)
const initialSelectedIds = ref<Set<number>>(new Set());

const filteredSources = computed(() => {
  if (!sources.value) return [];

  let result = [...sources.value];

  // Filter by search term if provided
  if (sourceSearch.value) {
    const search = sourceSearch.value.toLowerCase();
    result = result.filter(s =>
      s.name.toLowerCase().includes(search) ||
      s.url.toLowerCase().includes(search)
    );
  }

  // Sort: selected sources first (alphabetical), then unselected (alphabetical)
  // For editing: use initial selection for stable sorting (sources don't jump around)
  // For creating: use current selection so newly checked sources appear at top
  result.sort((a, b) => {
    const useInitial = initialSelectedIds.value.size > 0;
    const aSelected = useInitial
      ? initialSelectedIds.value.has(a.id)
      : source_ids.value.includes(a.id);
    const bSelected = useInitial
      ? initialSelectedIds.value.has(b.id)
      : source_ids.value.includes(b.id);

    // Selected sources come first
    if (aSelected && !bSelected) return -1;
    if (!aSelected && bSelected) return 1;

    // Within same group, sort alphabetically by name
    return a.name.localeCompare(b.name);
  });

  return result;
});

// Track selected disabled sources to show warning
const selectedDisabledSources = computed(() => {
  if (!sources.value) return [];
  return sources.value.filter(s =>
    source_ids.value.includes(s.id) && s.enabled === false
  );
});

// Digest mode options - use computed for i18n
const digestModeOptions = computed(() => [
  { value: 'individual', label: strings.feeds.digestMode.individual, description: strings.feeds.digestMode.individualDescription },
  { value: 'per_source', label: strings.feeds.digestMode.perSource, description: strings.feeds.digestMode.perSourceDescription },
  { value: 'all_sources', label: strings.feeds.digestMode.allSources, description: strings.feeds.digestMode.allSourcesDescription },
]);

// Validation schema
const formSchema = toTypedSchema(
  z.object({
    name: z.string().min(1, 'Name is required').max(200, 'Name is too long'),
    description: z.string().max(500, 'Description is too long').optional(),
    digest_mode: z.enum(['individual', 'per_source', 'all_sources']).default('individual'),
    source_ids: z.array(z.number()).min(1, 'Select at least one source'),
    prompt_template_id: z.number({ required_error: 'Select a prompt template' }),
    report_template_id: z.number({ required_error: 'Select a report template' }),
    schedule_cron: z.string().min(1, 'Schedule is required'),
    output_config: z.object({
      email_recipients: z.string().optional(),
      webhook_url: z.string().url('Invalid webhook URL').optional().or(z.literal('')),
    }),
    schedule_enabled: z.boolean(),
  })
);

const { defineField, handleSubmit, resetForm, errors, values } = useForm({
  validationSchema: formSchema,
  initialValues: {
    name: '',
    description: '',
    digest_mode: 'individual' as 'individual' | 'per_source' | 'all_sources',
    source_ids: [] as number[],
    prompt_template_id: undefined,
    report_template_id: undefined,
    schedule_cron: '0 9 * * *', // Daily at 9am
    output_config: {
      email_recipients: '',
      webhook_url: '',
    },
    schedule_enabled: true,
  },
});

const [name, nameAttrs] = defineField('name');
const [description, descriptionAttrs] = defineField('description');
const [digest_mode, digestModeAttrs] = defineField('digest_mode');
const [source_ids, sourceIdsAttrs] = defineField('source_ids');
const [prompt_template_id, promptTemplateIdAttrs] = defineField('prompt_template_id');
const [report_template_id, reportTemplateIdAttrs] = defineField('report_template_id');
const [schedule_cron, scheduleCronAttrs] = defineField('schedule_cron');
const [output_config] = defineField('output_config');
const [schedule_enabled, scheduleEnabledAttrs] = defineField('schedule_enabled');

// Parse cron schedule
const scheduleHumanReadable = computed(() => {
  try {
    return cronstrue.toString(schedule_cron.value || '0 9 * * *');
  } catch (e) {
    return 'Invalid cron expression';
  }
});

// Watch for feed prop changes (edit mode)
watch(
  () => props.feed,
  (newFeed) => {
    if (newFeed) {
      resetForm({
        values: {
          name: newFeed.name,
          description: newFeed.description || '',
          digest_mode: newFeed.digest_mode || 'individual',
          source_ids: newFeed.feed_sources?.map(fs => fs.source_id) || [],
          prompt_template_id: newFeed.prompt_template_id,
          report_template_id: newFeed.report_template_id,
          schedule_cron: newFeed.schedule_cron,
          output_config: newFeed.output_config || { email_recipients: '', webhook_url: '' },
          schedule_enabled: newFeed.schedule_enabled,
        },
      });

      // Load auto-export config from feed
      const exports = newFeed.output_config?.exports || {};
      Object.keys(exports).forEach((exporterName) => {
        const config = exports[exporterName];
        autoExportConfig.value[exporterName] = {
          enabled: config?.enabled || false,
          path: config?.path || '',
        };
      });
    } else {
      resetForm();
      // Reset auto-export config
      Object.keys(autoExportConfig.value).forEach((key) => {
        autoExportConfig.value[key] = { enabled: false, path: '' };
      });
    }
  },
  { immediate: true }
);

const isEditMode = computed(() => !!props.feed);

// Toggle source selection
const toggleSource = (sourceId: number) => {
  const index = source_ids.value.indexOf(sourceId);
  if (index === -1) {
    source_ids.value.push(sourceId);
  } else {
    source_ids.value.splice(index, 1);
  }
};

const isSourceSelected = (sourceId: number) => {
  return source_ids.value.includes(sourceId);
};

// Create/Update mutation
const saveMutation = useMutation({
  mutationFn: async (data: any) => {
    if (isEditMode.value && props.feed) {
      return await feedsApi.update(props.feed.id, data);
    } else {
      return await feedsApi.create(data);
    }
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['feeds'] });
    emit('success');
    emit('close');
    resetForm();
  },
  onError: (error: any) => {
    console.error('Failed to save feed:', error);
  },
});

// Watch for modal open to reset state
// Watch both isOpen and feed together to handle Vue reactivity timing
watch(
  () => [props.isOpen, props.feed] as const,
  ([isOpen, feed], [wasOpen]) => {
    if (isOpen && !wasOpen) {
      // Modal just opened
      saveMutation.reset();
      sourceSearch.value = '';

      // Capture initial selection for stable sorting (selected sources stay on top during editing)
      const currentIds = feed?.feed_sources?.map(fs => fs.source_id) || [];
      initialSelectedIds.value = new Set(currentIds);

      // Force form reset when opening in create mode (feed is null)
      // This ensures fresh fields even if modal was previously used for editing
      if (!feed) {
        resetForm();
        // Reset auto-export config
        Object.keys(autoExportConfig.value).forEach((key) => {
          autoExportConfig.value[key] = { enabled: false, path: '' };
        });
      }
    }
  }
);

// Computed for reactive pending state
const isSaving = computed(() => saveMutation.isPending.value);

const onSubmit = handleSubmit((values) => {
  // Build exports object from auto-export config
  const exports: Record<string, { enabled: boolean; path?: string }> = {};
  Object.entries(autoExportConfig.value).forEach(([exporterName, config]) => {
    if (config.enabled || config.path) {
      exports[exporterName] = {
        enabled: config.enabled,
        ...(config.path ? { path: config.path } : {}),
      };
    }
  });

  // Merge exports into output_config
  const outputConfig = {
    ...values.output_config,
    ...(Object.keys(exports).length > 0 ? { exports } : {}),
  };

  saveMutation.mutate({
    ...values,
    output_config: outputConfig,
  });
});

const handleClose = () => {
  if (!isSaving.value) {
    emit('close');
    resetForm();
    sourceSearch.value = '';
  }
};
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
          class="relative w-full max-w-3xl max-h-[90vh] overflow-y-auto rounded-2xl border border-border-default bg-gradient-to-br from-bg-elevated to-bg-surface shadow-2xl shadow-black/50"
        >
          <!-- Decorative gradient orb -->
          <div class="pointer-events-none absolute -right-20 -top-20 h-40 w-40 rounded-full bg-accent-primary/20 blur-3xl" />

          <!-- Sticky Header -->
          <div class="sticky top-0 z-10 border-b border-border-subtle bg-bg-elevated/95 backdrop-blur-sm p-6">
            <div class="flex items-center justify-between">
              <h2 class="text-2xl font-bold text-text-primary">
                {{ isEditMode ? strings.feeds.editFeed : strings.feeds.createNewFeed }}
              </h2>
              <button
                @click="handleClose"
                :disabled="isSaving"
                class="rounded-lg p-2 text-text-muted transition-colors hover:bg-bg-hover hover:text-text-primary disabled:opacity-50"
              >
                <X :size="20" />
              </button>
            </div>
          </div>

          <!-- Form -->
          <form @submit.prevent="onSubmit" class="p-6 space-y-8">
            <!-- Section 1: Basic Info -->
            <div class="space-y-4">
              <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.basicInformation }}</h3>

              <!-- Name -->
              <div>
                <label for="name" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.feeds.fields.feedName }}
                </label>
                <input
                  id="name"
                  v-model="name"
                  v-bind="nameAttrs"
                  type="text"
                  :placeholder="strings.feeds.placeholders.name"
                  class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                  :class="
                    errors.name
                      ? 'border-status-failed focus:ring-status-failed'
                      : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                  "
                />
                <Transition name="error">
                  <p v-if="errors.name" class="mt-2 text-sm text-status-failed">{{ errors.name }}</p>
                </Transition>
              </div>

              <!-- Description -->
              <div>
                <label for="description" class="mb-2 block text-sm font-medium text-text-primary">
                  Description <span class="text-text-muted">(optional)</span>
                </label>
                <textarea
                  id="description"
                  v-model="description"
                  v-bind="descriptionAttrs"
                  rows="3"
                  :placeholder="strings.feeds.placeholders.description"
                  class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all resize-none"
                  :class="
                    errors.description
                      ? 'border-status-failed focus:ring-status-failed'
                      : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                  "
                />
                <Transition name="error">
                  <p v-if="errors.description" class="mt-2 text-sm text-status-failed">{{ errors.description }}</p>
                </Transition>
              </div>

              <!-- Digest Mode -->
              <div>
                <div class="flex items-center gap-2 mb-3">
                  <FileStack :size="16" class="text-text-muted" />
                  <label class="text-sm font-medium text-text-primary">
                    {{ strings.feeds.digestMode.title }}
                  </label>
                </div>
                <div class="grid grid-cols-3 gap-3">
                  <label
                    v-for="option in digestModeOptions"
                    :key="option.value"
                    class="relative flex cursor-pointer rounded-lg border p-4 transition-all"
                    :class="digest_mode === option.value
                      ? 'border-accent-primary bg-accent-primary/5 ring-2 ring-accent-primary'
                      : 'border-border-subtle bg-bg-surface hover:border-border-default hover:bg-bg-hover'"
                  >
                    <input
                      type="radio"
                      :value="option.value"
                      v-model="digest_mode"
                      class="sr-only"
                    />
                    <div class="flex flex-col">
                      <span class="text-sm font-medium text-text-primary">{{ option.label }}</span>
                      <span class="text-xs text-text-muted mt-1">{{ option.description }}</span>
                    </div>
                    <div
                      v-if="digest_mode === option.value"
                      class="absolute right-2 top-2 h-3 w-3 rounded-full bg-accent-primary"
                    />
                  </label>
                </div>
                <p class="mt-3 text-xs text-text-muted" v-html="strings.feeds.digestMode.explanation"></p>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-border-subtle" />

            <!-- Section 2: Sources -->
            <div class="space-y-4">
              <div class="flex items-center justify-between">
                <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.selectSources }}</h3>
                <span class="text-sm text-text-secondary">
                  {{ source_ids.length }} {{ strings.feeds.sourceSelection.selected.replace('{count}', '') }}
                </span>
              </div>

              <!-- Search -->
              <div class="relative">
                <Search class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
                <input
                  v-model="sourceSearch"
                  type="search"
                  :placeholder="strings.feeds.placeholders.searchSources"
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                />
              </div>

              <!-- Source Checkboxes -->
              <div class="max-h-60 overflow-y-auto space-y-2 rounded-lg border border-border-subtle bg-bg-surface p-4">
                <label
                  v-for="source in filteredSources"
                  :key="source.id"
                  class="flex items-center gap-3 rounded-lg p-3 transition-colors hover:bg-bg-hover cursor-pointer"
                  :class="{ 'opacity-60': source.enabled === false }"
                >
                  <input
                    type="checkbox"
                    :checked="isSourceSelected(source.id)"
                    @change="toggleSource(source.id)"
                    class="h-4 w-4 rounded border-border-default bg-bg-elevated text-accent-primary focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                  />
                  <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2">
                      <span class="text-sm font-medium text-text-primary">{{ source.name }}</span>
                      <span
                        v-if="source.enabled === false"
                        class="text-xs font-medium px-1.5 py-0.5 rounded bg-text-muted/20 text-text-muted"
                      >
                        {{ strings.feeds.sourceSelection.disabled }}
                      </span>
                    </div>
                    <div class="text-xs text-text-muted truncate">{{ source.url }}</div>
                  </div>
                  <span
                    class="text-xs font-medium px-2 py-1 rounded-full"
                    :class="{
                      'bg-orange-400/10 text-orange-400': source.type === 'rss',
                      'bg-red-500/10 text-red-500': source.type === 'youtube',
                      'bg-blue-400/10 text-blue-400': source.type === 'website',
                      'bg-green-400/10 text-green-400': source.type === 'blog',
                    }"
                  >
                    {{ source.type }}
                  </span>
                </label>

                <div v-if="filteredSources?.length === 0" class="py-8 text-center text-sm text-text-muted">
                  {{ strings.feeds.sourceSelection.noSourcesFound }}
                </div>
              </div>

              <!-- Warning for disabled sources selected -->
              <Transition name="error">
                <div
                  v-if="selectedDisabledSources.length > 0"
                  class="mt-2 flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3"
                >
                  <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
                  <p class="text-xs text-amber-200">
                    {{ strings.feeds.sourceSelection.disabledSourcesWarning.replace('{count}', String(selectedDisabledSources.length)) }}
                  </p>
                </div>
              </Transition>

              <Transition name="error">
                <p v-if="errors.source_ids" class="mt-2 text-sm text-status-failed">{{ errors.source_ids }}</p>
              </Transition>
            </div>

            <!-- Divider -->
            <div class="border-t border-border-subtle" />

            <!-- Section 3: Templates -->
            <div class="grid gap-6 md:grid-cols-2">
              <!-- Prompt Template -->
              <div>
                <label for="prompt_template" class="mb-2 block text-sm font-medium text-text-primary">
                  Prompt Template
                </label>
                <select
                  id="prompt_template"
                  v-model="prompt_template_id"
                  v-bind="promptTemplateIdAttrs"
                  class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                  :class="
                    errors.prompt_template_id
                      ? 'border-status-failed focus:ring-status-failed'
                      : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                  "
                >
                  <option :value="undefined" disabled>{{ strings.feeds.templateOptions.selectTemplate }}</option>
                  <optgroup v-if="promptTemplates?.some(t => t.is_system)" :label="strings.feeds.templateOptions.systemTemplates">
                    <option v-for="t in promptTemplates?.filter(t => t.is_system)" :key="t.id" :value="t.id">
                      {{ t.name }}
                    </option>
                  </optgroup>
                  <optgroup v-if="promptTemplates?.some(t => !t.is_system)" :label="strings.feeds.templateOptions.userTemplates">
                    <option v-for="t in promptTemplates?.filter(t => !t.is_system)" :key="t.id" :value="t.id">
                      {{ t.name }}
                    </option>
                  </optgroup>
                </select>
                <Transition name="error">
                  <p v-if="errors.prompt_template_id" class="mt-2 text-sm text-status-failed">{{ errors.prompt_template_id }}</p>
                </Transition>
              </div>

              <!-- Report Template -->
              <div>
                <label for="report_template" class="mb-2 block text-sm font-medium text-text-primary">
                  Report Template
                </label>
                <select
                  id="report_template"
                  v-model="report_template_id"
                  v-bind="reportTemplateIdAttrs"
                  class="w-full rounded-lg border bg-bg-surface px-4 py-3 text-text-primary focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                  :class="
                    errors.report_template_id
                      ? 'border-status-failed focus:ring-status-failed'
                      : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                  "
                >
                  <option :value="undefined" disabled>{{ strings.feeds.templateOptions.selectTemplate }}</option>
                  <optgroup v-if="reportTemplates?.some(t => t.is_system)" :label="strings.feeds.templateOptions.systemTemplates">
                    <option v-for="t in reportTemplates?.filter(t => t.is_system)" :key="t.id" :value="t.id">
                      {{ t.name }}
                    </option>
                  </optgroup>
                  <optgroup v-if="reportTemplates?.some(t => !t.is_system)" :label="strings.feeds.templateOptions.userTemplates">
                    <option v-for="t in reportTemplates?.filter(t => !t.is_system)" :key="t.id" :value="t.id">
                      {{ t.name }}
                    </option>
                  </optgroup>
                </select>
                <Transition name="error">
                  <p v-if="errors.report_template_id" class="mt-2 text-sm text-status-failed">{{ errors.report_template_id }}</p>
                </Transition>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-border-subtle" />

            <!-- Section 4: Schedule -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <Calendar :size="16" class="text-text-muted" />
                <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.schedule }}</h3>
              </div>

              <div>
                <label for="schedule" class="mb-2 flex items-center gap-2 text-sm font-medium text-text-primary">
                  {{ strings.feeds.fields.cronExpression }}
                  <div class="group relative">
                    <HelpCircle :size="14" class="text-text-muted cursor-help hover:text-text-secondary" />
                    <div class="pointer-events-none absolute left-1/2 bottom-full mb-2 -translate-x-1/2 opacity-0 transition-opacity group-hover:opacity-100 z-50">
                      <div class="w-64 rounded-lg border border-border-subtle bg-bg-elevated p-3 shadow-xl text-xs">
                        <div class="font-semibold text-text-primary mb-2">{{ strings.feeds.cronHelp.title }}</div>
                        <code class="block bg-bg-surface rounded px-2 py-1 mb-2 text-text-secondary font-mono">
                          {{ strings.feeds.cronHelp.syntax }}
                        </code>
                        <div class="space-y-1 text-text-muted">
                          <div><code class="text-accent-primary">0 9 * * *</code> {{ strings.feeds.cronHelp.examples.daily9am }}</div>
                          <div><code class="text-accent-primary">0 8 * * 1-5</code> {{ strings.feeds.cronHelp.examples.weekdays8am }}</div>
                          <div><code class="text-accent-primary">0 */6 * * *</code> {{ strings.feeds.cronHelp.examples.every6hours }}</div>
                          <div><code class="text-accent-primary">30 7 * * 1</code> {{ strings.feeds.cronHelp.examples.monday730am }}</div>
                        </div>
                      </div>
                      <div class="absolute left-1/2 -translate-x-1/2 -bottom-1 h-2 w-2 rotate-45 border-b border-r border-border-subtle bg-bg-elevated"></div>
                    </div>
                  </div>
                </label>
                <input
                  id="schedule"
                  v-model="schedule_cron"
                  v-bind="scheduleCronAttrs"
                  type="text"
                  :placeholder="strings.feeds.placeholders.cron"
                  class="w-full rounded-lg border bg-bg-surface px-4 py-3 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                  :class="
                    errors.schedule_cron
                      ? 'border-status-failed focus:ring-status-failed'
                      : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                  "
                />
                <p class="mt-2 text-sm text-text-secondary">
                  {{ scheduleHumanReadable }}
                </p>
                <Transition name="error">
                  <p v-if="errors.schedule_cron" class="mt-2 text-sm text-status-failed">{{ errors.schedule_cron }}</p>
                </Transition>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-border-subtle" />

            <!-- Section 5: Output Configuration -->
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <Mail :size="16" class="text-text-muted" />
                <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.outputConfiguration }}</h3>
              </div>

              <!-- Email Recipients -->
              <div>
                <label for="email_recipients" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.feeds.fields.emailRecipients }} <span class="text-text-muted">({{ strings.common.optional }})</span>
                </label>
                <input
                  id="email_recipients"
                  v-model="output_config.email_recipients"
                  type="text"
                  :placeholder="strings.feeds.placeholders.emailRecipients"
                  class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-3 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                />
                <p class="mt-2 text-xs text-text-muted">{{ strings.feeds.hints.commaSeparatedEmails }}</p>
              </div>

              <!-- Webhook URL -->
              <div>
                <label for="webhook_url" class="mb-2 block text-sm font-medium text-text-primary">
                  {{ strings.feeds.fields.webhookUrl }} <span class="text-text-muted">({{ strings.common.optional }})</span>
                </label>
                <div class="relative">
                  <Webhook class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" :size="18" />
                  <input
                    id="webhook_url"
                    v-model="output_config.webhook_url"
                    type="url"
                    :placeholder="strings.feeds.placeholders.webhookUrl"
                    class="w-full rounded-lg border bg-bg-surface pl-10 pr-4 py-3 text-text-primary placeholder:text-text-muted focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-base transition-all"
                    :class="
                      errors['output_config.webhook_url']
                        ? 'border-status-failed focus:ring-status-failed'
                        : 'border-border-subtle focus:border-accent-primary focus:ring-accent-primary'
                    "
                  />
                </div>
                <Transition name="error">
                  <p v-if="errors['output_config.webhook_url']" class="mt-2 text-sm text-status-failed">
                    {{ errors['output_config.webhook_url'] }}
                  </p>
                </Transition>
              </div>
            </div>

            <!-- Divider -->
            <div class="border-t border-border-subtle" />

            <!-- Section 6: Auto-Export -->
            <div v-if="allDirectExportExporters && allDirectExportExporters.length > 0" class="space-y-4">
              <div class="flex items-center gap-2">
                <Download :size="16" class="text-text-muted" />
                <h3 class="text-sm font-semibold uppercase tracking-wider text-text-muted">{{ strings.feeds.sections.autoExport }}</h3>
              </div>
              <p class="text-xs text-text-muted">
                {{ strings.feeds.autoExport.description }}
              </p>

              <!-- Warning for disabled exporters that were previously configured -->
              <div
                v-if="disabledConfiguredExporters.length > 0"
                class="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3"
              >
                <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
                <div class="text-xs text-amber-200">
                  <p class="font-medium mb-1">{{ strings.feeds.autoExport.disabledExportersWarning }}</p>
                  <ul class="list-disc list-inside">
                    <li v-for="exp in disabledConfiguredExporters" :key="exp.name">
                      {{ exp.name.charAt(0).toUpperCase() + exp.name.slice(1) }}
                    </li>
                  </ul>
                  <p class="mt-1">{{ strings.feeds.autoExport.enableInSettings }} <span class="font-medium">{{ strings.feeds.autoExport.settingsExport }}</span> {{ strings.feeds.autoExport.toUseAgain }}</p>
                </div>
              </div>

              <!-- No enabled exporters message -->
              <div
                v-if="enabledExporters.length === 0"
                class="rounded-lg border border-border-subtle bg-bg-surface p-4 text-center"
              >
                <p class="text-sm text-text-muted">
                  {{ strings.feeds.autoExport.noExportersEnabled }}
                  <span class="font-medium text-text-secondary">{{ strings.feeds.autoExport.settingsExport }}</span>
                  {{ strings.feeds.autoExport.toConfigureAutoExport }}
                </p>
              </div>

              <div v-else class="space-y-3">
                <div
                  v-for="exporter in enabledExporters"
                  :key="exporter.name"
                  class="rounded-lg border border-border-subtle bg-bg-surface p-4"
                >
                  <div class="flex items-center justify-between mb-3">
                    <div class="flex items-center gap-3">
                      <input
                        :id="`export-${exporter.name}`"
                        type="checkbox"
                        v-model="autoExportConfig[exporter.name].enabled"
                        class="h-4 w-4 rounded border-border-default bg-bg-elevated text-accent-primary focus:ring-2 focus:ring-accent-primary focus:ring-offset-2 focus:ring-offset-bg-base"
                      />
                      <label :for="`export-${exporter.name}`" class="text-sm font-medium text-text-primary cursor-pointer">
                        {{ exporter.name.charAt(0).toUpperCase() + exporter.name.slice(1) }}
                      </label>
                    </div>
                    <span class="text-xs text-text-muted">.{{ exporter.file_extension }}</span>
                  </div>
                  <p class="text-xs text-text-muted mb-3">{{ exporter.description }}</p>

                  <!-- Warning when enabled but no path configured -->
                  <Transition name="slide">
                    <div
                      v-if="autoExportConfig[exporter.name]?.enabled && !hasPathConfigured(exporter.name)"
                      class="flex items-start gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 p-3 mb-3"
                    >
                      <AlertTriangle :size="16" class="text-amber-500 flex-shrink-0 mt-0.5" />
                      <p class="text-xs text-amber-200">
                        {{ strings.feeds.autoExport.noPathWarning }}
                        <span class="font-medium">{{ strings.feeds.autoExport.settingsExport }}</span>.
                      </p>
                    </div>
                  </Transition>

                  <!-- Path override input (shown when enabled) -->
                  <Transition name="slide">
                    <div v-if="autoExportConfig[exporter.name]?.enabled" class="mt-3">
                      <label :for="`export-path-${exporter.name}`" class="mb-1 block text-xs font-medium text-text-secondary">
                        {{ strings.feeds.fields.customPath }}
                        <span v-if="getGlobalExportPath(exporter.name)" class="text-text-muted">
                          ({{ strings.feeds.autoExport.leaveEmptyForGlobal }} <span class="font-mono text-text-secondary">{{ getGlobalExportPath(exporter.name) }}</span>)
                        </span>
                        <span v-else class="text-text-muted">({{ strings.feeds.autoExport.optionalOverride }})</span>
                      </label>
                      <input
                        :id="`export-path-${exporter.name}`"
                        v-model="autoExportConfig[exporter.name].path"
                        type="text"
                        :placeholder="getGlobalExportPath(exporter.name) ? strings.feeds.placeholders.overridePath : strings.feeds.placeholders.noGlobalPath"
                        class="w-full rounded-lg border border-border-subtle bg-bg-elevated px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-1 focus:ring-accent-primary"
                      />
                    </div>
                  </Transition>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="flex gap-3 pt-4">
              <button
                type="button"
                @click="handleClose"
                :disabled="isSaving"
                class="flex-1 rounded-lg border border-border-subtle bg-bg-surface px-6 py-3 font-medium text-text-primary transition-all hover:bg-bg-hover disabled:opacity-50"
              >
                {{ strings.common.cancel }}
              </button>
              <button
                type="submit"
                :disabled="isSaving"
                class="flex-1 rounded-lg bg-accent-primary px-6 py-3 font-medium text-white transition-all hover:bg-accent-primary-hover disabled:opacity-50 flex items-center justify-center gap-2"
              >
                <Loader2
                  v-if="isSaving"
                  :size="18"
                  class="animate-spin"
                />
                {{ isSaving ? strings.feeds.actions.saving : (isEditMode ? strings.feeds.actions.updateFeed : strings.feeds.createFeed) }}
              </button>
            </div>
          </form>
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

/* Slide transition for auto-export path input */
.slide-enter-active,
.slide-leave-active {
  transition: all 0.2s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-8px);
}

.slide-enter-to,
.slide-leave-from {
  opacity: 1;
  max-height: 100px;
}

/* Custom scrollbar */
.overflow-y-auto::-webkit-scrollbar {
  width: 8px;
}

.overflow-y-auto::-webkit-scrollbar-track {
  background: var(--color-bg-surface);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb {
  background: var(--color-bg-hover);
  border-radius: 4px;
}

.overflow-y-auto::-webkit-scrollbar-thumb:hover {
  background: var(--color-border-default);
}
</style>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useForm } from 'vee-validate';
import { toTypedSchema } from '@vee-validate/zod';
import * as z from 'zod';
import { useMutation, useQuery, useQueryClient } from '@tanstack/vue-query';
import { feedsApi, sourcesApi, promptTemplatesApi, reportTemplatesApi, settingsApi } from '@/services/api';
import type { Feed, FeedCreate, FeedUpdate } from '@/types/entities';
import { X, Loader2, Calendar, FileStack, HelpCircle } from 'lucide-vue-next';
import { useDirectExportCapableExporters, useEnabledDirectExportExporters } from '@/composables/useExporters';
import cronstrue from 'cronstrue';
import { strings } from '@/i18n/en';
import FeedFormSources from './FeedFormSources.vue';
import FeedFormOutput from './FeedFormOutput.vue';

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

// Ref for source sub-component
const sourcesRef = ref();

// Create/Update mutation
const saveMutation = useMutation({
  mutationFn: async (data: FeedCreate | FeedUpdate) => {
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
  onError: (error: Error) => {
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
      sourcesRef.value?.resetSearch();

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
    sourcesRef.value?.resetSearch();
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
            <FeedFormSources
              :sources="sources || []"
              v-model:source-ids="source_ids"
              :errors="errors"
              ref="sourcesRef"
            />

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

            <!-- Sections 5+6: Output Configuration + Auto-Export -->
            <FeedFormOutput
              :enabled-exporters="enabledExporters"
              :all-direct-export-exporters="allDirectExportExporters || []"
              :disabled-configured-exporters="disabledConfiguredExporters"
              :export-settings="exportSettings"
              v-model:output-config="output_config"
              v-model:auto-export-config="autoExportConfig"
              :errors="errors"
            />

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

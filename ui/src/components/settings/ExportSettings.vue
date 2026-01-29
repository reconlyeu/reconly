<script setup lang="ts">
/**
 * Export Settings Component
 *
 * Provides UI for configuring export settings including:
 * - Default export format selection via ExporterSelector
 * - Exporter-specific configuration via ExporterConfigPanel
 * - Direct export to filesystem for supported exporters
 *
 * Supports deep-linking via useSettingsNavigation composable
 */
import { ref, watch, computed, onMounted } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { settingsApi, digestsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import { useExportersList } from '@/composables/useExporters';
import { useSettingsNavigation } from '@/composables/useSettingsNavigation';
import { strings } from '@/i18n/en';
import ExporterSelector from './ExporterSelector.vue';
import ExporterConfigPanel from './ExporterConfigPanel.vue';
import { Loader2, Save, RotateCcw, Download, Upload, Info } from 'lucide-vue-next';
import type { SettingValue, Exporter } from '@/types/entities';

// Get deep-link target from navigation composable
const { consumeExporterTarget } = useSettingsNavigation();
const deepLinkExporter = ref<string | null>(null);

// Check for deep-link target on mount
onMounted(() => {
  const target = consumeExporterTarget();
  if (target) {
    deepLinkExporter.value = target;
  }
});

const queryClient = useQueryClient();
const toast = useToast();

// Fetch exporters list
const { data: exporters } = useExportersList();

// Settings query for export category
const { data: settings, isLoading } = useQuery({
  queryKey: ['settings', 'export'],
  queryFn: () => settingsApi.get('export'),
  staleTime: 30000,
});

// Local form state for editable settings
const localSettings = ref<{
  default_format: string;
  include_metadata: boolean;
}>({
  default_format: 'json',
  include_metadata: true,
});

// Track if form has changes
const hasChanges = ref(false);

// Get the currently selected exporter
const selectedExporter = computed<Exporter | null>(() => {
  if (!exporters.value) return null;
  return exporters.value.find(e => e.name === localSettings.value.default_format) || null;
});

// Check if selected exporter supports direct export
const supportsDirectExport = computed(() => {
  return selectedExporter.value?.supports_direct_export ?? false;
});

// Check if selected exporter is enabled
const isExporterEnabled = computed(() => {
  return selectedExporter.value?.enabled ?? false;
});

// Get the configured vault/export path for the selected exporter
const configuredPath = computed(() => {
  if (!settings.value?.categories?.export || !localSettings.value.default_format) return null;

  const format = localSettings.value.default_format;

  // Use path_setting_key from exporter metadata for the correct setting key
  // Settings are stored with exporter prefix: obsidian.vault_path, json.export_path, etc.
  const pathKey = selectedExporter.value?.metadata?.path_setting_key || 'export_path';
  return settings.value.categories.export[`${format}.${pathKey}`]?.value as string || null;
});

// Update local settings when data loads
const updateLocalFromSettings = () => {
  if (settings.value?.categories?.export) {
    const e = settings.value.categories.export;
    if (e.default_format?.value !== undefined) {
      localSettings.value.default_format = String(e.default_format.value || 'json');
    }
    if (e.include_metadata?.value !== undefined) {
      localSettings.value.include_metadata = Boolean(e.include_metadata.value);
    }
    hasChanges.value = false;
  }
};

// Watch for deep-link exporter and apply when exporters list is available
watch(
  [() => exporters.value, deepLinkExporter],
  ([exportersList, targetExporter]) => {
    if (targetExporter && exportersList) {
      // Check if the target exporter exists in the list
      const exists = exportersList.some(e => e.name === targetExporter);
      if (exists) {
        localSettings.value.default_format = targetExporter;
        // Clear the deep link so we don't keep overriding
        deepLinkExporter.value = null;
      }
    }
  },
  { immediate: true }
);

// Watch for settings changes
watch(settings, () => {
  updateLocalFromSettings();
}, { immediate: true });

// Handle format change from ExporterSelector
const handleFormatChange = (format: string) => {
  localSettings.value.default_format = format;
  hasChanges.value = true;
};

// Handle metadata toggle
const handleMetadataToggle = () => {
  localSettings.value.include_metadata = !localSettings.value.include_metadata;
  hasChanges.value = true;
};

// Save mutation for basic settings
const saveMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.update({
      settings: [
        { key: 'export.default_format', value: localSettings.value.default_format },
        { key: 'export.include_metadata', value: localSettings.value.include_metadata },
      ],
    });
  },
  onSuccess: () => {
    toast.success(strings.settings.exports.settingsSaved);
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || strings.settings.failedToSave);
  },
});

// Reset mutation
const resetMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.reset({
      keys: ['export.default_format', 'export.include_metadata'],
    });
  },
  onSuccess: () => {
    toast.success(strings.settings.exports.settingsReset);
    queryClient.invalidateQueries({ queryKey: ['settings'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || strings.settings.failedToReset);
  },
});

// Direct export mutation
const exportMutation = useMutation({
  mutationFn: async () => {
    if (!configuredPath.value) {
      throw new Error('No export path configured');
    }
    return digestsApi.exportToPath({
      format: localSettings.value.default_format,
      path: configuredPath.value,
    });
  },
  onSuccess: (data) => {
    if (data.files_written > 0 || data.files_skipped > 0) {
      // Build detailed message
      const parts: string[] = [];
      if (data.files_written > 0) {
        parts.push(`${data.files_written} exported`);
      }
      if (data.files_skipped > 0) {
        parts.push(`${data.files_skipped} skipped (already exist)`);
      }
      toast.success(`${parts.join(', ')} → ${data.target_path}`);
    } else {
      toast.info(strings.settings.exports.exportEmpty);
    }
    // Show errors if any
    if (data.errors && data.errors.length > 0) {
      toast.error(`${data.errors.length} file(s) failed to export`);
    }
  },
  onError: (err: any) => {
    toast.error(err.detail || err.message || strings.settings.exports.exportError);
  },
});

// Handle direct export button click
const handleExportToPath = () => {
  exportMutation.mutate();
};

// Get export setting as SettingValue format
const getExportSetting = (key: string): SettingValue => {
  if (!settings.value?.categories?.export?.[key]) {
    return { value: null, source: 'default', editable: true };
  }
  return settings.value.categories.export[key];
};
</script>

<template>
  <div class="space-y-6">
    <!-- Export Format Selection Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
      <div class="flex items-center justify-between mb-6">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
            <Download :size="20" class="text-accent-primary" />
          </div>
          <div>
            <h2 class="text-lg font-semibold text-text-primary">{{ strings.settings.exports.defaultFormat }}</h2>
            <p class="text-sm text-text-muted">{{ strings.settings.exports.defaultFormatDescription }}</p>
          </div>
        </div>

        <!-- Source indicator -->
        <span
          v-if="getExportSetting('default_format').source !== 'default'"
          :class="[
            'text-xs px-2.5 py-1 rounded-full font-medium',
            getExportSetting('default_format').source === 'database'
              ? 'bg-blue-500/10 text-blue-400'
              : 'bg-amber-500/10 text-amber-400'
          ]"
        >
          {{ getExportSetting('default_format').source === 'database' ? strings.settings.source.saved : strings.settings.source.env }}
        </span>
      </div>

      <div v-if="isLoading" class="flex items-center justify-center py-12">
        <Loader2 :size="32" class="animate-spin text-accent-primary" />
      </div>

      <div v-else class="space-y-6">
        <!-- Exporter Selector -->
        <ExporterSelector
          :model-value="localSettings.default_format"
          @update:model-value="handleFormatChange"
        />

        <!-- Include Metadata Toggle -->
        <div class="flex items-center justify-between rounded-xl border border-border-subtle bg-bg-surface p-4">
          <div>
            <div class="text-sm font-medium text-text-primary">
              {{ strings.settings.exports.includeMetadata }}
              <span
                v-if="getExportSetting('include_metadata').source !== 'default'"
                :class="[
                  'ml-2 text-xs px-2 py-0.5 rounded-full',
                  getExportSetting('include_metadata').source === 'database'
                    ? 'bg-blue-500/10 text-blue-400'
                    : 'bg-amber-500/10 text-amber-400'
                ]"
              >
                {{ getExportSetting('include_metadata').source === 'database' ? strings.settings.source.saved : strings.settings.source.env }}
              </span>
            </div>
            <div class="text-xs text-text-muted mt-1">
              {{ strings.settings.exports.includeMetadataDescription }}
            </div>
          </div>
          <button
            type="button"
            @click="handleMetadataToggle"
            :class="[
              'relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-accent-primary/20',
              localSettings.include_metadata ? 'bg-accent-primary' : 'bg-gray-300 dark:bg-gray-600'
            ]"
          >
            <span
              :class="[
                'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                localSettings.include_metadata ? 'translate-x-6' : 'translate-x-1'
              ]"
            />
          </button>
        </div>

        <!-- Save/Reset Buttons -->
        <div class="flex justify-end gap-3 pt-4 border-t border-border-subtle">
          <button
            type="button"
            :disabled="resetMutation.isPending.value"
            @click="resetMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2 text-sm font-medium text-text-secondary hover:bg-bg-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw :size="16" />
            {{ strings.settings.resetToDefaults }}
          </button>
          <button
            type="button"
            :disabled="!hasChanges || saveMutation.isPending.value"
            @click="saveMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="saveMutation.isPending.value" :size="16" class="animate-spin" />
            <Save v-else :size="16" />
            {{ strings.settings.saveChanges }}
          </button>
        </div>
      </div>
    </div>

    <!-- Exporter Configuration Panel -->
    <ExporterConfigPanel
      v-if="selectedExporter"
      :exporter="selectedExporter"
    />

    <!-- Direct Export Card (only for exporters that support it) -->
    <div
      v-if="supportsDirectExport"
      class="rounded-2xl border border-border-subtle bg-bg-elevated p-8"
    >
      <div class="flex items-center gap-3 mb-6">
        <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-status-success/10">
          <Upload :size="20" class="text-status-success" />
        </div>
        <div>
          <h2 class="text-lg font-semibold text-text-primary">{{ selectedExporter?.name === 'obsidian' ? strings.settings.exports.exportToVault : strings.settings.exports.exportToPath }}</h2>
          <p class="text-sm text-text-muted">{{ strings.settings.exports.directExportDescription }}</p>
        </div>
      </div>

      <!-- Exporter not enabled warning -->
      <div v-if="!isExporterEnabled" class="mb-6 rounded-xl border border-red-500/20 bg-red-500/5 p-4">
        <div class="flex items-start gap-3">
          <Info :size="18" class="text-red-400 mt-0.5 flex-shrink-0" />
          <div>
            <div class="text-sm font-medium text-red-400">{{ strings.settings.exports.exporterNotEnabled }}</div>
            <div class="text-xs text-text-muted mt-1">
              {{ strings.settings.exports.enableExporterFirst }}
            </div>
          </div>
        </div>
      </div>

      <!-- No path configured warning -->
      <div v-else-if="!configuredPath" class="mb-6 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4">
        <div class="flex items-start gap-3">
          <Info :size="18" class="text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <div class="text-sm font-medium text-amber-400">{{ strings.settings.exports.noPathConfigured }}</div>
            <div class="text-xs text-text-muted mt-1">
              {{ strings.settings.exports.noPathConfiguredDescription }}
            </div>
          </div>
        </div>
      </div>

      <!-- Export button -->
      <button
        type="button"
        :disabled="!isExporterEnabled || !configuredPath || exportMutation.isPending.value"
        @click="handleExportToPath"
        class="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-status-success px-4 py-3 text-sm font-medium text-white hover:bg-status-success/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all"
      >
        <Loader2 v-if="exportMutation.isPending.value" :size="18" class="animate-spin" />
        <Upload v-else :size="18" />
        {{ exportMutation.isPending.value ? strings.settings.exports.exporting : strings.settings.exports.exportButton.replace('{name}', selectedExporter?.name === 'obsidian' ? 'Vault' : 'Path') }}
      </button>
    </div>
  </div>
</template>

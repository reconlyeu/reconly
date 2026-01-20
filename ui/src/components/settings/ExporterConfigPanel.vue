<script setup lang="ts">
/**
 * Configuration panel for a specific exporter.
 *
 * Displays configuration fields based on the exporter's config_schema.
 * Supports field types: path, boolean, string.
 * Saves configuration to settings API using `export.{exporter_name}.{field_key}` keys.
 */
import { ref, watch, computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { settingsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import ToggleSwitch from '@/components/common/ToggleSwitch.vue';
import {
  Settings,
  Loader2,
  Save,
  RotateCcw,
  FolderOpen,
  Check,
  Info,
} from 'lucide-vue-next';
import type { Exporter } from '@/types/entities';

interface Props {
  exporter: Exporter;
}

const props = defineProps<Props>();

const queryClient = useQueryClient();
const toast = useToast();

// Settings query for this exporter's config
const { data: settings, isLoading } = useQuery({
  queryKey: ['settings', 'export'],
  queryFn: () => settingsApi.get('export'),
  staleTime: 30000,
});

// Local form state
const localConfig = ref<Record<string, unknown>>({});
const hasChanges = ref(false);

// Get config fields from exporter
const configFields = computed(() => {
  return props.exporter.config_schema.fields || [];
});

// Check if exporter has any configuration
const hasConfig = computed(() => configFields.value.length > 0);

// Build setting key for a field
const getSettingKey = (fieldKey: string): string => {
  return `export.${props.exporter.name}.${fieldKey}`;
};

// Get stored value for a field from settings
const getStoredValue = (fieldKey: string): unknown => {
  if (!settings.value?.export) return null;
  // Settings API returns keys with exporter prefix: export.obsidian.vault_path -> obsidian.vault_path
  const qualifiedKey = `${props.exporter.name}.${fieldKey}`;
  return settings.value.export[qualifiedKey]?.value ?? null;
};

// Get setting source for a field
const getSettingSource = (fieldKey: string): string => {
  if (!settings.value?.export) return 'default';
  // Settings API returns keys with exporter prefix
  const qualifiedKey = `${props.exporter.name}.${fieldKey}`;
  return settings.value.export[qualifiedKey]?.source || 'default';
};

// Update local config from settings
const updateLocalFromSettings = () => {
  const newConfig: Record<string, unknown> = {};

  for (const field of configFields.value) {
    const storedValue = getStoredValue(field.key);
    if (storedValue !== null && storedValue !== undefined) {
      newConfig[field.key] = storedValue;
    } else if (field.default !== undefined) {
      newConfig[field.key] = field.default;
    } else {
      // Set type-appropriate default
      switch (field.type) {
        case 'boolean':
          newConfig[field.key] = false;
          break;
        case 'path':
        case 'string':
        default:
          newConfig[field.key] = '';
          break;
      }
    }
  }

  localConfig.value = newConfig;
  hasChanges.value = false;
};

// Watch settings and update local config
watch(settings, () => {
  updateLocalFromSettings();
}, { immediate: true });

// Watch exporter change and reset
watch(() => props.exporter.name, () => {
  updateLocalFromSettings();
});

// Handle field value change
const handleFieldChange = (fieldKey: string, value: unknown) => {
  localConfig.value[fieldKey] = value;
  hasChanges.value = true;
};

// Validate required fields
const validateConfig = (): boolean => {
  for (const field of configFields.value) {
    if (field.required) {
      const value = localConfig.value[field.key];
      if (value === null || value === undefined || value === '') {
        toast.error(`${field.label} is required`);
        return false;
      }
    }
  }
  return true;
};

// Save mutation
const saveMutation = useMutation({
  mutationFn: async () => {
    if (!validateConfig()) {
      throw new Error('Validation failed');
    }

    const settingsToUpdate = configFields.value.map((field) => ({
      key: getSettingKey(field.key),
      value: localConfig.value[field.key],
    }));

    return settingsApi.update({ settings: settingsToUpdate });
  },
  onSuccess: () => {
    toast.success(`${props.exporter.name.charAt(0).toUpperCase() + props.exporter.name.slice(1)} settings saved`);
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings'] });
    // Also invalidate exporters to refresh is_configured state
    queryClient.invalidateQueries({ queryKey: ['exporters'] });
  },
  onError: (err: any) => {
    if (err.message !== 'Validation failed') {
      toast.error(err.detail || 'Failed to save settings');
    }
  },
});

// Reset mutation
const resetMutation = useMutation({
  mutationFn: async () => {
    const keysToReset = configFields.value.map((field) => getSettingKey(field.key));
    return settingsApi.reset({ keys: keysToReset });
  },
  onSuccess: () => {
    toast.success('Settings reset to defaults');
    queryClient.invalidateQueries({ queryKey: ['settings'] });
    // Also invalidate exporters to refresh is_configured state
    queryClient.invalidateQueries({ queryKey: ['exporters'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to reset settings');
  },
});

// Get display name for the exporter
const displayName = computed(() => {
  const nameMap: Record<string, string> = {
    json: 'JSON',
    csv: 'CSV',
    obsidian: 'Obsidian',
    markdown: 'Markdown',
  };
  return nameMap[props.exporter.name] || props.exporter.name.charAt(0).toUpperCase() + props.exporter.name.slice(1);
});
</script>

<template>
  <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
    <div class="flex items-center gap-3 mb-6">
      <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10">
        <Settings :size="20" class="text-blue-400" />
      </div>
      <div>
        <h2 class="text-lg font-semibold text-text-primary">{{ displayName }} Configuration</h2>
        <p class="text-sm text-text-muted">Configure settings for the {{ displayName }} exporter</p>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <Loader2 :size="32" class="animate-spin text-accent-primary" />
    </div>

    <!-- No configuration needed -->
    <div v-else-if="!hasConfig" class="rounded-xl border border-border-subtle bg-bg-surface p-6 text-center">
      <div class="flex items-center justify-center gap-2 text-text-muted">
        <Check :size="18" class="text-status-success" />
        <span>No additional configuration needed for {{ displayName }} export.</span>
      </div>
    </div>

    <!-- Configuration fields -->
    <div v-else class="space-y-5">
      <div v-for="field in configFields" :key="field.key" class="space-y-2">
        <!-- Label with source indicator -->
        <div class="flex items-center justify-between">
          <label :for="`config-${field.key}`" class="text-sm font-medium text-text-primary">
            {{ field.label }}
            <span v-if="field.required" class="text-status-failed">*</span>
          </label>
          <span
            v-if="getSettingSource(field.key) !== 'default'"
            :class="[
              'text-xs px-2 py-0.5 rounded-full',
              getSettingSource(field.key) === 'database'
                ? 'bg-blue-500/10 text-blue-400'
                : 'bg-amber-500/10 text-amber-400'
            ]"
          >
            {{ getSettingSource(field.key) === 'database' ? 'Saved' : 'ENV' }}
          </span>
        </div>

        <!-- Path input -->
        <div v-if="field.type === 'path'" class="relative">
          <div class="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted">
            <FolderOpen :size="18" />
          </div>
          <input
            :id="`config-${field.key}`"
            type="text"
            :value="localConfig[field.key] || ''"
            :placeholder="field.placeholder || 'Enter path...'"
            @input="handleFieldChange(field.key, ($event.target as HTMLInputElement).value)"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface pl-10 pr-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20 font-mono text-sm"
          />
        </div>

        <!-- Boolean toggle -->
        <div
          v-else-if="field.type === 'boolean'"
          class="flex items-center justify-between rounded-lg border border-border-subtle bg-bg-surface p-3"
        >
          <span class="text-sm text-text-secondary">{{ field.description }}</span>
          <ToggleSwitch
            :model-value="Boolean(localConfig[field.key])"
            @update:model-value="handleFieldChange(field.key, $event)"
          />
        </div>

        <!-- String input -->
        <input
          v-else
          :id="`config-${field.key}`"
          type="text"
          :value="localConfig[field.key] || ''"
          :placeholder="field.placeholder || ''"
          @input="handleFieldChange(field.key, ($event.target as HTMLInputElement).value)"
          class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
        />

        <!-- Description (for non-boolean fields) -->
        <p v-if="field.description && field.type !== 'boolean'" class="text-xs text-text-muted">
          {{ field.description }}
        </p>
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
          Reset to Defaults
        </button>
        <button
          type="button"
          :disabled="!hasChanges || saveMutation.isPending.value"
          @click="saveMutation.mutate()"
          class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Loader2 v-if="saveMutation.isPending.value" :size="16" class="animate-spin" />
          <Save v-else :size="16" />
          Save Configuration
        </button>
      </div>
    </div>
  </div>
</template>

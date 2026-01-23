<script setup lang="ts">
/**
 * Configuration panel for a specific fetcher.
 *
 * Displays configuration fields based on the fetcher's config_schema.
 * Uses DynamicConfigForm to render fields from the schema.
 * Saves configuration to settings API using `fetch.{fetcher_name}.{field_key}` keys.
 */
import { ref, watch, computed } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { settingsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import { getFetcherSettingKey } from '@/composables/useFetchers';
import { strings } from '@/i18n/en';
import DynamicConfigForm from '@/components/common/DynamicConfigForm.vue';
import {
  Settings,
  Loader2,
  Save,
  RotateCcw,
  Check,
} from 'lucide-vue-next';
import type { Fetcher, ConfigField } from '@/types/entities';

interface Props {
  fetcher: Fetcher;
}

const props = defineProps<Props>();

const queryClient = useQueryClient();
const toast = useToast();

// Settings query for fetcher config (fetch category)
const { data: settings, isLoading } = useQuery({
  queryKey: ['settings', 'fetch'],
  queryFn: () => settingsApi.get('fetch'),
  staleTime: 30000,
});

// Local form state
const localConfig = ref<Record<string, unknown>>({});
const hasChanges = ref(false);

// Track form validity from DynamicConfigForm
const isFormValid = ref(true);

// Get config fields from fetcher
const configFields = computed(() => {
  return props.fetcher.config_schema?.fields || [];
});

// Check if fetcher has any configuration
const hasConfig = computed(() => configFields.value.length > 0);

// Build setting key for a field (using the composable helper)
const getSettingKey = (fieldKey: string): string => {
  return getFetcherSettingKey(props.fetcher.name, fieldKey);
};

// Get stored value for a field from settings
const getStoredValue = (fieldKey: string): unknown => {
  if (!settings.value?.categories?.fetch) return null;
  // Settings API returns keys with fetcher prefix: fetch.rss.timeout -> rss.timeout
  const qualifiedKey = `${props.fetcher.name}.${fieldKey}`;
  return settings.value.categories.fetch[qualifiedKey]?.value ?? null;
};

// Get setting source for a field
const getSettingSource = (fieldKey: string): string => {
  if (!settings.value?.categories?.fetch) return 'default';
  // Settings API returns keys with fetcher prefix
  const qualifiedKey = `${props.fetcher.name}.${fieldKey}`;
  return settings.value.categories.fetch[qualifiedKey]?.source || 'default';
};

// Compute enhanced schema with editable state based on settings source
const enhancedSchema = computed((): ConfigField[] => {
  return configFields.value.map((field) => ({
    ...field,
    // Mark field as non-editable if set via environment variable
    editable: getSettingSource(field.key) !== 'env',
    // Set env_var for display in DynamicConfigForm
    env_var: getSettingSource(field.key) === 'env' ? field.env_var || 'ENV' : null,
  }));
});

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
        case 'integer':
          newConfig[field.key] = 0;
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

// Watch fetcher change and reset
watch(() => props.fetcher.name, () => {
  updateLocalFromSettings();
});

// Handle form values change from DynamicConfigForm
const handleValuesChange = (newValues: Record<string, unknown>) => {
  localConfig.value = newValues;
  hasChanges.value = true;
};

// Handle validation state change from DynamicConfigForm
const handleValidationChange = (valid: boolean) => {
  isFormValid.value = valid;
};

// Save mutation
const saveMutation = useMutation({
  mutationFn: async () => {
    if (!isFormValid.value) {
      toast.error(strings.dynamicForm.validation.formInvalid);
      throw new Error('Validation failed');
    }

    const settingsToUpdate = configFields.value.map((field) => ({
      key: getSettingKey(field.key),
      value: localConfig.value[field.key],
    }));

    return settingsApi.update({ settings: settingsToUpdate });
  },
  onSuccess: () => {
    toast.success(strings.settings.fetchers.settingsSaved.replace('{name}', displayName.value));
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings'] });
    // Also invalidate fetchers to refresh is_configured state
    queryClient.invalidateQueries({ queryKey: ['fetchers'] });
  },
  onError: (err: any) => {
    if (err.message !== 'Validation failed') {
      toast.error(err.detail || strings.settings.failedToSave);
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
    toast.success(strings.settings.settingsResetToDefaults);
    queryClient.invalidateQueries({ queryKey: ['settings'] });
    // Also invalidate fetchers to refresh is_configured state
    queryClient.invalidateQueries({ queryKey: ['fetchers'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || strings.settings.failedToReset);
  },
});

// Get display name for the fetcher
const displayName = computed(() => {
  const name = props.fetcher.name;
  return name.charAt(0).toUpperCase() + name.slice(1);
});
</script>

<template>
  <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
    <div class="flex items-center gap-3 mb-6">
      <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10">
        <Settings :size="20" class="text-purple-400" />
      </div>
      <div>
        <h2 class="text-lg font-semibold text-text-primary">{{ strings.settings.exports.configuration.replace('{name}', displayName) }}</h2>
        <p class="text-sm text-text-muted">{{ strings.settings.fetchers.description }}</p>
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
        <span>{{ strings.settings.fetchers.noConfigNeeded.replace('{name}', displayName) }}</span>
      </div>
    </div>

    <!-- Configuration fields -->
    <div v-else class="space-y-5">
      <DynamicConfigForm
        :schema="enhancedSchema"
        :values="localConfig"
        @update:values="handleValuesChange"
        @validation-change="handleValidationChange"
      />

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
          :disabled="!hasChanges || !isFormValid || saveMutation.isPending.value"
          @click="saveMutation.mutate()"
          class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-4 py-2 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Loader2 v-if="saveMutation.isPending.value" :size="16" class="animate-spin" />
          <Save v-else :size="16" />
          {{ strings.settings.saveConfiguration }}
        </button>
      </div>
    </div>
  </div>
</template>

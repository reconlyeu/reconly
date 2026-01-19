<script setup lang="ts">
/**
 * Configuration panel for a specific provider.
 *
 * Displays configuration fields based on the provider's config_schema.
 * Supports field types: string, boolean, integer, path, select.
 * Special handling for 'model' field with options_from: 'models'.
 * Saves configuration to settings API using `llm.{provider}.{field}` keys.
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
  Lock,
} from 'lucide-vue-next';
import type { Provider, ProviderConfigField } from '@/types/entities';

interface Props {
  provider: Provider;
}

const props = defineProps<Props>();

const queryClient = useQueryClient();
const toast = useToast();

// Settings query for provider config
const { data: settings, isLoading } = useQuery({
  queryKey: ['settings-v2', 'provider'],
  queryFn: () => settingsApi.getV2('provider'),
  staleTime: 30000,
});

// Local form state
const localConfig = ref<Record<string, unknown>>({});

// Compute whether there are actual differences from stored settings
const hasChanges = computed(() => {
  for (const field of configFields.value) {
    const storedValue = getStoredValue(field.key);
    const currentValue = localConfig.value[field.key];

    // If stored value is null/undefined but we have a current value, it's a change
    if ((storedValue === null || storedValue === undefined) && currentValue !== null && currentValue !== undefined && currentValue !== '') {
      return true;
    }

    // If values differ, it's a change
    if (storedValue !== currentValue) {
      return true;
    }
  }
  return false;
});

// Get config fields from provider, filtering out non-editable fields
const configFields = computed(() => {
  return props.provider.config_schema?.fields.filter(f => f.editable) || [];
});

// Check if provider has any editable configuration
const hasConfig = computed(() => configFields.value.length > 0);

// Check if provider has any env-var configured fields (for info display)
const envConfiguredFields = computed(() => {
  return props.provider.config_schema?.fields.filter(f => f.env_var && !f.editable) || [];
});

// Build setting key for a field
const getSettingKey = (fieldKey: string): string => {
  return `provider.${props.provider.name}.${fieldKey}`;
};

// Get stored value for a field from settings
const getStoredValue = (fieldKey: string): unknown => {
  if (!settings.value?.provider) return null;
  // Settings API returns keys with provider prefix: provider.ollama.model -> ollama.model
  const qualifiedKey = `${props.provider.name}.${fieldKey}`;
  return settings.value.provider[qualifiedKey]?.value ?? null;
};

// Get setting source for a field
const getSettingSource = (fieldKey: string): string => {
  if (!settings.value?.provider) return 'default';
  const qualifiedKey = `${props.provider.name}.${fieldKey}`;
  return settings.value.provider[qualifiedKey]?.source || 'default';
};

// Get select options for a field
const getFieldOptions = (field: ProviderConfigField): Array<{ value: string; label: string }> => {
  if (field.options_from === 'models' && props.provider.models) {
    return props.provider.models.map(m => ({
      value: m.id,
      label: m.name,
    }));
  }
  return [];
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
        case 'integer':
          newConfig[field.key] = 0;
          break;
        case 'select':
          // For model select, use first available model
          if (field.options_from === 'models' && props.provider.models?.length) {
            const defaultModel = props.provider.models.find(m => m.is_default);
            newConfig[field.key] = defaultModel?.id || props.provider.models[0].id;
          } else {
            newConfig[field.key] = '';
          }
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
};

// Watch settings and update local config
watch(settings, () => {
  updateLocalFromSettings();
}, { immediate: true });

// Watch provider change and reset
watch(() => props.provider.name, () => {
  updateLocalFromSettings();
});

// Handle field value change
const handleFieldChange = (fieldKey: string, value: unknown) => {
  localConfig.value[fieldKey] = value;
};

// Handle integer field change
const handleIntegerChange = (fieldKey: string, event: Event) => {
  const target = event.target as HTMLInputElement;
  const value = parseInt(target.value, 10);
  localConfig.value[fieldKey] = isNaN(value) ? 0 : value;
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

    return settingsApi.updateV2({ settings: settingsToUpdate });
  },
  onSuccess: () => {
    toast.success(`${displayName.value} settings saved`);
    queryClient.invalidateQueries({ queryKey: ['settings-v2'] });
    queryClient.invalidateQueries({ queryKey: ['provider-status'] });
    queryClient.invalidateQueries({ queryKey: ['providers'] });
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
    queryClient.invalidateQueries({ queryKey: ['settings-v2'] });
    queryClient.invalidateQueries({ queryKey: ['provider-status'] });
    queryClient.invalidateQueries({ queryKey: ['providers'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to reset settings');
  },
});

// Get display name for the provider
const displayName = computed(() => {
  const name = props.provider.name;
  // Special cases for common providers
  const nameMap: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    huggingface: 'HuggingFace',
    ollama: 'Ollama',
  };
  return nameMap[name] || name.charAt(0).toUpperCase() + name.slice(1);
});
</script>

<template>
  <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-8">
    <div class="flex items-center gap-3 mb-6">
      <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-primary/10">
        <Settings :size="20" class="text-accent-primary" />
      </div>
      <div>
        <h2 class="text-lg font-semibold text-text-primary">{{ displayName }} Configuration</h2>
        <p class="text-sm text-text-muted">Configure settings for {{ displayName }}</p>
      </div>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="flex items-center justify-center py-12">
      <Loader2 :size="32" class="animate-spin text-accent-primary" />
    </div>

    <div v-else class="space-y-5">
      <!-- Environment Variables Info (for non-editable fields) -->
      <div
        v-if="envConfiguredFields.length > 0"
        class="rounded-lg border border-amber-500/20 bg-amber-500/5 p-4"
      >
        <div class="flex items-start gap-3">
          <Lock :size="18" class="text-amber-400 mt-0.5 flex-shrink-0" />
          <div>
            <p class="text-sm font-medium text-amber-400 mb-1">Environment Variables</p>
            <p class="text-xs text-text-secondary mb-2">
              The following settings are configured via environment variables and cannot be changed here:
            </p>
            <div class="flex flex-wrap gap-2">
              <code
                v-for="field in envConfiguredFields"
                :key="field.key"
                class="rounded bg-bg-hover px-2 py-1 font-mono text-xs text-text-primary"
                :title="field.description"
              >
                {{ field.env_var }}
              </code>
            </div>
          </div>
        </div>
      </div>

      <!-- No editable configuration -->
      <div v-if="!hasConfig" class="rounded-xl border border-border-subtle bg-bg-surface p-6 text-center">
        <div class="flex items-center justify-center gap-2 text-text-muted">
          <Info :size="18" class="text-blue-400" />
          <span>
            {{ provider.config_schema.requires_api_key
              ? 'Configure API key via environment variables to enable this provider.'
              : 'No additional configuration needed for this provider.'
            }}
          </span>
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

          <!-- Select input (for model dropdown or other selects) -->
          <select
            v-if="field.type === 'select'"
            :id="`config-${field.key}`"
            :value="localConfig[field.key] || ''"
            @change="handleFieldChange(field.key, ($event.target as HTMLSelectElement).value)"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
          >
            <option value="" disabled>Select {{ field.label.toLowerCase() }}...</option>
            <option
              v-for="option in getFieldOptions(field)"
              :key="option.value"
              :value="option.value"
            >
              {{ option.label }}
            </option>
          </select>

          <!-- Path input -->
          <div v-else-if="field.type === 'path'" class="relative">
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

          <!-- Integer input -->
          <input
            v-else-if="field.type === 'integer'"
            :id="`config-${field.key}`"
            type="number"
            :value="localConfig[field.key] || 0"
            :placeholder="field.placeholder || '0'"
            @input="handleIntegerChange(field.key, $event)"
            class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary placeholder:text-text-muted focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
          />

          <!-- String input (default) -->
          <input
            v-else
            :id="`config-${field.key}`"
            :type="field.secret ? 'password' : 'text'"
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
  </div>
</template>

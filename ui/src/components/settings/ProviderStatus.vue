<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { providersApi, settingsApi } from '@/services/api';
import ProviderStatusCard from './ProviderStatusCard.vue';
import { Info, Loader2, ChevronUp, ChevronDown, Save, RotateCcw, GripVertical } from 'lucide-vue-next';
import { useToast } from '@/composables/useToast';
import type { SettingsV2, SettingValue } from '@/types/entities';

const queryClient = useQueryClient();
const toast = useToast();
const refreshingProvider = ref<string | null>(null);

// Provider status query
const { data: providers, isLoading: providersLoading, isError, error } = useQuery({
  queryKey: ['provider-status'],
  queryFn: () => providersApi.getStatus(),
  staleTime: 30000,
  refetchInterval: 30000,
});

// Settings V2 query
const { data: settings, isLoading: settingsLoading } = useQuery({
  queryKey: ['settings-v2', 'provider'],
  queryFn: () => settingsApi.getV2('provider'),
  staleTime: 30000,
});

// Local form state for editable settings
const localSettings = ref<{
  default_provider: string;
  default_model: string;
  fallback_chain: string[];
}>({
  default_provider: 'ollama',
  default_model: 'llama3.2',
  fallback_chain: ['ollama', 'huggingface', 'openai', 'anthropic'],
});

// Track if form has changes
const hasChanges = ref(false);

// Available providers for dropdown
const availableProviders = computed(() => {
  if (!providers.value) return [];
  return providers.value.map(p => ({
    value: p.name,
    label: p.name.charAt(0).toUpperCase() + p.name.slice(1),
    available: p.status === 'available' || p.status === 'configured',
  }));
});

// Available models for current provider
const availableModels = computed(() => {
  if (!providers.value || !localSettings.value.default_provider) return [];
  const provider = providers.value.find(p => p.name === localSettings.value.default_provider);
  if (!provider) return [];
  // Handle both ModelInfo objects (new format) and strings (legacy format)
  return provider.models.map(m => {
    if (typeof m === 'string') {
      return { value: m, label: m };
    }
    // ModelInfo object - use id for value, name for display
    return { value: m.id, label: m.name };
  });
});

// Watch for settings changes and update local state
const updateLocalFromSettings = () => {
  if (settings.value?.provider) {
    const p = settings.value.provider;
    if (p.default_provider?.value) {
      localSettings.value.default_provider = String(p.default_provider.value);
    }
    if (p.default_model?.value) {
      localSettings.value.default_model = String(p.default_model.value);
    }
    if (p.fallback_chain?.value) {
      localSettings.value.fallback_chain = p.fallback_chain.value as string[];
    }
    hasChanges.value = false;
  }
};

// Watch settings query and update local form when data arrives
watch(settings, (newSettings) => {
  if (newSettings) {
    updateLocalFromSettings();
  }
}, { immediate: true });

// Handler for provider change
const handleProviderChange = (value: unknown) => {
  localSettings.value.default_provider = String(value);
  // Reset model to first available for this provider
  if (availableModels.value.length > 0) {
    localSettings.value.default_model = availableModels.value[0].value;
  }
  hasChanges.value = true;
};

// Handler for model change
const handleModelChange = (value: unknown) => {
  localSettings.value.default_model = String(value);
  hasChanges.value = true;
};

// Move provider up/down in fallback chain
const moveProvider = (index: number, direction: 'up' | 'down') => {
  const chain = [...localSettings.value.fallback_chain];
  const newIndex = direction === 'up' ? index - 1 : index + 1;
  if (newIndex < 0 || newIndex >= chain.length) return;
  [chain[index], chain[newIndex]] = [chain[newIndex], chain[index]];
  localSettings.value.fallback_chain = chain;
  hasChanges.value = true;
};

// Save mutation
const saveMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.updateV2({
      settings: [
        { key: 'llm.default_provider', value: localSettings.value.default_provider },
        { key: 'llm.default_model', value: localSettings.value.default_model },
        { key: 'llm.fallback_chain', value: localSettings.value.fallback_chain },
      ],
    });
  },
  onSuccess: () => {
    toast.success('Provider settings saved');
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings-v2'] });
    queryClient.invalidateQueries({ queryKey: ['provider-status'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to save settings');
  },
});

// Reset mutation
const resetMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.reset({
      keys: ['llm.default_provider', 'llm.default_model', 'llm.fallback_chain'],
    });
  },
  onSuccess: () => {
    toast.success('Settings reset to defaults');
    queryClient.invalidateQueries({ queryKey: ['settings-v2'] });
    // Re-fetch and update local
    setTimeout(() => updateLocalFromSettings(), 500);
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to reset settings');
  },
});

const handleRefresh = async (providerName: string) => {
  refreshingProvider.value = providerName;
  try {
    await queryClient.invalidateQueries({ queryKey: ['provider-status'] });
    toast.success(`${providerName} status refreshed`);
  } catch (err) {
    toast.error(`Failed to refresh ${providerName}`);
  } finally {
    refreshingProvider.value = null;
  }
};

// Get provider setting as SettingValue format
const getProviderSetting = (key: string): SettingValue => {
  if (!settings.value?.provider?.[key]) {
    return { value: null, source: 'default', editable: true };
  }
  return settings.value.provider[key];
};
</script>

<template>
  <div class="space-y-6">
    <!-- Provider Defaults Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-6">
      <h3 class="mb-6 font-semibold text-text-primary">Default Provider Settings</h3>

      <div v-if="settingsLoading" class="flex items-center justify-center py-8">
        <Loader2 :size="24" class="animate-spin text-accent-primary" />
      </div>

      <div v-else class="space-y-6">
        <!-- Default Provider -->
        <div class="grid gap-6 md:grid-cols-2">
          <div>
            <label class="mb-2 block text-sm font-medium text-text-primary">
              Default Provider
              <span
                v-if="getProviderSetting('default_provider').source !== 'default'"
                :class="[
                  'ml-2 text-xs px-2 py-0.5 rounded-full',
                  getProviderSetting('default_provider').source === 'database'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300'
                ]"
              >
                {{ getProviderSetting('default_provider').source === 'database' ? 'DB' : 'ENV' }}
              </span>
            </label>
            <select
              v-model="localSettings.default_provider"
              @change="handleProviderChange(($event.target as HTMLSelectElement).value)"
              class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
            >
              <option v-for="p in availableProviders" :key="p.value" :value="p.value">
                {{ p.label }} {{ !p.available ? '(not configured)' : '' }}
              </option>
            </select>
          </div>

          <!-- Default Model -->
          <div>
            <label class="mb-2 block text-sm font-medium text-text-primary">
              Default Model
              <span
                v-if="getProviderSetting('default_model').source !== 'default'"
                :class="[
                  'ml-2 text-xs px-2 py-0.5 rounded-full',
                  getProviderSetting('default_model').source === 'database'
                    ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300'
                    : 'bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300'
                ]"
              >
                {{ getProviderSetting('default_model').source === 'database' ? 'DB' : 'ENV' }}
              </span>
            </label>
            <select
              v-model="localSettings.default_model"
              @change="handleModelChange(($event.target as HTMLSelectElement).value)"
              class="w-full rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5 text-text-primary focus:border-accent-primary focus:outline-none focus:ring-2 focus:ring-accent-primary/20"
            >
              <option v-for="m in availableModels" :key="m.value" :value="m.value">
                {{ m.label }}
              </option>
            </select>
          </div>
        </div>

        <!-- Fallback Chain -->
        <div>
          <label class="mb-2 block text-sm font-medium text-text-primary">
            Fallback Chain
            <span class="ml-2 text-xs text-text-muted">
              (when primary provider fails)
            </span>
          </label>
          <div class="space-y-2">
            <div
              v-for="(provider, idx) in localSettings.fallback_chain"
              :key="provider"
              class="flex items-center gap-3 rounded-lg border border-border-subtle bg-bg-surface px-4 py-2.5"
            >
              <GripVertical :size="16" class="text-text-muted" />
              <span class="flex-1 text-text-primary">
                {{ idx + 1 }}. {{ provider.charAt(0).toUpperCase() + provider.slice(1) }}
              </span>
              <div class="flex gap-1">
                <button
                  type="button"
                  :disabled="idx === 0"
                  @click="moveProvider(idx, 'up')"
                  class="rounded p-1 hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Move up"
                >
                  <ChevronUp :size="16" class="text-text-secondary" />
                </button>
                <button
                  type="button"
                  :disabled="idx === localSettings.fallback_chain.length - 1"
                  @click="moveProvider(idx, 'down')"
                  class="rounded p-1 hover:bg-bg-hover disabled:opacity-30 disabled:cursor-not-allowed"
                  title="Move down"
                >
                  <ChevronDown :size="16" class="text-text-secondary" />
                </button>
              </div>
            </div>
          </div>
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
            Save Changes
          </button>
        </div>
      </div>
    </div>

    <!-- Info Banner -->
    <div class="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6">
      <div class="flex gap-4">
        <div class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl bg-blue-500/10">
          <Info :size="20" class="text-blue-400" :stroke-width="2" />
        </div>
        <div>
          <h3 class="mb-2 font-semibold text-text-primary">Provider Configuration</h3>
          <p class="text-sm leading-relaxed text-text-secondary">
            API keys must be configured via environment variables in your
            <code class="rounded bg-bg-hover px-1.5 py-0.5 font-mono text-xs text-accent-primary">.env</code>
            file. Default provider and model settings are saved to the database for runtime configuration.
          </p>
        </div>
      </div>
    </div>

    <!-- Loading State -->
    <div v-if="providersLoading" class="grid gap-6 md:grid-cols-2">
      <div
        v-for="i in 4"
        :key="i"
        class="h-72 animate-pulse rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated/50 to-bg-surface/30"
      />
    </div>

    <!-- Error State -->
    <div
      v-else-if="isError"
      class="rounded-2xl border border-status-failed/20 bg-status-failed/5 p-8 text-center"
    >
      <p class="text-sm text-status-failed">
        Failed to load provider status: {{ error?.message || 'Unknown error' }}
      </p>
    </div>

    <!-- Provider Grid -->
    <div v-else-if="providers" class="grid gap-6 md:grid-cols-2">
      <ProviderStatusCard
        v-for="(provider, index) in providers"
        :key="provider.name"
        :provider="provider"
        :is-refreshing="refreshingProvider === provider.name"
        :style="{ animationDelay: `${index * 100}ms` }"
        @refresh="handleRefresh"
      />
    </div>

    <!-- Empty State (unlikely but defensive) -->
    <div
      v-else
      class="rounded-2xl border border-dashed border-border-subtle bg-bg-surface/50 p-12 text-center"
    >
      <p class="text-sm text-text-muted">No provider information available</p>
    </div>
  </div>
</template>

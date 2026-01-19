<script setup lang="ts">
/**
 * Provider fallback chain management component.
 *
 * Features:
 * - Drag-and-drop reordering of providers
 * - Add/remove providers from the chain
 * - Selected provider configuration panel
 * - Saves chain order to `llm.fallback_chain` setting
 */
import { ref, computed, watch } from 'vue';
import { useQuery, useMutation, useQueryClient } from '@tanstack/vue-query';
import { providersApi, settingsApi } from '@/services/api';
import { useToast } from '@/composables/useToast';
import ProviderChainItem from './ProviderChainItem.vue';
import ProviderConfigPanel from './ProviderConfigPanel.vue';
import {
  Plus,
  Loader2,
  Save,
  Info,
  ChevronDown,
  AlertCircle,
} from 'lucide-vue-next';
import type { Provider } from '@/types/entities';

const queryClient = useQueryClient();
const toast = useToast();

// Provider list query
const { data: providerResponse, isLoading: providersLoading, isError, error } = useQuery({
  queryKey: ['providers'],
  queryFn: () => providersApi.getAll(),
  staleTime: 30000,
  refetchInterval: 30000,
});

// Settings query for fallback chain
const { data: settings, isLoading: settingsLoading } = useQuery({
  queryKey: ['settings-v2', 'provider'],
  queryFn: () => settingsApi.getV2('provider'),
  staleTime: 30000,
});

// Local state
const localChain = ref<string[]>([]);
const selectedProviderName = ref<string | null>(null);
const hasChanges = ref(false);
const showAddDropdown = ref(false);
const draggedIndex = ref<number | null>(null);
const dragOverIndex = ref<number | null>(null);

// Map of provider name to Provider object
const providersMap = computed(() => {
  const map = new Map<string, Provider>();
  if (providerResponse.value?.providers) {
    for (const p of providerResponse.value.providers) {
      map.set(p.name, p);
    }
  }
  return map;
});

// Providers in the chain (in order)
const chainProviders = computed(() => {
  return localChain.value
    .map(name => providersMap.value.get(name))
    .filter((p): p is Provider => p !== undefined);
});

// Providers not in the chain (for add dropdown)
const availableProviders = computed(() => {
  if (!providerResponse.value?.providers) return [];
  return providerResponse.value.providers.filter(
    p => !localChain.value.includes(p.name)
  );
});

// Currently selected provider object
const selectedProvider = computed(() => {
  if (!selectedProviderName.value) return null;
  return providersMap.value.get(selectedProviderName.value) || null;
});

// Initialize local chain from settings or API response
const initializeChain = () => {
  // First try to get from settings
  if (settings.value?.provider?.fallback_chain?.value) {
    localChain.value = [...(settings.value.provider.fallback_chain.value as string[])];
    hasChanges.value = false;
    return;
  }
  // Fall back to API response
  if (providerResponse.value?.fallback_chain) {
    localChain.value = [...providerResponse.value.fallback_chain];
    hasChanges.value = false;
    return;
  }
  // Default fallback
  if (providerResponse.value?.providers) {
    localChain.value = providerResponse.value.providers.map(p => p.name);
    hasChanges.value = false;
  }
};

// Watch for data changes
watch([settings, providerResponse], () => {
  initializeChain();
}, { immediate: true });

// Add provider to chain
const addProvider = (name: string) => {
  if (!localChain.value.includes(name)) {
    localChain.value.push(name);
    hasChanges.value = true;
  }
  showAddDropdown.value = false;
};

// Remove provider from chain
const removeProvider = (provider: Provider) => {
  const index = localChain.value.indexOf(provider.name);
  if (index !== -1) {
    localChain.value.splice(index, 1);
    hasChanges.value = true;
    // Deselect if this provider was selected
    if (selectedProviderName.value === provider.name) {
      selectedProviderName.value = null;
    }
  }
};

// Select provider for configuration
const selectProvider = (provider: Provider) => {
  selectedProviderName.value = selectedProviderName.value === provider.name ? null : provider.name;
};

// Drag and drop handlers
const handleDragStart = (event: DragEvent, provider: Provider) => {
  draggedIndex.value = localChain.value.indexOf(provider.name);
};

const handleDragEnd = () => {
  draggedIndex.value = null;
  dragOverIndex.value = null;
};

const handleDragOver = (event: DragEvent, index: number) => {
  dragOverIndex.value = index;
};

const handleDrop = (event: DragEvent, dropIndex: number) => {
  if (draggedIndex.value === null || draggedIndex.value === dropIndex) {
    return;
  }

  const chain = [...localChain.value];
  const [draggedItem] = chain.splice(draggedIndex.value, 1);
  chain.splice(dropIndex, 0, draggedItem);

  localChain.value = chain;
  hasChanges.value = true;
  draggedIndex.value = null;
  dragOverIndex.value = null;
};

// Save mutation
const saveMutation = useMutation({
  mutationFn: async () => {
    return settingsApi.updateV2({
      settings: [
        { key: 'llm.fallback_chain', value: localChain.value },
      ],
    });
  },
  onSuccess: () => {
    toast.success('Fallback chain saved');
    hasChanges.value = false;
    queryClient.invalidateQueries({ queryKey: ['settings-v2'] });
    queryClient.invalidateQueries({ queryKey: ['providers'] });
  },
  onError: (err: any) => {
    toast.error(err.detail || 'Failed to save fallback chain');
  },
});

// Close dropdown when clicking outside
const handleClickOutside = (event: MouseEvent) => {
  const target = event.target as HTMLElement;
  if (!target.closest('.add-dropdown')) {
    showAddDropdown.value = false;
  }
};

// Close dropdown on escape
const handleKeyDown = (event: KeyboardEvent) => {
  if (event.key === 'Escape') {
    showAddDropdown.value = false;
  }
};
</script>

<template>
  <div class="space-y-6" @click="handleClickOutside" @keydown="handleKeyDown">
    <!-- Fallback Chain Card -->
    <div class="rounded-2xl border border-border-subtle bg-bg-elevated p-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-4">
        <div>
          <h3 class="font-semibold text-text-primary">Fallback Chain</h3>
          <p class="text-sm text-text-muted">Drag to reorder. First available provider will be used.</p>
        </div>
        <div class="flex items-center gap-2">
          <!-- Save Button -->
          <button
            v-if="hasChanges"
            type="button"
            :disabled="saveMutation.isPending.value"
            @click="saveMutation.mutate()"
            class="inline-flex items-center gap-2 rounded-lg bg-accent-primary px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-primary/90 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Loader2 v-if="saveMutation.isPending.value" :size="14" class="animate-spin" />
            <Save v-else :size="14" />
            Save Order
          </button>

          <!-- Add Provider Button -->
          <div class="relative add-dropdown">
            <button
              type="button"
              @click.stop="showAddDropdown = !showAddDropdown"
              :disabled="availableProviders.length === 0"
              class="inline-flex items-center gap-1.5 rounded-lg border border-border-subtle bg-bg-surface px-3 py-1.5 text-sm font-medium text-text-secondary hover:bg-bg-hover hover:text-text-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus :size="14" />
              Add Provider
              <ChevronDown
                :size="14"
                class="transition-transform"
                :class="{ 'rotate-180': showAddDropdown }"
              />
            </button>

            <!-- Dropdown Menu -->
            <div
              v-if="showAddDropdown && availableProviders.length > 0"
              class="absolute right-0 top-full z-10 mt-1 min-w-48 rounded-lg border border-border-subtle bg-bg-elevated py-1 shadow-lg"
            >
              <button
                v-for="provider in availableProviders"
                :key="provider.name"
                type="button"
                @click="addProvider(provider.name)"
                class="flex w-full items-center gap-2 px-4 py-2 text-sm text-text-primary hover:bg-bg-hover"
              >
                <span class="flex-1 text-left">
                  {{ provider.name.charAt(0).toUpperCase() + provider.name.slice(1) }}
                </span>
                <span
                  class="text-xs"
                  :class="[
                    provider.status === 'available' || provider.status === 'configured'
                      ? 'text-status-success'
                      : 'text-text-muted'
                  ]"
                >
                  {{ provider.status === 'available' || provider.status === 'configured' ? 'Ready' : 'Not Ready' }}
                </span>
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- Loading State -->
      <div v-if="providersLoading || settingsLoading" class="flex items-center justify-center py-8">
        <Loader2 :size="24" class="animate-spin text-accent-primary" />
      </div>

      <!-- Error State -->
      <div v-else-if="isError" class="rounded-lg border border-status-failed/20 bg-status-failed/5 p-4">
        <div class="flex items-center gap-2 text-status-failed">
          <AlertCircle :size="18" />
          <span class="text-sm">Failed to load providers: {{ error?.message || 'Unknown error' }}</span>
        </div>
      </div>

      <!-- Empty State -->
      <div
        v-else-if="chainProviders.length === 0"
        class="rounded-lg border border-dashed border-border-subtle bg-bg-surface/50 p-8 text-center"
      >
        <p class="text-sm text-text-muted">No providers in chain. Add a provider to get started.</p>
      </div>

      <!-- Chain List -->
      <div v-else class="space-y-2">
        <ProviderChainItem
          v-for="(provider, index) in chainProviders"
          :key="provider.name"
          :provider="provider"
          :position="index + 1"
          :is-selected="selectedProviderName === provider.name"
          :is-dragging="draggedIndex === index"
          :is-drag-over="dragOverIndex === index"
          @select="selectProvider"
          @remove="removeProvider"
          @dragstart="(event) => handleDragStart(event, provider)"
          @dragend="handleDragEnd"
          @dragover="(event) => handleDragOver(event, index)"
          @drop="(event) => handleDrop(event, index)"
        />
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
            file. Click the gear icon on a provider to configure its model and other settings.
          </p>
        </div>
      </div>
    </div>

    <!-- Selected Provider Config Panel -->
    <ProviderConfigPanel
      v-if="selectedProvider"
      :provider="selectedProvider"
    />
  </div>
</template>

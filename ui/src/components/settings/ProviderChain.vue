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
  Database,
  Server,
  Cloud,
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

// Embedding settings query
const { data: embeddingSettings, isLoading: embeddingLoading } = useQuery({
  queryKey: ['settings-v2', 'embedding'],
  queryFn: () => settingsApi.getV2('embedding'),
  staleTime: 30000,
});

// Embedding configuration computed from settings
const embeddingConfig = computed(() => {
  const emb = embeddingSettings.value?.embedding;
  if (!emb) {
    return {
      provider: 'ollama',
      model: 'bge-m3',
      dimension: 1024,
      source: 'default',
    };
  }

  const provider = (emb['provider']?.value as string) || 'ollama';
  const model = (emb['model']?.value as string) || 'bge-m3';
  const source = emb['provider']?.source || 'default';

  // Dimension lookup based on known models
  const dimensionMap: Record<string, number> = {
    'bge-m3': 1024,
    'nomic-embed-text': 768,
    'mxbai-embed-large': 1024,
    'text-embedding-3-small': 1536,
    'text-embedding-3-large': 3072,
    'text-embedding-ada-002': 1536,
    'BAAI/bge-m3': 1024,
  };

  return {
    provider,
    model,
    dimension: dimensionMap[model] || 1024,
    source,
  };
});

// Check if embedding provider is available (Ollama running, or API key configured)
const embeddingStatus = computed(() => {
  const provider = embeddingConfig.value.provider;
  // For Ollama, check if any Ollama provider is available
  if (provider === 'ollama') {
    const ollamaProvider = providersMap.value.get('ollama');
    return ollamaProvider?.status === 'available' ? 'available' : 'unavailable';
  }
  // For cloud providers, assume configured if we have settings
  return 'configured';
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

// Get configured model for a provider from settings
const getConfiguredModel = (providerName: string): string | null => {
  if (!settings.value?.provider) return null;
  // Settings key format: provider.{name}.model -> stored as {name}.model after prefix strip
  const modelSetting = settings.value.provider[`${providerName}.model`];
  return (modelSetting?.value as string) || null;
};

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
    <!-- Two Column Layout: Fallback Chain + Embedding Settings -->
    <div class="grid grid-cols-1 lg:grid-cols-5 gap-6">
      <!-- Fallback Chain Card (3/5 width) -->
      <div class="lg:col-span-3 rounded-2xl border border-border-subtle bg-bg-elevated p-6">
        <!-- Header -->
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="font-semibold text-text-primary">LLM Fallback Chain</h3>
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
                Add
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
            :configured-model="getConfiguredModel(provider.name)"
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

      <!-- Embedding Settings Card (2/5 width) -->
      <div class="lg:col-span-2 rounded-2xl border border-border-subtle bg-bg-elevated p-6">
        <div class="flex items-center gap-3 mb-4">
          <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-500/10">
            <Database :size="20" class="text-purple-400" />
          </div>
          <div>
            <h3 class="font-semibold text-text-primary">Embedding</h3>
            <p class="text-sm text-text-muted">For RAG & semantic search</p>
          </div>
        </div>

        <!-- Loading State -->
        <div v-if="embeddingLoading" class="flex items-center justify-center py-6">
          <Loader2 :size="20" class="animate-spin text-accent-primary" />
        </div>

        <!-- Embedding Info -->
        <div v-else class="space-y-4">
          <!-- Provider & Model -->
          <div class="space-y-3">
            <div class="flex items-center justify-between">
              <span class="text-sm text-text-muted">Provider</span>
              <div class="flex items-center gap-2">
                <component
                  :is="embeddingConfig.provider === 'ollama' ? Server : Cloud"
                  :size="14"
                  class="text-text-muted"
                />
                <span class="text-sm font-medium text-text-primary capitalize">
                  {{ embeddingConfig.provider }}
                </span>
              </div>
            </div>

            <div class="flex items-center justify-between">
              <span class="text-sm text-text-muted">Model</span>
              <span class="text-sm font-mono text-text-primary">
                {{ embeddingConfig.model }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <span class="text-sm text-text-muted">Dimension</span>
              <span class="text-sm font-mono text-text-secondary">
                {{ embeddingConfig.dimension }}
              </span>
            </div>

            <div class="flex items-center justify-between">
              <span class="text-sm text-text-muted">Status</span>
              <div class="flex items-center gap-1.5">
                <div
                  class="h-2 w-2 rounded-full"
                  :class="embeddingStatus === 'available' ? 'bg-status-success' : embeddingStatus === 'configured' ? 'bg-blue-500' : 'bg-amber-500'"
                />
                <span class="text-sm text-text-secondary capitalize">
                  {{ embeddingStatus === 'available' ? 'Available' : embeddingStatus === 'configured' ? 'Configured' : 'Not Running' }}
                </span>
              </div>
            </div>

            <!-- Source indicator -->
            <div class="flex items-center justify-between">
              <span class="text-sm text-text-muted">Source</span>
              <span
                :class="[
                  'text-xs px-2 py-0.5 rounded-full',
                  embeddingConfig.source === 'env'
                    ? 'bg-amber-500/10 text-amber-400'
                    : embeddingConfig.source === 'database'
                    ? 'bg-blue-500/10 text-blue-400'
                    : 'bg-bg-hover text-text-muted'
                ]"
              >
                {{ embeddingConfig.source === 'env' ? 'ENV' : embeddingConfig.source === 'database' ? 'Saved' : 'Default' }}
              </span>
            </div>
          </div>

          <!-- Warning about changing embeddings -->
          <div class="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 mt-4">
            <p class="text-xs text-amber-400/90 leading-relaxed">
              Changing embedding model requires re-embedding all content. Configure via
              <code class="font-mono bg-bg-hover px-1 rounded">EMBEDDING_PROVIDER</code> and
              <code class="font-mono bg-bg-hover px-1 rounded">EMBEDDING_MODEL</code> in your .env file.
            </p>
          </div>
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
          <h3 class="mb-2 font-semibold text-text-primary">Environment Configuration</h3>
          <p class="text-sm leading-relaxed text-text-secondary">
            API keys and embedding settings must be configured via environment variables in your
            <code class="rounded bg-bg-hover px-1.5 py-0.5 font-mono text-xs text-accent-primary">.env</code>
            file. Click the gear icon on a provider to configure its default model.
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

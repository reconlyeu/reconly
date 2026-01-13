<script setup lang="ts">
import { computed } from 'vue';
import { Cpu, ExternalLink, RefreshCw } from 'lucide-vue-next';
import BaseCard from '@/components/common/BaseCard.vue';

interface ModelInfo {
  id: string;
  name: string;
  provider: string;
  is_default: boolean;
  deprecated: boolean;
}

interface Provider {
  name: string;
  type: 'local' | 'api';
  status: 'configured' | 'not_configured' | 'available' | 'unavailable' | 'error';
  models?: ModelInfo[] | string[];
  env_vars?: string[];
}

interface Props {
  provider: Provider;
  isRefreshing?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  isRefreshing: false,
});

const emit = defineEmits<{
  refresh: [providerName: string];
}>();

const handleRefresh = () => {
  emit('refresh', props.provider.name);
};

const statusConfig = computed(() => {
  const configs = {
    configured: {
      label: 'Configured',
      color: 'bg-green-500/10 text-green-400 border-green-500/20',
      dotColor: 'bg-green-500',
    },
    not_configured: {
      label: 'Not Configured',
      color: 'bg-red-500/10 text-red-400 border-red-500/20',
      dotColor: 'bg-red-500',
    },
    available: {
      label: 'Available',
      color: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
      dotColor: 'bg-blue-500',
    },
    unavailable: {
      label: 'Not Running',
      color: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
      dotColor: 'bg-amber-500',
    },
    error: {
      label: 'Error',
      color: 'bg-red-500/10 text-red-400 border-red-500/20',
      dotColor: 'bg-red-500',
    },
  };
  return configs[props.provider.status];
});

// Helper to get model display name (handles both string and ModelInfo)
const getModelDisplayName = (model: string | ModelInfo): string => {
  if (typeof model === 'string') return model;
  return model.name;
};
</script>

<template>
  <BaseCard glow-color="orange">
    <template #header>
      <div class="flex items-start justify-between">
        <div class="flex items-center gap-3">
          <!-- Provider Icon -->
          <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-bg-hover">
            <Cpu :size="20" class="text-text-muted" :stroke-width="2" />
          </div>

          <!-- Provider Info -->
          <div>
            <h3 class="text-lg font-semibold text-text-primary">{{ provider.name }}</h3>
            <p class="text-xs text-text-muted">
              {{ provider.type === 'local' ? 'Local Provider' : 'API-based Provider' }}
            </p>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <!-- Refresh Button -->
          <button
            @click="handleRefresh"
            :disabled="isRefreshing"
            class="flex h-8 w-8 items-center justify-center rounded-lg border border-border-subtle bg-bg-surface text-text-muted transition-all hover:border-border-default hover:bg-bg-hover hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            :title="isRefreshing ? 'Refreshing...' : 'Refresh models'"
          >
            <RefreshCw
              :size="14"
              :stroke-width="2"
              :class="{ 'animate-spin': isRefreshing }"
            />
          </button>

          <!-- Status Badge -->
          <div
            class="flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors"
            :class="statusConfig.color"
          >
            <div
              class="h-2 w-2 rounded-full animate-pulse"
              :class="statusConfig.dotColor"
            />
            {{ statusConfig.label }}
          </div>
        </div>
      </div>
    </template>

    <!-- Configuration Details -->
    <div class="space-y-3">
      <!-- Environment Variables -->
      <div v-if="provider.env_vars && provider.env_vars.length > 0" class="rounded-lg bg-bg-surface p-3">
        <div class="mb-2 text-xs font-medium text-text-muted">Environment Variables</div>
        <div class="flex flex-wrap gap-2">
          <code
            v-for="envVar in provider.env_vars"
            :key="envVar"
            class="rounded bg-bg-hover px-2 py-1 font-mono text-xs text-text-primary"
          >
            {{ envVar }}
          </code>
        </div>
      </div>

      <!-- Available Models -->
      <div v-if="provider.models && provider.models.length > 0" class="rounded-lg bg-bg-surface p-3">
        <div class="mb-2 text-xs font-medium text-text-muted">Available Models</div>
        <div class="flex flex-wrap gap-2">
          <span
            v-for="(model, idx) in provider.models.slice(0, 3)"
            :key="typeof model === 'string' ? model : model.id"
            class="rounded-full bg-accent-primary/10 px-2.5 py-1 text-xs text-accent-primary"
          >
            {{ getModelDisplayName(model) }}
          </span>
          <span
            v-if="provider.models.length > 3"
            class="rounded-full bg-bg-hover px-2.5 py-1 text-xs text-text-muted"
          >
            +{{ provider.models.length - 3 }} more
          </span>
        </div>
      </div>

      <!-- Not Configured Message -->
      <div v-if="provider.status === 'not_configured'" class="rounded-lg bg-red-500/5 p-3 text-xs text-red-400">
        Configure via environment variables to enable this provider
      </div>

      <!-- Unavailable Message (for local providers like Ollama) -->
      <div v-if="provider.status === 'unavailable'" class="rounded-lg bg-amber-500/5 p-3 text-xs text-amber-400">
        Service is not running. Start Ollama to use this provider.
      </div>
    </div>

    <template #footer>
      <span
        class="inline-flex items-center gap-2 text-sm font-medium text-text-muted/50 cursor-not-allowed"
        title="Documentation coming soon"
      >
        <span>View Documentation</span>
        <ExternalLink :size="14" :stroke-width="2" />
      </span>
    </template>
  </BaseCard>
</template>



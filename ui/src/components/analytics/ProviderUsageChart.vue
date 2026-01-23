<script setup lang="ts">
import { ref, computed } from 'vue';
import { useQuery } from '@tanstack/vue-query';
import { analyticsApi } from '@/services/api';
import { Loader2, ChevronRight, ChevronDown } from 'lucide-vue-next';
import type { TokensByProvider } from '@/types/entities';
import { strings } from '@/i18n/en';

interface Props {
  period: string;
}

const props = defineProps<Props>();

const { data, isLoading, isError } = useQuery({
  queryKey: ['analytics-by-provider', props.period],
  queryFn: () => analyticsApi.getTokensByProvider(props.period),
  staleTime: 60000,
});

// Track expanded providers
const expandedProviders = ref<Set<string>>(new Set());

const toggleProvider = (provider: string) => {
  if (expandedProviders.value.has(provider)) {
    expandedProviders.value.delete(provider);
  } else {
    expandedProviders.value.add(provider);
  }
  // Trigger reactivity
  expandedProviders.value = new Set(expandedProviders.value);
};

const isExpanded = (provider: string) => expandedProviders.value.has(provider);

const providerColors: Record<string, { bg: string; bar: string; text: string }> = {
  ollama: { bg: 'bg-green-500/20', bar: 'bg-green-500', text: 'text-green-400' },
  huggingface: { bg: 'bg-blue-500/20', bar: 'bg-blue-500', text: 'text-blue-400' },
  openai: { bg: 'bg-emerald-500/20', bar: 'bg-emerald-500', text: 'text-emerald-400' },
  anthropic: { bg: 'bg-orange-500/20', bar: 'bg-orange-500', text: 'text-orange-400' },
  google: { bg: 'bg-red-500/20', bar: 'bg-red-500', text: 'text-red-400' },
};

const getProviderColor = (provider: string) => {
  const key = provider.toLowerCase();
  return providerColors[key] || { bg: 'bg-purple-500/20', bar: 'bg-purple-500', text: 'text-purple-400' };
};

const totalTokens = computed(() => {
  if (!data.value) return 0;
  return data.value.reduce((sum, p) => sum + (p.total_tokens || 0), 0);
});

const chartData = computed(() => {
  if (!data.value) return [];
  return data.value.map(provider => ({
    ...provider,
    color: getProviderColor(provider.provider),
    hasModels: provider.models && provider.models.length > 1,
  }));
});
</script>

<template>
  <div class="rounded-2xl border border-border-subtle bg-gradient-to-br from-bg-elevated to-bg-surface p-6">
    <h2 class="mb-6 flex items-center gap-2 text-lg font-semibold text-text-primary">
      <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-primary/10">
        <div class="h-3 w-3 rounded-full bg-accent-primary" />
      </div>
      {{ strings.analytics.providerChart.title }}
    </h2>

    <!-- Loading State -->
    <div v-if="isLoading" class="flex h-64 items-center justify-center">
      <Loader2 :size="32" class="animate-spin text-text-muted" :stroke-width="2" />
    </div>

    <!-- Error State -->
    <div v-else-if="isError" class="flex h-64 items-center justify-center">
      <p class="text-sm text-status-failed">{{ strings.analytics.providerChart.failedToLoad }}</p>
    </div>

    <!-- Empty State -->
    <div v-else-if="!chartData || chartData.length === 0" class="flex h-64 items-center justify-center">
      <p class="text-sm text-text-muted">{{ strings.analytics.providerChart.noData }}</p>
    </div>

    <!-- Chart -->
    <div v-else class="space-y-4">
      <div
        v-for="(provider, index) in chartData"
        :key="provider.provider"
        class="group"
        :style="{ animationDelay: `${index * 100}ms` }"
        style="animation: slideInRight 0.6s cubic-bezier(0.16, 1, 0.3, 1) backwards"
      >
        <!-- Provider Header (Clickable if has multiple models) -->
        <div
          class="mb-2 flex items-center justify-between rounded-lg px-2 py-1 -mx-2 transition-colors"
          :class="provider.hasModels ? 'cursor-pointer hover:bg-bg-surface-hover' : ''"
          @click="provider.hasModels && toggleProvider(provider.provider)"
        >
          <div class="flex items-center gap-2">
            <div
              class="h-3 w-3 rounded-full transition-transform duration-300 group-hover:scale-125"
              :class="provider.color.bar"
            />
            <span class="font-medium" :class="provider.color.text">
              {{ provider.provider }}
            </span>
            <span v-if="provider.hasModels" class="text-xs text-text-muted">
              ({{ provider.models.length }} {{ strings.analytics.providerChart.models }})
            </span>
            <!-- Expand/Collapse Icon -->
            <component
              :is="isExpanded(provider.provider) ? ChevronDown : ChevronRight"
              v-if="provider.hasModels"
              :size="16"
              class="text-text-muted transition-transform"
            />
          </div>
          <div class="flex items-center gap-3 text-sm">
            <span class="text-text-secondary">
              {{ provider.total_tokens.toLocaleString() }} {{ strings.analytics.providerChart.tokens }}
            </span>
            <span class="font-mono font-semibold" :class="provider.color.text">
              {{ provider.percentage.toFixed(1) }}%
            </span>
          </div>
        </div>

        <!-- Provider Bar -->
        <div class="relative h-3 overflow-hidden rounded-full" :class="provider.color.bg">
          <div
            class="h-full rounded-full transition-all duration-1000 ease-out"
            :class="provider.color.bar"
            :style="{ width: `${provider.percentage}%` }"
          >
            <!-- Shimmer effect -->
            <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent shimmer" />
          </div>
        </div>

        <!-- Model Breakdown (Expanded) -->
        <div
          v-if="provider.hasModels && isExpanded(provider.provider)"
          class="mt-3 ml-6 space-y-2 border-l-2 border-border-subtle pl-4"
        >
          <div
            v-for="model in provider.models"
            :key="model.model"
            class="flex items-center justify-between text-sm"
          >
            <div class="flex items-center gap-2">
              <div class="h-1.5 w-1.5 rounded-full" :class="provider.color.bar" />
              <span class="text-text-secondary font-mono text-xs">
                {{ model.model }}
              </span>
            </div>
            <div class="flex items-center gap-3">
              <span class="text-text-muted text-xs">
                {{ model.total_tokens.toLocaleString() }} {{ strings.analytics.providerChart.tokens }}
              </span>
              <span class="font-mono text-xs" :class="provider.color.text">
                {{ model.percentage.toFixed(1) }}%
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Total -->
      <div class="border-t border-border-subtle pt-4 mt-6">
        <div class="flex items-center justify-between text-sm">
          <span class="font-medium text-text-primary">{{ strings.analytics.providerChart.totalUsage }}</span>
          <span class="font-mono font-semibold text-accent-primary">
            {{ totalTokens.toLocaleString() }} {{ strings.analytics.providerChart.tokens }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

@keyframes shimmer {
  0% {
    transform: translateX(-100%);
  }
  100% {
    transform: translateX(100%);
  }
}

.shimmer {
  animation: shimmer 2s infinite;
}
</style>
